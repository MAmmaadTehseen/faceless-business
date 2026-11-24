"""Weekly retention review: find where viewers leave, and feed those moments back into the prompts.

Growth log 2026-11-24: a hand-run look at four retention curves showed every long video losing a
quarter to a third of its viewers at seconds 10-21, right where the opening turned to background.
This automates that. Once a week per channel (from sync), for recent public videos with enough
views, it reads the Analytics retention curve, finds the steepest drop, and stores the narration
spoken at that moment (estimated from the word count) as a negative example, plus the
best-holding opening as a positive one, in setting `retention_lessons_<channel>`. `prompt_block`
turns them into a short prompt section for the next scripts. No model calls; Analytics quota only,
plus one 1-unit videos.list per 50 videos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .common import log
from .publish import youtube

MIN_VIEWS = 15
MAX_VIDEOS = 20
KEY = "retention_lessons_"


def _curve(video_id: str) -> list[tuple[float, float]]:
    end = datetime.now(timezone.utc).date()
    res = youtube.yt_analytics().reports().query(
        ids="channel==MINE", startDate=(end - timedelta(days=90)).isoformat(), endDate=end.isoformat(),
        metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio", filters=f"video=={video_id}",
    ).execute()
    return [(float(r[0]), float(r[1])) for r in res.get("rows", [])]


def _at(points, ratio):
    return next((y for x, y in points if x >= ratio - 1e-9), None)


def snippet(script: str, ratio: float, words: int = 14) -> str:
    """The narration around a point in the video, estimated by word position (speech is near-uniform)."""
    tokens = (script or "").split()
    if not tokens:
        return ""
    mid = min(len(tokens) - 1, max(0, int(ratio * len(tokens))))
    lo, hi = max(0, mid - words // 2), min(len(tokens), mid + words // 2)
    return " ".join(tokens[lo:hi])


def analyse(points: list[tuple[float, float]], duration: float, script: str) -> dict | None:
    """Steepest drop after the first 3 % (the first points are noisy autoplay), and 30 s retention."""
    if len(points) < 10 or not duration:
        return None
    drops = [(points[i][0], points[i - 1][1] - points[i][1]) for i in range(1, len(points)) if points[i][0] > 0.03]
    if not drops:
        return None
    at, drop = max(drops, key=lambda d: d[1])
    return {"drop_at_s": round(at * duration), "drop": round(drop, 2),
            "kept_30s": round(_at(points, min(1.0, 30 / duration)) or 0, 2),
            "left_during": snippet(script, at), "opening": snippet(script, 0.0, 30)}


def review(db, channel) -> dict | None:
    """Recompute this channel's lessons at most once a week. Returns the stored lessons when it ran."""
    stamp_key = f"retention_review_at_{channel.key}"
    last = db.setting(stamp_key)
    now = datetime.now(timezone.utc)
    if last and now - datetime.fromisoformat(str(last)) < timedelta(days=7):
        return None
    if not youtube.configured() or youtube.auth_failed(channel):
        return None
    youtube.use_channel(channel)
    content = {c["id"]: c for c in db.select("content", {"channel": channel.key})}
    pubs = [p for p in db.select("publications", {"platform": "youtube", "status": "live"})
            if p["content_id"] in content and p.get("platform_id") and p.get("privacy") == "public"]
    pubs = sorted(pubs, key=lambda p: p.get("publish_at") or "", reverse=True)[:MAX_VIDEOS * 2]
    stats = youtube.stats([p["platform_id"] for p in pubs]) if pubs else {}
    rows = {"long": [], "short": []}
    for p in pubs:
        c = content[p["content_id"]]
        if (stats.get(p["platform_id"]) or {}).get("views", 0) < MIN_VIEWS:
            continue
        try:
            found = analyse(_curve(p["platform_id"]), float(c.get("duration_sec") or 0), c.get("script") or "")
        except Exception as e:
            log.warning("retention review: curve failed for %s (%s)", p["platform_id"], type(e).__name__)
            continue
        if found:
            kind = "short" if c.get("kind") == "short" else "long"
            rows[kind].append({"title": c.get("title") or "", **found})
    lessons = {}
    for kind, found in rows.items():
        if not found:
            continue
        worst = sorted(found, key=lambda r: -r["drop"])[:3]
        best = max(found, key=lambda r: r["kept_30s"])
        lessons[kind] = {"worst": worst, "best": best, "n": len(found)}
    db.set_setting(stamp_key, now.isoformat())
    if lessons:
        db.set_setting(KEY + channel.key, {"at": now.isoformat(), **lessons})
        log.info("retention review[%s]: %s", channel.key, {k: v["n"] for k, v in lessons.items()})
    return lessons


def prompt_block(db, channel_key: str, kind: str) -> str:
    """Measured drop-off moments for the next script prompt; empty until a review has run."""
    try:
        data = (db.setting(KEY + channel_key) or {}).get(kind) if db else None
    except Exception:
        return ""
    if not data:
        return ""
    lines = [f"Measured retention on this channel's recent {'Shorts' if kind == 'short' else 'long videos'} "
             "(YouTube Analytics; avoid what lost viewers, copy what kept them):"]
    for w in data.get("worst", []):
        lines.append(f"- '{w['title'][:60]}' lost {int(w['drop'] * 100)}% of viewers at {w['drop_at_s']} s, "
                     f"while the narration said: \"{w['left_during']}\"")
    b = data.get("best")
    if b:
        lines.append(f"- Best hold: '{b['title'][:60]}' kept {int(b['kept_30s'] * 100)}% at 30 s; its opening: \"{b['opening']}\"")
    return "\n".join(lines) + "\n"
