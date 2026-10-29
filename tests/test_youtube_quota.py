"""Offline quota and queue regression."""
from scripts.check_youtube_queue import main


def test_youtube_queue():
    main()


def test_rpc_checks_both_buckets():
    from unittest.mock import Mock
    from pipeline.publish.quota import reserve
    db = Mock()
    db.sb.rpc.return_value.execute.return_value.data = False
    assert not reserve(db, 50, uploads=1)
    db.sb.rpc.assert_called_once_with("reserve_youtube_quota", {
        "p_units": 50, "p_uploads": 1, "p_reserve": 1000, "p_upload_reserve": 2,
    })


def test_sqlite_existing_table_and_atomic_rejection(tmp_path, monkeypatch):
    import sqlite3
    from pipeline.db import DB
    from pipeline.publish.quota import reserve
    conn = sqlite3.connect(tmp_path / "local.db")
    conn.execute("create table quota_log(day text primary key, units int not null default 0)")
    conn.close()
    monkeypatch.setattr("pipeline.db.DATA_DIR", tmp_path)
    db = DB()
    db.set_setting("youtube_uploads_per_day", 3)
    assert reserve(db, 50, uploads=1)
    assert not reserve(db, 50, uploads=1)
    row = db.select("quota_log")[0]
    assert (row["units"], row["uploads"]) == (50, 1)
    assert not reserve(db, 9000, uploads=0)
    assert reserve(db, 8950)
    assert not reserve(db, -50, uploads=1)
    assert not reserve(db, 0)
    db.conn.close()
