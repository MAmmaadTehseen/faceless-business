"""Multilingual narration for the words channel: Kokoro (per language code), Piper (ONNX) or edge-tts.

Every segment is one voice saying one text. Segments are synthesized separately, then joined with
short gaps so the renderer gets exact segment boundaries. English narrator segments keep Kokoro
word timings for word-by-word captions; native-language segments carry one caption for the whole
segment because Kokoro's non-English G2P and Piper return no word timestamps.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

from .common import DATA_DIR, log
from .tts import (_concat_with_gaps, _mp3_duration, _restore_punctuation, _spoken, backend,
                  words_to_srt, _ts)

PIPER_DIR = Path(os.getenv("PIPER_VOICES_DIR", DATA_DIR / "piper"))
_KOKORO: dict[str, object] = {}
_PIPER: dict[str, object] = {}


def narrator_spec(channel_voice: dict) -> dict:
    """The English narrator uses the channel voice like every other channel."""
    return {"backend": "kokoro", "lang": "a", "voice": channel_voice.get("kokoro", "af_bella"),
            "edge": channel_voice.get("edge", "en-US-AvaNeural"), "rate": channel_voice.get("rate", "+0%")}


def _speed(spec: dict) -> float:
    return 1.0 + int(str(spec.get("rate", "+0%")).replace("%", "").replace("+", "") or 0) / 100.0


def _japanese_dictionary() -> None:
    """misaki[ja] imports `unidic.DICDIR`; let the small unidic-lite dictionary stand in for the 1 GB one."""
    import sys
    import types
    try:
        import unidic  # noqa: F401
        if hasattr(unidic, "DICDIR") and Path(unidic.DICDIR).is_dir():
            return
    except ImportError:
        pass
    import unidic_lite
    shim = types.ModuleType("unidic")
    shim.DICDIR = unidic_lite.DICDIR
    sys.modules["unidic"] = shim


def _kokoro(text: str, spec: dict, out_mp3: Path) -> list[dict]:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    lang = spec.get("lang", "a")
    if lang == "j" and lang not in _KOKORO:
        _japanese_dictionary()
    if lang not in _KOKORO:
        _KOKORO[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    chunks, words, offset = [], [], 0.0
    for res in _KOKORO[lang](text, voice=spec["voice"], speed=_speed(spec), split_pattern=r"\n+"):
        audio = res.audio.numpy() if hasattr(res.audio, "numpy") else np.asarray(res.audio)
        for t in (res.tokens or []):
            if t.start_ts is None or t.end_ts is None or not t.text.strip():
                continue
            words.append({"text": t.text, "start": offset + float(t.start_ts), "end": offset + float(t.end_ts)})
        chunks.append(audio)
        offset += len(audio) / 24000
    if not chunks or sum(len(c) for c in chunks) < 2400:
        raise RuntimeError(f"kokoro produced no audio for lang {lang!r}")
    _write_mp3(np.concatenate(chunks), 24000, out_mp3)
    return words


def piper_voice(name: str):
    """Load (and download once) a Piper voice. Voices are cached under data/piper."""
    if name not in _PIPER:
        from piper import PiperVoice
        PIPER_DIR.mkdir(parents=True, exist_ok=True)
        model = PIPER_DIR / f"{name}.onnx"
        if not model.is_file() or not model.with_suffix(".onnx.json").is_file():
            from piper.download_voices import download_voice
            log.info("piper: downloading voice %s", name)
            download_voice(name, PIPER_DIR)
        _PIPER[name] = PiperVoice.load(model)
    return _PIPER[name]


def _piper(text: str, spec: dict, out_mp3: Path) -> list[dict]:
    import numpy as np
    from piper import SynthesisConfig
    voice = piper_voice(spec["voice"])
    cfg = SynthesisConfig(speaker_id=spec.get("speaker"), length_scale=spec.get("length_scale", 1.1))
    pieces = [np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16) for chunk in voice.synthesize(text, syn_config=cfg)]
    if not pieces:
        raise RuntimeError(f"piper produced no audio for {spec['voice']}")
    audio = np.concatenate(pieces).astype(np.float32) / 32768.0
    _write_mp3(audio, voice.config.sample_rate, out_mp3)
    return []


def _edge(text: str, spec: dict, out_mp3: Path) -> list[dict]:
    from .tts import _synth
    return asyncio.run(_synth(text, spec["edge"], out_mp3, spec.get("rate", "+0%")))


def _write_mp3(audio, rate: int, out_mp3: Path) -> None:
    import soundfile as sf
    wav = out_mp3.with_suffix(".wav")
    sf.write(wav, audio, rate)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "2", str(out_mp3)], check=True)
    wav.unlink(missing_ok=True)


def synth_one(text: str, spec: dict, out_mp3: Path) -> list[dict]:
    """Synthesize one segment with the backend the spec asks for, honouring TTS_BACKEND=edge locally."""
    be = backend()
    if be == "edge":
        if not spec.get("edge"):
            raise RuntimeError("edge-tts voice missing for this language")
        return _edge(_spoken(text), spec, out_mp3)
    kind = spec.get("backend", "kokoro")
    try:
        if kind == "piper":
            return _piper(text, spec, out_mp3)
        return _kokoro(_spoken(text), spec, out_mp3)
    except Exception as exc:
        fallback = spec.get("fallback")
        if not fallback:
            raise
        log.warning("tts %s/%s failed (%s); using fallback %s", kind, spec.get("voice"), type(exc).__name__, fallback.get("voice"))
        return synth_one(text, {**fallback, "edge": spec.get("edge")}, out_mp3)


def synthesize_segments(segments: list[dict], out_dir: Path, name: str, gap: float = 0.45) -> dict:
    """segments: [{text, spec, caption, kind:"narrator"|"native", card}] -> joined mp3, SRT, timings.

    Returned timings mirror tts.synthesize: one entry per segment with absolute start/end and any
    word timings, plus the original segment dict under "segment" for the renderer.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    parts, timings, offset = [], [], 0.0
    for i, seg in enumerate(segments):
        mp3 = out_dir / f"{name}_{i:03d}.mp3"
        words = synth_one(seg["text"], seg["spec"], mp3)
        dur = _mp3_duration(mp3)
        if dur < 0.2:
            raise RuntimeError(f"segment {i} produced {dur:.2f}s of audio")
        if words:
            _restore_punctuation(words, seg["text"])
            for w in words:
                w["start"] += offset
                w["end"] += offset
        timings.append({"index": i, "start": offset, "end": offset + dur, "words": words, "segment": seg})
        parts.append(mp3)
        offset += dur + gap
    final = out_dir / f"{name}.mp3"
    _concat_with_gaps(parts, final, gap)
    total = _mp3_duration(final)
    srt = out_dir / f"{name}.srt"
    srt.write_text(segments_to_srt(timings))
    (out_dir / f"{name}_timings.json").write_text(json.dumps(
        [{k: v for k, v in t.items() if k != "segment"} for t in timings]))
    log.info("tts[words]: %d segments, %.1fs", len(segments), total)
    return {"audio": final, "srt": srt, "timings": timings, "duration": total}


def segments_to_srt(timings: list[dict]) -> str:
    """Narrator segments get word-chunk captions; other segments one caption each (Latin text only)."""
    cues = []
    for t in timings:
        seg = t["segment"]
        if t["words"] and seg.get("kind") == "narrator":
            block = words_to_srt(t["words"])
            cues.extend(c for c in block.strip().split("\n\n") if c.strip())
            continue
        text = seg.get("caption") or seg["text"]
        cues.append(f"0\n{_ts(t['start'])} --> {_ts(t['end'])}\n{text}")
    out = []
    for n, cue in enumerate(cues, 1):
        lines = cue.strip().split("\n")
        out.append("\n".join([str(n), *lines[1:]]) + "\n")
    return "\n".join(out)
