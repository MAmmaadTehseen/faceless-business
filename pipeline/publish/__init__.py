"""Publish a rendered content item (long + shorts) to every configured platform."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..common import Channel, log, now_iso
from . import meta, youtube
from .jarvis import record, update as publication_update
from .cross_promotion import instagram_caption
from .captions import reels_caption, short_tags, uses_legacy_description, youtube_short_description
from .quota import THUMB_COST, UPDATE_COST, reserve


FIXED_CALENDAR = {"futurework": ({0, 2, 4}, 6), "tradewinds": ({1, 3, 5}, 11), "escapevelocity": ({0, 3, 6}, 16)}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def channel_calendar(channel: Channel) -> tuple[set[int], int]:
    """Long-video weekdays and UTC hour: fixed for the original three, channel.json schedule otherwise."""
    if channel.key in FIXED_CALENDAR:
        return FIXED_CALENDAR[channel.key]
    schedule = channel.cfg.get("schedule") or {}
    days = {DAY_NAMES.index(d) for d in schedule.get("days", DAY_NAMES)}
    return days, int(schedule.get("utc_hour", 6))


def _next_slot(db, kind: str, channel: Channel | None = None, *, now=None,
               parent_slot=None, after=None, content_id=None) -> datetime:
    """Assign a channel calendar slot; failed publications do not occupy slots."""
    channel = channel or Channel()
    now = now or datetime.now(timezone.utc)
    earliest = now + timedelta(hours=1)
    content = {c["id"]: c for c in db.select("content", {"channel": channel.key})}
    occupied = []
    for r in db.select("publications", {"platform": "youtube"}):
        if (r["content_id"] in content and r["content_id"] != content_id
                and r.get("status") in ("live", "queued") and r.get("publish_at")):
            occupied.append((datetime.fromisoformat(r["publish_at"].replace("Z", "+00:00")),
                             content[r["content_id"]]["kind"]))
    weekdays, hour = channel_calendar(channel)
    same_day = bool(channel.cfg.get("shorts_same_day")) and parent_slot is not None
    spacing = timedelta(hours=float(channel.cfg.get("shorts_spacing_hours", 1))) if same_day else timedelta(days=1)
    per_day = int(channel.cfg.get("max_youtube_per_day", 3))
    if kind == "long":
        candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    else:
        hour = channel.cfg.get("shorts_hour_utc", {"futurework": 13, "tradewinds": 15,
                                                   "escapevelocity": 18}.get(channel.key, 13)) if parent_slot else channel.cfg.get("daily_short_hour_utc", 20)
        day = parent_slot if same_day else parent_slot + timedelta(days=1) if parent_slot else now
        if after:
            day = max(day, after + spacing)
        candidate = day.replace(hour=int(hour), minute=0, second=0, microsecond=0)
        if after and same_day:
            candidate = max(candidate, after + spacing)
    while True:
        slot = candidate
        day_count = sum(t.date() == slot.date() for t, _ in occupied)
        taken = any(t == slot or (kind == "long" and k == "long" and t.date() == slot.date()) for t, k in occupied)
        if slot >= earliest and (kind != "long" or candidate.weekday() in weekdays) and not taken and day_count < per_day:
            return slot
        if kind == "short" and same_day and day_count >= per_day:
            candidate = (candidate + timedelta(days=1)).replace(hour=int(hour), minute=0, second=0, microsecond=0)
        else:
            candidate += spacing if (kind == "short" and same_day) else timedelta(days=1)
            if kind == "short" and same_day and candidate.date() != slot.date():
                candidate = candidate.replace(hour=int(hour), minute=0, second=0, microsecond=0)  # never spill into the night


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


def _queue_media(db, row, existing=None):
    """Require durable media before committing a queue transition.

    SQLite is a local development backend; its existing file is the durable copy.
    Production must have a private storage/release key, never just a runner path.
    """
    if not Path(row.get("file_path") or "").is_file():
        from ..retry import restore
        row = restore(db, row, existing or {})
        if existing and existing.get("media_key"):
            return {k: existing[k] for k in ("media_key", "thumbnail_key") if existing.get(k)}
    fields = _persist_queue(db, row)
    if db.sb and not fields.get("media_key"):
        raise FileNotFoundError("Cannot queue without persisted media")
    if not db.sb and not Path(row.get("file_path") or "").is_file():
        raise FileNotFoundError("Cannot queue without local media")
    return fields


def _restore_queue(db, row, pub):
    if db.sb or any(str(pub.get(k) or "").startswith("https://") for k in ("media_key", "thumbnail_key")):
        from ..common import OUT_DIR
        work = OUT_DIR / row["id"]
        work.mkdir(parents=True, exist_ok=True)
        for column, key_column in (("file_path", "media_key"), ("thumbnail_path", "thumbnail_key")):
            if row.get(column) and Path(row[column]).is_file():
                continue
            key = pub.get(key_column)
            if not key:
                continue
            target = work / Path(key).name
            temporary = target.with_suffix(target.suffix + ".part")
            try:
                if key.startswith("https://"):
                    import requests
                    with requests.get(key, stream=True, timeout=900) as r:
                        r.raise_for_status()
                        with open(temporary, "wb") as fh:
                            for chunk in r.iter_content(1 << 20):
                                fh.write(chunk)
                else:
                    temporary.write_bytes(db.sb.storage.from_("youtube-queue").download(key))
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            row[column] = str(target)
    return row


def _queue_auth(db, row, channel, privacy, slot, existing=None):
    fields = _queue_media(db, row, existing)
    record(db, {"content_id": row["id"], "platform": "youtube", "status": "queued",
                "privacy": privacy, "publish_at": slot.isoformat(),
                "error": json.dumps({"reason": "youtube_auth_expired", "message": youtube.auth_error(channel)}),
                **fields})


def _youtube_publish(db, row, channel, privacy, slot, draining=False, force_queue=False, force=False):
    youtube.use_channel(channel)
    existing = db.one("publications", {"content_id": row["id"], "platform": "youtube"})
    if existing and existing.get("platform_id"):
        # A known remote ID remains authoritative even if a later DB write failed.
        if row.get("status") != "killed" and row.get("qa_status") == "passed" and not row.get("placeholder"):
            db.update("content", {"id": row["id"]}, {"status": "published"})
        return {"platform": "youtube", "content_id": row["id"], "id": existing["platform_id"],
                "url": existing.get("url") or f"https://youtu.be/{existing['platform_id']}"}
    if existing and existing.get("status") in ("live", "uploading"):
        raise RuntimeError("Publication needs reconciliation before another upload")
    if existing:
        try:
            uncertain = json.loads(existing.get("error") or "{}").get("upload_uncertain")
        except (ValueError, AttributeError):
            uncertain = False
        if uncertain:
            raise RuntimeError("Previous upload outcome uncertain; reconcile in Studio before retry")
    if row.get("placeholder"):
        raise RuntimeError("Refusing to publish placeholder footage")
    if row.get("qa_status") != "passed":
        raise RuntimeError("Refusing publication without passed QA")
    if youtube.auth_failed(channel):
        _queue_auth(db, row, channel, privacy, slot, existing)
        return None
    if draining:
        row = _restore_queue(db, dict(row), existing)
        if not Path(row.get("file_path") or "").is_file():
            from ..retry import restore
            row = restore(db, row, existing)
    if existing and not force:
        try:
            retry_at = json.loads(existing.get("error") or "{}").get("retry_after")
        except (ValueError, AttributeError):
            retry_at = None
        if retry_at and datetime.fromisoformat(retry_at) > datetime.now(timezone.utc):
            return None
    # The compliance audit must be explicitly recorded as passed before new
    # unscheduled/public uploads are allowed. Existing remote videos are untouched.
    if privacy != "private" and db.setting("youtube_compliance_audit_passed", False) is not True:
        privacy = "private"
        log.info("youtube: retaining private scheduled upload until compliance audit passes")
    video = Path(row["file_path"])
    if not video.exists():
        raise FileNotFoundError(f"Queued media missing for {row['id']}")
    thumbnail = Path(row["thumbnail_path"]) if row.get("thumbnail_path") else None
    units = THUMB_COST if thumbnail and thumbnail.exists() else 0
    if not (reserve(db, units, uploads=1, force=True) if force else reserve(db, units, uploads=1)):
        fields = _queue_media(db, row, existing)
        queued = {"content_id": row["id"], "platform": "youtube", "status": "queued",
                  "privacy": privacy, "publish_at": slot.isoformat(), **fields}
        if existing:
            db.update("publications", {"content_id": row["id"], "platform": "youtube",
                      "status": existing["status"]}, queued)
        else:
            try:
                db.insert("publications", queued)
            except Exception:
                if db.one("publications", {"content_id": row["id"], "platform": "youtube"}):
                    return None
                raise
        day = datetime.now(timezone.utc).date().isoformat()
        usage = db.one("quota_log", {"day": day}) or {}
        used_units, used_uploads = usage.get("units", 0), usage.get("uploads", 0)
        unit_limit = int(db.setting("youtube_quota_units_per_day", 10000)) - 1000
        upload_limit = int(db.setting("youtube_uploads_per_day", 100)) - 2
        buckets = []
        if used_units + units > unit_limit:
            buckets.append("general")
        if used_uploads + 1 > upload_limit:
            buckets.append("uploads")
        log.info("youtube: queued %s bucket=%s units=%s+%s/%s uploads=%s+1/%s",
                 row["id"], ",".join(buckets) or "reservation rejected (concurrent usage)",
                 used_units, units, unit_limit, used_uploads, upload_limit)
        return None
    claim = None
    acquired = False
    remote = None
    try:
        # Preserve order but move an expired scheduling slot into the future.
        if slot < datetime.now(timezone.utc) + timedelta(hours=1):
            parent = db.one("publications", {"content_id": row.get("parent_id"), "platform": "youtube"}) if row.get("parent_id") else None
            slot = _next_slot(db, row["kind"], channel, content_id=row["id"],
                              parent_slot=datetime.fromisoformat(parent["publish_at"].replace("Z", "+00:00")) if parent and parent.get("publish_at") else None)
        # Claim the unique publication before videos.insert. Concurrent runners must
        # not both upload; a crashed claim requires explicit owner reconciliation.
        media_fields = _queue_media(db, row, existing) if db.sb else {}
        import uuid
        claim = json.dumps({"upload_attempt": uuid.uuid4().hex, "upload_uncertain": True, "attempted_at": now_iso()})
        if existing:
            db.update("publications", {"content_id": row["id"], "platform": "youtube",
                      "status": existing["status"]}, {"status": "uploading", "error": claim, **media_fields})
        else:
            db.insert("publications", {"content_id": row["id"], "platform": "youtube",
                      "status": "uploading", "privacy": privacy, "publish_at": slot.isoformat(), "error": claim, **media_fields})
        claimed = db.one("publications", {"content_id": row["id"], "platform": "youtube"})
        if not claimed or claimed.get("error") != claim:
            return None
        acquired = True
        from .youtube_promotion import description_links, new_upload
        description = description_links(db, row, channel, row.get("description") or "")
        r = youtube.upload(video, row["title"], description, row.get("tags") or [],
            privacy=privacy, publish_at=slot if privacy == "private" else None, thumbnail=thumbnail,
            is_short=row["kind"] == "short", category_id=channel.cfg.get("category_id", "28"))
        remote = r
        if r.get("thumbnail_failed") and thumbnail and thumbnail.exists():
            remember_pending_thumbnail(db, channel, r["id"], thumbnail)
        record(db, {"content_id": row["id"], "platform": "youtube", "platform_id": r["id"],
            "url": r["url"], "privacy": privacy, "publish_at": slot.isoformat(), "status": "live",
            "published_at": now_iso(), "error": None}, on="content_id,platform")
        db.update("content", {"id": row["id"]}, {"status": "published"})
        new_upload(db, row, channel, r["id"])
        if db.sb:
            saved_media = {**(existing or {}), **media_fields}
            keys = [saved_media[k] for k in ("media_key", "thumbnail_key") if saved_media.get(k)]
            try:
                bucket_keys = [k for k in keys if not k.startswith("https://")]
                if bucket_keys:
                    db.sb.storage.from_("youtube-queue").remove(bucket_keys)
                for url in (k for k in keys if k.startswith("https://")):
                    tag, name = url.rsplit("/", 2)[-2:]
                    import subprocess
                    subprocess.run(["gh", "release", "delete-asset", tag, name, "-y"], capture_output=True)
                if keys:
                    db.update("publications", {"content_id": row["id"], "platform": "youtube"},
                              {"media_key": None, "thumbnail_key": None})
            except Exception:
                log.warning("queue media cleanup deferred for %s", row["id"])
        return {"platform": "youtube", "content_id": row["id"], **r}
    except Exception as e:
        if claim and not acquired:
            # Unique-key conflict or lost claim: another runner owns this upload.
            raise RuntimeError("Upload already claimed; refusing duplicate") from e
        if remote:
            # Never erase the ID when content/status persistence fails afterward.
            record(db, {"content_id": row["id"], "platform": "youtube",
                      "platform_id": remote["id"], "url": remote["url"], "status": "live",
                      "privacy": privacy, "publish_at": slot.isoformat()}, on="content_id,platform")
            raise
        if youtube.is_auth_failure(e):
            youtube.mark_auth_failed()
            _queue_auth(db, row, channel, privacy, slot, existing)
            return None
        details = youtube.error_details(e)
        # Transport errors may occur after YouTube accepted the upload. Fail closed.
        http_status = details.get("http_status")
        if acquired and (not http_status or http_status == 408 or http_status >= 500):
            details["upload_uncertain"] = True
            # Publication creation may predate this attempt by days in the queue.
            details.update({k: v for k, v in json.loads(claim).items()
                            if k in ("upload_attempt", "attempted_at")})
        daily_cap = "uploadLimitExceeded" in details["reason"].split(",")
        quota = daily_cap or (bool(set(details["reason"].split(",")) & youtube.QUOTA_REASONS) and not force)
        if daily_cap:
            details["message"] = "YouTube daily upload cap reached for this channel; try after the cap resets"
        fields = {}
        if quota:
            details["retry_after"] = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            try:
                fields = _queue_media(db, row, existing)
            except Exception as storage_error:
                quota = False
                details["storage_error"] = type(storage_error).__name__
        log.error("youtube upload failed for %s: %s", row["id"], json.dumps(details))
        record(db, {"content_id": row["id"], "platform": "youtube", "status": "queued" if quota else "failed",
            "privacy": privacy, "publish_at": slot.isoformat(), "error": json.dumps(details), **fields}, on="content_id,platform")
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
    if f.is_file():
        return f
    import requests
    from ..common import OUT_DIR
    target = OUT_DIR / s["id"] / f"{s['id']}.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(_media_url(db, s), stream=True, timeout=600) as r:
        r.raise_for_status()
        temporary = target.with_suffix(".mp4.part")
        try:
            with open(temporary, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


REELS_FOLLOW_DAYS = 7


def follow_youtube_to_reels(db, channel) -> int:
    """Shorts whose YouTube copy has gone public (scheduled publish) get their Instagram/Facebook Reels now."""
    meta.use_channel(channel)
    if not (meta.ig_configured() or meta.fb_configured()):
        return 0
    shorts = {c["id"]: c for c in db.select("content", {"channel": channel.key, "kind": "short"})
              if c.get("qa_status") == "passed" and not c.get("placeholder")}
    done = 0
    recent = (datetime.now(timezone.utc) - timedelta(days=REELS_FOLLOW_DAYS)).isoformat()
    for p in db.select("publications", {"platform": "youtube", "status": "live"}):
        s = shorts.get(p["content_id"])
        if not s or p.get("privacy") != "public":
            continue
        if (p.get("publish_at") or p.get("published_at") or "") < recent:
            continue  # old backlog: Reels days or weeks late add nothing and would flood the accounts
        have = {q["platform"] for q in db.select("publications", {"content_id": s["id"]}) if q.get("status") == "live"}
        want = ({"instagram"} if meta.ig_configured() else set()) | ({"facebook"} if meta.fb_configured() else set())
        if want <= have:
            continue
        if not s.get("media_url") and not Path(s.get("file_path") or "").is_file():
            try:
                from ..retry import restore
                s = restore(db, s, p)
            except Exception as e:
                log.warning("reels follow-up: no media for %s on this runner (%s); skipped", s["id"], type(e).__name__)
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


PENDING_THUMB = "yt_thumbnail_pending_"


def remember_pending_thumbnail(db, channel, video_id: str, thumbnail: Path) -> None:
    """Keep a rejected custom thumbnail (unverified channel, quota) so sync can retry thumbnails.set."""
    try:
        key = f"thumbs/{video_id}.jpg"
        if db.sb:
            db.sb.storage.from_("youtube-queue").upload(key, thumbnail.read_bytes(), {"upsert": "true", "content-type": "image/jpeg"})
        else:
            key = str(thumbnail)
        db.set_setting(PENDING_THUMB + video_id, {"channel": channel.key, "key": key, "at": now_iso()})
    except Exception as e:
        log.warning("could not retain thumbnail for retry on %s (%s)", video_id, type(e).__name__)


def retry_pending_thumbnails(db, channel, limit: int = 10) -> int:
    """Sync step: re-send custom thumbnails that failed at upload (50 units each, reserved)."""
    rows = db.sb.table("settings").select("key,value").like("key", PENDING_THUMB + "%").execute().data if db.sb else \
        [r for r in db.select("settings") if str(r["key"]).startswith(PENDING_THUMB)]
    done = 0
    for r in rows or []:
        v = r["value"]
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                v = {}
        if not isinstance(v, dict) or v.get("channel") != channel.key:
            continue
        if done >= limit or not reserve(db, THUMB_COST):
            break
        video_id = r["key"][len(PENDING_THUMB):]
        try:
            from ..common import OUT_DIR
            if db.sb:
                local = OUT_DIR / "thumbs" / f"{video_id}.jpg"
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(db.sb.storage.from_("youtube-queue").download(v["key"]))
            else:
                local = Path(v["key"])
            youtube.use_channel(channel)
            youtube.set_thumbnail(video_id, local)
            if db.sb:
                db.sb.storage.from_("youtube-queue").remove([v["key"]])
                db.sb.table("settings").delete().eq("key", r["key"]).execute()
            else:
                db.conn.execute("delete from settings where key=?", (r["key"],))
                db.conn.commit()
            done += 1
            log.info("thumbnail retry succeeded for %s", video_id)
        except Exception as e:
            log.warning("thumbnail retry still failing for %s (%s); channel phone verification needed?", video_id, type(e).__name__)
            break  # same cause for the whole channel; do not burn quota
    return done


def short_description(s, channel, long_url=None) -> str:
    """YouTube description for a Short: rebuild keyword-free legacy stubs, otherwise fill the long-video URL."""
    if channel.cfg.get("format") != "words" and uses_legacy_description(s.get("description")):
        return youtube_short_description(s, channel, long_url)
    return (s.get("description") or "").replace("{LONG_URL}", long_url or "")


def reel_caption(s, channel, desc: str) -> str:
    """Reels caption: hook + question + niche hashtags for explainer channels; words-format channels keep their own text."""
    if channel.cfg.get("format") == "words":
        return f"{s['title']}\n\n{desc}".strip()
    return reels_caption(s, channel)


def reels_wait_for_youtube(db, s) -> bool:
    """Child Shorts post their Reels when the YouTube copy goes public, one per day, instead of four in two minutes.

    Setting `reels_follow_youtube` (default true) gates it. Standalone Shorts, Shorts without a
    scheduled YouTube row and words-format channels publish Reels immediately as before.
    """
    if not s.get("parent_id") or db.setting("reels_follow_youtube", True) is not True:
        return False
    yt_pub = db.one("publications", {"content_id": s["id"], "platform": "youtube"})
    if not yt_pub or yt_pub.get("status") not in ("live", "queued") or yt_pub.get("privacy") == "public":
        return False
    publish_at = yt_pub.get("publish_at")
    if not publish_at:
        return False
    try:
        return datetime.fromisoformat(str(publish_at).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except ValueError:
        return False


def publish_short(db, short_row, channel, privacy, long_url=None, *, slot=None, queue_youtube=False):
    youtube.use_channel(channel); meta.use_channel(channel)
    s = dict(short_row)
    if s.get("placeholder") or s.get("qa_status") != "passed":
        raise RuntimeError("Refusing to publish placeholder or unapproved Short")
    if db.sb and not s.get("media_url") and s.get("file_path") and Path(s["file_path"]).is_file():
        try:
            _media_url(db, s)
        except Exception as exc:
            log.warning("short media persistence deferred for %s (%s)", s["id"], type(exc).__name__)
    desc = short_description(s, channel, long_url)
    s["description"] = desc
    db.update("content", {"id": s["id"]}, {"description": desc})
    results = []
    if youtube.configured():
        try:
            r = _youtube_publish(db, s, channel, privacy, slot or _next_slot(db, "short", channel, content_id=s["id"]), force_queue=queue_youtube)
            if r:
                results.append(r)
        except Exception as e:
            # YouTube/storage problems must not prevent independent Meta Reels.
            log.error("youtube short deferred for %s (%s)", s["id"], type(e).__name__)
    if meta.configured() and privacy == "public" and reels_wait_for_youtube(db, s):
        log.info("meta: reels for %s wait for its scheduled YouTube slot (sync publishes them when it goes public)", s["id"])
    elif meta.configured() and privacy == "public":
        caption = reel_caption(s, channel, desc)
        ig = db.one("publications", {"content_id": s["id"], "platform": "instagram"})
        fb = db.one("publications", {"content_id": s["id"], "platform": "facebook"})
        try:
            if not meta.ig_configured():
                raise RuntimeError("instagram not configured for this channel")
            if ig and ig.get("platform_id"):
                r = {"id": ig["platform_id"], "url": ig.get("url")}
                mention_metadata = ig.get("error")
            else:
                url = _media_url(db, s)
                ig_caption, mention_metadata = instagram_caption(db, s, channel, caption)
                r = meta.publish_instagram_reel(url, ig_caption)
            record(db, {"content_id": s["id"], "platform": "instagram", "platform_id": r["id"], "url": r.get("url"), "privacy": "public",
                                       "status": "live", "published_at": (ig or {}).get("published_at") or now_iso(),
                                       "error": mention_metadata}, on="content_id,platform")
            results.append({"platform": "instagram", "content_id": s["id"], **r})
        except Exception as e:
            log.error("instagram failed: %s", e)
            record(db, {"content_id": s["id"], "platform": "instagram", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
        try:
            if not meta.fb_configured():
                raise RuntimeError("facebook not configured for this channel")
            if fb and fb.get("platform_id"):
                r = {"id": fb["platform_id"], "url": fb.get("url")}
            else:
                r = meta.publish_facebook_reel(_local_file(db, s), caption)
            record(db, {"content_id": s["id"], "platform": "facebook", "platform_id": r["id"], "url": r.get("url"), "privacy": "public",
                                       "status": "live", "published_at": now_iso()}, on="content_id,platform")
            results.append({"platform": "facebook", "content_id": s["id"], **r})
        except Exception as e:
            log.error("facebook failed: %s", e)
            record(db, {"content_id": s["id"], "platform": "facebook", "status": "failed", "error": str(e)[:500]}, on="content_id,platform")
    elif meta.configured():
        log.info("meta: skipping reels while publish_privacy is private (Reels cannot be scheduled private)")

    if results:
        db.update("content", {"id": s["id"]}, {"status": "published"})
    return results


def publish_all(db, content_id, privacy="private", channel=None):
    long = db.one("content", {"id": content_id})
    channel = channel or Channel(long.get("channel") or "futurework")
    youtube.use_channel(channel); meta.use_channel(channel)
    slot = _next_slot(db, "long", channel, content_id=content_id)
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
    if parent_pub and parent_pub.get("publish_at"):
        slot = datetime.fromisoformat(parent_pub["publish_at"].replace("Z", "+00:00"))
    previous_short = None
    shorts = db.select("content", {"parent_id": content_id, "kind": "short"}, order="id")
    for i, short in enumerate(shorts):
        if short.get("qa_status") != "passed":
            continue
        tags = short_tags(short, channel, long.get("tags") or [])
        if tags != (short.get("tags") or []):
            short["tags"] = tags
            db.update("content", {"id": short["id"]}, {"tags": tags})
        short_slot = _next_slot(db, "short", channel, parent_slot=slot, after=previous_short, content_id=short["id"])
        results.extend(publish_short(db, short, channel, privacy, long_url, slot=short_slot))
        previous_short = short_slot
    return results


def drain_youtube_queue(db, channel):
    youtube.use_channel(channel)
    from .reconcile import reconcile_uploads
    reconcile_uploads(db, channel)
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
                current = db.one("publications", {"id": p["id"]}) or {}
                if current.get("platform_id") or current.get("status") != "queued":
                    # Another worker may have claimed or completed this item.
                    continue
                try:
                    previous = json.loads(current.get("error") or "{}")
                    if previous.get("upload_uncertain"):
                        continue
                    attempts = previous.get("drain_attempts", 0)
                except (ValueError, AttributeError):
                    attempts = 0
                attempts += 1
                publication_update(db, {"id": p["id"], "status": "queued", "error": current.get("error")}, {
                    "status": "failed" if attempts >= 3 else "queued",
                    "error": json.dumps({"drain_attempts": attempts, "error": "Queue drain failed: " + type(e).__name__})})
                log.error("youtube queue drain failed for %s (%s)", p["content_id"], type(e).__name__)
                continue
            if not r:
                current = db.one("publications", {"id": p["id"]})
                if current and current.get("status") == "queued":
                    break
                continue
            drained += 1
    remaining = sum(1 for p in db.select("publications", {"platform": "youtube", "status": "queued"}) if p["content_id"] in rows)
    log.info("youtube queue[%s]: drained %d, remaining %d", channel.key, drained, remaining)
    return drained
