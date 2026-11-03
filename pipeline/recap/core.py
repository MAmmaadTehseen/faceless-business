"""Local job files, validation and deterministic planning. No network imports."""
from __future__ import annotations

import json
import math
import re
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "out" / "recap"
STAGES = ("probe", "transcribe", "scenes", "script", "select", "voice", "assembly", "thumbnail", "qa")
PIECES = ("long", "short1", "short2", "short3", "short4")


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str))
    temp.replace(path)


def job_dir(job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("Invalid project id")
    path = OUTPUT / job_id
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Project not found")
    return path


def validate_path(value):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("Enter an existing absolute local video path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Video path must be absolute")
    path = path.resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}:
        raise ValueError("Select an existing regular video file")
    info = probe(path)
    if not info.get("width") or not info.get("height") or not math.isfinite(info["duration"]) or info["duration"] <= 0:
        raise ValueError("Selected file has no valid video stream")
    return path, info


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(path)], capture_output=True, text=True, check=True, timeout=60)
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"duration": float(data.get("format", {}).get("duration", 0)), "width": video.get("width"), "height": video.get("height"), "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}


def rights_gate(rights):
    if not isinstance(rights, dict) or rights.get("basis") not in {"public domain", "Creative Commons", "written permission", "own work"}:
        raise ValueError("Select a supported Rights basis")
    result = {"basis": rights["basis"]}
    if result["basis"] == "Creative Commons":
        url = urlparse(str(rights.get("url", "")))
        if not isinstance(rights.get("licence"), str) or not rights["licence"].strip() or url.scheme not in {"https", "http"} or not url.netloc:
            raise ValueError("Creative Commons requires a licence and valid URL")
        result.update(licence=str(rights["licence"]).strip(), url=str(rights["url"]).strip())
    if result["basis"] == "written permission":
        if not isinstance(rights.get("note"), str) or not rights["note"].strip():
            raise ValueError("Written permission requires a note")
        result["note"] = str(rights["note"]).strip()
    return result


def plan(duration):
    # Budget estimate includes transcript input, all five scripts and five vision checks.
    from pipeline.common import PRICES, MODEL
    prices = PRICES.get(MODEL, PRICES["claude-opus-5-5"])
    estimate = round((duration * 5 + 18000) * prices["in"] / 1e6 + 17000 * prices["out"] / 1e6, 2)
    return {"stages": list(STAGES), "pieces": list(PIECES), "estimate_usd": estimate,
            "estimate_note": "Estimate, not a price cap; regeneration and retries cost extra.", "long_seconds": [300, 540], "short_max_seconds": 59}


def create(payload):
    rights = rights_gate(payload.get("rights"))
    title = payload.get("title", "")
    if not isinstance(title, str):
        raise ValueError("Film title must be text")
    title = title.strip()
    year = int(payload.get("year", 0))
    if not title or len(title) > 200 or not 1888 <= year <= 2100:
        raise ValueError("Film title and valid year are required")
    path, info = validate_path(payload.get("path"))
    bed = float(payload.get("bed", 0))
    if not math.isfinite(bed) or not 0 <= bed <= 0.08:
        raise ValueError("Original-audio bed must be between 0 and 0.08")
    job_id = uuid.uuid4().hex
    work = OUTPUT / job_id
    work.mkdir(parents=True)
    dump(work / "rights.json", rights)
    state = {"id": job_id, "title": title, "year": year, "source": str(path), "probe": info,
             "bed": bed, "status": "estimated", "stage": "probe", "percent": 0,
             "plan": plan(info["duration"]), "items": {}}
    dump(work / "state.json", state)
    return state


def srt(segments):
    def stamp(seconds):
        value = max(0, round(float(seconds) * 1000))
        hours, value = divmod(value, 3600000)
        minutes, value = divmod(value, 60000)
        seconds, ms = divmod(value, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"
    rows = []
    for segment in segments:
        if segment["end"] <= segment["start"]:
            continue
        text = str(segment["text"]).replace("-->", "→").strip()
        if text:
            rows.append(f"{len(rows)+1}\n{stamp(segment['start'])} --> {stamp(segment['end'])}\n{text}\n")
    return "\n".join(rows)


def public_state(work):
    state = json.loads((work / "state.json").read_text())
    state.pop("source", None)
    state["rights"] = json.loads((work / "rights.json").read_text())
    return state
