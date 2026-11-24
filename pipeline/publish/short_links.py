"""Comment on each child Short with a link to its full long video once both are public.

Shorts viewers who want more have no tappable route to the long video: description links are
hidden behind "more" on Shorts. A first comment from the channel is the visible fallback the API
allows (pinning and the Shorts "Related video" field are Studio-only; the growth loop sets the
related video through the browser). Growth log 2026-11-24.

One comment per Short, ever: the attempt is remembered in setting `yt_link_comment_<short video id>`
before the API call, so an uncertain failure never posts twice. Each comment is a 50-unit
commentThreads.insert under the normal quota reservation. Setting `short_link_comments_enabled`
(JSON boolean, default true) turns it off; `short_link_comments_max_per_run` (default 10) caps a sync.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..common import log
from . import youtube
from .quota import reserve

COMMENT_COST = 50
RECENT_DAYS = 7
DONE = "yt_link_comment_"


def comment_text(channel, parent_title: str, url: str) -> str:
    template = channel.cfg.get("short_link_comment") or "Full video: {title}\n{url}"
    return template.format(title=parent_title.strip(), url=url)


def comment_long_links(db, channel) -> int:
    if db.setting("short_link_comments_enabled", True) is not True:
        return 0
    if not youtube.configured() or youtube.auth_failed(channel):
        return 0
    limit = int(db.setting("short_link_comments_max_per_run", 10) or 0)
    recent = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).isoformat()
    content = {c["id"]: c for c in db.select("content", {"channel": channel.key})}
    youtube.use_channel(channel)
    done = 0
    for p in db.select("publications", {"platform": "youtube", "status": "live"}):
        short = content.get(p["content_id"])
        if done >= limit:
            break
        if not short or short.get("kind") != "short" or not short.get("parent_id") or not p.get("platform_id"):
            continue
        if p.get("privacy") != "public" or (p.get("publish_at") or p.get("published_at") or "") < recent:
            continue
        key = DONE + p["platform_id"]
        if db.setting(key):
            continue
        parent_pub = db.one("publications", {"content_id": short["parent_id"], "platform": "youtube"})
        if not parent_pub or not parent_pub.get("platform_id") or parent_pub.get("privacy") != "public":
            continue  # a link to a scheduled video would show "video unavailable"; try next sync
        parent = content.get(short["parent_id"]) or {}
        url = parent_pub.get("url") or f"https://youtu.be/{parent_pub['platform_id']}"
        if not reserve(db, COMMENT_COST):
            log.info("short link comments[%s]: quota reserve refused; stopping", channel.key)
            break
        db.set_setting(key, {"attempted_at": datetime.now(timezone.utc).isoformat(), "parent": parent_pub["platform_id"]})
        try:
            youtube.yt().commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": p["platform_id"],
                "topLevelComment": {"snippet": {"textOriginal": comment_text(channel, parent.get("title") or "", url)}}}}).execute()
            done += 1
        except Exception as e:
            log.warning("short link comment failed for %s (%s); not retried", p["platform_id"], type(e).__name__)
    if done:
        log.info("short link comments[%s]: %d posted", channel.key, done)
    return done
