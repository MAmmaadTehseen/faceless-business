"""Assemble narration + footage + burned captions + music into the final video with ffmpeg."""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
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
    return tracks[0] if tracks else None


def _caption_style(orientation: str, style: dict | None = None) -> str:
    style = style or {}
    font = _font()
    fontname = Path(font).stem if font else "DejaVu Sans"
    colour = style.get("caption_colour", "&H00FFFFFF"); outline = style.get("caption_outline", "&H80000000")
    if orientation == "landscape":
        return f"FontName={fontname},FontSize={style.get('font_size_long', 20)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=48"
    return f"FontName={fontname},FontSize={style.get('font_size_short', 26)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=110"


def _dims(orientation: str) -> tuple[int, int]:
    return (1920, 1080) if orientation == "landscape" else (1080, 1920)


def _fit_clip(src: Path, sec: float, orientation: str, out: Path) -> Path:
    """Strip black first, then loop usable footage; clone at most half a second."""
    from .qa import probe
    w, h = _dims(orientation)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        clean = Path(temp) / "clean.mp4"
        vf = (f"fps=30,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              "blackframe=amount=0:threshold=38,"
              "metadata=mode=select:key=lavfi.blackframe.pblack:value=97:function=less,"
              "setpts=N/(30*TB),format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-t", f"{sec:.6f}",
                        "-i", str(src), "-vf", vf, "-an", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "20", str(clean)],
                       check=True, capture_output=True, timeout=max(60, sec*20))
        duration = probe(clean)["duration"]
        if duration <= 0:
            raise ValueError(f"source has no usable frames: {src}")
        loop = duration >= 2 and duration < sec - 1/30
        padding = min(max(0, sec - duration), 14/30) if sec - duration <= 0.5 else 0
        target = sec if loop else min(sec, duration + padding)
        if loop:
            log.info("render slot %s: looping %.3fs cleaned clip to %.3fs", out.name, duration, sec)
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if loop:
            cmd += ["-stream_loop", "-1"]
        cmd += ["-i", str(clean), "-vf", f"tpad=stop_mode=clone:stop_duration={padding:.6f}",
                "-t", f"{target:.6f}", "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "20", str(out)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=max(60, sec*20))
    return out


def _background_card(text: str, sec: float, orientation: str, out: Path,
                     style: dict | None = None) -> Path:
    """Encode a branded card in the same single command as a normal slot."""
    style = style or {}
    w, h = _dims(orientation)
    accent = "0x" + "".join(f"{int(c):02x}" for c in style.get("accent", (251, 191, 36)))
    # Keep the card visibly nonblack even with the channel's very dark background.
    bg = "0x" + "".join(f"{max(32, int(c)):02x}" for c in style.get("bg", (32, 32, 40)))
    import textwrap
    label = out.with_suffix(".txt")
    label.write_text("\n".join(textwrap.wrap(text, width=48 if w > h else 27)), encoding="utf-8")
    label_path = str(label.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    vf = (f"drawbox=x=0:y=0:w=iw:h={max(8, h//60)}:color={accent}:t=fill,"
          f"drawtext=textfile='{label_path}':expansion=none:fontcolor=white:"
          f"fontsize={max(8, h//24)}:x=(w-text_w)/2:y=(h-text_h)/2,"
          f"zoompan=z='1+0.025*on/30':d=1:x='iw/2-iw/zoom/2':"
          f"y='ih/2-ih/zoom/2':s={w}x{h}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c={bg}:s={w}x{h}:r=30", "-vf", vf,
                    "-frames:v", str(max(1, math.ceil(sec*30))), "-an", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", str(out)], check=True)
    return out


def _fill_slot(seg: dict, sec: float, orientation: str, out: Path,
               footage: Footage, style: dict | None = None) -> Path:
    from .qa import probe
    alternatives = seg.get("candidate_queries") or [" ".join(seg["query"].split()[:2])]
    queries = list(dict.fromkeys([seg["query"], *alternatives]))
    if seg.get("_retry"):
        queries = queries[1:] + queries[:1]
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        parts = []
        remaining = sec
        for query in queries:
            try:
                src = footage.clip(query, remaining, orientation, seg.get("mood", "calm"))
                if src is None:
                    continue
                log.info("render slot %s: query=%r source=%s", out.name, query, src)
                part = _fit_clip(Path(src), remaining, orientation, Path(temp) / f"part{len(parts)}.mp4")
                parts.append(part)
                remaining -= probe(part)["duration"]
                if remaining <= 1/30:
                    break
                log.info("render slot %s: short source, concatenating next candidate (%.3fs left)", out.name, remaining)
            except Exception as exc:
                log.warning("render slot %s query %r failed: %s", out.name, query, exc)
        if remaining > 1/30:
            log.warning("render slot %s: using moving branded caption card", out.name)
            card = _background_card(seg.get("caption") or seg.get("text") or seg["query"],
                                    remaining, orientation, out, style)
            saved = Path(temp) / "card.mp4"
            shutil.copyfile(card, saved)
            parts.append(saved)
        if len(parts) == 1:
            shutil.copyfile(parts[0], out)
        else:
            listing = Path(temp) / "parts.txt"
            listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                            "-i", str(listing), "-t", str(sec), "-c", "copy", str(out)],
                           check=True, timeout=max(60, sec*10))
    return out


def _check_black(video: Path) -> None:
    from .qa import black_segments
    try:
        for start, end in black_segments(video):
            log.warning("render self-check: black segment %.3f-%.3fs (%.3fs)", start, end, end-start)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        log.warning("render self-check unavailable: %s", exc)


def _render(segments: list[dict], audio: Path, srt: Path, out: Path, orientation: str = "landscape",
           footage: Footage | None = None, music_db: float = -22.0, style: dict | None = None) -> Path:
    """segments: [{query, mood, start, end}] in order, covering the narration."""
    footage = footage or Footage()
    work = out.parent / f"{out.stem}_work"
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, seg in enumerate(segments):
        sec = max(seg["end"] - seg["start"], 1.0)
        parts.append(_fill_slot(seg, sec, orientation, work / f"seg_{i:03d}.mp4", footage, style))
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
    _check_black(out)
    from .qa import freeze_segments
    freezes = freeze_segments(out)
    if freezes:
        offset = 0.0
        for i, seg in enumerate(segments):
            sec = max(seg["end"] - seg["start"], 1.0)
            if any(start < offset + sec and end > offset for start, end in freezes):
                log.warning("render self-check: freeze overlaps slot %d (%.3f-%.3fs); retrying next candidate once",
                            i, offset, offset + sec)
                _fill_slot(dict(seg, _retry=True), sec, orientation, parts[i], footage, style)
            offset += sec
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(visual)], check=True)
        subprocess.run(cmd, check=True)
        for start, end in freeze_segments(out):
            log.warning("render self-check: freeze persists after one repair %.3f-%.3fs; handing to QA", start, end)
    shutil.rmtree(work, ignore_errors=True)
    log.info("render: %s", out)
    return out


def render(segments: list[dict], audio: Path, srt: Path, out: Path, orientation: str = "landscape",
           footage: Footage | None = None, music_db: float = -22.0, style: dict | None = None) -> Path:
    try:
        return _render(segments, audio, srt, out, orientation, footage, music_db, style)
    finally:
        shutil.rmtree(out.parent / f"{out.stem}_work", ignore_errors=True)


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
            segs.append({"query": s["query"], "mood": s.get("mood", "calm"), "start": start + k * step, "end": start + (k + 1) * step,
                         "candidate_queries": s.get("candidate_queries", []),
                         "caption": s.get("caption") or " ".join(w["text"] for w in t.get("words", [])
                             if start + k * step <= w["start"] < start + (k + 1) * step)})
    # close gaps so shots are contiguous
    for a, b in zip(segs, segs[1:]):
        a["end"] = b["start"]
    return segs
