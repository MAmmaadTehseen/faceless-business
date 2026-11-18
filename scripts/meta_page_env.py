"""Owner-only: save one Facebook Page's long-lived token and id into local .env for a channel key.

Usage: .venv/bin/python scripts/meta_page_env.py "<Page name>" <CHANNEL_KEY>
The short-lived user token from Graph API Explorer is read from a hidden prompt (never an argument,
never printed). Writes META_PAGE_ID_<KEY> and META_ACCESS_TOKEN_<KEY>; the owner then sets the
matching GitHub secrets with gh secret set.
"""
import getpass
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
G = "https://graph.facebook.com/v21.0"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    page_name, key = sys.argv[1], sys.argv[2].upper()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    app_id, app_secret = os.getenv("META_APP_ID"), os.getenv("META_APP_SECRET")
    if not app_id or not app_secret:
        sys.exit("META_APP_ID and META_APP_SECRET must be in .env")
    short = getpass.getpass("Paste the Graph API Explorer user token (hidden): ").strip()
    if not short.startswith("EAA"):
        sys.exit("That does not look like a user token")
    r = requests.get(f"{G}/oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": app_id,
                                                      "client_secret": app_secret, "fb_exchange_token": short}, timeout=60).json()
    if "access_token" not in r:
        sys.exit(f"Exchange failed: {r.get('error', {}).get('message', 'unknown error')}")
    pages = requests.get(f"{G}/me/accounts", params={"access_token": r["access_token"], "limit": 100}, timeout=60).json().get("data", [])
    page = next((p for p in pages if p["name"].strip().casefold() == page_name.strip().casefold()), None)
    if not page:
        sys.exit("Page not found among: " + ", ".join(p["name"] for p in pages))
    env_path = ROOT / ".env"
    env = env_path.read_text() if env_path.exists() else ""
    for name, value in ((f"META_PAGE_ID_{key}", page["id"]), (f"META_ACCESS_TOKEN_{key}", page["access_token"])):
        if re.search(rf"^{name}=", env, re.M):
            env = re.sub(rf"^{name}=.*$", lambda _: f"{name}={value}", env, flags=re.M)
        else:
            env = env.rstrip("\n") + f"\n{name}={value}\n"
    env_path.write_text(env)
    print(f"Saved META_PAGE_ID_{key} ({page['id']}) and META_ACCESS_TOKEN_{key} to .env; token not printed.")


if __name__ == "__main__":
    main()
