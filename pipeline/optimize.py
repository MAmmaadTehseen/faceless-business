"""Swap title (and thumbnail text) on YouTube long videos 48h-7d old whose CTR is below the channel median.
One swap per video. Logs the swap in title_variants so review.py can learn."""
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
        if m and m.get("ctr") is not None:
            rows.append((p, c, age, float(m["ctr"]), int(m.get("impressions") or 0)))
    if len(rows) < 4:
        log.info("optimize: not enough data (%d videos with CTR)", len(rows))
        return
    ctrs = sorted(r[3] for r in rows)
    median = ctrs[len(ctrs) // 2]
    swapped = 0
    for p, c, age, ctr, imp in rows:
        if not (timedelta(hours=48) <= age <= timedelta(days=7)) or ctr >= median or imp < 300:
            continue
        variants = c.get("title_variants") or []
        if any(isinstance(v, str) and v.startswith("[swapped]") for v in variants) or not variants:
            continue
        prompt = (f"This video has CTR {ctr:.2%} against a channel median of {median:.2%} after {imp} impressions.\n"
                  f"Current title: {c['title']}\nUntested variants: {variants}\nScript opening: {(c.get('script') or '')[:600]}\n"
                  "Pick the variant most likely to lift CTR (or write a better one that follows the formulas and the policy rules), "
                  "and give new 3-word thumbnail text. No clickbait the video does not deliver.")
        try:
            pick, _ = claude.run("optimize", prompt, schema=PICK, effort="medium", max_tokens=1500, content_id=c["id"])
            youtube.update_title(p["platform_id"], pick["title"])
            if c.get("file_path") and Path(c["file_path"]).exists():
                thumb = make_thumbnail(Path(c["file_path"]), pick["thumbnail_text"], Path(c["file_path"]).with_suffix(".v2.jpg"))
                youtube.set_thumbnail(p["platform_id"], thumb)
            new_variants = [f"[swapped] {c['title']} -> {pick['title']} @ctr {ctr:.4f}"] + [v for v in variants if v != pick["title"]]
            db.update("content", {"id": c["id"]}, {"title": pick["title"], "title_variants": new_variants})
            swapped += 1
            log.info("optimize: swapped %s -> %s (%s)", c["title"], pick["title"], pick["reason"])
        except Exception as e:
            log.warning("optimize failed for %s: %s", c["id"], e)
    log.info("optimize: %d swaps (median ctr %.2f%%)", swapped, median * 100)


if __name__ == "__main__":
    main()
