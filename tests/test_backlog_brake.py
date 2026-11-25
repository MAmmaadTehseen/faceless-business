"""Fresh long-video production pauses while the channel's long queue reaches too far ahead."""
from argparse import Namespace
from datetime import datetime, timedelta, timezone

from pipeline.common import Channel
from pipeline.publish import long_backlog_days
from pipeline.run_all import backlog_full
from tests.test_schedule import MemoryDB

NOW = datetime.now(timezone.utc)


def _db(days_ahead, privacy="private", kind="long", channel="futurework"):
    db = MemoryDB()
    db.tables["content"].append({"id": "L", "channel": channel, "kind": kind})
    db.tables["publications"].append({"id": "1", "content_id": "L", "platform": "youtube", "status": "live",
                                      "privacy": privacy, "publish_at": (NOW + timedelta(days=days_ahead)).isoformat()})
    return db


def _args(**kw):
    base = dict(resume=None, dry_run=False, bank=False, publish=True, no_publish=False)
    return Namespace(**{**base, **kw})


def test_backlog_days_counts_only_future_private_longs():
    ch = Channel("futurework")
    assert 29 < long_backlog_days(_db(30), ch) <= 30
    assert long_backlog_days(_db(30, privacy="public"), ch) == 0
    assert long_backlog_days(_db(30, kind="short"), ch) == 0
    assert long_backlog_days(_db(30, channel="tradewinds"), ch) == 0
    assert long_backlog_days(MemoryDB(), ch) == 0


def test_brake_skips_fresh_publish_runs_only():
    ch = Channel("futurework")
    assert backlog_full(_db(30), ch, _args())
    assert not backlog_full(_db(5), ch, _args())
    for kw in ({"resume": "x"}, {"dry_run": True}, {"bank": True}, {"publish": False}, {"no_publish": True}):
        assert not backlog_full(_db(30), ch, _args(**kw))


def test_brake_can_be_switched_off():
    db = _db(30)
    db.setting = lambda key, default=None: False if key == "production_backlog_brake_enabled" else default
    assert not backlog_full(db, Channel("futurework"), _args())
