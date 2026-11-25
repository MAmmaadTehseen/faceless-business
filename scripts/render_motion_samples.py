"""Render one portrait 3 s sample of every Remotion composition into motion/out/.

Stage 1 proof (2026-11-25): uses pipeline.remotion.render_segment exactly as
production would. Run from the repo root:

    .venv/bin/python scripts/render_motion_samples.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.remotion import available, render_segment  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "motion" / "out"

TW = {"accent": [231, 196, 122], "bg": [14, 18, 26]}
EV = {"accent": [34, 211, 238], "bg": [10, 14, 24]}
TT = {"accent": [167, 139, 250], "bg": [20, 14, 36]}

SAMPLES = [
    (
        "chart",
        "chart",
        TW,
        {
            "title": "War risk premium, % of ship value",
            "items": [
                {"label": "Before", "value": 0.05, "shown": "0.05%"},
                {"label": "After", "value": 0.5, "shown": "0.5%"},
            ],
        },
    ),
    (
        "map",
        "map",
        TW,
        {"countries": ["Iran", "Oman", "United Arab Emirates"], "label": "Strait of Hormuz"},
    ),
    (
        "text",
        "kinetic-text",
        TW,
        {"text": "Watch the insurers, not the navies"},
    ),
    (
        "timeline",
        "timeline",
        EV,
        {
            "title": "Voyager",
            "events": [
                {"when": "1977", "label": "Launch"},
                {"when": "1979", "label": "Jupiter"},
                {"when": "1980", "label": "Saturn"},
                {"when": "1990", "label": "Pale Blue Dot"},
                {"when": "2012", "label": "Interstellar space"},
            ],
        },
    ),
    (
        "scale",
        "scale",
        EV,
        {
            "title": "Earth vs Jupiter",
            "items": [
                {"label": "Earth", "value": 12742, "shown": "12,742 km"},
                {"label": "Jupiter", "value": 139820, "shown": "139,820 km"},
            ],
        },
    ),
    (
        "orbit",
        "orbit",
        EV,
        {"bodies": ["Earth", "Mars"], "label": "Transfer to Mars"},
    ),
    (
        "reveal",
        "word-reveal-cjk",
        TT,
        {"native": "水", "romanisation": "shuǐ", "language": "Chinese", "script": "cjk", "direction": "ltr"},
    ),
    (
        "reveal",
        "word-reveal-rtl",
        TT,
        {"native": "پانی", "romanisation": "paanī", "language": "Urdu", "script": "nastaliq", "direction": "rtl"},
    ),
]


def main() -> int:
    if not available():
        print("Remotion not available (node or motion/node_modules missing)")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    failures = []
    for kind, name, brand, props in SAMPLES:
        out = OUT / f"{name}.mp4"
        t0 = time.monotonic()
        try:
            render_segment(kind, props, seconds=3.0, orientation="portrait", out=out, brand=brand)
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures.append((name, exc))
            print(f"FAIL {name}: {str(exc)[-500:]}")
            continue
        dt = time.monotonic() - t0
        print(f"ok   {name}.mp4  {dt:5.1f}s  {out.stat().st_size/1024:8.0f} KiB")
    if failures:
        print(f"\n{len(failures)} render(s) failed")
        return 1
    print("\nall samples rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
