"""Reels follow-up must stay fast and never leave failed rows behind: quick restore, and
Shorts with unrecoverable media are tried once and skipped quietly."""
from unittest.mock import Mock, patch
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


def test_unrestorable_media_creates_no_failed_publication_row(tmp_path, monkeypatch):
    """A Short whose only media is a stored media_url nobody can fetch must be skipped quietly
    by follow_youtube_to_reels (remembered in reels_follow_missing_<channel>). Before the fix,
    a set media_url bypassed the restore check, publish_short ran, its Meta publishes failed
    on the dead media, and it recorded failed instagram/facebook publication rows."""
    db = _db(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat()
    db.insert("content", {"id": "futurework-z-short-1", "channel": "futurework", "kind": "short", "topic": "t",
                          "title": "t", "qa_status": "passed", "parent_id": "futurework-z",
                          "file_path": str(tmp_path / "gone.mp4"),
                          "media_url": "https://cdn.example.dead/media.mp4"})
    db.insert("publications", {"content_id": "futurework-z-short-1", "platform": "youtube", "status": "live",
                               "privacy": "public", "publish_at": now, "platform_id": "abc"})

    def dead_restore(db_, row, pub, deep=True):
        raise FileNotFoundError("No uploadable file found.")

    with patch.object(publish.meta, "ig_configured", return_value=True), \
         patch.object(publish.meta, "fb_configured", return_value=True), \
         patch.object(publish.meta, "configured", lambda: True), \
         patch.object(publish.meta, "use_channel"), \
         patch.object(publish.youtube, "configured", lambda: False), \
         patch.object(publish.meta, "publish_instagram_reel",
                      Mock(side_effect=RuntimeError("media fetch failed"))), \
         patch.object(publish.meta, "publish_facebook_reel",
                      Mock(side_effect=RuntimeError("media fetch failed"))), \
         patch("pipeline.retry.restore", side_effect=dead_restore):
        assert publish.follow_youtube_to_reels(db, Channel("futurework")) == 0
    rows = db.select("publications", {"content_id": "futurework-z-short-1"})
    assert all(r.get("status") != "failed" for r in rows), \
        "a media miss in the follow-up must not leave failed instagram/facebook rows behind"
    assert db.setting("reels_follow_missing_futurework") == ["futurework-z-short-1"]


def test_quick_restore_skips_artifact_scan(tmp_path, monkeypatch):
    from pipeline import retry
    db = _db(tmp_path, monkeypatch)
    row = {"id": "futurework-y-short-1", "channel": "futurework", "file_path": str(tmp_path / "no.mp4")}
    with patch.object(retry, "_restore_queue", return_value=row), \
         patch.object(retry, "_artifact_file", side_effect=AssertionError("artifact download must not run")), \
         patch.object(retry, "_api", side_effect=AssertionError("artifact scan must not run")):
        try:
            retry.restore(db, row, {"platform": "youtube", "artifact_run_id": "123"}, deep=False)
        except FileNotFoundError as e:
            assert "skipped (quick restore)" in str(e)


def test_old_project_media_url_is_stale(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://newref.supabase.co")
    assert publish._stale_media_url("https://oldref.supabase.co/storage/v1/object/public/media/a.mp4")
    assert not publish._stale_media_url("https://newref.supabase.co/storage/v1/object/public/media/a.mp4")
    assert not publish._stale_media_url("https://github.com/x/releases/download/a.mp4")


def test_instagram_error_is_not_zero_views(monkeypatch):
    import pytest
    from pipeline.publish import meta
    class R:
        def __init__(self, d): self.d = d
        def json(self): return self.d
    monkeypatch.setattr(meta, "_ig_tok", lambda: "t")
    monkeypatch.setattr(meta.requests, "get", lambda *a, **k: R({"error": {"message": "checkpoint"}}))
    with pytest.raises(RuntimeError):
        meta.ig_insights("123")
