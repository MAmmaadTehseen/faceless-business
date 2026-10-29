"""Pull metrics and comments for every live publication into the DB. Runs every 6h."""
from __future__ import annotations

import re

from .common import Channel, log, now_iso
from .db import DB
from .publish import meta, youtube, drain_youtube_queue

FLAG = re.compile(r"\b(lawsuit|lawyer|sue|legal action|defam|copyright|dmca|refund|chargeback|scam|fraud|suicide|kill (my|your)self|diagnos|prescri|medical advice|overdose|invest(ment)? advice|guaranteed returns)\b", re.I)
ABUSE = re.compile(r"\b(idiot|stupid|moron|trash|garbage channel|fake|bot channel|ai slop)\b", re.I)


def flag_reason(text: str) -> str | None:
    if FLAG.search(text):
        return "sensitive: " + FLAG.search(text).group(0)
    if ABUSE.search(text):
        return "hostile"
    return None


def main():
    db = DB()
    for key in Channel.keys():
        try:
            sync_channel(db, Channel(key))
        except Exception as e:
            log.error("sync %s failed: %s", key, e)


def sync_channel(db, channel):
    drain_youtube_queue(db, channel)
    youtube.use_channel(channel); meta.use_channel(channel)
    ids = {c["id"] for c in db.select("content", {"channel": channel.key})}
    pubs = [p for p in db.select("publications", {"status": "live"}) if p["content_id"] in ids]
    if not pubs:
        return
    yt_pubs = [p for p in pubs if p["platform"] == "youtube" and p.get("platform_id")]
    if yt_pubs and youtube.configured():
        ids = [p["platform_id"] for p in yt_pubs]
        st = youtube.stats(ids)
        an = youtube.analytics(ids)
        for p in yt_pubs:
            s = st.get(p["platform_id"])
            if not s:
                continue
            a = an.get(p["platform_id"], {})
            db.insert("metrics", {"publication_id": p["id"], "views": s["views"], "likes": s["likes"], "comments": s["comments"],
                                  "ctr": a.get("ctr"), "avg_view_duration_sec": a.get("avg_view_duration_sec"), "impressions": a.get("impressions")})
            if s["privacy"] != p.get("privacy"):
                db.update("publications", {"id": p["id"]}, {"privacy": s["privacy"]})
            if s["comments"]:
                for c in youtube.comments(p["platform_id"]):
                    if c.pop("is_own", False):
                        continue
                    _store_comment(db, p, "youtube", c)
    if meta.configured():
        for p in pubs:
            if p["platform"] == "instagram" and p.get("platform_id"):
                try:
                    m = meta.ig_insights(p["platform_id"])
                    db.insert("metrics", {"publication_id": p["id"], **m})
                    for c in meta.ig_comments(p["platform_id"]):
                        _store_comment(db, p, "instagram", c)
                except Exception as e:
                    log.warning("ig sync failed %s: %s", p["platform_id"], e)
            elif p["platform"] == "facebook" and p.get("platform_id"):
                try:
                    m = meta.fb_insights(p["platform_id"])
                    db.insert("metrics", {"publication_id": p["id"], **m})
                    for c in meta.fb_comments(p["platform_id"]):
                        _store_comment(db, p, "facebook", c)
                except Exception as e:
                    log.warning("fb sync failed %s: %s", p["platform_id"], e)
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
