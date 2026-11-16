"""Owner-only: apply a generated brand kit to a YouTube channel through the Data API.
Sets the banner, description, keywords, country and the video watermark. The avatar cannot be set
through the API; upload assets/brand/<key>/avatar-800.png in Studio > Customization > Profile.

Usage: .venv/bin/python scripts/youtube_brand.py <channel key> ["description text"]
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else ""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from pipeline.common import Channel
    from pipeline.publish import youtube
    if key == "filmreview":
        from pipeline.recap.channel import FilmReviewChannel
        channel = FilmReviewChannel()
    else:
        channel = Channel(key)
    cfg = channel.cfg
    kit = ROOT / "assets" / "brand" / key
    banner, watermark = kit / "youtube-banner-2560x1440.png", kit / "watermark-150.png"
    if not banner.exists() or not watermark.exists():
        sys.exit(f"Run scripts/brand.py {key} first")
    youtube.use_channel(channel)
    if not youtube.configured():
        sys.exit("YouTube token for this channel is not configured locally")
    service = youtube.yt()
    mine = service.channels().list(part="snippet,brandingSettings", mine=True).execute()["items"][0]
    channel_id = mine["id"]
    print("channel:", mine["snippet"]["title"], channel_id)
    description = sys.argv[2] if len(sys.argv) > 2 else cfg.get("description") or (
        f"{cfg['name']}: {cfg.get('tagline', '')} Narrated recaps of films, told like the movie and closed with an honest verdict. "
        "Spoilers are flagged in every video. Commentary and review; footage is used under the rights stated in each description.")
    keywords = " ".join(f'"{k}"' if " " in k else k for k in cfg.get("niche_keywords", []))
    from googleapiclient.http import MediaFileUpload
    uploaded = service.channelBanners().insert(media_body=MediaFileUpload(str(banner), mimetype="image/png")).execute()
    body = {"id": channel_id, "brandingSettings": {
        "channel": {"description": description[:1000], "keywords": keywords[:500], "country": cfg.get("country", "PK"),
                    "defaultLanguage": "en", "unsubscribedTrailer": mine["brandingSettings"].get("channel", {}).get("unsubscribedTrailer", "")},
        "image": {"bannerExternalUrl": uploaded["url"]}}}
    service.channels().update(part="brandingSettings", body=body).execute()
    print("banner, description and keywords applied")
    # watermarks.set returns an empty 204 body that googleapiclient's httplib2 path mishandles; use a plain request.
    import requests
    from google.auth.transport.requests import Request
    creds = youtube._creds()
    creds.refresh(Request())
    token = creds.token
    meta = json.dumps({"timing": {"type": "offsetFromStart", "offsetMs": 0}, "position": {"type": "corner", "cornerPosition": "topRight"}})
    response = requests.post("https://www.googleapis.com/upload/youtube/v3/watermarks/set",
                             params={"channelId": channel_id, "uploadType": "multipart"},
                             headers={"Authorization": f"Bearer {token}"},
                             files={"metadata": ("metadata", meta, "application/json"), "image": ("watermark.png", watermark.read_bytes(), "image/png")},
                             timeout=60)
    if response.status_code not in (200, 204):
        sys.exit(f"watermark failed: HTTP {response.status_code}")
    print("watermark applied; upload the avatar in Studio > Customization > Profile:", kit / "avatar-800.png")


if __name__ == "__main__":
    main()
