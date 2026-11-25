"""Verify the extracted motion frames programmatically (no eyes needed).

Checks per sample:
- a (0.3 s) and b (2.5 s) differ -> animation is moving.
- b contains the channel accent colour somewhere -> brand applied.
- the late frame is not a blank single colour.
"""
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "motion" / "out"
NAMES = [
    "chart",
    "map",
    "kinetic-text",
    "timeline",
    "scale",
    "orbit",
    "word-reveal-cjk",
    "word-reveal-rtl",
]

ACCENTS = {
    "chart": (231, 196, 122),
    "map": (231, 196, 122),
    "kinetic-text": (231, 196, 122),
    "timeline": (34, 211, 238),
    "scale": (34, 211, 238),
    "orbit": (34, 211, 238),
    "word-reveal-cjk": (167, 139, 250),
    "word-reveal-rtl": (167, 139, 250),
}


def near(c, target, tol=36):
    return all(abs(c[i] - target[i]) <= tol for i in range(3))


fails = []
for name in NAMES:
    a = Image.open(OUT / f"{name}_a.png").convert("RGB")
    b = Image.open(OUT / f"{name}_b.png").convert("RGB")
    pa, pb = list(a.getdata()), list(b.getdata())
    diff = sum(1 for x, y in zip(pa[::37], pb[::37]) if x != y) / (len(pa) // 37 + 1)
    # KineticText's sample has no digits, so per spec every word is white and
    # no accent colour is expected; check for white text instead.
    target = (255, 255, 255) if name == "kinetic-text" else ACCENTS[name]
    accent_hit = any(near(c, target) for c in pb[::29])
    colours = len(set(pb[::53]))
    status = "ok  "
    if diff < 0.02 or not accent_hit or colours < 8:
        status = "FAIL"
        fails.append(name)
    print(f"{status} {name:18s} moving={diff:6.1%}  accent={'yes' if accent_hit else 'NO'}  distinct_colours={colours}")

print("\nFAILURES:", fails if fails else "none")
raise SystemExit(1 if fails else 0)
