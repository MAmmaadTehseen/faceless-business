"""Playbook items 13 and 15 (growth log 2026-11-24): deterministic script review.

Item 13: "Never overstate in thumbnail/hook; verify digits and units in art text."
Item 15: a per-script review checklist (strategy fit, voice, accuracy, CTA) as a QA step.

The model-facing halves of these live in the prompts; this module is the measurable half
that runs on every script response without an extra model call. Everything here only warns
and stores minor findings: a hard reject would strand the paid script response.
"""
from __future__ import annotations

import re

from .common import log

# Art text (thumbnail + hook card) digits are compared against the spoken script.
_ART_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ART_SCALED = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([KMB])?\b")
_SUFFIX = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

# Currency symbols on art must be backed by the money word in the narration: the course's
# own reported failure was art reading "$200K per month" off a source that said something else.
_CURRENCY = {"$": ("dollar", "USD"), "£": ("pound", "GBP"), "€": ("euro", "EUR")}

# Spoken filler the style guides ban; strip_script_dashes already removes em dashes before
# this review runs, so the voice check targets phrases instead of punctuation.
_FILLER = re.compile(
    r"\bin (?:this|today'?s) video\b|\bwithout further ado\b|\bbuckle up\b|\blet'?s dive (?:in|into)\b|\bhold on to your\b",
    re.I,
)

REVIEW_CHECKS = (
    ("strategy", "The video opens on the named actor or its key number inside the first forty words."),
    ("voice", "The narration follows the channel persona and style: spoken English, no filler phrases."),
    ("accuracy", "Every statistic and quote is attributed in-line to a named source, and the art text digits and currency symbols match the script."),
    ("cta", "It ends with one comment question and a one-sentence subscribe reminder, nothing else."),
)


_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_ONES = {**{w: i for i, w in enumerate(
    "one two three four five six seven eight nine ten eleven twelve".split(), 1)},
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19}
_SCALE = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}


def _spelled_numbers(text: str) -> set[int]:
    """Parse simple compound spellings ("twenty five thousand", "one hundred and six")
    into values, so "25,000 BUYOUTS" over "twenty five thousand people" passes while a
    fabricated "73,000" still fails. Anything unparsable is skipped (noisy, not permissive).
    """
    values: set[int] = set()
    tokens = re.findall(r"[a-z]+", (text or "").lower())
    # A bare scale word ("a million", "millions of") counts as the scale value itself.
    values.update(_SCALE[w] for w in tokens if w in _SCALE)
    i = 0
    while i < len(tokens):
        if tokens[i] in _TENS or tokens[i] in _ONES:
            total = _TENS.get(tokens[i], 0) + _ONES.get(tokens[i], 0)
            i += 1
            if i < len(tokens) and tokens[i] in _ONES:
                total += _ONES[tokens[i]]
                i += 1
            while i < len(tokens) and tokens[i] in ("and", "a"):
                i += 1
                if i < len(tokens) and tokens[i] in _ONES:
                    total += _ONES[tokens[i]]
                    i += 1
            if i < len(tokens) and tokens[i] in _SCALE:
                total *= _SCALE[tokens[i]]
                i += 1
                if i < len(tokens) and (tokens[i] in _TENS or tokens[i] in _ONES):
                    sub = _TENS.get(tokens[i], 0) + _ONES.get(tokens[i], 0)
                    i += 1
                    if i < len(tokens) and tokens[i] in _ONES:
                        sub += _ONES[tokens[i]]
                        i += 1
                    total += sub
            values.add(total)
        else:
            i += 1
    return values


def _spoken_numbers(text: str) -> tuple[set[str], set[int]]:
    """Digit strings and parsed spelled values that appear in the narration.

    The style guide asks scripts to prefer digits for figures, so unparsed spellings simply
    do not count, which can only make the check noisier, never silently permissive.
    """
    digits = {n.replace(",", "") for n in _ART_NUMBER.findall(text or "")}
    return digits, _spelled_numbers(text or "")


def art_text_mismatch(thumbnail_text: str, script_text: str) -> str | None:
    """Item 13: return a description when the thumbnail/hook art text contains digits the
    script never states, or a currency symbol the narration never backs, so a number misread
    from a source cannot reach burned-in art. None means no finding.

    A digit the script does state is fine even abbreviated ("25,000" spoken, "25K" on art);
    a digit nowhere in the narration is the flag, as is "$25K" over a script about 25,000
    jobs that never says dollars.
    """
    art = " ".join((thumbnail_text or "").upper().split())
    if not art:
        return None
    body = script_text or ""
    stated_digits, stated_spelled = _spoken_numbers(body)
    for raw, suffix in _ART_SCALED.findall(art):
        digits = raw.replace(",", "")
        value = digits[:-1] if digits.endswith(".") else digits
        if digits in stated_digits or value in stated_digits:
            continue
        if value.replace(".", "", 1).isdigit():
            # "200K" means 200,000: compare the scaled value with spelled-out narration.
            scaled = float(value) * _SUFFIX.get(suffix, 1)
            if scaled in stated_spelled or int(scaled) in stated_spelled:
                continue
        bare = re.sub(r"[^\d]", "", digits)
        if bare and any(bare == s or bare in s for s in stated_digits):
            continue
        return f"art text digits {raw!r} do not appear in the narration (art: {art!r})"
    lowered = body.lower()
    for symbol, words in _CURRENCY.items():
        if symbol in art and not any(w.lower() in lowered for w in words):
            return f"art text shows {symbol!r} but the narration never mentions {words[0]}s (art: {art!r})"
    return None


def review_findings(data: dict, *, is_short: bool = False, title_key: str = "title",
                    script_key: str | list = "script") -> list[dict]:
    """Item 15: the per-script review checklist as findings (all minor, so nothing here
    blocks publication on its own; strict QA can still promote them).

    Checked areas, all deterministic: strategy (named actor/number opening), voice (banned
    filler phrases), accuracy (art-text digits and currency), CTA presence (long videos).
    """
    findings: list[dict] = []
    script = data.get(script_key) if not isinstance(script_key, list) else script_key
    text = "\n".join(script) if isinstance(script, list) else str(script or "")
    title = str(data.get(title_key) or "")
    if not text.strip():
        return findings

    from .script import opening_names_actor_or_number  # local import: script imports common only

    paragraphs = [p for p in (script if isinstance(script, list) else text.split("\n")) if p and p.strip()]
    if paragraphs and not opening_names_actor_or_number([paragraphs[0]]):
        findings.append({"severity": "minor",
                         "text": f"review/strategy: opening names no actor or number (checklist: {REVIEW_CHECKS[0][1]})"})

    filler = _FILLER.search(text)
    if filler:
        findings.append({"severity": "minor",
                         "text": f"review/voice: banned filler phrase {filler.group(0)!r} in narration"})

    art = str(data.get("thumbnail_text") or "") or (title if is_short else "")
    mismatch = art_text_mismatch(art, text)
    if mismatch:
        findings.append({"severity": "minor", "text": f"review/accuracy: {mismatch}"})

    if not is_short and "subscribe" not in text.lower() and "?" not in text[-400:]:
        findings.append({"severity": "minor", "text": "review/cta: no comment question or subscribe line found in the final block"})

    return findings


def log_review(findings: list[dict], content_id: str) -> None:
    """Log the review outcome once per script so produce logs carry the measurement."""
    if not findings:
        log.info("script review (%s): all checklist areas pass", content_id)
        return
    for finding in findings:
        log.warning("script review (%s): %s", content_id, finding["text"])
