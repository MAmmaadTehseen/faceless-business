"""Best-effort, bounded upload alerts. Never send scripts, errors or credentials."""
import hashlib
import hmac
import json
import os
import time
import requests


def notify(publication, channel):
    url = os.getenv("JARVIS_WEBHOOK_URL")
    secret = os.getenv("JARVIS_WEBHOOK_SECRET")
    if not url or not secret or publication.get("status") not in ("live", "failed"):
        return
    try:
        payload = {k: publication[k] for k in ("id", "content_id", "platform", "status")}
        payload["channel"] = channel
        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        requests.post(url, data=body, headers={"Content-Type": "application/json",
            "X-Faceless-Timestamp": timestamp, "X-Faceless-Signature": signature}, timeout=(1, 2))
    except Exception:
        # No response/error logging: third-party errors can include credentials.
        pass


def record(db, row, on="content_id,platform"):
    previous = db.one("publications", {"content_id": row["content_id"], "platform": row["platform"]})
    from datetime import datetime, timezone
    if not previous or previous.get("status") != row.get("status"):
        row = {**row, "status_changed_at": datetime.now(timezone.utc).isoformat()}
    result = db.upsert("publications", row, on=on)
    if not previous or previous.get("status") != row.get("status"):
        try:
            publication = db.one("publications", {"content_id": row["content_id"], "platform": row["platform"]})
            content = db.one("content", {"id": row["content_id"]})
            if publication and content:
                notify(publication, content["channel"])
        except Exception:
            pass
    return result


def update(db, match, fields):
    """Preserve conditional update guards for queue drains and owner retries."""
    previous = db.one("publications", match)
    if not previous:
        return
    from datetime import datetime, timezone
    changed = "status" in fields and previous.get("status") != fields["status"]
    if changed:
        fields = {**fields, "status_changed_at": datetime.now(timezone.utc).isoformat()}
    result = db.update("publications", match, fields)
    if changed:
        try:
            publication = db.one("publications", {"id": previous["id"]})
            if publication and publication.get("status") == fields["status"]:
                content = db.one("content", {"id": publication["content_id"]})
                if content:
                    notify(publication, content["channel"])
        except Exception:
            pass
    return result
