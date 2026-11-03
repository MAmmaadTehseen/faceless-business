"""Offline webhook contract and upload isolation."""
import hashlib
import hmac
import json
from unittest.mock import patch
from pipeline.publish.jarvis import notify, record


def test_signed_payload(monkeypatch):
    monkeypatch.setenv("JARVIS_WEBHOOK_URL", "https://fixture.invalid/hooks/faceless")
    monkeypatch.setenv("JARVIS_WEBHOOK_SECRET", "fixture-secret")
    pub = dict(id=7, content_id="futurework-test", platform="youtube", status="live", error="private", platform_id="remote")
    with patch("pipeline.publish.jarvis.requests.post") as post, patch("pipeline.publish.jarvis.time.time", return_value=1793700000):
        notify(pub, "futurework")
    args = post.call_args.kwargs
    assert args["timeout"] == (1, 2)
    assert "private" not in args["data"].decode()
    assert "remote" not in args["data"].decode()
    assert args["headers"]["X-Faceless-Signature"] == hmac.new(b"fixture-secret", b"1793700000." + args["data"], hashlib.sha256).hexdigest()
    assert json.loads(args["data"])["id"] == 7


def test_webhook_failure_never_fails_upload(monkeypatch):
    monkeypatch.setenv("JARVIS_WEBHOOK_URL", "https://fixture.invalid/hooks/faceless")
    monkeypatch.setenv("JARVIS_WEBHOOK_SECRET", "fixture-secret")
    with patch("pipeline.publish.jarvis.requests.post", side_effect=RuntimeError("offline")):
        notify(dict(id=1, content_id="test", platform="youtube", status="failed"), "futurework")


def test_unconfigured_and_queued_skip(monkeypatch):
    monkeypatch.delenv("JARVIS_WEBHOOK_URL", raising=False)
    with patch("pipeline.publish.jarvis.requests.post") as post:
        notify({}, "futurework")
        assert not post.called


def test_record_notifies_once_per_transition():
    from unittest.mock import Mock
    db = Mock()
    rows = {}
    db.one.side_effect = lambda table, match: ({"channel": "futurework"} if table == "content" else rows.get(match.get("content_id")))
    def upsert(table, row, on):
        rows[row["content_id"]] = {"id": 1, **row}
        return rows[row["content_id"]]
    db.upsert.side_effect = upsert
    row = dict(content_id="test", platform="youtube", status="live")
    with patch("pipeline.publish.jarvis.notify") as alert:
        record(db, row); record(db, row)
        assert alert.call_count == 1
        record(db, {**row, "status": "failed"})
        assert alert.call_count == 2


def test_real_upload_path_succeeds_when_jarvis_is_down(tmp_path, monkeypatch):
    from test_upload_idempotency import setup, run
    db, row, upload = setup(tmp_path, monkeypatch)
    monkeypatch.setenv("JARVIS_WEBHOOK_URL", "https://fixture.invalid/hooks/faceless")
    monkeypatch.setenv("JARVIS_WEBHOOK_SECRET", "fixture-secret")
    with patch("pipeline.publish.jarvis.requests.post", side_effect=TimeoutError("offline")) as post:
        assert run(db, row)["id"] == "remote"
    assert post.called
    assert db.one("publications", {"content_id": row["id"]})["status"] == "live"


def test_conditional_retry_transition_alerts_once_and_keeps_guard():
    from pipeline.db import DB
    from pipeline.publish.jarvis import update
    db = DB()
    try:
        db.insert("content", dict(id="futurework-test", channel="futurework", kind="short", title="Test", topic="test"))
        pub = db.insert("publications", dict(content_id="futurework-test", platform="facebook", status="queued"))
        with patch("pipeline.publish.jarvis.notify") as alert:
            update(db, {"id": pub["id"], "status": "queued"}, {"status": "failed"})
            update(db, {"id": pub["id"], "status": "queued"}, {"status": "live"})
            update(db, {"id": pub["id"]}, {"status": "failed", "error": "retry"})
            assert alert.call_count == 1
            assert db.one("publications", {"id": pub["id"]})["status"] == "failed"
    finally:
        db.conn.close()
