"""Fast slot regressions; all media generated locally and encoded at tiny dimensions."""
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from pipeline import render
from pipeline.footage import Footage
from pipeline.qa import black_segments, probe


@pytest.fixture(autouse=True)
def small_frames(monkeypatch, tmp_path):
    # Bound indirect renderer/QA subprocesses as well as fixture encodes.
    real_run = subprocess.run

    def bounded_run(command, **kwargs):
        command = list(command)
        if Path(command[0]).name == 'ffmpeg' and not any(
                flag in command for flag in ('-t', '-frames:v', '-vframes')):
            command[-1:-1] = ['-t', '5']
        kwargs['timeout'] = min(kwargs.get('timeout', 30), 30)
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', bounded_run)
    monkeypatch.setattr('pipeline.footage.CACHE', tmp_path)
    monkeypatch.setattr(render, '_dims', lambda orientation: (160, 90))
    monkeypatch.setattr(Footage, '_dims', staticmethod(lambda orientation: (160, 90)))


def colour(tmp_path, colour='red', duration=0.1):
    src = tmp_path / f'{colour}.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    f'color=c={colour}:s=160x90:r=30:d={duration}',
                    '-t', str(duration), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(src)], check=True, timeout=30)
    return src


def test_short_clip_caps_last_frame_padding(tmp_path):
    out = render._fit_clip(colour(tmp_path), 0.5, 'landscape', tmp_path / 'slot.mp4')
    assert probe(out)['duration'] == pytest.approx(0.5, abs=0.034)
    assert black_segments(out, 0.03) == []


@pytest.mark.parametrize('missing', [None, 'missing.mp4'])
def test_missing_clip_tries_next_query_then_card(tmp_path, missing):
    footage = Mock()
    footage.clip.return_value = missing
    out = render._fill_slot({'query': 'rocket launch smoke', 'candidate_queries': ['space rocket'],
                             'caption': "NASA's 100%: next step"}, 0.2, 'landscape',
                            tmp_path / 'card.mp4', footage, {'accent': [34, 211, 238], 'bg': [4, 7, 14]})
    assert [call.args[0] for call in footage.clip.call_args_list] == ['rocket launch smoke', 'space rocket']
    assert probe(out)['duration'] == pytest.approx(0.2, abs=0.034)
    assert black_segments(out, 0.03) == []
    assert out.with_suffix('.txt').read_text() == "NASA's 100%: next step"


def test_second_candidate_succeeds(tmp_path):
    footage = Mock()
    footage.clip.side_effect = [RuntimeError('download failed'), colour(tmp_path)]
    render._fill_slot({'query': 'first', 'candidate_queries': ['second']}, 0.2,
                      'landscape', tmp_path / 'slot.mp4', footage)
    assert footage.clip.call_count == 2
    assert not (tmp_path / 'slot.txt').exists()


def test_photo_fallback(tmp_path, monkeypatch):
    # PPM is a real still image requiring no image libraries or external footage.
    img = tmp_path / 'photo.ppm'
    img.write_bytes(b'P6\n16 16\n255\n' + bytes([220, 80, 40]) * 256)
    monkeypatch.setattr('pipeline.footage.CACHE', tmp_path)
    footage = Footage(placeholder=True)
    photo_clip = footage._ken_burns(img, 0.1, 'landscape')
    out = render._fit_clip(photo_clip, 0.3, 'landscape', tmp_path / 'slot.mp4')
    assert probe(out)['duration'] == pytest.approx(0.3, abs=0.034)
    assert black_segments(out, 0.03) == []


def test_entirely_black_source_uses_card(tmp_path):
    footage = Mock()
    footage.clip.return_value = colour(tmp_path, 'black')
    out = render._fill_slot({'query': 'space'}, 0.2, 'landscape', tmp_path / 'slot.mp4', footage)
    assert out.with_suffix('.txt').exists()
    assert black_segments(out, 0.03) == []


def test_embedded_black_frames_removed(tmp_path):
    src = tmp_path / 'black-intro.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=black:s=160x90:r=30:d=0.1', '-f', 'lavfi', '-i',
                    'color=red:s=160x90:r=30:d=0.1', '-filter_complex',
                    '[0:v][1:v]concat=n=2:v=1:a=0', '-t', '0.2', '-c:v', 'libx264', str(src)], check=True, timeout=30)
    out = render._fit_clip(src, 0.3, 'landscape', tmp_path / 'slot.mp4')
    assert probe(out)['duration'] == pytest.approx(0.3, abs=0.034)
    assert black_segments(out, 0.03) == []


def test_self_check_logs_timestamps(tmp_path, caplog):
    src = colour(tmp_path, 'black', 1.2)
    render._check_black(src)
    assert 'black segment 0.000-' in caplog.text


def test_real_lookup_exhaustion_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr('pipeline.footage.CACHE', tmp_path)
    footage = Footage(placeholder=True)
    footage.placeholder = False
    footage.key = footage.pb_key = None
    assert footage.clip('unavailable', 1) is None


def test_failed_photo_encode_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr('pipeline.footage.CACHE', tmp_path)
    footage = Footage(placeholder=True)
    img = tmp_path / 'broken.jpg'
    img.write_bytes(b'invalid image')

    def fail_encode(command, **kwargs):
        Path(command[-1]).write_bytes(b'partial encode')
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr('pipeline.footage.subprocess.run', fail_encode)
    with pytest.raises(subprocess.CalledProcessError):
        footage._ken_burns(img, 0.1, 'landscape')
    assert not list(tmp_path.glob('*kb*.mp4'))


def test_failed_photo_falls_back_to_card(tmp_path):
    footage = Mock()
    footage.clip.side_effect = subprocess.CalledProcessError(1, ['ffmpeg'])
    out = render._fill_slot({'query': 'space', 'caption': 'The next mission'}, 0.2,
                            'landscape', tmp_path / 'card.mp4', footage)
    assert out.with_suffix('.txt').read_text() == 'The next mission'
    assert black_segments(out, 0.03) == []


def test_partial_download_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr('pipeline.footage.CACHE', tmp_path)
    footage = Footage(placeholder=True)
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    def interrupted(size):
        yield b'partial data'
        raise OSError('connection lost')

    response.iter_content.side_effect = interrupted
    monkeypatch.setattr('pipeline.footage.requests.get', Mock(return_value=response))
    with pytest.raises(OSError):
        footage._download('https://example.invalid/clip', 'clip.mp4')
    assert not list(tmp_path.glob('clip*'))


def test_almost_black_source_uses_card(tmp_path):
    src = tmp_path / 'nearly-black.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=0x141414:s=160x90:r=30:d=0.2', '-vf',
                    'drawbox=x=10:y=10:w=18:h=12:color=white:t=fill',
                    '-t', '0.2', '-c:v', 'libx264', str(src)], check=True, timeout=30)
    footage = Mock()
    footage.clip.return_value = src
    out = render._fill_slot({'query': 'space'}, 0.2, 'landscape', tmp_path / 'slot.mp4', footage)
    assert out.with_suffix('.txt').exists()
    assert black_segments(out, 0.03) == []


def motion(tmp_path, name, duration):
    src = tmp_path / f'{name}.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=s=160x90:r=30', '-t', str(duration), '-c:v', 'libx264',
                    '-preset', 'ultrafast', str(src)], check=True, timeout=4)
    return src


def test_short_motion_loops_without_half_second_freeze(tmp_path, caplog):
    from pipeline.qa import freeze_segments
    caplog.set_level('INFO')
    src = motion(tmp_path, 'moving', 2.1)
    out = render._fit_clip(src, 4.5, 'landscape', tmp_path / 'loop.mp4')
    assert probe(out)['duration'] == pytest.approx(4.5, abs=0.034)
    assert freeze_segments(out, 0.5) == []
    assert 'looping' in caplog.text


def test_tiny_motion_concatenates_next_candidate(tmp_path, caplog):
    from pipeline.qa import freeze_segments
    footage = Mock()
    caplog.set_level('INFO')
    footage.clip.side_effect = [motion(tmp_path, 'tiny', 0.2), motion(tmp_path, 'next', 2.1)]
    out = render._fill_slot({'query': 'first', 'candidate_queries': ['next']}, 4.5,
                            'landscape', tmp_path / 'joined.mp4', footage)
    assert [call.args[0] for call in footage.clip.call_args_list] == ['first', 'next']
    assert probe(out)['duration'] == pytest.approx(4.5, abs=0.034)
    assert freeze_segments(out, 0.51) == []
    assert 'concatenating next candidate' in caplog.text


def test_six_second_photo_motion_clears_qa(tmp_path):
    from pipeline.qa import freeze_segments
    img = tmp_path / 'lavfi.bmp'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=s=320x180:r=1', '-t', '1', '-frames:v', '1', str(img)],
                   check=True, timeout=4)
    footage = Footage(placeholder=True)
    out = footage._ken_burns(img, 6, 'landscape')
    assert probe(out)['duration'] == pytest.approx(6, abs=0.034)
    assert freeze_segments(out) == []
    assert freeze_segments(out, 0.5) == []


def test_moving_caption_card_clears_qa(tmp_path):
    from pipeline.qa import freeze_segments
    out = render._background_card('The next mission to the Moon', 6, 'landscape', tmp_path / 'card.mp4')
    assert freeze_segments(out) == []


def test_retry_starts_with_next_candidate(tmp_path):
    footage = Mock()
    footage.clip.return_value = motion(tmp_path, 'retry', 2.1)
    render._fill_slot({'query': 'first', 'candidate_queries': ['second'], '_retry': True},
                      2, 'landscape', tmp_path / 'retry-slot.mp4', footage)
    assert footage.clip.call_args.args[0] == 'second'


@pytest.mark.parametrize('failures', [1, 2, 3, 4])
def test_post_render_retry_loop_and_fallback(tmp_path, monkeypatch, caplog, failures):
    caplog.set_level('INFO')
    fill = Mock(side_effect=lambda seg, sec, orientation, out, *args: out)
    monkeypatch.setattr(render, '_fill_slot', fill)
    monkeypatch.setattr(render, '_check_black', Mock())
    monkeypatch.setattr(render, '_music', lambda: None)
    monkeypatch.setattr(render, '_font', lambda: None)
    scan = Mock(side_effect=[[(6, 10.1)]] * failures + [[]])
    card = Mock()
    monkeypatch.setattr(render, '_background_card', card)
    monkeypatch.setattr('pipeline.qa.probe', lambda path: {'duration': 6})
    monkeypatch.setattr('pipeline.qa.freeze_segments', scan)
    runner = Mock()
    monkeypatch.setattr(subprocess, 'run', runner)
    segments = [{'query': 'first', 'start': 0, 'end': 6},
                {'query': 'second', 'start': 6, 'end': 12}]
    out = tmp_path / 'final.mp4'
    render.render(segments, tmp_path / 'voice.wav', tmp_path / 'captions.srt', out,
                  footage=Mock())
    assert fill.call_count == 2 + min(failures, 3)
    assert fill.call_args.args[0] == dict(segments[1], _retry=True)
    assert scan.call_count == failures + 1
    assert card.call_count == (1 if failures == 4 else 0)
    if failures == 4:
        assert card.call_args.args[0] == 'second'
        assert card.call_args.args[3].name == 'seg_001.mp4'
    assert 'replacement attempt 1/3' in caplog.text
    assert not (tmp_path / 'final_work').exists()


def test_black_stripping_loops_cleaned_motion(tmp_path):
    from pipeline.qa import freeze_segments
    src = tmp_path / 'black-and-motion.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=black:s=160x90:r=30:d=0.4', '-f', 'lavfi', '-i',
                    'testsrc2=s=160x90:r=30:d=2.1', '-filter_complex',
                    '[0:v][1:v]concat=n=2:v=1:a=0', '-t', '2.5', '-c:v',
                    'libx264', '-preset', 'ultrafast', str(src)], check=True, timeout=4)
    out = render._fit_clip(src, 4.5, 'landscape', tmp_path / 'clean-loop.mp4')
    assert probe(out)['duration'] == pytest.approx(4.5, abs=0.034)
    assert black_segments(out, 0.03) == []
    assert freeze_segments(out, 0.5) == []


def test_renderer_detector_merges_qa_short_events(monkeypatch, tmp_path):
    from pipeline.qa import freeze_segments
    monkeypatch.setattr('pipeline.qa.probe', lambda path: {'duration': 12})
    events = '\n'.join(f'freeze_start: {i}\nfreeze_duration: 1\nfreeze_end: {i+1}'
                       for i in range(3, 8))
    runner = Mock(return_value=Mock(stderr=events))
    monkeypatch.setattr(subprocess, 'run', runner)
    assert freeze_segments(tmp_path / 'video.mp4') == [(3, 8)]
    assert 'freezedetect=n=-60dB:d=0.1' in runner.call_args.args[0]


def test_frozen_card_fails_closed_and_cleans_work(monkeypatch, tmp_path):
    monkeypatch.setattr(render, '_fill_slot', lambda seg, sec, orientation, out, *args: out)
    monkeypatch.setattr(render, '_background_card', Mock())
    monkeypatch.setattr(render, '_check_black', Mock())
    monkeypatch.setattr(render, '_music', lambda: None)
    monkeypatch.setattr(render, '_font', lambda: None)
    monkeypatch.setattr('pipeline.qa.probe', lambda path: {'duration': 6})
    monkeypatch.setattr('pipeline.qa.freeze_segments', lambda path: [(0, 6)])
    monkeypatch.setattr(subprocess, 'run', Mock())
    with pytest.raises(RuntimeError, match='moving card still frozen'):
        render.render([{'query': 'static', 'start': 0, 'end': 6}],
                      tmp_path / 'audio', tmp_path / 'srt', tmp_path / 'final.mp4', footage=Mock())
    assert not (tmp_path / 'final_work').exists()
