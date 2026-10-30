import json
from unittest.mock import Mock

import pytest

from pipeline import run_all

CID = 'escapevelocity-2026-10-29-test'


@pytest.fixture
def artifact(tmp_path):
    data = json.loads(run_all.FIXTURE.read_text())
    (tmp_path / 'script.json').write_text(json.dumps(data))
    (tmp_path / f'{CID}.mp4').touch()
    return tmp_path


def test_default_resume_reuses_long(artifact):
    assert run_all.resume_plan(artifact, CID) == ('thumbnail', 'qa', 'shorts', 'publish', 'article')


def test_rerender_without_audio_or_old_video(artifact):
    (artifact / f'{CID}.mp4').unlink()
    assert run_all.resume_plan(artifact, CID, rerender=True) == (
        'tts', 'footage', 'render', 'thumbnail', 'qa', 'shorts', 'publish', 'article')


def test_rerender_retains_audio(artifact):
    (artifact / 'voice.mp3').touch()
    (artifact / 'voice.srt').touch()
    (artifact / 'voice_timings.json').write_text('[{"index": 0, "start": 0, "end": 2}]')
    assert 'tts' not in run_all.resume_plan(artifact, CID, rerender=True)


@pytest.mark.parametrize('missing', ['script.json', f'{CID}.mp4'])
def test_default_resume_missing_file(artifact, missing):
    (artifact / missing).unlink()
    with pytest.raises(FileNotFoundError, match=missing):
        run_all.resume_plan(artifact, CID)


def test_missing_shots_fail_before_work(artifact):
    data = json.loads((artifact / 'script.json').read_text())
    del data['shot_list']
    (artifact / 'script.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='shot_list'):
        run_all.resume_plan(artifact, CID, rerender=True)
    (artifact / 'result.json').write_text(json.dumps({'shot_list': [{'paragraph_index': 0, 'query': 'moon'}]}))
    assert 'render' in run_all.resume_plan(artifact, CID, rerender=True)


def test_retained_audio_requires_timings(artifact):
    (artifact / 'voice.mp3').touch()
    with pytest.raises(FileNotFoundError, match='voice_timings.json'):
        run_all.resume_plan(artifact, CID, rerender=True)


@pytest.mark.parametrize('rerender', [False, True])
def test_resume_executes_plan_without_script_calls(artifact, monkeypatch, rerender):
    out = artifact / CID
    out.mkdir()
    for file in list(artifact.iterdir()):
        if file.is_file():
            file.rename(out / file.name)
    data = json.loads((out / 'script.json').read_text())
    data['shorts'] = data['shorts'][:1]
    (out / 'script.json').write_text(json.dumps(data))
    sid = f'{CID}-short-1'
    short_file = out / f'{sid}.mp4'
    short_file.touch()
    monkeypatch.setattr(run_all, 'OUT_DIR', artifact)
    synth = Mock(return_value={'timings': [{'index': 0, 'start': 0, 'end': 2}],
                               'duration': 2, 'audio': out / 'voice.mp3', 'srt': out / 'voice.srt'})
    render = Mock(side_effect=lambda segs, audio, srt, video, *a, **kw: video)
    short = Mock(return_value={'file': short_file, 'duration': 2, 'title': 'Saved', 'script': 'Saved'})
    monkeypatch.setattr(run_all, 'synthesize', synth)
    monkeypatch.setattr(run_all, 'render', render)
    monkeypatch.setattr(run_all, 'make_short', short)
    monkeypatch.setattr(run_all, 'probe', lambda _: {'duration': 2})
    monkeypatch.setattr(run_all, 'make_thumbnail', lambda v, t, p, **kw: p)
    qa = Mock(return_value={'pass': True, 'issues': []})
    monkeypatch.setattr(run_all, 'run_qa', qa)
    for name in ('choose_topic', 'write_script'):
        monkeypatch.setattr(run_all, name, Mock(side_effect=AssertionError('must reuse script')))
    db = Mock()
    db.one.return_value = {}
    footage = Mock(placeholder=False)
    result = run_all.produce_one(db, Mock(), footage, dry_run=False, publish=False,
                                 privacy='private', resume=CID, rerender=rerender, channel=run_all.Channel('escapevelocity'))
    assert result['title'] == data['title']
    assert synth.call_count == render.call_count == short.call_count == int(rerender)
    assert qa.call_count == 2
