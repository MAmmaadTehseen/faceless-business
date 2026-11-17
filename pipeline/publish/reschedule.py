"""Re-slot not-yet-public YouTube publications under the current channel calendar.

Growth log round 2 (2026-11-17): one upload a day per channel left a backlog that
stretched into December, so the shorter Shorts format could not reach the public for
weeks. plan() recomputes slots for every future, non-public YouTube publication of a
channel in its original order (long videos keep their cron days, child Shorts follow
their parent under shorts_same_day / shorts_spacing_hours / max_youtube_per_day);
apply() writes the new publish_at to YouTube (status.publishAt, 51 units each,
reserved) and the database. Never touches public videos or other channels.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..common import Channel, log
from . import _next_slot, youtube
from .quota import reserve


def _dt(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class _Overlay:
    """DB view where the publications being re-slotted carry their new publish_at (or none yet)."""

    def __init__(self, db, overrides):
        self.db, self.overrides, self.sb = db, overrides, getattr(db, "sb", None)

    def select(self, table, *a, **kw):
        rows = self.db.select(table, *a, **kw)
        if table != "publications":
            return rows
        out = []
        for r in rows:
            if r["id"] in self.overrides:
                r = {**r, "publish_at": self.overrides[r["id"]]}
            out.append(r)
        return out

    def __getattr__(self, name):
        return getattr(self.db, name)


def movable(db, channel: Channel, now=None):
    """Future, non-public YouTube publications of the channel, oldest slot first."""
    now = now or datetime.now(timezone.utc)
    content = {c["id"]: c for c in db.select("content", {"channel": channel.key})}
    rows = []
    for p in db.select("publications", {"platform": "youtube"}):
        c = content.get(p["content_id"])
        if not c or p.get("status") not in ("live", "queued") or not p.get("publish_at") or p.get("privacy") == "public":
            continue
        if _dt(p["publish_at"]) <= now + timedelta(hours=1):
            continue
        rows.append((p, c))
    rows.sort(key=lambda pc: (_dt(pc[0]["publish_at"]), pc[1].get("kind") != "long"))
    return rows


def plan(db, channel: Channel, now=None) -> list[dict]:
    """[{publication, content, old, new}] in assignment order; new == old when nothing moves."""
    now = now or datetime.now(timezone.utc)
    rows = movable(db, channel, now)
    overrides = {p["id"]: None for p, _ in rows}
    view = _Overlay(db, overrides)
    new_by_content: dict[str, datetime] = {}
    last_child: dict[str, datetime] = {}
    existing = {p["content_id"]: _dt(p["publish_at"]) for p in db.select("publications", {"platform": "youtube"}) if p.get("publish_at")}
    out = []
    for p, c in rows:
        kind = "long" if c.get("kind") == "long" else "short"
        parent = c.get("parent_id")
        if kind == "short" and parent:
            parent_slot = new_by_content.get(parent) or existing.get(parent)
            slot = _next_slot(view, "short", channel, now=now, parent_slot=parent_slot, after=last_child.get(parent), content_id=c["id"])
            last_child[parent] = slot
        else:
            slot = _next_slot(view, kind, channel, now=now, content_id=c["id"])
        overrides[p["id"]] = slot.isoformat()
        new_by_content[c["id"]] = slot
        out.append({"publication": p, "content": c, "old": _dt(p["publish_at"]), "new": slot})
    return out


def apply(db, channel: Channel, items: list[dict], max_updates: int | None = None) -> int:
    """Push changed slots to YouTube (live rows) and the database. Returns rows changed.

    max_updates caps YouTube status updates per call (51 units each) so a sync run leaves
    quota for other work; the rest moves on a later run.
    """
    youtube.use_channel(channel)
    changed = 0
    updates = 0
    for it in items:
        p, new = it["publication"], it["new"]
        if new == it["old"]:
            continue
        if p["status"] == "live" and p.get("platform_id") and max_updates is not None and updates >= max_updates:
            log.info("reschedule: per-run cap of %d YouTube updates reached; the rest waits", max_updates)
            break
        if p["status"] == "live" and p.get("platform_id"):
            if not reserve(db, 51):
                log.warning("reschedule: quota exhausted before %s; stopping", p["content_id"])
                break
            updates += 1
            try:
                v = youtube.yt().videos().list(part="status", id=p["platform_id"]).execute()["items"][0]
                if v["status"].get("privacyStatus") == "public":
                    log.info("reschedule: %s already public, skipped", p["content_id"])
                    continue
                v["status"]["privacyStatus"] = "private"
                v["status"]["publishAt"] = new.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                youtube.yt().videos().update(part="status", body={"id": p["platform_id"], "status": v["status"]}).execute()
            except Exception as e:
                details = youtube.error_details(e)
                if any(r in str(details.get("reason")) for r in youtube.QUOTA_REASONS):
                    log.warning("reschedule: YouTube quota exhausted at %s; the rest waits for the next run", p["content_id"])
                    break
                log.warning("reschedule: %s not moved (%s)", p["content_id"], details.get("reason"))
                continue
        db.update("publications", {"id": p["id"]}, {"publish_at": new.isoformat()})
        log.info("reschedule: %s %s -> %s", p["content_id"], it["old"].isoformat(), new.isoformat())
        changed += 1
    return changed


def compress(db, channel: Channel) -> int:
    """Sync entry point: re-slot the channel's future uploads under its calendar and push changes."""
    if db.setting("compress_schedule_enabled", True) is False:
        return 0
    items = plan(db, channel)
    if not any(i["new"] != i["old"] for i in items):
        return 0
    return apply(db, channel, items, max_updates=int(db.setting("compress_schedule_max_per_run", 20)))
