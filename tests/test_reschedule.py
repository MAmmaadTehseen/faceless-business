"""plan() compresses a one-per-day backlog under same-day Shorts without touching public rows."""
from datetime import datetime, timedelta, timezone

from pipeline.common import Channel
from pipeline.publish import reschedule
from tests.test_schedule import MemoryDB

NOW = datetime(2026, 11, 17, 8, tzinfo=timezone.utc)  # Tuesday


def _seed(db, channel):
    # one long per cron day plus four children one per day: slots run far into the future
    long_day = datetime(2026, 11, 19, 11, tzinfo=timezone.utc)  # Thursday for tradewinds
    db.tables['content'].append({"id": "L", "channel": channel.key, "kind": "long"})
    db.upsert("publications", {"content_id": "L", "platform": "youtube", "status": "live", "platform_id": "vL",
              "privacy": "private", "publish_at": long_day.isoformat()}, "content_id,platform")
    for i in range(4):
        cid = f"S{i}"
        db.tables['content'].append({"id": cid, "channel": channel.key, "kind": "short", "parent_id": "L"})
        db.upsert("publications", {"content_id": cid, "platform": "youtube", "status": "live" if i < 2 else "queued",
                  "platform_id": f"v{i}", "privacy": "private",
                  "publish_at": (long_day + timedelta(days=10 + i)).replace(hour=15).isoformat()}, "content_id,platform")
    # already public: must never move
    db.tables['content'].append({"id": "P", "channel": channel.key, "kind": "short"})
    db.upsert("publications", {"content_id": "P", "platform": "youtube", "status": "live", "platform_id": "vP",
              "privacy": "public", "publish_at": (NOW - timedelta(days=1)).isoformat()}, "content_id,platform")
    return long_day


def test_plan_moves_children_onto_parent_days_and_keeps_order():
    db, channel = MemoryDB(), Channel("tradewinds")
    long_day = _seed(db, channel)
    items = reschedule.plan(db, channel, now=NOW)
    by = {i["content"]["id"]: i for i in items}
    assert "P" not in by
    new_long = datetime(2026, 11, 17, 11, tzinfo=timezone.utc)  # nearest free cron day (Tuesday, > now + 1 h)
    assert by["L"]["new"] == new_long
    news = [by[f"S{i}"]["new"] for i in range(4)]
    assert news == sorted(news)
    assert news[0] == new_long.replace(hour=15) and news[1] == new_long.replace(hour=19)
    assert news[2] == (new_long + timedelta(days=1)).replace(hour=15)
    assert max(news) < new_long + timedelta(days=2)
    assert sum(i["new"] != i["old"] for i in items) == 5


def test_apply_updates_youtube_for_live_rows_and_db_for_all(monkeypatch):
    db, channel = MemoryDB(), Channel("tradewinds")
    _seed(db, channel)
    items = reschedule.plan(db, channel, now=NOW)
    calls = []

    class V:
        def list(self, part, id):
            return type("E", (), {"execute": lambda s: {"items": [{"status": {"privacyStatus": "private"}}]}})()

        def update(self, part, body):
            calls.append(body)
            return type("E", (), {"execute": lambda s: {}})()

    monkeypatch.setattr(reschedule.youtube, "yt", lambda: type("Y", (), {"videos": lambda s: V()})())
    monkeypatch.setattr(reschedule.youtube, "use_channel", lambda c: None)
    monkeypatch.setattr(reschedule, "reserve", lambda db, units: True)
    assert reschedule.apply(db, channel, items) == 5
    assert sorted(b["id"] for b in calls) == ["v0", "v1", "vL"]  # queued rows need no API call
    assert all(b["status"]["privacyStatus"] == "private" and b["status"]["publishAt"].endswith("Z") for b in calls)
    assert db.one("publications", {"content_id": "S3"})["publish_at"] == items[-1]["new"].isoformat()


def test_apply_respects_per_run_update_cap(monkeypatch):
    db, channel = MemoryDB(), Channel("tradewinds")
    _seed(db, channel)
    items = reschedule.plan(db, channel, now=NOW)
    calls = []

    class V:
        def list(self, part, id):
            return type("E", (), {"execute": lambda s: {"items": [{"status": {"privacyStatus": "private"}}]}})()

        def update(self, part, body):
            calls.append(body["id"])
            return type("E", (), {"execute": lambda s: {}})()

    monkeypatch.setattr(reschedule.youtube, "yt", lambda: type("Y", (), {"videos": lambda s: V()})())
    monkeypatch.setattr(reschedule.youtube, "use_channel", lambda c: None)
    monkeypatch.setattr(reschedule, "reserve", lambda db, units: True)
    assert reschedule.apply(db, channel, items, max_updates=1) == 1
    assert calls == ["vL"]
