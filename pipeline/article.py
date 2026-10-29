"""Turn a long video's saved script into a Plainsight Media article."""
from __future__ import annotations

import argparse
import json
import re
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
    headings = [data["title"], *re.findall(r"^#{1,6}\s+(.+)$", body, re.M)]
    check(bool(keyword) and all(keyword not in h.casefold() for h in headings)
          and keyword not in data["intro_md"].casefold(), "Keep keyword out of headings and intro")
    if keyword and keyword in body.casefold():
        position = len(body[:body.casefold().index(keyword)].split())
        check(350 <= position <= 800, f"Place keyword around word 500 (currently {position})")
    check(90 <= len(data["intro_md"].split()) <= 110, "Intro needs 90-110 words")
    check(30 <= len(data["quick_answer"].split()) <= 40, "Quick Answer needs 30-40 words")
    check(4 <= len(data["key_takeaways"]) <= 5, "Use 4-5 takeaways")
    check(not BANNED_TITLE.search(data["title"]), "Title failed policy guardrail")
    check(body.count("{{YOUTUBE}}") == 1, "Use only the code-generated YouTube embed")
    return errors


def write_article(db: DB, content_id: str, *, claude: Claude | None = None, dry_run: bool = False) -> dict:
    content = db.one("content", {"id": content_id})
    if not content or content["kind"] != "long":
        raise ValueError("Article requires an existing long content row")
    channel = Channel(content.get("channel") or "futurework")
    script = json.loads((OUT_DIR / content_id / "script.json").read_text())
    publication = db.one("publications", {"content_id": content_id, "platform": "youtube"}) or {}
    existing = db.one("articles", {"id": content_id})
    youtube_id = publication.get("platform_id") if publication.get("status") == "live" else None
    # Keep reruns cheap, but pick up a newly available YouTube ID.
    if existing and existing.get("published_at") and not dry_run:
        db.update("articles", {"id": content_id}, {"youtube_id": youtube_id})
        return {**existing, "youtube_id": youtube_id}
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
            if not CostGuard(db).check("article", est_usd=0.5):
                raise RuntimeError("Article skipped by budget guard")
            data, _ = claude.run("article", prompt, schema=ARTICLE_SCHEMA, effort="medium",
                                 web_search=True, max_searches=4, max_tokens=10000, content_id=content_id)
            data["body_md"] = assemble_body(data)
            failures = validation_errors(data, data["body_md"])
            if not failures:
                break
            log.warning("article validation attempt %d: %s", attempt + 1, "; ".join(failures))
            if attempt:
                raise ValueError("Article validation failed: " + "; ".join(failures))
            prompt += "\n\nPrevious attempt failed these checks. Correct all on this retry:\n" + "\n".join(failures)
    row = {
        "id": content_id, "content_id": content_id, "channel": channel.key,
        # Content id makes slugs stable and unique across channels and similar titles.
        "slug": existing["slug"] if existing else f"{slugify(data['slug'])}-{content_id}",
        "title": data["title"], "excerpt": data["excerpt"], "body_md": data["body_md"],
        **{k: data[k] for k in ("meta_title", "meta_description", "primary_keyword", "faqs", "entities", "quick_answer")},
        "takeaways": data["key_takeaways"],
        "youtube_id": youtube_id, "published_at": None if dry_run else now_iso(),
    }
    return db.upsert("articles", row, on="id")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_id", help="Long content id with out/<id>/script.json")
    args = parser.parse_args()
    row = write_article(DB(), args.content_id)
    print(f"Article saved: {row['slug']}")


if __name__ == "__main__":
    main()
