"""Weekly: Claude reviews top/bottom performers and appends learnings to persona/style.md; promotes best scripts to examples."""
from __future__ import annotations

from datetime import datetime, timezone

from .common import PERSONA_DIR, Claude, CostGuard, log
from .db import DB

REVIEW = {"type": "object", "additionalProperties": False, "required": ["learnings", "promote_ids", "keyword_suggestions"],
          "properties": {"learnings": {"type": "string", "description": "Markdown bullets, concrete and actionable, max 12 lines"},
                         "promote_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
                         "keyword_suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 6}}}


def main():
    db = DB()
    claude = Claude(db)
    if not CostGuard(db).check("review", 1.0):
        return
    pubs = db.select("publications", {"platform": "youtube", "status": "live"})
    rows = []
    for p in pubs:
        c = db.one("content", {"id": p["content_id"]})
        m = db.latest_metrics(p["id"])
        if c and m:
            rows.append({"id": c["id"], "kind": c["kind"], "title": c["title"], "views": m["views"], "likes": m["likes"], "comments": m["comments"],
                         "ctr": m.get("ctr"), "avd": m.get("avg_view_duration_sec"), "dur": c.get("duration_sec"), "opening": (c.get("script") or "")[:300]})
    if len(rows) < 6:
        log.info("review: not enough published videos yet (%d)", len(rows))
        return
    rows.sort(key=lambda r: (r["views"] or 0), reverse=True)
    top, bottom = rows[:5], rows[-5:]
    prompt = ("Weekly performance review for the channel. Top 5 and bottom 5 by views, with CTR and average view duration where available.\n"
              f"TOP:\n{top}\n\nBOTTOM:\n{bottom}\n\n"
              "What patterns separate them (topics, title formulas, openings, length)? Write concrete learnings as bullets that the script writer "
              "should follow next week. Then pick up to 2 content ids whose scripts should become reference examples. Then suggest up to 6 niche "
              "news keywords to add or replace, based on what is working.")
    res, _ = claude.run("review", prompt, schema=REVIEW, effort="high", max_tokens=4000)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(PERSONA_DIR / "style.md", "a") as f:
        f.write(f"\n### Review {stamp}\n{res['learnings'].strip()}\n")
    for cid in res["promote_ids"]:
        c = db.one("content", {"id": cid})
        if c and c.get("script"):
            (PERSONA_DIR / "examples" / f"{cid}.md").write_text(f"# {c['title']}\n\n{c['script']}\n")
    log.info("review: appended learnings; promoted %s; keywords %s", res["promote_ids"], res["keyword_suggestions"])
    if res["keyword_suggestions"]:
        db.set_setting("keyword_suggestions", res["keyword_suggestions"])


if __name__ == "__main__":
    main()
