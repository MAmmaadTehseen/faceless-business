"""Narration with edge-tts (free). Produces mp3 + word timings + per-paragraph timings + SRT/ASS captions."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import edge_tts

from .common import log

DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"


def _spoken(text: str) -> str:
    # edge-tts reads symbols oddly; soften a few.
    return text.replace("%", " percent").replace("&", " and ").replace("—", ", ").replace("–", ", ")


async def _synth(text: str, voice: str, out_mp3: Path, rate: str = "+4%") -> list[dict]:
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offsets are in 100-nanosecond units
                words.append({"text": chunk["text"], "start": chunk["offset"] / 1e7, "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    return words


_KOKORO = {}


def _kokoro_available() -> bool:
    try:
        import kokoro  # noqa: F401
        return True
    except Exception:
        return False


def _kokoro_synth(text: str, voice: str, out_mp3: Path, speed: float = 1.0) -> list[dict]:
    """Offline Kokoro-82M. Returns word timings like the edge path."""
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    lang = "b" if voice.startswith(("bm_", "bf_")) else "a"
    if lang not in _KOKORO:
        _KOKORO[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    pipe = _KOKORO[lang]
    chunks, words, offset = [], [], 0.0
    for res in pipe(text, voice=voice, speed=speed, split_pattern=r"\n+"):
        audio = res.audio.numpy() if hasattr(res.audio, "numpy") else np.asarray(res.audio)
        for t in (res.tokens or []):
            if t.start_ts is None or t.end_ts is None or not t.text.strip():
                continue
            words.append({"text": t.text, "start": offset + float(t.start_ts), "end": offset + float(t.end_ts)})
        chunks.append(audio)
        offset += len(audio) / 24000
    wav = out_mp3.with_suffix(".wav")
    sf.write(wav, np.concatenate(chunks) if chunks else np.zeros(2400), 24000)
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "2", str(out_mp3)], check=True)
    wav.unlink(missing_ok=True)
    return words


def backend() -> str:
    """TTS_BACKEND=kokoro|edge|auto. Auto prefers kokoro (works on CI; edge is blocked from datacenter IPs)."""
    b = os.getenv("TTS_BACKEND", "auto")
    if b == "auto":
        return "kokoro" if _kokoro_available() else "edge"
    return b


def synthesize(paragraphs: list[str], out_dir: Path, voice=DEFAULT_VOICE, name: str = "voice") -> dict:
    """Synthesize paragraph by paragraph so we get exact paragraph boundaries, then concat.
    `voice` is either an edge voice name (str) or a channel voice dict {kokoro, edge, rate}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    be = backend()
    if isinstance(voice, dict):
        v_edge, v_kok, rate = voice.get("edge", DEFAULT_VOICE), voice.get("kokoro", "am_michael"), voice.get("rate", "+0%")
    else:
        v_edge, v_kok, rate = voice, "am_michael", "+4%"
    speed = 1.0 + int(rate.replace("%", "").replace("+", "") or 0) / 100.0
    parts, timings, offset = [], [], 0.0
    gap = 0.35  # seconds of silence between paragraphs
    for i, para in enumerate(paragraphs):
        mp3 = out_dir / f"{name}_{i:03d}.mp3"
        if be == "kokoro":
            words = _kokoro_synth(_spoken(para), v_kok, mp3, speed)
        else:
            words = asyncio.run(_synth(_spoken(para), v_edge, mp3, rate))
        dur = _mp3_duration(mp3)
        if not words:
            raise RuntimeError("edge-tts returned no word boundaries; check network or voice name")
        _restore_punctuation(words, para)
        for w in words:
            w["start"] += offset
            w["end"] += offset
        timings.append({"index": i, "start": offset, "end": offset + dur, "words": words})
        parts.append(mp3)
        offset += dur + gap
    final = out_dir / f"{name}.mp3"
    _concat_with_gaps(parts, final, gap)
    total = _mp3_duration(final)
    all_words = [w for t in timings for w in t["words"]]
    srt = out_dir / f"{name}.srt"
    srt.write_text(words_to_srt(all_words))
    (out_dir / f"{name}_timings.json").write_text(json.dumps(timings))
    log.info("tts[%s]: %d paragraphs, %.1fs, %d words", be, len(paragraphs), total, len(all_words))
    return {"audio": final, "srt": srt, "timings": timings, "duration": total, "words": all_words}


def _restore_punctuation(words: list[dict], original: str) -> None:
    """edge-tts word boundaries drop punctuation and expand numbers ("2025" -> three boundaries).
    Map boundaries back onto the original tokens in order; boundaries that belong to one original
    token (numbers, symbols) are merged into it, keeping the first start and the last end."""
    tokens = original.split()

    def norm(t: str) -> str:
        return re.sub(r"[^a-z0-9]", "", t.lower())

    def match(b: str, t: str) -> bool:
        b, t = norm(b), norm(t)
        return bool(b) and bool(t) and (t.startswith(b[:4]) or b.startswith(t[:4]))

    merged: list[dict] = []
    ti = 0
    for w in words:
        if ti < len(tokens) and match(w["text"], tokens[ti]):
            merged.append({"text": tokens[ti], "start": w["start"], "end": w["end"]})
            ti += 1
        elif ti + 1 < len(tokens) and match(w["text"], tokens[ti + 1]):
            # boundary skipped a token (rare); emit the skipped token with this timing, then this one
            merged.append({"text": tokens[ti], "start": w["start"], "end": w["start"]})
            merged.append({"text": tokens[ti + 1], "start": w["start"], "end": w["end"]})
            ti += 2
        elif merged and ti < len(tokens) and not re.search(r"[a-z]", norm(tokens[ti])) :
            # current token is a number/symbol being spoken as several words: start it, then absorb
            merged.append({"text": tokens[ti], "start": w["start"], "end": w["end"]})
            ti += 1
        elif merged:
            # extra spoken word for the previous token (e.g. "sixty thousand" for "60,000"): extend it
            merged[-1]["end"] = w["end"]
        else:
            merged.append({"text": w["text"], "start": w["start"], "end": w["end"]})
    words[:] = merged


def _mp3_duration(path: Path) -> float:
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def _concat_with_gaps(parts: list[Path], out: Path, gap: float) -> None:
    import subprocess
    # Decode each part to wav, add silence, concat, encode once.
    inputs, filters = [], []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        filters.append(f"[{i}:a]aresample=44100,apad=pad_dur={gap}[a{i}]")
    chain = "".join(f"[a{i}]" for i in range(len(parts)))
    fc = ";".join(filters) + f";{chain}concat=n={len(parts)}:v=0:a=1[out]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(out)], check=True)


def _ts(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def words_to_srt(words: list[dict], max_words: int = 5, max_dur: float = 2.5) -> str:
    """Short caption chunks (3-5 words) that read well on screen."""
    out, i, n = [], 0, 1
    while i < len(words):
        chunk = [words[i]]
        j = i + 1
        while j < len(words) and len(chunk) < max_words and words[j]["end"] - chunk[0]["start"] <= max_dur:
            chunk.append(words[j])
            if re.search(r"[.!?]$", words[j]["text"]):
                j += 1
                break
            j += 1
        text = " ".join(w["text"] for w in chunk)
        end = chunk[-1]["end"]
        if j < len(words):
            end = min(end + 0.15, words[j]["start"])
        out.append(f"{n}\n{_ts(chunk[0]['start'])} --> {_ts(end)}\n{text}\n")
        n += 1
        i = j
    return "\n".join(out)
