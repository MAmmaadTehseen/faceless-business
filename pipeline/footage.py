"""Stock footage from Pixabay and/or Pexels (both free). Order: Pixabay video, Pexels video, Pixabay photo,
Pexels photo (Ken Burns), then a renderer-owned branded card. Explicit dry runs use placeholders."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from pathlib import Path

import requests

from .common import DATA_DIR, log

CACHE = DATA_DIR / "cache" / "pexels"
API = "https://api.pexels.com"


class Footage:
    def __init__(self, placeholder: bool = False, providers: list[str] | None = None):
        self.providers = providers or ["pixabay", "pexels"]
        self.key = os.getenv("PEXELS_API_KEY")
        self.pb_key = os.getenv("PIXABAY_API_KEY")
        self.placeholder = placeholder or not (self.key or self.pb_key)
        if self.placeholder:
            log.warning("footage: placeholder mode (no PIXABAY_API_KEY or PEXELS_API_KEY)")
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

    def clip(self, query: str, min_sec: float, orientation: str = "landscape", mood: str = "calm") -> Path | None:
        """Return footage or None so the renderer can try its next candidate query."""
        if self.placeholder:
            return self._placeholder(query, min_sec, orientation)
        if "nasa" in self.providers:
            try:
                path = self._nasa_video(query, min_sec, orientation)
                if path:
                    return path
            except Exception as e:
                log.warning("nasa video failed for %r: %s", query, e)
        if self.pb_key:
            try:
                path = self._pixabay_video(query, min_sec, orientation)
                if path:
                    return path
            except Exception as e:
                log.warning("pixabay video failed for %r: %s", query, e)
        if self.key:
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
                log.warning("pexels video search failed for %r: %s", query, e)
        if self.pb_key:
            try:
                path = self._pixabay_photo(query, min_sec, orientation)
                if path:
                    return path
            except Exception as e:
                log.warning("pixabay photo failed for %r: %s", query, e)
        if self.key:
            try:
                data = self._get("/v1/search", query=query, per_page=10, orientation=orientation)
                for ph in data.get("photos", []):
                    if ph["id"] in self.used:
                        continue
                    self.used.add(ph["id"])
                    img = self._download(ph["src"]["large2x"], f"p{ph['id']}.jpg")
                    return self._ken_burns(img, min_sec, orientation)
            except Exception as e:
                log.warning("pexels photo search failed for %r: %s", query, e)
        return None

    # ---------- NASA Image and Video Library (public domain) ----------
    def _nasa_video(self, query: str, min_sec: float, orientation: str) -> Path | None:
        r = requests.get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "video", "page_size": 20}, timeout=30)
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])
        for it in items:
            data = (it.get("data") or [{}])[0]
            nid = data.get("nasa_id")
            if not nid or f"nasa{nid}" in self.used:
                continue
            try:
                assets = requests.get(f"https://images-api.nasa.gov/asset/{nid}", timeout=30).json().get("collection", {}).get("items", [])
            except Exception:
                continue
            urls = [a["href"] for a in assets if a.get("href", "").endswith(".mp4")]
            pick = next((u for u in urls if "~medium" in u), None) or next((u for u in urls if "~small" in u), None) or (urls[0] if urls else None)
            if not pick:
                continue
            self.used.add(f"nasa{nid}")
            path = self._download(pick, f"nasa_{re.sub(r'[^A-Za-z0-9]+', '_', nid)[:60]}.mp4")
            if path.stat().st_size < 50_000:
                continue
            return path
        return None

    # ---------- Pixabay ----------
    def _pb(self, path: str, **params) -> dict:
        for attempt in range(3):
            r = requests.get(f"https://pixabay.com/api/{path}", params={"key": self.pb_key, "safesearch": "true", **params}, timeout=30)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("Pixabay rate limited")

    def _pixabay_video(self, query: str, min_sec: float, orientation: str) -> Path | None:
        data = self._pb("videos/", q=query[:100], per_page=20, video_type="film")
        want_landscape = orientation == "landscape"
        hits = []
        for h in data.get("hits", []):
            key = f"pb{h['id']}"
            if key in self.used or h.get("duration", 0) < min(min_sec, 4):
                continue
            f = h["videos"].get("medium") or h["videos"].get("large") or h["videos"].get("small")
            if not f or not f.get("url"):
                continue
            is_landscape = (f.get("width") or 16) >= (f.get("height") or 9)
            score = (0 if is_landscape == want_landscape else 1, abs(h["duration"] - max(min_sec, 8)))
            hits.append((score, key, f["url"], f.get("width", 0)))
        hits.sort()
        for _, key, url, w in hits[:1]:
            self.used.add(key)
            return self._download(url, f"{key}_{w}.mp4")
        return None

    def _pixabay_photo(self, query: str, min_sec: float, orientation: str) -> Path | None:
        data = self._pb("", q=query[:100], per_page=20, image_type="photo", orientation="horizontal" if orientation == "landscape" else "vertical", min_width=1280)
        for h in data.get("hits", []):
            key = f"pbp{h['id']}"
            if key in self.used:
                continue
            self.used.add(key)
            img = self._download(h["largeImageURL"], f"{key}.jpg")
            return self._ken_burns(img, min_sec, orientation)
        return None

    def _download(self, url: str, name: str) -> Path:
        path = CACHE / name
        if path.exists() and path.stat().st_size > 0:
            return path
        # Never let a failed response become a valid-looking cached download.
        partial = path.with_suffix(path.suffix + ".part")
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(partial, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            if not partial.stat().st_size:
                raise ValueError("empty footage download")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
        return path

    @staticmethod
    def _dims(orientation: str) -> tuple[int, int]:
        return (1920, 1080) if orientation == "landscape" else (1080, 1920)

    def _ken_burns(self, img: Path, sec: float, orientation: str) -> Path:
        w, h = self._dims(orientation)
        out = CACHE / f"{img.stem}_kb_motion2_{sec:.6f}_{orientation[0]}.mp4"
        if out.exists() and out.stat().st_size > 0:
            return out
        frames = int(sec * 30) + 1
        vf = (f"scale={w*1.3:.0f}:{h*1.3:.0f}:force_original_aspect_ratio=increase,crop={w*1.3:.0f}:{h*1.3:.0f},"
              f"zoompan=z='1+0.025*on/30':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,format=yuv420p")
        partial = out.with_suffix(".part.mp4")
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(img), "-vf", vf, "-t", f"{sec:.6f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", str(partial)], check=True, timeout=max(60, sec * 10))
            partial.replace(out)
        finally:
            partial.unlink(missing_ok=True)
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
