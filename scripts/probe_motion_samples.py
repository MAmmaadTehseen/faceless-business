"""ffprobe + frame extraction for the motion samples (stage 1 proof)."""
import subprocess
import sys
from pathlib import Path

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


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{proc.stderr[-800:]}")
    return proc.stdout.strip()


for name in NAMES:
    mp4 = OUT / f"{name}.mp4"
    dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1", str(mp4)])
    dim = run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
               "-of", "csv=p=0", str(mp4)])
    kib = mp4.stat().st_size / 1024
    print(f"{name}.mp4  duration={dur}s  {dim}  {kib:.0f} KiB")
    for tag, t in (("a", 0.3), ("b", 2.5)):
        png = OUT / f"{name}_{tag}.png"
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(mp4),
             "-frames:v", "1", str(png)])
        if not png.exists():
            sys.exit(f"missing {png}")
print("\nframes extracted")
