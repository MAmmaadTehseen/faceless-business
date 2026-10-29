"""Assemble narration + footage + burned captions + music into the final video with ffmpeg."""
from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

from .common import ASSETS_DIR, log
from .footage import Footage

FONT_DIR = ASSETS_DIR / "fonts"


def _font() -> str | None:
    for p in sorted(FONT_DIR.glob("*.ttf")) + sorted(FONT_DIR.glob("*.otf")):
        return str(p)
    return None


def _music() -> Path | None:
    tracks = sorted((ASSETS_DIR / "music").glob("*.mp3"))
    return random.choice(tracks) if tracks else None


def _caption_style(orientation: str, style: dict | None = None) -> str:
    style = style or {}
    font = _font()
    fontname = Path(font).stem if font else "DejaVu Sans"
    colour = style.get("caption_colour", "&H00FFFFFF"); outline = style.get("caption_outline", "&H80000000")
    if orientation == "landscape":
        return f"FontName={fontname},FontSize={style.get('font_size_long', 20)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=48"
    return f"FontName={fontname},FontSize={style.get('font_size_short', 26)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=110"


def _fit_clip(src: Path, sec: float, orientation: str, out: Path) -> Path:
    """Trim/loop a source clip to exactly `sec`, scaled and cropped to the frame, no audio."""
    w, h = (1920, 1080) if orientation == "landscape" else (1080, 1920)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,format=yuv420p"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{sec:.3f}", "-vf", vf, "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)], check=True)
    return out


def render(segments: list[dict], audio: Path, srt: Path, out: Path, orientation: str = "landscape",
           footage: Footage | None = None, music_db: float = -22.0, style: dict | None = None) -> Path:
    """segments: [{query, mood, start, end}] in order, covering the narration."""
    footage = footage or Footage()
    work = out.parent / f"{out.stem}_work"
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, seg in enumerate(segments):
        sec = max(seg["end"] - seg["start"], 1.0)
        src = footage.clip(seg["query"], sec, orientation, seg.get("mood", "calm"))
        parts.append(_fit_clip(src, sec, orientation, work / f"seg_{i:03d}.mp4"))
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    visual = work / "visual.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(visual)], check=True)

    # clean frame (no captions) for the thumbnail
    total = sum(max(sg["end"] - sg["start"], 1.0) for sg in segments)
    for i, frac in enumerate((0.08, 0.2, 0.35, 0.5, 0.65, 0.8)):
        clean = out.with_suffix(f".clean{i}.jpg") if i else out.with_suffix(".clean.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(1.0, total * frac):.2f}", "-i", str(visual), "-frames:v", "1", "-q:v", "2", str(clean)], check=True)

    srt_path = str(srt.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fontsdir = f":fontsdir={FONT_DIR}" if _font() else ""
    vf = f"subtitles='{srt_path}':force_style='{_caption_style(orientation, style)}'{fontsdir}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(visual), "-i", str(audio)]
    music = _music()
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        fc = f"[2:a]volume={music_db}dB[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-vf", vf, "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(work, ignore_errors=True)
    log.info("render: %s", out)
    return out


def segments_from_timings(timings: list[dict], shot_list: list[dict], min_shot: float = 5.0, max_shot: float = 9.0) -> list[dict]:
    """Turn paragraph timings + one query per paragraph into shots no longer than max_shot seconds."""
    q_by_idx = {s["paragraph_index"]: s for s in shot_list}
    segs = []
    for t in timings:
        s = q_by_idx.get(t["index"]) or (shot_list[t["index"] % len(shot_list)] if shot_list else {"query": "abstract technology", "mood": "calm"})
        start, end = t["start"], t["end"]
        # include the inter-paragraph gap in the last shot
        n = max(1, round((end - start) / ((min_shot + max_shot) / 2)))
        step = (end - start) / n
        for k in range(n):
            segs.append({"query": s["query"], "mood": s.get("mood", "calm"), "start": start + k * step, "end": start + (k + 1) * step})
    # close gaps so shots are contiguous
    for a, b in zip(segs, segs[1:]):
        a["end"] = b["start"]
    return segs
