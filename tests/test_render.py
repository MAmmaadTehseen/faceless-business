"""Fast slot regressions; all media generated locally and encoded at tiny dimensions."""
import json
import re
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

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
    monkeypatch.setattr('pipeline.qa.probe', lambda path: {'duration': 6})
    monkeypatch.setattr('pipeline.qa.freeze_segments', lambda path: [(0, 6)])
    monkeypatch.setattr(subprocess, 'run', Mock())
    with pytest.raises(RuntimeError, match='moving card still frozen'):
        render.render([{'query': 'static', 'start': 0, 'end': 6}],
                      tmp_path / 'audio', tmp_path / 'srt', tmp_path / 'final.mp4', footage=Mock())
    assert not (tmp_path / 'final_work').exists()


def test_hook_lines_wrap_and_cap():
    from pipeline.render import hook_lines
    assert hook_lines("Only 5 Starship Launches This Year?") == ["Only 5 Starship", "Launches This", "Year?"]
    assert hook_lines("") == []
    long = hook_lines("A very long hook title that goes on and on well past three lines of text")
    assert len(long) == 3 and long[-1].endswith("...")


def test_hook_filter_only_for_portrait(tmp_path):
    from pipeline.render import _hook_filter, HOOK_SECONDS
    assert _hook_filter("Swift fell 114 km", tmp_path, "landscape") is None
    f = _hook_filter("Swift fell 114 km", tmp_path, "portrait")
    assert f.startswith("drawtext=") and f"enable='lt(t,{HOOK_SECONDS})'" in f
    # 15-character lines since 2026-11-24 (92 px type): "Swift fell 114 km" wraps to two lines.
    assert f.count("drawtext=") == 2 and (tmp_path / "hook_0.txt").read_text() == "Swift fell 114"
    assert "fontcolor=black" in f and "boxcolor=0xfbbf24" in f  # black on the default accent
    assert f"fontfile='{render._font_path(render.FALLBACK_FONT)}':" in f  # no style -> DejaVu fallback
    two = _hook_filter("Only 5 Starship Launches This Year?", tmp_path, "portrait", {"accent": (34, 211, 238)})
    assert two.count("drawtext=") == 3  # one per wrapped line (ffmpeg 8 draws newlines as missing glyphs)
    assert "boxcolor=0x22d3ee" in two and (tmp_path / "hook_2.txt").read_text() == "Year?"


# ---------- per-channel fonts (2026-11-25) ----------

def test_font_for_each_channel_and_fallback():
    """channel.json style.fonts picks the vendored file; anything else falls back to DejaVu."""
    from pipeline.common import Channel
    from pipeline.render import FALLBACK_FONT, OFL_FONT_DIR, font_for
    expected = {
        "futurework": ("Montserrat-Black.ttf", "Montserrat-ExtraBold.ttf"),
        "tradewinds": ("Anton-Regular.ttf", "Oswald-Bold.ttf"),
        "escapevelocity": ("BebasNeue-Regular.ttf", "Exo2-Black.ttf"),
        "tentongues": ("Poppins-ExtraBold.ttf", "Poppins-ExtraBold.ttf"),
    }
    for key, (caption, headline) in expected.items():
        style = Channel(key).style
        assert font_for(style, "caption") == OFL_FONT_DIR / caption, key
        assert font_for(style, "headline") == OFL_FONT_DIR / headline, key
        assert font_for(style, "caption").is_file(), key  # vendored files must exist
    assert font_for(None, "caption") == FALLBACK_FONT
    assert font_for({}, "headline") == FALLBACK_FONT
    assert font_for({"fonts": {}}, "caption") == FALLBACK_FONT
    # a missing file (typo in channel.json) must fall back, never fail a render
    assert font_for({"fonts": {"caption": "Nope.ttf", "headline": ""}}, "caption") == FALLBACK_FONT
    assert font_for({"fonts": {"headline": "../evil.ttf"}}, "headline") == FALLBACK_FONT


def test_hook_filter_and_card_use_the_headline_fontfile(tmp_path):
    """drawtext hooks and stat cards burn the channel's headline font, not the DejaVu default."""
    from pipeline.common import Channel
    from pipeline.render import _background_card, _font_path, _hook_filter, font_for
    style = Channel("tradewinds").style
    headline = font_for(style, "headline")
    assert headline.name == "Oswald-Bold.ttf"
    vf = _hook_filter("Swift fell 114 km", tmp_path, "portrait", style)
    assert f"fontfile='{_font_path(headline)}':" in vf
    assert "DejaVu" not in vf
    card = _background_card("25,000 JOBS", 2, "portrait", tmp_path / "card.mp4", style, big=True)
    assert card.is_file()  # ffmpeg accepted the fontfile and rendered


def test_caption_style_names_the_caption_family_and_fontsdir_is_its_folder():
    """force_style FontName must be a name libass/fontconfig matches (see render._font_family),
    and fontsdir must be exactly the caption font's own folder (the scan is not recursive
    and a multi-directory value silently disables app-font loading)."""
    from pipeline.common import Channel
    from pipeline.render import FALLBACK_FONT, _caption_style, caption_fontsdir, font_for
    for key, family in [("futurework", "Montserrat Black"), ("tradewinds", "Anton Regular"),
                        ("escapevelocity", "Bebas Neue Regular"), ("tentongues", "Poppins ExtraBold")]:
        style = Channel(key).style
        assert f"FontName={family}" in _caption_style("portrait", style), key
        assert "DejaVu" not in _caption_style("portrait", style), key
        assert caption_fontsdir(style) == f":fontsdir={font_for(style, 'caption').parent}", key
    # no style -> DejaVu fallback, fontsdir points at assets/fonts (its own folder)
    assert "FontName=DejaVu Sans Bold" in _caption_style("landscape", None)
    assert caption_fontsdir(None) == f":fontsdir={FALLBACK_FONT.parent}"
    # the named family must be the real TTF family of the caption font, not the file stem
    from PIL import ImageFont
    fam, sub = ImageFont.truetype(str(font_for(Channel("futurework").style, "caption")), 24).getname()
    assert _caption_style("portrait", Channel("futurework").style).split(",")[0] == f"FontName={fam} {sub}"


def test_graphics_and_thumbnails_use_the_headline_font(tmp_path):
    """Charts/maps draw their text in the headline font; thumbnails take an optional font path."""
    from PIL import ImageFont
    from pipeline.common import Channel
    from pipeline.graphics import chart_image, map_image
    from pipeline.render import font_for
    from pipeline.thumbnail import make_card_thumbnail, make_thumbnail
    style = Channel("tradewinds").style
    headline = font_for(style, "headline")
    chart = chart_image("US tariff | 2023=25%, 2024=100%", (160, 90), style)
    ImageFont.truetype(str(headline), 12)  # headline font is a loadable TTF the chart drew with
    assert chart.size == (160, 90)
    map_img = map_image("Iran, Oman | Strait of Hormuz", (160, 90), style)
    assert map_img.size == (160, 90)
    # DejaVu is kept as the fallback when style has no fonts
    assert chart_image("T | a=1, b=2", (160, 90), None).size == (160, 90)
    assert map_image("Iran | Hormuz", (160, 90), {}).size == (160, 90)
    thumb = make_card_thumbnail("AI JOB CUTS", tmp_path / "card.jpg", (251, 191, 36), font_path=headline)
    assert thumb.is_file() and thumb.stat().st_size > 1000
    # the frame thumbnail takes the same optional font path (its pipeline callers pass it)
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (640, 360), (30, 30, 60)).save(frame)
    photo_thumb = make_thumbnail(tmp_path / "missing.mp4", "AI JOB CUTS", tmp_path / "photo.jpg",
                                  frame=frame, font_path=headline)
    assert photo_thumb.is_file() and photo_thumb.stat().st_size > 1000


def test_add_hook_card_reencodes_portrait_clip(tmp_path):
    from pipeline.render import add_hook_card
    from pipeline.qa import probe
    src = tmp_path / "s.mp4"
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=540x960:rate=24:duration=2',
                    '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-shortest', '-c:v', 'libx264', '-c:a', 'aac', str(src)], check=True)
    dst = add_hook_card(src, tmp_path / "s.hook.mp4", "Swift fell 114 km in 69 days")
    assert dst.is_file() and dst != src
    assert abs(probe(dst)["duration"] - 2.0) < 0.3
    assert not (tmp_path / "s.hook_hookwork").exists()


def test_apply_shots_gives_each_segment_its_own_visual():
    from pipeline.render import apply_shots
    segs = [{"query": "dish", "caption": f"c{i}"} for i in range(4)]
    out = apply_shots(segs, ["Voyager spacecraft", "CARD: 15 BILLION MILES", "mission control"], "dish")
    assert out[0]["query"] == "Voyager spacecraft" and out[0]["candidate_queries"] == ["dish"]
    assert out[1]["card"] == "15 BILLION MILES"
    assert out[2]["query"] == "mission control"
    assert out[3]["query"] == "Voyager spacecraft" and "card" not in out[3]  # cycles through footage queries only
    legacy = [{"query": "dish"}]
    assert apply_shots(legacy, None, "dish") == [{"query": "dish"}]  # resumed scripts without shots are unchanged


def test_chart_and_map_shots(tmp_path):
    from pipeline.render import apply_shots, _fill_slot
    from pipeline.graphics import parse_chart, parse_map
    title, items = parse_chart("US tariff | 2023=25%, 2024=100%")
    assert title == "US tariff" and [v for _, v, _ in items] == [25.0, 100.0]
    assert [v for _, v, _ in parse_chart("Cuts | Amazon=14,000, Intel=24,000")[1]] == [14000.0, 24000.0]
    assert parse_chart("Debt | 2020=1.2 trillion, 2024=2 trillion")[1][1][1] == 2e12
    assert parse_map("Iran, Oman | Strait of Hormuz") == (["Iran", "Oman"], "Strait of Hormuz")
    segs = apply_shots([{"query": "q"}, {"query": "q"}], ["CHART: T | a=1, b=2", "MAP: Iran | Hormuz"], "q")
    assert segs[0]["graphic"] == ("chart", "T | a=1, b=2") and segs[1]["graphic"] == ("map", "Iran | Hormuz")
    footage = Mock()
    out = _fill_slot({"query": "MAP: Iran, Oman | Strait of Hormuz", "caption": "c"}, 0.5, "portrait",
                     tmp_path / "map.mp4", footage)
    assert out.exists() and (tmp_path / "map.png").exists() and not footage.clip.called
    out = _fill_slot({"query": "q", "graphic": ("map", "Atlantis | Nowhere")}, 0.5, "landscape", tmp_path / "bad.mp4", footage)
    assert out.with_suffix(".txt").read_text() == "NOWHERE"  # unknown place falls back to a stat card


# ---------- word-highlight captions (2026-11-25) ----------

@pytest.fixture()
def real_frames(monkeypatch):
    """The module fixture shrinks frames to 160x90 for fast slot encodes; caption layout needs the
    real 1080x1920 / 1920x1080 PlayRes the production filter burns, so restore it per test."""
    monkeypatch.setattr(render, '_dims', lambda orientation: (1920, 1080) if orientation == 'landscape' else (1080, 1920))


def _word_timings(*lines, gap=0.4, dur=0.4):
    """[sentence] -> tts-style timings [{index,start,end,words:[{text,start,end}]}]]."""
    timings, words, t = [], [], 0.0
    for i, line in enumerate(lines):
        sent = []
        for w in line.split():
            sent.append({"text": w, "start": t, "end": t + dur})
            t += gap
        timings.append({"index": i, "start": sent[0]["start"], "end": sent[-1]["end"], "words": sent})
        words.extend(sent)
    return timings


def _dialogues(ass_text):
    return [l.split(",", 9)[-1] for l in ass_text.splitlines() if l.startswith("Dialogue:")]


def test_caption_chunks_two_to_three_words_with_punctuation_break(real_frames):
    from pipeline.render import caption_chunks
    words = _word_timings("The new robots are coming for office jobs now. Stay calm.")[-1]["words"]
    chunks = caption_chunks(words, None, 60.0, 1080)
    assert [len(c) for c in chunks] == [3, 3, 3, 2]
    assert [w["text"] for c in chunks for w in c] == [w["text"] for w in words]
    # a sentence ender closes its chunk; the next word starts a fresh one
    assert chunks[2][-1]["text"] == "now." and chunks[3][0]["text"] == "Stay"
    # a mid-sentence comma does not shatter a chunk (only sentence enders break early)
    comma = _word_timings("Robots are coming, but slowly.")[-1]["words"]
    assert [len(c) for c in caption_chunks(comma, None, 60.0, 1080)] == [3, 2]


def test_write_ass_highlights_only_the_active_word_in_the_accent_colour(tmp_path, real_frames):
    from pipeline.render import caption_chunks, font_size_portrait, write_ass
    style = {"accent": [34, 211, 238]}
    timings = _word_timings("The robots are coming")
    out = write_ass(timings, tmp_path / "cap.ass", "portrait", style)
    text = out.read_text()
    dialogues = _dialogues(text)
    words = timings[0]["words"]
    chunks = caption_chunks(words, style, font_size_portrait(style), 1080)
    assert len(dialogues) == len(words)  # one event per word
    # RGB 34,211,238 -> ASS &H00BBGGRR& with B=238 G=211 R=34 = &H00EED322&
    assert "&H00EED322&" in dialogues[0]
    for line, (chunk, active) in zip(dialogues, [(c, w) for c in chunks for w in c]):
        # exactly one accent-colour override per event: the active word, reset to white after it
        assert line.count("{\\c&H00EED322&}") == 1 and line.count("{\\c&H00FFFFFF&}") == 1
        marked = line.split("{\\c&H00EED322&}")[1].split("{\\c&H00FFFFFF&}")[0]
        assert marked == active["text"]
        # strip the tags and the event reads back as the whole chunk, in order
        plain = line.replace("{\\c&H00EED322&}", "").replace("{\\c&H00FFFFFF&}", "")
        assert plain == " ".join(w["text"] for w in chunk)


def test_write_ass_preserves_word_timings_verbatim(tmp_path, real_frames):
    from pipeline.render import _ass_ts, write_ass
    timings = _word_timings("Automation will replace forty percent of jobs", gap=0.31, dur=0.25)
    out = write_ass(timings, tmp_path / "cap.ass", "landscape", {})
    lines = [l for l in out.read_text().splitlines() if l.startswith("Dialogue:")]
    flat = [w for t in timings for w in t["words"]]
    assert len(lines) == len(flat)
    for line, word in zip(lines, flat):
        fields = line.split(",")
        assert fields[1] == _ass_ts(word["start"]) and fields[2] == _ass_ts(word["end"])
    # the first event starts at the first word's start, the last ends at the last word's end
    assert lines[0].split(",")[1] == "0:00:00.00"
    assert float(timings[-1]["words"][-1]["end"]) > 1.0  # the data really spans past a second


def test_write_ass_shrinks_a_single_over_wide_word(tmp_path, real_frames):
    from pipeline.render import caption_chunks, write_ass
    # a long single word at the full caption size is wider than 88% of a 1080 px frame
    long_word = "Extraordinarilyunbelievableantidisestablishmentarianism"
    timings = _word_timings(f"one {long_word} two", gap=0.4, dur=0.3)
    words = timings[0]["words"]
    size = 173.33
    chunks = caption_chunks(words, None, size, 1080)
    assert [w["text"] for c in chunks for w in c] == [w["text"] for w in words]
    out = write_ass(timings, tmp_path / "cap.ass", "portrait", None)
    dialogues = _dialogues(out.read_text())
    assert len(dialogues) == 3
    assert not dialogues[0].startswith("{\\fs")  # 'one' at the default size needs no shrink
    shrunk = dialogues[1]
    assert shrunk.startswith("{\\fs")
    assert long_word in shrunk and "Extra" in shrunk
    # the shrink actually brings the measured width under the limit
    from pipeline.render import _caption_font
    fs = int(shrunk.split("}")[0][len("{\\fs"):])
    assert _caption_font(None, fs).getlength(long_word) <= 1080 * 0.88
    # a normal word next to it keeps the default size
    assert not dialogues[2].startswith("{\\fs")


def test_write_ass_splits_wide_chunks_and_keeps_style_frame(tmp_path, real_frames):
    from pipeline.render import write_ass
    from pipeline.common import Channel
    style = Channel("futurework").style
    timings = _word_timings("Automation will replace forty percent of jobs now", gap=0.4, dur=0.3)
    out = write_ass(timings, tmp_path / "cap.ass", "portrait", style)
    text = out.read_text()
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    assert f"Style: Cap,Montserrat Black,173.33," in text
    assert ",1,6,0,2,0,0,733,1" in text  # Outline 6 portrait, BorderStyle 1, Shadow 0, Alignment 2, MarginV 733
    landscape = write_ass(timings, tmp_path / "cap2.ass", "landscape", style).read_text()
    assert "PlayResX: 1920" in landscape and "PlayResY: 1080" in landscape
    assert f"Style: Cap,Montserrat Black,75.00," in landscape
    assert ",1,4,0,2,0,0,180,1" in landscape  # Outline 4 landscape, MarginV 180
    # every event text stays within 88% of the frame width as libass will measure it
    from pipeline.render import _caption_font, font_size_portrait
    font_size = font_size_portrait(style)
    for line in _dialogues(text):
        # strip every override tag ({\fsNN} shrink, {\c...} colour) before measuring the chunk
        body = re.sub(r"\{\\[^}]*\}", "", line)
        assert _caption_font(style, font_size).getlength(body) <= 1080 * 0.88, body


def test_render_uses_ass_when_timings_exist_else_srt(tmp_path, monkeypatch, real_frames):
    """render() burns the word-highlight ASS for word timings, the SRT path when there are none."""
    from pipeline.render import _caption_ass, write_ass
    timings = _word_timings("Robots are taking over the office", gap=0.4, dur=0.3)
    style = {"accent": [251, 191, 36], "fonts": {"caption": "Montserrat-Black.ttf"}}
    # explicit timings -> an ASS with word-highlight events
    ass = _caption_ass(timings, tmp_path / "voice.mp3", tmp_path, "portrait", style)
    assert ass is not None and "Dialogue: 0," in ass.read_text()
    assert "{\\c&H0024BFFB&}" in ass.read_text()  # RGB 251,191,36 -> &H0024BFFB&
    # timings=None -> loaded from <audio stem>_timings.json next to the audio
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"")
    (tmp_path / "voice_timings.json").write_text(
        json.dumps([{"index": 0, "start": 0, "end": 1.2,
                     "words": [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.3}
                               for i, w in enumerate("a b c".split())]}]))
    ass = _caption_ass(None, audio, tmp_path, "portrait", style)
    assert ass is not None and _dialogues(ass.read_text())[:1] == ["{\\c&H0024BFFB&}a{\\c&H00FFFFFF&} b c"]
    # a timings file without per-word detail (retained audio) -> None: keep the SRT path
    (tmp_path / "voice_timings.json").write_text(json.dumps([{"index": 0, "start": 0, "end": 2}]))
    assert _caption_ass(None, audio, tmp_path, "portrait", style) is None
    # no timings anywhere -> None
    assert _caption_ass(None, tmp_path / "missing.mp3", tmp_path, "portrait", style) is None
    # an empty/invalid JSON timings file must not break the render
    (tmp_path / "voice_timings.json").write_text("{oops")
    assert _caption_ass(None, audio, tmp_path, "portrait", style) is None


def test_render_passes_the_ass_to_the_subtitles_filter(tmp_path, monkeypatch, caplog):
    """_render builds captions.ass in its work dir and burns it with fontsdir (no force_style)."""
    caplog.set_level('INFO')
    monkeypatch.setattr(render, '_fill_slot', lambda seg, sec, orientation, out, *a: out)
    monkeypatch.setattr(render, '_check_black', Mock())
    monkeypatch.setattr(render, '_music', lambda: None)
    monkeypatch.setattr('pipeline.qa.freeze_segments', lambda path: [])
    runner = Mock()
    monkeypatch.setattr(subprocess, 'run', runner)
    timings = _word_timings("Robots are taking over the office", gap=0.4, dur=0.3)
    out = tmp_path / 'final.mp4'
    render.render([{'query': 'robots', 'start': 0, 'end': 1.2}], tmp_path / 'voice.wav',
                  tmp_path / 'captions.srt', out, footage=Mock(), hook_text=None, timings=timings)
    vf_line = None
    for c in runner.call_args_list:
        for item in (c.args[0] if c.args and isinstance(c.args[0], (list, tuple)) else c.args):
            if isinstance(item, str) and item.startswith('subtitles='):
                vf_line = item
    assert vf_line is not None and vf_line.startswith("subtitles='")
    assert '.ass' in vf_line and 'force_style' not in vf_line and ':fontsdir=' in vf_line
    assert 'word-highlight captions' in caplog.text
    assert not (tmp_path / 'final_work').exists()  # render() cleans the work dir


def test_render_keeps_srt_path_without_timings(tmp_path, monkeypatch):
    monkeypatch.setattr(render, '_fill_slot', lambda seg, sec, orientation, out, *a: out)
    monkeypatch.setattr(render, '_check_black', Mock())
    monkeypatch.setattr(render, '_music', lambda: None)
    monkeypatch.setattr('pipeline.qa.freeze_segments', lambda path: [])
    runner = Mock()
    monkeypatch.setattr(subprocess, 'run', runner)
    render.render([{'query': 'robots', 'start': 0, 'end': 1.2}], tmp_path / 'novoice.wav',
                  tmp_path / 'captions.srt', tmp_path / 'final.mp4', footage=Mock())
    vf_line = None
    for c in runner.call_args_list:
        for item in (c.args[0] if c.args and isinstance(c.args[0], (list, tuple)) else c.args):
            if isinstance(item, str) and item.startswith('subtitles='):
                vf_line = item
    assert vf_line is not None and '.srt' in vf_line and 'force_style' in vf_line
    # no <audio stem>_timings.json exists next to the audio, so nothing switched the pass on


def test_caption_chunks_shrink_measured_with_pil_at_libass_equivalent_size(real_frames):
    """The 88% rule measures with PIL at the em-corrected size, which matches libass within ~1%
    (measured 2026-11-25: 'hello world' PIL 909 vs libass 910 at Fontsize 173.33). The check is
    per-chunk: every returned chunk fits one line, and a chunk that would wrap is split."""
    from pipeline.render import _caption_font, caption_chunks, font_size_portrait
    size = font_size_portrait()  # 26 * 1920/288 = 173.33
    font = _caption_font(None, size)
    words = _word_timings("robots are coming to an office near you")[-1]["words"]
    chunks = caption_chunks(words, None, size, 1080)
    assert 1 <= len(chunks) <= 4 and [w["text"] for c in chunks for w in c] == [w["text"] for w in words]
    for chunk in chunks:
        assert 1 <= len(chunk) <= 3
        assert font.getlength(" ".join(w["text"] for w in chunk)) <= 1080 * 0.88
    # 'to an office' fits at this size, so the greedy 3-word chunk stays intact
    assert ["to", "an", "office"] in [[w["text"] for w in c] for c in chunks]
    # 'robots are coming' is wider than the frame at this size (libass wraps it: measured 858 px
    # on a 1080 px frame with a 318 px tall multi-line block), so it can never come back as one chunk
    assert ["robots", "are", "coming"] not in [[w["text"] for w in c] for c in chunks]


def test_font_size_portrait_and_landscape_scale():
    from pipeline.render import font_size_landscape, font_size_portrait
    assert font_size_portrait() == pytest.approx(26 * 1920 / 288)  # 173.33
    assert font_size_portrait({"font_size_short": 30}) == pytest.approx(30 * 1920 / 288)
    assert font_size_landscape() == pytest.approx(20 * 1080 / 288)  # 75
    assert font_size_landscape({"font_size_long": 24}) == pytest.approx(24 * 1080 / 288)


def test_sfx_cues_and_track(tmp_path):
    from pipeline.sfx import cue_times, track
    segs = [{"query": "a", "start": 0, "end": 2}, {"card": "25,000 JOBS", "start": 2, "end": 4},
            {"query": "MAP: Iran | Hormuz", "start": 4, "end": 6}, {"query": "b", "start": 6, "end": 8}]
    assert cue_times(segs, "portrait") == [(2, "whoosh"), (2, "hit"), (4, "whoosh"), (4, "hit"), (6, "whoosh")]
    assert cue_times(segs, "landscape") == [(2, "whoosh"), (2, "hit"), (4, "whoosh"), (4, "hit")]  # long: graphics only
    out = track(segs, "portrait", 8.0, tmp_path / "sfx.wav")
    assert out.exists() and out.stat().st_size > 1000
    assert track([{"query": "a", "start": 0, "end": 2}], "landscape", 2.0, tmp_path / "none.wav") is None


def test_sfx_cue_times_counts_all_graphic_segments():
    """Every synthesised graphic segment gets a hit: chart/map/diagram/text types,
    the old card/graphic keys and the CARD/CHART/MAP/TIMELINE/SCALE/ORBIT/TEXT
    query prefixes; plain footage and PRESENTER shots do not (they are not graphics)."""
    from pipeline.sfx import cue_times
    segs = [{"query": "cargo ship at port", "start": 0, "end": 2},
            {"type": "chart", "query": "CHART: T | a=1", "start": 2, "end": 4},
            {"type": "diagram", "sub_kind": "timeline", "query": "TIMELINE: Voyager | 1977=Launch", "start": 4, "end": 6},
            {"type": "text", "query": "TEXT: one key line", "start": 6, "end": 8},
            {"type": "map", "query": "MAP: Iran | Hormuz", "start": 8, "end": 10},
            {"query": "SCALE: Earth vs Moon | a=1, b=2", "start": 10, "end": 12},   # prefix only, no type
            {"query": "ORBIT: Earth, Mars | transfer", "start": 12, "end": 14},     # prefix only
            {"card": "25,000 JOBS", "start": 14, "end": 16},                        # legacy key
            {"graphic": ("chart", "T | a=1"), "start": 16, "end": 18},              # legacy key
            {"type": "presenter", "presenter_text": "hi", "query": "PRESENTER: hi", "start": 18, "end": 20},
            {"query": "worker packing boxes", "start": 20, "end": 22}]
    cues = cue_times(segs, "landscape")
    hits = [t for t, kind in cues if kind == "hit"]
    assert hits == [2, 4, 6, 8, 10, 12, 14, 16]  # every graphic, not the presenter/footage shots
    assert all(t not in (0, 18, 20) for t, _ in cues)
    # Portrait: whoosh into every cut, including the plain footage segments.
    portrait = [(t, k) for t, k in cue_times(segs, "portrait") if k == "whoosh"]
    assert portrait == [(2, "whoosh"), (4, "whoosh"), (6, "whoosh"), (8, "whoosh"), (10, "whoosh"),
                        (12, "whoosh"), (14, "whoosh"), (16, "whoosh"), (18, "whoosh"), (20, "whoosh")]


# ---------- typed shot plan + Remotion engine switch (stage 2) ----------

def test_shot_type_per_prefix():
    from pipeline.render import shot_type
    assert shot_type("cargo ship at port") == "footage"
    assert shot_type("CARD: 25,000 JOBS") == "text"
    assert shot_type("TEXT: big idea") == "text"
    assert shot_type("CHART: T | a=1, b=2") == "chart"
    assert shot_type("MAP: Iran | Hormuz") == "map"
    assert shot_type("TIMELINE: Voyager | 1977=Launch") == "diagram"
    assert shot_type("SCALE: Earth vs Jupiter | a=1, b=2") == "diagram"
    assert shot_type("ORBIT: Earth, Mars | transfer") == "diagram"
    assert shot_type("PRESENTER: welcome back") == "presenter"
    assert shot_type("") == "footage"


def test_apply_shots_types_each_prefix():
    from pipeline.render import apply_shots
    segs = apply_shots([{"query": "q", "caption": "c"} for _ in range(8)],
                       ["plain query", "CARD: A BIG NUMBER", "CHART: T | a=1, b=2",
                        "MAP: Iran | Hormuz", "TIMELINE: Voyager | 1977=Launch, 2012=Exit",
                        "SCALE: Sizes | a=1, b=2", "ORBIT: Earth, Mars | transfer",
                        "PRESENTER: hi there"], "q")
    assert segs[0]["type"] == "footage" and segs[0]["query"] == "plain query"
    assert segs[1]["type"] == "text" and segs[1]["card"] == "A BIG NUMBER"
    assert segs[2]["type"] == "chart" and segs[2]["graphic"] == ("chart", "T | a=1, b=2")
    assert segs[3]["type"] == "map" and segs[3]["graphic"] == ("map", "Iran | Hormuz")
    assert segs[4]["type"] == "diagram" and segs[4]["sub_kind"] == "timeline"
    assert segs[4]["graphic"] == ("timeline", "Voyager | 1977=Launch, 2012=Exit")
    assert segs[5]["type"] == "diagram" and segs[5]["sub_kind"] == "scale"
    assert segs[6]["type"] == "diagram" and segs[6]["sub_kind"] == "orbit"
    assert segs[7]["type"] == "presenter" and segs[7]["presenter_text"] == "hi there"


def test_long_video_prefix_handling_types():
    """_fill_slot derives the same typed plan from a raw long-video query."""
    from pipeline.render import _typed_seg
    seg = _typed_seg({"query": "TIMELINE: Voyager | 1977=Launch, 2012=Exit", "caption": "c"}, "TIMELINE: Voyager | 1977=Launch, 2012=Exit")
    assert seg["type"] == "diagram" and seg["sub_kind"] == "timeline" and seg["graphic"][0] == "timeline"
    seg = _typed_seg({"query": "PRESENTER: hello", "caption": "c"}, "PRESENTER: hello")
    assert seg["type"] == "presenter" and seg["presenter_text"] == "hello"
    # old scripts: a plain query keeps the footage path
    assert _typed_seg({"query": "server room"}, "server room")["type"] == "footage"


def test_presenter_stub_text_card_and_footage_fallback(tmp_path):
    from pipeline.render import _presenter_slot
    footage = Mock()
    footage.clip.return_value = colour(tmp_path)
    out = _presenter_slot({"presenter_text": "WELCOME TO THE SHOW", "query": "news anchor studio",
                           "caption": "c"}, 0.2, "landscape", tmp_path / "p1.mp4", footage)
    assert out.exists() and out.with_suffix(".txt").read_text() == "WELCOME TO THE"  # 16-char wrap
    assert not footage.clip.called  # the text renders, not the stock query
    out = _presenter_slot({"type": "presenter", "query": "news anchor studio", "caption": "c"},
                          0.2, "landscape", tmp_path / "p2.mp4", footage)
    assert footage.clip.call_args.args[0] == "news anchor studio"  # no text: the query is the visual


def _motion_style(**extra):
    return {"accent": [34, 211, 238], "bg": [4, 7, 14], "motion": True, **extra}


class _FakeRemotion:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def available(self):
        return True

    def ensure_installed(self):
        return True

    def bundled_entry_point(self):
        return "out/bundle"

    def render_segment(self, kind, props, seconds, orientation, out, brand, entry_point=None):
        self.calls.append((kind, props, seconds, orientation, entry_point))
        if self.fail:
            raise RuntimeError("remotion exploded")
        Path(out).write_bytes(b"mp4")
        return Path(out)


def test_engine_off_uses_pillow(tmp_path, monkeypatch):
    import pipeline.remotion as R
    fake = _FakeRemotion()
    monkeypatch.setattr("pipeline.remotion.ensure_installed", fake.ensure_installed)
    monkeypatch.setattr("pipeline.remotion.render_segment", fake.render_segment)
    monkeypatch.setattr("pipeline.remotion.bundled_entry_point", fake.bundled_entry_point)
    monkeypatch.setattr(R, "available", lambda: True)
    footage = Mock()
    footage.clip.return_value = colour(tmp_path)
    seg = {"query": "q", "graphic": ("chart", "T | a=1, b=2"), "type": "chart", "caption": "c"}
    out = render._fill_slot(dict(seg), 0.3, "landscape", tmp_path / "off.mp4", footage,
                             {"accent": [34, 211, 238], "bg": [4, 7, 14]})  # motion not set
    assert not fake.calls and out.exists()


def test_engine_on_renders_with_remotion(tmp_path, monkeypatch):
    import pipeline.remotion as R
    fake = _FakeRemotion()
    monkeypatch.setattr("pipeline.remotion.ensure_installed", fake.ensure_installed)
    monkeypatch.setattr("pipeline.remotion.render_segment", fake.render_segment)
    monkeypatch.setattr("pipeline.remotion.bundled_entry_point", fake.bundled_entry_point)
    footage = Mock()
    for kind, spec, expected in (
        ("chart", "T | a=1, b=2", "chart"),
        ("map", "Iran, Oman | Hormuz", "map"),
        ("timeline", "Voyager | 1977=Launch, 2012=Interstellar", "timeline"),
        ("scale", "Sizes | Earth=1, Jupiter=11", "scale"),
        ("orbit", "Earth, Mars | Transfer", "orbit"),
        ("text", "A BIG NUMBER", "text"),
    ):
        seg = {"query": "q", "caption": "c", "type": "diagram" if kind in ("timeline", "scale", "orbit") else kind}
        if kind == "text":
            seg["card"] = spec
        else:
            seg["graphic"] = (kind, spec)
        if kind in ("timeline", "scale", "orbit"):
            seg["sub_kind"] = kind
        out = tmp_path / f"on-{kind}.mp4"
        render._fill_slot(seg, 0.5, "portrait", out, footage, _motion_style())
        assert out.exists()
    kinds = [c[0] for c in fake.calls]
    assert kinds == ["chart", "map", "timeline", "scale", "orbit", "text"]
    # spec parsing reached the compositions as structured props
    assert fake.calls[0][1]["items"][0]["label"] == "a"
    assert fake.calls[1][1]["countries"] == ["Iran", "Oman"]
    assert fake.calls[2][1]["events"] == [{"when": "1977", "label": "Launch"},
                                          {"when": "2012", "label": "Interstellar"}]
    assert fake.calls[4][1]["bodies"] == ["Earth", "Mars"]
    assert fake.calls[5][1]["text"] == "A BIG NUMBER"
    assert all(c[3] == "portrait" for c in fake.calls)
    assert all(c[4] == "out/bundle" for c in fake.calls)
    assert not footage.clip.called


def test_engine_failure_falls_back_to_pillow(tmp_path, monkeypatch, caplog):
    import pipeline.remotion as R
    fake = _FakeRemotion(fail=True)
    monkeypatch.setattr("pipeline.remotion.ensure_installed", fake.ensure_installed)
    monkeypatch.setattr("pipeline.remotion.render_segment", fake.render_segment)
    monkeypatch.setattr("pipeline.remotion.bundled_entry_point", fake.bundled_entry_point)
    caplog.set_level("WARNING")
    footage = Mock()
    seg = {"query": "q", "caption": "c", "type": "chart", "graphic": ("chart", "T | a=1, b=2")}
    out = render._fill_slot(seg, 0.5, "landscape", tmp_path / "fail.mp4", footage, _motion_style())
    assert fake.calls and out.exists()  # Pillow chart still rendered
    assert "fell back to Pillow" in caplog.text
    # a diagram failure falls back to a text card of the title
    seg = {"query": "q", "caption": "c", "type": "diagram", "sub_kind": "timeline",
           "graphic": ("timeline", "Voyager | 1977=Launch")}
    out = render._fill_slot(seg, 0.5, "landscape", tmp_path / "fail2.mp4", footage, _motion_style())
    assert out.with_suffix(".txt").read_text() == "VOYAGER"


def test_engine_unavailable_uses_pillow_diagram_card(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.remotion.ensure_installed", lambda: False)
    monkeypatch.setattr("pipeline.remotion.render_segment",
                        lambda *a, **k: pytest.fail("render_segment must not run"))
    footage = Mock()
    seg = {"query": "q", "caption": "c", "type": "diagram", "sub_kind": "timeline",
           "graphic": ("timeline", "Voyager | 1977=Launch, 2012=Exit")}
    out = render._fill_slot(seg, 0.5, "landscape", tmp_path / "noengine.mp4", footage, _motion_style())
    assert out.exists() and out.with_suffix(".txt").read_text() == "VOYAGER"  # title text card


def test_remotion_specs_that_do_not_parse_fall_back(tmp_path, monkeypatch):
    import pipeline.remotion as R
    fake = _FakeRemotion()
    monkeypatch.setattr("pipeline.remotion.ensure_installed", lambda: True)
    monkeypatch.setattr("pipeline.remotion.render_segment", fake.render_segment)
    monkeypatch.setattr("pipeline.remotion.bundled_entry_point", fake.bundled_entry_point)
    monkeypatch.setattr(R, "available", lambda: True)
    footage = Mock()
    # a chart with no numbers and a timeline with no events cannot be parsed
    seg = {"query": "q", "caption": "c", "type": "chart", "graphic": ("chart", "no numbers here")}
    out = render._fill_slot(seg, 0.5, "landscape", tmp_path / "unparsable.mp4", footage, _motion_style())
    assert out.exists() and not fake.calls  # Pillow path, no remotion attempt past parsing
    seg = {"query": "q", "caption": "c", "type": "diagram", "sub_kind": "timeline",
           "graphic": ("timeline", "only one | 1977=Launch")}
    out = render._fill_slot(seg, 0.5, "landscape", tmp_path / "shorttl.mp4", footage, _motion_style())
    assert out.exists()
