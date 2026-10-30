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


def test_short_clip_holds_last_frame(tmp_path):
    out = render._fit_clip(colour(tmp_path), 0.6, 'landscape', tmp_path / 'slot.mp4')
    assert probe(out)['duration'] == pytest.approx(0.6, abs=0.034)
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
