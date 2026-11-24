"""Audience retention curves for public long videos (YouTube Analytics elapsedVideoTimeRatio).

    PYTHONPATH=. .venv/bin/python scripts/retention_curves.py                     # explainer channels
    PYTHONPATH=. .venv/bin/python scripts/retention_curves.py --channels tentongues --json data/retention.json

Prints, per video, the share of viewers still watching at 5/10/20/30 s, 25/50 % and the steepest drop
between curve points, so the opening can be judged against the script. Read-only; Analytics quota
only (no Data API units beyond the scoreboard's uploads scan).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from pipeline.common import log  # noqa: E402
from pipeline.publish import youtube  # noqa: E402
from scripts.yt_scoreboard import channel_for, channel_videos  # noqa: E402


def curve(video_id: str, days: int = 90) -> list[tuple[float, float]]:
    """(elapsed ratio, audienceWatchRatio) pairs; watch ratio is 1.0 at the start for most videos."""
    end = datetime.now(timezone.utc).date()
    res = youtube.yt_analytics().reports().query(
        ids="channel==MINE", startDate=(end - timedelta(days=days)).isoformat(), endDate=end.isoformat(),
        metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio", filters=f"video=={video_id}",
    ).execute()
    return [(float(r[0]), float(r[1])) for r in res.get("rows", [])]


def at(points: list[tuple[float, float]], ratio: float) -> float | None:
    """Watch ratio at the first curve point at or after `ratio` (curves have 100 points)."""
    for x, y in points:
        if x >= ratio - 1e-9:
            return y
    return None


def summarise(row: dict, points: list[tuple[float, float]]) -> dict:
    dur = row["seconds"] or 1
    out = {"id": row["id"], "channel": row["channel"], "title": row["title"], "views": row["views"], "seconds": dur}
    for s in (5, 10, 20, 30, 60):
        out[f"s{s}"] = round(at(points, s / dur) or 0, 2)
    out["p25"] = round(at(points, 0.25) or 0, 2)
    out["p50"] = round(at(points, 0.50) or 0, 2)
    drops = [(points[i][0], points[i - 1][1] - points[i][1]) for i in range(1, len(points))]
    worst = max(drops, key=lambda d: d[1], default=(0, 0))
    out["worst_drop_at_s"] = round(worst[0] * dur)
    out["worst_drop"] = round(worst[1], 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", nargs="*", default=["futurework", "tradewinds", "escapevelocity"])
    ap.add_argument("--min-views", type=int, default=15)
    ap.add_argument("--json")
    args = ap.parse_args()
    results = []
    for key in args.channels:
        try:
            rows = [r for r in channel_videos(key) if r["kind"] == "long" and r["views"] >= args.min_views]
        except Exception as e:
            log.warning("retention skipped %s: %s", key, type(e).__name__)
            continue
        youtube.use_channel(channel_for(key))
        for r in rows:
            try:
                pts = curve(r["id"])
            except Exception as e:
                log.warning("curve failed %s: %s", r["id"], type(e).__name__)
                continue
            if pts:
                results.append(summarise(r, pts))
    print("| channel | views | len | 5s | 10s | 20s | 30s | 60s | 25% | 50% | worst drop | title |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in sorted(results, key=lambda s: -s["views"]):
        print(f"| {s['channel']} | {s['views']} | {s['seconds']}s | {s['s5']} | {s['s10']} | {s['s20']} | {s['s30']} | {s['s60']} "
              f"| {s['p25']} | {s['p50']} | -{s['worst_drop']} at {s['worst_drop_at_s']}s | {s['title'][:50]} |")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
