"""Offline QA severity and retained-render resume regressions."""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pipeline.qa import run_qa, temporal_findings, parse_temporal_output
from pipeline.run_all import produce_one
from pipeline.common import Channel


@pytest.mark.parametrize('findings,model_pass,strict,expected', [
    ([{'severity': 'minor', 'text': 'NASA logo with black pillarboxing'}], True, False, True),
    ([{'severity': 'minor', 'text': 'Incidental billboard, not a watermark'},
      {'severity': 'blocking', 'text': 'Captions cut off'}], True, False, False),
    ([{'severity': 'minor', 'text': 'Sparse but legible thumbnail'}], True, True, False),
    ([{'severity': 'minor', 'text': 'Soft archival footage with black side bars'}], False, False, True),
])
def test_severity_verdict(findings, model_pass, strict, expected, tmp_path, caplog):
    claude = Mock()
    claude.vision.return_value = ({'pass': model_pass, 'issues': findings, 'thumbnail_ok': True,
                                   'frames_ok': False, 'frames_without_caption': 3}, {})
    db = Mock()
    db.setting.return_value = strict
    with patch('pipeline.qa.probe', return_value={'duration': 20, 'has_audio': True, 'width': 1920, 'height': 1080}), \
         patch('pipeline.qa.temporal_findings', return_value=[]), \
         patch('pipeline.qa.grab_frame', return_value=tmp_path / 'frame.jpg'), caplog.at_level('INFO'):
        result = run_qa(claude, tmp_path / 'video.mp4', tmp_path / 'thumb.jpg', 20, 'id', tmp_path, db=db)
    assert result['pass'] is expected
    assert result['thumbnail_ok'] is True
    db.setting.assert_called_once_with('qa_strict', False)
    assert 'qa minor:' in caplog.text


@pytest.mark.parametrize('stderr,severity', [
    ('black_start:0 black_end:1.4 black_duration:1.4', None),
    ('black_start:300 black_end:302.5 black_duration:2.5', 'blocking'),
    ('black_start:120 black_end:121.5 black_duration:1.5', 'minor'),
    ('freeze_start:50\nfreeze_duration:6\nfreeze_end:56', 'blocking'),
    ('black_start:498 black_end:500 black_duration:2', None),
    ('freeze_start:496', 'minor'),
    ('black_start:2 black_end:4 black_duration:2', 'minor'),
    ('black_start:30 black_end:32 black_duration:2', 'blocking'),
    ('freeze_start:50\nfreeze_duration:4\nfreeze_end:54', 'blocking'),
])
def test_temporal_parser(stderr, severity):
    findings = parse_temporal_output(stderr, 500)
    assert [f['severity'] for f in findings] == ([severity] if severity else [])
    if findings:
        assert 's (' in findings[0]['text']


@pytest.mark.parametrize('failure', [FileNotFoundError('ffmpeg'), ValueError('parse')])
def test_detector_failure_is_minor(failure):
    with patch('pipeline.qa.subprocess.run', side_effect=failure):
        assert temporal_findings(Path('video.mp4'), 500)[0]['severity'] == 'minor'


def test_malformed_detector_output_is_minor():
    with patch('pipeline.qa.subprocess.run', return_value=Mock(stderr='black_duration:2')) as run:
        assert temporal_findings(Path('video.mp4'), 500)[0]['severity'] == 'minor'
    run.assert_called_once()


@pytest.mark.parametrize('vision,raises', [(True, False), (True, True), (False, False)])
def test_local_minor_preserved_and_vision_runs(vision, raises, tmp_path):
    local = {'severity': 'minor', 'text': 'black footage at 120.000-121.500s'}
    model = {'severity': 'blocking', 'text': 'Unreadable captions'}
    claude = Mock()
    if raises:
        claude.vision.side_effect = RuntimeError('offline')
    else:
        claude.vision.return_value = ({'issues': [model], 'thumbnail_ok': True}, {})
    with patch('pipeline.qa.probe', return_value={'duration': 500, 'has_audio': True, 'width': 1920, 'height': 1080}), \
         patch('pipeline.qa.temporal_findings', return_value=[local]) as detectors, \
         patch('pipeline.qa.grab_frame', return_value=tmp_path / 'frame.jpg'):
        result = run_qa(claude, tmp_path / 'video.mp4', None, 500, 'id', tmp_path, vision=vision)
    detectors.assert_called_once_with(tmp_path / 'video.mp4', 500)
    assert local in result['issues']
    assert result['pass'] is (not vision or raises)
    assert claude.vision.call_count == int(vision)
    if vision and not raises:
        assert model in result['issues']


def test_blocked_render_retained_and_resume_publishes_without_rendering(tmp_path):
    channel = Channel('escapevelocity')
    cid = 'escapevelocity-2026-10-29-fixture'
    work = tmp_path / cid
    work.mkdir()
    data = {'title': 'Fixture', 'thumbnail_text': 'Fixture', 'title_variants': ['Fixture'],
            'description': 'Description', 'script': ['Narration'], 'shorts': []}
    (work / 'script.json').write_text(json.dumps(data))
    video = work / f'{cid}.mp4'
    video.write_bytes(b'retained render')
    (work / f'{cid}.jpg').write_bytes(b'retained thumbnail')
    row = {'id': cid, 'topic': 'Fixture', 'placeholder': False}
    db = Mock()
    db.one.return_value = row
    findings = [{'severity': 'blocking', 'text': 'Unreadable captions'}]
    with patch('pipeline.run_all.OUT_DIR', tmp_path), \
         patch('pipeline.run_all.probe', return_value={'duration': 20}), \
         patch('pipeline.run_all.synthesize') as voice, \
         patch('pipeline.run_all.render') as render, \
         patch('pipeline.run_all.make_thumbnail') as thumb, \
         patch('pipeline.run_all.run_qa', side_effect=[{'pass': False, 'issues': findings}, {'pass': True, 'issues': []}]) as qa, \
         patch('pipeline.publish.publish_all', return_value=[]) as publish:
        kwargs = dict(dry_run=False, publish=True, privacy='private', resume=cid, channel=channel)
        with pytest.raises(RuntimeError, match='QA failed'):
            produce_one(db, Mock(), Mock(placeholder=False), **kwargs)
        assert video.read_bytes() == b'retained render'
        assert any(c.args[2].get('status') == 'qa_failed' for c in db.update.call_args_list)
        assert any(c.args[2].get('qa_notes') == json.dumps(findings) for c in db.update.call_args_list)
        produce_one(db, Mock(), Mock(placeholder=False), **kwargs)
        assert qa.call_count == 2
        publish.assert_called_once_with(db, cid, 'private', channel)
        voice.assert_not_called()
        render.assert_not_called()
        thumb.assert_not_called()
