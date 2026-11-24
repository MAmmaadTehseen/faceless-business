"""Set each YouTube channel's About description, new-visitor trailer and video watermark (playbook items 16-18).

    PYTHONPATH=. .venv/bin/python scripts/channel_profile.py            # dry run: print what would change
    PYTHONPATH=. .venv/bin/python scripts/channel_profile.py --apply    # channels.update + watermarks.set

Descriptions follow the playbook pattern: the first sentence says what the channel covers in the words
people search, then the upload schedule, then links. Keywords, banner and country are left as they are.
Cost per channel: 1 + 50 (update) + 50 (watermark) quota units. The avatar and Home-tab sections are
Studio-only (no API).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HUB = "https://hub.ammaad.online/c/"

PROFILES = {
    "futurework": {
        "trailer": "mX8MSCkWrbE",
        "description": (
            "Future Work Explained covers AI and the future of work: layoffs, AI jobs, automation, hiring trends, "
            "workplace scams and the company filings behind them, explained for the person at the desk.\n\n"
            "Every video names the company, the number and the source, then tells you what it means for your next twelve months.\n\n"
            "New explainers every Monday, Wednesday and Friday, plus Shorts most days.\n\n"
            "Read the articles: " + HUB + "futurework\n"
            "Instagram: https://www.instagram.com/futurework.explained/\n\n"
            "Narration is AI-generated; research, sources and editing are checked for every video."
        ),
    },
    "tradewinds": {
        "trailer": "mTzhMe5JJPk",
        "description": (
            "Trade Winds Report explains tariffs, global trade, sanctions, energy prices, chips and shipping: "
            "who holds the power in world events and who pays the price.\n\n"
            "We follow one product, one ship or one number to show where the money really goes.\n\n"
            "New explainers every Tuesday, Thursday and Saturday, plus Shorts most days.\n\n"
            "Read the articles: " + HUB + "tradewinds\n"
            "Instagram: https://www.instagram.com/tradewindsreport/\n\n"
            "Narration is AI-generated; research, sources and editing are checked for every video."
        ),
    },
    "escapevelocity": {
        "trailer": "JhjYStQ7LOI",
        "description": (
            "Escape Velocity covers space news and space science: Starship, NASA, Artemis, Mars, asteroids, "
            "telescopes like James Webb, and the missions that get us off this rock.\n\n"
            "Every launch, mission and discovery explained with the real numbers and what happens next.\n\n"
            "New explainers every Monday, Thursday and Sunday, plus Shorts most days.\n\n"
            "Read the articles: " + HUB + "escapevelocity\n"
            "Instagram: https://www.instagram.com/escapevelocitydaily/\n\n"
            "Narration is AI-generated; research, sources and editing are checked for every video."
        ),
    },
    "tentongues": {
        "trailer": "R4LnSOzp_iw",
        "description": (
            "Ten Tongues teaches how to say one everyday English word in ten languages: Mandarin, Hindi, Spanish, "
            "French, Bengali, Portuguese, Russian, Urdu, Japanese and Italian.\n\n"
            "Each word comes with its native script, pronunciation and an example sentence. "
            "A new full episode every day, and one Short per language through the day.\n\n"
            "Word lists for every episode: " + HUB + "tentongues\n"
            "Instagram: https://www.instagram.com/ten.tongues/\n\n"
            "Narration and pronunciation audio are AI-generated: a guide, not a native speaker. "
            "Bengali voice: bn_BD-google (CC BY-SA 4.0)."
        ),
    },
}


def set_watermark(youtube, channel_id: str, watermark: Path) -> int:
    """watermarks.set returns an empty 204 that googleapiclient mishandles; use a plain multipart request."""
    import requests
    from google.auth.transport.requests import Request
    creds = youtube._creds()
    creds.refresh(Request())
    meta = json.dumps({"timing": {"type": "offsetFromStart", "offsetMs": 0},
                       "position": {"type": "corner", "cornerPosition": "topRight"}})
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/watermarks/set",
                      params={"channelId": channel_id, "uploadType": "multipart"},
                      headers={"Authorization": f"Bearer {creds.token}"},
                      files={"metadata": ("metadata", meta, "application/json"),
                             "image": ("watermark.png", watermark.read_bytes(), "image/png")}, timeout=60)
    return r.status_code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--channels", nargs="*", default=list(PROFILES))
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from pipeline.common import Channel
    from pipeline.publish import youtube
    from pipeline.publish.quota import reserve
    from pipeline.db import DB
    db = DB() if args.apply else None
    for key in args.channels:
        prof = PROFILES[key]
        youtube.use_channel(Channel(key))
        mine = youtube.yt().channels().list(part="snippet,brandingSettings", mine=True).execute()["items"][0]
        branding = mine["brandingSettings"]
        chan = dict(branding.get("channel", {}))
        print(f"== {key} ({mine['snippet']['title']}): trailer {chan.get('unsubscribedTrailer')} -> {prof['trailer']}")
        print("   " + prof["description"].split("\n")[0])
        if not args.apply:
            continue
        if not reserve(db, 100):
            sys.exit("YouTube quota reserve refused; try after the 08:00 UTC reset")
        chan.update({"description": prof["description"][:1000], "unsubscribedTrailer": prof["trailer"]})
        body = {"id": mine["id"], "brandingSettings": {"channel": chan}}
        if branding.get("image"):
            body["brandingSettings"]["image"] = branding["image"]
        youtube.yt().channels().update(part="brandingSettings", body=body).execute()
        status = set_watermark(youtube, mine["id"], ROOT / "assets" / "brand" / key / "watermark-150.png")
        print(f"   applied description + trailer; watermark HTTP {status}")


if __name__ == "__main__":
    main()
