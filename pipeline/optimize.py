"""Swap title (and thumbnail text) on YouTube long videos 48h-7d old that are underperforming:
views per day since publish below the channel median (the Analytics API exposes no impressions/CTR;
the `ctr` column holds average view percentage, used as a tie-breaker). One swap per video."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import Claude, CostGuard, log
from .db import DB
from .publish import youtube
from .thumbnail import make_thumbnail

PICK = {"type": "object", "additionalProperties": False, "required": ["title", "thumbnail_text", "reason"],
        "properties": {"title": {"type": "string"}, "thumbnail_text": {"type": "string"}, "reason": {"type": "string"}}}


def main():
    db = DB()
    if not youtube.configured():
        log.info("optimize: youtube not configured")
        return
    claude = Claude(db)
    if not CostGuard(db).check("optimize", 0.3):
        return
    now = datetime.now(timezone.utc)
    pubs = db.select("publications", {"platform": "youtube", "status": "live"})
    rows = []
    for p in pubs:
        c = db.one("content", {"id": p["content_id"]})
        if not c or c["kind"] != "long" or not p.get("published_at"):
            continue
        age = now - datetime.fromisoformat(p["published_at"].replace("Z", "+00:00"))
        m = db.latest_metrics(p["id"])
        if m and p.get("privacy") == "public":
            days = max(age.total_seconds() / 86400, 0.5)
            rows.append((p, c, age, (m.get("views") or 0) / days, int(m.get("views") or 0)))
    if len(rows) < 4:
        log.info("optimize: not enough public videos with metrics (%d)", len(rows))
        return
    rates = sorted(r[3] for r in rows)
    median = rates[len(rates) // 2]
    swapped = 0
    for p, c, age, ctr, imp in rows:
        if not (timedelta(hours=48) <= age <= timedelta(days=7)) or ctr >= median or imp < 50:
            continue
        variants = c.get("title_variants") or []
        if any(isinstance(v, str) and v.startswith("[swapped]") for v in variants) or not variants:
            continue
        prompt = (f"This video gets {ctr:.1f} views/day against a channel median of {median:.1f} views/day ({imp} views so far).\n"
                  f"Current title: {c['title']}\nUntested variants: {variants}\nScript opening: {(c.get('script') or '')[:600]}\n"
                  "Pick the variant most likely to lift CTR (or write a better one that follows the formulas and the policy rules), "
                  "and give new 3-word thumbnail text. No clickbait the video does not deliver.")
        try:
            pick, _ = claude.run("optimize", prompt, schema=PICK, effort="medium", max_tokens=1500, content_id=c["id"])
            youtube.update_title(p["platform_id"], pick["title"])
            if c.get("file_path") and Path(c["file_path"]).exists():
                thumb = make_thumbnail(Path(c["file_path"]), pick["thumbnail_text"], Path(c["file_path"]).with_suffix(".v2.jpg"))
                youtube.set_thumbnail(p["platform_id"], thumb)
            new_variants = [f"[swapped] {c['title']} -> {pick['title']} @views/day {ctr:.1f}"] + [v for v in variants if v != pick["title"]]
            db.update("content", {"id": c["id"]}, {"title": pick["title"], "title_variants": new_variants})
            swapped += 1
            log.info("optimize: swapped %s -> %s (%s)", c["title"], pick["title"], pick["reason"])
        except Exception as e:
            log.warning("optimize failed for %s: %s", c["id"], e)
    log.info("optimize: %d swaps (median %.1f views/day)", swapped, median)


if __name__ == "__main__":
    main()
