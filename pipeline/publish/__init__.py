"""Publish a rendered content item (long + shorts) to every configured platform."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..common import log, now_iso
from . import meta, youtube


def _next_slot(db, kind: str) -> datetime:
    """Stagger: long videos 12h apart starting 1h from now; shorts 2h after their parent."""
    now = datetime.now(timezone.utc)
    rows = db.select("publications", {"platform": "youtube"}, order="publish_at", desc=True, limit=20)
    future = [datetime.fromisoformat(r["publish_at"].replace("Z", "+00:00")) for r in rows if r.get("publish_at")]
    future = [t for t in future if t > now]
    base = max(future) + timedelta(hours=12) if future else now + timedelta(hours=1)
    return base


def publish_all(db, content_id: str, privacy: str = "private") -> list[dict]:
    long = db.one("content", {"id": content_id})
    shorts = db.select("content", {"parent_id": content_id, "kind": "short"})
    results = []
    long_url = None

    if youtube.configured():
        slot = _next_slot(db, "long")
        try:
            r = youtube.upload(Path(long["file_path"]), long["title"], long["description"] or "", long.get("tags") or [],
                               privacy=privacy, publish_at=slot if privacy == "private" else None, thumbnail=Path(long["thumbnail_path"]) if long.get("thumbnail_path") else None)
            long_url = r["url"]
            db.upsert("publications", {"content_id": content_id, "platform": "youtube", "platform_id": r["id"], "url": r["url"], "privacy": privacy,
                                       "publish_at": slot.isoformat(), "status": "live", "published_at": now_iso()}, on="content_id,platform")
            results.append({"platform": "youtube", "content_id": content_id, **r})
        except Exception as e:
            log.error("youtube long upload failed: %s", e)
            db.upsert("publications", {"content_id": content_id, "platform": "youtube", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
    else:
        log.warning("youtube not configured; skipping")

    for i, s in enumerate(shorts):
        desc = (s["description"] or "").replace("{LONG_URL}", long_url or "")
        db.update("content", {"id": s["id"]}, {"description": desc})
        if youtube.configured():
            try:
                r = youtube.upload(Path(s["file_path"]), s["title"], desc, long.get("tags") or [], privacy=privacy,
                                   publish_at=(slot + timedelta(hours=2 * (i + 1))) if privacy == "private" else None, is_short=True)
                db.upsert("publications", {"content_id": s["id"], "platform": "youtube", "platform_id": r["id"], "url": r["url"], "privacy": privacy,
                                           "publish_at": (slot + timedelta(hours=2 * (i + 1))).isoformat(), "status": "live", "published_at": now_iso()}, on="content_id,platform")
                results.append({"platform": "youtube", "content_id": s["id"], **r})
            except Exception as e:
                log.error("youtube short upload failed: %s", e)
                db.upsert("publications", {"content_id": s["id"], "platform": "youtube", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
        if meta.configured() and privacy == "public":
            caption = f"{s['title']}\n\n{desc}".strip()
            try:
                url = meta.public_url_for(Path(s["file_path"]), tag=f"media-{datetime.now(timezone.utc):%Y%m%d}")
                r = meta.publish_instagram_reel(url, caption)
                db.upsert("publications", {"content_id": s["id"], "platform": "instagram", "platform_id": r["id"], "url": r.get("url"), "privacy": "public",
                                           "status": "live", "published_at": now_iso()}, on="content_id,platform")
                results.append({"platform": "instagram", "content_id": s["id"], **r})
            except Exception as e:
                log.error("instagram failed: %s", e)
                db.upsert("publications", {"content_id": s["id"], "platform": "instagram", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
            try:
                r = meta.publish_facebook_reel(Path(s["file_path"]), caption)
                db.upsert("publications", {"content_id": s["id"], "platform": "facebook", "platform_id": r["id"], "url": r.get("url"), "privacy": "public",
                                           "status": "live", "published_at": now_iso()}, on="content_id,platform")
                results.append({"platform": "facebook", "content_id": s["id"], **r})
            except Exception as e:
                log.error("facebook failed: %s", e)
                db.upsert("publications", {"content_id": s["id"], "platform": "facebook", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
        elif meta.configured():
            log.info("meta: skipping reels while publish_privacy is private (Reels cannot be scheduled private)")

    db.update("content", {"id": content_id}, {"status": "published" if results else "failed"})
    for s in shorts:
        db.update("content", {"id": s["id"]}, {"status": "published" if results else "failed"})
    return results
