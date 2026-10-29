"""Draft replies for new comments in persona; auto-send where the dashboard toggle allows; like on Facebook."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .common import Channel, Claude, CostGuard, log, now_iso
from .db import DB
from .publish import meta, youtube

REPLY_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["replies"],
    "properties": {"replies": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["id", "reply", "skip"],
                                                            "properties": {"id": {"type": "integer"}, "reply": {"type": "string"}, "skip": {"type": "boolean", "description": "true for spam, one-word comments, or anything not worth answering"}}}}},
}


def main():
    db = DB()
    if not CostGuard(db).check("engage", 0.3):
        return
    for key in Channel.keys():
        try:
            engage_channel(db, Channel(key))
        except Exception as e:
            log.error("engage %s failed: %s", key, e)


def engage_channel(db, channel):
    claude = Claude(db, channel=channel)
    youtube.use_channel(channel); meta.use_channel(channel)
    ids = {c["id"] for c in db.select("content", {"channel": channel.key})}
    pub_ids = {p["id"] for p in db.select("publications") if p["content_id"] in ids}
    auto = db.setting("auto_reply", {})
    auto_like = db.setting("auto_like", {})
    max_per_day = int(db.setting("max_replies_per_day", 40))
    tone = db.setting("reply_tone_notes", "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sent_today = len(db.select("comments", {"reply_status": "sent"}, gte={"reply_sent_at": today}))

    new = [c for c in db.select("comments", {"reply_status": "new"}, order="posted_at", desc=True, limit=200) if c["publication_id"] in pub_ids][:60]
    if not new:
        log.info("engage[%s]: nothing new", channel.key)
        return
    # Draft in one batch, grouped with the video title for context.
    ctx = []
    for c in new:
        pub = db.one("publications", {"id": c["publication_id"]}) or {}
        content = db.one("content", {"id": pub.get("content_id")}) or {}
        ctx.append({"id": c["id"], "platform": c["platform"], "video": content.get("title"), "author": c.get("author"), "comment": c["text"]})
    prompt = (
        "Draft a reply to each comment below as the channel persona. Rules: two sentences max, warm and direct, "
        "answer the actual point, ask one follow-up question when natural, never argue, never promise outcomes, never give medical, legal, or financial advice, "
        "no emojis on YouTube, at most one emoji on Instagram/Facebook. Skip spam, pure insults, or one-word comments. "
        f"Tone notes from the owner: {tone}\n\nComments:\n{json.dumps(ctx, ensure_ascii=False, indent=1)}"
    )
    res, _ = claude.run("engage", prompt, schema=REPLY_SCHEMA, effort="low", max_tokens=6000)
    drafts = {r["id"]: r for r in res["replies"]}
    for c in new:
        d = drafts.get(c["id"])
        if not d or d["skip"]:
            db.update("comments", {"id": c["id"]}, {"reply_status": "skipped"})
            continue
        db.update("comments", {"id": c["id"]}, {"draft_reply": d["reply"], "reply_status": "drafted"})
        if c.get("flagged") or not auto.get(c["platform"]) or sent_today >= max_per_day:
            continue
        try:
            if c["platform"] == "youtube":
                youtube.reply(c["platform_comment_id"], d["reply"])
            elif c["platform"] == "instagram":
                meta.ig_reply(c["platform_comment_id"], d["reply"])
            elif c["platform"] == "facebook":
                meta.fb_reply(c["platform_comment_id"], d["reply"])
                if auto_like.get("facebook"):
                    try:
                        meta.fb_like(c["platform_comment_id"])
                        db.update("comments", {"id": c["id"]}, {"liked": True})
                    except Exception:
                        pass
            db.update("comments", {"id": c["id"]}, {"reply_status": "sent", "reply_sent_at": now_iso()})
            sent_today += 1
        except Exception as e:
            log.warning("reply failed %s: %s", c["id"], e)
            db.update("comments", {"id": c["id"]}, {"reply_status": "failed"})
    log.info("engage: drafted %d, sent today %d", len(drafts), sent_today)


if __name__ == "__main__":
    main()
