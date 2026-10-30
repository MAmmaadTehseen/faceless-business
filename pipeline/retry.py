"""Owner-requested retries. No generation, QA bypass, or local quota blocking."""
from __future__ import annotations

import argparse
import json
import io
import os
import zipfile
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


def _json(value):
    try:
        parsed = json.loads(value or "{}") if isinstance(value, str) else value
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def production_notes(issues, channel, workflow):
    """Keep provenance in existing content metadata, without a schema migration."""
    run_id = os.getenv("GITHUB_RUN_ID")
    if not run_id:
        return json.dumps(issues)
    prefix = "videos" if workflow == "produce" else "shorts"
    return json.dumps({"issues": issues, "artifact_run_id": run_id,
                       "artifact_name": f"{prefix}-{channel.key}-{run_id}"})


def _api(endpoint, binary=False):
    result = subprocess.run(["gh", "api", endpoint], check=True,
                            capture_output=True, timeout=900)
    return result.stdout if binary else json.loads(result.stdout)


def _artifact_file(row, run_id, artifact_name=None):
    expected = Path(row.get("file_path") or f"{row['id']}.mp4").name
    artifacts = _api(f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/artifacts?per_page=100")
    for artifact in artifacts.get("artifacts", []):
        if artifact.get("expired") or (artifact_name and artifact["name"] != artifact_name):
            continue
        # GitHub exposes no archive member listing. Inspect in memory and extract
        # only the requested final file; never restore unrelated run outputs.
        data = _api(f"repos/{{owner}}/{{repo}}/actions/artifacts/{artifact['id']}/zip", binary=True)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            matches = [n for n in archive.namelist() if Path(n).name == expected]
            if len(matches) == 1:
                target = OUT_DIR / row["id"] / expected
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(matches[0]))
                return str(target)
    return None


def restore(db, row, pub):
    row = dict(row)
    if row.get("file_path") and Path(row["file_path"]).is_file():
        return row
    tried = []
    if row.get("media_url"):
        tried.append("content.media_url")
        try:
            row["file_path"] = str(_local_file(db, row))
            return row
        except Exception:
            pass
    tried.append("youtube-queue/release media_key")
    queue_pub = dict(db.one("publications", {"content_id": row["id"], "platform": "youtube"}) or {})
    queue_pub.update({k: v for k, v in pub.items() if v is not None})
    try:
        row = _restore_queue(db, row, queue_pub)
        if row.get("file_path") and Path(row["file_path"]).is_file():
            return row
    except Exception:
        pass
    info = {**_json(row.get("qa_notes")), **_json(pub.get("error"))}
    run_id = pub.get("artifact_run_id") or row.get("artifact_run_id") or info.get("artifact_run_id")
    artifact = pub.get("artifact_name") or row.get("artifact_name") or info.get("artifact_name")
    tried.append("producing GitHub artifact")
    if run_id and str(run_id).isdigit():
        try:
            path = _artifact_file(row, run_id, artifact)
            if path:
                return {**row, "file_path": path}
        except Exception:
            pass
    tried.append("recent produce.yml/shorts.yml artifacts")
    for workflow in ("produce.yml", "shorts.yml"):
        try:
            runs = _api(f"repos/{{owner}}/{{repo}}/actions/workflows/{workflow}/runs?per_page=30")
            for run in runs.get("workflow_runs", []):
                try:
                    path = _artifact_file(row, run["id"])
                    if path:
                        return {**row, "file_path": path}
                except Exception:
                    continue
        except Exception:
            pass
    if pub.get("platform") in {"instagram", "facebook"}:
        yt = db.one("publications", {"content_id": row["id"], "platform": "youtube"}) or {}
        if yt.get("status") == "live" and db.sb:
            tried.append("public media bucket production upload")
            try:
                date = row["id"].removeprefix(row.get("channel", "") + "-")[:10].replace("-", "")
                name = Path(row.get("file_path") or f"{row['id']}.mp4").name
                url = db.sb.storage.from_("media").get_public_url(f"media-{date}/{name}")
                row["file_path"] = str(_local_file(db, {**row, "media_url": url}))
                row["media_url"] = url
                db.update("content", {"id": row["id"]}, {"media_url": url})
                return row
            except Exception:
                pass
    raise FileNotFoundError("media not recoverable: " + ", ".join(tried))


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
        if isinstance(exc, FileNotFoundError):
            details["message"] = str(exc)
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
