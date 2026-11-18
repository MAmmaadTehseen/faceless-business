"""Owner-only: save one Facebook Page's long-lived token and id into local .env for a channel key.

Usage: .venv/bin/python scripts/meta_page_env.py "<Page name>" <CHANNEL_KEY>
       .venv/bin/python scripts/meta_page_env.py --all      # every Page in PAGES below
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
PAGES = {"Future Work Explained": "FUTUREWORK", "Trade Winds Report": "TRADEWINDS", "Escape Velocity": "ESCAPEVELOCITY",
         "Ten Tongues": "TENTONGUES", "Frame and Argument": "FILMREVIEW"}


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--all":
        wanted = dict(PAGES)
    elif len(sys.argv) == 3:
        wanted = {sys.argv[1]: sys.argv[2].upper()}
    else:
        sys.exit(__doc__)
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
    by_name = {p["name"].strip().casefold(): p for p in pages}
    env_path = ROOT / ".env"
    env = env_path.read_text() if env_path.exists() else ""
    saved, missing = [], []
    for page_name, key in wanted.items():
        page = by_name.get(page_name.strip().casefold())
        if not page:
            missing.append(page_name)
            continue
        for name, value in ((f"META_PAGE_ID_{key}", page["id"]), (f"META_ACCESS_TOKEN_{key}", page["access_token"])):
            if re.search(rf"^{name}=", env, re.M):
                env = re.sub(rf"^{name}=.*$", lambda _: f"{name}={value}", env, flags=re.M)
            else:
                env = env.rstrip("\n") + f"\n{name}={value}\n"
        if key == "FUTUREWORK":
            for name, value in (("META_PAGE_ID", page["id"]), ("META_ACCESS_TOKEN", page["access_token"])):
                if re.search(rf"^{name}=", env, re.M):
                    env = re.sub(rf"^{name}=.*$", lambda _: f"{name}={value}", env, flags=re.M)
        saved.append(f"{key} ({page['id']})")
    env_path.write_text(env)
    print("Saved to .env (tokens not printed):", ", ".join(saved) or "nothing")
    if missing:
        print("Not granted to the app, re-run after fixing Page access:", ", ".join(missing))
        print("Pages the token can see:", ", ".join(p["name"] for p in pages) or "none")
        sys.exit(1)


if __name__ == "__main__":
    main()
