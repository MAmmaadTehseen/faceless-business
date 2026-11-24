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


HOOK_SECONDS = 2.5


def hook_lines(text: str, max_chars: int = 18, max_lines: int = 3) -> list[str]:
    """Wrap a hook title into short bold lines a phone viewer can read in one glance."""
    words = str(text or "").split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "..."
    return lines


def _hook_filter(text: str, work: Path, orientation: str, style: dict | None = None) -> str | None:
    """drawtext filter showing the hook title for the first HOOK_SECONDS of a portrait Short.

    Growth log 2026-11-17: Shorts autoplay muted and faceless openers have no face to
    carry them; every source agrees the first frame must state the topic in text, and
    the same frame is Instagram's cover (thumb offset 2 s). Placed in the upper third,
    clear of the right-hand action rail and the burned captions at the bottom.
    """
    lines = hook_lines(text, max_chars=15)
    if not lines or orientation != "portrait":
        return None
    font = _font()
    fontfile = f"fontfile='{str(Path(font).resolve()).replace(chr(92), '/')}':" if font else ""
    # 2026-11-24: the 68 px white-on-grey title was unreadable at phone size in contact sheets;
    # now 92 px black on the channel accent, the most legible pairing on any footage.
    accent = "0x" + "".join(f"{int(c):02x}" for c in (style or {}).get("accent", (251, 191, 36)))
    size, gap = 92, 26
    parts = []
    # One drawtext per line: ffmpeg 8 renders the newline itself as a missing glyph.
    for i, line in enumerate(lines):
        tf = work / f"hook_{i}.txt"
        tf.write_text(line, encoding="utf-8")
        path = str(tf.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        y = f"h*0.12+{i * (size + gap)}"
        parts.append(f"drawtext={fontfile}textfile='{path}':fontsize={size}:fontcolor=black:"
                     f"box=1:boxcolor={accent}@0.96:boxborderw=22:"
                     f"x=(w-text_w)/2:y={y}:enable='lt(t,{HOOK_SECONDS})'")
    return ",".join(parts)


def add_hook_card(src: Path, dst: Path, title: str) -> Path:
    """Burn the hook card onto an already rendered portrait Short (banked or queued media).

    Video is re-encoded once; audio is copied. Returns dst (or src when nothing to draw).
    """
    work = dst.parent / f"{dst.stem}_hookwork"
    work.mkdir(parents=True, exist_ok=True)
    try:
        vf = _hook_filter(title, work, "portrait")
        if not vf:
            return src
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "medium",
                        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return dst


def _music() -> Path | None:
    tracks = sorted((ASSETS_DIR / "music").glob("*.mp3"))
    return tracks[0] if tracks else None


def _caption_style(orientation: str, style: dict | None = None) -> str:
    style = style or {}
    font = _font()
    fontname = Path(font).stem if font else "DejaVu Sans"
    colour = style.get("caption_colour", "&H00FFFFFF"); outline = style.get("caption_outline", "&H80000000")
    if orientation == "landscape":
        return f"FontName={fontname},FontSize={style.get('font_size_long', 20)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=48,MarginL=64,MarginR=64"
    return f"FontName={fontname},FontSize={style.get('font_size_short', 26)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=110,MarginL=48,MarginR=48"


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
                     style: dict | None = None, big: bool = False) -> Path:
    """Encode a branded card in the same single command as a normal slot.

    big=True is the stat card a script asks for with a 'CARD: <words>' shot: a key number or name
    in huge accent-coloured type, a pattern interrupt that is always on topic (growth log 2026-11-24).
    """
    style = style or {}
    w, h = _dims(orientation)
    accent = "0x" + "".join(f"{int(c):02x}" for c in style.get("accent", (251, 191, 36)))
    # Keep the card visibly nonblack even with the channel's very dark background.
    bg = "0x" + "".join(f"{max(32, int(c)):02x}" for c in style.get("bg", (32, 32, 40)))
    import textwrap
    if big:
        wrap = 10 if w < h else 16
        lines = textwrap.wrap(text.upper(), width=wrap)[:3]
        size = (w // 6 if w < h else h // 6) if max((len(l) for l in lines), default=1) <= 8 else (int(w / 7.5) if w < h else h // 8)
        colour = accent
    else:
        lines = textwrap.wrap(text, width=48 if w > h else 27)
        size, colour = max(8, h // 24), "white"
    font = _font()
    fontfile = f"fontfile='{str(Path(font).resolve()).replace(chr(92), '/')}':" if font else ""
    # One drawtext per line (ffmpeg 8 draws a newline as a missing-glyph box). Stat cards sit in
    # the upper third so the burned narration captions in the middle never cover them.
    step = int(size * 1.15)
    top = f"h*0.06" if big and w < h else f"(h-{step * len(lines)})/2"
    draws = []
    for i, line in enumerate(lines):
        label = out.with_suffix(".txt" if i == 0 else f".{i}.txt")
        label.write_text(line, encoding="utf-8")
        label_path = str(label.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        draws.append(f"drawtext={fontfile}textfile='{label_path}':expansion=none:fontcolor={colour}:"
                     f"borderw={max(2, size // 25)}:bordercolor=black:fontsize={size}:x=(w-text_w)/2:y={top}+{i * step}")
    vf = (f"drawbox=x=0:y=0:w=iw:h={max(8, h//60)}:color={accent}:t=fill,"
          + ",".join(draws) + ","
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
    # Long-video shot lists use the same prefixes in `query` ("CARD: ...", "CHART: ...", "MAP: ...").
    prefix, _, rest = (seg.get("query") or "").partition(":")
    if not seg.get("card") and not seg.get("graphic") and prefix.strip().upper() in ("CARD", "CHART", "MAP") and rest.strip():
        kind = prefix.strip().lower()
        seg = dict(seg, **({"card": rest.strip()[:40]} if kind == "card" else {"graphic": (kind, rest.strip())}),
                   query=seg.get("caption") or "abstract background")
    if seg.get("graphic"):
        clip = _graphic_clip(*seg["graphic"], sec, orientation, out, style)
        if clip:
            return clip
        # An undrawable spec (unknown country, no numbers) falls back to a stat card of its text.
        return _background_card(seg["graphic"][1].split("|")[-1].strip()[:40] or seg.get("caption", ""), sec, orientation, out, style, big=True)
    if seg.get("card"):
        return _background_card(seg["card"], sec, orientation, out, style, big=True)
    # No truncated fallback ("large radio" for a Voyager script found wildflowers, 2026-11-24):
    # an off-topic clip is worse than the branded caption card below.
    queries = list(dict.fromkeys([seg["query"], *(seg.get("candidate_queries") or [])]))
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
           footage: Footage | None = None, music_db: float = -22.0, style: dict | None = None, hook_text: str | None = None,
           sfx_db: float | None = -17.0) -> Path:
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
    hook = _hook_filter(hook_text, work, orientation, style) if hook_text else None
    if hook:
        vf = f"{vf},{hook}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(visual), "-i", str(audio)]
    music = _music()
    sfx_track = None
    if sfx_db is not None:
        try:
            from .sfx import track
            sfx_track = track(segments, orientation, total, work / "sfx.wav")
        except Exception as exc:  # sound design is optional; never fail a render over it
            log.warning("sfx track skipped: %s", exc)
    mix, n = ["[1:a]"], 1
    filters = []
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        n += 1
        filters.append(f"[{n}:a]volume={music_db}dB[m]")
        mix.append("[m]")
    if sfx_track:
        cmd += ["-i", str(sfx_track)]
        n += 1
        filters.append(f"[{n}:a]volume={sfx_db}dB[s]")
        mix.append("[s]")
    if len(mix) > 1:
        # normalize=0 keeps the narration at full level instead of dividing it by the input count.
        fc = ";".join(filters + [f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[a]"])
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-vf", vf, "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    _check_black(out)
    from .qa import freeze_segments
    # Scan the final encode with QA's detector settings. A new candidate may also
    # be static, so each slot has its own bounded retry budget.
    attempts = [0] * len(parts)
    cards = set()
    while freezes := freeze_segments(out):
        from .qa import probe
        offset = 0.0
        for i, seg in enumerate(segments):
            sec = max(seg["end"] - seg["start"], 1.0)
            # Encodes round to frames; accumulated rounding shifts later slots.
            end_offset = offset + probe(parts[i])["duration"]
            if any(start < end_offset and end > offset for start, end in freezes):
                if i in cards:
                    raise RuntimeError(f"render self-check: moving card still frozen in slot {i}")
                if attempts[i] < 3:
                    attempts[i] += 1
                    log.warning("render self-check: freeze overlaps slot %d (%.3f-%.3fs); replacement attempt %d/3",
                                i, offset, end_offset, attempts[i])
                    _fill_slot(dict(seg, _retry=True), sec, orientation, parts[i], footage, style)
                else:
                    log.warning("render self-check: slot %d frozen after 3 replacements; using moving branded caption card", i)
                    _background_card(seg.get("caption") or seg.get("text") or seg["query"],
                                     sec, orientation, parts[i], style)
                    cards.add(i)
            offset = end_offset
        if not any(start < offset and end > 0 for start, end in freezes):
            raise RuntimeError("render self-check: freeze outside rendered slots")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(visual)], check=True)
        subprocess.run(cmd, check=True)
    shutil.rmtree(work, ignore_errors=True)
    log.info("render: %s", out)
    return out


def render(segments: list[dict], audio: Path, srt: Path, out: Path, orientation: str = "landscape",
           footage: Footage | None = None, music_db: float = -22.0, style: dict | None = None, hook_text: str | None = None,
           sfx_db: float | None = -17.0) -> Path:
    try:
        return _render(segments, audio, srt, out, orientation, footage, music_db, style, hook_text, sfx_db)
    finally:
        shutil.rmtree(out.parent / f"{out.stem}_work", ignore_errors=True)


def _graphic_clip(kind: str, spec: str, sec: float, orientation: str, out: Path, style: dict | None = None) -> Path | None:
    """CHART:/MAP: shot as a moving clip (slow push-in, so the freeze detector never fires)."""
    from .graphics import graphic_image
    w, h = _dims(orientation)
    img = graphic_image(kind, spec, (w, h), style)
    if img is None:
        return None
    still = out.with_suffix(".png")
    img.save(still)
    frames = max(1, math.ceil(sec * 30))
    vf = (f"scale={int(w * 1.06)}:{int(h * 1.06)},zoompan=z='1+0.05*on/{frames}':d={frames}:"
          f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':s={w}x{h}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(still), "-vf", vf,
                    "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)],
                   check=True, timeout=max(60, sec * 10))
    return out


def apply_shots(segs: list[dict], shots: list | None, fallback_query: str) -> list[dict]:
    """Give each Short segment its own visual from the script's ordered `shots` list: a stock search
    matching that moment, or 'CARD: <words>' for a branded stat card. Older scripts without shots
    keep their single query."""
    shots = [str(x).strip() for x in (shots or []) if str(x).strip()]
    if not shots:
        return segs
    plain = [x for x in shots if x.split(":", 1)[0].strip().upper() not in ("CARD", "CHART", "MAP")] or [fallback_query]
    for i, seg in enumerate(segs):
        # Past the end of the list, reuse only footage queries: a repeated card or map looks like a glitch.
        shot = shots[i] if i < len(shots) else plain[(i - len(shots)) % len(plain)]
        head = shot.split(":", 1)[0].strip().upper()
        if head == "CARD":
            seg["card"] = shot[5:].strip()[:40] or seg.get("caption", "")
        elif head in ("CHART", "MAP") and ":" in shot:
            seg["graphic"] = (head.lower(), shot.split(":", 1)[1].strip())
        else:
            seg["query"] = shot
            seg["candidate_queries"] = [fallback_query] if fallback_query and fallback_query != shot else []
    return segs


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
