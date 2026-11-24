"""YouTube search terms that brought viewers to each channel (Analytics insightTrafficSourceDetail).

    PYTHONPATH=. .venv/bin/python scripts/search_terms.py                       # all four channels, 28 days
    PYTHONPATH=. .venv/bin/python scripts/search_terms.py --channels tentongues --days 7 --json data/search_terms.json

Studio shows search as 65% of Escape Velocity's long-video views (2026-11-24), so the exact phrases
viewers typed are the best evidence for titles and topics. Read-only; Analytics quota only.
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
from scripts.yt_scoreboard import channel_for  # noqa: E402

CHANNELS = ["futurework", "tradewinds", "escapevelocity", "tentongues"]


def search_terms(days: int = 28, limit: int = 25) -> list[dict]:
    """Top YouTube search terms for the selected channel, most views first."""
    end = datetime.now(timezone.utc).date()
    res = youtube.yt_analytics().reports().query(
        ids="channel==MINE", startDate=(end - timedelta(days=days)).isoformat(), endDate=end.isoformat(),
        metrics="views,estimatedMinutesWatched", dimensions="insightTrafficSourceDetail",
        filters="insightTrafficSourceType==YT_SEARCH", sort="-views", maxResults=limit,
    ).execute()
    return rows_to_terms(res.get("rows", []))


def rows_to_terms(rows: list) -> list[dict]:
    return [{"term": r[0], "views": int(r[1]), "minutes": round(float(r[2]), 1)} for r in rows if r and r[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", nargs="*", default=CHANNELS)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json")
    args = ap.parse_args()
    out = {}
    for key in args.channels:
        try:
            youtube.use_channel(channel_for(key))
            out[key] = search_terms(args.days, args.limit)
        except Exception as e:
            log.warning("search terms skipped %s: %s", key, type(e).__name__)
            continue
        total = sum(t["views"] for t in out[key])
        print(f"\n## {key}: {len(out[key])} terms, {total} search views in {args.days} days")
        for t in out[key]:
            print(f"{t['views']:>5}  {t['term']}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "days": args.days,
                                               "channels": out}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
