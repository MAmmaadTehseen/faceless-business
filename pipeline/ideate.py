"""Pick today's topic: user queue first, else Google News RSS for the niche keywords, Claude chooses."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser

from .common import Claude, log

PICK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["chosen_index", "topic", "angle", "why", "runner_ups"],
    "properties": {
        "chosen_index": {"type": "integer", "description": "Index into the candidate list, or -1 if none is worth a video"},
        "topic": {"type": "string", "description": "One-line working topic for the video"},
        "angle": {"type": "string", "description": "The persona's distinct take, 1-2 sentences"},
        "why": {"type": "string"},
        "runner_ups": {"type": "array", "items": {"type": "integer"}, "description": "Up to 3 other candidate indexes worth queuing"},
    },
}


def fetch_news(keywords: list[str], per_kw: int = 12, hours: int = 48) -> list[dict]:
    items, seen = [], set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for kw in keywords:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(kw)}+when:2d&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for e in feed.entries[:per_kw]:
            title = e.get("title", "").strip()
            if not title or title.lower() in seen:
                continue
            published = None
            if e.get("published_parsed"):
                published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                if published < cutoff:
                    continue
            seen.add(title.lower())
            items.append({"headline": title, "url": e.get("link", ""), "source": (e.get("source") or {}).get("title", ""),
                          "published": published.isoformat() if published else None, "keyword": kw})
    log.info("news: %d candidates from %d keywords", len(items), len(keywords))
    return items


def choose_topic(db, claude: Claude) -> dict | None:
    """Returns {topic, angle, source_url, source_headline, queue_id}."""
    queued = db.select("topic_queue", {"status": "queued"}, order="priority", desc=True, limit=1)
    user_items = [q for q in queued if q.get("added_by") == "user"]
    if user_items:
        q = user_items[0]
        log.info("topic from user queue: %s", q["topic"])
        return {"topic": q["topic"], "angle": "", "source_url": q.get("source_url"), "source_headline": q.get("source_headline"), "queue_id": q["id"]}

    keywords = db.setting("niche_keywords", ["artificial intelligence", "AI business"])
    recent = db.select("content", {"kind": "long"}, order="created_at", desc=True, limit=60)
    recent_titles = [r["topic"] for r in recent]
    news = fetch_news(keywords)
    if not news and queued:
        q = queued[0]
        return {"topic": q["topic"], "angle": "", "source_url": q.get("source_url"), "source_headline": q.get("source_headline"), "queue_id": q["id"]}
    if not news:
        return None

    listing = "\n".join(f"[{i}] {n['headline']} ({n['source']}, {n['published'] or 'n/a'})" for i, n in enumerate(news))
    prompt = (
        "Pick the single best candidate for today's long YouTube video for this channel.\n"
        "Criteria, in order: mass appeal beyond insiders; a strong, honest angle the persona can own; "
        "freshness; enough substance for 8-12 minutes; not a duplicate of recent videos.\n"
        "Skip anything that only works as clickbait, anything medical/legal/financial-advice shaped, "
        "and anything the persona's red lines forbid.\n\n"
        f"Recent video topics (avoid repeats):\n- " + "\n- ".join(recent_titles[:40]) + "\n\n"
        f"Candidates:\n{listing}\n"
    )
    pick, _ = claude.run("ideate", prompt, schema=PICK_SCHEMA, effort="medium", max_tokens=3000)
    for idx in pick.get("runner_ups", [])[:3]:
        if 0 <= idx < len(news):
            db.insert("topic_queue", {"topic": news[idx]["headline"], "source_url": news[idx]["url"],
                                      "source_headline": news[idx]["headline"], "priority": 1, "added_by": "claude"})
    i = pick["chosen_index"]
    if i < 0 or i >= len(news):
        if queued:
            q = queued[0]
            return {"topic": q["topic"], "angle": "", "source_url": q.get("source_url"), "source_headline": q.get("source_headline"), "queue_id": q["id"]}
        return None
    src = news[i]
    log.info("topic: %s | angle: %s", pick["topic"], pick["angle"])
    return {"topic": pick["topic"], "angle": pick["angle"], "source_url": src["url"], "source_headline": src["headline"], "queue_id": None}
