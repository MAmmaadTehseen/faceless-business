"""Generate a channel brand kit (avatar, YouTube banner, Facebook cover, watermark, square card).
Usage: python scripts/brand.py '<json config>'   (see CHANNELS at the bottom for the three channels)
       python scripts/brand.py all
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BOLD = str(ROOT / "assets/fonts/DejaVuSans-Bold.ttf")
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
WHITE = (255, 255, 255)


def f(size, bold=True):
    return ImageFont.truetype(BOLD if bold else REG, size)


def build(cfg: dict):
    out = ROOT / cfg["out"]; out.mkdir(parents=True, exist_ok=True)
    BG, BG2, ACC, MUTED = (tuple(cfg[k]) for k in ("bg", "bg2", "accent", "muted"))

    def gradient(w, h):
        im = Image.new("RGB", (w, h), BG); d = ImageDraw.Draw(im)
        for y in range(h):
            t = y / h
            d.line([(0, y), (w, y)], fill=tuple(int(BG[i] + (BG2[i] - BG[i]) * t) for i in range(3)))
        return im

    def mark(s):
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, s, s), radius=int(s * 0.22), fill=BG)
        fs = int(s * 0.36); fnt = f(fs); tw = d.textlength(cfg["mono"], font=fnt)
        a = int(s * 0.11); t = max(4, int(s * 0.06)); total = tw + int(s * 0.08) + a
        x0 = (s - total) / 2; cy = s * 0.5
        d.text((x0, cy - fs * 0.60), cfg["mono"], font=fnt, fill=WHITE)
        cx = x0 + tw + int(s * 0.08)
        shape = cfg.get("shape", "chevron")
        if shape == "chevron":
            d.line([(cx, cy - a), (cx + a, cy), (cx, cy + a)], fill=ACC, width=t, joint="curve")
        elif shape == "compass":  # diamond
            d.polygon([(cx + a / 2, cy - a), (cx + a, cy), (cx + a / 2, cy + a), (cx, cy)], fill=ACC)
        elif shape == "orbit":  # ring with dot
            d.ellipse((cx - 2, cy - a, cx + 2 * a - 2, cy + a), outline=ACC, width=t)
            d.ellipse((cx + a - 2 - t, cy - a - t, cx + a - 2 + t, cy - a + t), fill=WHITE)
        return im

    def wordmark(d, x, y, scale=1.0, align="left"):
        f1 = f(int(96 * scale)); f2 = f(int(34 * scale), bold=False)
        l1, l2, tag = cfg["line1"], cfg["line2"], cfg["tagline"]
        w1, w2, wt = (d.textlength(t, font=ft) for t, ft in ((l1, f1), (l2, f1), (tag, f2)))
        x1, x2, xt = ((x - w1 / 2, x - w2 / 2, x - wt / 2) if align == "center" else (x, x, x))
        d.text((x1, y), l1, font=f1, fill=WHITE)
        d.text((x2, y + int(104 * scale)), l2, font=f1, fill=ACC)
        d.text((xt, y + int(230 * scale)), tag, font=f2, fill=MUTED)

    # avatar
    im = gradient(800, 800); m = mark(576); im.paste(m, (112, 112), m)
    im.save(out / "avatar-800.png"); im.resize((320, 320), Image.LANCZOS).save(out / "avatar-320.png")
    # youtube banner (safe area 1546x423 centred)
    W, H = 2560, 1440; im = gradient(W, H); d = ImageDraw.Draw(im)
    for gx in range(0, W, 128): d.line([(gx, 0), (gx, H)], fill=tuple(min(255, c + 7) for c in BG), width=1)
    for gy in range(0, H, 128): d.line([(0, gy), (W, gy)], fill=tuple(min(255, c + 7) for c in BG), width=1)
    sx, sy = (W - 1546) // 2, (H - 423) // 2
    m = mark(300); im.paste(m, (sx + 20, sy + 60), m); d = ImageDraw.Draw(im)
    wordmark(d, sx + 360, sy + 40, 0.95)
    d.text((sx + 360, sy + 330), cfg["footer"], font=f(30, bold=False), fill=MUTED)
    im.save(out / "youtube-banner-2560x1440.png")
    # facebook cover
    W, H = 1640, 624; im = gradient(W, H); m = mark(260); im.paste(m, (120, (H - 260) // 2), m)
    d = ImageDraw.Draw(im); wordmark(d, 430, 150, 0.85); im.save(out / "facebook-cover-1640x624.png")
    # watermark + square card
    mark(150).save(out / "watermark-150.png")
    W = 1080; im = gradient(W, W); m = mark(280); im.paste(m, ((W - 280) // 2, 190), m)
    d = ImageDraw.Draw(im); wordmark(d, W // 2, 540, 0.8, "center"); im.save(out / "profile-card-1080.png")
    print("brand kit:", out)


CHANNELS = {
    "futurework": {"out": "assets/brand/futurework", "mono": "FW", "shape": "chevron", "bg": [15, 23, 42], "bg2": [24, 33, 62], "accent": [251, 191, 36], "muted": [148, 163, 184],
                   "line1": "FUTURE WORK", "line2": "EXPLAINED", "tagline": "How technology changes your job, your money and your safety.", "footer": "New videos every week  ·  youtube.com/@futurework.explained"},
    "tradewinds": {"out": "assets/brand/tradewinds", "mono": "TW", "shape": "compass", "bg": [28, 16, 16], "bg2": [64, 22, 22], "accent": [231, 196, 122], "muted": [196, 170, 150],
                   "line1": "TRADE WINDS", "line2": "REPORT", "tagline": "Who holds the power and who pays the price: trade, energy, chips and money.", "footer": "Three videos a week  ·  youtube.com/@tradewindsreport"},
    "escapevelocity": {"out": "assets/brand/escapevelocity", "mono": "EV", "shape": "orbit", "bg": [4, 7, 14], "bg2": [8, 20, 40], "accent": [34, 211, 238], "muted": [140, 170, 190],
                       "line1": "ESCAPE", "line2": "VELOCITY", "tagline": "Launches, missions and the science that gets us off this rock.", "footer": "Three videos a week  ·  youtube.com/@escapevelocitydaily"},
}

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "all":
        for c in CHANNELS.values(): build(c)
    elif arg in CHANNELS:
        build(CHANNELS[arg])
    else:
        build(json.loads(arg))
