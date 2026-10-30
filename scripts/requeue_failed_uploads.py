"""Recover legacy YouTube upload failures; defaults to a read-only plan."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.db import DB
from pipeline.retry import restore
from pipeline.publish import _persist_queue, _next_slot
from pipeline.common import Channel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = DB()
    for pub in db.select("publications", {"platform": "youtube", "status": "failed"}):
        if "ResumableUploadError" not in (pub.get("error") or ""):
            continue
        row = db.one("content", {"id": pub["content_id"]})
        try:
            row = restore(db, row, pub)
        except Exception as exc:
            print(f"Skip {pub['id']} ({pub['content_id']}): media unavailable ({type(exc).__name__})")
            continue
        print(f"{'Queue' if args.apply else 'Would queue'} {pub['id']} ({pub['content_id']})")
        if args.apply:
            fields = _persist_queue(db, row)
            if not pub.get("publish_at"):
                fields["publish_at"] = _next_slot(db, row["kind"], Channel(row.get("channel") or "futurework"), content_id=row["id"]).isoformat()
            db.update("publications", {"id": pub["id"]}, {"status": "queued", "error": None, **fields})


if __name__ == "__main__":
    main()
