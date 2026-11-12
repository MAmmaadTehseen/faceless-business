"""Turn a long video's saved script into a Plainsight Media article."""
from __future__ import annotations

import argparse
import copy
import uuid
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
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


def repair_article(data):
    """Normalize presentation without inventing claims or moving prose out of context."""
    data = copy.deepcopy(data)
    def clean(value):
        if isinstance(value, str):
            return re.sub(r"[\u2013\u2014]", ", ", value)
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        return value
    data = clean(data)
    small = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
    def title(text):
        index = 0
        def word(match):
            nonlocal index
            w = match.group()
            result = w if index and w in small else w[0].upper() + w[1:]
            index += 1
            return result
        return re.sub(r"[A-Za-z0-9]+", word, text)
    data["title"] = title(data["title"])
    data["slug"] = slugify(data["slug"] or data["title"], max_len=60)
    def clip(text, limit):
        if len(text) <= limit:
            return text
        prefix = text[:limit + 1]
        return prefix.rsplit(" ", 1)[0].rstrip(" ,;:") if " " in prefix else text[:limit]
    for field, limit in (("meta_title", 65), ("meta_description", 165)):
        data[field] = clip(data[field].strip(), limit)
    for section in data["sections"]:
        section["heading"] = title(section["heading"])
        section["body_md"] = re.sub(r"^### (.+)$", lambda m: "### " + title(m[1]), section["body_md"], flags=re.M)
    # Normalize spelling only at existing occurrences; never fabricate keyword prose.
    keyword = data["primary_keyword"].strip()
    data["primary_keyword"] = keyword
    if keyword:
        for section in data["sections"]:
            section["body_md"] = re.sub(re.escape(keyword), lambda _: keyword, section["body_md"], flags=re.I)
    body = assemble_body(data)
    data["entities"] = [e for e in data["entities"] if e.strip() and e.casefold() in body.casefold()]
    return data


# Editorial targets are useful diagnostics, not reasons to buy another draft.
EDITORIAL_TARGETS = (
    "Primary keyword must", "Preserve exact keyword", "Keep keyword", "Meta title must differ",
    "Meta title is almost", "Self QA must", "Intro needs", "Quick Answer needs", "FAQ ",
)


def article_checks(data, body):
    errors, warnings = [], []
    for message in validation_errors(data, body):
        (warnings if message.startswith(EDITORIAL_TARGETS) else errors).append(message)
    # Reject genuinely empty or insubstantial summaries/answers despite editorial tolerance.
    for field, minimum, maximum in (("intro_md", 75, 130), ("quick_answer", 25, 50)):
        count = len(data[field].split())
        if not minimum <= count <= maximum:
            errors.append(f"{field} needs {minimum}-{maximum} words (got {count})")
    for i, faq in enumerate(data["faqs"]):
        count = len(faq["answer"].split())
        if not 30 <= count <= 75:
            errors.append(f"faqs answer {i+1} needs 30-75 words (got {count})")
    # Explicit FAIL is a quality concern; missing checkbox boilerplate is not.
    if any(q.lstrip().upper().startswith("FAIL") for q in data.get("self_qa", [])):
        errors.append("self_qa reports an unresolved quality failure")
    if not data["primary_keyword"].strip() or not data["meta_title"].strip() or not data["meta_description"].strip():
        errors.append("Metadata and primary_keyword must be nonempty")
    return errors, warnings


def failed_fields(failures):
    """Top-level patch schema reuses the original field definitions."""
    fields = set()
    for error in failures:
        lower = error.lower()
        if "faq" in lower:
            fields.add("faqs")
        elif "intro_md" in lower:
            fields.add("intro_md")
        elif "quick_answer" in lower:
            fields.add("quick_answer")
        elif "cta" in lower:
            fields.add("cta_md")
        elif "title failed" in lower:
            fields.add("title")
        elif "takeaways" in lower:
            fields.add("key_takeaways")
        elif "self_qa" in lower:
            fields.add("self_qa")
        elif "metadata" in lower:
            fields.update(("primary_keyword", "meta_title", "meta_description"))
        else:
            fields.add("sections")
    return sorted(fields)


def save_article_failure(content_id, attempt, raw, repaired, failures, warnings):
    directory = OUT_DIR / "article-failures"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slugify(content_id, max_len=120)}-{uuid.uuid4().hex}-attempt-{attempt}.json"
    path.write_text(json.dumps({"content_id": content_id, "attempt": attempt,
        "raw": raw, "repaired": repaired, "failures": failures, "warnings": warnings},
        ensure_ascii=False, indent=2) + "\n")
    return path


def sharing_summary(excerpt: str) -> str | None:
    if len(excerpt) <= 160:
        return None
    prefix = excerpt[:159]
    if not excerpt[159].isspace() and not prefix[-1].isspace():
        prefix = prefix.rsplit(" ", 1)[0] if " " in prefix else ""
    return prefix.rstrip() + "…"


def article_thumbnail(db, content_id, existing, dry_run):
    """Persist a bucket-relative public image path; offline runs never upload."""
    content = db.one("content", {"id": content_id}) or {}
    candidates = [OUT_DIR / content_id / "thumbnail.jpg", OUT_DIR / content_id / f"{content_id}.jpg"]
    if content.get("thumbnail_path"):
        candidate = (OUT_DIR / content_id / Path(content["thumbnail_path"]).name)
        candidates.insert(0, candidate)
    path = next((p for p in candidates if p.is_file()), candidates[0])
    previous = (existing or {}).get("thumbnail_path")
    if dry_run or not path.is_file() or not getattr(db, "sb", None):
        return previous
    key = f"articles/{content_id}/thumbnail.jpg"
    try:
        db.sb.storage.from_("media").upload(key, path.read_bytes(),
            file_options={"content-type": "image/jpeg", "upsert": "true"})
        return key
    except Exception:
        # Storage failures must not prevent the article from being saved.
        log.warning("Article thumbnail upload failed; keeping existing artwork")
        return previous


def write_article(db: DB, content_id: str, *, claude: Claude | None = None, dry_run: bool = False, force: bool = False, script_data: dict | None = None, prepare_only: bool = False) -> dict:
    # SQLite bootstraps older schemas locally; keep the optional SEO columns compatible.
    if getattr(db, "kind", None) == "sqlite":
        columns = {r[1] for r in db.conn.execute("pragma table_info(articles)")}
        for name in ("summary_for_og", "updated_at", "thumbnail_path"):
            if name not in columns:
                db.conn.execute(f"alter table articles add column {name} text")
    content = db.one("content", {"id": content_id})
    if not content or content["kind"] != "long":
        raise ValueError("Article requires an existing long content row")
    channel = Channel(content.get("channel") or "futurework")
    publication = db.one("publications", {"content_id": content_id, "platform": "youtube"}) or {}
    existing = db.one("articles", {"id": content_id})
    thumbnail_path = None if prepare_only else article_thumbnail(db, content_id, existing, dry_run)
    youtube_id = publication.get("platform_id") or (existing or {}).get("youtube_id")
    # Keep reruns cheap, but pick up a newly available YouTube ID.
    if existing and existing.get("published_at") and not dry_run and not force:
        updates = {"thumbnail_path": thumbnail_path, "youtube_id": youtube_id, "summary_for_og": sharing_summary(existing.get("excerpt") or "")}
        db.update("articles", {"id": content_id}, updates)
        return {**existing, **updates}
    script = script_data if script_data is not None else json.loads((OUT_DIR / content_id / "script.json").read_text())
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
            "No invented sources. Prioritize accurate, useful prose over exact word counts. "
            "Do not emit the YouTube placeholder or duplicate Quick Answer, takeaways or FAQs in sections. "
            "body_md contains paragraphs and optional H3s only; heading is plain text. "
            f"CTA channel URL: https://www.youtube.com/@{channel.handle}\n\n{rules}\n\n"
            + "\nImplementation overrides: keyword position, frequency, title exclusion and near-identical meta titles "
            "are editorial targets only. Natural topic phrasing is allowed. Intro 75-130 words, Quick Answer "
            "25-50 words, FAQ answers 30-75 words are accepted. Code normalizes casing, slugs and metadata lengths.\n"
            + json.dumps(script, ensure_ascii=False)
        )
        restricted_sources = getattr(claude, "provider", "anthropic") == "lunaroute"
        supplied_sources = script.get("supplied_sources", [])
        if restricted_sources and not supplied_sources:
            raise ValueError("LunaRoute article requires saved supplied_sources; restore verified source URLs first")
        schema = ARTICLE_SCHEMA
        previous = None
        for attempt in range(2):
            if not CostGuard(db).check("article", est_usd=0.6):
                raise RuntimeError("Article skipped by budget guard")
            raw, _ = claude.run("article", prompt, schema=schema, effort="medium",
                                web_search=True, max_searches=4, max_tokens=20000, content_id=content_id,
                                **({"supplied_sources": supplied_sources} if restricted_sources else {}))
            merged = {**previous, **{k: raw[k] for k in schema["properties"]}} if previous is not None else raw
            data = repair_article(merged)
            data["body_md"] = assemble_body(data)
            failures, warnings = article_checks(data, data["body_md"])
            if restricted_sources:
                for section in data["sections"]:
                    evidence = section.get("evidence")
                    if evidence and evidence["source_url"] not in supplied_sources:
                        failures.append("Evidence source_url must come from supplied_sources")
            if f"https://www.youtube.com/@{channel.handle}" not in data["cta_md"]:
                failures.append("CTA must link the supplied channel URL")
            for warning in warnings:
                log.warning("Article editorial target: %s", warning)
            if not failures:
                break
            path = save_article_failure(content_id, attempt + 1, raw, data, failures, warnings)
            log.warning("article validation attempt %d: %s; saved %s", attempt + 1, "; ".join(failures), path)
            if attempt:
                raise ValueError("Article validation failed: " + "; ".join(failures) + f"; draft: {path}")
            fields = failed_fields(failures)
            schema = obj({k: ARTICLE_SCHEMA["properties"][k] for k in fields})
            previous = data
            prompt = ("Repair only these failed article fields; return only the requested schema fields. "
                      "Preserve verified claims and sources. No invented evidence.\nFailures:\n" +
                      "\n".join(failures) + f"\nCTA channel URL: https://www.youtube.com/@{channel.handle}\n" +
                      "Failed fields:\n" + json.dumps({k: data[k] for k in fields}, ensure_ascii=False) +
                      "\nTopic: " + script["title"])
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
        "takeaways": data["key_takeaways"], "thumbnail_path": thumbnail_path,
        "youtube_id": youtube_id, "published_at": None if dry_run else (existing or {}).get("published_at") or now_iso(),
    }
    candidates = db.select("articles", lte={"published_at": now_iso()})
    related = pick_internal_links(row, candidates)
    links = "\n\n## Further Reading\n\n" + "\n".join(
        f"- [{r['title']}](/a/{r['slug']})" for r in related)
    links += f"\n\nExplore [{channel.name}](/c/{channel.key}).\n\n"
    row["body_md"] = row["body_md"].replace("## Frequently asked questions", links + "## Frequently asked questions")
    if prepare_only:
        row["published_at"] = None
        return row
    saved = db.upsert("articles", row, on="id")
    if not dry_run:
        ping_indexnow(article_slug)
        from .publish.youtube_promotion import article_saved
        article_saved(db, content_id)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_id", help="Long content id with out/<id>/script.json")
    args = parser.parse_args()
    row = write_article(DB(), args.content_id)
    print(f"Article saved: {row['slug']}")


if __name__ == "__main__":
    main()
