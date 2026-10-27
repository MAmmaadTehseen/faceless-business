"""Get a long-lived Meta (Instagram + Facebook) token and the ids the pipeline needs.
1. Instagram account must be Creator/Business and linked to a Facebook Page you admin.
2. developers.facebook.com -> create app (type Business) -> add 'Instagram Graph API' and 'Facebook Login for Business'.
3. Graph API Explorer: select your app, add permissions instagram_basic, instagram_content_publish, instagram_manage_comments,
   instagram_manage_insights, pages_show_list, pages_read_engagement, pages_manage_posts, pages_manage_engagement, pages_read_user_content.
   Generate a User token (works for your own accounts while the app is in Development mode; no app review needed).
4. python scripts/meta_token.py <APP_ID> <APP_SECRET> <SHORT_LIVED_USER_TOKEN>
   -> prints META_ACCESS_TOKEN (page token, long-lived), META_PAGE_ID, META_IG_USER_ID.
   Re-run roughly every 60 days; the dashboard reminds you.
"""
import sys

import requests

G = "https://graph.facebook.com/v21.0"
app_id, app_secret, short = sys.argv[1:4]
r = requests.get(f"{G}/oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret, "fb_exchange_token": short}).json()
long_user = r["access_token"]
pages = requests.get(f"{G}/me/accounts", params={"access_token": long_user}).json()["data"]
for p in pages:
    ig = requests.get(f"{G}/{p['id']}", params={"fields": "instagram_business_account", "access_token": p["access_token"]}).json().get("instagram_business_account", {})
    print(f"\nPage: {p['name']}\nMETA_PAGE_ID={p['id']}\nMETA_IG_USER_ID={ig.get('id', 'NOT LINKED')}\nMETA_ACCESS_TOKEN={p['access_token']}")
