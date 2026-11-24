"""Child Shorts get one link comment to their long video once both are public (growth log 2026-11-24)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from pipeline.common import Channel
from pipeline.db import DB
from pipeline.publish import short_links


def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr("pipeline.db.DATA_DIR", tmp_path)
    return DB()


def _seed(db, parent_privacy="public"):
    now = datetime.now(timezone.utc).isoformat()
    db.insert("content", {"id": "futurework-x", "channel": "futurework", "kind": "long", "topic": "t", "title": "The Long One"})
    db.insert("content", {"id": "futurework-x-short-1", "channel": "futurework", "kind": "short", "topic": "t",
                          "title": "s", "parent_id": "futurework-x"})
    db.insert("publications", {"content_id": "futurework-x", "platform": "youtube", "status": "live",
                               "privacy": parent_privacy, "publish_at": now, "platform_id": "LONG1"})
    db.insert("publications", {"content_id": "futurework-x-short-1", "platform": "youtube", "status": "live",
                               "privacy": "public", "publish_at": now, "platform_id": "SHORT1"})


def _run(db):
    api = MagicMock()
    with patch.object(short_links.youtube, "configured", return_value=True), \
         patch.object(short_links.youtube, "auth_failed", return_value=False), \
         patch.object(short_links.youtube, "use_channel"), \
         patch.object(short_links.youtube, "yt", return_value=api), \
         patch.object(short_links, "reserve", return_value=True):
        n = short_links.comment_long_links(db, Channel("futurework"))
    return n, api


def test_posts_once_with_parent_link(tmp_path, monkeypatch):
    db = _db(tmp_path, monkeypatch)
    _seed(db)
    n, api = _run(db)
    assert n == 1
    body = api.commentThreads().insert.call_args.kwargs["body"]["snippet"]
    assert body["videoId"] == "SHORT1"
    assert "https://youtu.be/LONG1" in body["topLevelComment"]["snippet"]["textOriginal"]
    assert "The Long One" in body["topLevelComment"]["snippet"]["textOriginal"]
    n2, _ = _run(db)
    assert n2 == 0  # remembered; never posted twice


def test_waits_for_parent_to_be_public(tmp_path, monkeypatch):
    db = _db(tmp_path, monkeypatch)
    _seed(db, parent_privacy="private")
    n, api = _run(db)
    assert n == 0 and not db.setting("yt_link_comment_SHORT1")


def test_disabled_by_setting(tmp_path, monkeypatch):
    db = _db(tmp_path, monkeypatch)
    _seed(db)
    db.set_setting("short_link_comments_enabled", False)
    assert _run(db)[0] == 0


def test_tentongues_wording():
    assert short_links.comment_text(Channel("tentongues"), "WATER", "u").startswith("Hear the word in all ten languages: WATER")
