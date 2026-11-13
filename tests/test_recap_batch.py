import json
from pathlib import Path
from pipeline.recap import batch, core
from pipeline.recap.source import LocalFolder
from pipeline.db import DB


def test_names():
    assert batch.parse_name('The.Matrix.1999.1080p.WEBRip.x264.mkv') == ('the matrix', 1999)
    assert batch.parse_name('A_Film_2020_720p.mp4') == ('a film', 2020)
    assert batch.parse_name('Film.WEBRip.x264.mp4') == ('film', None)


def test_hash(tmp_path):
    source = LocalFolder(tmp_path)
    a, b = tmp_path/'a.mp4', tmp_path/'renamed.mp4'
    a.write_bytes(b'a'*4096); b.write_bytes(a.read_bytes())
    assert batch.fast_hash(source,a,100) == batch.fast_hash(source,b,100)
    data=bytearray(b.read_bytes()); data[2000:2100]=b'b'*100; b.write_bytes(data)
    assert batch.fast_hash(source,a,100) != batch.fast_hash(source,b,100)


def test_decisions():
    a=dict(id='a',content_hash='x',normalized_title='film',year=2000,duration=6000)
    b={**a,'id':'b'}
    assert batch.duplicate_decision(b,[a]) == 'duplicate'
    b['content_hash']='y'
    assert batch.duplicate_decision(b,[a]) == 'possible duplicate'
    b.update(normalized_title='other',year=2001)
    assert batch.duplicate_decision(b,[a]) == 'possible duplicate'
    b['duplicate_confirmed']=True
    assert batch.duplicate_decision(b,[a]) == 'new'


def setup_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(core,'OUTPUT',tmp_path/'out')
    monkeypatch.setattr(core,'probe',lambda p:dict(duration=600,width=1920,height=1080,has_audio=False))
    source_path=tmp_path/'films';source_path.mkdir()
    for i in range(3):
        p=source_path/f'Film{i}.200{i}.mp4';p.write_bytes(bytes([i])*10)
    # Only individually keyed rights, never folder-wide defaults.
    (source_path/'rights.json').write_text(json.dumps({'Film0.2000.mp4':{'basis':'own work'},'Film1.2001.mp4':{'basis':'own work'}}))
    return LocalFolder(source_path), DB()


def test_rights_resume_failure_and_review(tmp_path,monkeypatch):
    source,db=setup_folder(tmp_path,monkeypatch)
    # Avoid possible duplicates for unrelated tiny test sources.
    monkeypatch.setattr(batch,'duplicate_decision',lambda row,others:'new')
    report=batch.scan(source,db)
    assert [r['status'] for r in report['films']] == ['new','new','needs rights']
    calls=[]
    def runner(work,state,**kw):
        calls.append(state['title'])
        if state['title']=='Film0': raise RuntimeError('fixture failure')
        state['status']='review';core.dump(work/'state.json',state)
    assert batch.run_batch(source,db,runner=runner)['films'][0]['status']=='new'
    batch.run_batch(source,db,approve=True,runner=runner)
    assert calls==['Film0','Film1']
    assert [r['status'] for r in batch.scan(source,db)['films']]==['failed','already processed','needs rights']
    batch.run_batch(source,db,runner=runner)
    assert calls==['Film0','Film1']


def test_restart_uses_saved_project(tmp_path,monkeypatch):
    source,db=setup_folder(tmp_path,monkeypatch)
    monkeypatch.setattr(batch,'duplicate_decision',lambda row,others:'new')
    seen=[]
    def crash(work,state,**kw):
        seen.append(state['id']);raise KeyboardInterrupt()
    import pytest
    with pytest.raises(KeyboardInterrupt): batch.run_batch(source,db,approve=True,runner=crash)
    def finish(work,state,**kw):
        seen.append(state['id']);state['status']='review';core.dump(work/'state.json',state)
    batch.run_batch(source,db,runner=finish)
    assert seen[0]==seen[1]
    assert len(seen)==3


def test_renamed_registry_duplicate(tmp_path,monkeypatch):
    source,db=setup_folder(tmp_path,monkeypatch)
    batch.scan(source,db)
    p=source.folder/'Film0.2000.mp4';p.rename(source.folder/'Renamed.2000.mp4')
    rows=batch.scan(source,db)['films']
    assert next(r for r in rows if r['filename']=='Renamed.2000.mp4')['status']=='duplicate'


def test_identical_new_copies_process_one():
    from pipeline.recap.batch import duplicate_decision
    a = dict(id='a', content_hash='h', normalized_title='x', year=1950, duration=100.0, status='new')
    b = dict(a, id='b', status='duplicate')
    assert duplicate_decision(a, [a, b]) == 'new'
    assert duplicate_decision(dict(b, status='new'), [a, b]) == 'duplicate'
