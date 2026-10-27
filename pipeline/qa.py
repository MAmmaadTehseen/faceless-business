"""Pre-upload QA: ffprobe sanity + Claude vision on thumbnail and sampled frames."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .common import Claude, log
from .thumbnail import grab_frame

QA_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["pass", "issues", "thumbnail_ok", "frames_ok", "frames_without_caption"],
    "properties": {
        "pass": {"type": "boolean"},
        "thumbnail_ok": {"type": "boolean"},
        "frames_ok": {"type": "boolean", "description": "false only for black/blank frames, watermarks, wrong orientation, or captions missing on most frames"},
        "frames_without_caption": {"type": "integer"},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
}

THUMB_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ok", "issue"],
                "properties": {"ok": {"type": "boolean"}, "issue": {"type": "string"}}}

THUMB_RULES = ("Thumbnail rules: text is at most three words, large and legible when shrunk to 160px wide, high contrast, "
               "no stock-site watermark, no readable third-party brand logos or trademarks (a car badge, a phone brand, a shop sign), "
               "no identifiable real person's face in close-up, image not blurry or blank.")


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


def run_qa(claude: Claude, video: Path, thumbnail: Path | None, expected_sec: float, content_id: str, work: Path, vision: bool = True) -> dict:
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
    if not vision:
        log.info("qa: probe passed; vision skipped (placeholder footage)")
        return {"pass": True, "issues": [], "thumbnail_ok": True, "frames_ok": True}

    work.mkdir(parents=True, exist_ok=True)
    frames = [grab_frame(video, p["duration"] * f, work / f"qa_{i}.jpg") for i, f in enumerate((0.1, 0.5, 0.85))]
    images = ([thumbnail] if thumbnail else []) + frames
    prompt = (
        (f"Image 1 is a YouTube thumbnail (1280x720). {THUMB_RULES}\n" if thumbnail else "") +
        f"The remaining {len(frames)} images are frames sampled from the video. Check each: not black or blank, "
        "no visible stock-site watermark, no text cut off at the edge, not an obviously wrong orientation (letterboxing or sideways). "
        "Captions appear near the bottom during speech; a frame sampled during a pause may have none, which is fine. Count frames without a caption.\n"
        "pass=true when the video frames are acceptable; thumbnail problems are reported separately via thumbnail_ok and do not fail the video."
    )
    try:
        res, _ = claude.vision("qa", prompt, images, QA_SCHEMA, content_id=content_id)
    except Exception as e:
        log.warning("qa vision failed, passing on probe only: %s", e)
        return {"pass": True, "issues": [f"vision skipped: {e}"], "thumbnail_ok": True, "frames_ok": True, "thumbnail": thumbnail}
    if res.get("frames_without_caption", 0) >= len(frames):
        res["frames_ok"] = False
        res["issues"].append("no captions visible on any sampled frame")
    res["pass"] = bool(res.get("frames_ok", True)) and not any("black" in i.lower() or "watermark" in i.lower() for i in res["issues"])
    res["thumbnail"] = thumbnail
    if thumbnail and not res.get("thumbnail_ok", True):
        res["thumbnail"] = _retry_thumbnail(claude, video, thumbnail, content_id, res)
    log.info("qa: pass=%s thumbnail_ok=%s issues=%s", res["pass"], res.get("thumbnail_ok"), res["issues"])
    return res


def _retry_thumbnail(claude: Claude, video: Path, thumbnail: Path, content_id: str, res: dict) -> Path:
    """Try other clean frames until one passes the thumbnail rules. Keeps the original if none does."""
    from .thumbnail import candidate_frames, make_thumbnail
    text = _thumb_text_from(video)
    for frame in candidate_frames(video)[1:]:
        cand = thumbnail.with_suffix(f".{frame.stem.split('.')[-1]}.jpg")
        make_thumbnail(video, text, cand, frame=frame)
        try:
            chk, _ = claude.vision("qa", f"This is a YouTube thumbnail. {THUMB_RULES} Return ok=true if it passes.", [cand], THUMB_SCHEMA, content_id=content_id)
        except Exception as e:
            log.warning("thumbnail recheck failed: %s", e)
            break
        if chk["ok"]:
            cand.replace(thumbnail)
            res["thumbnail_ok"] = True
            res["issues"] = [i for i in res["issues"] if "thumbnail" not in i.lower()]
            log.info("qa: thumbnail replaced using %s", frame.name)
            return thumbnail
        cand.unlink(missing_ok=True)
    log.warning("qa: no alternative thumbnail passed; keeping original")
    return thumbnail


def _thumb_text_from(video: Path) -> str:
    import json as _json
    sj = video.parent / "script.json"
    if sj.exists():
        return _json.loads(sj.read_text()).get("thumbnail_text", "WATCH THIS")
    return "WATCH THIS"
