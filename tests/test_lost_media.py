"""Incident regressions: durable queue transitions and artifact-free rebuilds."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from pipeline import publish, run_all
from pipeline.common import Channel
from test_upload_idempotency import setup, run


@pytest.mark.parametrize('cause', ['circuit', 'refresh', 'quota', 'daily_cap', 'uncertain'])
def test_production_persists_before_queue_or_uncertainty(tmp_path, monkeypatch, cause):
    from google.auth.exceptions import RefreshError
    db, row, upload = setup(tmp_path, monkeypatch)
    db.sb = Mock()
    events = []
    original = db.upsert
    def record(table, fields, on):
        if table == 'publications' and fields.get('status') in ('queued', 'uploading'):
            assert events and events[0] == 'persist'
        return original(table, fields, on)
    monkeypatch.setattr(db, 'upsert', record)
    persist = Mock(side_effect=lambda *a: events.append('persist') or {'media_key': 'saved/video.mp4'})
    monkeypatch.setattr(publish, '_persist_queue', persist)
    if cause == 'circuit':
        publish.youtube.use_channel(Channel())
        publish.youtube.mark_auth_failed()
    elif cause == 'refresh':
        upload.side_effect = RefreshError('invalid_grant')
    elif cause == 'quota':
        db.tables['quota_log'] = []
        monkeypatch.setattr(publish, 'reserve', lambda *a, **kw: False)
    elif cause == 'daily_cap':
        exc = Exception()
        exc.resp = Mock(status=403)
        exc.content = b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'
        upload.side_effect = exc
    else:
        upload.side_effect = TimeoutError()
    assert run(db, row) is None
    pub = db.one('publications', {'content_id': row['id']})
    assert pub['media_key'] == 'saved/video.mp4'
    assert pub['status'] == ('failed' if cause == 'uncertain' else 'queued')
    if cause == 'uncertain':
        assert json.loads(pub['error'])['upload_uncertain']


@pytest.mark.parametrize('cause', ['circuit', 'quota', 'daily_cap'])
def test_storage_failure_never_creates_queued_row(tmp_path, monkeypatch, cause):
    db, row, upload = setup(tmp_path, monkeypatch)
    db.sb = Mock()
    monkeypatch.setattr(publish, '_persist_queue', Mock(side_effect=OSError('storage down')))
    if cause == 'circuit':
        publish.youtube.use_channel(Channel())
        publish.youtube.mark_auth_failed()
    elif cause == 'quota':
        monkeypatch.setattr(publish, 'reserve', lambda *a, **kw: False)
    else:
        exc = Exception(); exc.resp = Mock(status=403)
        exc.content = b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'
        upload.side_effect = exc
    try:
        run(db, row)
    except OSError:
        pass
    assert not db.select('publications', {'status': 'queued'})
    upload.assert_not_called()


def test_reconcile_missing_media_preserves_uncertainty(tmp_path, monkeypatch):
    from test_production_recovery import uncertain
    from pipeline.publish.reconcile import reconcile_uploads
    db, row, upload, _ = uncertain(tmp_path, monkeypatch)
    monkeypatch.setattr('pipeline.retry.restore', Mock(side_effect=FileNotFoundError()))
    decision = reconcile_uploads(db, Channel())[0]
    assert decision['reason'] == 'media_not_recoverable'
    assert db.one('publications', {'content_id': row['id']})['status'] == 'uploading'
    upload.assert_not_called()


def test_recovery_groups_and_only_resets_counters(tmp_path, monkeypatch, capsys):
    from scripts.recover_lost_media import recover
    db, row, _ = setup(tmp_path, monkeypatch)
    original_error = {'reason': 'youtube_auth_expired', 'drain_attempts': 2, 'audit': 'retain'}
    for cid, parent in [('parent', None), ('child', 'parent'), ('standalone-short-example', None)]:
        db.tables['content'].append(dict(id=cid, parent_id=parent))
        db.insert('publications', dict(content_id=cid, platform='youtube', status='queued', error=json.dumps(original_error)))
    monkeypatch.setattr('scripts.recover_lost_media.restore', Mock(side_effect=FileNotFoundError()))
    before = [dict(p) for p in db.tables['publications']]
    assert set(recover(db)) == {'parent', 'standalone-short-example'}
    assert db.tables['publications'] == before
    assert capsys.readouterr().out.count('gh workflow run produce.yml') == 2
    recover(db, apply=True)
    for pub in db.tables['publications']:
        assert json.loads(pub['error']) == {**original_error, 'drain_attempts': 0}
        assert pub['status'] == 'queued'


@pytest.mark.parametrize('standalone', [False, True])
def test_db_rebuild_without_artifact_or_generation(tmp_path, monkeypatch, standalone):
    from pipeline.db import DB
    db = DB()
    cid = 'futurework-2026-11-01-' + ('short-example' if standalone else 'example')
    data = json.loads(run_all.FIXTURE.read_text())
    data['shorts'] = data['shorts'][:1]
    if standalone:
        data = {**data['shorts'][0], 'description': 'Saved description', 'tags': []}
    row = dict(id=cid, channel='futurework', topic='Example', title='Saved title',
               kind='short' if standalone else 'long', script='Saved script',
               qa_notes=json.dumps({'daily_script' if standalone else 'rebuild_script': data}))
    db.insert('content', row)
    monkeypatch.setenv('TTS_BACKEND', 'kokoro')
    monkeypatch.setattr(run_all, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(run_all, 'choose_topic', Mock(side_effect=AssertionError('new topic')))
    monkeypatch.setattr(run_all, 'write_script', Mock(side_effect=AssertionError('new script')))
    monkeypatch.setattr('pipeline.article.write_article', Mock(side_effect=AssertionError('article Claude call')))
    tts = Mock(return_value={'timings': [{'index': 0, 'start': 0, 'end': 2}], 'duration': 2,
                            'audio': tmp_path/'voice.mp3', 'srt': tmp_path/'voice.srt'})
    monkeypatch.setattr(run_all, 'synthesize', tts)
    monkeypatch.setattr(run_all, 'render', lambda *a, **kw: a[3])
    monkeypatch.setattr(run_all, 'make_thumbnail', lambda *a, **kw: a[2])
    short = Mock(return_value={'file': tmp_path/'short.mp4', 'duration': 2, 'title': 'Saved', 'script': 'Saved'})
    monkeypatch.setattr(run_all, 'make_short', short)
    qa = Mock(return_value={'pass': True, 'issues': []})
    monkeypatch.setattr(run_all, 'run_qa', qa)
    monkeypatch.setattr('pipeline.publish.publish_all', Mock(return_value=[]))
    monkeypatch.setattr('pipeline.publish.publish_short', Mock(return_value=[]))
    result = run_all.produce_one(db, Mock(), Mock(placeholder=False), dry_run=False,
        publish=True, privacy='private', resume=cid, rebuild=True, channel=Channel())
    assert result['content_id'] == cid
    assert qa.call_count == (1 if standalone else 2)
    assert short.call_count == 1
    assert tts.call_count == (0 if standalone else 1)
    import os
    assert os.environ['TTS_BACKEND'] == 'kokoro'
    db.conn.close()


def test_missing_db_script_fails_before_generation(tmp_path, monkeypatch):
    db = Mock(); db.one.return_value = {'id': 'missing', 'kind': 'long'}
    monkeypatch.setattr(run_all, 'OUT_DIR', tmp_path)
    with pytest.raises(ValueError, match='DB lacks saved script'):
        run_all.produce_one(db, Mock(), Mock(), dry_run=False, publish=False,
            privacy='private', resume='missing', rebuild=True, channel=Channel())
    assert not (tmp_path/'missing').exists()


def test_short_artifacts_include_paid_script_and_narration():
    import yaml
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/shorts.yml').read_text())
    upload = next(s for s in workflow['jobs']['shorts']['steps'] if s.get('uses', '').startswith('actions/upload-artifact'))
    assert 'script.json' in upload['with']['path']
    assert '*.mp3' in upload['with']['path']


def test_persisted_queue_survives_fresh_runner(tmp_path, monkeypatch):
    db, row, upload = setup(tmp_path, monkeypatch)
    objects = {}
    db.tables['quota_log'] = []
    db.sb = Mock()
    bucket = db.sb.storage.from_.return_value
    bucket.upload.side_effect = lambda key, data, options: objects.update({key: data})
    bucket.download.side_effect = objects.__getitem__
    monkeypatch.setattr(publish, 'reserve', lambda *a, **kw: False)
    run(db, row)
    pub = db.one('publications', {'content_id': row['id']})
    assert objects[pub['media_key']] == b'video'
    Path(row['file_path']).unlink()
    monkeypatch.setattr('pipeline.common.OUT_DIR', tmp_path/'fresh-runner')
    restored = publish._restore_queue(db, dict(row), pub)
    assert Path(restored['file_path']).read_bytes() == b'video'
    upload.assert_not_called()


def test_rebuild_live_publication_never_uploads(tmp_path, monkeypatch):
    db, row, upload = setup(tmp_path, monkeypatch)
    db.insert('publications', dict(content_id=row['id'], platform='youtube', status='live', platform_id='existing'))
    # Rebuild may replace the local render but publishing must keep the remote ID.
    Path(row['file_path']).write_bytes(b'rebuilt media')
    assert run(db, row)['id'] == 'existing'
    upload.assert_not_called()


def test_large_queue_file_uses_release_before_queue(tmp_path, monkeypatch):
    db, row, upload = setup(tmp_path, monkeypatch)
    db.sb = Mock()
    db.tables['quota_log'] = []
    monkeypatch.setattr(publish, 'BIG_FILE', 1)
    monkeypatch.setattr(publish, 'reserve', lambda *a, **kw: False)
    release = Mock(return_value='https://github.com/owner/repo/releases/download/queue/video.mp4')
    monkeypatch.setattr(publish.meta, '_github_release_url', release)
    run(db, row)
    pub = db.one('publications', {'content_id': row['id']})
    assert pub['media_key'] == release.return_value
    release.assert_called_once()
    db.sb.storage.from_.assert_not_called()
    upload.assert_not_called()


def test_restore_never_leaves_partial_final_media(tmp_path, monkeypatch):
    db, row, _ = setup(tmp_path, monkeypatch)
    Path(row['file_path']).unlink()
    monkeypatch.setattr('pipeline.common.OUT_DIR', tmp_path/'restored')
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    def broken_stream(*a):
        yield b'incomplete'
        raise OSError('download interrupted')
    response.iter_content.side_effect = broken_stream
    monkeypatch.setattr('requests.get', Mock(return_value=response))
    with pytest.raises(OSError):
        publish._restore_queue(db, row, {'media_key': 'https://example.test/video.mp4'})
    assert not list((tmp_path/'restored').rglob('*.mp4'))
    assert not list((tmp_path/'restored').rglob('*.part'))


def test_rebuild_uses_final_db_narration():
    data = run_all.recovery_data({'id': 'saved', 'script': 'Final hook\n\nFinal paragraph',
                                 'qa_notes': json.dumps({'paid_script': {'script': ['Early draft'], 'shot_list': []}})})
    assert data['script'] == ['Final hook', 'Final paragraph']


def test_rebuild_workflow_requires_no_artifact():
    import yaml
    workflow = yaml.safe_load(Path('.github/workflows/produce.yml').read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert inputs['rebuild']['type'] == 'boolean'
    steps = workflow['jobs']['produce']['steps']
    restore = next(step for step in steps if step.get('name') == 'Restore rendered files')
    assert "rebuild != 'true'" in restore['if']
    produce = next(step for step in steps if step.get('name') == 'Produce and publish')
    assert '--rebuild' in produce['run']
