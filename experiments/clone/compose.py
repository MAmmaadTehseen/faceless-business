"""Compose the final 1080x1920 sample: presenter clip + narration + captions, in full, corner or hybrid layout.

  python compose.py --presenter results/presenter.mp4 --audio results/narration.wav --srt results/narration.srt \
      --out results/sample_60s.mp4 --layout hybrid [--stock path.mp4] [--full-head 8 --full-tail 5]
hybrid = presenter full-screen for the hook (first --full-head s) and close (last --full-tail s), corner box over the
background in between. Background is --stock if given, else a dark branded gradient. Captions burn in via ffmpeg
subtitles (word-timed cues from clone_voice.py). ffmpeg only; no model calls.
"""
import sys, argparse, subprocess, shlex
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from common import *

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--presenter", required=True); ap.add_argument("--audio", required=True); ap.add_argument("--srt"); ap.add_argument("--out", required=True)
    ap.add_argument("--layout", default="hybrid", choices=["full", "corner", "hybrid"]); ap.add_argument("--stock")
    ap.add_argument("--full-head", type=float, default=8); ap.add_argument("--full-tail", type=float, default=5); ap.add_argument("--corner", type=int, default=420)
    a = ap.parse_args(); guard(); dur = duration(a.audio); W, H = 1080, 1920; c = a.corner
    inputs = ["-i", a.presenter, "-i", a.audio]
    bg = f"color=c=0x101820:s={W}x{H}:r=25:d={dur:.3f}[bg0];[bg0]drawbox=x=0:y={H-700}:w={W}:h=700:color=0x1b2838@0.9:t=fill[bg]" if not a.stock else None
    if a.stock: inputs += ["-stream_loop", "-1", "-i", a.stock]; bg = f"[2:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},trim=duration={dur:.3f},setpts=PTS-STARTPTS[bg]"
    pres = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts=PTS-STARTPTS[full];[0:v]scale={c}:{c}:force_original_aspect_ratio=increase,crop={c}:{c},setpts=PTS-STARTPTS[small]"
    if a.layout == "full": chain = f"{pres};[full]null[v0]"
    elif a.layout == "corner": chain = f"{bg};{pres};[bg][small]overlay=x={W-c-40}:y=120[v0]"
    else:
        h0, h1 = a.full_head, max(a.full_head, dur - a.full_tail)
        chain = (f"{bg};{pres};[bg][small]overlay=x={W-c-40}:y=120:enable='between(t,{h0},{h1})'[mid];"
                 f"[mid][full]overlay=x=0:y=0:enable='lt(t,{h0})+gte(t,{h1})'[v0]")
    if a.srt:
        style = "FontName=DejaVu Sans,FontSize=19,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=0,Alignment=2,MarginV=260"
        chain += f";[v0]subtitles={shlex.quote(a.srt)}:force_style='{style}'[v]"
    else: chain += ";[v0]null[v]"
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", chain, "-map", "[v]", "-map", "1:a",
           "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", a.out]
    print(" ".join(shlex.quote(x) for x in cmd)); subprocess.run(cmd, check=True); print("wrote", a.out, round(duration(a.out), 2), "s")

if __name__ == "__main__": main()
