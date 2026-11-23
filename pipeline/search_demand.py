"""Search demand from YouTube autocomplete (growth loop, 2026-11-23).

Our best-performing Shorts across all channels match phrases people type into YouTube search
("Rice in Russian", "Tea in Russian"). Autocomplete is the free, keyless signal for that demand:
a subject with many completions is something people search for, and the completions themselves
are the phrasing to put in titles. No model calls; every function fails soft to an empty result.
"""
from __future__ import annotations

import re

import requests

from .common import log

URL = "https://suggestqueries.google.com/complete/search"
STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "was", "how", "why", "what",
        "this", "that", "with", "from", "by", "at", "its", "it", "just", "now", "new", "says", "will", "be", "as",
        "you", "your", "should", "so", "can", "not", "our", "we", "they", "their", "who", "when", "where", "do", "does",
        "did", "has", "have", "had", "out", "up", "than", "about", "after", "over", "into", "been", "could", "would",
        "may", "might", "more", "most", "some", "any", "all", "every", "there", "here", "then", "no", "yes", "isn",
        "isnt", "dont", "don", "t", "s", "real", "own", "only", "still", "first", "next", "one", "two", "three"}
_cache: dict[str, list[str]] = {}


def suggestions(query: str, timeout: float = 6.0) -> list[str]:
    """YouTube autocomplete completions for query (lowercased, deduplicated), [] on any failure."""
    q = " ".join(str(query or "").lower().split())[:80]
    if not q:
        return []
    if q in _cache:
        return _cache[q]
    try:
        r = requests.get(URL, params={"client": "firefox", "ds": "yt", "hl": "en", "q": q}, timeout=timeout)
        r.raise_for_status()
        out = [s for s in dict.fromkeys(str(x).strip().lower() for x in (r.json()[1] or [])) if s]
    except Exception as e:  # network, JSON, schema
        log.info("search demand: no suggestions for %r (%s)", q, type(e).__name__)
        out = []
    _cache[q] = out
    return out


def phrases_from(text: str, max_tokens: int = 12) -> list[str]:
    """Contiguous 3- and 2-word phrases, most specific first. Inner small words stay ("rice in russian"),
    but a phrase must start and end on a content word, so "so should you" never qualifies."""
    tokens = re.findall(r"[a-z0-9][a-z0-9\-]*", str(text or "").lower().replace("'s", "").replace("\u2019s", ""))[:max_tokens]
    grams = []
    for n in (3, 2):
        for i in range(len(tokens) - n + 1):
            w = tokens[i:i + n]
            if w[0] in STOP or w[-1] in STOP:
                continue
            grams.append(" ".join(w))
    return list(dict.fromkeys(grams))


def subject_terms(text: str, limit: int = 6) -> list[str]:
    return phrases_from(text)[:limit]


def demand(text: str, max_queries: int = 6) -> dict:
    """Relevance-weighted demand: completions that extend a specific headline phrase.

    score = sum over queried phrases of (completions starting with the phrase) x (words in the phrase),
    so "starship flight 15" (people search it) beats "so should you" (no phrase extends it).
    phrases = the matching completions, most specific first.
    """
    score, phrases = 0, []
    for gram in subject_terms(text, max_queries):
        hits = [s for s in suggestions(gram) if s == gram or s.startswith(gram + " ")]
        score += len(hits) * len(gram.split())
        phrases += [h for h in hits if h not in phrases]
    return {"score": score, "phrases": phrases[:8]}


def prompt_block(text: str) -> str:
    """Prompt lines with real search phrasing for a topic, or "" when nothing was found."""
    d = demand(text)
    if not d["phrases"]:
        return ""
    return ("Real YouTube search phrases people type about this subject (from autocomplete): "
            + "; ".join(d["phrases"])
            + ". Where one fits the story honestly, use its wording near the start of the main title and of at least one "
              "Short hook_title. Never bend the facts to match a phrase.\n")
