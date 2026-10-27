"""Vertical Shorts/Reels cut from the long video's extra scripts (same TTS voice, bigger captions)."""
from __future__ import annotations

from pathlib import Path

from .common import log
from .footage import Footage
from .render import render, segments_from_timings
from .tts import synthesize


def make_short(short: dict, out_dir: Path, voice: str, footage: Footage, name: str) -> dict:
    paragraphs = [p.strip() for p in short["script"].replace("\n\n", "\n").split("\n") if p.strip()]
    if len(paragraphs) == 1:
        # split into sentence groups for shot variety
        import re
        sents = re.split(r"(?<=[.!?])\s+", paragraphs[0])
        paragraphs = [" ".join(sents[i:i + 2]) for i in range(0, len(sents), 2)]
    tts = synthesize(paragraphs, out_dir, voice=voice, name=f"{name}_voice")
    shots = [{"paragraph_index": i, "query": short["query"], "mood": "bright"} for i in range(len(paragraphs))]
    segs = segments_from_timings(tts["timings"], shots, min_shot=3.0, max_shot=5.0)
    out = out_dir / f"{name}.mp4"
    render(segs, tts["audio"], tts["srt"], out, orientation="portrait", footage=footage, music_db=-20.0)
    log.info("short: %s (%.1fs)", out, tts["duration"])
    return {"file": out, "duration": tts["duration"], "title": short["hook_title"], "script": short["script"]}
