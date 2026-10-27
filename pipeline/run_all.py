"""Produce one long video + its Shorts, QA them, optionally publish.

Usage:
  python -m pipeline.run_all --dry-run            # fixture script, placeholder footage, no Claude, no upload
  python -m pipeline.run_all --no-publish         # real Claude + Pexels, renders to out/, no upload
  python -m pipeline.run_all --publish            # full run, privacy from settings (private until audit passes)
  python -m pipeline.run_all --publish --privacy public
"""
from __future__ import annotations

import argparse
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .common import OUT_DIR, ROOT, Claude, CostGuard, log, now_iso, slugify, write_json
from .db import DB
from .footage import Footage
from .ideate import choose_topic
from .qa import run_qa
from .render import render, segments_from_timings
from .script import write_script
from .shorts import make_short
from .thumbnail import make_thumbnail
from .tts import synthesize

FIXTURE = ROOT / "data" / "fixture_script.json"


def produce_one(db: DB, claude: Claude | None, footage: Footage, *, dry_run: bool, publish: bool, privacy: str | None) -> dict:
    voice = db.setting("tts_voice", "en-US-AndrewMultilingualNeural")
    shorts_per_long = int(db.setting("shorts_per_long", 2))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if dry_run:
        data = json.loads(FIXTURE.read_text())
        topic = {"topic": data["topic"], "angle": "", "source_url": None, "source_headline": None, "queue_id": None}
    else:
        topic = choose_topic(db, claude)
        if not topic:
            raise RuntimeError("No topic available")
    content_id = f"{today}-{slugify(topic['topic'])}"
    out_dir = OUT_DIR / content_id
    out_dir.mkdir(parents=True, exist_ok=True)
    db.upsert("content", {"id": content_id, "kind": "long", "topic": topic["topic"], "title": topic["topic"], "status": "draft"}, on="id")
    if topic.get("queue_id"):
        db.update("topic_queue", {"id": topic["queue_id"]}, {"status": "used"})

    data = data if dry_run else write_script(claude, topic, content_id)
    write_json(out_dir / "script.json", data)

    tts = synthesize(data["script"], out_dir, voice=voice)
    segs = segments_from_timings(tts["timings"], data["shot_list"])
    video = render(segs, tts["audio"], tts["srt"], out_dir / f"{content_id}.mp4", "landscape", footage)
    thumb = make_thumbnail(video, data["thumbnail_text"], out_dir / f"{content_id}.jpg")

    chapters = []
    for ch in data.get("chapters", []):
        t = next((x for x in tts["timings"] if x["index"] == ch["paragraph_index"]), None)
        if t:
            chapters.append({"title": ch["title"], "sec": round(t["start"])})
    if chapters and chapters[0]["sec"] != 0:
        chapters.insert(0, {"title": "Intro", "sec": 0})
    desc = data["description"]
    if chapters and "0:00" not in desc:
        desc += "\n\nChapters:\n" + "\n".join(f"{c['sec']//60:02d}:{c['sec']%60:02d} {c['title']}" for c in chapters)

    db.update("content", {"id": content_id}, {
        "title": data["title"], "title_variants": data["title_variants"], "description": desc,
        "script": "\n\n".join(data["script"]), "chapters": chapters, "tags": data.get("tags", []),
        "duration_sec": tts["duration"], "file_path": str(video), "thumbnail_path": str(thumb), "status": "rendered",
    })

    qa = {"pass": True, "issues": []}
    if claude:
        qa = run_qa(claude, video, thumb, tts["duration"], content_id, out_dir / "qa")
    db.update("content", {"id": content_id}, {"qa_status": "passed" if qa["pass"] else "failed", "qa_notes": "; ".join(qa["issues"])})
    if not qa["pass"]:
        raise RuntimeError(f"QA failed for {content_id}: {qa['issues']}")

    shorts = []
    for i, s in enumerate(data.get("shorts", [])[:shorts_per_long]):
        sid = f"{content_id}-short-{i+1}"
        try:
            res = make_short(s, out_dir, voice, footage, name=sid)
        except Exception as e:
            log.error("short %s failed: %s", sid, e)
            continue
        db.upsert("content", {"id": sid, "kind": "short", "parent_id": content_id, "topic": topic["topic"], "title": res["title"],
                              "description": f"{res['title']}\n\nFull video: {{LONG_URL}}\n#shorts", "script": res["script"],
                              "duration_sec": res["duration"], "file_path": str(res["file"]), "status": "rendered", "qa_status": "passed"}, on="id")
        shorts.append({"id": sid, **res})

    result = {"content_id": content_id, "video": str(video), "thumbnail": str(thumb), "shorts": [str(s["file"]) for s in shorts], "title": data["title"]}
    if publish:
        from .publish import publish_all
        result["publications"] = publish_all(db, content_id, privacy or db.setting("publish_privacy", "private"))
    write_json(out_dir / "result.json", result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="fixture script, placeholder footage, no Claude")
    ap.add_argument("--placeholder", action="store_true", help="placeholder footage even with a Pexels key")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--privacy", choices=["private", "public", "unlisted"])
    ap.add_argument("--count", type=int, default=None, help="long videos this run (default from settings)")
    args = ap.parse_args()

    db = DB()
    run = db.insert("runs", {"workflow": "produce", "status": "running"})
    if db.setting("pipeline_paused", False) and not args.dry_run:
        log.warning("pipeline paused from dashboard; exiting")
        db.update("runs", {"id": run["id"]}, {"status": "skipped", "finished_at": now_iso(), "log": "paused"})
        return
    claude = None if args.dry_run else Claude(db)
    guard = None if args.dry_run else CostGuard(db)
    footage = Footage(placeholder=args.dry_run or args.placeholder)
    count = args.count or int(db.setting("long_videos_per_run", 1))
    if guard and not guard.check("produce", est_usd=1.0):
        count = min(count, 1)
    results, errors = [], []
    for _ in range(count):
        try:
            results.append(produce_one(db, claude, footage, dry_run=args.dry_run, publish=args.publish and not args.no_publish, privacy=args.privacy))
        except Exception as e:
            errors.append(f"{e}\n{traceback.format_exc()}")
            log.error("produce failed: %s", e)
    db.update("runs", {"id": run["id"]}, {"status": "failed" if errors and not results else "ok", "finished_at": now_iso(),
                                          "log": json.dumps({"results": results, "errors": errors})[:20000]})
    print(json.dumps(results, indent=2))
    if errors and not results:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
