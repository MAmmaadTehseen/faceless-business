"""YouTube Data API v3: upload, thumbnail, update title/thumbnail, analytics, comments."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from ..common import log

SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]


from ..common import Channel

_current = Channel()


def use_channel(channel: Channel) -> None:
    """Select which channel's refresh token subsequent calls use."""
    global _current, _channel_cache
    _current = channel
    _channel_cache = {}


def _token() -> str | None:
    return _current.env("YT_REFRESH_TOKEN")


def _creds() -> Credentials:
    return Credentials(None, refresh_token=_token(), token_uri="https://oauth2.googleapis.com/token",
                       client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"], scopes=SCOPES)


def yt():
    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def yt_analytics():
    return build("youtubeAnalytics", "v2", credentials=_creds(), cache_discovery=False)


def configured() -> bool:
    return bool(os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET") and _token())


def upload(video: Path, title: str, description: str, tags: list[str], privacy: str = "private",
           publish_at: datetime | None = None, thumbnail: Path | None = None, is_short: bool = False, category_id: str = "28") -> dict:
    body = {
        "snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:15], "categoryId": category_id,
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    if publish_at and privacy == "private":
        body["status"]["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt().videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
    vid = resp["id"]
    if thumbnail and thumbnail.exists():
        try:
            yt().thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")).execute()
        except Exception as e:  # thumbnails need a verified phone on the channel
            log.warning("thumbnail set failed (verify the channel's phone number in Studio): %s", e)
    log.info("youtube: uploaded %s as %s (%s)", vid, privacy, "short" if is_short else "long")
    return {"id": vid, "url": f"https://youtu.be/{vid}" if not is_short else f"https://youtube.com/shorts/{vid}"}



def update_title(video_id: str, title: str) -> None:
    v = yt().videos().list(part="snippet", id=video_id).execute()["items"][0]
    v["snippet"]["title"] = title[:100]
    yt().videos().update(part="snippet", body={"id": video_id, "snippet": v["snippet"]}).execute()


def set_thumbnail(video_id: str, path: Path) -> None:
    yt().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()


def stats(video_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        res = yt().videos().list(part="statistics,status", id=",".join(chunk)).execute()
        for it in res.get("items", []):
            s = it["statistics"]
            out[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                             "comments": int(s.get("commentCount", 0)), "privacy": it["status"]["privacyStatus"]}
    return out


def analytics(video_ids: list[str], days: int = 28) -> dict[str, dict]:
    """CTR, impressions, avg view duration per video from the Analytics API."""
    if not video_ids:
        return {}
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    try:
        res = yt_analytics().reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,averageViewDuration,averageViewPercentage,likes,subscribersGained",
            dimensions="video", filters="video==" + ",".join(video_ids[:200]),
        ).execute()
    except Exception as e:
        log.warning("analytics query failed: %s", e)
        return {}
    cols = [c["name"] for c in res.get("columnHeaders", [])]
    out = {}
    for row in res.get("rows", []):
        d = dict(zip(cols, row))
        # The Analytics API has no impressions/CTR (Studio only). ctr column stores average view percentage (0-1) instead.
        avp = d.get("averageViewPercentage")
        out[d["video"]] = {"avg_view_duration_sec": d.get("averageViewDuration"), "impressions": None,
                           "ctr": (avp / 100.0) if avp is not None else None}
    return out


def comments(video_id: str, max_results: int = 50) -> list[dict]:
    try:
        res = yt().commentThreads().list(part="snippet", videoId=video_id, maxResults=max_results, order="time", textFormat="plainText").execute()
    except Exception as e:
        log.warning("comments fetch failed for %s: %s", video_id, e)
        return []
    out = []
    for it in res.get("items", []):
        top = it["snippet"]["topLevelComment"]
        s = top["snippet"]
        out.append({"platform_comment_id": top["id"], "author": s.get("authorDisplayName"), "text": s.get("textDisplay", ""),
                    "posted_at": s.get("publishedAt"), "is_own": s.get("authorChannelId", {}).get("value") == _my_channel_id()})
    return out


_channel_cache: dict = {}


def _my_channel_id() -> str:
    if "id" not in _channel_cache:
        res = yt().channels().list(part="id", mine=True).execute()
        _channel_cache["id"] = res["items"][0]["id"]
    return _channel_cache["id"]


def reply(parent_comment_id: str, text: str) -> str:
    res = yt().comments().insert(part="snippet", body={"snippet": {"parentId": parent_comment_id, "textOriginal": text[:9000]}}).execute()
    return res["id"]
