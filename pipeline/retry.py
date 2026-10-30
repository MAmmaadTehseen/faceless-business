"""Owner-requested retries. No generation, QA bypass, or local quota blocking."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .common import Channel, OUT_DIR, now_iso
from .db import DB
from .publish import (_restore_queue, _local_file, _media_url, _youtube_publish,
                      _next_slot, follow_youtube_to_reels, youtube, meta)


def plan(db, ids=None, content_id=None, platform=None):
    wanted = {str(i) for i in (ids or [])}
    return [p for p in db.select("publications")
            if p.get("status") in {"failed", "queued"}
            and p.get("platform") in {"youtube", "instagram", "facebook"}
            and (not wanted or str(p["id"]) in wanted)
            and (not content_id or p["content_id"] == content_id)
            and (not platform or p["platform"] == platform)]


def restore(db, row, pub):
    row = dict(row)
    try:
        row = _restore_queue(db, row, pub)
    except Exception:
        # Try public media/artifact sources when a queue object has expired.
        pass
    if row.get("file_path") and Path(row["file_path"]).is_file():
        return row
    if row.get("media_url"):
        row["file_path"] = str(_local_file(db, row))
        return row
    try:
        info = json.loads(pub.get("error") or "{}")
    except (ValueError, TypeError):
        info = {}
    run_id = pub.get("artifact_run_id") or row.get("artifact_run_id") or info.get("artifact_run_id")
    artifact = pub.get("artifact_name") or info.get("artifact_name")
    if run_id and str(run_id).isdigit():
        target = OUT_DIR / row["id"] / "retry-artifact"
        target.mkdir(parents=True, exist_ok=True)
        args = ["gh", "run", "download", str(run_id), "--dir", str(target)]
        if artifact:
            args += ["--name", artifact]
        subprocess.run(args, check=True, capture_output=True, timeout=900)
        files = list(target.rglob("*.mp4"))
        expected = Path(row.get("file_path") or f"{row['id']}.mp4").name
        matches = [f for f in files if f.name == expected]
        if len(matches) == 1:
            row["file_path"] = str(matches[0])
            return row
    raise FileNotFoundError("No restorable media for " + row["id"])


def retry_one(db, pub, force=False):
    try:
        row = db.one("content", {"id": pub["content_id"]})
        if not row or row.get("placeholder") or row.get("qa_status") != "passed" or row.get("status") == "killed":
            raise RuntimeError("Refusing placeholder, killed or unapproved content")
        channel = Channel(row.get("channel") or "futurework")
        youtube.use_channel(channel)
        meta.use_channel(channel)
        row = restore(db, row, pub)
        if pub["platform"] == "youtube":
            if not youtube.configured():
                raise RuntimeError("YouTube not configured")
            slot = datetime.fromisoformat(pub["publish_at"].replace("Z", "+00:00")) if pub.get("publish_at") else _next_slot(db, row["kind"], channel, content_id=row["id"])
            # Retain the audit privacy requirement for every manual upload.
            result = _youtube_publish(db, row, channel, "private", slot, force=force)
            if result:
                follow_youtube_to_reels(db, channel)
            return bool(result)
        if db.setting("publish_privacy", "private") != "public":
            raise RuntimeError("Reels require public publish_privacy")
        if row["kind"] != "short":
            raise RuntimeError("Reels require Short content")
        caption = f"{row['title']}\n\n{row.get('description') or ''}".strip()
        if pub["platform"] == "instagram":
            result = meta.publish_instagram_reel(_media_url(db, row), caption)
        else:
            result = meta.publish_facebook_reel(Path(row["file_path"]), caption)
        db.update("publications", {"id": pub["id"]}, {"status": "live", "platform_id": result["id"],
                  "url": result.get("url"), "privacy": "public", "published_at": now_iso(), "error": None})
        db.update("content", {"id": row["id"]}, {"status": "published"})
        return True
    except Exception as exc:
        details = youtube.error_details(exc)
        db.update("publications", {"id": pub["id"]}, {"status": "failed", "error": json.dumps(details)})
        print(f"Publication {pub['id']} failed: {json.dumps(details)}")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated publication IDs")
    parser.add_argument("--content-id")
    parser.add_argument("--platform", choices=["youtube", "instagram", "facebook"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.ids and not args.content_id:
        parser.error("--ids or --content-id required")
    db = DB()
    pubs = plan(db, args.ids.split(",") if args.ids else None, args.content_id, args.platform)
    failed = 0
    for pub in pubs:
        ok = retry_one(db, pub, args.force)
        print(f"Publication {pub['id']} ({pub['platform']}): {'done' if ok else 'failed'}")
        failed += not ok
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
