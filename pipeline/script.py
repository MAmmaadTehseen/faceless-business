"""Research + write the long-form script, titles, description, chapters, shot list, and thumbnail text."""
from __future__ import annotations

import re

from .common import Claude, log

BANNED_TITLE = re.compile(
    r"while you sleep|guarantee|get rich|secret method|doctors hate|don't want you to know|make money fast|\$\d+[,\d]*\s*(a|per)\s*(day|week|month)|cure|lose \d+ (lbs|pounds|kg)",
    re.I,
)

SCRIPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "title_variants", "thumbnail_text", "description", "tags", "chapters", "script", "shot_list", "facts_check", "shorts"],
    "properties": {
        "title": {"type": "string", "description": "Best title, under 65 chars"},
        "title_variants": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 6, "description": "Other strong titles using different formulas"},
        "thumbnail_text": {"type": "string", "description": "Max 3 words, uppercase"},
        "description": {"type": "string", "description": "YouTube description: 2-3 sentence summary, then chapters with timestamps as 'mm:ss Title' lines, then 'Sources:' with the urls used"},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 15},
        "chapters": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title", "paragraph_index"], "properties": {"title": {"type": "string"}, "paragraph_index": {"type": "integer"}}}},
        "script": {"type": "array", "items": {"type": "string"}, "description": "Narration paragraphs in order, spoken English only, no headings, no stage directions, 1300-1900 words total"},
        "shot_list": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["paragraph_index", "query", "mood"], "properties": {"paragraph_index": {"type": "integer"}, "query": {"type": "string", "description": "2-4 word stock footage search, concrete and visual (e.g. 'server room aisle', 'city traffic timelapse')"}, "mood": {"type": "string", "enum": ["calm", "tense", "bright", "dark"]}}}, "description": "One entry per paragraph"},
        "facts_check": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["claim", "source", "confidence"], "properties": {"claim": {"type": "string"}, "source": {"type": "string"}, "confidence": {"type": "string", "enum": ["verified", "likely", "unverified"]}}}},
        "shorts": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "object", "additionalProperties": False, "required": ["hook_title", "script", "query"], "properties": {"hook_title": {"type": "string", "description": "Short title under 50 chars, no hashtags"}, "script": {"type": "string", "description": "110-150 words, self-contained, hook first line"}, "query": {"type": "string", "description": "stock footage search for the short"}}}},
    },
}

HOOK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["opening_paragraphs", "changed"],
    "properties": {"opening_paragraphs": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2}, "changed": {"type": "boolean"}},
}


def write_script(claude: Claude, topic: dict, content_id: str) -> dict:
    user = (
        f"Today's video topic: {topic['topic']}\n"
        f"Angle: {topic.get('angle') or 'choose the persona\'s strongest honest angle'}\n"
        f"Seed headline: {topic.get('source_headline') or ''}\nSeed url: {topic.get('source_url') or ''}\n\n"
        "Step 1: research. Use web search to confirm the core facts, find 4-8 concrete, recent, attributable facts "
        "(numbers, names, dates, quotes) and at least one contrasting view. Prefer primary sources and major outlets.\n"
        "Step 2: write the long video following the script sequence and style exactly. 1300-1900 words of narration. "
        "Each paragraph is 2-5 sentences and is one visual beat. Put a clear framework in the middle. "
        "Attribute facts in-line in spoken form. End with one question for the comments and a one-sentence CTA to subscribe.\n"
        "Step 3: produce 5 titles across different formulas, thumbnail text, description with chapters, tags, "
        "one shot-list query per paragraph (concrete, filmable things, never abstract words like 'innovation'), "
        "a facts_check table, and 2-3 Shorts scripts each covering one idea from the video.\n"
        "Hard rules: no income promises, no medical/legal/financial advice, no fabricated quotes, no 'experts say' without naming who. "
        "The first two paragraphs must be a pattern break that pays off the title within ninety seconds."
    )
    data, _ = claude.run("script", user, schema=SCRIPT_SCHEMA, effort="high", web_search=True, max_searches=8, max_tokens=24000, content_id=content_id)

    # Hook rewrite pass: cheap, big effect on retention.
    hook_prompt = (
        "Here is the title and the first two narration paragraphs of a video. Rewrite the two paragraphs only if they can be "
        "made sharper: a bolder specific claim in the first sentence, stakes by the third sentence, no throat-clearing. Keep length similar. "
        "Keep every fact. If they are already strong, return them unchanged with changed=false.\n\n"
        f"Title: {data['title']}\n\nParagraph 1: {data['script'][0]}\n\nParagraph 2: {data['script'][1] if len(data['script']) > 1 else ''}"
    )
    try:
        hook, _ = claude.run("hook", hook_prompt, schema=HOOK_SCHEMA, effort="medium", max_tokens=3000, content_id=content_id)
        if hook.get("changed") and len(data["script"]) > 1:
            data["script"][0], data["script"][1] = hook["opening_paragraphs"]
    except Exception as e:  # non-fatal
        log.warning("hook pass skipped: %s", e)

    # Title guardrail.
    all_titles = [data["title"], *data["title_variants"]]
    safe = [t for t in all_titles if not BANNED_TITLE.search(t)]
    if not safe:
        raise RuntimeError("All titles failed the policy guardrail")
    data["title"] = safe[0]
    data["title_variants"] = safe[1:]
    data["thumbnail_text"] = " ".join(data["thumbnail_text"].upper().split()[:3])
    words = sum(len(p.split()) for p in data["script"])
    log.info("script: %d paragraphs, %d words, title: %s", len(data["script"]), words, data["title"])
    return data
