"""YouTube scoreboard straight from the API (no Supabase): every public upload per channel with
views, age, views/day, average % viewed and format, plus progress against the owner's targets
(10,000 views per long video, 40,000 per Short).

    PYTHONPATH=. .venv/bin/python scripts/yt_scoreboard.py               # all channels, table
    PYTHONPATH=. .venv/bin/python scripts/yt_scoreboard.py --json out.json

Cost: about 3-6 quota units per channel. Read-only. Used by the 6-hourly growth loop.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pipeline.common import Channel, log  # noqa: E402
from pipeline.publish import youtube  # noqa: E402

TARGET = {"long": 10_000, "short": 40_000}
CHANNELS = ["futurework", "tradewinds", "escapevelocity", "tentongues", "filmreview"]


def seconds(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def channel_for(key: str):
    """Frame and Argument (filmreview) lives outside Channel.keys(); it has its own class and local.json."""
    if key == "filmreview":
        from pipeline.recap.channel import FilmReviewChannel
        return FilmReviewChannel()
    return Channel(key)


def channel_videos(key: str, max_items: int = 200) -> list[dict]:
    ch = channel_for(key)
    youtube.use_channel(ch)
    me = youtube.yt().channels().list(part="contentDetails,statistics", mine=True).execute()["items"][0]
    uploads = me["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < max_items:
        res = youtube.yt().playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        token = res.get("nextPageToken")
        if not token:
            break
    # The uploads playlist can repeat items across pages (seen 2026-11-23: 23 Future Work
    # videos twice), which inflated n and skewed medians.
    ids = list(dict.fromkeys(ids))
    rows = []
    for i in range(0, len(ids), 50):
        res = youtube.yt().videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for it in res.get("items", []):
            if it["status"]["privacyStatus"] != "public":
                continue
            published = it["status"].get("publishAt") or it["snippet"]["publishedAt"]
            age = max((datetime.now(timezone.utc) - datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00"))).total_seconds() / 86400, 0.25)
            dur = seconds(it["contentDetails"]["duration"])
            views = int(it["statistics"].get("viewCount", 0))
            rows.append({"channel": key, "id": it["id"], "title": it["snippet"]["title"], "published": published[:10],
                         "kind": "short" if dur <= 180 else "long", "seconds": dur, "views": views,
                         "likes": int(it["statistics"].get("likeCount", 0)), "comments": int(it["statistics"].get("commentCount", 0)),
                         "age_days": round(age, 1), "views_per_day": round(views / age, 1)})
    an = youtube.analytics([r["id"] for r in rows], days=90) if rows else {}
    for r in rows:
        a = an.get(r["id"], {})
        r["avg_pct"] = round(a["ctr"] * 100) if a.get("ctr") is not None else None
        r["avg_sec"] = a.get("avg_view_duration_sec")
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    out = []
    for key in CHANNELS:
        for kind in ("long", "short"):
            g = [r for r in rows if r["channel"] == key and r["kind"] == kind]
            if not g:
                continue
            v = [r["views"] for r in g]
            pct = [r["avg_pct"] for r in g if r["avg_pct"] is not None]
            out.append({"channel": key, "kind": kind, "n": len(g), "median": st.median(v), "best": max(v),
                        "share_of_target_best": round(max(v) / TARGET[kind] * 100, 2),
                        "hit_target": sum(x >= TARGET[kind] for x in v), "median_avg_pct": st.median(pct) if pct else None})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--channels", nargs="*", default=CHANNELS)
    args = ap.parse_args()
    rows = []
    for key in args.channels:
        try:
            rows += channel_videos(key)
        except Exception as e:
            log.warning("scoreboard skipped %s: %s", key, type(e).__name__)
    summary = summarise(rows)
    print(f"YouTube scoreboard {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC (public uploads; targets long 10k, short 40k)")
    print("| channel | kind | n | median views | best | best as % of target | at target | median % viewed |")
    print("|---|---|---|---|---|---|---|---|")
    for s in summary:
        print(f"| {s['channel']} | {s['kind']} | {s['n']} | {s['median']} | {s['best']} | {s['share_of_target_best']}% | {s['hit_target']} | {s['median_avg_pct']} |")
    print("\nTop 10 by views:")
    for r in sorted(rows, key=lambda r: -r["views"])[:10]:
        print(f"- {r['views']:6} | {r['avg_pct']}% viewed | {r['channel']} {r['kind']} {r['seconds']}s | {r['title'][:70]}")
    print("\nNewest 10 (age, views/day):")
    for r in sorted(rows, key=lambda r: r["published"], reverse=True)[:10]:
        print(f"- {r['published']} {r['age_days']}d | {r['views']} views, {r['views_per_day']}/day | {r['avg_pct']}% | {r['channel']} {r['kind']} | {r['title'][:60]}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "summary": summary, "videos": rows}, indent=1))


if __name__ == "__main__":
    main()
