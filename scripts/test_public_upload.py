"""Upload one small Short as PUBLIC via the API and report whether YouTube kept it public.

Usage: .venv/bin/python scripts/test_public_upload.py <path-to-short.mp4> [channel]
Then delete the test video in YouTube Studio (or run with --delete <video_id>).
"""
import sys
from pathlib import Path

from pipeline.common import Channel
from pipeline.publish import youtube


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--delete":
        youtube.use_channel(Channel(sys.argv[3] if len(sys.argv) > 3 else "futurework"))
        youtube.yt().videos().delete(id=sys.argv[2]).execute()
        print("deleted", sys.argv[2])
        return
    path = Path(sys.argv[1])
    youtube.use_channel(Channel(sys.argv[2] if len(sys.argv) > 2 else "futurework"))
    r = youtube.upload(path, "API public-upload test (delete me)", "Temporary test of public uploads via the API.", ["test"],
                       privacy="public", publish_at=None, thumbnail=None, is_short=True, category_id="28")
    st = youtube.yt().videos().list(part="status", id=r["id"]).execute()["items"][0]["status"]
    print("uploaded:", r["url"])
    print("status:", {k: st.get(k) for k in ("privacyStatus", "uploadStatus", "rejectionReason", "failureReason")})
    print("RESULT:", "PUBLIC OK, no private lock" if st.get("privacyStatus") == "public" else "LOCKED/NOT PUBLIC")
    print(f"cleanup: .venv/bin/python scripts/test_public_upload.py --delete {r['id']}")


if __name__ == "__main__":
    main()
