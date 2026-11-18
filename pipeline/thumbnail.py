"""Thumbnail: a frame from the video + big three-word text. 1280x720 JPEG under 2MB."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import ASSETS_DIR, log


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in sorted((ASSETS_DIR / "fonts").glob("*.ttf")):
        return ImageFont.truetype(str(p), size)
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(cand).exists():
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def grab_frame(video: Path, at_sec: float, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at_sec:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)], check=True)
    return out


def candidate_frames(video: Path) -> list[Path]:
    c = [video.with_suffix(".clean.jpg")] + [video.with_suffix(f".clean{i}.jpg") for i in range(1, 6)]
    found = [p for p in c if p.exists()]
    if len(found) <= 1:
        # Older renders: grab frames inside the silent gaps between paragraphs (no caption burned there).
        import json
        tj = video.parent / "voice_timings.json"
        if tj.exists():
            timings = json.loads(tj.read_text())
            for i, t in enumerate(timings[2:14:2], start=1):
                p = video.with_suffix(f".gap{i}.jpg")
                if not p.exists():
                    grab_frame(video, t["end"] + 0.25, p)
                found.append(p)
    return found


def frame_score(path: Path) -> float:
    """Prefer sharp, contrasty, well-lit frames: variance of a downscaled grey copy minus a dark/flat penalty."""
    from PIL import ImageStat
    g = Image.open(path).convert("L").resize((160, 90))
    st = ImageStat.Stat(g)
    mean, std = st.mean[0], st.stddev[0]
    edges = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0]
    penalty = max(0.0, 70 - mean) + max(0.0, mean - 200)
    # Flat single-hue frames (branded fallback cards, colour washes) are not footage: one hue
    # covering most of the image costs more than any contrast it offers.
    hsv = Image.open(path).convert("RGB").resize((80, 45)).convert("HSV")
    h = hsv.split()[0].histogram()
    sat = ImageStat.Stat(hsv.split()[1]).mean[0]
    dominant = max(sum(h[(i + k) % 256] for k in range(-8, 9)) for i in range(0, 256, 4)) / (80 * 45)
    if dominant > 0.6 and sat > 90:
        penalty += 150
    return std + edges * 2 - penalty


def best_frame(video: Path) -> Path | None:
    frames = candidate_frames(video)
    return max(frames, key=frame_score) if frames else None


def thumbnail_lines(text: str) -> list[str]:
    """Up to 3 lines, at most 5 words, subject first; lines wrap at 12 characters."""
    words = [w for w in text.upper().split() if w][:5]
    lines, cur = [], ""
    for w in words:
        if cur and (len(cur) + 1 + len(w) > 12):
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:3]


def make_thumbnail(video: Path, text: str, out: Path, at_sec: float = 12.0, frame: Path | None = None, accent: tuple | None = None) -> Path:
    """Growth log 2026-11-19: subject-first text, big and high-contrast, on the sharpest clean frame.

    Research consensus (vidIQ 2026 study and others): 1-5 words that say what the video is about,
    one dominant element, strong contrast; vague three-word teasers do not earn clicks.
    """
    clean = frame or best_frame(video) or video.with_suffix(".clean.jpg")
    if clean.exists():
        frame = clean
    else:
        frame = out.with_suffix(".frame.jpg")
        grab_frame(video, at_sec, frame)
    img = Image.open(frame).convert("RGB").resize((1280, 720))
    # slight blur + darken the left 60% so the text block owns the frame; the subject stays visible on the right
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(1280):
        a = int(235 * max(0.0, 1 - x / 860) ** 0.7)
        d.line([(x, 0), (x, 720)], fill=(0, 0, 0, a))
    for y in range(720):
        a = int(90 * (y / 720) ** 2)
        d.line([(0, y), (1280, y)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)
    lines = thumbnail_lines(text)
    longest = max((len(l) for l in lines), default=1)
    size = 190 if longest <= 7 else 160 if longest <= 9 else 130
    font = _font(size)
    lh = int(size * 1.0)
    block = lh * len(lines)
    y = (720 - block) // 2 + 10
    accent = tuple(accent or (255, 214, 0))
    draw.rectangle([(0, 0), (18, 720)], fill=accent + (255,))  # channel accent bar
    for i, line in enumerate(lines):
        color = accent if i == len(lines) - 1 and len(lines) > 1 else (255, 255, 255)
        yy = y + i * lh
        for dx, dy in ((-5, -5), (5, -5), (-5, 5), (5, 5), (0, 8), (-7, 0), (7, 0)):
            draw.text((64 + dx, yy + dy), line, font=font, fill=(0, 0, 0))
        draw.text((64, yy), line, font=font, fill=color)
    img = img.convert("RGB")
    q = 90
    while True:
        img.save(out, "JPEG", quality=q, optimize=True)
        if out.stat().st_size < 1_900_000 or q <= 50:
            break
        q -= 10
    if frame.name.endswith(".frame.jpg"):
        frame.unlink(missing_ok=True)
    log.info("thumbnail: %s (%d KB)", out, out.stat().st_size // 1024)
    return out
