"""Deterministic, opt-in Instagram captions; no model or platform calls."""
import json
import re

from ..common import Channel, log


def overlap_score(topic, config):
    """Count distinct niche terms with word boundaries (AI must not match paid)."""
    return sum(bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", topic, re.I))
               for term in set(config.get("cross_mention_keywords", [])) if term.strip())


def metadata(publication):
    try:
        data = json.loads(publication.get("error") or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def instagram_caption(db, row, channel, caption):
    """Return caption and success metadata for the existing publications.error field.

    Require three unmentioned successful Reels before each mention, including
    startup. Restrict history to this account through content.channel, not IDs.
    Missing/broken history fails closed while ordinary publishing continues.
    """
    base = caption[:2200]
    try:
        if db.setting("cross_mentions_enabled", False) is not True or re.search(r"@\w", caption):
            return base, None
        rows = db.select("content", {"channel": channel.key, "kind": "short"}, limit=1000)
        # A possibly truncated account history must never permit extra mentions.
        if len(rows) >= 1000:
            return base, None
        own = {r["id"] for r in rows}
        history = []
        ids = sorted(own)
        for start in range(0, len(ids), 100):
            history.extend(p for p in db.select("publications", {"platform": "instagram", "status": "live"},
                           in_={"content_id": ids[start:start + 100]}, limit=1000) if p.get("platform_id"))
        recent = sorted(history, key=lambda p: (p.get("published_at") or "", p.get("id", 0)), reverse=True)[:3]
        if len(recent) < 3 or any(metadata(p).get("cross_mention") for p in recent):
            return base, None
        # Only title/topic determine overlap, never generic footers/hashtags.
        topic = row.get("title") or ""
        candidates = []
        for key in Channel.keys():
            if key == channel.key:
                continue
            sister = Channel(key)
            handle = sister.cfg.get("instagram_handle", "").strip().lstrip("@")
            score = overlap_score(topic, sister.cfg)
            if score and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.]{0,29}", handle):
                candidates.append((score, key, handle, sister.cfg))
        if not candidates:
            return base, None
        _, key, handle, cfg = sorted(candidates, key=lambda c: (-c[0], c[1]))[0]
        line = cfg["cross_mention_line"].format(handle=handle)
        if len(line) > 2198 or line.count("@") != 1 or "\n" in line:
            return base, None
        # Reserve room for the whole line; never truncate the sister handle.
        result = caption[:2200 - len(line) - 2].rstrip() + "\n\n" + line
        return result, json.dumps({"cross_mention": {"channel": key, "handle": handle}})
    except Exception as exc:
        log.warning("Instagram cross mention skipped (%s)", type(exc).__name__)
        return base, None
