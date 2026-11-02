from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock
import pytest
from pipeline.common import Channel
from pipeline import publish
from test_schedule import MemoryDB


def setup(tmp_path,monkeypatch):
    db=MemoryDB(); f=tmp_path/'video.mp4'; f.write_bytes(b'video')
    row=dict(id='video',channel='futurework',kind='long',status='rendered',qa_status='passed',title='Title',file_path=str(f))
    db.tables['content'].append(row)
    upload=Mock(return_value={'id':'remote','url':'https://youtu.be/remote'})
    monkeypatch.setattr(publish.youtube,'upload',upload)
    monkeypatch.setattr(publish,'reserve',Mock(return_value=True))
    return db,row,upload


def run(db,row):
    return publish._youtube_publish(db,row,Channel(),'private',datetime.now(timezone.utc)+timedelta(days=2))


@pytest.mark.parametrize('status',['failed','queued','live'])
def test_known_id_never_uploads_even_on_failed_row(tmp_path,monkeypatch,status):
    db,row,upload=setup(tmp_path,monkeypatch)
    db.upsert('publications',dict(content_id='video',platform='youtube',status=status,platform_id='known'),'content_id,platform')
    assert run(db,row)['id']=='known'
    upload.assert_not_called()
    assert db.one('content',{'id':'video'})['status']=='published'


def test_transport_uncertainty_blocks_second_insert(tmp_path,monkeypatch):
    db,row,upload=setup(tmp_path,monkeypatch)
    upload.side_effect=TimeoutError('connection interrupted')
    assert run(db,row) is None
    assert json.loads(db.one('publications',{'content_id':'video'})['error'])['upload_uncertain']
    with pytest.raises(RuntimeError,match='uncertain'): run(db,row)
    assert upload.call_count==1


@pytest.mark.parametrize('http_status',[408,500,503])
def test_ambiguous_server_response_requires_reconciliation(tmp_path,monkeypatch,http_status):
    db,row,upload=setup(tmp_path,monkeypatch)
    exc=Exception('upload response unavailable')
    exc.resp=Mock(status=http_status)
    exc.content=b'{}'
    upload.side_effect=exc
    assert run(db,row) is None
    with pytest.raises(RuntimeError,match='uncertain'):
        run(db,row)
    assert upload.call_count==1


def test_retry_keeps_uncertain_marker_across_attempts(tmp_path,monkeypatch):
    from pipeline import retry
    db,row,upload=setup(tmp_path,monkeypatch)
    upload.side_effect=TimeoutError('connection interrupted')
    assert run(db,row) is None
    pub=db.one('publications',{'content_id':'video'})
    before=dict(pub)
    restore=Mock(side_effect=AssertionError('must not restore uncertain upload'))
    monkeypatch.setattr(retry,'restore',restore)
    for _ in range(3):
        assert retry.retry_one(db,pub) is False
    assert db.one('publications',{'content_id':'video'})==before
    restore.assert_not_called()
    assert upload.call_count==1


def test_stale_drain_cannot_erase_concurrent_upload_claim(tmp_path,monkeypatch):
    db,row,upload=setup(tmp_path,monkeypatch)
    db.upsert('publications',dict(id='p',content_id='video',platform='youtube',status='queued',publish_at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()),'content_id,platform')
    monkeypatch.setattr(publish.youtube,'configured',lambda:True)
    def concurrent(*args,**kwargs):
        db.update('publications',{'id':'p'},{'status':'uploading','error':'claim'})
        raise RuntimeError('another runner owns upload')
    monkeypatch.setattr(publish,'_youtube_publish',concurrent)
    assert publish.drain_youtube_queue(db,Channel())==0
    assert db.one('publications',{'id':'p'})['status']=='uploading'
    assert db.one('publications',{'id':'p'})['error']=='claim'


def test_concurrent_resume_sees_claim(tmp_path,monkeypatch):
    db,row,upload=setup(tmp_path,monkeypatch)
    def first(*args,**kwargs):
        with pytest.raises(RuntimeError,match='reconciliation'): run(db,row)
        return {'id':'remote','url':'https://youtu.be/remote'}
    upload.side_effect=first
    assert run(db,row)['id']=='remote'
    assert upload.call_count==1


def test_content_write_failure_preserves_remote_id(tmp_path,monkeypatch):
    db,row,upload=setup(tmp_path,monkeypatch)
    update=db.update
    def fail(table,match,fields):
        if table=='content': raise OSError('DB write failed')
        return update(table,match,fields)
    monkeypatch.setattr(db,'update',fail)
    with pytest.raises(OSError): run(db,row)
    assert db.one('publications',{'content_id':'video'})['platform_id']=='remote'
    assert upload.call_count==1


def test_private_short_persists_missing_media_on_resume(tmp_path,monkeypatch):
    db,row,_=setup(tmp_path,monkeypatch);row['kind']='short';db.sb=Mock()
    monkeypatch.setattr(publish.youtube,'configured',lambda:False)
    monkeypatch.setattr(publish.meta,'configured',lambda:False)
    media=Mock(return_value='https://media.test/video.mp4')
    monkeypatch.setattr(publish.meta,'public_url_for',media)
    publish.publish_short(db,row,Channel(),'private')
    assert db.one('content',{'id':'video'})['media_url']=='https://media.test/video.mp4'
    media.assert_called_once()


def test_sqlite_conditional_null_update(tmp_path):
    from pipeline.db import DB
    db=DB(); db.insert('content',dict(id='sample',kind='long',topic='test',title='test'))
    db.update('content',{'id':'sample','media_url':None},{'media_url':'https://media.test/video.mp4'})
    assert db.one('content',{'id':'sample'})['media_url']=='https://media.test/video.mp4'
    db.conn.close()


def test_unapproved_public_request_stays_private_and_scheduled(tmp_path,monkeypatch):
    db,row,upload=setup(tmp_path,monkeypatch)
    slot=datetime.now(timezone.utc)+timedelta(days=2)
    publish._youtube_publish(db,row,Channel(),'public',slot)
    assert upload.call_args.kwargs['privacy']=='private'
    assert upload.call_args.kwargs['publish_at']==slot
    assert db.one('publications',{'content_id':'video'})['privacy']=='private'


def test_quota_loser_cannot_overwrite_another_runners_claim(tmp_path,monkeypatch):
    db,row,upload=setup(tmp_path,monkeypatch)
    db.tables['quota_log']=[]
    db.upsert('publications',dict(content_id='video',platform='youtube',status='queued'),'content_id,platform')
    def lose_quota(*args,**kwargs):
        db.update('publications',{'content_id':'video'},{'status':'uploading','error':'winner'})
        return False
    monkeypatch.setattr(publish,'reserve',lose_quota)
    assert run(db,row) is None
    assert db.one('publications',{'content_id':'video'})['status']=='uploading'
    upload.assert_not_called()
