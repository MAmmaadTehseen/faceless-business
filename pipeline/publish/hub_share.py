"""Share hub articles as Facebook Page link posts (growth log 2026-11-16).

Facebook Pages with no followers get nothing from Reels alone, and the hub gets
no traffic without someone linking to it. Every published hub article becomes
one link post on its channel's Page: new articles immediately after they are
saved, older ones backfilled by sync at most one per Page per UTC day.
No model calls. Settings:
  fb_article_posts_enabled      JSON boolean, default true
  fb_article_post_<article id>  {"post_id": ..., "at": iso} once shared (also records skips)
  fb_article_post_day_<channel> last UTC day a backfill post went out
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from ..common import Channel, log, now_iso
from . import meta

HUB = "https://hub.ammaad.online"


def article_url(article: dict) -> str:
    return f"{HUB}/a/{article['slug']}"


def _sentences(text: str, limit: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return " ".join(p for p in parts[:limit] if p).strip()


def article_post_message(article: dict, channel: Channel) -> str:
    """Title, the article's own quick answer (or excerpt), a question and the link."""
    body = _sentences(article.get("quick_answer") or article.get("excerpt") or "", 2)
    question = channel.cfg.get("caption_question") or "What do you think?"
    tags = " ".join(f"#{t}" for t in (channel.cfg.get("hashtags") or [])[:2])
    lines = [str(article.get("title") or "").strip(), "", body, "", question, "", f"Read the full story: {article_url(article)}"]
    if tags:
        lines += ["", tags]
    text = "\n".join(lines).replace("\n\n\n", "\n\n").strip()
    return text[:5000]


def shared_marker(db, article_id: str) -> dict | None:
    v = db.setting(f"fb_article_post_{article_id}")
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return {"post_id": v}
    return v if isinstance(v, dict) else None


def is_live(article: dict) -> bool:
    """The hub serves an article only once published_at has passed (scheduled episodes are future-dated)."""
    try:
        when = datetime.fromisoformat(str(article.get("published_at")).replace("Z", "+00:00"))
    except ValueError:
        return False
    return when <= datetime.now(timezone.utc)


def share_article_to_facebook(db, article: dict, channel: Channel, *, dry_run: bool = False) -> str | None:
    """Post one link post for a published article. Idempotent via settings; never raises."""
    if not article.get("published_at") or not is_live(article):
        return None
    if db.setting("fb_article_posts_enabled", True) is False:
        return None
    if shared_marker(db, article["id"]):
        return None
    meta.use_channel(channel)
    if not meta.fb_configured():
        log.info("fb share skipped for %s: Facebook not configured for %s", article["id"], channel.key)
        return None
    message = article_post_message(article, channel)
    if dry_run:
        log.info("fb share dry run %s:\n%s", article["id"], message)
        return None
    try:
        post = meta.publish_facebook_link_post(message, article_url(article))
    except Exception as e:  # never block article saving or sync
        log.warning("fb share failed for %s: %s", article["id"], e)
        return None
    db.set_setting(f"fb_article_post_{article['id']}", {"post_id": post["id"], "at": now_iso(), "url": post.get("url")})
    log.info("fb share: %s -> %s", article["id"], post.get("url") or post["id"])
    return post["id"]


def backfill_articles(db, channel: Channel, *, max_per_day: int = 1) -> int:
    """Share the newest unshared published articles, at most max_per_day per Page per UTC day."""
    if db.setting("fb_article_posts_enabled", True) is False:
        return 0
    today = datetime.now(timezone.utc).date().isoformat()
    key = f"fb_article_post_day_{channel.key}"
    state = db.setting(key) or {}
    if isinstance(state, str):
        state = {"day": state, "count": 1}
    done_today = int(state.get("count") or 0) if state.get("day") == today else 0
    if done_today >= max_per_day:
        return 0
    rows = [r for r in db.select("articles", {"channel": channel.key}, order="published_at", desc=True) if r.get("published_at") and is_live(r)]
    posted = 0
    for article in rows:
        if done_today + posted >= max_per_day:
            break
        if shared_marker(db, article["id"]):
            continue
        if share_article_to_facebook(db, article, channel):
            posted += 1
            db.set_setting(key, {"day": today, "count": done_today + posted})
        else:
            break  # not configured, disabled or failed: do not spin through the list
    return posted
