"""Audit and repair planners never publish or mutate their inputs."""
from copy import deepcopy
from datetime import datetime, timezone
from scripts.audit_videos import inspect, duration, safe_error, dt
from scripts.repair_videos import plan


def content(**fields):
    return dict(id='sample',channel='futurework',kind='short',status='rendered',qa_status='passed',title='A useful title',topic='sample',created_at='2026-11-01T00:00:00Z',**fields)


def test_killed_placeholders_excluded():
    c=content(); c.update(status='killed',placeholder=True)
    assert inspect([c],[],[],[],{},set())==[]
    assert plan([c],[dict(id=1,content_id='sample',platform='youtube',status='live',platform_id='known')],[])==[]
    assert inspect([c],[],[],[dict(content_id='sample',usd=1,step='script')],{},set())==[]


def test_public_short_missing_reels_and_media():
    c=content(); c['status']='published'
    p=dict(id=1,content_id=c['id'],platform='youtube',status='live',platform_id='known',privacy='public',url='https://youtu.be/known')
    v=dict(id='known',status=dict(privacyStatus='public',containsSyntheticMedia=True),snippet=dict(title='Fine',description='Fine',thumbnails={'default':{}}),contentDetails={'duration':'PT181S'})
    issues=inspect([c],[p],[],[],{'known':v},{'known'})
    assert {'Public Short missing Reels','Short missing media_url','Short over 3 minutes or not vertical'} <= {x['problem'] for x in issues}


def test_inaccessible_is_not_claimed_deleted():
    c=content(); p=dict(id=1,content_id='sample',platform='youtube',status='live',platform_id='known',url='x')
    issues=inspect([c],[p],[],[],{}, {'known'})
    assert any(x['problem']=='YouTube id inaccessible or deleted' and 'do not prove deletion' in x['action'] for x in issues)


def test_duration_and_errors():
    assert duration('PT1H2M3S')==3723
    assert duration('unknown') is None
    assert 'secret' not in safe_error('{"message":"secret","reason":"quotaExceeded"}')


def test_timestamps_normalize_negative_offsets():
    assert dt('2026-11-01T20:00:00-04:00') == dt('2026-11-02T00:00:00Z')
    assert dt('2026-11-02T00:00:00').tzinfo == timezone.utc


def test_long_media_availability_is_reported():
    c=content(); c.update(kind='long',status='published',media_url='https://media.test/long.mp4')
    issues=inspect([c],[],[],[],{},set(),heads={c['media_url']:404})
    assert any(x['problem']=='Media HEAD unavailable' for x in issues)
    c.pop('media_url')
    assert any(x['problem']=='Long missing media_url' for x in inspect([c],[],[],[],{},set()))


def test_repair_is_deterministic_and_does_not_modify_inputs():
    c=content(); c['file_path']='video.mp4'
    p=dict(id=1,content_id='sample',platform='youtube',platform_id='known',status='live')
    a=dict(id='article',content_id='sample',youtube_id=None)
    original=deepcopy((c,p,a))
    changes=plan([c],[p],[a])
    assert (c,p,a)==original
    assert {x['table'] for x in changes}=={'content','publications','articles'}
    assert not plan([{**c,'status':'published'}],[{**p,'url':'https://youtube.com/shorts/known'}],[{**a,'youtube_id':'known'}])


def test_existing_article_can_link_video_without_retained_script(tmp_path,monkeypatch):
    from unittest.mock import Mock
    from pipeline import article
    monkeypatch.setattr(article,'OUT_DIR',tmp_path)
    existing=dict(id='sample',published_at='2026-11-01T00:00:00Z',excerpt='An explainer',youtube_id=None)
    rows={'content':dict(id='sample',kind='long',channel='futurework'),
          'publications':dict(platform_id='known',status='live'),'articles':existing}
    db=Mock();db.sb=None;db.one.side_effect=lambda table,match:rows[table]
    claude=Mock()
    result=article.write_article(db,'sample',claude=claude)
    assert result['youtube_id']=='known'
    claude.run.assert_not_called()


def test_artifact_history_finds_ids_overwritten_by_resume(monkeypatch):
    import io
    import json
    import zipfile
    from scripts import audit_videos as audit
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('sample/result.json',json.dumps({'content_id':'sample','publications':[{'platform':'youtube','id':'earlier','content_id':'sample'}]}))
        z.writestr('sample/sample.mp4',b'mock')
    monkeypatch.setattr(audit,'RemoteArchive',lambda *args:io.BytesIO(data.getvalue()))
    monkeypatch.setattr(audit,'gh_json',lambda *args:{'artifacts':[{'id':1,'name':'videos-futurework-123','size_in_bytes':len(data.getvalue()),'workflow_run':{'id':123}}]})
    mapping,alternates,errors=audit.artifact_history([content()],[{'content_id':'sample','platform':'youtube','platform_id':'current'}])
    assert errors==0
    assert mapping['sample']['run_id']==123
    assert alternates[0]['platform_id']=='earlier'
