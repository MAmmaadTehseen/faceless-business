"""Synthesised sound design: a short whoosh into cuts and a low hit under stat cards, charts and maps.

Growth log 2026-11-24: videos had narration and music only. Cut sounds are a standard pattern
interrupt; they are synthesised here (filtered noise and a decaying sine), so there is no sample
library and no licence question. Mixed well under the narration.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

RATE = 44100


def whoosh(seconds: float = 0.42, seed: int = 0) -> np.ndarray:
    """Noise swept from dark to bright and back, swelling into the cut."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    noise = rng.standard_normal(n)
    t = np.linspace(0, 1, n)
    # One-pole low-pass with a cutoff that rises to the cut point and falls after it.
    cutoff = 300 + 5200 * np.sin(np.pi * t) ** 2
    alpha = 1 - np.exp(-2 * np.pi * cutoff / RATE)
    out = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc += alpha[i] * (noise[i] - acc)
        out[i] = acc
    env = np.sin(np.pi * t) ** 2
    out *= env
    return out / (np.abs(out).max() or 1)


def hit(seconds: float = 0.45) -> np.ndarray:
    """Low thump: a 55 Hz sine dropping in pitch with a fast decay, plus a soft click."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    freq = 70 * np.exp(-t * 3) + 45
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    body = np.sin(phase) * np.exp(-t * 9)
    click = np.random.default_rng(1).standard_normal(n) * np.exp(-t * 300) * 0.3
    out = body + click
    return out / (np.abs(out).max() or 1)


def cue_times(segments: list[dict], orientation: str) -> list[tuple[float, str]]:
    """(time, kind) cues: a hit at every card/chart/map start; whooshes at every cut in Shorts,
    only into graphics in long videos (a whoosh every 5 s for ten minutes would tire)."""
    cues = []
    t = 0.0
    for i, seg in enumerate(segments):
        graphic = bool(seg.get("card") or seg.get("graphic") or
                       (seg.get("query") or "").split(":", 1)[0].strip().upper() in ("CARD", "CHART", "MAP"))
        if i > 0 and (orientation == "portrait" or graphic):
            cues.append((t, "whoosh"))
        if graphic:
            cues.append((t, "hit"))
        t += max(seg["end"] - seg["start"], 1.0)
    return cues


def track(segments: list[dict], orientation: str, total: float, out: Path) -> Path | None:
    """Write the cue track as a WAV the renderer mixes under the narration, or None if no cues."""
    cues = cue_times(segments, orientation)
    if not cues:
        return None
    buf = np.zeros(int((total + 1) * RATE))
    sounds = {"whoosh": whoosh() * 0.55, "hit": hit() * 0.8}
    for k, (at, kind) in enumerate(cues):
        snd = whoosh(seed=k) * 0.55 if kind == "whoosh" else sounds["hit"]
        # The whoosh peaks on the cut; the hit lands on it.
        start = int((at - (len(snd) / RATE / 2 if kind == "whoosh" else 0)) * RATE)
        start = max(0, start)
        end = min(len(buf), start + len(snd))
        buf[start:end] += snd[: end - start]
    peak = np.abs(buf).max() or 1
    import soundfile as sf
    sf.write(out, (buf / peak * 0.9).astype(np.float32), RATE)
    return out
