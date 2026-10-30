import json
from unittest.mock import Mock

from pipeline.publish.youtube import error_details
from pipeline.retry import plan, retry_one


def test_response_reason():
    exc = Exception()
    exc.resp = Mock(status=403)
    exc.content = b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'
    assert error_details(exc) == {"error": "Exception", "http_status": 403, "reason": "uploadLimitExceeded"}


def test_force_bypasses_both_buckets(tmp_path, monkeypatch):
    from pipeline.db import DB
    from pipeline.publish.quota import reserve
    monkeypatch.setattr("pipeline.db.DATA_DIR", tmp_path)
    db = DB()
    db.set_setting("youtube_uploads_per_day", 0)
    db.set_setting("youtube_quota_units_per_day", 0)
    assert not reserve(db, 50, uploads=1)
    assert reserve(db, 50, uploads=1, force=True)
    assert reserve(db, 50, uploads=1, force=True)
    usage = db.select("quota_log")[0]
    assert (usage["units"], usage["uploads"]) == (100, 2)
    db.conn.close()


def test_retry_plan_excludes_live_and_filters():
    db = Mock()
    db.select.return_value = [dict(id=i, content_id="video", platform=p, status=s) for i, p, s in [(1,"youtube","live"), (2,"youtube","failed"), (3,"instagram","queued")]]
    assert [p["id"] for p in plan(db, ["2", "3"], platform="youtube")] == [2]


def setup_retry(monkeypatch, tmp_path):
    import pipeline.retry as retry
    db = Mock()
    row = dict(id="video", channel="futurework", kind="short", qa_status="passed", title="Title", file_path=str(tmp_path / "video.mp4"))
    db.one.return_value = row
    db.setting.return_value = "public"
    monkeypatch.setattr(retry, "restore", lambda *args: dict(row))
    return retry, db, dict(id=1, content_id="video", platform="facebook", status="failed")


def test_real_api_error_fails_with_reason(monkeypatch, tmp_path):
    retry, db, pub = setup_retry(monkeypatch, tmp_path)
    exc = Exception()
    exc.resp = Mock(status=403)
    exc.content = b'{"error":{"errors":[{"reason":"forbidden"}]}}'
    monkeypatch.setattr(retry.meta, "publish_facebook_reel", Mock(side_effect=exc))
    assert not retry_one(db, pub, force=True)
    fields = db.update.call_args.args[2]
    assert fields["status"] == "failed"
    assert json.loads(fields["error"])["reason"] == "forbidden"
    assert json.loads(fields["error"])["http_status"] == 403


def test_retry_success(monkeypatch, tmp_path):
    retry, db, pub = setup_retry(monkeypatch, tmp_path)
    monkeypatch.setattr(retry.meta, "publish_facebook_reel", Mock(return_value={"id":"fb1", "url":"https://facebook.com/fb1"}))
    assert retry_one(db, pub, force=True)
    fields = db.update.call_args_list[0].args[2]
    assert fields["status"] == "live" and fields["platform_id"] == "fb1" and fields["error"] is None


def test_forced_youtube_failure_stays_failed(monkeypatch, tmp_path):
    from datetime import datetime, timezone, timedelta
    import pipeline.publish as publish
    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    db = Mock(sb=None)
    db.one.return_value = None
    row = dict(id="video", kind="long", file_path=str(video), title="Title", qa_status="passed")
    exc = Exception()
    exc.resp = Mock(status=403)
    exc.content = b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}'
    reserve = Mock(return_value=True)
    monkeypatch.setattr(publish, "reserve", reserve)
    monkeypatch.setattr(publish.youtube, "upload", Mock(side_effect=exc))
    assert publish._youtube_publish(db, row, publish.Channel(), "private", datetime.now(timezone.utc)+timedelta(days=2), force=True) is None
    reserve.assert_called_once_with(db, 0, uploads=1, force=True)
    fields = db.upsert.call_args.args[1]
    assert fields["status"] == "failed"
    assert json.loads(fields["error"])["reason"] == "quotaExceeded"


def test_automatic_quota_failure_queues(monkeypatch, tmp_path):
    from datetime import datetime, timezone, timedelta
    import pipeline.publish as publish
    video = tmp_path / "v.mp4"
    video.write_bytes(b"video")
    db = Mock(sb=None)
    db.one.return_value = None
    row = dict(id="video", kind="long", file_path=str(video), title="Title", qa_status="passed")
    exc = Exception()
    exc.resp = Mock(status=403)
    exc.content = b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'
    monkeypatch.setattr(publish, "reserve", Mock(return_value=True))
    monkeypatch.setattr(publish.youtube, "upload", Mock(side_effect=exc))
    persist = Mock(return_value={"media_key":"saved/video.mp4"})
    monkeypatch.setattr(publish, "_persist_queue", persist)
    publish._youtube_publish(db, row, publish.Channel(), "private", datetime.now(timezone.utc)+timedelta(days=2))
    fields = db.upsert.call_args.args[1]
    assert fields["status"] == "queued" and fields["media_key"] == "saved/video.mp4"
    assert "retry_after" in json.loads(fields["error"])
    persist.assert_called_once()


def test_meta_response_keeps_status_and_reason():
    import requests
    from pipeline.publish.meta import _publish_response
    response = Mock(ok=False, status_code=403)
    response.json.return_value = {"error": {"type": "OAuthException", "code": 190}}
    try:
        _publish_response(response)
    except requests.HTTPError as exc:
        details = error_details(exc)
        assert details["http_status"] == 403
        assert details["reason"] == "OAuthException" and details["code"] == 190
    else:
        assert False, "Expected API error"


def test_restore_falls_back_after_missing_queue(monkeypatch, tmp_path):
    import pipeline.retry as retry
    path = tmp_path / "media.mp4"
    path.write_bytes(b"media")
    monkeypatch.setattr(retry, "_restore_queue", Mock(side_effect=FileNotFoundError()))
    monkeypatch.setattr(retry, "_local_file", Mock(return_value=path))
    result = retry.restore(Mock(), {"id":"video", "media_url":"https://example.com/media.mp4"}, {})
    assert result["file_path"] == str(path)
