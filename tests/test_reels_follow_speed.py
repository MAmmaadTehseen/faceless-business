"""Reels follow-up must stay fast: quick restore, and Shorts with unrecoverable media are tried once."""
from unittest.mock import patch
from datetime import datetime, timezone

from pipeline.db import DB
from pipeline.common import Channel
from pipeline import publish


def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr("pipeline.db.DATA_DIR", tmp_path)
    return DB()


def test_missing_media_is_tried_once(tmp_path, monkeypatch):
    db = _db(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat()
    db.insert("content", {"id": "futurework-x-short-1", "channel": "futurework", "kind": "short", "topic": "t",
                          "title": "t", "qa_status": "passed", "file_path": str(tmp_path / "gone.mp4")})
    db.insert("publications", {"content_id": "futurework-x-short-1", "platform": "youtube", "status": "live",
                               "privacy": "public", "publish_at": now, "platform_id": "abc"})
    calls = []

    def fake_restore(db_, row, pub, deep=True):
        calls.append(deep)
        raise FileNotFoundError("gone")

    with patch.object(publish.meta, "ig_configured", return_value=True), \
         patch.object(publish.meta, "fb_configured", return_value=False), \
         patch.object(publish.meta, "use_channel"), \
         patch("pipeline.retry.restore", side_effect=fake_restore):
        publish.follow_youtube_to_reels(db, Channel("futurework"))
        publish.follow_youtube_to_reels(db, Channel("futurework"))
    assert calls == [False]
    assert db.setting("reels_follow_missing_futurework") == ["futurework-x-short-1"]


def test_quick_restore_skips_artifact_scan(tmp_path, monkeypatch):
    from pipeline import retry
    db = _db(tmp_path, monkeypatch)
    row = {"id": "futurework-y-short-1", "channel": "futurework", "file_path": str(tmp_path / "no.mp4")}
    with patch.object(retry, "_restore_queue", return_value=row), \
         patch.object(retry, "_api", side_effect=AssertionError("artifact scan must not run")):
        try:
            retry.restore(db, row, {"platform": "youtube"}, deep=False)
        except FileNotFoundError as e:
            assert "skipped (quick restore)" in str(e)
