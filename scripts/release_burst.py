"""Release N banked bundles per channel now, every video GAP hours apart (owner request 2026-11-25).

Bypasses the channel calendar for these videos only: each video takes the first time at least
GAP hours from every other scheduled video of the channel, starting an hour from now. Released
content ids are added to setting schedule_pinned_<channel> so sync's schedule compression keeps
the spacing. Quota limits apply as usual; rerun to continue after quota resets (already released
bundles are skipped, already-scheduled videos keep their slots).

  python scripts/release_burst.py --channel futurework --bundles 12 --gap 3
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import publish, release_banked  # noqa: E402
from pipeline.common import Channel, log  # noqa: E402
from pipeline.db import DB  # noqa: E402
from pipeline.homelab_store import backend_for  # noqa: E402
from pipeline.stockpile import notes as stockpile_notes  # noqa: E402


def spaced_slot(db, channel, gap, now=None, exclude=None):
    now = now or datetime.now(timezone.utc)
    ids = {c["id"] for c in db.select("content", {"channel": channel.key})}
    taken = sorted(datetime.fromisoformat(str(p["publish_at"]).replace("Z", "+00:00"))
                   for p in db.select("publications", {"platform": "youtube"})
                   if p["content_id"] in ids and p["content_id"] != exclude and p.get("status") in ("live", "queued", "uploading") and p.get("publish_at"))
    t = (now + timedelta(hours=1)).replace(second=0, microsecond=0)
    while True:
        clash = [o for o in taken if abs((o - t).total_seconds()) < gap * 3600]
        if not clash:
            return t
        t = max(clash) + timedelta(hours=gap)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", required=True, choices=Channel.keys())
    ap.add_argument("--bundles", type=int, default=12)
    ap.add_argument("--gap", type=float, default=3.0)
    args = ap.parse_args()
    db, channel = DB(), Channel(args.channel)
    key = f"schedule_pinned_{channel.key}"

    def slot(db_, kind, ch=None, **kw):
        cid = kw.get("content_id")
        existing = db.one("publications", {"content_id": cid, "platform": "youtube"}) if cid else None
        pinned = db.setting(key, None) or []
        if existing and existing.get("publish_at") and (existing.get("platform_id") or cid in pinned):
            return datetime.fromisoformat(existing["publish_at"].replace("Z", "+00:00"))
        if cid:
            db.set_setting(key, list(dict.fromkeys([*pinned, cid])))
        new = spaced_slot(db, channel, args.gap, exclude=cid)
        if existing and existing.get("status") == "queued":
            # Queued from an earlier calendar release: move it onto the spaced schedule before upload.
            db.update("publications", {"id": existing["id"]}, {"publish_at": new.isoformat()})
        return new

    publish._next_slot = slot  # release_one and publish_all resolve the slot through this module attribute
    from pipeline.publish import youtube
    from pipeline.stockpile import lock
    youtube.use_channel(channel)
    if not youtube.configured() or youtube.auth_failed(channel):
        raise SystemExit(f"{channel.key}: YouTube not configured or auth expired")
    with lock(db, "release_" + channel.key, wait_seconds=1800):
        done = burst(db, channel, args.bundles)
    print(f"{channel.key}: released {done} bundles")


def burst(db, channel, bundles):
    done = 0
    for row in release_banked.pending(db, channel):
        if done >= bundles:
            break
        children = db.select("content", {"parent_id": row["id"]})
        if not release_banked.capacity(db, [row, *children]):
            log.warning("quota full; rerun after the reset (08:00 UTC)")
            break
        if not release_banked.release_one(db, channel, row, backend_for(stockpile_notes(row)['stockpile'])):
            log.warning("%s not fully released (quota or upload); rerun later", row["id"])
            break
        done += 1
        log.info("released %s (%d/%d)", row["id"], done, bundles)
    return done


if __name__ == "__main__":
    main()
