"""Instagram Reels + Facebook Reels via the Graph API.
Instagram needs a public, direct mp4 URL. We put the file in a public Supabase Storage bucket (free tier)
when Supabase is configured, else as a GitHub release asset (public repo)."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import requests

from ..common import log

G = "https://graph.facebook.com/v21.0"      # Facebook Pages (page token)
IG = "https://graph.instagram.com/v21.0"    # Instagram API with Instagram Login (user token, 60-day, refreshable)


from ..common import Channel

_current = Channel()


def use_channel(channel: Channel) -> None:
    global _current
    _current = channel


def fb_configured() -> bool:
    return all(_current.env(k) for k in ("META_ACCESS_TOKEN", "META_PAGE_ID"))


def ig_configured() -> bool:
    return bool(_current.env("META_IG_USER_ID") and _ig_tok())


def configured() -> bool:
    return fb_configured() or ig_configured()


def _tok() -> str:
    return _current.env("META_ACCESS_TOKEN")


_ig_cache: dict[str, str] = {}


def _ig_tok() -> str | None:
    """Instagram user token: refreshed copy in the settings table wins over the env seed."""
    key = _current.key
    if key not in _ig_cache:
        tok = None
        if os.getenv("SUPABASE_URL") or os.getenv("DB_BACKEND"):
            try:
                from ..db import DB
                tok = DB().setting(f"ig_token_{key}")
            except Exception:
                tok = None
        _ig_cache[key] = tok or _current.env("IG_ACCESS_TOKEN") or ""
    return _ig_cache[key] or None


def refresh_ig_token(db, channel: Channel, min_age_days: int = 7) -> bool:
    """Instagram Login tokens last 60 days; refresh after 7 and store in settings so every job uses the new one."""
    use_channel(channel)
    tok = _ig_tok()
    if not tok:
        return False
    from datetime import datetime, timezone
    last = db.setting(f"ig_token_refreshed_{channel.key}")
    if last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).days < min_age_days:
        return False
    r = requests.get(f"{IG}/refresh_access_token", params={"grant_type": "ig_refresh_access_token", "access_token": tok}, timeout=30).json()
    if "access_token" not in r:
        log.warning("instagram token refresh failed for %s: %s", channel.key, r.get("error", {}).get("message", r))
        return False
    db.set_setting(f"ig_token_{channel.key}", r["access_token"])
    db.set_setting(f"ig_token_refreshed_{channel.key}", datetime.now(timezone.utc).isoformat())
    _ig_cache[channel.key] = r["access_token"]
    log.info("instagram: token refreshed for %s (expires in %s days)", channel.key, r.get("expires_in", 0) // 86400)
    return True


def public_url_for(video: Path, tag: str) -> str:
    """Return a public direct URL for the mp4. Prefers Supabase Storage bucket 'media' (public)."""
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
    if url and key:
        from supabase import create_client
        sb = create_client(url, key)
        try:
            sb.storage.create_bucket("media", options={"public": True})
        except Exception:
            pass
        path = f"{tag}/{video.name}"
        with open(video, "rb") as f:
            sb.storage.from_("media").upload(path, f, {"content-type": "video/mp4", "upsert": "true"})
        return sb.storage.from_("media").get_public_url(path)
    return _github_release_url(video, tag)


def _github_release_url(video: Path, tag: str) -> str:
    """Fallback: GitHub release asset (public repo). Needs gh CLI with GH_TOKEN."""
    repo = os.getenv("GITHUB_REPOSITORY")
    cmd_base = ["gh", "release"]
    env = os.environ.copy()
    if repo:
        cmd_base += []  # gh picks GITHUB_REPOSITORY up automatically
    try:
        subprocess.run([*cmd_base, "view", tag], capture_output=True, env=env, check=True)
    except subprocess.CalledProcessError:
        subprocess.run([*cmd_base, "create", tag, "--title", tag, "--notes", "temporary media host for Meta publishing"], check=True, env=env)
    subprocess.run([*cmd_base, "upload", tag, str(video), "--clobber"], check=True, env=env)
    repo = repo or subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], capture_output=True, text=True, check=True).stdout.strip()
    return f"https://github.com/{repo}/releases/download/{tag}/{video.name}"


def _publish_response(response):
    data = response.json()
    if not response.ok or (isinstance(data, dict) and data.get("error")):
        # Keep the response for structured status/reason extraction, never the URL/token.
        raise requests.HTTPError("Meta publishing API error", response=response)
    return data


def _wait_container(container_id: str, timeout: int = 600) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = _publish_response(requests.get(f"{IG}/{container_id}", params={"fields": "status_code,status", "access_token": _ig_tok()}, timeout=30))
        if r.get("status_code") == "FINISHED":
            return
        if r.get("status_code") == "ERROR":
            raise RuntimeError(f"meta container error: {r}")
        time.sleep(10)
    raise RuntimeError("meta container timed out")


def publish_instagram_reel(video_url: str, caption: str, thumb_offset_ms: int = 2000) -> dict:
    ig = _current.env("META_IG_USER_ID")
    r = _publish_response(requests.post(f"{IG}/{ig}/media", data={"media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
                                              "share_to_feed": "true", "thumb_offset": thumb_offset_ms, "access_token": _ig_tok()}, timeout=60))
    if "id" not in r:
        raise RuntimeError(f"instagram container failed: {r}")
    _wait_container(r["id"])
    p = _publish_response(requests.post(f"{IG}/{ig}/media_publish", data={"creation_id": r["id"], "access_token": _ig_tok()}, timeout=60))
    if "id" not in p:
        raise RuntimeError(f"instagram publish failed: {p}")
    perm = _publish_response(requests.get(f"{IG}/{p['id']}", params={"fields": "permalink", "access_token": _ig_tok()}, timeout=30)).get("permalink")
    log.info("instagram: reel %s", p["id"])
    return {"id": p["id"], "url": perm}


def publish_facebook_reel(video_path: Path, description: str) -> dict:
    page = _current.env("META_PAGE_ID")
    s = _publish_response(requests.post(f"{G}/{page}/video_reels", data={"upload_phase": "start", "access_token": _tok()}, timeout=60))
    if "video_id" not in s:
        raise RuntimeError(f"facebook reel start failed: {s}")
    vid = s["video_id"]
    size = video_path.stat().st_size
    with open(video_path, "rb") as f:
        up = _publish_response(requests.post(f"https://rupload.facebook.com/video-upload/v21.0/{vid}",
                           headers={"Authorization": f"OAuth {_tok()}", "offset": "0", "file_size": str(size)}, data=f, timeout=600))
    if not up.get("success"):
        raise RuntimeError(f"facebook reel upload failed: {up}")
    fin = _publish_response(requests.post(f"{G}/{page}/video_reels", data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                                         "description": description[:5000], "access_token": _tok()}, timeout=60))
    if not fin.get("success"):
        raise RuntimeError(f"facebook reel finish failed: {fin}")
    log.info("facebook: reel %s", vid)
    return {"id": vid, "url": f"https://www.facebook.com/reel/{vid}"}


def ig_insights(media_id: str) -> dict:
    r = requests.get(f"{IG}/{media_id}", params={"fields": "like_count,comments_count", "access_token": _ig_tok()}, timeout=30).json()
    views = 0
    try:
        ins = requests.get(f"{IG}/{media_id}/insights", params={"metric": "views", "access_token": _ig_tok()}, timeout=30).json()
        for m in ins.get("data", []):
            views = m.get("values", [{}])[0].get("value", 0)
    except Exception:
        pass
    return {"views": views, "likes": r.get("like_count", 0), "comments": r.get("comments_count", 0)}


def fb_insights(video_id: str) -> dict:
    r = requests.get(f"{G}/{video_id}", params={"fields": "views,likes.summary(true),comments.summary(true)", "access_token": _tok()}, timeout=30).json()
    return {"views": r.get("views", 0), "likes": r.get("likes", {}).get("summary", {}).get("total_count", 0),
            "comments": r.get("comments", {}).get("summary", {}).get("total_count", 0)}


def ig_comments(media_id: str) -> list[dict]:
    r = requests.get(f"{IG}/{media_id}/comments", params={"fields": "id,text,username,timestamp", "limit": 50, "access_token": _ig_tok()}, timeout=30).json()
    return [{"platform_comment_id": c["id"], "author": c.get("username"), "text": c.get("text", ""), "posted_at": c.get("timestamp")} for c in r.get("data", [])]


def fb_comments(video_id: str) -> list[dict]:
    r = requests.get(f"{G}/{video_id}/comments", params={"fields": "id,message,from,created_time", "limit": 50, "access_token": _tok()}, timeout=30).json()
    return [{"platform_comment_id": c["id"], "author": (c.get("from") or {}).get("name"), "text": c.get("message", ""), "posted_at": c.get("created_time")} for c in r.get("data", [])]


def ig_reply(comment_id: str, text: str) -> str:
    r = requests.post(f"{IG}/{comment_id}/replies", data={"message": text[:2200], "access_token": _ig_tok()}, timeout=30).json()
    return r.get("id", "")


def fb_reply(comment_id: str, text: str) -> str:
    r = requests.post(f"{G}/{comment_id}/comments", data={"message": text[:8000], "access_token": _tok()}, timeout=30).json()
    return r.get("id", "")


def fb_like(comment_id: str) -> bool:
    r = requests.post(f"{G}/{comment_id}/likes", data={"access_token": _tok()}, timeout=30).json()
    return bool(r.get("success"))
