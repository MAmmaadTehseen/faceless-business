"""Offline quota checks: isolated SQLite, fake uploads, no credentials/API calls.

Run: DB_BACKEND=sqlite .venv/bin/python -m scripts.check_youtube_queue
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os

os.environ["DB_BACKEND"] = "sqlite"
from pipeline.common import Channel
from pipeline.db import DB
from pipeline.publish import publish_short, _youtube_publish
from pipeline.publish.quota import reserve
from pipeline.sync import sync_channel


def main():
    with TemporaryDirectory() as tmp, patch("pipeline.db.DATA_DIR", Path(tmp)):
        db = DB()
        channel = Channel("tradewinds")
        video = Path(tmp) / "test.mp4"
        video.write_bytes(b"mock upload content")
        slot = datetime.now(timezone.utc) + timedelta(hours=1)
        calls = []
        titles = []
        def upload(*args, **kwargs):
            calls.append(kwargs)
            titles.append(args[1])
            return {"id": str(len(calls)), "url": "https://example.test/video"}
        with patch("pipeline.publish.youtube.configured", return_value=True), \
             patch("pipeline.publish.youtube.upload", side_effect=upload), \
             patch("pipeline.publish.meta.configured", return_value=False), \
             patch("pipeline.publish.youtube.stats", return_value={}), \
             patch("pipeline.publish.youtube.analytics", return_value={}):
            for i in range(1, 101):
                row = {"id": f"test-{i}", "channel": channel.key, "kind": "short", "topic": str(i),
                       "title": str(i), "file_path": str(video), "qa_status": "passed"}
                db.insert("content", row)
                publish_short(db, row, channel, "private", slot=slot + timedelta(hours=i))
            assert len(calls) == 98, calls
            assert db.one("publications", {"content_id": "test-99"})["status"] == "queued"
            assert db.one("publications", {"content_id": "test-100"})["status"] == "queued"
            assert len(db.select("publications", {"status": "queued"})) == 2
            sync_channel(db, channel)
            assert len(calls) == 98  # upload reserve prevents draining on the same UTC day
            # Simulate the next UTC accounting day, retaining old publication history.
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
            db.conn.execute("update quota_log set day=?", (yesterday,))
            db.conn.execute("update publications set published_at=? where status='live'", (yesterday + "T12:00:00+00:00",))
            db.conn.commit()
            sync_channel(db, channel)
            assert len(calls) == 100 and all(c["is_short"] for c in calls)
            assert titles[-2:] == ["99", "100"]
            assert not db.select("publications", {"status": "queued"})
            assert db.one("publications", {"content_id": "test-100"})["status"] == "live"
            assert db.one("quota_log", {"day": datetime.now(timezone.utc).date().isoformat()})["uploads"] == 2
            # Thumbnail charges general units, independently of upload count.
            thumbnail = Path(tmp) / "thumb.jpg"
            thumbnail.write_bytes(b"mock thumbnail")
            thumb_row = {"id": "thumb-test", "channel": channel.key, "kind": "long", "topic": "thumb",
                         "title": "thumb", "file_path": str(video), "thumbnail_path": str(thumbnail), "qa_status": "passed"}
            db.insert("content", thumb_row)
            _youtube_publish(db, thumb_row, channel, "private", slot)
            today = datetime.now(timezone.utc).date().isoformat()
            assert db.one("quota_log", {"day": today})["units"] == 50
            # Failed attempts retain quota, preventing retries from overspending.
            row = {"id": "failed-test", "channel": channel.key, "kind": "long", "topic": "failure", "title": "failure",
                   "file_path": str(video), "qa_status": "passed"}
            db.insert("content", row)
            with patch("pipeline.publish.youtube.upload", side_effect=RuntimeError("mock")):
                _youtube_publish(db, row, channel, "private", slot)
            assert db.one("quota_log", {"day": datetime.now(timezone.utc).date().isoformat()})["uploads"] == 4
            # The 1000-unit reserve is available to sync/engage, but stops at the full budget.
            assert reserve(db, 8950)
            assert not reserve(db, 1)
            assert reserve(db, 1000, keep_reserve=0)
            assert not reserve(db, 1, keep_reserve=0)
            # All 100 upload slots are available when retry headroom is explicitly released.
            for _ in range(94):
                assert reserve(db, 0, keep_reserve=0, uploads=1)
            assert not reserve(db, 0, keep_reserve=0, uploads=1)
            assert reserve(db, 0, keep_reserve=0, uploads=2, keep_upload_reserve=0)
            assert not reserve(db, 0, keep_reserve=0, uploads=1, keep_upload_reserve=0)
            assert db.one("quota_log", {"day": today})["uploads"] == 100
            # YouTube queueing must not prevent public Meta Reels.
            row = {"id": "meta-test", "channel": channel.key, "kind": "short", "topic": "meta", "title": "meta",
                   "file_path": str(video), "qa_status": "passed"}
            db.insert("content", row)
            with patch("pipeline.publish.meta.configured", return_value=True), \
                 patch("pipeline.publish.meta.ig_configured", return_value=True), \
                 patch("pipeline.publish.meta.fb_configured", return_value=True), \
                 patch("pipeline.publish.meta.public_url_for", return_value="https://example.test/file.mp4"), \
                 patch("pipeline.publish.meta.publish_instagram_reel", return_value={"id": "ig"}), \
                 patch("pipeline.publish.meta.publish_facebook_reel", return_value={"id": "fb"}):
                results = publish_short(db, row, channel, "public")
                assert {r["platform"] for r in results} == {"instagram", "facebook"}
                assert db.one("publications", {"content_id": "meta-test", "platform": "youtube"})["status"] == "queued"
        print("PASS: 99th upload queues with retry reserve; 100 slots available; thumbnail costs 50; next-day drain; failed attempts charged; Meta unaffected")


if __name__ == "__main__":
    main()
