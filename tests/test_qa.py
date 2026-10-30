"""Offline QA severity and retained-render resume regressions."""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pipeline.qa import run_qa, temporal_findings
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


@pytest.mark.parametrize('stderr,expected', [
    ('black_duration:0.9', False),
    ('black_duration:1.1', True),
    ('freeze_start:2\nfreeze_duration:2\nfreeze_end:4', True),
    ('freeze_start:2', True),
])
def test_sustained_black_or_frozen(stderr, expected):
    with patch('pipeline.qa.subprocess.run', return_value=Mock(stderr=stderr)), \
         patch('pipeline.qa.probe', return_value={'duration': 5}):
        assert bool(temporal_findings(Path('video.mp4'))) is expected


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
