"""Playbook items 10/25/28 (answer-first article prompt) and 34 (slower hook line A/B)."""
import json
from pathlib import Path

import pipeline.tts as tts


def test_rate_to_speed():
    assert tts.rate_to_speed("+4%") == 1.04
    assert abs(tts.rate_to_speed("-6%") - 0.94) < 1e-9
    assert tts.rate_to_speed("") == 1.0


def test_hook_rate_slows_only_the_first_paragraph(monkeypatch, tmp_path):
    speeds = []
    monkeypatch.setattr(tts, "backend", lambda: "kokoro")

    def fake(text, voice, mp3, speed):
        speeds.append(round(speed, 2))
        Path(mp3).write_bytes(b"")
        return [{"text": w, "start": 0.0, "end": 0.1} for w in text.split()]

    monkeypatch.setattr(tts, "_kokoro_synth", fake)
    monkeypatch.setattr(tts, "_mp3_duration", lambda p: 1.0)
    monkeypatch.setattr(tts, "_concat", lambda *a, **k: None, raising=False)
    try:
        tts.synthesize(["Hook line here.", "Body one.", "Body two."], tmp_path,
                       voice={"kokoro": "af_heart", "rate": "+2%", "hook_rate": "-6%"})
    except Exception:
        pass  # concatenation/srt details are not under test; the per-paragraph speeds are
    assert speeds[:3] == [0.94, 1.02, 1.02]


def test_escapevelocity_carries_the_ab_and_others_do_not():
    for key in ("futurework", "tradewinds", "escapevelocity"):
        voice = json.loads(Path(f"channels/{key}/channel.json").read_text())["voice"]
        assert ("hook_rate" in voice) == (key == "escapevelocity")


def test_article_prompt_is_answer_first():
    src = Path("pipeline/article.py").read_text()
    assert "Answer-first structure" in src and "40-60 word" in src and "sub-questions" in src


def test_opening_has_viewer_stake():
    from pipeline.script import opening_has_viewer_stake
    assert opening_has_viewer_stake(["The price on your screen may not be the price on your neighbor's screen."])
    assert not opening_has_viewer_stake(["The Dutch government just put a number on the desk jobs it no longer needs. Twenty-five thousand."])
    # "you" after the 45-word window does not count
    assert not opening_has_viewer_stake([" ".join(["word"] * 50) + " you"])


def test_motion_hint_follows_the_style_flag():
    """motion_hint is empty unless style.motion is set, and names the diagram shot formats."""
    from types import SimpleNamespace

    from pipeline.script import motion_hint, nasa_hint

    def claude(motion):
        return SimpleNamespace(channel=SimpleNamespace(
            key="escapevelocity", footage={"nasa": False}, style={"motion": motion} if motion is not None else {}))

    assert motion_hint(claude(None)) == ""
    assert motion_hint(claude(False)) == ""
    hint = motion_hint(claude(True))
    for needle in ("TIMELINE: title | 1977=Launch, 1979=Jupiter",
                   "SCALE: title | label=value, label=value",
                   "ORBIT: Body, Body | label",
                   "TEXT: <key line, max 8 words>",
                   "at most four", "one paragraph in four", "facts the script states"):
        assert needle in hint, needle
    # The hint is wired next to nasa_hint in both prompts.
    src = Path("pipeline/script.py").read_text()
    assert "f\"{motion_hint(claude)}\"" in src and "f\"{nasa_hint(claude)}\"" in src
    daily = Path("pipeline/shorts_daily.py").read_text()
    assert "motion_hint(claude)" in daily and "nasa_hint(claude)" in daily
