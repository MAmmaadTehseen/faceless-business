"""Typographic word cards for the words channel: PNG stills rendered with Pillow + raqm.

No stock footage. Each card is a dark background, a language colour bar, the word in its native
script, the romanisation and IPA, then optional lines (example sentence, memory hook). Fonts are
Noto per script when installed; missing fonts fall back to the channel font, which only covers Latin
and Cyrillic, so the workflow installs fonts-noto-core/cjk/extra.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

from .common import ASSETS_DIR, log

LATIN = ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"
FONT_DIRS = [Path("/usr/share/fonts"), Path.home() / ".fonts", Path.home() / ".local/share/fonts", ASSETS_DIR / "fonts"]
# Preferred font file name stems per script, in order.
SCRIPT_FONTS = {
    "latin": ["NotoSans-Bold", "DejaVuSans-Bold"],
    "cyrillic": ["NotoSans-Bold", "DejaVuSans-Bold"],
    "devanagari": ["NotoSansDevanagari-Bold", "NotoSansDevanagari-Regular", "NotoSansDevanagari"],
    "bengali": ["NotoSansBengali-Bold", "NotoSansBengali-Regular", "NotoSansBengali"],
    "arabic": ["NotoNaskhArabic-Bold", "NotoSansArabic-Bold", "NotoSansArabic-Regular", "NotoSansArabic"],
    "nastaliq": ["NotoNastaliqUrdu-Bold", "NotoNastaliqUrdu-Regular", "NotoNastaliqUrdu", "NotoNaskhArabic-Bold", "NotoSansArabic-Bold", "NotoSansArabic"],
    "cjk": ["NotoSansCJK-Bold", "NotoSansCJKsc-Bold", "NotoSansCJK-Regular", "NotoSansCJKjp-Bold", "NotoSansSC-Bold", "NotoSansJP-Bold"],
}
_FOUND: dict[str, Path | None] = {}


def font_path(script: str) -> Path:
    if script in _FOUND:
        return _FOUND[script] or LATIN
    found = None
    for stem in SCRIPT_FONTS.get(script, SCRIPT_FONTS["latin"]):
        for base in FONT_DIRS:
            if not base.exists():
                continue
            hits = sorted(base.rglob(stem + ".ttf")) + sorted(base.rglob(stem + ".otf")) + sorted(base.rglob(stem + ".ttc"))
            if hits:
                found = hits[0]
                break
        if found:
            break
    if not found and script not in ("latin", "cyrillic"):
        log.warning("cards: no font for script %r; falling back to %s (glyphs may be missing)", script, LATIN.name)
    _FOUND[script] = found
    return found or LATIN


def font(script: str, size: int) -> ImageFont.FreeTypeFont:
    path = font_path(script)
    try:
        return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM if features.check_feature("raqm") else ImageFont.Layout.BASIC)
    except OSError:
        return ImageFont.truetype(str(LATIN), size)


def _direction(script: str) -> str | None:
    return "rtl" if script in ("arabic", "nastaliq") else None


def _fit(draw: ImageDraw.ImageDraw, text: str, script: str, max_w: int, size: int, min_size: int = 28) -> ImageFont.FreeTypeFont:
    while size > min_size:
        f = font(script, size)
        if draw.textlength(text, font=f, direction=_direction(script)) <= max_w:
            return f
        size = int(size * 0.9)
    return font(script, min_size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int, script: str) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if draw.textlength(cand, font=f, direction=_direction(script)) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text(draw, xy, text, f, fill, script="latin", anchor="la"):
    kw = {"direction": _direction(script)} if _direction(script) and features.check_feature("raqm") else {}
    draw.text(xy, text, font=f, fill=fill, anchor=anchor, **kw)


def render_card(out: Path, *, size: tuple[int, int], bg: tuple, accent: tuple, colour: tuple,
                kicker: str, headline: str, headline_script: str = "latin", sub: str = "",
                sub2: str = "", lines: list[tuple[str, str]] | None = None, footer: str = "",
                chips: list[tuple[str, str]] | None = None, headline_scale: float = 1.0) -> Path:
    """Draw one card. lines = [(text, script)] paragraphs beneath the headline block, shrunk to fit
    above the caption area; chips = [(text, script)] short items drawn inline on one row."""
    w, h = size
    portrait = h > w
    img = Image.new("RGB", size, tuple(bg))
    # Soft diagonal glow in the language colour so cards are never flat black (QA black-frame check).
    glow = Image.new("RGB", size, tuple(bg))
    gd = ImageDraw.Draw(glow)
    for i in range(0, max(w, h), 8):
        t = i / max(w, h)
        c = tuple(int(bg[k] + (colour[k] - bg[k]) * 0.22 * (1 - t)) for k in range(3))
        gd.line([(0, i), (i, 0)], fill=c, width=9)
    img = Image.blend(img, glow, 0.9)
    d = ImageDraw.Draw(img)
    bar = max(10, h // 54)
    d.rectangle((0, 0, w, bar), fill=tuple(colour))
    margin = int(w * 0.07)
    max_w = w - 2 * margin
    # Burned captions: landscape at the bottom (keep text above), portrait around 46-62 percent of
    # the height (libass scales MarginV), so portrait paragraphs start below that band.
    bottom = h - int(h * (0.09 if portrait else 0.24))
    caption_band_end = int(h * 0.64)
    y = bar + int(h * (0.06 if portrait else 0.07))
    kf = font("latin", int(h * (0.024 if portrait else 0.034)))
    _text(d, (margin, y), kicker.upper(), kf, tuple(accent))
    if footer and d.textlength(kicker.upper(), font=kf) + d.textlength(footer, font=kf) + int(w * 0.04) <= max_w:
        _text(d, (w - margin, y), footer, kf, (150, 150, 170), anchor="ra")
    elif footer:
        # Narrow cards: the footer sits just above the caption area instead.
        _text(d, (margin, h - int(margin * 1.3)), footer, kf, (150, 150, 170), anchor="ld")
    y += int(kf.size * 2.2)
    hf = _fit(d, headline, headline_script, max_w, int(h * (0.16 if portrait else 0.26) * headline_scale))
    # Nastaliq needs extra vertical room for its descenders.
    box = d.textbbox((margin, y), headline, font=hf, anchor="la")
    extra = int(hf.size * (0.6 if headline_script == "nastaliq" else 0.15))
    _text(d, (margin, y), headline, hf, (255, 255, 255), headline_script)
    y = box[3] + extra + int(h * 0.02)
    if sub:
        sf = _fit(d, sub, "latin", max_w, int(h * (0.06 if portrait else 0.085)))
        _text(d, (margin, y), sub, sf, tuple(colour))
        y += int(sf.size * 1.35)
    if sub2:
        s2 = _fit(d, sub2, "latin", max_w, int(h * (0.036 if portrait else 0.05)))
        _text(d, (margin, y), sub2, s2, (200, 200, 215))
        y += int(s2.size * 1.6)
    if chips:
        cf = font("latin", int(h * (0.036 if portrait else 0.05)))
        x = margin
        row = int(cf.size * 1.7)
        for i, (text, script) in enumerate(chips):
            f = font(script, cf.size)
            sep = d.textlength(" · ", font=cf) if x > margin else 0
            width = d.textlength(text, font=f, direction=_direction(script))
            if x > margin and x + sep + width > w - margin:
                x, y = margin, y + row
                sep = 0
            if sep:
                _text(d, (x, y), " · ", cf, (150, 150, 170))
                x += sep
            _text(d, (x, y), text, f, (235, 235, 245), script)
            x += width
        y += row
    y += int(h * 0.02)
    if lines and portrait:
        y = max(y, caption_band_end)
    if lines:
        size_px = int(h * (0.04 if portrait else 0.05))
        while True:
            fonts = {script: font(script, size_px) for _, script in lines}
            height = 0
            for text, script in lines:
                lf = fonts[script]
                height += len(_wrap(d, text, lf, max_w, script)) * int(lf.size * (2.0 if script == "nastaliq" else 1.45)) + int(lf.size * 0.4)
            if y + height <= bottom or size_px <= int(h * 0.024):
                break
            size_px = int(size_px * 0.92)
        for text, script in lines:
            lf = fonts[script]
            for line in _wrap(d, text, lf, max_w, script):
                _text(d, (margin, y), line, lf, (235, 235, 245), script)
                y += int(lf.size * (2.0 if script == "nastaliq" else 1.45))
            y += int(lf.size * 0.4)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out


def card_clip(png: Path, sec: float, out: Path, orientation: str = "landscape") -> Path:
    """A still card becomes a slowly zooming 30 fps clip so freeze detectors see motion."""
    w, h = (1920, 1080) if orientation == "landscape" else (1080, 1920)
    frames = max(1, math.ceil(sec * 30))
    # A slow breathing zoom with a gentle drift: every frame differs by a pixel or two, so the
    # freeze detector (-60 dB) never sees a still, however long the card stays up.
    vf = (f"scale={w * 2}:{h * 2}:flags=lanczos,"
          f"zoompan=z='1.045+0.04*sin(on/19)':d={frames}:"
          f"x='iw/2-iw/zoom/2+{w // 40}*sin(on/31)':y='ih/2-ih/zoom/2+{h // 60}*cos(on/23)':"
          f"s={w}x{h}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png), "-vf", vf,
                    "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)],
                   check=True, timeout=max(60, sec * 20))
    return out
