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

from .common import OUT_DIR, ROOT, Channel, Claude, CostGuard, log, now_iso, slugify, write_json
from .db import DB
from .footage import Footage
from .ideate import choose_topic
from .qa import probe, run_qa
from .render import render, segments_from_timings
from .script import write_script
from .shorts import make_short
from .thumbnail import make_thumbnail
from .tts import synthesize

FIXTURE = ROOT / "data" / "fixture_script.json"


def produce_one(db: DB, claude: Claude | None, footage: Footage, *, dry_run: bool, publish: bool, privacy: str | None, resume: str | None = None, channel: Channel | None = None) -> dict:
    channel = channel or (claude.channel if claude else Channel())
    voice = channel.voice or db.setting("tts_voice", "en-US-AndrewMultilingualNeural")
    shorts_per_long = channel.shorts_per_long
    style = channel.style
    accent = tuple(style.get("accent", (255, 214, 0)))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if resume:
        content_id = resume
        out_dir = OUT_DIR / content_id
        # Resume must reuse the retained long render, never silently regenerate it.
        for required in (out_dir / "script.json", out_dir / f"{content_id}.mp4"):
            if not required.is_file():
                raise FileNotFoundError(f"Cannot resume {content_id}: missing required artifact file: {required}")
        data = json.loads((out_dir / "script.json").read_text())
        row = db.one("content", {"id": content_id}) or {}
        topic = {"topic": row.get("topic") or data.get("title"), "angle": "", "source_url": None, "source_headline": None, "queue_id": None}
        if publish and row.get("placeholder"):
            raise RuntimeError("Refusing to publish a resumed placeholder video")
        log.info("resuming %s", content_id)
    elif dry_run:
        data = json.loads(FIXTURE.read_text())
        topic = {"topic": data["topic"], "angle": "", "source_url": None, "source_headline": None, "queue_id": None}
    else:
        topic = choose_topic(db, claude, channel)
        if not topic:
            raise RuntimeError("No topic available")
    if not resume:
        content_id = f"{channel.key}-{today}-{slugify(topic['topic'], 40)}"
        out_dir = OUT_DIR / content_id
        out_dir.mkdir(parents=True, exist_ok=True)
        db.upsert("content", {"id": content_id, "channel": channel.key, "kind": "long", "topic": topic["topic"], "title": topic["topic"], "status": "draft"}, on="id")
        if topic.get("queue_id"):
            db.update("topic_queue", {"id": topic["queue_id"]}, {"status": "used"})
        data = data if dry_run else write_script(claude, topic, content_id, shorts_per_long)
        write_json(out_dir / "script.json", data)

    video = out_dir / f"{content_id}.mp4"
    timings_file = out_dir / "voice_timings.json"
    reused_render = bool(resume and video.exists())
    if reused_render:
        timings = json.loads(timings_file.read_text()) if timings_file.exists() else []
        tts = {"timings": timings, "duration": timings[-1]["end"] if timings else probe(video)["duration"],
               "audio": out_dir / "voice.mp3", "srt": out_dir / "voice.srt"}
    else:
        tts = synthesize(data["script"], out_dir, voice=voice)
        segs = segments_from_timings(tts["timings"], data["shot_list"])
        video = render(segs, tts["audio"], tts["srt"], video, "landscape", footage, style=style)
    thumb = out_dir / f"{content_id}.jpg"
    if not (resume and thumb.exists()):
        thumb = make_thumbnail(video, data["thumbnail_text"], thumb, accent=accent)

    chapters = (row.get("chapters") or []) if reused_render and not tts["timings"] else []
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
        "duration_sec": tts["duration"], "file_path": str(video), "thumbnail_path": str(thumb), "status": "rendered", "placeholder": bool(row.get("placeholder")) if reused_render else footage.placeholder,
    })

    qa = {"pass": True, "issues": []}
    if claude:
        qa = run_qa(claude, video, thumb, tts["duration"], content_id, out_dir / "qa", vision=not (bool(row.get("placeholder")) if reused_render else footage.placeholder), db=db)
    thumb = qa.get("thumbnail") or thumb
    db.update("content", {"id": content_id}, {"qa_status": "passed" if qa["pass"] else "failed", "qa_notes": json.dumps(qa["issues"]), "thumbnail_path": str(thumb)})
    if not qa["pass"]:
        db.update("content", {"id": content_id}, {"status": "qa_failed"})
        raise RuntimeError(f"QA failed for {content_id}: {qa['issues']}")

    shorts = []
    for i, s in enumerate(data.get("shorts", [])[:shorts_per_long]):
        sid = f"{content_id}-short-{i+1}"
        existing = db.one("content", {"id": sid}) if resume else None
        if existing and existing.get("qa_status") == "passed" and Path(existing.get("file_path") or "").is_file():
            shorts.append({"id": sid, "file": Path(existing["file_path"])})
            continue
        try:
            short_file = out_dir / f"{sid}.mp4"
            if resume and short_file.exists():
                res = {"file": short_file, "duration": probe(short_file)["duration"],
                       "title": s["hook_title"], "script": s["script"]}
            else:
                res = make_short(s, out_dir, voice, footage, name=sid, style=style)
        except Exception as e:
            log.error("short %s failed: %s", sid, e)
            continue
        short_qa = run_qa(claude, res["file"], None, res["duration"], sid, out_dir / f"qa-{sid}", vision=not footage.placeholder, db=db)
        db.upsert("content", {"id": sid, "channel": channel.key, "kind": "short", "parent_id": content_id,
                              "topic": topic["topic"], "title": res["title"], "file_path": str(res["file"]),
                              "description": f"{res['title']}\n\nFull video: {{LONG_URL}}\n#shorts", "script": res["script"],
                              "duration_sec": res["duration"], "placeholder": footage.placeholder,
                              "status": "rendered" if short_qa["pass"] else "qa_failed",
                              "qa_status": "passed" if short_qa["pass"] else "failed",
                              "qa_notes": json.dumps(short_qa["issues"])}, on="id")
        if not short_qa["pass"]:
            log.error("short %s failed QA: %s", sid, short_qa["issues"])
            continue
        if publish and not footage.placeholder:
            try:
                from .publish import meta
                db.update("content", {"id": sid}, {"media_url": meta.public_url_for(res["file"], tag=f"media-{datetime.now(timezone.utc):%Y%m%d}")})
            except Exception as e:
                log.warning("short %s: could not store public media url (%s)", sid, type(e).__name__)
        shorts.append({"id": sid, **res})

    result = {"content_id": content_id, "video": str(video), "thumbnail": str(thumb), "shorts": [str(s["file"]) for s in shorts], "title": data["title"]}
    if publish:
        from .publish import publish_all
        result["publications"] = publish_all(db, content_id, privacy or db.setting("publish_privacy", "private"), channel)
    if dry_run or (publish and any(
        p.get("platform") == "youtube" and p.get("content_id") == content_id
        for p in result.get("publications", [])
    )):
        try:
            from .article import write_article
            write_article(db, content_id, claude=claude, dry_run=dry_run)
        except Exception as e:
            log.warning("article skipped for %s (%s)", content_id, type(e).__name__)
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
    ap.add_argument("--resume", help="content id in out/ to continue from its rendered video (thumbnail, QA, shorts, publish)")
    ap.add_argument("--channel", default=None, help="channel key (folder in channels/). Default: futurework, or inferred from --resume id")
    args = ap.parse_args()

    db = DB()
    ckey = args.channel or (args.resume.split("-20")[0] if args.resume and not args.resume.startswith("20") else None) or "futurework"
    channel = Channel(ckey)
    log.info("channel: %s (%s)", channel.key, channel.name)
    run = db.insert("runs", {"workflow": "produce", "channel": channel.key, "status": "running"})
    if db.setting("pipeline_paused", False) and not args.dry_run:
        log.warning("pipeline paused from dashboard; exiting")
        db.update("runs", {"id": run["id"]}, {"status": "skipped", "finished_at": now_iso(), "log": "paused"})
        return
    claude = None if args.dry_run else Claude(db, channel=channel)
    guard = None if args.dry_run else CostGuard(db)
    footage = Footage(placeholder=args.dry_run or args.placeholder, providers=channel.footage.get("providers"))
    if args.publish and footage.placeholder:
        log.error("refusing to publish with placeholder footage (no footage API key)")
        raise SystemExit(2)
    count = 1 if args.resume else (args.count or int(db.setting("long_videos_per_run", 1)))
    if guard and not guard.check("produce", est_usd=1.0):
        db.update("runs", {"id": run["id"]}, {"status": "skipped", "finished_at": now_iso(), "log": "budget guard"})
        return
    results, errors = [], []
    for _ in range(count):
        if guard and not guard.check("produce", est_usd=1.0):
            break
        try:
            results.append(produce_one(db, claude, footage, dry_run=args.dry_run, publish=args.publish and not args.no_publish, privacy=args.privacy, resume=args.resume, channel=channel))
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
