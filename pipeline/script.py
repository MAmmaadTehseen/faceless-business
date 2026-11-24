"""Research + write the long-form script, titles, description, chapters, shot list, and thumbnail text."""
from __future__ import annotations

import re
import json

from .common import Claude, log, OUT_DIR, write_json

BANNED_TITLE = re.compile(
    r"while you sleep|guarantee|get rich|secret method|doctors hate|don't want you to know|make money fast|\$\d+[,\d]*\s*(a|per)\s*(day|week|month)|cure|lose \d+ (lbs|pounds|kg)",
    re.I,
)

SCRIPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "title_variants", "thumbnail_text", "description", "tags", "chapters", "script", "shot_list", "facts_check", "shorts"],
    "properties": {
        "title": {"type": "string", "description": "Best title, under 65 chars; starts with the searchable subject (the named thing or topic phrase people type) within the first 40 characters, then a colon and the angle"},
        "title_variants": {"type": "array", "items": {"type": "string"}, "description": "Exactly 4 to 6 other strong titles using different formulas"},
        "thumbnail_text": {"type": "string", "description": "2-3 words where possible (never more than 4), uppercase, with a strong verb or the key number, that say what the video is about: the named subject and/or the key number from the title (e.g. GOLDMAN: AI LAYOFFS, DIESEL £2, VOYAGER 1 CALL); never a vague teaser like NOT SO SAFE"},
        "description": {"type": "string", "description": "YouTube description: first sentence names the subject and the searchable topic phrase in plain words, 2-3 sentence summary, then chapters with timestamps as 'mm:ss Title' lines whose labels are phrases people would search, then 'Sources:' with the urls used"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "chapters": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title", "paragraph_index"], "properties": {"title": {"type": "string"}, "paragraph_index": {"type": "integer"}}}},
        "script": {"type": "array", "items": {"type": "string"}, "description": "Narration paragraphs in order, spoken English only, no headings, no stage directions, 1300-1900 words total"},
        "shot_list": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["paragraph_index", "query", "mood"], "properties": {"paragraph_index": {"type": "integer"}, "query": {"type": "string", "description": "2-4 word stock VIDEO search that a free stock library will certainly have: generic, physical, filmable things (e.g. 'office worker typing', 'server room aisle', 'city street timelapse', 'handshake meeting', 'parliament building exterior'). Never company names, countries, people, abstract nouns, or events. Exception: about one paragraph in four may instead use 'CARD: <2-4 words>' (a key number or name), 'CHART: <title> | <label>=<value>, <label>=<value>' (a bar chart of 2-6 numbers the paragraph states) or 'MAP: <country>, <country> | <label>' (the countries the paragraph names, highlighted); use these where the paragraph is about a number or a place."}, "mood": {"type": "string", "enum": ["calm", "tense", "bright", "dark"]}}}, "description": "One entry per paragraph"},
        "facts_check": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["claim", "source", "confidence"], "properties": {"claim": {"type": "string"}, "source": {"type": "string"}, "confidence": {"type": "string", "enum": ["verified", "likely", "unverified"]}}}},
        "shorts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["hook_title", "script", "query", "shots"], "properties": {"hook_title": {"type": "string", "description": "Short title under 45 chars, no hashtags; names the specific subject (proper noun or number) in its first three words; states the same claim as the first spoken sentence; never begins with a gerund or an adjective; shown on screen for the first two seconds"}, "script": {"type": "string", "description": "Self-contained; QUICK Shorts (1 and 3) 50-70 words, STANDARD Shorts (2 and 4) 75-110 words; first sentence under 12 words with a named actor or a number; payoff by sentence three; last line a question or a loop back to the first line"}, "query": {"type": "string", "description": "stock footage search for the short"}, "shots": {"type": "array", "items": {"type": "string"}, "description": "Ordered visuals, one per 3-4 seconds of narration (8-12 for a 35-45 second Short, 6-8 for a quick one): each is either a 2-5 word stock video search showing exactly what the narration says at that moment (a physical, filmable thing: 'cargo ship at port', 'rocket engine firing', 'worker packing boxes'), or 'CARD: <2-4 words>' for a full-screen branded text card with a key number or name stock footage cannot show ('CARD: 25,000 JOBS', 'CARD: VOYAGER 1'), or 'CHART: <title> | <label>=<value>, <label>=<value>' to draw a bar chart of 2-6 numbers the narration states ('CHART: US tariff on Chinese EVs | 2023=25%, 2024=100%'), or 'MAP: <country>, <country> | <label>' to show a highlighted map of the countries the narration names ('MAP: Iran, Oman | Strait of Hormuz'). Use a CARD or CHART for the first big number, a MAP when a place matters, at most four CARD/CHART/MAP shots in total, only numbers the script states; never repeat a query."}}}},
    },
}

HOOK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["opening_paragraphs", "changed"],
    "properties": {"opening_paragraphs": {"type": "array", "items": {"type": "string"}}, "changed": {"type": "boolean"}},
}

# Shorts length budget (growth log 2026-11-16): retention cliffs near 30 s, so
# scripts aim for 75-110 words. The prompt asks for it; tighten_shorts enforces it.
SHORT_WORDS = (75, 110)
SHORT_WORDS_ACCEPT = (60, 115)
# Length experiment (2026-11-23): Ten Tongues' 27-35 s Shorts out-view the 48-54 s explainer Shorts.
# Shorts 1 and 3 of each video are QUICK, 2 and 4 STANDARD; the scoreboard compares them by duration.
QUICK_WORDS = (50, 70)
QUICK_WORDS_ACCEPT = (40, 78)


def budget(short: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    return (QUICK_WORDS, QUICK_WORDS_ACCEPT) if short.get("length") == "quick" else (SHORT_WORDS, SHORT_WORDS_ACCEPT)
TIGHTEN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["script"],
    "properties": {"script": {"type": "string", "description": "The tightened Short script, 75-110 words"}},
}


def word_count(text: str) -> int:
    return len(str(text or "").split())


# Playbook item 1: words that open concept-only sentences ("Being right is no longer enough",
# "The two column job check") and spoken number words. Used only by the opening-quality warning.
_SENTENCE_NEUTRAL = frozenset("""
the a an this that these those here there it they you we i he she being before after when where
how why what who which will would could should is are was were has have had does did do
nobody nothing everyone most many some all every each imagine picture take make get so but and or
if now first then next because while despite about into onto at in on for from by with without
one two three four five six seven eight nine ten eleven twelve twenty
""".split())
_NUMBER_WORDS = frozenset("""
zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred
thousand million billion trillion percent
""".split())


def opening_names_actor_or_number(script: list[str], window: int = 40) -> bool:
    """Playbook item 1: the first `window` words of a long video must contain a named actor
    or a number. Concept-only openings ("Being right is no longer enough") are the measured
    anti-pattern on every channel. Digits count; spoken numbers count (the style guide says
    numbers are spoken as words); a capitalized word counts when it is either mid-sentence
    or a sentence start that is not a common opening word ("Microsoft just filed" passes,
    "The company just filed" does not). Warning-only by design: a reject would strand the
    paid script response.
    """
    words = " ".join(script[:2]).split()[:window]
    at_sentence_start = True
    for raw in words:
        token = raw.strip("\"'“”([{)]")
        if any(ch.isdigit() for ch in token):
            return True
        bare = token.replace("'", "").replace("’", "").replace(",", "").replace(".", "").lower()
        if bare in _NUMBER_WORDS:
            return True
        if token[:1].isupper() and bare != "i" and (not at_sentence_start or bare not in _SENTENCE_NEUTRAL):
            # capitalized mid-sentence (any proper noun), or a sentence start that is not a
            # common opening word: "Microsoft just filed" passes, "The company just filed" does not.
            return True
        at_sentence_start = token.endswith((".", "!", "?"))
    return False


def opening_has_viewer_stake(script: list[str], window: int = 45) -> bool:
    """Retention rule (growth log 2026-11-24): the first `window` spoken words address the viewer
    ("you", "your"). Measured: openings that stayed in third person lost 25-32% of viewers at
    seconds 10-21; the one second-person opening kept 65% to one minute. Warning-only, like
    opening_names_actor_or_number.
    """
    words = " ".join(script[:2]).lower().split()[:window]
    return any(w.strip("\"'“”,.!?;:()") in {"you", "your", "you're", "you’re", "you'll", "you’ll", "yours"} for w in words)


def tighten_shorts(claude, shorts: list[dict], content_id: str | None = None) -> list[dict]:
    """Shorten any Short script over the word budget with one small model call each.

    Non-fatal: a failed or still-too-long rewrite keeps the original script. Facts,
    the first-sentence hook and the closing question must survive the rewrite.
    """
    out = []
    for short in shorts:
        words = word_count(short.get("script"))
        (lo, hi), (acc_lo, acc_hi) = budget(short)
        log.info("short %r (%s): %d words", short.get("hook_title"), short.get("length", "standard"), words)
        if words <= hi:
            out.append(short)
            continue
        prompt = (
            f"This Short script is {words} words; it must be {lo}-{hi} words (about {round(lo / 2.5)}-{round(hi / 2.5)} seconds spoken). "
            "Cut it to length. Keep the first sentence as the hook (under twelve words, naming a specific actor, object or number), "
            "keep every fact, number and attribution you retain accurate, reach the payoff by sentence three, and keep the last line "
            "as a question or a loop back to the first line. Remove examples, repetition and transitions before anything else. "
            "Natural spoken English, no em dashes, no headings.\n\n"
            f"Hook title: {short.get('hook_title', '')}\n\nScript:\n{short.get('script', '')}"
        )
        try:
            data, _ = claude.run("short_tighten", prompt, schema=TIGHTEN_SCHEMA, effort="low", max_tokens=1500, content_id=content_id, retries=1)
            new = str(data.get("script") or "").strip()
            n = word_count(new)
            if acc_lo <= n <= acc_hi:
                log.info("short %r tightened: %d -> %d words", short.get("hook_title"), words, n)
                short = {**short, "script": new}
            else:
                log.warning("short %r tighten rejected (%d words); keeping original", short.get("hook_title"), n)
        except Exception as e:  # non-fatal
            log.warning("short tighten skipped for %r: %s", short.get("hook_title"), e)
        out.append(short)
    return out


def strip_script_dashes(value):
    """Normalize generated text recursively, preserving numeric en-dash ranges."""
    count = 0
    def clean(item):
        nonlocal count
        if isinstance(item, str):
            pattern = r"\s*\u2014\s*|\s*(?<!\d)\u2013\s*|\s*\u2013(?!\d)\s*"
            def replace(match):
                nonlocal count
                count += 1
                prefix = item[:match.start()].rstrip()
                if not prefix or prefix[-1] in ",.;:!?":
                    return " "
                return ", "
            return re.sub(pattern, replace, item).strip()
        if isinstance(item, list):
            return [clean(v) for v in item]
        if isinstance(item, dict):
            return {k: clean(v) for k, v in item.items()}
        return item
    result = clean(value)
    log.info("script: replaced %d em/en dashes", count)
    return result


def search_block(topic: dict) -> str:
    """Real YouTube autocomplete phrasing for the topic (growth loop 2026-11-23); "" when unavailable."""
    try:
        from .search_demand import prompt_block
        return prompt_block(f"{topic.get('topic', '')} {topic.get('source_headline') or ''}")
    except Exception:
        return ""


def nasa_hint(claude) -> str:
    """Channels with the NASA library (Escape Velocity) may name spacecraft and missions in shot queries:
    images-api.nasa.gov has real footage and photos of them, generic stock does not."""
    ch = getattr(claude, "channel", None)
    if not ch or not (getattr(ch, "footage", None) or {}).get("nasa"):
        return ""
    return ("Footage note: this channel searches the NASA image and video library first, so shot queries and Shorts `shots` "
            "SHOULD name the real spacecraft, rocket, telescope or mission when the narration is about it ('Voyager spacecraft', "
            "'Artemis II rocket launch', 'James Webb telescope mirror'), overriding the generic-query rule for shot_list.\n")


def write_script(claude: Claude, topic: dict, content_id: str, shorts_per_long: int = 4) -> dict:
    user = (
        f"Today's video topic: {topic['topic']}\n"
        f"Angle: {topic.get('angle') or 'choose the persona\'s strongest honest angle'}\n"
        f"Seed headline: {topic.get('source_headline') or ''}\nSeed url: {topic.get('source_url') or ''}\n"
        f"{search_block(topic)}\n"
        f"{nasa_hint(claude)}"
        "Step 1: research. Use web search to confirm the core facts, find 4-8 concrete, recent, attributable facts "
        "(numbers, names, dates, quotes) and at least one contrasting view. Prefer primary sources and major outlets.\n"
        "Step 2: write the long video following the script sequence and style exactly. 1300-1900 words of narration. "
        "Structure, in order: (1) Hook: one shocking named-authority claim stated as fact, then one sentence of why it breaks the usual assumption; the first 40 words must contain the named actor or number. "
        "Retention rule for the first fifteen seconds (measured 2026-11-24: every long video lost a quarter to a third of its viewers between second 10 and 21, right where the opening finished restating the title and turned to background; the one that opened on the viewer's own stake kept 65% to the one-minute mark against 26-42%): within the first 45 spoken words, say what this means for the viewer in second person ('you', 'your') and promise the specific thing the video will reveal later (an open question answered after the midpoint). Unit conversions, exact dates, 'the headlines say' and background come only after that promise. "
        "(2) Context beat: that matters because [stake]; [named source] said [paraphrase], before any framework. "
        "(3) Core message with one memorable framework, previewed by 0:40. "
        "(4) Evidence: at least two attributed quotes or excerpts from named sources; the strongest goes before the 40% mark, never saved for the end. "
        "(5) Application: what it means for the viewer's own next twelve months, right before the CTA. "
        "(6) CTA: one question for the comments, one-sentence subscribe reminder, nothing else. "
        "Each of the six blocks must introduce a genuinely different angle. No two paragraphs may restate the same point. "
        "Use simple natural spoken English, no filler or generic transitions. Hedge uncertain causes with can, may, "
        "or may indicate. No em dashes in any captions, titles, descriptions or Shorts. Attribute every statistic in-line. "
        "Each paragraph is 2-5 sentences and is one visual beat. End on the application or the question, never a recap.\n"
        "Step 3: produce 5 titles across different formulas, thumbnail text, description with chapters, tags, "
        "Title rules: the main title begins with the searchable subject (the named organisation, object, event or topic phrase a person would type) inside the first 40 characters, then the angle; it states one checkable claim, never a mood or a metaphor; when a named authority backs the claim, prefer the pattern '[Checkable claim], [named authority] just confirmed it'; the title, the first spoken sentence and the thumbnail text must all state the same claim. "
        "Clever lines go in title_variants, never first. "
        "Description rule: its first sentence states the subject and the topic phrase plainly; chapter labels are search phrases, not jokes. "
        "one shot-list query per paragraph (generic stock-video phrases that always exist: people at desks, buildings, screens, streets, hands, machines; vary them so no two consecutive paragraphs share a query; never names of companies, countries, or people), "
        f"a facts_check table, and exactly {shorts_per_long} Shorts scripts. Each must cover a DIFFERENT angle "
        "(the number, the human consequence, the contrarian take, the what-to-do-now), be self-contained, "
        "with its own hook in the first line. Length experiment: Shorts 1 and 3 are QUICK, 50-70 words (about 20-28 seconds): one fact, one turn, and a last line that loops into the first; Shorts 2 and 4 are STANDARD, 75-110 words (about 35-45 seconds). No two Shorts may share a hook or statistic. "
        "Shorts hook rules: hook_title is under 45 characters and names the specific subject (a proper noun or a number) in its first three words, because it is shown on screen for the first two seconds; it states the same claim the first spoken sentence makes, in the same words where possible; "
        "the first sentence is under twelve words, states a checkable fact or an exact answer (not a mood), and names a specific actor, object or number; "
        "no setup, no 'in this video', no question-only opener, no title that begins with a gerund or an adjective; the payoff lands by the third sentence; "
        "the last line is either a question the viewer can answer in one comment or a line that loops back to the first sentence. "
        "Shorts visuals (growth log 2026-11-24: one generic query per Short put wildflowers and city skylines under a Voyager story): "
        "write every sentence about something that can be shown, and give `shots` in narration order so the picture changes every 3-4 seconds and always shows what is being said; "
        "put the first big number on a CARD. Entertainment rules for Shorts: a concrete image in every sentence, one twist or surprising contrast at the midpoint "
        "('but here is the part nobody mentions'), and no sentence a viewer could skip without losing the thread.\n"
        "Long-video entertainment rules: re-hook at the start of every chapter with an open question the chapter answers; alternate a fact with a concrete scene or example; "
        "at least one moment of contrast or irony per chapter; never two abstract sentences in a row.\n"
        "Hard rules: no income promises, no medical/legal/financial advice, no fabricated quotes, no 'experts say' without naming who. "
        "The first two paragraphs must be a pattern break that pays off the title within ninety seconds."
    )
    if topic.get('evergreen'):
        user = user.replace("Today's video topic:", "Evergreen video topic:").replace(
            "4-8 concrete, recent, attributable facts", "4-8 concrete, durable, attributable facts")
        user += "\nThis video will be released later. No breaking news, current prices, upcoming deadlines or references to today. Explain enduring mechanisms."
    supplied_sources = list(dict.fromkeys(([topic["source_url"]] if topic.get("source_url") else [])
                                         + [n["url"] for n in topic.get("news", []) if n.get("url")]))
    if getattr(claude, "provider", "anthropic") == "lunaroute":
        user += "\nSupplied ideation news: " + json.dumps(topic.get("news", []))
    # A paid response is checkpointed before hook/validation can fail. Retrying
    # validation must never silently purchase a replacement script.
    saved = OUT_DIR / content_id / "script.json"
    raw = OUT_DIR / content_id / "paid_script.json"
    db = getattr(claude, "db", None)
    row = db.one("content", {"id": content_id}) if db else None
    try:
        notes = json.loads((row or {}).get("qa_notes") or "{}")
    except (ValueError, TypeError):
        notes = {}
    checkpoint = notes.get("paid_script") if isinstance(notes, dict) else None
    reused = saved.is_file() or raw.is_file() or checkpoint is not None
    if reused:
        data = json.loads((saved if saved.is_file() else raw).read_text()) if saved.is_file() or raw.is_file() else checkpoint
    else:
        if db and db.select("costs", {"content_id": content_id, "step": "script"}):
            raise RuntimeError("Paid script missing; restore its artifact before retrying")
        data, _ = claude.run("script", user, schema=SCRIPT_SCHEMA, effort="high", web_search=True, max_searches=8, max_tokens=24000, content_id=content_id, retries=0, **({"supplied_sources": supplied_sources} if getattr(claude, "provider", "anthropic") == "lunaroute" else {}))
        if getattr(claude, "provider", "anthropic") == "lunaroute":
            data["supplied_sources"] = supplied_sources
        raw.parent.mkdir(parents=True, exist_ok=True)
        write_json(raw, data)
        if db and row:
            db.update("content", {"id": content_id}, {"qa_notes": json.dumps({"paid_script": data})})

    if not reused:
        # Hook rewrite pass: cheap, big effect on retention.
        hook_prompt = (
            "Here is the title and the first two narration paragraphs of a video. Rewrite the two paragraphs only if they can be "
            "made sharper: the first sentence states one shocking, named-authority claim as fact (the named actor or a number "
            "must appear in the first forty words), one sentence of why it breaks the usual assumption follows, and the stakes "
            "land by the third sentence with no throat-clearing. The first spoken sentence must state the same claim as the "
            "title. Within the first 45 words, say what it means for the viewer in second person (you, your) and promise the "
            "specific thing the video reveals later; move unit conversions, exact dates and 'the headlines say' after that "
            "promise (viewers were measured leaving at seconds 10-21 when the opening turned to background instead). Keep length similar. "
            "Keep every fact and in-line statistic attribution. Use natural spoken English, hedge uncertain causes, "
            "and use no em dashes, filler or generic transitions. If they are already strong, return them unchanged with changed=false.\n\n"
            f"Title: {data['title']}\n\nParagraph 1: {data['script'][0]}\n\nParagraph 2: {data['script'][1] if len(data['script']) > 1 else ''}"
        )
        try:
            hook, _ = claude.run("hook", hook_prompt, schema=HOOK_SCHEMA, effort="medium", max_tokens=3000, content_id=content_id)
            if hook.get("changed") and len(data["script"]) > 1:
                data["script"][0], data["script"][1] = hook["opening_paragraphs"]
        except Exception as e:  # non-fatal
            log.warning("hook pass skipped: %s", e)

    data = strip_script_dashes(data)

    # Title guardrail.
    all_titles = [data["title"], *data["title_variants"]]
    safe = [t for t in all_titles if not BANNED_TITLE.search(t)]
    if not safe:
        raise RuntimeError("All titles failed the policy guardrail")
    data["title"] = safe[0]
    data["title_variants"] = safe[1:]
    data["thumbnail_text"] = " ".join(data["thumbnail_text"].upper().split()[:5])
    seen = set()
    unique = []
    for short in data.get("shorts", []):
        first = re.split(r"(?<=[.!?])\s+|\n", short["script"].strip(), maxsplit=1)[0].casefold()
        if first in seen or BANNED_TITLE.search(short["hook_title"]):
            log.warning("dropping short with duplicate first sentence or unsafe hook: %s", short["hook_title"])
            continue
        seen.add(first)
        unique.append(short)
    data["shorts"] = unique[:shorts_per_long]
    for i, short in enumerate(data["shorts"]):
        short.setdefault("length", "quick" if i % 2 == 0 else "standard")
    if not reused:
        data["shorts"] = strip_script_dashes({"shorts": tighten_shorts(claude, data["shorts"], content_id)})["shorts"]
    words = sum(len(p.split()) for p in data["script"])
    if not opening_names_actor_or_number(data["script"]):
        # Non-fatal on purpose: rejecting would strand the paid script. The warning is the
        # measurement: count should drop to zero once the prompt rule bites.
        log.warning("script opening has no named actor or number in the first 40 words: %r", data["title"])
    if not opening_has_viewer_stake(data["script"]):
        log.warning("script opening never addresses the viewer (you/your) in the first 45 words: %r", data["title"])
    # Playbook items 13+15 (growth log 2026-11-24): per-script review checklist and art-text
    # digit verification, logged and stored as minor findings (strict QA can still promote them).
    from .review_script import review_findings as _review_findings, log_review as _log_review
    review = _review_findings(data)
    _log_review(review, content_id)
    if review:
        notes = {}
        try:
            notes = json.loads((db.one("content", {"id": content_id}) or {}).get("qa_notes") or "{}") if db else {}
        except (ValueError, TypeError):
            notes = {}
        if isinstance(notes, dict):
            notes["script_review"] = review
            if db:
                db.update("content", {"id": content_id}, {"qa_notes": json.dumps(notes)})
    log.info("script: %d paragraphs, %d words, title: %s", len(data["script"]), words, data["title"])
    return data
