"""Produce one fresh, standalone vertical Short per channel per UTC day."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from .common import Channel, Claude, CostGuard, OUT_DIR, log, now_iso, slugify, write_json
from .db import DB
from .footage import Footage
from .ideate import fetch_news
from .publish import publish_short
from .qa import run_qa
from .script import BANNED_TITLE, SCRIPT_SCHEMA, strip_script_dashes
from .shorts import make_short

DAILY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["hook_title", "script", "query", "description", "tags", "facts_check"],
    "properties": {
        "hook_title": {"type": "string"},
        "script": {"type": "string", "description": "120-160 spoken words; self-contained with a hook in the first line"},
        "query": {"type": "string", "description": "Generic physical stock video search"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "facts_check": SCRIPT_SCHEMA["properties"]["facts_check"],
    },
}


def fresh_topic(db, channel):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    recent = db.select("content", {"channel": channel.key}, gte={"created_at": cutoff})
    used = db.select("topic_queue", {"channel": channel.key, "status": "used"}, gte={"created_at": cutoff})
    titles = [r.get(k) or "" for r in recent + used for k in ("topic", "title", "source_headline")]
    def fresh(title):
        normalized = slugify(title, 500)
        return all(SequenceMatcher(None, normalized, slugify(t, 500)).ratio() < 0.65 for t in titles if t)
    queued = db.select("topic_queue", {"channel": channel.key, "status": "queued"}, order="priority", desc=True)
    for q in queued:
        if fresh(q["topic"]) and fresh(q.get("source_headline") or q["topic"]):
            return {"topic": q["topic"], "source_url": q.get("source_url"), "queue_id": q["id"]}, titles
    news = fetch_news(db.setting(f"niche_keywords_{channel.key}") or channel.keywords)
    for n in news:
        if fresh(n["headline"]):
            return {"topic": n["headline"], "source_url": n["url"], "queue_id": None}, titles
    raise RuntimeError("No fresh topic outside this channel's last 14 days")


def produce_daily(db, channel, *, dry_run=False, placeholder=False, no_publish=False, privacy=None):
    if db.setting("pipeline_paused", False) and not dry_run:
        log.info("daily short: pipeline paused")
        return None
    if not dry_run and not CostGuard(db).check("short_daily", est_usd=0.3):
        return None
    today = datetime.now(timezone.utc).date().isoformat()
    # Daily jobs may be retried: do not create another topic/upload for this date.
    prefix = f"{channel.key}-{today}-short-"
    existing = next((r for r in db.select("content", {"channel": channel.key, "kind": "short", "parent_id": None}) if r["id"].startswith(prefix)), None)
    if existing and existing.get("qa_status") == "passed" and not dry_run and not existing.get("placeholder"):
        if not no_publish:
            publish_short(db, existing, channel, privacy or db.setting("publish_privacy", "private"))
        return {"content_id": existing["id"], "video": existing["file_path"]}
    claude = None if dry_run else Claude(db, channel=channel)
    if dry_run:
        from .run_all import FIXTURE
        fixture = json.loads(FIXTURE.read_text())
        data = {**fixture["shorts"][0], "description": "Standalone fixture Short. #shorts", "tags": fixture.get("tags", []), "facts_check": []}
        topic = {"topic": data["hook_title"], "queue_id": None}
    else:
        topic, recent = fresh_topic(db, channel)
        content_id = f"{prefix}{slugify(topic['topic'], 40)}"
        prompt = (
            f"Write a standalone daily Short about {topic['topic']}. Source seed: {topic.get('source_url') or ''}.\n"
            "Use web search to verify recent facts; at most 3 searches. Follow the channel persona. "
            "120-160 spoken words, a specific hook on the first line, one clear idea with a payoff and human stakes. "
            "The Short must stand alone without a long video. Title under 50 characters. "
            "No income promises, medical/legal/financial advice, fabricated claims or unsupported statistics. "
            "Use simple natural spoken English without filler or generic transitions. Hedge uncertain causes, "
            "attribute every statistic in-line and use no em dashes. "
            "Include attributable source URLs in facts_check and description. Use a generic physical footage query. "
            f"Do not repeat any of these recent topics or titles: {json.dumps(recent)}"
        )
        data, _ = claude.run("short_daily", prompt, schema=DAILY_SCHEMA, effort="medium", web_search=True,
                             max_searches=3, max_tokens=2500, retries=0, content_id=content_id)
        if not 120 <= len(data["script"].split()) <= 160:
            raise RuntimeError("Daily Short script outside 120-160 word range")
        if any(f["confidence"] == "unverified" for f in data["facts_check"]):
            raise RuntimeError("Daily Short contains unverified claims")
    data = strip_script_dashes(data)
    if BANNED_TITLE.search(data["hook_title"]):
        raise RuntimeError("Daily Short title failed policy guardrail")
    content_id = f"{prefix}{slugify(topic['topic'], 40)}"
    out = OUT_DIR / content_id
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "script.json", data)
    footage = Footage(placeholder=dry_run or placeholder, providers=channel.footage.get("providers"))
    if footage.placeholder and not (dry_run or no_publish):
        raise RuntimeError("Refusing to publish placeholder footage")
    res = make_short(data, out, channel.voice, footage, name=content_id, style=channel.style)
    qa = run_qa(claude, res["file"], None, res["duration"], content_id, out / "qa", vision=not footage.placeholder)
    row = {"id": content_id, "channel": channel.key, "kind": "short", "parent_id": None,
           "topic": topic["topic"], "title": data["hook_title"], "description": data["description"],
           "tags": data["tags"], "script": data["script"], "duration_sec": res["duration"],
           "file_path": str(res["file"]), "status": "rendered", "placeholder": footage.placeholder, "qa_status": "passed" if qa["pass"] else "failed",
           "qa_notes": "; ".join(qa["issues"])}
    db.upsert("content", row, on="id")
    if not qa["pass"]:
        raise RuntimeError(f"Daily Short QA failed: {qa['issues']}")
    if topic.get("queue_id"):
        db.update("topic_queue", {"id": topic["queue_id"]}, {"status": "used"})
    result = {"content_id": content_id, "video": str(res["file"])}
    if not dry_run and not no_publish:
        result["publications"] = publish_short(db, row, channel, privacy or db.setting("publish_privacy", "private"))
    write_json(out / "result.json", result)
    return result


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--channel", required=True, choices=Channel.keys())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--placeholder", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--privacy", choices=["private", "public", "unlisted"])
    args = ap.parse_args()
    db = DB()
    run = db.insert("runs", {"workflow": "shorts", "channel": args.channel, "status": "running"})
    try:
        result = produce_daily(db, Channel(args.channel), dry_run=args.dry_run, placeholder=args.placeholder,
                               no_publish=args.no_publish, privacy=args.privacy)
        db.update("runs", {"id": run["id"]}, {"status": "ok" if result else "skipped", "finished_at": now_iso(), "log": json.dumps(result)})
        print(json.dumps(result, indent=2))
    except Exception as e:
        db.update("runs", {"id": run["id"]}, {"status": "failed", "finished_at": now_iso(), "log": type(e).__name__})
        raise


if __name__ == "__main__":
    main()
