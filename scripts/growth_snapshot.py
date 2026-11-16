"""Read-only growth snapshot for docs/growth-log.md: per platform/channel/kind for the last N days.

Usage: PYTHONPATH=. .venv/bin/python scripts/growth_snapshot.py [--days 30] [--json out.json]
Reads Supabase through pipeline.db (SUPABASE_URL/SUPABASE_SERVICE_KEY from .env). Never writes.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from pipeline.db import DB


def page(db, table, **gte):
    out, off = [], 0
    while True:
        q = db.sb.table(table).select("*")
        for k, v in gte.items():
            q = q.gte(k, v)
        rows = q.order("id").range(off, off + 999).execute().data or []
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def dt(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json")
    args = ap.parse_args()
    db = DB()
    if db.kind != "supabase":
        raise SystemExit("needs Supabase configuration")
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=args.days)).isoformat()
    content = {c["id"]: c for c in page(db, "content")}
    pubs = page(db, "publications")
    latest = {}
    for m in sorted(page(db, "metrics", captured_at=since), key=lambda m: m["captured_at"]):
        latest[m["publication_id"]] = m
    rows = []
    for p in pubs:
        if p["status"] != "live":
            continue
        c = content.get(p["content_id"]) or {}
        m = latest.get(p["id"]) or {}
        when = dt(p.get("publish_at") or p.get("published_at"))
        if p["platform"] == "youtube" and when and when > now:
            continue  # scheduled, not public yet
        rows.append({"platform": p["platform"], "channel": c.get("channel"), "kind": c.get("kind"), "title": c.get("title"),
                     "views": m.get("views") or 0, "likes": m.get("likes") or 0, "comments": m.get("comments") or 0,
                     "ret": m.get("ctr"), "avd": m.get("avg_view_duration_sec"), "dur": c.get("duration_sec"),
                     "age_days": max((now - when).days, 1) if when else None, "content_id": p["content_id"]})
    groups = defaultdict(list)
    for r in rows:
        groups[(r["platform"], r["channel"], r["kind"])].append(r)
    print(f"snapshot {now:%Y-%m-%d} last {args.days} days (public only)")
    print("| platform | channel | kind | n | median views | mean views | views/day median | median retention % | median AVD s | zero-view | comments |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        g = groups[key]
        views = [r["views"] for r in g]
        vpd = [r["views"] / r["age_days"] for r in g if r["age_days"]]
        ret = [r["ret"] * 100 for r in g if r["ret"] is not None]
        avd = [r["avd"] for r in g if r["avd"] is not None]
        print(f"| {key[0]} | {key[1]} | {key[2]} | {len(g)} | {st.median(views):.0f} | {st.mean(views):.0f} | "
              f"{st.median(vpd) if vpd else 0:.1f} | {st.median(ret) if ret else float('nan'):.0f} | {st.median(avd) if avd else float('nan'):.0f} | "
              f"{sum(1 for v in views if not v)} | {sum(r['comments'] for r in g)} |")
    top = sorted((r for r in rows if r["platform"] == "youtube"), key=lambda r: -r["views"])[:10]
    print("\nTop YouTube (views, retention %, channel, title):")
    for r in top:
        print(f"- {r['views']} | {(r['ret'] or 0) * 100:.0f}% | {r['channel']} {r['kind']} | {r['title']}")
    try:
        hub = db.sb.rpc("hub_analytics", {"since": since, "until_ts": now.isoformat()}).execute().data
        print("\nhub:", json.dumps(hub.get("total")), "countries:", [d for d in hub.get("dimensions", []) if d["kind"] == "countries"][:3])
    except Exception as exc:
        print("hub analytics unavailable:", type(exc).__name__)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
