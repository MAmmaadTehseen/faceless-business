"""Ten Tongues hub articles, built deterministically from a saved episode (no model calls).

Usage:
  python -m pipeline.words_article --channel tentongues            # dry run: list what would be written
  python -m pipeline.words_article --channel tentongues --apply    # write one article per published episode
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .article import article_thumbnail, pick_internal_links, ping_indexnow, sharing_summary
from .common import Channel, OUT_DIR, log, now_iso, slugify
from .db import DB

# Languages whose word Shorts draw the most views; their "how do you say" questions go in the FAQ.
FAQ_LANGUAGES = ("ru", "ja", "es", "hi", "fr")


def episode_data(db, content_id: str) -> dict | None:
    row = db.one("content", {"id": content_id}) or {}
    try:
        notes = json.loads(row.get("qa_notes") or "{}")
    except (ValueError, TypeError):
        notes = {}
    data = notes.get("words_episode") if isinstance(notes, dict) else None
    saved = OUT_DIR / content_id / "episode.json"
    if not data and saved.is_file():
        data = json.loads(saved.read_text())
    return data


def _instant(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _cell(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def build_article(channel: Channel, data: dict) -> dict:
    """Article fields in the shape pipeline.article.write_article saves."""
    names = {l["code"]: l["name"] for l in channel.cfg["languages"]}
    word = data["word"].strip().lower()
    Word = word.capitalize()
    langs = [(names.get(l["code"], l["code"]), l) for l in data["languages"]]
    listing = ", ".join(n for n, _ in langs[:-1]) + " and " + langs[-1][0]

    def says(name, lang):
        if lang["native"].casefold() == lang["romanisation"].casefold():
            return f"{lang['native']} in {name}"
        return f"{lang['native']} ({lang['romanisation']}) in {name}"

    quick = f"{Word} is " + ", ".join(says(n, l) for n, l in langs[:-1]) + ", and " + says(*langs[-1]) + "."
    glance = "\n".join(["| Language | Word | Romanisation | IPA |", "|---|---|---|---|"] + [
        f"| {_cell(n)} | {_cell(l['native'])} | {_cell(l['romanisation'])} | {_cell(l.get('ipa'))} |" for n, l in langs])
    examples = "\n".join(["| Language | Example | Romanised | English |", "|---|---|---|---|"] + [
        f"| {_cell(n)} | {_cell(l['example_native'])} | {_cell(l['example_romanised'])} | {_cell(l['example_english'])} |"
        for n, l in langs])
    sections = []
    for n, l in langs:
        ipa = f", {l['ipa']}" if l.get("ipa") else ""
        sections.append(
            f"## How to say {word} in {n}\n\n**{l['native']}** ({l['romanisation']}{ipa}).\n\n"
            f"Example: {l['example_native']} ({l['example_romanised']}) means \"{l['example_english']}\"\n\n"
            f"Memory hook: {l['memory_hook']}\n\n{l['cultural_note']}")
    faqs = [{"question": f"How do you say {word} in different languages?", "answer": quick}]
    by_code = {l["code"]: (n, l) for n, l in langs}
    for code in FAQ_LANGUAGES:
        if code in by_code:
            n, l = by_code[code]
            faqs.append({"question": f"How do you say {word} in {n}?",
                         "answer": f"{Word} in {n} is {l['native']}, pronounced {l['romanisation']}"
                                   + (f" ({l['ipa']})" if l.get("ipa") else "")
                                   + f". Example: {l['example_native']} ({l['example_romanised']}) means \"{l['example_english']}\""})
    takeaways = [f"{n}: {l['memory_hook']}" for n, l in langs[:3]]
    cta = (f"Ten Tongues teaches one everyday English word a day in ten languages. "
           f"Subscribe to [{channel.name}](https://www.youtube.com/@{channel.handle}) for tomorrow's word.")
    if channel.cfg.get("tts_attribution"):
        cta += "\n\n" + channel.cfg["tts_attribution"]
    intro = (f"How do you say {word} in {listing}? Here is the word in each language's own script, "
             f"with a learner romanisation, IPA, an everyday example sentence, a memory hook and one usage note. "
             + data.get("description", "").strip()).strip()
    body = "\n\n".join([
        intro, "## Quick Answer\n\n" + quick,
        "## Key Takeaways\n\n" + "\n".join("- " + t for t in takeaways), "{{YOUTUBE}}",
        f"## {Word} in 10 languages at a glance\n\n" + glance,
        f"## {Word} in example sentences\n\n" + examples, *sections, cta,
        "## Frequently asked questions\n\n" + "\n\n".join(f"### {f['question']}\n\n{f['answer']}" for f in faqs)])
    excerpt = (f"How to say {word} in {listing}: native script, pronunciation, IPA "
               f"and an everyday example sentence for each.")
    return {
        "title": f"{word.upper()} in 10 languages", "slug": f"how-to-say-{word}-in-10-languages",
        "meta_title": f"How to say {word} in 10 languages, with pronunciation"[:70],
        "meta_description": (f"{Word} in {listing}, with native script, romanisation, IPA and example sentences.")[:160],
        "primary_keyword": f"{word} in different languages", "excerpt": excerpt,
        "quick_answer": quick, "key_takeaways": takeaways, "faqs": faqs, "body_md": body,
        "entities": [Word, *(n for n, _ in langs)],
    }


def write_words_article(db, content_id: str, *, share: bool = True) -> dict | None:
    """Save the hub article for a published Ten Tongues episode; None when it is not ready."""
    content = db.one("content", {"id": content_id})
    if not content or content.get("kind") != "long":
        raise ValueError("Article requires an existing long content row")
    channel = Channel(content["channel"])
    if channel.cfg.get("format") != "words":
        raise ValueError(f"{channel.key} is not a words-format channel")
    publication = db.one("publications", {"content_id": content_id, "platform": "youtube"}) or {}
    youtube_id = publication.get("platform_id")
    data = episode_data(db, content_id)
    if not youtube_id or not data:
        log.info("words article %s: %s", content_id, "no YouTube id yet" if data else "no saved episode")
        return None
    data = build_article(channel, data)
    existing = db.one("articles", {"id": content_id})
    if existing:
        slug = existing["slug"]
    else:
        slug = base = slugify(data["slug"], max_len=60).strip("-")
        suffix = 2
        while db.one("articles", {"slug": slug}):
            slug = f"{base[:60 - len(str(suffix)) - 1].rstrip('-')}-{suffix}"
            suffix += 1
    row = {
        "id": content_id, "content_id": content_id, "channel": channel.key, "slug": slug,
        "summary_for_og": sharing_summary(data["excerpt"]), "updated_at": now_iso(),
        "title": data["title"], "excerpt": data["excerpt"], "body_md": data["body_md"],
        **{k: data[k] for k in ("meta_title", "meta_description", "primary_keyword", "faqs", "entities", "quick_answer")},
        "takeaways": data["key_takeaways"], "thumbnail_path": article_thumbnail(db, content_id, existing, False),
        # Scheduled episodes: the hub shows the article when the video goes public, not before.
        "youtube_id": youtube_id, "published_at": (existing or {}).get("published_at")
        or max(now_iso(), publication.get("publish_at") or "", key=_instant),
    }
    related = pick_internal_links(row, db.select("articles", lte={"published_at": now_iso()}))
    links = "\n\n## Further Reading\n\n" + "\n".join(f"- [{r['title']}](/a/{r['slug']})" for r in related) if related else ""
    links += f"\n\nExplore [{channel.name}](/c/{channel.key}).\n\n"
    row["body_md"] = row["body_md"].replace("## Frequently asked questions", links + "## Frequently asked questions")
    saved = db.upsert("articles", row, on="id")
    ping_indexnow(slug)
    from .publish.youtube_promotion import article_saved
    article_saved(db, content_id)
    if share:
        from .publish.hub_share import share_article_to_facebook
        share_article_to_facebook(db, row, channel)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="tentongues")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = DB()
    for row in db.select("content", {"channel": args.channel, "kind": "long"}, order="created_at"):
        pub = db.one("publications", {"content_id": row["id"], "platform": "youtube"}) or {}
        if not pub.get("platform_id"):
            continue
        if not args.apply:
            print("would write", row["id"], pub["platform_id"])
            continue
        # Sync shares older articles to Facebook one per Page per day; the backfill does not post.
        saved = write_words_article(db, row["id"], share=False)
        print("saved" if saved else "skipped", row["id"], (saved or {}).get("slug", ""))


if __name__ == "__main__":
    main()
