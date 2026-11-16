"""Deterministic Short/Reel metadata: hook line, comment question, niche hashtags. No model calls.

YouTube Shorts and Reels are tested on a small pool first; the caption's job is to
give that pool a reason to watch and to comment, and to tell the platform the niche.
Everything here is built from the content row and channel.json so it costs nothing.
"""
from __future__ import annotations

import re

MAX_HASHTAGS = 5
YOUTUBE_SHORT_HASHTAGS = 3   # YouTube reads at most the first three hashtags of a description


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", (text or "").strip()) if s.strip()]


def hashtags(channel, limit: int = MAX_HASHTAGS) -> list[str]:
    """Channel niche hashtags from channel.json `hashtags`, normalised and de-duplicated."""
    out: list[str] = []
    for raw in channel.cfg.get("hashtags", []) or []:
        tag = re.sub(r"[^0-9A-Za-z_]", "", str(raw))
        if tag and not tag[0].isdigit() and tag.lower() not in {t.lower() for t in out}:
            out.append(tag)
        if len(out) >= limit:
            break
    return out


def hook_line(row: dict) -> str:
    """The spoken first sentence of the Short, or its title: the line the viewer sees first in the caption."""
    sents = _sentences(row.get("script") or "")
    title = (row.get("title") or "").strip()
    first = sents[0] if sents else ""
    if first and 15 <= len(first) <= 140 and first.casefold() != title.casefold():
        return first
    return title


def comment_question(row: dict, channel) -> str:
    """A question that invites a reply: the script's own closing question when it has one, else the channel default."""
    sents = _sentences(row.get("script") or "")
    for s in reversed(sents[-3:]):
        if s.endswith("?") and 12 <= len(s) <= 160:
            return s
    return (channel.cfg.get("caption_question") or "What would you add? Tell us in the comments.").strip()


def summary_line(row: dict) -> str:
    """Second or third sentence of the script: the one-line payoff after the hook."""
    sents = _sentences(row.get("script") or "")
    for s in sents[1:3]:
        if 20 <= len(s) <= 180:
            return s
    return ""


def reels_caption(row: dict, channel) -> str:
    """Instagram/Facebook caption: hook, payoff, question, niche hashtags. No off-platform links.

    Links are not clickable in Reels captions and a YouTube-only tag like #shorts tells
    Instagram nothing about the niche, so neither appears here. Cross-account mentions
    are added separately by cross_promotion.instagram_caption; this text contains no '@'.
    """
    parts = [hook_line(row)]
    payoff = summary_line(row)
    if payoff and payoff.casefold() != parts[0].casefold():
        parts.append(payoff)
    parts.append(comment_question(row, channel))
    name = channel.cfg.get("name") or channel.name
    parts.append(f"Full story on our YouTube channel: {name}." if row.get("parent_id") else f"More every day from {name}.")
    tags = hashtags(channel)
    if tags:
        parts.append(" ".join(f"#{t}" for t in tags))
    text = "\n\n".join(p for p in parts if p).replace("@", "")
    return text[:2200]


def youtube_short_description(row: dict, channel, long_url: str | None = None) -> str:
    """YouTube Shorts description: hook, payoff, full-video link, three niche hashtags plus #Shorts.

    Keeps the `{LONG_URL}` placeholder convention used by publish_short when no URL is known yet.
    """
    parts = [hook_line(row)]
    payoff = summary_line(row)
    if payoff and payoff.casefold() != parts[0].casefold():
        parts.append(payoff)
    if row.get("parent_id"):
        parts.append(f"Full video: {long_url or '{LONG_URL}'}")
    footer = (channel.cfg.get("description_footer") or "").strip()
    if footer:
        parts.append(footer)
    tags = hashtags(channel, YOUTUBE_SHORT_HASHTAGS)
    parts.append(" ".join(f"#{t}" for t in tags + ["Shorts"]))
    return "\n\n".join(p for p in parts if p)[:4900]


def short_tags(row: dict, channel, parent_tags: list[str] | None = None, limit: int = 15) -> list[str]:
    """Tags for a Short: parent/long tags first, then channel niche keywords, de-duplicated."""
    out: list[str] = []
    for t in list(row.get("tags") or []) + list(parent_tags or []) + list(channel.cfg.get("niche_keywords") or []):
        t = str(t).strip()
        if t and t.lower() not in {x.lower() for x in out}:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def uses_legacy_description(desc: str | None) -> bool:
    """True for the old 'title / Full video / #shorts' stub descriptions that carry no keywords."""
    d = (desc or "").strip()
    return not d or bool(re.fullmatch(r"[^\n]*\n+Full video: [^\n]*\n#shorts\s*", d))
