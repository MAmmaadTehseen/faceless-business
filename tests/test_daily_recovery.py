import json
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from pipeline.common import Channel
from pipeline import shorts_daily as daily


def test_paid_invalid_daily_response_survives_new_runner(tmp_path,monkeypatch):
    monkeypatch.setattr(daily,'OUT_DIR',tmp_path)
    cid='futurework-'+datetime.now(timezone.utc).date().isoformat()+'-short-example'
    data={'script':'too short','hook_title':'Example','facts_check':[]}
    row=dict(id=cid,topic='Example',qa_notes=json.dumps({'daily_script':data}),status='draft')
    db=Mock(); db.setting.side_effect=lambda k,default=None:default;db.select.return_value=[row]
    monkeypatch.setattr(daily.CostGuard,'check',lambda *a,**kw:True)
    client=Mock();monkeypatch.setattr(daily,'Claude',Mock(return_value=client))
    with pytest.raises(RuntimeError,match='paid response saved'):
        daily.produce_daily(db,Channel())
    client.run.assert_not_called()


def test_daily_saved_qa_findings_are_not_mistaken_for_script(tmp_path,monkeypatch):
    monkeypatch.setattr(daily,'OUT_DIR',tmp_path)
    assert daily.saved_daily_script(dict(id='v',qa_notes='[]')) is None
    assert daily.saved_daily_script(dict(id='v',qa_notes='not json')) is None


@pytest.mark.parametrize('cloud',[False,True])
def test_qa_failure_preserves_paid_script_for_fresh_runner(tmp_path,monkeypatch,cloud):
    monkeypatch.setattr(daily,'OUT_DIR',tmp_path)
    if cloud:
        monkeypatch.setenv('GITHUB_RUN_ID','123')
    else:
        monkeypatch.delenv('GITHUB_RUN_ID',raising=False)
    data={'script':'saved narration','hook_title':'Example','facts_check':[]}
    notes=daily.daily_production_notes([{'severity':'blocking','text':'black frames'}],Channel(),data)
    assert daily.saved_daily_script({'id':'video','qa_notes':notes})==data
    assert json.loads(notes)['issues'][0]['severity']=='blocking'
    if cloud:
        assert json.loads(notes)['artifact_run_id']=='123'
