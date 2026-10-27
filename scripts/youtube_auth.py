"""Run once on your machine to get a YouTube refresh token.
1. Google Cloud Console -> new project -> enable 'YouTube Data API v3' and 'YouTube Analytics API'.
2. OAuth consent screen: External, add your Google account as a test user. Scopes: youtube, youtube.force-ssl, yt-analytics.readonly.
3. Credentials -> OAuth client ID -> Desktop app. Copy client id/secret into .env as YT_CLIENT_ID / YT_CLIENT_SECRET.
4. python scripts/youtube_auth.py  -> opens a browser, prints YT_REFRESH_TOKEN. Put it in .env and GitHub secrets.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl", "https://www.googleapis.com/auth/yt-analytics.readonly"]
cid, sec = os.getenv("YT_CLIENT_ID"), os.getenv("YT_CLIENT_SECRET")
if not cid or not sec:
    sys.exit("Set YT_CLIENT_ID and YT_CLIENT_SECRET in .env first")
flow = InstalledAppFlow.from_client_config({"installed": {"client_id": cid, "client_secret": sec, "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                                          "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}, SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nYT_REFRESH_TOKEN=" + creds.refresh_token)
