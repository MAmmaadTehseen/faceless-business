"""Assemble narration + footage + burned captions + music into the final video with ffmpeg."""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .common import ASSETS_DIR, log
from .footage import Footage

FONT_DIR = ASSETS_DIR / "fonts"
OFL_FONT_DIR = ASSETS_DIR / "fonts" / "ofl"
FALLBACK_FONT = FONT_DIR / "DejaVuSans-Bold.ttf"

# Shot prefix -> segment type. Plain queries are footage; every other type comes
# from a "PREFIX: ..." shot (motion-graphics plan stage 2, 2026-11-25). Diagrams
# keep their sub-kind in seg["sub_kind"] so the engine can pick a composition.
PREFIX_TYPES: dict[str, str] = {
    "CARD": "text",
    "TEXT": "text",
    "CHART": "chart",
    "MAP": "map",
    "TIMELINE": "diagram",
    "SCALE": "diagram",
    "ORBIT": "diagram",
    "PRESENTER": "presenter",
}
DIAGRAM_KINDS = ("timeline", "scale", "orbit")


def shot_type(query: str) -> str:
    """Segment type for a shot query: footage unless it carries a known prefix."""
    head = (str(query) or "").split(":", 1)[0].strip().upper()
    return PREFIX_TYPES.get(head, "footage")


def _typed_seg(seg: dict, query: str) -> dict:
    """Copy of `seg` with type/sub_kind derived from the shot prefix.

    Old behaviour is kept: CARD/CHART/MAP keep filling seg["card"]/seg["graphic"]
    and a plain query stays a footage query, so resumed scripts render unchanged.
    """
    out = dict(seg)
    shot = str(query) or ""
    head, _, rest = shot.partition(":")
    head = head.strip().upper()
    rest = rest.strip()
    kind = PREFIX_TYPES.get(head)
    out["type"] = kind or "footage"
    if kind == "text":
        out["card"] = rest[:40] or str(seg.get("caption") or "")[:40]
    elif kind == "chart" and rest:
        out["graphic"] = ("chart", rest)
    elif kind == "map" and rest:
        out["graphic"] = ("map", rest)
    elif kind == "diagram" and rest:
        out["graphic"] = (head.lower(), rest)
        out["sub_kind"] = head.lower()
    elif kind == "presenter" and rest:
        out["presenter_text"] = rest
    return out


def _font() -> str | None:
    for p in sorted(FONT_DIR.glob("*.ttf")) + sorted(FONT_DIR.glob("*.otf")):
        return str(p)
    return None


def font_for(style: dict | None, role: str) -> Path:
    """Per-channel font file (channel.json style.fonts.<role>), DejaVu when unset or missing.

    role is 'caption' (burned narration subtitles) or 'headline' (hook cards, stat cards,
    charts and maps). Fonts live in assets/fonts/ofl/<file>; a missing file falls back to
    assets/fonts/DejaVuSans-Bold.ttf so a typo in channel.json can never fail a render.
    """
    fonts = (style or {}).get("fonts") or {}
    name = fonts.get(role)
    if name:
        p = OFL_FONT_DIR / str(name)
        if p.is_file():
            return p
    return FALLBACK_FONT


def _font_family(path: Path) -> str:
    """Name libass/fontconfig actually matches for this file, read from the TTF name table.

    Google's static weights (Black, ExtraBold) are non-RIBBI: fontconfig registers them under
    the full name ('Montserrat Black'), so the bare PIL family ('Montserrat') silently falls
    back to a system font. 'family style' matched every vendored file and the DejaVu fallback
    in the ffmpeg 8 fontselect probe (2026-11-25): Montserrat Black, Montserrat ExtraBold,
    Anton Regular, Bebas Neue Regular, Exo 2 Black, Oswald Bold, Poppins ExtraBold,
    DejaVu Sans Bold. Do not shorten this back to getname()[0].
    """
    try:
        from PIL import ImageFont
        family, style = ImageFont.truetype(str(path), 24).getname()
        return f"{family} {style}".strip() if style else family
    except Exception:
        return "DejaVu Sans"


def caption_fontsdir(style: dict | None) -> str:
    """:fontsdir= option for the subtitles filter: the caption font's own folder.

    libass's fontsdir scan is not recursive (assets/fonts does not see ofl/), and a
    multi-directory value silently disables app-font loading entirely, so the value must
    be exactly one directory: assets/fonts/ofl for a vendored channel font, assets/fonts
    for the DejaVu fallback. Glyphs the caption font lacks (non-Latin scripts) still fall
    back per-glyph through fontconfig's system fonts.
    """
    return f":fontsdir={font_for(style, 'caption').parent}"


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
    fontfile = f"fontfile='{_font_path(font_for(style, 'headline'))}':"
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


def add_hook_card(src: Path, dst: Path, title: str, style: dict | None = None) -> Path:
    """Burn the hook card onto an already rendered portrait Short (banked or queued media).

    Video is re-encoded once; audio is copied. Returns dst (or src when nothing to draw).
    """
    work = dst.parent / f"{dst.stem}_hookwork"
    work.mkdir(parents=True, exist_ok=True)
    try:
        vf = _hook_filter(title, work, "portrait", style)
        if not vf:
            return src
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "medium",
                        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return dst


def _font_path(path: Path) -> str:
    """Absolute posix path for a fontfile= option (drawtext needs forward slashes)."""
    return str(Path(path).resolve()).replace(chr(92), "/")


def _music() -> Path | None:
    tracks = sorted((ASSETS_DIR / "music").glob("*.mp3"))
    return tracks[0] if tracks else None


def _caption_style(orientation: str, style: dict | None = None) -> str:
    style = style or {}
    fontname = _font_family(font_for(style, "caption"))
    colour = style.get("caption_colour", "&H00FFFFFF"); outline = style.get("caption_outline", "&H80000000")
    if orientation == "landscape":
        return f"FontName={fontname},FontSize={style.get('font_size_long', 20)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=48,MarginL=64,MarginR=64"
    return f"FontName={fontname},FontSize={style.get('font_size_short', 26)},Bold=1,PrimaryColour={colour},OutlineColour={outline},BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=110,MarginL=48,MarginR=48"


def _dims(orientation: str) -> tuple[int, int]:
    return (1920, 1080) if orientation == "landscape" else (1080, 1920)


def font_size_portrait(style: dict | None = None) -> float:
    """ASS caption Fontsize for a portrait (1080x1920) frame: the legacy force_style 26 scaled
    by ffmpeg's 384x288 -> 1920 PlayRes factor, i.e. pixel-identical type to the old SRT burn."""
    return float((style or {}).get("font_size_short", 26)) * 1920 / 288


def font_size_landscape(style: dict | None = None) -> float:
    """ASS caption Fontsize for a landscape (1920x1080) frame: legacy force_style 20 scaled by 288 -> 1080."""
    return float((style or {}).get("font_size_long", 20)) * 1080 / 288


def _ass_ts(t: float) -> str:
    """Seconds -> ASS 'H:MM:SS.cc' (centiseconds, the resolution the Events format expects).

    Rounds to centiseconds first and formats from integer centiseconds so 0.999s is 0:00:01.00,
    never an invalid 'SS.100' field."""
    cs = int(round(max(float(t or 0.0), 0.0) * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{int(cs):02d}"


def _ass_colour(rgb, default: str = "&H00FFFFFF") -> str:
    """Channel accent RGB (order R,G,B) or an existing ASS string -> ASS &H00BBGGRR& opaque."""
    s = str(rgb) if rgb is not None else ""
    if not s:
        return default
    if s.startswith("&H") or s.startswith("&h") or s.startswith("&"):
        return s
    try:
        r, g, b = (max(0, min(255, int(c))) for c in rgb)
    except (TypeError, ValueError):
        return default
    return f"&H00{b:02X}{g:02X}{r:02X}&"


def _ends_sentence(text: str) -> bool:
    """Sentence enders only, matching words_to_srt: a comma must not shatter a 2-3 word chunk."""
    return bool(re.search(r"[.!?…]\s*$", str(text or "")))


def _ass_word(text: str) -> str:
    """One word as safe ASS text: braces are override-tag syntax and newlines are line breaks."""
    return str(text or "").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


# libass draws Fontsize as em = Fontsize * units_per_em / (usWinAscent + usWinDescent), so a PIL
# ImageFont at Fontsize overstates the rendered width by 1/that factor (measured 2026-11-25 with
# fontselect verified per font: Montserrat Black 0.63, Anton 0.56, Bebas 0.75, Poppins 0.55,
# Oswald 0.56, Exo 2 0.66, DejaVu 0.84, each within ~3% of its metric ratio). Measuring at the
# metric-corrected size therefore predicts the real libass width from slightly above, so the
# 88% rule splits early and letters are never cropped; a failed parse falls back to 1.0, the
# maximally early-splitting direction.
_em_factor_cache: dict[str, float] = {}


def _font_em_factor(path: Path) -> float:
    key = str(path)
    if key in _em_factor_cache:
        return _em_factor_cache[key]
    val = 1.0
    try:
        import struct
        data = Path(path).read_bytes()
        num_tables = struct.unpack(">H", data[4:6])[0]
        offsets = {}
        for i in range(num_tables):
            off = 12 + 16 * i
            offsets[data[off:off + 4].decode("latin-1")] = struct.unpack(">I", data[off + 8:off + 12])[0]
        head = offsets["head"]
        upm = struct.unpack(">H", data[head + 18:head + 20])[0]
        os2 = offsets["OS/2"]
        win_asc, win_desc = struct.unpack(">HH", data[os2 + 74:os2 + 78])
        if upm and win_asc + win_desc:
            val = upm / (win_asc + win_desc)
    except Exception:
        val = 1.0
    val = min(max(val, 0.25), 1.0)
    _em_factor_cache[key] = val
    return val


_caption_font_cache: dict[str, "object"] = {}


def _caption_font(style: dict | None, font_size: float):
    """PIL ImageFont of the caption font at the libass-equivalent measure size for ASS Fontsize."""
    path = font_for(style, "caption")
    size = max(6.0, float(font_size) * _font_em_factor(path))
    key = f"{path}@{size:.2f}"
    if key not in _caption_font_cache:
        from PIL import ImageFont
        try:
            _caption_font_cache[key] = ImageFont.truetype(str(path), size)
        except Exception:  # unloadable file -> PIL's default bitmap font still measures a width
            _caption_font_cache[key] = ImageFont.load_default()
    return _caption_font_cache[key]


def _split_wide_chunk(words: list[dict], style: dict | None, font_size: float, frame_w: int) -> list[list[dict]]:
    """Split a chunk until it fits 88% of the frame width; a single over-wide word comes back alone."""
    limit = frame_w * 0.88
    if _caption_font(style, font_size).getlength(" ".join(str(w["text"]) for w in words)) <= limit:
        return [words]
    if len(words) == 1:
        return [words]
    mid = len(words) // 2
    return (_split_wide_chunk(words[:mid], style, font_size, frame_w)
            + _split_wide_chunk(words[mid:], style, font_size, frame_w))


def caption_chunks(words: list[dict], style: dict | None, font_size: float, frame_w: int) -> list[list[dict]]:
    """Word-timed list -> chunks of 2-3 words, breaking at sentence punctuation, each narrow enough.

    Greedy 3-word chunks; a word ending a sentence closes its chunk early (the words_to_srt
    precedent). Timings are never altered, so tests can assert on the chunking directly."""
    chunks: list[list[dict]] = []
    for w in words:
        if not str(w.get("text") or "").strip():
            continue
        if chunks and len(chunks[-1]) < 3 and not _ends_sentence(chunks[-1][-1]["text"]):
            chunks[-1].append(w)
        else:
            chunks.append([w])
    fitted: list[list[dict]] = []
    for chunk in chunks:
        fitted.extend(_split_wide_chunk(chunk, style, font_size, frame_w))
    return fitted


def _ass_events(timings: list[dict], style: dict, font_size: float, frame_w: int) -> list[str]:
    """One Dialogue event per word time span: the whole chunk with that word in the accent colour.

    Word timings are used verbatim (each event is exactly its word's span). The active word is
    wrapped in a colour override that resets to white after it, so every event colours exactly
    one word; non-active words take the style's white PrimaryColour."""
    accent = _ass_colour(style.get("accent"), "&H0024BFFB&")
    white = "&H00FFFFFF&"
    font = _caption_font(style, font_size)
    events: list[str] = []
    for t in timings or []:
        words = [dict(x) for x in (t.get("words") or []) if str(x.get("text") or "").strip()]
        if not words:
            continue
        for chunk in caption_chunks(words, style, font_size, frame_w):
            for i, word in enumerate(chunk):
                text = ""
                size_override = ""
                if len(chunk) == 1:
                    width = font.getlength(str(word["text"]))
                    if width > frame_w * 0.88:
                        # single word still too wide: shrink just this event so letters are never cropped
                        shrink = max(6.0, font_size * frame_w * 0.88 / max(width, 1.0))
                        size_override = f"{{\\fs{int(round(shrink))}}}"
                for j, other in enumerate(chunk):
                    if j:
                        text += " "
                    word_text = _ass_word(other["text"])
                    if j == i:
                        text += f"{{\\c{accent}}}{word_text}{{\\c{white}}}"
                    else:
                        text += word_text
                start = max(float(word.get("start") or 0.0), 0.0)
                end = max(float(word.get("end") or 0.0), start + 0.01)
                events.append(f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},Cap,,0,0,0,,{size_override}{text}")
    return events


def write_ass(timings: list[dict], out_path: Path, orientation: str, style: dict | None = None) -> Path:
    """Word-highlight captions as an ASS file for the subtitles filter (see the caption pass notes).

    PlayResX/PlayResY are the frame size, so libass scales 1:1 and every value below is in frame
    pixels. Font size and MarginV keep today's burned captions pixel-identical: the legacy SRT
    path forces FontSize 26/20 at ffmpeg's default 384x288 PlayRes, which on a 1080x1920 frame
    equals 173/75 here (verified 2026-11-25 by comparing rendered extents). Outline 6 portrait /
    4 landscape with BorderStyle=1 and Shadow=0: thick black stroke, no box. Chunks of 2-3 words
    are split by the width rule (88% of frame, PIL-measured at the libass-equivalent size) and a
    single over-wide word gets a per-event font-size override."""
    style = style or {}
    w, h = _dims(orientation)
    portrait = orientation != "landscape"
    font_size = font_size_portrait(style) if portrait else font_size_landscape(style)
    outline = 6 if portrait else 4
    margin_v = int(round((110 if portrait else 48) * h / 288))
    family = _font_family(font_for(style, "caption"))
    events = _ass_events(timings, style, font_size, w)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,"
        " Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
        " Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{family},{font_size:.2f},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"1,0,0,0,100,100,0,0,1,{outline},0,2,0,0,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "".join(f"{line}\n" for line in events),
        encoding="utf-8")
    return out_path


def _timings_beside(audio: Path | None) -> list | None:
    """tts.synthesize writes <name>_timings.json next to <name>.mp3; load it for the caption pass."""
    if not audio:
        return None
    p = Path(audio).with_name(f"{Path(audio).stem}_timings.json")
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, list) else None


def _caption_ass(timings: list | None, audio: Path, work: Path, orientation: str,
                 style: dict | None) -> Path | None:
    """The word-highlight ASS for this render, or None to keep the SRT caption path.

    None whenever there is nothing word-timed to show (timings absent, or retained timings
    without per-word detail) so a caption can never silently disappear behind an empty ASS."""
    tl = timings if timings is not None else _timings_beside(audio)
    if not tl:
        return None
    try:
        out = work / "captions.ass"
        write_ass(tl, out, orientation, style)
        if "Dialogue:" not in out.read_text(encoding="utf-8"):
            return None
        return out
    except Exception as exc:  # noqa: BLE001 - captions must never fail a render; SRT still burns
        log.warning("word-highlight captions unavailable, burning SRT captions: %s", exc)
        return None


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
    fontfile = f"fontfile='{_font_path(font_for(style, 'headline'))}':"
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


def _presenter_slot(seg: dict, sec: float, orientation: str, out: Path,
                    footage: Footage, style: dict | None = None) -> Path:
    """A PRESENTER: shot. The text after the prefix renders as a text segment when
    present, otherwise the segment's footage query supplies the visual.

    This is the stub where the owner's voice/avatar clone (experiments/clone)
    plugs in later: a PRESENTER shot will render the clone delivering the line
    instead of a branded card or stock clip.
    """
    text = (seg.get("presenter_text") or "").strip()
    if text:
        return _background_card(text, sec, orientation, out, style, big=True)
    return _fill_slot({k: v for k, v in seg.items() if k not in ("presenter_text", "type", "sub_kind")},
                      sec, orientation, out, footage, style)


def _brand(style: dict | None, accent=(251, 191, 36), bg=(14, 18, 26)) -> dict:
    """Remotion brand props: accent, background and the channel headline font (if vendored)."""
    style = style or {}
    brand = {"accent": list(style.get("accent") or accent), "bg": list(style.get("bg") or bg)}
    font = font_for(style, "headline")
    if font.parent == OFL_FONT_DIR:
        brand["font"] = "Brand " + font.stem
        brand["fontFile"] = font.name
    return brand


def _remotion_clip(kind: str, spec: str, sec: float, orientation: str, out: Path,
                   style: dict | None = None) -> Path | None:
    """One chart/map/diagram/text shot through the Remotion compositions.

    Spec parsing: CHART/SCALE use graphics.parse_chart ('title | label=value, ...'),
    MAP uses graphics.parse_map, TIMELINE is 'title | 1977=Launch, ...' and ORBIT is
    'Earth, Mars | label'. Returns the clip, or None (caller falls back to Pillow)
    when the spec does not parse or Remotion is unavailable/raises.
    """
    from . import remotion
    from .graphics import parse_chart, parse_map
    try:
        if kind == "chart":
            title, items = parse_chart(spec)
            props = {"title": title, "items": [{"label": l, "value": v, "shown": s} for l, v, s in items]}
        elif kind == "scale":
            title, items = parse_chart(spec)
            props = {"title": title, "items": [{"label": l, "value": v, "shown": s} for l, v, s in items]}
        elif kind == "map":
            names, label = parse_map(spec)
            props = {"countries": names, "label": label}
        elif kind == "timeline":
            title, _, body = spec.partition("|")
            events = []
            for part in body.split(","):
                if "=" not in part:
                    continue
                when, _, label = part.partition("=")
                if when.strip() and label.strip():
                    events.append({"when": when.strip()[:8], "label": label.strip()[:40]})
            if len(events) < 2:
                return None
            props = {"title": title.strip()[:60], "events": events[:6]}
        elif kind == "orbit":
            bodies, _, label = spec.partition("|")
            names = [b.strip().title() for b in bodies.split(",") if b.strip()]
            if not names:
                return None
            props = {"bodies": names, "label": label.strip()[:48]}
        elif kind == "text":
            props = {"text": " ".join(str(spec).split())[:120]}
        else:
            return None
        if not remotion.available():
            return None
        return remotion.render_segment(kind if kind != "text" else "text", props, sec, orientation, out,
                                       _brand(style), entry_point=remotion.bundled_entry_point())
    except Exception as exc:
        log.warning("remotion %s shot fell back to Pillow (%s): %s", kind, exc, str(spec)[:80])
        return None


def _uniform(path: Path) -> Path:
    """Re-encode a slot whose stream parameters differ from the footage slots.

    Slots are joined with the concat demuxer and `-c copy`, which needs identical timebase and
    pixel format. Remotion clips arrive as yuvj420p and image-loop graphics with a 1/90000
    timebase; mixing them with 1/15360 footage made the 2026-11-25 sample run 55 s of picture
    against 40.6 s of narration, with frozen frames and stuck captions.
    """
    try:
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=time_base,pix_fmt,r_frame_rate", "-of", "csv=p=0", str(path)],
                              capture_output=True, text=True, check=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return path
    if info.replace(" ", "") in ("yuv420p,30/1,1/15360",):
        return path
    tmp = path.with_suffix(".uniform.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf", "fps=30,format=yuv420p,setpts=N/(30*TB)",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-video_track_timescale", "15360",
                    str(tmp)], check=True, capture_output=True, timeout=300)
    tmp.replace(path)
    return path


def _fill_slot(seg: dict, sec: float, orientation: str, out: Path,
               footage: Footage, style: dict | None = None) -> Path:
    return _uniform(_fill_slot_raw(seg, sec, orientation, out, footage, style))


def _fill_slot_raw(seg: dict, sec: float, orientation: str, out: Path,
                   footage: Footage, style: dict | None = None) -> Path:
    from .qa import probe
    # Long-video shot lists use the same prefixes in `query` ("CARD: ...", "CHART: ...",
    # "MAP: ...", and now TIMELINE:/SCALE:/ORBIT:/TEXT:/PRESENTER:); the typed plan
    # derives seg["type"] and fills card/graphic exactly as apply_shots() does.
    if not seg.get("card") and not seg.get("graphic") and not seg.get("presenter_text"):
        typed = _typed_seg(seg, seg.get("query") or "")
        if typed["type"] != "footage" and (typed.get("card") or typed.get("graphic") or typed.get("presenter_text")):
            typed.setdefault("query", seg.get("caption") or "abstract background")
            seg = typed
    motion = bool((style or {}).get("motion"))
    if motion and seg.get("type") in ("chart", "map", "diagram", "text") \
            and (seg.get("graphic") or seg.get("card")):
        from . import remotion
        if remotion.ensure_installed():
            kind = seg.get("sub_kind") or (seg.get("graphic") or (None, None))[0] \
                or ("text" if seg.get("card") else None)
            spec = seg["graphic"][1] if seg.get("graphic") else seg.get("card", "")
            clip = _remotion_clip(kind, spec, sec, orientation, out, style)
            if clip:
                return clip
        # Remotion unavailable or failed: fall through to the Pillow path below.
    if seg.get("type") == "presenter":
        return _presenter_slot(seg, sec, orientation, out, footage, style)
    if seg.get("graphic") and seg["graphic"][0] in ("timeline", "scale", "orbit"):
        # TIMELINE/SCALE/ORBIT outside Remotion: a text card of the title.
        return _background_card(seg["graphic"][1].split("|")[0].strip()[:40] or seg.get("caption", ""),
                                sec, orientation, out, style, big=True)
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
           sfx_db: float | None = -17.0, timings: list[dict] | None = None) -> Path:
    """segments: [{query, mood, start, end}] in order, covering the narration.

    `timings` (tts.synthesize output, [{index,start,end,words:[{text,start,end}]}]) switches on
    the word-highlight caption pass: an ASS file where each word's time span shows its 2-3 word
    chunk with that word in the channel accent and the others white. Without usable word
    timings the SRT captions burn exactly as before; when timings are not passed at all, the
    <audio stem>_timings.json tts.synthesize writes next to the audio is used if it exists."""
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

    ass = _caption_ass(timings, audio, work, orientation, style)
    if ass is not None:
        # word-highlight pass: the ASS carries its own font (fontsdir) and per-word colour overrides
        cap_path = str(ass.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        log.info("render %s: word-highlight captions (%d events)", out.name,
                 ass.read_text(encoding="utf-8").count("Dialogue:"))
        vf = f"subtitles='{cap_path}'{caption_fontsdir(style)}"
    else:
        srt_path = str(srt.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles='{srt_path}':force_style='{_caption_style(orientation, style)}'{caption_fontsdir(style)}"
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
           sfx_db: float | None = -17.0, timings: list[dict] | None = None) -> Path:
    try:
        return _render(segments, audio, srt, out, orientation, footage, music_db, style, hook_text, sfx_db, timings)
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
    matching that moment, or a typed shot — 'CARD: <words>' text, 'CHART:'/'MAP:' graphics and the
    TIMELINE:/SCALE:/ORBIT:/TEXT:/PRESENTER: kinds. Older scripts without shots keep their single query."""
    shots = [str(x).strip() for x in (shots or []) if str(x).strip()]
    if not shots:
        return segs
    typed_prefixes = set(PREFIX_TYPES)
    plain = [x for x in shots if x.split(":", 1)[0].strip().upper() not in typed_prefixes] or [fallback_query]
    for i, seg in enumerate(segs):
        # Past the end of the list, reuse only footage queries: a repeated card or map looks like a glitch.
        shot = shots[i] if i < len(shots) else plain[(i - len(shots)) % len(plain)]
        head = shot.split(":", 1)[0].strip().upper()
        if head in typed_prefixes and ":" in shot:
            seg.update(_typed_seg(seg, shot))
            if head == "PRESENTER":
                seg["query"] = seg.get("query") if seg.get("query") not in (None, "", shot) else (seg.get("caption") or "abstract background")
            elif not seg.get("card") and not seg.get("graphic"):
                seg["query"] = shot
        else:
            seg["query"] = shot
            seg["type"] = "footage"
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
