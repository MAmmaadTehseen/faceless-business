"""Owner-run: clear YouTube's altered/synthetic-content label on already uploaded videos.

Only channels whose channel.json lacks `synthetic_media: true` are touched. Reads status in batches
of 50 (1 unit each) and updates only videos still flagged (50 units each) through the normal quota
reservation, keeping the sync/engage reserve. Privacy, schedule and the kids flag are resent unchanged.

    .venv/bin/python scripts/remove_ai_label.py --dry-run
    .venv/bin/python scripts/remove_ai_label.py --max 120            # rerun daily until "0 left"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import Channel  # noqa: E402
from pipeline.db import DB  # noqa: E402
from pipeline.publish import youtube  # noqa: E402
from pipeline.publish.quota import reserve  # noqa: E402


def flagged_ids(service, ids, everything=False):
    """videos.list omits containsSyntheticMedia for most videos, so by default every video whose
    status does not already say False is treated as labelled."""
    out = []
    for i in range(0, len(ids), 50):
        items = service.videos().list(part="status", id=",".join(ids[i:i + 50]), maxResults=50).execute().get("items", [])
        out += [v for v in items if everything or v["status"].get("containsSyntheticMedia") is not False]
    return out


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--channel", choices=Channel.keys())
    ap.add_argument("--max", type=int, default=120, help="updates this run across channels")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--everything", action="store_true", help="update even videos whose status already reads False")
    args = ap.parse_args()
    db = DB()
    budget = args.max
    for key in ([args.channel] if args.channel else Channel.keys()):
        channel = Channel(key)
        if channel.cfg.get("synthetic_media"):
            print(f"{key}: keeps the label (synthetic_media: true)")
            continue
        youtube.use_channel(channel)
        if not youtube.configured():
            print(f"{key}: no YouTube token configured; skipped")
            continue
        rows = [r for r in db.select("publications", {"platform": "youtube"})
                if r.get("platform_id") and r["content_id"].startswith(key + "-") and r.get("status") == "live"]
        # videos.list never reports the flag back, so cleared IDs are remembered in a setting.
        cleared = set(db.setting("synthetic_label_cleared", []) or [])
        ids = sorted({r["platform_id"] for r in rows} - cleared)
        reads = (len(ids) + 49) // 50
        if not ids or not reserve(db, reads):
            print(f"{key}: {len(ids)} videos, read quota unavailable" if ids else f"{key}: no videos")
            continue
        service = youtube.yt()
        flagged = flagged_ids(service, ids, args.everything)
        print(f"{key}: {len(ids)} live videos, {len(flagged)} to clear")
        done = 0
        for v in flagged:
            if budget <= 0:
                break
            status = {k: v["status"][k] for k in ("privacyStatus", "publishAt", "selfDeclaredMadeForKids") if k in v["status"]}
            status["containsSyntheticMedia"] = False
            if args.dry_run:
                print(f"  would clear {v['id']} ({status.get('privacyStatus')})")
                continue
            if not reserve(db, 50):
                print("  general quota reserve reached; rerun tomorrow")
                budget = 0
                break
            service.videos().update(part="status", body={"id": v["id"], "status": status}).execute()
            cleared.add(v["id"])
            db.set_setting("synthetic_label_cleared", sorted(cleared))
            done += 1
            budget -= 1
        print(f"{key}: cleared {done}, {len(flagged) - done} left")


if __name__ == "__main__":
    main()
