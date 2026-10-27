"""Stock footage from Pexels (free). Falls back to Pexels photos (Ken Burns) and finally to generated
gradient clips so a dry run works without any key."""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path

import requests

from .common import DATA_DIR, log

CACHE = DATA_DIR / "cache" / "pexels"
API = "https://api.pexels.com"


class Footage:
    def __init__(self, placeholder: bool = False):
        self.key = os.getenv("PEXELS_API_KEY")
        self.placeholder = placeholder or not self.key
        if self.placeholder:
            log.warning("footage: placeholder mode (no PEXELS_API_KEY)")
        self.used: set[int] = set()
        CACHE.mkdir(parents=True, exist_ok=True)

    def _get(self, path: str, **params) -> dict:
        for attempt in range(3):
            r = requests.get(f"{API}{path}", headers={"Authorization": self.key}, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("Pexels rate limited")

    def clip(self, query: str, min_sec: float, orientation: str = "landscape", mood: str = "calm") -> Path:
        """Return a local video file at least min_sec long (or a photo-based clip)."""
        if self.placeholder:
            return self._placeholder(query, min_sec, orientation)
        try:
            data = self._get("/videos/search", query=query, per_page=15, orientation=orientation, size="medium")
            vids = [v for v in data.get("videos", []) if v["id"] not in self.used and v["duration"] >= min(min_sec, 4)]
            vids.sort(key=lambda v: abs(v["duration"] - max(min_sec, 8)))
            for v in vids[:5]:
                files = [f for f in v["video_files"] if f.get("width") and f["width"] >= 1280 and f.get("file_type") == "video/mp4"]
                if not files:
                    continue
                files.sort(key=lambda f: f["width"])
                f = files[0]
                path = self._download(f["link"], f"v{v['id']}_{f['width']}.mp4")
                self.used.add(v["id"])
                return path
        except Exception as e:
            log.warning("footage video search failed for %r: %s", query, e)
        try:
            data = self._get("/v1/search", query=query, per_page=10, orientation=orientation)
            for ph in data.get("photos", []):
                if ph["id"] in self.used:
                    continue
                self.used.add(ph["id"])
                img = self._download(ph["src"]["large2x"], f"p{ph['id']}.jpg")
                return self._ken_burns(img, min_sec, orientation)
        except Exception as e:
            log.warning("footage photo search failed for %r: %s", query, e)
        return self._placeholder(query, min_sec, orientation)

    def _download(self, url: str, name: str) -> Path:
        path = CACHE / name
        if path.exists() and path.stat().st_size > 0:
            return path
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        return path

    @staticmethod
    def _dims(orientation: str) -> tuple[int, int]:
        return (1920, 1080) if orientation == "landscape" else (1080, 1920)

    def _ken_burns(self, img: Path, sec: float, orientation: str) -> Path:
        w, h = self._dims(orientation)
        out = CACHE / f"{img.stem}_kb_{int(sec)}_{orientation[0]}.mp4"
        if out.exists():
            return out
        frames = int(sec * 30) + 1
        vf = (f"scale={w*1.3:.0f}:{h*1.3:.0f}:force_original_aspect_ratio=increase,crop={w*1.3:.0f}:{h*1.3:.0f},"
              f"zoompan=z='min(zoom+0.0008,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(img), "-vf", vf, "-t", f"{sec:.2f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", str(out)], check=True)
        return out

    def _placeholder(self, query: str, sec: float, orientation: str) -> Path:
        w, h = self._dims(orientation)
        hue = int(hashlib.md5(query.encode()).hexdigest()[:2], 16)
        out = CACHE / f"ph_{hashlib.md5(query.encode()).hexdigest()[:8]}_{int(sec)}_{orientation[0]}.mp4"
        if out.exists():
            return out
        color = f"0x{(hue*3)%256:02x}{(hue*7)%256:02x}{(hue*11)%256:02x}"
        label = query.replace("'", "").replace(":", "")
        vf = f"drawtext=text='{label}':fontcolor=white@0.6:fontsize={h//18}:x=(w-text_w)/2:y=(h-text_h)/2,format=yuv420p"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:r=30:d={sec:.2f}", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", str(out)], check=True)
        return out
