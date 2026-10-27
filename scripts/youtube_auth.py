"""Two-step YouTube OAuth without a local server (works in sandboxes).
Step 1: python scripts/youtube_auth.py url        -> prints the URL to open; log in with the channel's account, click Allow.
Step 2: the browser lands on http://localhost:8765/?code=... (page will not load; that is expected).
        python scripts/youtube_auth.py token "<paste that full URL>"   -> saves YT_REFRESH_TOKEN into .env

Prerequisites: Google Cloud project with YouTube Data API v3 + YouTube Analytics API enabled, OAuth consent screen
(External, your Gmail as test user), Desktop-app OAuth client; its id/secret in .env as YT_CLIENT_ID / YT_CLIENT_SECRET.
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl", "https://www.googleapis.com/auth/yt-analytics.readonly"]
REDIRECT = "http://localhost:8765/"

cid, sec = os.getenv("YT_CLIENT_ID"), os.getenv("YT_CLIENT_SECRET")
if not cid or not sec:
    sys.exit("Set YT_CLIENT_ID and YT_CLIENT_SECRET in .env first")

flow = Flow.from_client_config({"installed": {"client_id": cid, "client_secret": sec, "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                              "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [REDIRECT]}}, SCOPES, redirect_uri=REDIRECT, autogenerate_code_verifier=False)
cmd = sys.argv[1] if len(sys.argv) > 1 else "url"
if cmd == "url":
    url, _ = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    print(url)
elif cmd == "token":
    pasted = sys.argv[2].strip()
    code = re.search(r"[?&]code=([^&]+)", pasted)
    if not code:
        sys.exit("Could not find code= in the pasted URL")
    import os as _os
    _os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # redirect is http://localhost
    flow.fetch_token(code=code.group(1).replace("%2F", "/"))
    rt = flow.credentials.refresh_token
    if not rt:
        sys.exit("No refresh token returned; remove the app's access at myaccount.google.com/permissions and retry")
    env = (ROOT / ".env").read_text()
    env = re.sub(r"^YT_REFRESH_TOKEN=.*$", f"YT_REFRESH_TOKEN={rt}", env, flags=re.M) if "YT_REFRESH_TOKEN=" in env else env + f"\nYT_REFRESH_TOKEN={rt}\n"
    (ROOT / ".env").write_text(env)
    print("YT_REFRESH_TOKEN saved to .env")
