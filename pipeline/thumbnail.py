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


def make_thumbnail(video: Path, text: str, out: Path, at_sec: float = 12.0, frame: Path | None = None) -> Path:
    clean = frame or video.with_suffix(".clean.jpg")
    if clean.exists():
        frame = clean
    else:
        frame = out.with_suffix(".frame.jpg")
        grab_frame(video, at_sec, frame)
    img = Image.open(frame).convert("RGB").resize((1280, 720))
    # darken left/bottom for contrast
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(720):
        a = int(170 * (y / 720) ** 1.6)
        d.line([(0, y), (1280, y)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)
    words = text.upper().split()[:3]
    size = 150 if len(" ".join(words)) <= 10 else 120
    font = _font(size)
    y = 720 - 60 - size * len(words) * 0.95
    for i, w in enumerate(words):
        color = (255, 214, 0) if i == len(words) - 1 else (255, 255, 255)
        yy = y + i * size * 0.95
        for dx, dy in ((-4, -4), (4, -4), (-4, 4), (4, 4), (0, 6)):
            draw.text((60 + dx, yy + dy), w, font=font, fill=(0, 0, 0))
        draw.text((60, yy), w, font=font, fill=color)
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
