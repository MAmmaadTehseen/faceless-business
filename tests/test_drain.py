"""Queue failures cannot starve later uploads; quota alone controls queueing."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from pipeline.common import Channel
from pipeline import publish
from test_schedule import MemoryDB


@pytest.mark.parametrize('restore_error', [False, True])
def test_unrestorable_row_retries_three_times_and_continues(tmp_path, monkeypatch, restore_error):
    db, channel = MemoryDB(), Channel('futurework')
    video = tmp_path / 'good.mp4'
    video.write_bytes(b'mock video')
    slot = datetime.now(timezone.utc) + timedelta(days=1)
    for cid, path in [('bad', tmp_path / 'missing.mp4'), ('good', video)]:
        db.tables['content'].append({'id': cid, 'channel': channel.key, 'kind': 'short',
                                    'title': cid, 'file_path': str(path), 'qa_status': 'passed'})
        db.upsert('publications', {'content_id': cid, 'platform': 'youtube', 'status': 'queued',
                                  'publish_at': slot.isoformat()}, 'content_id,platform')
    restored = []

    def restore(db, row, pub):
        restored.append(row['id'])
        if row['id'] == 'bad' and restore_error:
            raise OSError('storage unavailable')
        return row

    monkeypatch.setattr(publish, '_restore_queue', restore)
    monkeypatch.setattr(publish.youtube, 'configured', lambda: True)
    monkeypatch.setattr(publish.youtube, 'use_channel', lambda channel: None)
    reserve = Mock(return_value=True)
    monkeypatch.setattr(publish, 'reserve', reserve)
    upload = Mock(return_value={'id': 'uploaded', 'url': 'https://example.test/video'})
    monkeypatch.setattr(publish.youtube, 'upload', upload)
    for attempt in range(1, 4):
        # A new healthy row on every sync proves continuing past the broken head.
        db.update('publications', {'content_id': 'good'}, {'status': 'queued'})
        assert publish.drain_youtube_queue(db, channel) == 1
        bad = db.one('publications', {'content_id': 'bad'})
        assert json.loads(bad['error'])['drain_attempts'] == attempt
        assert bad['status'] == ('failed' if attempt == 3 else 'queued')
        assert db.one('publications', {'content_id': 'good'})['status'] == 'live'
    assert restored == ['bad', 'good'] * 3
    assert publish.drain_youtube_queue(db, channel) == 0
    assert upload.call_count == reserve.call_count == 3


def test_fresh_upload_with_bucket_room_does_not_queue(tmp_path, monkeypatch):
    from pipeline.db import DB
    monkeypatch.setenv('DB_BACKEND', 'sqlite')
    monkeypatch.setattr('pipeline.db.DATA_DIR', tmp_path)
    db = DB()
    try:
        video, thumbnail = tmp_path / 'video.mp4', tmp_path / 'thumbnail.jpg'
        video.write_bytes(b'mock video')
        thumbnail.write_bytes(b'mock thumbnail')
        row = {'id': 'fresh', 'channel': 'futurework', 'kind': 'long', 'topic': 'test',
               'title': 'Fresh', 'qa_status': 'passed', 'file_path': str(video),
               'thumbnail_path': str(thumbnail)}
        db.insert('content', row)
        upload = Mock(return_value={'id': 'uploaded', 'url': 'https://example.test/video'})
        persist = Mock(side_effect=AssertionError('unexpected queue persistence'))
        monkeypatch.setattr(publish.youtube, 'upload', upload)
        monkeypatch.setattr(publish, '_persist_queue', persist)
        result = publish._youtube_publish(db, row, Channel('futurework'), 'private',
                    datetime.now(timezone.utc) + timedelta(days=1), force_queue=True)
        assert result['id'] == 'uploaded'
        assert db.one('publications', {'content_id': 'fresh'})['status'] == 'live'
        assert not db.select('publications', {'status': 'queued'})
        usage = db.select('quota_log')[0]
        assert (usage['uploads'], usage['units']) == (1, 50)
        upload.assert_called_once()
        persist.assert_not_called()
    finally:
        db.conn.close()
