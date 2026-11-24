"""On-topic explainer graphics for channels without a real footage library (growth log 2026-11-24).

Scripts ask for them as shots, the same way as stat cards:

    CHART: US tariff on Chinese EVs | 2023=25%, 2024=100%
    MAP: Iran, Oman | Strait of Hormuz

A chart draws the script's own numbers as bars in the channel accent; a map draws the world from
Natural Earth 1:110m country outlines (public domain, assets/geo) and highlights the named
countries, cropped to them. Both are still images that the renderer moves with a slow zoom, so
the freeze detector never sees a static frame. No model calls, no network.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import ASSETS_DIR, log

GEO = ASSETS_DIR / "geo" / "ne_110m_countries.geojson"
FONT = ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"

ALIASES = {
    "us": "united states of america", "usa": "united states of america", "united states": "united states of america",
    "america": "united states of america", "uk": "united kingdom", "britain": "united kingdom",
    "great britain": "united kingdom", "england": "united kingdom", "korea": "south korea",
    "russia": "russia", "uae": "united arab emirates", "emirates": "united arab emirates",
    "congo": "dem. rep. congo", "drc": "dem. rep. congo", "czech republic": "czechia",
    "holland": "netherlands", "the netherlands": "netherlands", "ivory coast": "côte d'ivoire",
    "eu": "__eu__", "european union": "__eu__", "europe": "__eu__",
}
EU = ["austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia", "denmark", "estonia", "finland", "france",
      "germany", "greece", "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg", "netherlands",
      "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden"]


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default()


def _rgb(c, default=(251, 191, 36)) -> tuple:
    return tuple(int(x) for x in (c or default))[:3]


def _fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, size: int, min_size: int = 18):
    """Largest font size (from `size` down) at which `text` fits in max_w pixels."""
    while size > min_size and draw.textlength(text, font=_font(size)) > max_w:
        size -= 2
    return _font(size)


def _wrap(draw, text: str, font, max_w: int, max_lines: int = 2) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines[:max_lines]


# ---------- charts ----------

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "mn": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9,
          "t": 1e12, "tn": 1e12, "trillion": 1e12}


def parse_chart(spec: str) -> tuple[str, list[tuple[str, float, str]]]:
    """'Title | a=25%, b=100%' -> (title, [(label, value, shown text)]). Bars need 2-6 numeric items."""
    title, _, body = spec.partition("|") if "|" in spec else ("", "", spec)
    items = []
    for part in re.split(r"[,;](?![\d]{3}\b)", body):
        if "=" not in part:
            continue
        label, _, shown = part.partition("=")
        m = _NUM.search(shown)
        if not m or not label.strip():
            continue
        value = float(m.group().replace(",", ""))
        tail = shown[m.end():].strip().lower()
        word = re.match(r"[a-z]+", tail)
        if word and word.group() in _SCALE:
            value *= _SCALE[word.group()]
        items.append((label.strip()[:24], value, shown.strip()[:16]))
    if len(items) < 2:
        raise ValueError(f"chart needs at least two label=value items: {spec!r}")
    return title.strip()[:60], items[:6]


def chart_image(spec: str, size: tuple[int, int], style: dict | None = None) -> Image.Image:
    style = style or {}
    w, h = size
    accent = _rgb(style.get("accent"))
    bg = tuple(max(18, c) for c in _rgb(style.get("bg"), (14, 18, 26)))
    title, items = parse_chart(spec)
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (w, max(8, h // 60))], fill=accent)
    portrait = h > w
    pad = int(w * 0.07)
    top = int(h * 0.07) if portrait else int(h * 0.08)
    if title:
        tfont = _fit(d, title, w - 2 * pad, int(w * (0.075 if portrait else 0.045)))
        for i, line in enumerate(_wrap(d, title, tfont, w - 2 * pad)):
            d.text((w / 2, top + i * tfont.size * 1.15), line, font=tfont, fill=(255, 255, 255), anchor="ma")
        top += int(tfont.size * 2.6)
    peak = max(v for _, v, _ in items) or 1.0
    n = len(items)
    if portrait:
        # Horizontal bars in the upper 60 % of the frame, above the burned captions' zone.
        area_bottom = int(h * 0.62)
        slot = (area_bottom - top) / n
        bar_h = slot * 0.55
        lfont = _font(int(min(slot * 0.28, w * 0.055)))
        vfont = _font(int(min(slot * 0.34, w * 0.07)))
        for i, (label, value, shown) in enumerate(items):
            y = top + i * slot
            d.text((pad, y), label, font=lfont, fill=(225, 228, 235))
            bar_top = y + lfont.size * 1.25
            length = max(8, (w - 2 * pad) * 0.78 * value / peak)
            colour = accent if i == n - 1 else tuple(int(c * 0.55 + 40) for c in accent)
            d.rounded_rectangle([(pad, bar_top), (pad + length, bar_top + bar_h)], radius=int(bar_h * 0.18), fill=colour)
            d.text((pad + length + w * 0.02, bar_top + bar_h / 2), shown, font=vfont, fill=(255, 255, 255), anchor="lm")
    else:
        base = int(h * 0.80)
        gap = (w - 2 * pad) / n
        bar_w = gap * 0.55
        lfont = _font(int(h * 0.04))
        vfont = _font(int(h * 0.055))
        for i, (label, value, shown) in enumerate(items):
            x = pad + i * gap + (gap - bar_w) / 2
            height = max(8, (base - top - vfont.size * 1.6) * value / peak)
            colour = accent if i == n - 1 else tuple(int(c * 0.55 + 40) for c in accent)
            d.rounded_rectangle([(x, base - height), (x + bar_w, base)], radius=int(bar_w * 0.08), fill=colour)
            d.text((x + bar_w / 2, base - height - 10), shown, font=vfont, fill=(255, 255, 255), anchor="md")
            d.text((x + bar_w / 2, base + 14), label, font=lfont, fill=(225, 228, 235), anchor="ma")
    return img


# ---------- maps ----------

@lru_cache(maxsize=1)
def _countries() -> list[dict]:
    data = json.loads(GEO.read_text(encoding="utf-8"))
    out = []
    for f in data["features"]:
        p = f["properties"]
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        names = {str(p.get(k) or "").lower() for k in ("NAME", "NAME_LONG", "ADMIN", "NAME_EN", "ISO_A3")}
        out.append({"names": names - {""}, "rings": [poly[0] for poly in polys]})
    return out


def _match(name: str) -> list[dict]:
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    wanted = EU if key == "__eu__" else [key]
    return [c for c in _countries() if any(n in c["names"] for n in wanted)]


def parse_map(spec: str) -> tuple[list[str], str]:
    places, _, label = spec.partition("|")
    names = [p.strip() for p in places.split(",") if p.strip()]
    return names, label.strip()[:48]


def map_image(spec: str, size: tuple[int, int], style: dict | None = None) -> Image.Image:
    style = style or {}
    w, h = size
    accent = _rgb(style.get("accent"))
    bg = (8, 12, 22)
    names, label = parse_map(spec)
    hits = [c for n in names for c in _match(n)]
    if not hits:
        raise ValueError(f"map: no known country in {spec!r}")
    xs = [x for c in hits for ring in c["rings"] for x, _ in ring if -170 < x < 179]  # skip antimeridian slivers
    ys = [y for c in hits for ring in c["rings"] for _, y in ring]
    lon0, lon1, lat0, lat1 = min(xs), max(xs), min(ys), max(ys)
    # Pad to a readable neighbourhood (at least ~30 deg wide) and to the frame's aspect ratio.
    cx, cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
    span_x = max(lon1 - lon0, 30) * 1.6
    span_y = max(lat1 - lat0, 30 * h / w) * 1.6
    if span_x / span_y > w / h:
        span_y = span_x * h / w
    else:
        span_x = span_y * w / h
    left, top_lat = cx - span_x / 2, cy + span_y / 2

    def px(lon, lat):
        return ((lon - left) / span_x * w, (top_lat - lat) / span_y * h)

    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    hit_ids = {id(c) for c in hits}
    for c in _countries():
        fill = accent if id(c) in hit_ids else (66, 80, 104)
        outline = (255, 255, 255) if id(c) in hit_ids else (96, 110, 136)
        for ring in c["rings"]:
            pts = [px(x, y) for x, y in ring]
            if len(pts) > 2:
                d.polygon(pts, fill=fill, outline=outline)
    d.rectangle([(0, 0), (w, max(8, h // 60))], fill=accent)
    text = label or ", ".join(names)
    portrait = h > w
    font = _fit(d, text, int(w * 0.86), int(w * (0.085 if portrait else 0.05)))
    y = int(h * (0.07 if portrait else 0.06))
    for i, line in enumerate(_wrap(d, text.upper(), font, int(w * 0.86))):
        d.text((w / 2, y + i * font.size * 1.15), line, font=font, fill=(255, 255, 255), anchor="ma",
               stroke_width=max(2, font.size // 14), stroke_fill=(0, 0, 0))
    return img


def graphic_image(kind: str, spec: str, size: tuple[int, int], style: dict | None = None) -> Image.Image | None:
    """Image for a CHART:/MAP: shot, or None when the spec cannot be drawn (the caller falls back)."""
    try:
        return chart_image(spec, size, style) if kind == "chart" else map_image(spec, size, style)
    except Exception as e:
        log.warning("graphic %s skipped (%s): %r", kind, e, spec[:80])
        return None
