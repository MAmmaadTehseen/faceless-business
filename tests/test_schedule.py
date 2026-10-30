"""Deterministic UTC calendar regressions, without network or persistent state."""
from datetime import datetime, timedelta, timezone

import pytest

from pipeline.common import Channel
from pipeline.publish import _next_slot


class MemoryDB:
    sb = None

    def __init__(self):
        self.tables = {"content": [], "publications": []}

    def select(self, table, filters=None, order=None):
        rows = [dict(r) for r in self.tables[table]
                if all(r.get(k) == v for k, v in (filters or {}).items())]
        return sorted(rows, key=lambda r: r[order]) if order else rows

    def one(self, table, filters):
        return next(iter(self.select(table, filters)), None)

    def update(self, table, filters, fields):
        for row in self.tables[table]:
            if all(row.get(k) == v for k, v in filters.items()):
                row.update(fields)

    def upsert(self, table, row, on):
        filters = {k: row[k] for k in on.split(',')}
        if self.one(table, filters):
            self.update(table, filters, row)
        else:
            self.tables[table].append({"id": str(len(self.tables[table])), **row})

    def occupy(self, channel, slot, kind="short", status="live"):
        cid = str(len(self.tables['content']))
        self.tables['content'].append({"id": cid, "channel": channel.key, "kind": kind})
        self.upsert("publications", {"content_id": cid, "platform": "youtube",
                    "status": status, "publish_at": slot.isoformat()}, "content_id,platform")


NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)  # Friday
CHANNELS = [("futurework", 30, 6, 13, 3), ("tradewinds", 31, 11, 15, 3),
            ("escapevelocity", 1, 16, 18, 1)]


@pytest.mark.parametrize('key,day,hour,short_hour,gap', CHANNELS)
def test_channel_calendar(key, day, hour, short_hour, gap):
    db, channel = MemoryDB(), Channel(key)
    expected = datetime(2026, 11 if day == 1 else 10, day, hour, tzinfo=timezone.utc)
    long = _next_slot(db, 'long', channel, now=NOW)
    assert long == expected
    db.occupy(channel, long, 'long')
    assert _next_slot(db, 'long', channel, now=NOW) == long + timedelta(days=gap)
    previous = None
    for offset in range(1, 5):
        slot = _next_slot(db, 'short', channel, now=NOW, parent_slot=long, after=previous)
        assert slot == (long + timedelta(days=offset)).replace(hour=short_hour)
        assert slot >= NOW + timedelta(hours=1)
        db.occupy(channel, slot)
        previous = slot
    daily = _next_slot(db, 'short', channel, now=NOW)
    assert daily == NOW.replace(hour=20)
    db.occupy(channel, daily)
    assert _next_slot(db, 'short', channel, now=NOW) == daily + timedelta(days=1)
    assert long >= NOW + timedelta(hours=1)


@pytest.mark.parametrize('key,day,hour,short_hour,gap', CHANNELS)
def test_daily_cap_and_failed_slots(key, day, hour, short_hour, gap):
    db, channel = MemoryDB(), Channel(key)
    daily = NOW.replace(hour=20)
    db.occupy(channel, daily, status='failed')
    assert _next_slot(db, 'short', channel, now=NOW) == daily
    for hour in (5, 10, 15):
        db.occupy(channel, NOW.replace(hour=hour), status='queued')
    assert _next_slot(db, 'short', channel, now=NOW) == daily + timedelta(days=1)


@pytest.mark.parametrize('key,day,hour,short_hour,gap', CHANNELS)
@pytest.mark.parametrize('minutes', [-60, -30, 0, 30])
def test_long_lead_time_preserves_cron(key, day, hour, short_hour, gap, minutes):
    channel, db = Channel(key), MemoryDB()
    first = _next_slot(db, 'long', channel, now=NOW)
    now = first + timedelta(minutes=minutes)
    slot = _next_slot(db, 'long', channel, now=now)
    assert slot >= now + timedelta(hours=1)
    assert slot == (first if minutes == -60 else first + timedelta(days=gap))


@pytest.mark.parametrize('key,day,hour,short_hour,gap', CHANNELS)
def test_daily_lead_time_and_config_override(key, day, hour, short_hour, gap):
    channel, db = Channel(key), MemoryDB()
    now = NOW.replace(hour=19, minute=30)
    assert _next_slot(db, 'short', channel, now=now) == NOW.replace(hour=20) + timedelta(days=1)
    channel.cfg = {**channel.cfg, 'shorts_hour_utc': 12, 'daily_short_hour_utc': 22}
    assert _next_slot(db, 'short', channel, now=NOW) == NOW.replace(hour=22)
    assert _next_slot(db, 'short', channel, now=NOW, parent_slot=NOW) == (NOW + timedelta(days=1)).replace(hour=12)
