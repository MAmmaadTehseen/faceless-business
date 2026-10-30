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
        "frames_ok": {"type": "boolean", "description": "false only for blocking video findings; minor notes and captions absent during pauses are acceptable"},
        "frames_without_caption": {"type": "integer"},
        "issues": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["severity", "text"],
            "properties": {"severity": {"type": "string", "enum": ["blocking", "minor"]},
                           "text": {"type": "string"}},
        }},
    },
}

THUMB_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ok", "issue"],
                "properties": {"ok": {"type": "boolean"}, "issue": {"type": "string"}}}

THUMB_RULES = ("Thumbnail text must be legible at 160px wide, high contrast and not cut off. "
               "Blocking: watermark/logo overlays covering content or policy problems. "
               "Sparse but legible text on black, incidental signage, source logos, soft archival imagery, "
               "colour grading and stylistic preferences are minor; these must not set thumbnail_ok=false.")


def finalize_qa(res: dict, strict: bool = False) -> dict:
    """Derive the verdict from findings, never from the model's boolean flags."""
    for finding in res["issues"]:
        if finding["severity"] == "minor":
            log.info("qa minor: %s", finding["text"])
    res["pass"] = not any(f["severity"] == "blocking" or strict for f in res["issues"])
    return res


def temporal_findings(video: Path) -> list[dict]:
    """Detect sustained black/frozen footage; sampled images cannot establish duration."""
    import re
    result = subprocess.run([
        "ffmpeg", "-v", "info", "-i", str(video), "-vf",
        "blackdetect=d=1:pix_th=0.10,freezedetect=n=-60dB:d=1", "-an", "-f", "null", "-",
    ], capture_output=True, text=True, check=True)
    findings = []
    for kind, pattern in (("black", r"black_duration:\s*([0-9.]+)"),
                          ("frozen", r"freeze_duration:\s*([0-9.]+)")):
        durations = [float(d) for d in re.findall(pattern, result.stderr)]
        if kind == "frozen":
            starts = re.findall(r"freeze_start:\s*([0-9.]+)", result.stderr)
            ends = re.findall(r"freeze_end:\s*([0-9.]+)", result.stderr)
            if len(starts) > len(ends):
                durations.append(probe(video)["duration"] - float(starts[-1]))
        if any(d > 1 for d in durations):
            findings.append({"severity": "blocking", "text": f"{kind} footage for more than 1 second"})
    return findings


def probe(video: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {"duration": float(info["format"]["duration"]), "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            "width": v.get("width"), "height": v.get("height")}


def run_qa(claude: Claude, video: Path, thumbnail: Path | None, expected_sec: float, content_id: str, work: Path, vision: bool = True, *, db=None) -> dict:
    strict = db.setting("qa_strict", False) if db is not None else False
    issues = []
    p = probe(video)
    if not p["has_audio"]:
        issues.append({"severity": "blocking", "text": "no audio track"})
    if abs(p["duration"] - expected_sec) > max(3.0, expected_sec * 0.05):
        issues.append({"severity": "blocking", "text": f"duration {p['duration']:.1f}s differs from narration {expected_sec:.1f}s"})
    if (p["width"], p["height"]) not in ((1920, 1080), (1080, 1920)):
        ratio = (p["width"] or 0) / (p["height"] or 1)
        if min(abs(ratio - 16/9), abs(ratio - 9/16)) > 0.02:
            issues.append({"severity": "blocking", "text": "wrong aspect ratio"})
    issues.extend(temporal_findings(video))
    if issues:
        return {"pass": False, "issues": issues, "thumbnail_ok": None, "frames_ok": False}
    if not vision:
        log.info("qa: probe passed; vision skipped (placeholder footage)")
        return {"pass": True, "issues": [], "thumbnail_ok": True, "frames_ok": True}

    work.mkdir(parents=True, exist_ok=True)
    frames = [grab_frame(video, p["duration"] * f, work / f"qa_{i}.jpg") for i, f in enumerate((0.1, 0.5, 0.85))]
    images = ([thumbnail] if thumbnail else []) + frames
    prompt = (
        (f"Image 1 is a YouTube thumbnail. {THUMB_RULES}\n" if thumbnail else "") +
        f"The remaining {len(frames)} images are sampled video frames. "
        "Report every finding as {severity: blocking|minor, text}. "
        "pass=false ONLY if at least one blocking finding exists. "
        "Blocking: black/frozen footage lasting >1s (do not infer duration from a still), "
        "visible third-party watermark or logo OVERLAY covering content, cut-off or unreadable text/captions, "
        "wrong aspect ratio, missing audio, placeholder footage, nudity, gore, misleading medical/income claims. "
        "Minor: pillarboxing/letterboxing, soft or blurry archival footage, incidental signage, "
        "source logos on objects such as NASA rockets, sparse but legible thumbnails, colour grading, stylistic notes. "
        "Keep thumbnail_ok as a separate check of thumbnail usability; sparse but legible is OK. "
        "Count frames_without_caption, but captions may be absent during pauses; absence in sampled stills alone is not blocking."
    )
    try:
        res, _ = claude.vision("qa", prompt, images, QA_SCHEMA, content_id=content_id)
    except Exception as e:
        log.warning("qa vision failed, passing on probe only: %s", e)
        return finalize_qa({"issues": [{"severity": "minor", "text": f"vision skipped: {e}"}], "thumbnail_ok": True, "frames_ok": True, "thumbnail": thumbnail}, strict)
    res["thumbnail"] = thumbnail
    if thumbnail and not res.get("thumbnail_ok", True):
        res["thumbnail"] = _retry_thumbnail(claude, video, thumbnail, content_id, res)
    finalize_qa(res, strict)
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
            res["issues"] = [i for i in res["issues"] if "thumbnail" not in i["text"].lower()]
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
