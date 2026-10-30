"""Turn a long video's saved script into a Plainsight Media article."""
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
import requests
from urllib.parse import urlparse

import tldextract

from .common import ROOT, log, OUT_DIR, Channel, Claude, CostGuard, load_persona, now_iso, slugify
from .db import DB
from .script import BANNED_TITLE

# Use the bundled Public Suffix List, without network requests or cache writes.
DOMAIN_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

def obj(properties, required=None):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties) if required is None else required}


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}
EVIDENCE = obj({k: STRING for k in ("label", "text", "source_url", "source_name")})
ARTICLE_SCHEMA = obj({
    **{k: STRING for k in ("title", "primary_keyword", "slug", "meta_title", "meta_description",
                           "excerpt", "intro_md", "quick_answer", "cta_md")},
    "key_takeaways": STRINGS,
    "sections": {"type": "array", "items": obj({"heading": STRING, "body_md": STRING,
        "evidence": {"anyOf": [EVIDENCE, {"type": "null"}]}}, ["heading", "body_md"])},
    "faqs": {"type": "array", "items": obj({"question": STRING, "answer": STRING})},
    "entities": STRINGS, "self_qa": STRINGS,
})


def assemble_body(data):
    parts = [data["intro_md"], "## Quick Answer\n\n" + data["quick_answer"],
             "## Key Takeaways\n\n" + "\n".join("- " + t for t in data["key_takeaways"]), "{{YOUTUBE}}"]
    for section in data["sections"]:
        paragraphs = section["body_md"].strip().split("\n\n", 1)
        text = paragraphs[0]
        evidence = section.get("evidence")
        if evidence:
            box = (f"**{evidence['label']}**: {evidence['text']}\n\n"
                   f"[Source: {evidence['source_name']}]({evidence['source_url']})")
            text += "\n\n" + "\n".join("> " + line for line in box.splitlines())
        if len(paragraphs) > 1:
            text += "\n\n" + paragraphs[1]
        parts.append("## " + section["heading"] + "\n\n" + text)
    parts += [data["cta_md"], "## Frequently asked questions\n\n" + "\n\n".join(
        "### " + f["question"] + "\n\n" + f["answer"] for f in data["faqs"])]
    return "\n\n".join(parts)


def pick_internal_links(current, candidates, limit=3):
    """Prefer channel peers, then shared entities/search terms, with stable ties."""
    def tokens(row):
        return set(re.findall(r"[a-z0-9]{3,}", " ".join([row.get("title") or "", row.get("primary_keyword") or "", *(row.get("entities") or [])]).casefold()))
    target = tokens(current)
    eligible = [r for r in candidates if r.get("published_at") and r.get("id") != current.get("id")]
    return sorted(eligible, key=lambda r: (r.get("channel") != current.get("channel"),
                  -len(target & tokens(r)), r.get("slug", "")))[:limit]


INDEXNOW_KEY = "93f0a1c87d624b56a902e13dfe6748ca"


def ping_indexnow(slug):
    try:
        response = requests.post("https://www.bing.com/indexnow", json={
            "host": "hub.ammaad.online", "key": INDEXNOW_KEY,
            "keyLocation": f"https://hub.ammaad.online/{INDEXNOW_KEY}.txt",
            "urlList": [f"https://hub.ammaad.online/a/{slug}"]}, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        log.warning("IndexNow notification failed; article remains saved")


def validation_errors(data, body):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    check(not re.search(r"[\u2013\u2014]", json.dumps(data, ensure_ascii=False)), "Remove all em/en dashes")
    check(4 <= len(data["sections"]) <= 6, "Use 4-6 sections")
    check(len(data["faqs"]) == 5, "Use exactly 5 FAQs")
    for i, faq in enumerate(data["faqs"]):
        check(40 <= len(faq["answer"].split()) <= 60, f"FAQ {i+1} needs 40-60 words")
    check(len(data["meta_title"]) <= 65, "Meta title exceeds 65 characters")
    check(data["meta_title"].casefold() != data["title"].casefold(), "Meta title must differ from H1")
    check(len(data["meta_description"]) <= 165, "Meta description exceeds 165 characters")
    boxes = [s["evidence"] for s in data["sections"] if s.get("evidence")]
    check(3 <= len(boxes) <= 4, "Use 3-4 evidence boxes")
    domains = []
    for box in boxes:
        try:
            url = urlparse(box["source_url"])
            valid_url = url.scheme in ("http", "https") and bool(url.hostname)
            domain = DOMAIN_EXTRACT(box["source_url"]).top_domain_under_public_suffix if valid_url else ""
        except ValueError:
            valid_url, domain = False, ""
        check(valid_url, "Evidence requires an http(s) URL")
        domains.append(domain)
        check(box["label"] in ("Fact", "Important", "Do You Know", "Stat", "Pro Tip"), "Invalid evidence label")
    check(all(domains) and len(set(domains)) == len(domains), "Evidence needs distinct registered domains")
    keyword = data["primary_keyword"].strip().casefold()
    check(bool(keyword) and body.casefold().count(keyword) == 1, "Primary keyword must appear exactly once in body")
    check(data["primary_keyword"].strip() in body, "Preserve exact keyword spelling and capitalization")
    headings = [data["title"], *re.findall(r"^#{1,6}\s+(.+)$", body, re.M)]
    check(bool(keyword) and all(keyword not in h.casefold() for h in headings)
          and keyword not in data["intro_md"].casefold(), "Keep keyword out of headings and intro")
    if keyword and keyword in body.casefold():
        position = len(body[:body.casefold().index(keyword)].split())
        check(450 <= position <= 600, "Primary keyword must start at words 450-600")
    check(len(data["cta_md"].strip().split("\n\n")) == 2, "CTA needs two paragraphs")
    check(bool(re.search(r"\[[^]]+\]\(https://www\.youtube\.com/@[^)]+\)", data["cta_md"])), "CTA needs channel YouTube link")
    check(all(word in data["cta_md"].casefold() for word in ("watch", "subscribe")), "CTA must invite watch and subscribe")
    check(SequenceMatcher(None, data["title"].casefold(), data["meta_title"].casefold()).ratio() < .85, "Meta title is almost identical to H1")
    check(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["slug"])) and len(data["slug"]) <= 60, "Slug needs lowercase hyphenated words, at most 60 characters")
    check(len({s["heading"].casefold() for s in data["sections"]}) == len(data["sections"]), "Section headings must be distinct")
    small = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
    def title_case(text):
        return all(w[0].isupper() or (i > 0 and w in small) or w[0].isdigit()
                   for i, w in enumerate(re.findall(r"[A-Za-z0-9]+", text)))
    check(title_case(data["title"]), "H1 needs Title Case")
    for section in data["sections"]:
        subheads = re.findall(r"^### (.+)$", section["body_md"], re.M)
        check(len(subheads) <= 2, "At most two H3s per section")
        check(title_case(section["heading"]) and all(title_case(h) for h in subheads), "Headings need Title Case")
        check(not re.search(r"^#{1,2} |^#{4,6} ", section["body_md"], re.M), "Section body permits only H3 headings")
        if section.get("evidence"):
            check(len(section["body_md"].strip().split("\n\n", 1)) == 2, "Evidence needs first paragraph and continuation")
        if keyword and keyword in section["body_md"].casefold():
            check(section is not data["sections"][-1], "Keep keyword out of last body section")
    names = [re.sub(r"\W+", "", b["source_name"].casefold()) for b in boxes]
    check(all(names) and len(set(names)) == len(names), "Evidence needs distinct organizations")
    check(all(e.strip() and e.casefold() in body.casefold() for e in data["entities"]), "Entities must occur in article")
    check(bool(data.get("self_qa")) and all(q.startswith("PASS") for q in data.get("self_qa", [])), "Self QA must contain only PASS results")
    tables = list(re.finditer(r"^\s*\|?.+\|.+\n\s*\|?\s*:?-{3,}", body, re.M))
    check(len(tables) <= 1, "At most one table")
    if tables:
        start = tables[0].start()
        after = body[tables[0].end():].split("\n\n", 1)
        check(bool(body[:start].strip()) and len(after) == 2 and bool(after[1].strip()), "Table needs introduction and takeaway")
    check(not re.search(r"!\[\s*\]\(", body), "Images need descriptive alt text")
    check(90 <= len(data["intro_md"].split()) <= 110, "Intro needs 90-110 words")
    check(30 <= len(data["quick_answer"].split()) <= 40, "Quick Answer needs 30-40 words")
    check(4 <= len(data["key_takeaways"]) <= 5, "Use 4-5 takeaways")
    check(not BANNED_TITLE.search(data["title"]), "Title failed policy guardrail")
    check(body.count("{{YOUTUBE}}") == 1, "Use only the code-generated YouTube embed")
    return errors


def sharing_summary(excerpt: str) -> str | None:
    if len(excerpt) <= 160:
        return None
    prefix = excerpt[:159]
    if not excerpt[159].isspace() and not prefix[-1].isspace():
        prefix = prefix.rsplit(" ", 1)[0] if " " in prefix else ""
    return prefix.rstrip() + "…"


def write_article(db: DB, content_id: str, *, claude: Claude | None = None, dry_run: bool = False, force: bool = False) -> dict:
    # SQLite bootstraps older schemas locally; keep the optional SEO columns compatible.
    if getattr(db, "kind", None) == "sqlite":
        columns = {r[1] for r in db.conn.execute("pragma table_info(articles)")}
        for name in ("summary_for_og", "updated_at"):
            if name not in columns:
                db.conn.execute(f"alter table articles add column {name} text")
    content = db.one("content", {"id": content_id})
    if not content or content["kind"] != "long":
        raise ValueError("Article requires an existing long content row")
    channel = Channel(content.get("channel") or "futurework")
    script = json.loads((OUT_DIR / content_id / "script.json").read_text())
    publication = db.one("publications", {"content_id": content_id, "platform": "youtube"}) or {}
    existing = db.one("articles", {"id": content_id})
    youtube_id = publication.get("platform_id") if publication.get("status") == "live" else None
    # Keep reruns cheap, but pick up a newly available YouTube ID.
    if existing and existing.get("published_at") and not dry_run and not force:
        updates = {"youtube_id": youtube_id, "summary_for_og": sharing_summary(existing.get("excerpt") or "")}
        db.update("articles", {"id": content_id}, updates)
        return {**existing, **updates}
    if dry_run:
        # Offline fixture path deliberately avoids API calls and research claims.
        data = {"title": script["title"], "excerpt": "Local preview article from the fixture script.",
                "slug": slugify(script["title"]), "meta_title": "Preview: " + script["title"][:56],
                "meta_description": "An offline preview of this channel's educational video.",
                "primary_keyword": "", "faqs": [], "entities": [], "quick_answer": "",
                "key_takeaways": [], "intro_md": "Offline fixture preview.",
                "sections": [{"heading": "Video Preview", "body_md": "\n\n".join(script.get("script", []))}],
                "cta_md": f"Watch the embedded video for the full explanation.\n\nSubscribe to [{channel.name}](https://www.youtube.com/@{channel.handle})."}
        data["body_md"] = assemble_body(data)
    else:
        claude = claude or Claude(db, channel=channel)
        if claude.channel.key != channel.key:
            raise ValueError("Claude channel does not match article channel")
        claude.persona = load_persona(channel)
        rules = (ROOT / "persona" / "blog-rules.md").read_text()
        prompt = (
            "Adapt this saved video script into a standalone educational Plainsight Media article. "
            "Follow ALL these writing rules and return the structured fields, not an assembled body. "
            "Use web search (at most four searches) to verify evidence URLs and the precise claims they support. "
            "No invented sources. Write enough section text to place the keyword near word 500. "
            "Do not emit the YouTube placeholder or duplicate Quick Answer, takeaways or FAQs in sections. "
            "body_md contains paragraphs and optional H3s only; heading is plain text. "
            f"CTA channel URL: https://www.youtube.com/@{channel.handle}\n\n{rules}\n\n"
            + json.dumps(script, ensure_ascii=False)
        )
        for attempt in range(2):
            if not CostGuard(db).check("article", est_usd=0.6):
                raise RuntimeError("Article skipped by budget guard")
            data, _ = claude.run("article", prompt, schema=ARTICLE_SCHEMA, effort="medium",
                                 web_search=True, max_searches=4, max_tokens=20000, content_id=content_id)
            data["body_md"] = assemble_body(data)
            failures = validation_errors(data, data["body_md"])
            if f"https://www.youtube.com/@{channel.handle}" not in data["cta_md"]:
                failures.append("CTA must link the supplied channel URL")
            if not failures:
                break
            log.warning("article validation attempt %d: %s", attempt + 1, "; ".join(failures))
            if attempt:
                raise ValueError("Article validation failed: " + "; ".join(failures))
            prompt += "\n\nPrevious attempt failed these checks. Correct all on this retry:\n" + "\n".join(failures)
    # Preserve all existing URLs; new URLs use short readable slugs with numeric collision suffixes.
    if existing:
        article_slug = existing["slug"]
    else:
        base_slug = slugify(data["slug"], max_len=60).strip("-") or "story"
        article_slug = base_slug
        suffix = 2
        while db.one("articles", {"slug": article_slug}):
            tail = f"-{suffix}"
            article_slug = base_slug[:60 - len(tail)].rstrip("-") + tail
            suffix += 1
    row = {
        "id": content_id, "content_id": content_id, "channel": channel.key,
        "slug": article_slug, "summary_for_og": sharing_summary(data["excerpt"]), "updated_at": now_iso(),
        "title": data["title"], "excerpt": data["excerpt"], "body_md": data["body_md"],
        **{k: data[k] for k in ("meta_title", "meta_description", "primary_keyword", "faqs", "entities", "quick_answer")},
        "takeaways": data["key_takeaways"],
        "youtube_id": youtube_id, "published_at": None if dry_run else (existing or {}).get("published_at") or now_iso(),
    }
    candidates = db.select("articles", lte={"published_at": now_iso()})
    related = pick_internal_links(row, candidates)
    links = "\n\n## Further Reading\n\n" + "\n".join(
        f"- [{r['title']}](/a/{r['slug']})" for r in related)
    links += f"\n\nExplore [{channel.name}](/c/{channel.key}).\n\n"
    row["body_md"] = row["body_md"].replace("## Frequently asked questions", links + "## Frequently asked questions")
    saved = db.upsert("articles", row, on="id")
    if not dry_run:
        ping_indexnow(article_slug)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_id", help="Long content id with out/<id>/script.json")
    args = parser.parse_args()
    row = write_article(DB(), args.content_id)
    print(f"Article saved: {row['slug']}")


if __name__ == "__main__":
    main()
