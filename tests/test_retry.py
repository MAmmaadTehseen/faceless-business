from pathlib import Path
import json
from unittest.mock import Mock

from pipeline.publish.youtube import error_details
from pipeline.retry import plan, retry_one


def test_response_reason():
    exc = Exception()
    exc.resp = Mock(status=403)
    exc.content = b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'
    assert error_details(exc) == {"error": "Exception", "http_status": 403, "reason": "uploadLimitExceeded", "message": ""}


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
    result = retry.restore(Mock(one=Mock(return_value=None)), {"id":"video", "media_url":"https://example.com/media.mp4"}, {})
    assert result["file_path"] == str(path)


def test_restore_public_before_queue(monkeypatch, tmp_path):
    import pipeline.retry as retry
    path = tmp_path / 'v.mp4'
    path.write_bytes(b'video')
    local = Mock(return_value=path)
    queue = Mock()
    monkeypatch.setattr(retry, '_local_file', local)
    monkeypatch.setattr(retry, '_restore_queue', queue)
    assert retry.restore(Mock(one=Mock(return_value=None)), {'id': 'v', 'media_url': 'https://media/v.mp4'}, {})['file_path'] == str(path)
    queue.assert_not_called()


def test_restore_queue_before_artifact(monkeypatch, tmp_path):
    import pipeline.retry as retry
    path = tmp_path / 'v.mp4'
    path.write_bytes(b'video')
    monkeypatch.setattr(retry, '_local_file', Mock(side_effect=OSError()))
    monkeypatch.setattr(retry, '_restore_queue', Mock(return_value={'id': 'v', 'file_path': str(path)}))
    artifact = Mock()
    monkeypatch.setattr(retry, '_artifact_file', artifact)
    retry.restore(Mock(one=Mock(return_value=None)), {'id': 'v', 'media_url': 'https://media/v.mp4'}, {})
    artifact.assert_not_called()


def test_restore_provenance_before_search(monkeypatch, tmp_path):
    import pipeline.retry as retry
    monkeypatch.setattr(retry, '_restore_queue', lambda db, row, pub: row)
    artifact = Mock(return_value=str(tmp_path / 'v.mp4'))
    api = Mock()
    monkeypatch.setattr(retry, '_artifact_file', artifact)
    monkeypatch.setattr(retry, '_api', api)
    notes = json.dumps({'artifact_run_id': '123', 'artifact_name': 'shorts-test-123'})
    retry.restore(Mock(one=Mock(return_value=None)), {'id': 'v', 'qa_notes': notes}, {})
    artifact.assert_called_once_with({'id': 'v', 'qa_notes': notes}, '123', 'shorts-test-123')
    api.assert_not_called()


def test_restore_legacy_search_extracts_only_matching_file(monkeypatch, tmp_path):
    import io
    import zipfile
    import pipeline.retry as retry
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('out/v/v.mp4', b'correct')
        z.writestr('out/other.mp4', b'unrelated')
    calls = []
    def api(endpoint, binary=False):
        calls.append(endpoint)
        if 'workflows/' in endpoint:
            return {'workflow_runs': [{'id': 12}]}
        if '/runs/' in endpoint:
            return {'artifacts': [{'id': 34, 'name': 'shorts-test-12', 'expired': False}]}
        return archive.getvalue()
    monkeypatch.setattr(retry, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(retry, '_api', api)
    monkeypatch.setattr(retry, '_restore_queue', lambda db, row, pub: row)
    result = retry.restore(Mock(one=Mock(return_value=None)), {'id': 'v'}, {})
    assert Path(result['file_path']).read_bytes() == b'correct'
    assert list(tmp_path.rglob('*.mp4')) == [Path(result['file_path'])]
    assert 'produce.yml' in calls[0]


def test_restore_unrecoverable_is_clear(monkeypatch):
    import pytest
    import pipeline.retry as retry
    monkeypatch.setattr(retry, '_restore_queue', lambda db, row, pub: row)
    monkeypatch.setattr(retry, '_api', Mock(side_effect=OSError()))
    with pytest.raises(FileNotFoundError, match='No uploadable file found. Checked: .*youtube-queue.*GitHub artifact'):
        retry.restore(Mock(one=Mock(return_value=None)), {'id': 'v'}, {'platform': 'youtube'})


def test_forced_daily_cap_queues_with_explanation(monkeypatch, tmp_path):
    from datetime import datetime, timezone, timedelta
    import pipeline.publish as publish
    video = tmp_path / 'v.mp4'
    video.write_bytes(b'video')
    db = Mock(sb=None)
    db.one.return_value = None
    exc = Exception()
    exc.content = b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'
    monkeypatch.setattr(publish, 'reserve', Mock(return_value=True))
    monkeypatch.setattr(publish.youtube, 'upload', Mock(side_effect=exc))
    monkeypatch.setattr(publish, '_persist_queue', Mock(return_value={'media_key': 'saved/v.mp4'}))
    publish._youtube_publish(db, dict(id='v', kind='short', title='Title', file_path=str(video), qa_status='passed'),
                             publish.Channel(), 'private', datetime.now(timezone.utc) + timedelta(days=2), force=True)
    fields = db.upsert.call_args.args[1]
    assert fields['status'] == 'queued'
    details = json.loads(fields['error'])
    assert details['message'] == 'YouTube daily upload cap reached for this channel; try after the cap resets'
    assert details['retry_after']


def test_cancelled_status_mapping():
    # Execute the actual status expression from the button without loading React.
    import re
    import subprocess
    source = Path('dashboard/src/components/ActionButton.tsx').read_text()
    expression = re.search(r'setMessage\(\s*(j.conclusion.*?),\s*\);', source).group(1)
    script = 'const j = {conclusion: process.argv[1]}; console.log(' + expression + ');'
    for conclusion, expected in [('cancelled', 'Cancelled, retry again'), ('success', 'Done'), ('failure', 'Failed (failure)')]:
        result = subprocess.run(['node', '-e', script, conclusion], check=True, capture_output=True, text=True)
        assert result.stdout.strip() == expected


def test_restore_live_meta_public_bucket_last(monkeypatch, tmp_path):
    import pipeline.retry as retry
    db = Mock()
    db.one.return_value = {'status': 'live'}
    db.sb.storage.from_.return_value.get_public_url.return_value = 'https://media/production.mp4'
    monkeypatch.setattr(retry, '_restore_queue', lambda db, row, pub: row)
    monkeypatch.setattr(retry, '_api', Mock(return_value={'workflow_runs': []}))
    local = Mock(return_value=tmp_path / 'restored.mp4')
    monkeypatch.setattr(retry, '_local_file', local)
    result = retry.restore(db, {'id': 'tradewinds-2026-10-30-short-test', 'channel': 'tradewinds'}, {'platform': 'facebook'})
    assert result['media_url'] == 'https://media/production.mp4'
    db.sb.storage.from_.return_value.get_public_url.assert_called_once_with('media-20261030/tradewinds-2026-10-30-short-test.mp4')


def test_production_notes_preserves_issues_and_provenance(monkeypatch):
    from pipeline.retry import production_notes
    from pipeline.common import Channel
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    for workflow, prefix in [('produce', 'videos'), ('shorts', 'shorts')]:
        notes = json.loads(production_notes(['finding'], Channel('tradewinds'), workflow))
        assert notes == {'issues': ['finding'], 'artifact_run_id': '123', 'artifact_name': f'{prefix}-tradewinds-123'}


def test_retry_error_messages():
    from pipeline.retry import retry_error_details
    details = retry_error_details(RuntimeError("useful failure " * 40))
    assert details["error"] == "RuntimeError"
    assert details["message"] == ("useful failure " * 40)[:300]
    message = "No uploadable file found. Checked: local (missing); queue (empty)"
    details = retry_error_details(FileNotFoundError(message))
    assert details["reason"] == "media_not_recoverable"
    assert details["message"] == message


def test_dashboard_recovery_decisions():
    import subprocess
    script = r"""
const ts = require('./dashboard/node_modules/typescript');
const fs = require('fs');
const code = ts.transpile(fs.readFileSync('dashboard/src/lib/recovery.ts', 'utf8'), {module:ts.ModuleKind.CommonJS});
const mod = {exports:{}};
new Function('exports', code)(mod.exports);
const f = mod.exports.recoveryAction;
const assert = require('assert');
const passed = {status:'rendered',qa_status:'passed'};
assert.equal(f(passed,[{status:'failed',error:'{"reason":"quotaExceeded"}'}]),'retry');
assert.equal(f(passed,[{status:'failed',error:'{"reason":"media_not_recoverable"}'}]),'rebuild');
assert.equal(f({status:'qa_failed',qa_status:'failed'},[]),'rebuild');
assert.equal(f({status:'rendered',qa_status:'pending'},[],false),'reproduce');
assert.equal(f(passed,[{status:'failed',error:'invalid'}]),'retry');
"""
    subprocess.run(['node', '-e', script], check=True)
