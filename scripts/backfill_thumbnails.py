"""Regenerate and re-set thumbnails for scheduled (private, future) long videos.

    PYTHONPATH=. .venv/bin/python scripts/backfill_thumbnails.py --channel escapevelocity            # dry run: writes out/thumbs/<video id>.jpg
    PYTHONPATH=. .venv/bin/python scripts/backfill_thumbnails.py --channel escapevelocity --apply    # thumbnails.set, 50 units each

Text: one small model call per video producing 2-5 subject/number words (falls back to the title's
first clause). Frame: a stock clip for the title's subject via the normal footage providers, since
the rendered video is not on this machine. Design: pipeline.thumbnail.make_thumbnail.
"""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pipeline.common import Channel, Claude, OUT_DIR, log  # noqa: E402
from pipeline.db import DB  # noqa: E402
from pipeline.footage import Footage  # noqa: E402
from pipeline.publish import youtube  # noqa: E402
from pipeline.publish.quota import THUMB_COST, reserve  # noqa: E402
from pipeline.thumbnail import make_thumbnail  # noqa: E402

TEXT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["thumbnail_text", "image_query"],
               "properties": {"thumbnail_text": {"type": "string"}, "image_query": {"type": "string"}}}


def fallback_text(title: str) -> str:
    first = re.split(r"[:.?!]", title)[0]
    return " ".join(first.upper().split()[:4])


def plan_text(claude, title: str, content_id: str) -> tuple[str, str]:
    if claude is None:
        return fallback_text(title), title
    prompt = ("Write YouTube thumbnail text for this video title: 2-5 uppercase words that say what the video is about, "
              "using the named subject (organisation, mission, product, country) and/or the key number from the title. "
              "Never a vague teaser (no 'NOT SO SAFE', 'WHO KEEPS IT', 'STILL WAITING'). Also give a 2-4 word generic "
              "stock-footage query for a background image (objects, places, machines; no names of people or companies).\n\n"
              f"Title: {title}")
    try:
        data, _ = claude.run("thumbnail_text", prompt, schema=TEXT_SCHEMA, effort="low", max_tokens=400, content_id=content_id, retries=1)
        text = " ".join(str(data.get("thumbnail_text", "")).upper().split()[:5]) or fallback_text(title)
        return text, str(data.get("image_query") or title)
    except Exception as e:
        log.warning("thumbnail text model call failed (%s); using title", type(e).__name__)
        return fallback_text(title), title


def frame_for(footage: Footage, query: str, out: Path) -> Path | None:
    for q in (query, " ".join(query.split()[:2]), "city skyline"):
        clip = footage.clip(q, 4.0, orientation="landscape")
        if clip:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5", "-i", str(clip), "-frames:v", "1", "-q:v", "2", str(out)], check=True)
            return out
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-model", action="store_true")
    args = ap.parse_args()
    db, channel = DB(), Channel(args.channel)
    claude = None if args.no_model else Claude(db, channel=channel)
    footage = Footage()
    youtube.use_channel(channel)
    now = datetime.now(timezone.utc).isoformat()
    pubs = db.sb.table("publications").select("content_id,platform_id,publish_at").eq("platform", "youtube").eq("status", "live") \
        .eq("privacy", "private").gt("publish_at", now).execute().data or []
    ids = [p["content_id"] for p in pubs]
    rows = []
    for i in range(0, len(ids), 100):
        rows += db.sb.table("content").select("id,channel,kind,title").in_("id", ids[i:i + 100]).eq("kind", "long").eq("channel", channel.key).execute().data or []
    pub = {p["content_id"]: p for p in pubs}
    accent = tuple(channel.style.get("accent", (255, 214, 0)))
    work = OUT_DIR / "thumbs"
    work.mkdir(parents=True, exist_ok=True)
    done = 0
    for r in sorted(rows, key=lambda r: pub[r["id"]]["publish_at"]):
        vid = pub[r["id"]]["platform_id"]
        text, query = plan_text(claude, r["title"], r["id"])
        frame = frame_for(footage, query, work / f"{vid}.frame.jpg")
        if not frame:
            print(f"SKIP {vid} no frame | {r['title'][:50]}")
            continue
        out = make_thumbnail(Path("/nonexistent.mp4"), text, work / f"{vid}.jpg", frame=frame, accent=accent)
        print(f"{pub[r['id']]['publish_at'][:10]} {vid} | {text:28} | {query:24} | {r['title'][:45]}")
        if args.apply:
            if not reserve(db, THUMB_COST):
                print("quota reserve refused; stopping")
                break
            youtube.set_thumbnail(vid, out)
            done += 1
            print("   set")
    print(f"{len(rows)} scheduled longs, {done} thumbnails set")


if __name__ == "__main__":
    main()
