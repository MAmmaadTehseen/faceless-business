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
        "thumbnail_text": {"type": "string", "description": "Max 3 words, uppercase"},
        "description": {"type": "string", "description": "YouTube description: first sentence names the subject and the searchable topic phrase in plain words, 2-3 sentence summary, then chapters with timestamps as 'mm:ss Title' lines whose labels are phrases people would search, then 'Sources:' with the urls used"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "chapters": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title", "paragraph_index"], "properties": {"title": {"type": "string"}, "paragraph_index": {"type": "integer"}}}},
        "script": {"type": "array", "items": {"type": "string"}, "description": "Narration paragraphs in order, spoken English only, no headings, no stage directions, 1300-1900 words total"},
        "shot_list": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["paragraph_index", "query", "mood"], "properties": {"paragraph_index": {"type": "integer"}, "query": {"type": "string", "description": "2-4 word stock VIDEO search that a free stock library will certainly have: generic, physical, filmable things (e.g. 'office worker typing', 'server room aisle', 'city street timelapse', 'handshake meeting', 'parliament building exterior'). Never company names, countries, people, abstract nouns, or events."}, "mood": {"type": "string", "enum": ["calm", "tense", "bright", "dark"]}}}, "description": "One entry per paragraph"},
        "facts_check": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["claim", "source", "confidence"], "properties": {"claim": {"type": "string"}, "source": {"type": "string"}, "confidence": {"type": "string", "enum": ["verified", "likely", "unverified"]}}}},
        "shorts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["hook_title", "script", "query"], "properties": {"hook_title": {"type": "string", "description": "Short title under 45 chars, no hashtags; names the specific subject (proper noun or number) in its first three words; it is shown on screen for the first two seconds"}, "script": {"type": "string", "description": "75-110 words, self-contained; first sentence under 12 words with a named actor or a number; payoff by sentence three; last line a question or a loop back to the first line"}, "query": {"type": "string", "description": "stock footage search for the short"}}}},
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
TIGHTEN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["script"],
    "properties": {"script": {"type": "string", "description": "The tightened Short script, 75-110 words"}},
}


def word_count(text: str) -> int:
    return len(str(text or "").split())


def tighten_shorts(claude, shorts: list[dict], content_id: str | None = None) -> list[dict]:
    """Shorten any Short script over the word budget with one small model call each.

    Non-fatal: a failed or still-too-long rewrite keeps the original script. Facts,
    the first-sentence hook and the closing question must survive the rewrite.
    """
    out = []
    for short in shorts:
        words = word_count(short.get("script"))
        log.info("short %r: %d words", short.get("hook_title"), words)
        if words <= SHORT_WORDS[1]:
            out.append(short)
            continue
        prompt = (
            f"This Short script is {words} words; it must be {SHORT_WORDS[0]}-{SHORT_WORDS[1]} words (about 35-45 seconds spoken). "
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
            if SHORT_WORDS_ACCEPT[0] <= n <= SHORT_WORDS_ACCEPT[1]:
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


def write_script(claude: Claude, topic: dict, content_id: str, shorts_per_long: int = 4) -> dict:
    user = (
        f"Today's video topic: {topic['topic']}\n"
        f"Angle: {topic.get('angle') or 'choose the persona\'s strongest honest angle'}\n"
        f"Seed headline: {topic.get('source_headline') or ''}\nSeed url: {topic.get('source_url') or ''}\n\n"
        "Step 1: research. Use web search to confirm the core facts, find 4-8 concrete, recent, attributable facts "
        "(numbers, names, dates, quotes) and at least one contrasting view. Prefer primary sources and major outlets.\n"
        "Step 2: write the long video following the script sequence and style exactly. 1300-1900 words of narration. "
        "Each of the five parts must introduce a genuinely different angle. No two paragraphs may restate the same point. "
        "Use simple natural spoken English, no filler or generic transitions. Hedge uncertain causes with can, may, "
        "or may indicate. No em dashes in any captions, titles, descriptions or Shorts. Attribute every statistic in-line. "
        "Each paragraph is 2-5 sentences and is one visual beat. Put a clear framework in the middle. "
        "Attribute facts in-line in spoken form. End with one question for the comments and a one-sentence CTA to subscribe.\n"
        "Step 3: produce 5 titles across different formulas, thumbnail text, description with chapters, tags, "
        "Title rules: the main title begins with the searchable subject (the named organisation, object, event or topic phrase a person would type) inside the first 40 characters, then the angle; clever lines go in title_variants, never first. "
        "Description rule: its first sentence states the subject and the topic phrase plainly; chapter labels are search phrases, not jokes. "
        "one shot-list query per paragraph (generic stock-video phrases that always exist: people at desks, buildings, screens, streets, hands, machines; vary them so no two consecutive paragraphs share a query; never names of companies, countries, or people), "
        f"a facts_check table, and exactly {shorts_per_long} Shorts scripts. Each must cover a DIFFERENT angle "
        "(the number, the human consequence, the contrarian take, the what-to-do-now), be self-contained, "
        "75-110 words (about 35-45 seconds spoken), with its own hook in the first line. No two Shorts may share a hook or statistic. "
        "Shorts hook rules: hook_title is under 45 characters and names the specific subject (a proper noun or a number) in its first three words, because it is shown on screen for the first two seconds; the first sentence is under twelve words and names a specific actor, object or number; "
        "no setup, no 'in this video', no question-only opener; the payoff lands by the third sentence; "
        "the last line is either a question the viewer can answer in one comment or a line that loops back to the first sentence.\n"
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
            "made sharper: a bolder specific claim in the first sentence, stakes by the third sentence, no throat-clearing. Keep length similar. "
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
    data["thumbnail_text"] = " ".join(data["thumbnail_text"].upper().split()[:3])
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
    if not reused:
        data["shorts"] = strip_script_dashes({"shorts": tighten_shorts(claude, data["shorts"], content_id)})["shorts"]
    words = sum(len(p.split()) for p in data["script"])
    log.info("script: %d paragraphs, %d words, title: %s", len(data["script"]), words, data["title"])
    return data
