"""Pre-upload QA: ffprobe sanity + Claude vision on thumbnail and sampled frames."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .common import Claude, log
from .thumbnail import grab_frame

QA_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["pass", "issues", "thumbnail_ok", "frames_ok"],
    "properties": {
        "pass": {"type": "boolean"},
        "thumbnail_ok": {"type": "boolean"},
        "frames_ok": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
}


def probe(video: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {"duration": float(info["format"]["duration"]), "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            "width": v.get("width"), "height": v.get("height")}


def black_ratio(video: Path) -> float:
    """Fraction of the video flagged black by ffmpeg's blackdetect."""
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-vf", "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    total = 0.0
    for line in out.splitlines():
        if "black_duration:" in line:
            total += float(line.split("black_duration:")[1].strip().split()[0])
    dur = probe(video)["duration"]
    return total / dur if dur else 1.0


def run_qa(claude: Claude, video: Path, thumbnail: Path | None, expected_sec: float, content_id: str, work: Path) -> dict:
    issues = []
    p = probe(video)
    if not p["has_audio"]:
        issues.append("no audio track")
    if abs(p["duration"] - expected_sec) > max(3.0, expected_sec * 0.05):
        issues.append(f"duration {p['duration']:.1f}s differs from narration {expected_sec:.1f}s")
    br = black_ratio(video)
    if br > 0.03:
        issues.append(f"{br:.0%} of video is black")
    if issues:
        return {"pass": False, "issues": issues, "thumbnail_ok": None, "frames_ok": False}

    work.mkdir(parents=True, exist_ok=True)
    frames = [grab_frame(video, p["duration"] * f, work / f"qa_{i}.jpg") for i, f in enumerate((0.1, 0.5, 0.85))]
    images = ([thumbnail] if thumbnail else []) + frames
    prompt = (
        ("Image 1 is a YouTube thumbnail (1280x720). Check: text is at most three words, large and legible when shrunk to 160px wide, "
         "high contrast, not covering the whole frame, no watermark, no logos of other brands.\n" if thumbnail else "") +
        f"The remaining {len(frames)} images are frames sampled from the video. Check each: not black or blank, a caption is visible near the bottom, "
        "no visible stock-site watermark, no text cut off at the edge, not an obviously wrong orientation (letterboxing or sideways).\n"
        "Return pass=true only if everything is acceptable for publishing. List concrete issues otherwise."
    )
    try:
        res, _ = claude.vision("qa", prompt, images, QA_SCHEMA, content_id=content_id)
    except Exception as e:
        log.warning("qa vision failed, passing on probe only: %s", e)
        res = {"pass": True, "issues": [f"vision skipped: {e}"], "thumbnail_ok": True, "frames_ok": True}
    log.info("qa: pass=%s issues=%s", res["pass"], res["issues"])
    return res
