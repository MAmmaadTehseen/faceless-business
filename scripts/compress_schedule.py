"""Compress a channel's YouTube publish backlog under its current calendar settings.

    PYTHONPATH=. .venv/bin/python scripts/compress_schedule.py --channel tradewinds           # dry run
    PYTHONPATH=. .venv/bin/python scripts/compress_schedule.py --channel tradewinds --apply   # update YouTube + DB

Only future, non-public YouTube publications move. Live rows cost 51 quota units each.
"""
import argparse

from dotenv import load_dotenv

load_dotenv()

from pipeline.common import Channel  # noqa: E402
from pipeline.db import DB  # noqa: E402
from pipeline.publish import reschedule  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db, channel = DB(), Channel(args.channel)
    items = reschedule.plan(db, channel)
    moved = [i for i in items if i["new"] != i["old"]]
    for i in items:
        mark = "->" if i["new"] != i["old"] else "=="
        print(f"{i['content']['kind']:5} {i['publication']['status']:6} {i['old']:%Y-%m-%d %H:%M} {mark} {i['new']:%Y-%m-%d %H:%M}  {i['content']['id']}")
    print(f"{len(items)} scheduled, {len(moved)} would move, last slot {max((i['new'] for i in items), default=None)}")
    if args.apply and moved:
        print("applied:", reschedule.apply(db, channel, items))


if __name__ == "__main__":
    main()
