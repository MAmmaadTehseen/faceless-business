import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from google.auth.exceptions import RefreshError

from pipeline.common import Channel
from pipeline import publish
from pipeline.publish import youtube
from pipeline.publish.jarvis import record, update
from pipeline.publish.reconcile import reconcile_uploads
from test_upload_idempotency import setup, run


def test_trigger_column_never_written_and_optional_pgrst204_isolated(tmp_path, monkeypatch):
    db, row, _ = setup(tmp_path, monkeypatch)
    original = db.upsert
    def write(table, fields, on):
        assert 'status_changed_at' not in fields
        return original(table, fields, on)
    monkeypatch.setattr(db, 'upsert', write)
    monkeypatch.setattr('pipeline.publish.jarvis.notify', Mock(side_effect=RuntimeError('PGRST204 unknown optional column')))
    record(db, dict(content_id='video', platform='youtube', status='queued', status_changed_at='bad'))
    update(db, {'content_id': 'video'}, {'status': 'live', 'status_changed_at': 'bad'})
    assert 'status_changed_at' not in db.one('publications', {'content_id': 'video'})
    assert db.one('publications', {'content_id': 'video'})['status'] == 'live'


def test_auth_failure_queues_and_circuit_survives_use_channel(tmp_path, monkeypatch, caplog):
    db, row, upload = setup(tmp_path, monkeypatch)
    upload.side_effect = RefreshError('invalid_grant: private diagnostics')
    assert run(db, row) is None
    youtube.use_channel(Channel())
    assert run(db, row) is None
    assert upload.call_count == 1
    pub = db.one('publications', {'content_id': 'video'})
    assert pub['status'] == 'queued'
    assert json.loads(pub['error'])['reason'] == 'youtube_auth_expired'
    assert 'upload_uncertain' not in pub['error']
    assert 'private diagnostics' not in caplog.text
    assert caplog.text.count('YouTube login expired for futurework; re-authorise') == 1
    assert not youtube.auth_failed(Channel('tradewinds'))


def test_request_guard_stops_all_later_requests(monkeypatch):
    youtube.use_channel(Channel())
    raw = Mock()
    raw.execute.side_effect = RefreshError('invalid_grant')
    guarded = youtube._Guarded(raw)
    for _ in range(2):
        with pytest.raises(youtube.YouTubeAuthExpired):
            guarded.execute()
    assert raw.execute.call_count == 1


def uncertain(tmp_path, monkeypatch, age=25):
    db, row, upload = setup(tmp_path, monkeypatch)
    stamp = (datetime.now(timezone.utc) - timedelta(hours=age)).isoformat()
    db.insert('publications', dict(content_id='video', platform='youtube', status='uploading',
        error=json.dumps({'upload_uncertain': True, 'attempted_at': stamp})))
    api = Mock()
    api.channels.return_value.list.return_value.execute.return_value = {'items': [
        {'contentDetails': {'relatedPlaylists': {'uploads': 'UUfixture'}}}]}
    api.playlistItems.return_value.list.return_value.execute.return_value = {'items': []}
    monkeypatch.setattr(youtube, 'configured', lambda: True)
    monkeypatch.setattr(youtube, 'yt', lambda: api)
    monkeypatch.setattr('pipeline.publish.reconcile.reserve', lambda *args: True)
    return db, row, upload, api


def test_reconcile_found_never_reuploads(tmp_path, monkeypatch):
    db, row, upload, api = uncertain(tmp_path, monkeypatch)
    api.playlistItems.return_value.list.return_value.execute.return_value = {'items': [
        {'snippet': {'title': 'Title'}, 'contentDetails': {'videoId': 'existing',
         'videoPublishedAt': datetime.now(timezone.utc).isoformat()}} ]}
    assert reconcile_uploads(db, Channel())[0]['platform_id'] == 'existing'
    assert run(db, row)['id'] == 'existing'
    upload.assert_not_called()
    api.search.assert_not_called()


@pytest.mark.parametrize('age,apply,expected', [(25, True, 'queued'), (23, True, 'uploading'), (25, False, 'uploading')])
def test_reconcile_age_and_dry_run(tmp_path, monkeypatch, age, apply, expected):
    db, row, upload, api = uncertain(tmp_path, monkeypatch, age)
    reconcile_uploads(db, Channel(), apply=apply)
    assert db.one('publications', {'content_id': 'video'})['status'] == expected
    upload.assert_not_called()


def test_partial_scan_and_auth_failure_never_clear_uncertainty(tmp_path, monkeypatch):
    db, row, upload, api = uncertain(tmp_path, monkeypatch)
    quota = Mock(side_effect=[True, True, False])
    monkeypatch.setattr('pipeline.publish.reconcile.reserve', quota)
    api.playlistItems.return_value.list.return_value.execute.return_value = {'items': [], 'nextPageToken': 'next'}
    assert reconcile_uploads(db, Channel()) == []
    monkeypatch.setattr('pipeline.publish.reconcile.reserve', lambda *a: True)
    api.channels.return_value.list.return_value.execute.side_effect = RefreshError('invalid_grant')
    assert reconcile_uploads(db, Channel()) == []
    assert db.one('publications', {'content_id': 'video'})['status'] == 'uploading'


def test_daily_token_retry_is_bounded_and_shortens_prompt():
    from pipeline.shorts_daily import daily_script
    claude = Mock()
    claude.run.side_effect = [RuntimeError('max_tokens hit in step short_daily'), ({'script': 'ok'}, 0.1)]
    assert daily_script(claude, 'prompt', 'id')[0]['script'] == 'ok'
    assert claude.run.call_count == 2
    assert 'compact JSON' in claude.run.call_args.args[1]
    assert claude.run.call_args.kwargs['max_tokens'] == 6000
    claude.run.side_effect = RuntimeError('max_tokens hit in step short_daily')
    claude.reset_mock()
    with pytest.raises(RuntimeError):
        daily_script(claude, 'prompt', 'id')
    assert claude.run.call_count == 2


@pytest.mark.parametrize('key,var', [('futurework','YT_REFRESH_TOKEN'), ('tradewinds','YT_REFRESH_TOKEN_TRADEWINDS'), ('escapevelocity','YT_REFRESH_TOKEN_ESCAPEVELOCITY')])
def test_auth_helper_channel_steps(key, var):
    from scripts.youtube_auth import token_variable, steps
    assert token_variable(key) == var
    assert f'url {key}' in steps(key)
    assert var in steps(key)


def test_optional_alert_lookup_pgrst204_cannot_block_core_write():
    db = Mock()
    db.one.side_effect = RuntimeError('PGRST204 optional alert lookup')
    row = dict(content_id='test', platform='youtube', status='live')
    record(db, row)
    db.upsert.assert_called_once_with('publications', row, on='content_id,platform')
    update(db, {'id': 1}, {'status': 'live', 'status_changed_at': 'ignored'})
    db.update.assert_called_once_with('publications', {'id': 1}, {'status': 'live'})


@pytest.mark.parametrize('scenario,pushes', [('clean',0), ('race',2), ('denied',3), ('conflict',0)])
def test_persona_commit_script_with_fake_git(tmp_path, scenario, pushes):
    """No real git writes: the executable only records simulated commands."""
    import os
    import subprocess
    from pathlib import Path
    fake = tmp_path / 'git'
    fake.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
log = Path(os.environ['FAKE_GIT_LOG'])
args = sys.argv[1:]
previous = log.read_text() if log.exists() else ''
with log.open('a') as out: out.write(' '.join(args) + '\\n')
scenario = os.environ['FAKE_SCENARIO']
if args[0] == 'diff': sys.exit(0 if scenario == 'clean' else 1)
if args[0] == 'push':
    if scenario == 'denied' or (scenario == 'race' and 'push ' not in previous): sys.exit(128)
if args[0] == 'rebase' and '--abort' not in args and scenario == 'conflict': sys.exit(1)
''')
    fake.chmod(0o755)
    log = tmp_path / 'git.log'
    result = subprocess.run(['bash', str(Path('scripts/commit_persona.sh').resolve()), 'main'], cwd=tmp_path,
        env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH'],
             'FAKE_GIT_LOG': str(log), 'FAKE_SCENARIO': scenario}, capture_output=True, text=True)
    assert result.returncode == 0
    calls = log.read_text().splitlines()
    assert sum(c.startswith('push ') for c in calls) == pushes
    if scenario == 'conflict':
        assert calls.count('rebase --abort') == 3
    if scenario == 'clean':
        assert not any(c.startswith('commit ') for c in calls)


def test_uncertain_retry_uses_attempt_time_not_old_publication_creation(tmp_path, monkeypatch):
    db, row, upload = setup(tmp_path, monkeypatch)
    db.insert('publications', dict(content_id='video', platform='youtube', status='queued',
                                  created_at='2026-01-01T00:00:00+00:00'))
    upload.side_effect = TimeoutError('uncertain')
    run(db, row)
    error = json.loads(db.one('publications', {'content_id': 'video'})['error'])
    assert error['upload_uncertain']
    assert datetime.now(timezone.utc) - datetime.fromisoformat(error['attempted_at']) < timedelta(minutes=1)
    assert error['upload_attempt']


def test_same_title_outside_attempt_window_never_adopted_or_retried(tmp_path, monkeypatch):
    db, row, upload, api = uncertain(tmp_path, monkeypatch)
    api.playlistItems.return_value.list.return_value.execute.return_value = {'items': [
        {'snippet': {'title': 'Title'}, 'contentDetails': {'videoId': 'old', 'videoPublishedAt': '2020-01-01T00:00:00Z'}}]}
    assert reconcile_uploads(db, Channel()) == []
    assert db.one('publications', {'content_id': 'video'})['status'] == 'uploading'
    upload.assert_not_called()
