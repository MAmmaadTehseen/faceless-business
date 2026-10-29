"""Publish a rendered content item (long + shorts) to every configured platform."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..common import Channel, log, now_iso
from . import meta, youtube
from .quota import UPLOAD_COST, THUMB_COST, UPDATE_COST, reserve


def _next_slot(db, kind: str, channel: Channel | None = None) -> datetime:
    """Stagger: long videos 12h apart starting 1h from now; shorts 2h after their parent. Per channel."""
    now = datetime.now(timezone.utc)
    rows = db.select("publications", {"platform": "youtube"}, order="publish_at", desc=True, limit=60)
    if channel:
        ids = {c["id"] for c in db.select("content", {"channel": channel.key})}
        rows = [r for r in rows if r["content_id"] in ids]
    future = [datetime.fromisoformat(r["publish_at"].replace("Z", "+00:00")) for r in rows if r.get("publish_at")]
    future = [t for t in future if t > now]
    base = max(future) + timedelta(hours=12) if future else now + timedelta(hours=1)
    return base


BIG_FILE = 45 * 1024 * 1024   # Supabase free tier caps objects at 50 MB; larger queued files go to a GitHub release


def _persist_queue(db, row):
    """Store privately so another Actions runner can drain the queue. Big files go to a release asset (key = URL)."""
    fields = {}
    if db.sb:
        for column, key_column in (("file_path", "media_key"), ("thumbnail_path", "thumbnail_key")):
            if row.get(column):
                path = Path(row[column])
                if path.stat().st_size > BIG_FILE:
                    fields[key_column] = meta._github_release_url(path, tag=f"queue-{datetime.now(timezone.utc):%Y%m%d}")
                    continue
                key = f"{row['id']}/{path.name}"
                db.sb.storage.from_("youtube-queue").upload(key, path.read_bytes(),
                    {"upsert": "true", "content-type": "video/mp4" if column == "file_path" else "image/jpeg"})
                fields[key_column] = key
    return fields


def _restore_queue(db, row, pub):
    if db.sb:
        from ..common import OUT_DIR
        work = OUT_DIR / row["id"]
        work.mkdir(parents=True, exist_ok=True)
        for column, key_column in (("file_path", "media_key"), ("thumbnail_path", "thumbnail_key")):
            key = pub.get(key_column)
            if not key:
                continue
            target = work / Path(key).name
            if key.startswith("https://"):
                import requests
                with requests.get(key, stream=True, timeout=900) as r:
                    r.raise_for_status()
                    with open(target, "wb") as fh:
                        for chunk in r.iter_content(1 << 20):
                            fh.write(chunk)
            else:
                target.write_bytes(db.sb.storage.from_("youtube-queue").download(key))
            row[column] = str(target)
    return row


def _youtube_publish(db, row, channel, privacy, slot, draining=False, force_queue=False):
    existing = db.one("publications", {"content_id": row["id"], "platform": "youtube"})
    if existing and existing.get("status") == "live":
        return {"platform": "youtube", "content_id": row["id"], "id": existing["platform_id"], "url": existing["url"]}
    if existing and existing.get("status") == "queued" and not draining:
        return None
    if row.get("placeholder"):
        raise RuntimeError("Refusing to publish placeholder footage")
    if row.get("qa_status") != "passed":
        raise RuntimeError("Refusing publication without passed QA")
    if draining:
        row = _restore_queue(db, dict(row), existing)
    video = Path(row["file_path"])
    if not video.exists():
        raise FileNotFoundError(f"Queued media missing for {row['id']}")
    thumbnail = Path(row["thumbnail_path"]) if row.get("thumbnail_path") else None
    units = UPLOAD_COST + (THUMB_COST if thumbnail and thumbnail.exists() else 0)
    if force_queue or not reserve(db, units):
        fields = {}
        if not draining:
            db.upsert("publications", {"content_id": row["id"], "platform": "youtube", "status": "queued",
                      "privacy": privacy, "publish_at": slot.isoformat()}, on="content_id,platform")
            try:
                fields = _persist_queue(db, row)
            except Exception as e:
                db.update("publications", {"content_id": row["id"], "platform": "youtube"},
                          {"error": "Queue storage failed: " + type(e).__name__})
                raise
        db.upsert("publications", {"content_id": row["id"], "platform": "youtube", "status": "queued",
                  "privacy": privacy, "publish_at": slot.isoformat(), **fields}, on="content_id,platform")
        log.info("youtube: queued %s (daily quota reserve)", row["id"])
        return None
    try:
        # Preserve order but move an expired scheduling slot into the future.
        slot = max(slot, datetime.now(timezone.utc) + timedelta(hours=1))
        r = youtube.upload(video, row["title"], row.get("description") or "", row.get("tags") or [],
            privacy=privacy, publish_at=slot if privacy == "private" else None, thumbnail=thumbnail,
            is_short=row["kind"] == "short", category_id=channel.cfg.get("category_id", "28"))
        db.upsert("publications", {"content_id": row["id"], "platform": "youtube", "platform_id": r["id"],
            "url": r["url"], "privacy": privacy, "publish_at": slot.isoformat(), "status": "live",
            "published_at": now_iso(), "error": None}, on="content_id,platform")
        db.update("content", {"id": row["id"]}, {"status": "published"})
        if draining and db.sb:
            keys = [existing[k] for k in ("media_key", "thumbnail_key") if existing.get(k)]
            try:
                bucket_keys = [k for k in keys if not k.startswith("https://")]
                if bucket_keys:
                    db.sb.storage.from_("youtube-queue").remove(bucket_keys)
                for url in (k for k in keys if k.startswith("https://")):
                    tag, name = url.rsplit("/", 2)[-2:]
                    import subprocess
                    subprocess.run(["gh", "release", "delete-asset", tag, name, "-y"], capture_output=True)
                if keys:
                    db.update("publications", {"id": existing["id"]}, {"media_key": None, "thumbnail_key": None})
            except Exception:
                log.warning("queue media cleanup deferred for %s", row["id"])
        return {"platform": "youtube", "content_id": row["id"], **r}
    except Exception as e:
        log.error("youtube upload failed for %s (%s)", row["id"], type(e).__name__)
        db.upsert("publications", {"content_id": row["id"], "platform": "youtube", "status": "failed",
            "error": type(e).__name__}, on="content_id,platform")
        return None


def _media_url(db, s) -> str:
    """Public mp4 URL for a Short: stored at production time, else uploaded now from the local file."""
    if s.get("media_url"):
        return s["media_url"]
    url = meta.public_url_for(Path(s["file_path"]), tag=f"media-{datetime.now(timezone.utc):%Y%m%d}")
    db.update("content", {"id": s["id"]}, {"media_url": url})
    s["media_url"] = url
    return url


def _local_file(db, s) -> Path:
    """Local mp4 for a Short; on a fresh runner, download it from its public media URL."""
    f = Path(s.get("file_path") or "")
    if f.exists():
        return f
    import requests
    from ..common import OUT_DIR
    target = OUT_DIR / s["id"] / f"{s['id']}.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(_media_url(db, s), stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(target, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return target


def follow_youtube_to_reels(db, channel) -> int:
    """Shorts whose YouTube copy has gone public (scheduled publish) get their Instagram/Facebook Reels now."""
    meta.use_channel(channel)
    if not (meta.ig_configured() or meta.fb_configured()):
        return 0
    shorts = {c["id"]: c for c in db.select("content", {"channel": channel.key, "kind": "short"})
              if c.get("qa_status") == "passed" and not c.get("placeholder")}
    done = 0
    for p in db.select("publications", {"platform": "youtube", "status": "live"}):
        s = shorts.get(p["content_id"])
        if not s or p.get("privacy") != "public":
            continue
        have = {q["platform"] for q in db.select("publications", {"content_id": s["id"]}) if q.get("status") == "live"}
        want = ({"instagram"} if meta.ig_configured() else set()) | ({"facebook"} if meta.fb_configured() else set())
        if want <= have:
            continue
        parent = db.one("publications", {"content_id": s.get("parent_id") or "", "platform": "youtube"}) if s.get("parent_id") else None
        try:
            res = publish_short(db, s, channel, "public", long_url=(parent or {}).get("url"))
            done += sum(1 for r in res if r["platform"] in ("instagram", "facebook"))
        except Exception as e:
            log.error("reels follow-up failed for %s (%s)", s["id"], type(e).__name__)
    if done:
        log.info("reels[%s]: published %d following YouTube going public", channel.key, done)
    return done


def publish_short(db, short_row, channel, privacy, long_url=None, *, slot=None, queue_youtube=False):
    youtube.use_channel(channel); meta.use_channel(channel)
    s = dict(short_row)
    if s.get("placeholder") or s.get("qa_status") != "passed":
        raise RuntimeError("Refusing to publish placeholder or unapproved Short")
    desc = (s.get("description") or "").replace("{LONG_URL}", long_url or "")
    s["description"] = desc
    db.update("content", {"id": s["id"]}, {"description": desc})
    results = []
    if youtube.configured():
        try:
            r = _youtube_publish(db, s, channel, privacy, slot or _next_slot(db, "short", channel), force_queue=queue_youtube)
            if r:
                results.append(r)
        except Exception as e:
            # YouTube/storage problems must not prevent independent Meta Reels.
            log.error("youtube short deferred for %s (%s)", s["id"], type(e).__name__)
    if meta.configured() and privacy == "public":
        caption = f"{s['title']}\n\n{desc}".strip()
        ig = db.one("publications", {"content_id": s["id"], "platform": "instagram"})
        fb = db.one("publications", {"content_id": s["id"], "platform": "facebook"})
        try:
            if not meta.ig_configured():
                raise RuntimeError("instagram not configured for this channel")
            if ig and ig.get("status") == "live":
                r = {"id": ig["platform_id"], "url": ig.get("url")}
            else:
                url = _media_url(db, s)
                r = meta.publish_instagram_reel(url, caption)
            db.upsert("publications", {"content_id": s["id"], "platform": "instagram", "platform_id": r["id"], "url": r.get("url"), "privacy": "public",
                                       "status": "live", "published_at": now_iso()}, on="content_id,platform")
            results.append({"platform": "instagram", "content_id": s["id"], **r})
        except Exception as e:
            log.error("instagram failed: %s", e)
            db.upsert("publications", {"content_id": s["id"], "platform": "instagram", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
        try:
            if not meta.fb_configured():
                raise RuntimeError("facebook not configured for this channel")
            if fb and fb.get("status") == "live":
                r = {"id": fb["platform_id"], "url": fb.get("url")}
            else:
                r = meta.publish_facebook_reel(_local_file(db, s), caption)
            db.upsert("publications", {"content_id": s["id"], "platform": "facebook", "platform_id": r["id"], "url": r.get("url"), "privacy": "public",
                                       "status": "live", "published_at": now_iso()}, on="content_id,platform")
            results.append({"platform": "facebook", "content_id": s["id"], **r})
        except Exception as e:
            log.error("facebook failed: %s", e)
            db.upsert("publications", {"content_id": s["id"], "platform": "facebook", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
    elif meta.configured():
        log.info("meta: skipping reels while publish_privacy is private (Reels cannot be scheduled private)")

    if results:
        db.update("content", {"id": s["id"]}, {"status": "published"})
    return results


def publish_all(db, content_id, privacy="private", channel=None):
    long = db.one("content", {"id": content_id})
    channel = channel or Channel(long.get("channel") or "futurework")
    youtube.use_channel(channel); meta.use_channel(channel)
    slot = _next_slot(db, "long", channel)
    results = []
    long_url = None
    if youtube.configured():
        try:
            r = _youtube_publish(db, long, channel, privacy, slot)
            if r:
                results.append(r)
                long_url = r["url"]
        except Exception as e:
            log.error("youtube long deferred for %s (%s)", content_id, type(e).__name__)
    parent_pub = db.one("publications", {"content_id": content_id, "platform": "youtube"})
    queue_shorts = bool(parent_pub and parent_pub.get("status") == "queued")
    shorts = db.select("content", {"parent_id": content_id, "kind": "short"}, order="id")
    for i, short in enumerate(shorts):
        if short.get("qa_status") != "passed":
            continue
        if not short.get("tags"):
            short["tags"] = long.get("tags") or []
            db.update("content", {"id": short["id"]}, {"tags": short["tags"]})
        results.extend(publish_short(db, short, channel, privacy, long_url, slot=slot + timedelta(hours=2*(i+1)), queue_youtube=queue_shorts))
    return results


def drain_youtube_queue(db, channel):
    youtube.use_channel(channel)
    rows = {r["id"]: r for r in db.select("content", {"channel": channel.key})}
    queued = [p for p in db.select("publications", {"platform": "youtube", "status": "queued"}, order="publish_at")
              if p["content_id"] in rows]
    drained = 0
    if youtube.configured():
        for p in queued:
            slot = datetime.fromisoformat(p["publish_at"].replace("Z", "+00:00"))
            try:
                r = _youtube_publish(db, rows[p["content_id"]], channel, p.get("privacy") or "private", slot, draining=True)
            except Exception as e:
                db.update("publications", {"id": p["id"]}, {"error": "Queue drain failed: " + type(e).__name__})
                log.error("youtube queue drain failed for %s (%s)", p["content_id"], type(e).__name__)
                break
            if not r:
                break
            drained += 1
    remaining = sum(1 for p in db.select("publications", {"platform": "youtube", "status": "queued"}) if p["content_id"] in rows)
    log.info("youtube queue[%s]: drained %d, remaining %d", channel.key, drained, remaining)
    return drained
