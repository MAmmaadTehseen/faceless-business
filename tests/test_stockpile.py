import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock
import pytest
from pipeline.common import Channel
from pipeline.db import DB
from pipeline.drive import Drive, DriveFull, FLOOR, digest
from pipeline import stockpile, release_banked, evergreen
from pipeline.bank_gate import enabled


class FakeDrive:
    def __init__(self):
        self.data = {}
        self.moves = []
    def space(self, required=0):
        return {'used': 1000, 'limit': 100 * 1024**3}
    def folder(self, name, parent=None):
        return (parent or '') + '/' + name
    def upload(self, path, parent):
        key = str(len(self.data))
        self.data[key] = Path(path).read_bytes()
        return key
    def download(self, key, target, checksum):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.data[key])
        if digest(target) != checksum:
            raise RuntimeError('checksum mismatch')
        return target
    def release(self, folder, root):
        self.moves.append(folder)


def bundle(tmp_path, monkeypatch, *, short=False):
    db = DB()
    cid = 'futurework-2026-11-12-bank-test'
    monkeypatch.setattr(stockpile, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(release_banked, 'OUT_DIR', tmp_path)
    out = tmp_path / cid
    out.mkdir()
    for i in range(1 if short else 5):
        key = cid if i == 0 else f'{cid}-short-{i}'
        path = out / f'{key}.mp4'
        path.write_bytes(('video' + str(i)).encode())
        db.insert('content', {'id': key, 'channel': 'futurework', 'kind': 'short' if i or short else 'long',
            'parent_id': cid if i else None, 'title': key, 'topic': 'test', 'description': 'Full video: {LONG_URL}' if i else 'test',
            'file_path': str(path), 'qa_status': 'passed', 'status': 'rendered', 'qa_notes': '{"issues":[]}'})
    (out / 'voice.srt').write_text('captions')
    if not short:
        (out / 'bank-article.json').write_text(json.dumps({'id': cid, 'content_id': cid, 'channel': 'futurework',
            'title': 'Article', 'slug': 'article', 'body_md': 'Article text', 'excerpt': 'article', 'published_at': None}))
    return db, cid, FakeDrive()


def test_bank_complete_bundle_no_publications_or_article(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    metadata = stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    assert len(db.select('content', {'status': 'banked'})) == 5
    assert not db.select('publications') and not db.select('articles')
    manifest = json.loads(drive.data[metadata['manifest_id']])
    assert manifest['containsSyntheticMedia'] is True
    assert manifest['article']['published_at'] is None
    assert len(manifest['content']) == 5 and 'voice.srt' in manifest['files']
    assert all(Path(r['file_path']).exists() for r in db.select('content'))
    assert stockpile.notes(db.one('content', {'id': cid}))['issues'] == []


@pytest.mark.parametrize('failure', ['quota', 'upload', 'qa'])
def test_failed_banking_never_marks_partial_bundle(tmp_path, monkeypatch, failure):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    if failure == 'quota':
        drive.space = Mock(side_effect=DriveFull('full'))
    elif failure == 'upload':
        drive.upload = Mock(side_effect=RuntimeError('upload failed'))
    elif failure == 'qa':
        db.update('content', {'id': cid}, {'qa_status': 'failed'})
    else:
        db.conn.execute('delete from content where id=?', (cid + '-short-4',))
        db.conn.commit()
    with pytest.raises(RuntimeError):
        stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    assert not db.select('content', {'status': 'banked'})
    assert not db.select('publications')


def mock_publish(monkeypatch):
    from pipeline import publish
    monkeypatch.setattr(publish.youtube, 'configured', lambda: True)
    monkeypatch.setattr(publish.youtube, 'upload', Mock(side_effect=lambda *a, **k: {'id': Path(a[0]).stem, 'url': 'https://youtu.be/test'}))
    monkeypatch.setattr('pipeline.article.ping_indexnow', lambda slug: None)
    monkeypatch.setattr('pipeline.article.article_thumbnail', lambda *args: None)
    return publish.youtube.upload


def test_release_normal_publisher_and_replay_no_models(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    upload = mock_publish(monkeypatch)
    monkeypatch.setattr('pipeline.common.Claude.run', Mock(side_effect=AssertionError('no models on release')))
    assert release_banked.release(db, Channel(), drive=drive) == 1
    assert upload.call_count == 5
    assert len(db.select('publications', {'platform': 'youtube', 'status': 'live'})) == 5
    assert db.one('articles', {'id': cid})['youtube_id'] == cid
    assert len(drive.moves) == 1
    assert release_banked.release(db, Channel(), drive=drive) == 0
    assert upload.call_count == 5


def test_release_interrupted_after_uploads_is_discoverable(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    upload = mock_publish(monkeypatch)
    original = drive.release
    drive.release = Mock(side_effect=RuntimeError('move failed'))
    with pytest.raises(RuntimeError):
        release_banked.release(db, Channel(), drive=drive)
    assert release_banked.pending(db, Channel())[0]['id'] == cid
    drive.release = original
    assert release_banked.release(db, Channel(), drive=drive) == 1
    assert upload.call_count == 5


def test_corrupt_download_blocks_upload_and_move(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    meta = stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    upload = mock_publish(monkeypatch)
    drive.data[meta['files'][cid + '.mp4']['id']] = b'corrupt'
    with pytest.raises(RuntimeError):
        release_banked.release(db, Channel(), drive=drive)
    upload.assert_not_called()
    assert not drive.moves


def test_release_setting_and_capacity_leave_no_publications(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch, short=True)
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    upload = mock_publish(monkeypatch)
    assert release_banked.release(db, Channel(), scheduled=True, drive=drive) == 0
    db.set_setting('banked_release_per_day', 1)
    db.set_setting('youtube_uploads_per_day', 2)
    assert release_banked.release(db, Channel(), scheduled=True, drive=drive) == 0
    assert not db.select('publications')
    db.set_setting('youtube_uploads_per_day', 100)
    assert release_banked.release(db, Channel(), scheduled=True, drive=drive) == 1
    assert upload.call_count == 1


def test_evergreen_avoids_all_history_and_persists_use():
    db, channel = DB(), Channel()
    db.insert('content', {'id': 'old', 'kind': 'long', 'title': 'How neural networks learn', 'topic': 'Neural network training', 'channel': channel.key})
    db.set_setting('evergreen_topics_futurework', [{'topic': 'How neural networks learn'}, {'topic': 'Privacy by design'}, {'topic': 'The history of labor bargaining'}])
    assert evergreen.choose(db, channel)['topic'] == 'Privacy by design'
    assert evergreen.choose(db, channel)['topic'] == 'The history of labor bargaining'
    with pytest.raises(RuntimeError, match='exhausted'):
        evergreen.choose(db, channel)


def test_schedule_gate_requires_boolean_and_date():
    db = DB()
    assert not enabled(db)
    db.set_setting('bank_mode_enabled', 'true')
    db.set_setting('bank_until', '2026-11-25')
    assert not enabled(db, date(2026, 11, 12))
    db.set_setting('bank_mode_enabled', True)
    assert enabled(db, date(2026, 11, 12))
    assert not enabled(db, date(2026, 11, 26))
    db.set_setting('bank_until', 'invalid')
    assert not enabled(db)


def test_drive_space_floor_and_scope():
    from pipeline.drive import SCOPE
    assert SCOPE == 'https://www.googleapis.com/auth/drive.file'
    service = Mock()
    service.about().get().execute.return_value = {'storageQuota': {'limit': str(FLOOR + 100), 'usage': '10'}}
    drive = Drive(service)
    assert drive.space(90)['used'] == 10
    with pytest.raises(DriveFull):
        drive.space(91)


def test_drive_upload_uses_resumable_and_checks_remote_bytes(tmp_path):
    service = Mock()
    service.about().get().execute.return_value = {'storageQuota': {'limit': str(100 * 1024**3), 'usage': '0'}}
    service.files().list().execute.return_value = {'files': []}
    service.files().create().next_chunk.return_value = (None, {'id': 'file'})
    path = tmp_path / 'video.mp4'
    path.write_bytes(b'video')
    service.files().get().execute.return_value = {'size': '5', 'md5Checksum': digest(path, 'md5')}
    drive = Drive(service)
    assert drive.upload(path, 'parent') == 'file'
    assert service.files().create.call_args.kwargs['media_body'].resumable()
    service.files().get().execute.return_value = {'size': '5', 'md5Checksum': 'bad'}
    with pytest.raises(RuntimeError, match='verification'):
        drive.upload(path, 'parent')
    assert path.exists()


def test_release_daily_rate_shared_across_syncs(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch, short=True)
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    mock_publish(monkeypatch)
    db.set_setting('banked_release_per_day', 1)
    assert release_banked.release(db, Channel(), scheduled=True, drive=drive) == 1
    # Another finished standalone item in the same UTC day must wait.
    second = cid + '-second'
    path = tmp_path / second
    path.mkdir()
    video = path / (second + '.mp4')
    video.write_bytes(b'second')
    db.insert('content', {'id': second, 'channel': 'futurework', 'kind': 'short', 'title': 'Second', 'topic': 'Second',
        'file_path': str(video), 'qa_status': 'passed', 'status': 'rendered'})
    stockpile.bank_bundle(db, second, Channel(), drive=drive)
    assert release_banked.release(db, Channel(), scheduled=True, drive=drive) == 0
    assert db.one('content', {'id': second})['status'] == 'banked'


def test_release_uncertain_publication_never_reuploads(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch, short=True)
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    upload = mock_publish(monkeypatch)
    db.insert('publications', {'content_id': cid, 'platform': 'youtube', 'status': 'failed',
        'error': json.dumps({'upload_uncertain': True})})
    assert release_banked.release(db, Channel(), drive=drive) == 0
    upload.assert_not_called()
    assert not drive.moves


def test_storage_lock_blocks_competing_operation_and_releases():
    db = DB()
    with stockpile.lock(db, 'test'):
        with pytest.raises(RuntimeError, match='locked'):
            with stockpile.lock(db, 'test'):
                pytest.fail('competing writer acquired lock')
    assert db.setting('stockpile_lock_test') is None


def test_drive_target_has_separate_token_and_scope(capsys, monkeypatch):
    from scripts import youtube_auth
    assert youtube_auth.token_variable('drive') == 'GDRIVE_REFRESH_TOKEN'
    assert youtube_auth.token_variable('futurework') == 'YT_REFRESH_TOKEN'
    monkeypatch.setattr('sys.argv', ['youtube_auth.py', 'steps', 'drive'])
    youtube_auth.main()
    assert 'GDRIVE_REFRESH_TOKEN' in capsys.readouterr().out


def test_workflow_yaml_and_global_concurrency():
    import yaml
    root = Path(__file__).resolve().parents[1]
    for path in (root / '.github/workflows').glob('*.yml'):
        assert isinstance(yaml.load(path.read_text(), Loader=yaml.BaseLoader), dict)
    workflow = yaml.load((root / '.github/workflows/bank.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['concurrency']['cancel-in-progress'] == 'false'
    assert workflow['jobs']['bank']['strategy']['max-parallel'] == '2'
    assert workflow['jobs']['bank']['env']['TTS_BACKEND'] == 'kokoro'


def test_failed_parent_does_not_upload_children_without_parent_link(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    mock_publish(monkeypatch)
    parent = Mock(return_value=None)
    monkeypatch.setattr('pipeline.publish._youtube_publish', parent)
    assert release_banked.release(db, Channel(), drive=drive) == 0
    assert parent.call_count == 1
    assert not db.select('publications') and not drive.moves


@pytest.mark.parametrize('failed_children', [0, 1, 4])
@pytest.mark.parametrize('article_failure', [False, True])
def test_bank_long_runs_full_qa_and_prepares_article_without_publishing(tmp_path, monkeypatch, failed_children, article_failure):
    from pipeline import run_all, publish, article
    db, channel, drive = DB(), Channel(), FakeDrive()
    db.set_setting('evergreen_topics_futurework', [{'topic': 'Durable mechanisms of workplace automation'}])
    monkeypatch.setattr(run_all, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(stockpile, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(stockpile, 'Drive', lambda: drive)
    data = json.loads(run_all.FIXTURE.read_text())
    seed = data['shorts'][0]
    data['shorts'] = [{**seed, 'hook_title': f'Distinct angle {i}'} for i in range(4)]
    monkeypatch.setattr(run_all, 'choose_topic', Mock(side_effect=AssertionError('no news ideation')))
    monkeypatch.setattr(run_all, 'write_script', lambda *a: data)
    monkeypatch.setattr(run_all, 'synthesize', lambda *a, **k: {'timings': [{'index': 0, 'start': 0, 'end': 2}],
        'duration': 2, 'audio': tmp_path / 'voice.mp3', 'srt': tmp_path / 'voice.srt'})
    def rendered(*args, **kwargs):
        path = args[3]
        path.write_bytes(b'long')
        return path
    def thumbnail(video, text, path, **kwargs):
        path.write_bytes(b'thumbnail')
        return path
    def short(data, out, voice, footage, name, style):
        path = out / (name + '.mp4')
        path.write_bytes(b'short')
        return {'file': path, 'duration': 2, 'title': data['hook_title'], 'script': data['script']}
    monkeypatch.setattr(run_all, 'render', rendered)
    monkeypatch.setattr(run_all, 'make_thumbnail', thumbnail)
    monkeypatch.setattr(run_all, 'make_short', short)
    findings = [{'severity': 'blocking', 'text': 'Third-party watermark'}]
    qa = Mock(side_effect=[{'pass': True, 'issues': []}] +
        [{'pass': i >= failed_children, 'issues': findings if i < failed_children else []} for i in range(4)])
    monkeypatch.setattr(run_all, 'run_qa', qa)
    prepare = Mock(return_value={'title': 'Article', 'slug': 'article', 'body_md': 'Saved article'})
    if article_failure:
        prepare.side_effect = ValueError('Article validation failed after retries')
    monkeypatch.setattr(article, 'write_article', prepare)
    publishing = Mock(side_effect=AssertionError('bank cannot publish'))
    monkeypatch.setattr(publish, 'publish_all', publishing)
    result = run_all.produce_one(db, Mock(provider='lunaroute'), Mock(placeholder=False),
        dry_run=False, publish=False, privacy=None, channel=channel, bank=True)
    assert qa.call_count == 5 and all(c.kwargs['vision'] for c in qa.call_args_list)
    assert prepare.call_args.kwargs['prepare_only'] is True
    assert len(db.select('content', {'status': 'banked'})) == 5 - failed_children
    failed = db.select('content', {'status': 'qa_failed'})
    assert len(failed) == failed_children
    assert all(stockpile.notes(row)['issues'] == findings for row in failed)
    manifest = json.loads(drive.data[result['stockpile']['manifest_id']])
    assert manifest['article_failed'] is article_failure
    assert (manifest['article'] is None) is article_failure
    assert len(manifest['content']) == 5 - failed_children
    assert not {r['id'] for r in failed} & {r['id'] for r in manifest['content']}
    assert all(c.kwargs['caption_text'] for c in qa.call_args_list)
    assert len(result['shorts']) == 4 - failed_children
    assert not db.select('publications')
    publishing.assert_not_called()


def test_bank_standalone_does_not_affect_daily_job_or_send_meta(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from pipeline import shorts_daily as daily
    db, drive = DB(), FakeDrive()
    today = datetime.now(timezone.utc).date().isoformat()
    db.insert('content', {'id': f'futurework-{today}-short-normal', 'kind': 'short', 'channel': 'futurework',
        'topic': 'Normal daily topic', 'title': 'Normal', 'qa_status': 'passed', 'status': 'published'})
    db.set_setting('evergreen_topics_futurework', [{'topic': 'Evergreen mechanism'}])
    monkeypatch.setattr(daily, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(stockpile, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(stockpile, 'Drive', lambda: drive)
    monkeypatch.setattr(daily, 'Claude', lambda *a, **k: Mock(provider='lunaroute'))
    monkeypatch.setattr(daily, 'Footage', lambda **k: Mock(placeholder=False))
    data = {'script': ' '.join(['word'] * 130), 'hook_title': 'A durable idea', 'query': 'people working',
            'description': 'An explanation', 'tags': [], 'facts_check': []}
    monkeypatch.setattr(daily, 'daily_script', lambda *a, **k: (data, 0))
    def short(data, out, voice, footage, name, style):
        path = out / (name + '.mp4')
        path.write_bytes(b'short')
        return {'file': path, 'duration': 50, 'title': data['hook_title'], 'script': data['script']}
    monkeypatch.setattr(daily, 'make_short', short)
    monkeypatch.setattr(daily, 'run_qa', lambda *a, **k: {'pass': True, 'issues': []})
    forbidden = Mock(side_effect=AssertionError('bank cannot upload'))
    monkeypatch.setattr(daily, 'publish_short', forbidden)
    monkeypatch.setattr(daily.meta, 'public_url_for', forbidden)
    result = daily.produce_daily(db, Channel(), bank=True)
    assert '-bank-short-' in result['content_id']
    assert len(db.select('content', {'status': 'banked'})) == 1
    assert db.one('content', {'id': f'futurework-{today}-short-normal'})['status'] == 'published'
    forbidden.assert_not_called()


def test_article_preparation_never_saves_or_notifies(tmp_path, monkeypatch):
    from pipeline import article, run_all
    db = DB()
    db.insert('content', {'id': 'article-test', 'channel': 'futurework', 'kind': 'long',
                         'title': 'Evergreen', 'topic': 'Evergreen'})
    blocked = Mock(side_effect=AssertionError('preparation cannot publish'))
    monkeypatch.setattr(article, 'article_thumbnail', blocked)
    monkeypatch.setattr(article, 'ping_indexnow', blocked)
    row = article.write_article(db, 'article-test', dry_run=True, prepare_only=True,
                               script_data=json.loads(run_all.FIXTURE.read_text()))
    assert row['published_at'] is None and row['body_md']
    assert not db.select('articles') and not db.select('publications')
    blocked.assert_not_called()


def test_bank_missing_child_uses_only_present_pieces(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    db.conn.execute('delete from content where id=?', (cid + '-short-4',))
    db.conn.commit()
    metadata = stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    manifest = json.loads(drive.data[metadata['manifest_id']])
    assert len(manifest['content']) == 4


@pytest.mark.parametrize('failed_count', [1, 4])
def test_release_bundle_excludes_qa_failed_children(tmp_path, monkeypatch, failed_count):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    for i in range(1, failed_count + 1):
        db.update('content', {'id': f'{cid}-short-{i}'},
                  {'qa_status': 'failed', 'status': 'qa_failed',
                   'qa_notes': json.dumps({'issues': [{'severity': 'blocking', 'text': 'watermark'}]})})
    stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    upload = mock_publish(monkeypatch)
    assert release_banked.release(db, Channel(), drive=drive) == 1
    assert upload.call_count == 5 - failed_count
    assert len(db.select('content', {'status': 'qa_failed'})) == failed_count


@pytest.mark.parametrize('failure', [ValueError('Article validation failed: Invalid evidence label'),
                                     RuntimeError('provider unavailable')])
def test_article_failure_banks_and_releases_all_passing_media(tmp_path, monkeypatch, caplog, failure):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    (tmp_path / cid / 'bank-article.json').unlink()
    prepare = Mock(side_effect=failure)
    monkeypatch.setattr('pipeline.article.write_article', prepare)
    metadata = stockpile.bank_bundle(db, cid, Channel(), drive=drive)
    prepare.assert_called_once()
    manifest = json.loads(drive.data[metadata['manifest_id']])
    assert manifest['article'] is None and manifest['article_failed'] is True
    assert len(manifest['content']) == 5
    assert len(db.select('content', {'status': 'banked'})) == 5
    for row in db.select('content'):
        assert stockpile.notes(row)['stockpile']['article_failed'] is True
        assert Path(row['file_path']).is_file()
    assert 'banking passing media without article' in caplog.text
    upload = mock_publish(monkeypatch)
    monkeypatch.setattr('pipeline.common.Claude.run', Mock(side_effect=AssertionError('no release model calls')))
    assert release_banked.release(db, Channel(), drive=drive) == 1
    assert upload.call_count == 5 and not db.select('articles')
    assert len(drive.moves) == 1
    assert stockpile.notes(db.one('content', {'id': cid}))['stockpile']['article_failed'] is True
    assert release_banked.release(db, Channel(), drive=drive) == 0
    assert upload.call_count == 5


def test_drive_client_uses_long_socket_timeout(monkeypatch):
    import pipeline.drive as drive_module
    captured = {}
    monkeypatch.setenv('GDRIVE_REFRESH_TOKEN', 'r')
    monkeypatch.setenv('YT_CLIENT_ID', 'c')
    monkeypatch.setenv('YT_CLIENT_SECRET', 's')
    import httplib2
    import googleapiclient.discovery
    real_http = httplib2.Http
    monkeypatch.setattr(httplib2, 'Http', lambda timeout=None: captured.setdefault('timeout', timeout) and real_http(timeout=timeout))
    monkeypatch.setattr(googleapiclient.discovery, 'build', lambda *a, **k: (captured.setdefault('build', k), 'svc')[1])
    assert Drive().service == 'svc'
    assert captured['timeout'] == drive_module.SOCKET_TIMEOUT >= 300
    assert 'http' in captured['build'] and 'credentials' not in captured['build']


def test_upload_resumes_same_request_after_transient_errors(tmp_path, monkeypatch):
    from googleapiclient.errors import HttpError
    from pipeline.drive import next_chunk_retrying
    import httplib2
    sleeps = []
    request = Mock()
    five = HttpError(Mock(status=503), b'busy')
    request.next_chunk.side_effect = [TimeoutError(), ConnectionResetError(), five, httplib2.HttpLib2Error('x'),
                                      (None, None), (None, {'id': 'f'})]
    assert next_chunk_retrying(request, 'upload', sleep=sleeps.append) == {'id': 'f'}
    assert request.next_chunk.call_count == 6 and len(sleeps) == 4 and sleeps == sorted(sleeps)
    # 4xx and unrelated errors are never retried.
    request = Mock()
    request.next_chunk.side_effect = HttpError(Mock(status=403), b'denied')
    with pytest.raises(HttpError):
        next_chunk_retrying(request, 'upload', sleep=sleeps.append)
    assert request.next_chunk.call_count == 1
    request = Mock()
    request.next_chunk.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        next_chunk_retrying(request, 'upload', sleep=lambda s: None)
    assert request.next_chunk.call_count == 10
    # Downloads finish on done=True after a retry.
    request = Mock()
    request.next_chunk.side_effect = [(None, False), TimeoutError(), (None, True)]
    assert next_chunk_retrying(request, 'download', sleep=lambda s: None) is True


def test_bank_resume_reuses_checkpoints_without_production(tmp_path, monkeypatch):
    db, cid, drive = bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(stockpile, 'Drive', lambda: drive)
    monkeypatch.setattr(stockpile, 'Claude', None, raising=False)
    import pipeline.common as common
    monkeypatch.setattr(common, 'Claude', lambda db, channel=None: Mock(provider='lunaroute'))
    metadata = stockpile.resume_bank(db, cid)
    assert metadata['folder_id'].endswith('/' + cid) and db.one('content', {'id': cid})['status'] == 'banked'
    assert not db.select('publications', {}) and not db.select('articles', {})
    # Second resume is a no-op on the checkpoint.
    assert stockpile.resume_bank(db, cid) == metadata
    with pytest.raises(ValueError):
        stockpile.resume_bank(db, cid, 'tradewinds')


def test_bank_workflow_resume_inputs():
    import yaml
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load((root / '.github/workflows/bank.yml').read_text(), Loader=yaml.BaseLoader)
    inputs = workflow[True]['workflow_dispatch']['inputs'] if True in workflow else workflow['on']['workflow_dispatch']['inputs']
    assert {'resume_id', 'artifact_run_id'} <= set(inputs)
    steps = {s.get('name'): s for s in workflow['jobs']['bank']['steps']}
    assert "inputs.resume_id != ''" in steps['Retry Drive storage for a produced bundle']['if']
    assert "inputs.resume_id == ''" in steps['Bank finished bundles']['if']
    assert 'pipeline.stockpile --resume' in steps['Retry Drive storage for a produced bundle']['run']
