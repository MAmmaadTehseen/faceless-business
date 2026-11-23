"""Pull metrics and comments for every live publication into the DB. Runs every 6h."""
from __future__ import annotations

import time
import re

from .common import Channel, log, now_iso
from .db import DB
from .publish import meta, youtube, drain_youtube_queue, follow_youtube_to_reels

FLAG = re.compile(r"\b(lawsuit|lawyer|sue|legal action|defam|copyright|dmca|refund|chargeback|scam|fraud|suicide|kill (my|your)self|diagnos|prescri|medical advice|overdose|invest(ment)? advice|guaranteed returns)\b", re.I)
ABUSE = re.compile(r"\b(idiot|stupid|moron|trash|garbage channel|fake|bot channel|ai slop)\b", re.I)


def flag_reason(text: str) -> str | None:
    if FLAG.search(text):
        return "sensitive: " + FLAG.search(text).group(0)
    if ABUSE.search(text):
        return "hostile"
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drain-only", action="store_true")
    ap.add_argument("--channel", choices=Channel.keys() + ["filmreview"])
    args = ap.parse_args()
    db = DB()
    for key in ([args.channel] if args.channel else Channel.keys() + ["filmreview"]):
        try:
            # The film recap channel keeps local.json (no crons), but its YouTube metrics and comments
            # still belong in the dashboard.
            channel = _film_channel() if key == "filmreview" else Channel(key)
            started = time.monotonic()
            (drain_youtube_queue if args.drain_only else sync_channel)(db, channel)
            log.info("sync %s took %.0fs", key, time.monotonic() - started)
        except Exception as e:
            log.error("sync %s failed: %s", key, e)


def _film_channel():
    from .recap.channel import FilmReviewChannel
    return FilmReviewChannel()


def sync_channel(db, channel):
    drain_youtube_queue(db, channel)
    youtube.use_channel(channel); meta.use_channel(channel)
    try:
        meta.refresh_ig_token(db, channel)
    except Exception as e:
        log.warning("ig token refresh skipped for %s: %s", channel.key, e)
    try:
        from .publish import retry_pending_thumbnails
        if youtube.configured() and not youtube.auth_failed(channel):
            retry_pending_thumbnails(db, channel)
    except Exception as e:
        log.warning("thumbnail retry skipped for %s: %s", channel.key, e)
    try:
        from .publish.hub_share import backfill_articles
        backfill_articles(db, channel)
    except Exception as e:
        log.warning("hub article share skipped for %s: %s", channel.key, e)
    ids = {c["id"] for c in db.select("content", {"channel": channel.key})}
    pubs = [p for p in db.select("publications", {"status": "live"}) if p["content_id"] in ids]
    if not pubs:
        return
    pending_metrics = []
    yt_pubs = [p for p in pubs if p["platform"] == "youtube" and p.get("platform_id")]
    if yt_pubs and youtube.configured() and not youtube.auth_failed(channel):
        ids = [p["platform_id"] for p in yt_pubs]
        st = youtube.stats(ids)
        an = youtube.analytics(ids)
        for p in yt_pubs:
            s = st.get(p["platform_id"])
            if not s:
                continue
            a = an.get(p["platform_id"], {})
            pending_metrics.append({"publication_id": p["id"], "views": s["views"], "likes": s["likes"], "comments": s["comments"],
                                  "ctr": a.get("ctr"), "avg_view_duration_sec": a.get("avg_view_duration_sec"), "impressions": a.get("impressions")})
            if s["privacy"] != p.get("privacy"):
                db.update("publications", {"id": p["id"]}, {"privacy": s["privacy"]})
            if s["comments"]:
                for c in youtube.comments(p["platform_id"]):
                    if c.pop("is_own", False):
                        continue
                    _store_comment(db, p, "youtube", c)
    if meta.configured():
        # Insights and comments are one slow Graph call each per Reel; fetch them in parallel,
        # then write to the database from this thread.
        from concurrent.futures import ThreadPoolExecutor

        def fetch(p):
            try:
                if p["platform"] == "instagram":
                    return p, meta.ig_insights(p["platform_id"]), list(meta.ig_comments(p["platform_id"])), None
                return p, meta.fb_insights(p["platform_id"]), list(meta.fb_comments(p["platform_id"])), None
            except Exception as e:
                return p, None, [], e

        social = [p for p in pubs if p["platform"] in ("instagram", "facebook") and p.get("platform_id")]
        with ThreadPoolExecutor(max_workers=8) as pool:
            for p, m, comments, err in pool.map(fetch, social):
                if err:
                    log.warning("%s sync failed %s: %s", "ig" if p["platform"] == "instagram" else "fb", p["platform_id"], err)
                    continue
                pending_metrics.append({"publication_id": p["id"], **m})
                for c in comments:
                    _store_comment(db, p, p["platform"], c)
    db.insert_many("metrics", pending_metrics)
    try:
        follow_youtube_to_reels(db, channel)
    except Exception as e:
        log.error("reels follow-up failed for %s: %s", channel.key, e)
    try:
        from .publish.reschedule import compress
        moved = compress(db, channel)
        if moved:
            log.info("sync[%s]: compressed schedule, %d uploads moved earlier", channel.key, moved)
    except Exception as e:
        log.warning("schedule compression skipped for %s: %s", channel.key, e)
    log.info("sync[%s]: %d publications", channel.key, len(pubs))


def _store_comment(db, pub, platform, c):
    if db.one("comments", {"platform_comment_id": c["platform_comment_id"]}):
        return
    reason = flag_reason(c["text"])
    db.insert("comments", {"publication_id": pub["id"], "platform": platform, "platform_comment_id": c["platform_comment_id"],
                           "author": c.get("author"), "text": c["text"], "posted_at": c.get("posted_at"),
                           "flagged": bool(reason), "flag_reason": reason, "reply_status": "new"})


if __name__ == "__main__":
    main()
