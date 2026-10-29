"""Turn a long video's saved script into a Plainsight Media article."""
from __future__ import annotations

import argparse
import json

from .common import OUT_DIR, Channel, Claude, CostGuard, load_persona, now_iso, slugify
from .db import DB
from .script import BANNED_TITLE

ARTICLE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "excerpt", "body_md", "slug"],
    "properties": {key: {"type": "string"} for key in ("title", "excerpt", "body_md", "slug")},
}


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
    closing = f"Follow [{channel.name}](https://www.youtube.com/@{channel.handle}) for more."
    if dry_run:
        paragraphs = script.get("script", [])
        data = {"title": script["title"], "excerpt": "Local preview article from the fixture script.",
                "slug": slugify(script["title"]),
                "body_md": "{{YOUTUBE}}\n\n" + "\n\n".join(paragraphs) + "\n\n" + closing}
    else:
        if not CostGuard(db).check("article", est_usd=0.5):
            raise RuntimeError("Article skipped by budget guard")
        claude = claude or Claude(db, channel=channel)
        if claude.channel.key != channel.key:
            raise ValueError("Claude channel does not match article channel")
        claude.persona = load_persona(channel)
        data, _ = claude.run(
            "article",
            "Adapt this video script into a standalone 700-1000 word Markdown article for Plainsight Media. "
            "Write in this channel's persona. Use descriptive headings and clear paragraphs, preserve source "
            "links and factual caveats, and invent no facts, quotes or sources. No income promises or medical, "
            "legal or financial advice. Return title, short excerpt, body_md and a lowercase hyphenated slug. "
            "Include exactly one {{YOUTUBE}} placeholder on its own line. "
            f"End with this exact line: {closing}\n\n" + json.dumps(script, ensure_ascii=False),
            schema=ARTICLE_SCHEMA, effort="medium", max_tokens=6000, content_id=content_id,
        )
        if BANNED_TITLE.search(data["title"]):
            raise ValueError("Article title failed the policy guardrail")
        if data["body_md"].count("{{YOUTUBE}}") != 1:
            raise ValueError("Article must contain one YouTube placeholder")
        words = len(data["body_md"].split())
        if not 400 <= words <= 1600:
            raise ValueError(f"Article length out of range ({words} words)")
        if not data["body_md"].rstrip().endswith(closing):
            data["body_md"] = data["body_md"].rstrip() + "\n\n" + closing
    row = {
        "id": content_id, "content_id": content_id, "channel": channel.key,
        # Content id makes slugs stable and unique across channels and similar titles.
        "slug": existing["slug"] if existing else f"{slugify(data['slug'])}-{content_id}",
        "title": data["title"], "excerpt": data["excerpt"], "body_md": data["body_md"],
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
