"""Ten Tongues: one everyday English word a day, taught in ten languages.

Produces one long episode (about five minutes) plus one vertical Short per language, all from a
single structured model call. Visuals are typographic cards (no stock footage); narration mixes
the channel's English narrator with a native-language voice per language.

Usage:
  python -m pipeline.words --channel tentongues --dry-run            # fixture episode, no model calls
  python -m pipeline.words --channel tentongues --no-publish         # model call, renders to out/
  python -m pipeline.words --channel tentongues --publish --privacy private
  python -m pipeline.words --channel tentongues --resume <content-id> # re-render from the saved episode
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import traceback
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .cards import card_clip, render_card
from .common import Channel, Claude, CostGuard, OUT_DIR, ROOT, log, now_iso, slugify, write_json
from .db import DB
from .qa import probe, run_qa
from .retry import production_notes
from .script import BANNED_TITLE, strip_script_dashes
from .words_tts import narrator_spec, synthesize_segments

FIXTURE = ROOT / "data" / "fixture_words.json"
LANDSCAPE, PORTRAIT = (1920, 1080), (1080, 1920)

LANGUAGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["code", "native", "romanisation", "ipa", "example_native", "example_romanised", "example_english",
                 "memory_hook", "cultural_note", "narrator_intro", "narrator_wrap"],
    "properties": {
        "code": {"type": "string", "description": "language code exactly as supplied"},
        "native": {"type": "string", "description": "the word in the language's own script, most common everyday form"},
        "romanisation": {"type": "string", "description": "Latin-letter spelling a learner would use (pinyin with tone marks, Hepburn, etc.); for Latin-script languages repeat the word"},
        "ipa": {"type": "string", "description": "IPA between slashes"},
        "example_native": {"type": "string", "description": "one short everyday sentence (4-9 words) in the native script, with native punctuation"},
        "example_romanised": {"type": "string"},
        "example_english": {"type": "string"},
        "memory_hook": {"type": "string", "description": "one concrete, slightly playful memory hook, 8-20 words"},
        "cultural_note": {"type": "string", "description": "one true, specific, non-political cultural note or usage tip, 10-25 words; include a common regional variant when one exists"},
        "narrator_intro": {"type": "string", "description": "English narrator line naming the language and saying the word with its romanisation, 8-16 words"},
        "narrator_wrap": {"type": "string", "description": "English narrator spoken version of the memory hook and the cultural note, 25-45 words"},
    },
}

WORDS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["word", "title", "title_variants", "description", "tags", "intro", "outro", "languages"],
    "properties": {
        "word": {"type": "string"},
        "title": {"type": "string", "description": "Long video title under 60 chars, must contain the word in capitals and the phrase '10 languages'"},
        "title_variants": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string", "description": "2-3 sentence summary for YouTube; the word list is appended automatically"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "intro": {"type": "string", "description": "Opening narration, 30-50 words: the English word, why it matters, what is coming"},
        "outro": {"type": "string", "description": "Closing narration, 30-50 words: recap, one comment question, one-sentence subscribe CTA"},
        "languages": {"type": "array", "items": LANGUAGE_SCHEMA, "description": "one entry per supplied language, in the supplied order"},
    },
}


def languages(channel: Channel) -> list[dict]:
    langs = channel.cfg.get("languages") or []
    if not langs:
        raise ValueError(f"channel {channel.key} has no languages configured")
    return langs


def word_inventory(channel: Channel) -> list[dict]:
    data = json.loads((channel.dir / "words.json").read_text())
    return data["words"]


def used_words(db, channel: Channel) -> set[str]:
    used = {w.lower() for w in (db.setting(f"words_used_{channel.key}") or [])}
    for row in db.select("content", {"channel": channel.key, "kind": "long"}):
        if row.get("topic"):
            used.add(str(row["topic"]).lower())
    return used


def pick_word(db, channel: Channel, requested: str | None = None) -> str:
    """Next unused word in inventory order; an explicit word is accepted even when used (owner re-runs)."""
    inventory = word_inventory(channel)
    if requested:
        requested = requested.strip().lower()
        if requested not in {w["word"] for w in inventory}:
            raise ValueError(f"{requested!r} is not in {channel.key}/words.json")
        return requested
    used = used_words(db, channel)
    for entry in inventory:
        if entry["word"].lower() not in used:
            return entry["word"]
    raise RuntimeError(f"Word inventory exhausted for {channel.key}; add words to words.json")


def mark_used(db, channel: Channel, word: str) -> None:
    current = [w for w in (db.setting(f"words_used_{channel.key}") or []) if w.lower() != word.lower()]
    db.set_setting(f"words_used_{channel.key}", current + [word.lower()])


def validate_episode(data: dict, langs: list[dict]) -> dict:
    data = strip_script_dashes(data)
    expected = [l["code"] for l in langs]
    got = [l.get("code") for l in data.get("languages", [])]
    if got != expected:
        by_code = {l.get("code"): l for l in data.get("languages", [])}
        # GLM sometimes appends an invented extra entry ("fr-example-note"); every configured language is what counts.
        if not set(expected) <= set(by_code) or len(set(got) & set(expected)) != len(expected):
            raise ValueError(f"episode languages {got} do not match configured {expected}")
        data["languages"] = [by_code[c] for c in expected]
    for lang in data["languages"]:
        for key in ("native", "romanisation", "example_native", "narrator_intro", "narrator_wrap", "memory_hook", "cultural_note"):
            if not str(lang.get(key, "")).strip():
                raise ValueError(f"{lang['code']}: empty {key}")
        if not re.search(r"[A-Za-z]", lang["romanisation"]):
            raise ValueError(f"{lang['code']}: romanisation must use Latin letters")
        if not lang.get("ipa", "").strip():
            lang["ipa"] = ""
    if BANNED_TITLE.search(data["title"]) or any(BANNED_TITLE.search(t) for t in data.get("title_variants", [])):
        safe = [t for t in [data["title"], *data.get("title_variants", [])] if not BANNED_TITLE.search(t)]
        if not safe:
            raise RuntimeError("All titles failed the policy guardrail")
        data["title"], data["title_variants"] = safe[0], safe[1:]
    if "10 languages" not in data["title"].lower() and "ten languages" not in data["title"].lower():
        data["title"] = f"{data['word'].upper()} in 10 languages: {data['title']}"[:100]
    return data


def episode_prompt(word: str, langs: list[dict]) -> str:
    listing = json.dumps([{"code": l["code"], "name": l["name"]} for l in langs])
    return (
        f"Today's English word: {word}\n"
        f"Languages, in this exact order: {listing}\n\n"
        "Write one Ten Tongues episode as JSON. For every language give the most common everyday translation of "
        "the word in the native script, a learner romanisation (pinyin with tone marks for Mandarin, Hepburn for "
        "Japanese, IAST-style for Hindi, common Urdu romanisation, a simple scheme for Russian; for "
        "Latin-script languages repeat the word), IPA, one short everyday example sentence in the native script with its "
        "romanisation and English, one concrete memory hook, and one true cultural note or usage tip (name a common "
        "regional variant when there is one, for example Brazilian vs European Portuguese). Choose the form a beginner would learn first. "
        "narrator_intro is the English narrator's line for that block: name the language and say the word using the "
        "romanisation, for example 'Number three, Spanish. Water is agua.' Include the block number. narrator_wrap is "
        "the narrator speaking the memory hook and the cultural note in natural spoken English, 25 to 45 words. "
        "Intro and outro are 30 to 50 words each; the outro ends with one question for the comments and a one-sentence "
        "subscribe CTA. Title under 60 characters containing the word in capitals and '10 languages'. "
        "Four title variants. Tags: the word, each language name, 'learn <language>', 'word of the day'. "
        "Simple natural spoken English, no em dashes, no filler, nothing political, no medical or financial content, "
        "no claims about a native-level accent. Return JSON only."
    )


def generate_episode(claude, db, channel: Channel, word: str, content_id: str) -> dict:
    """One structured call, checkpointed before validation so retries never buy it twice."""
    out = OUT_DIR / content_id
    saved = out / "episode.json"
    row = db.one("content", {"id": content_id}) or {}
    try:
        notes = json.loads(row.get("qa_notes") or "{}")
    except (ValueError, TypeError):
        notes = {}
    checkpoint = notes.get("words_episode") if isinstance(notes, dict) else None
    if saved.is_file():
        data = json.loads(saved.read_text())
    elif checkpoint:
        data = checkpoint
    else:
        if db.select("costs", {"content_id": content_id, "step": "words"}):
            raise RuntimeError("Paid episode missing; restore its artifact (episode.json) before retrying")
        if not CostGuard(db).check("words", est_usd=0.6):
            raise RuntimeError("Budget guard stopped the words episode")
        data, _ = claude.run("words", episode_prompt(word, languages(channel)), schema=WORDS_SCHEMA,
                             effort="medium", max_tokens=12000, content_id=content_id, retries=1)
        out.mkdir(parents=True, exist_ok=True)
        write_json(saved, data)
        db.update("content", {"id": content_id}, {"qa_notes": json.dumps({"words_episode": data})})
    return data


# ---------- segment plans ----------

def _lang_cfg(channel: Channel, code: str) -> dict:
    return next(l for l in languages(channel) if l["code"] == code)


def _word_card(channel, cfg, lang, n, total, word):
    return {"kicker": f"{n} / {total}  ·  {cfg['name']}  ·  {word.upper()}", "headline": lang["native"],
            "headline_script": cfg["script"], "sub": lang["romanisation"], "sub2": lang.get("ipa", ""),
            "colour": cfg["colour"], "footer": channel.name}


def _sentence_card(channel, cfg, lang, n, total, word):
    return {"kicker": f"{n} / {total}  ·  {cfg['name']}  ·  example", "headline": lang["example_native"],
            "headline_script": cfg["script"], "sub": lang["example_romanised"], "sub2": lang["example_english"],
            "colour": cfg["colour"], "footer": f"{channel.name}  ·  {word.upper()} = {lang['romanisation']}"}


def _hook_card(channel, cfg, lang, n, total, word):
    return {"kicker": f"{n} / {total}  ·  {cfg['name']}  ·  remember it", "headline": lang["romanisation"],
            "headline_script": "latin", "headline_scale": 0.62, "sub": f"{word} in {cfg['name']}",
            "lines": [(lang["memory_hook"], "latin"), (lang["cultural_note"], "latin")],
            "colour": cfg["colour"], "footer": channel.name}


def _title_card(channel, word, sub, colour):
    return {"kicker": f"{channel.name}  ·  word of the day", "headline": word.upper(), "headline_script": "latin",
            "sub": sub, "colour": colour, "footer": channel.cfg.get("tagline", "")}


def _recap_card(channel, data, langs):
    chips = [(f"{cfg['name']} {lang['romanisation']}", "latin") for cfg, lang in zip(langs, data["languages"])]
    return {"kicker": f"{channel.name}  ·  recap", "headline": data["word"].upper(), "headline_script": "latin",
            "sub": "in 10 languages", "chips": chips, "colour": channel.style.get("accent", [167, 139, 250]),
            "footer": "Which one surprised you? Tell us in the comments."}


def long_segments(channel: Channel, data: dict) -> list[dict]:
    narrator = narrator_spec(channel.voice)
    langs = languages(channel)
    word = data["word"]
    segs = [{"kind": "narrator", "text": data["intro"], "spec": narrator,
             "card": _title_card(channel, word, "in 10 languages", channel.style.get("accent", [167, 139, 250]))}]
    total = len(langs)
    for n, (cfg, lang) in enumerate(zip(langs, data["languages"]), 1):
        native = {**cfg["tts"], "rate": "+0%"}
        word_card = _word_card(channel, cfg, lang, n, total, word)
        segs += [
            {"kind": "narrator", "text": lang["narrator_intro"], "spec": narrator, "card": word_card},
            {"kind": "native", "text": lang.get("tts_word") or f"{lang['native']}. {lang['native']}.", "spec": native,
             "caption": f"{lang['romanisation']}  ·  {lang['romanisation']}", "card": word_card},
            {"kind": "native", "text": lang.get("tts_example") or lang["example_native"], "spec": native,
             "caption": lang["example_romanised"], "card": _sentence_card(channel, cfg, lang, n, total, word)},
            {"kind": "narrator", "text": lang["narrator_wrap"], "spec": narrator, "card": _hook_card(channel, cfg, lang, n, total, word)},
        ]
    segs.append({"kind": "narrator", "text": data["outro"], "spec": narrator, "card": _recap_card(channel, data, langs)})
    return segs


def short_segments(channel: Channel, data: dict, code: str) -> list[dict]:
    narrator = narrator_spec(channel.voice)
    cfg = _lang_cfg(channel, code)
    lang = next(l for l in data["languages"] if l["code"] == code)
    native = {**cfg["tts"], "rate": "+0%"}
    word = data["word"]
    n = [l["code"] for l in languages(channel)].index(code) + 1
    total = len(languages(channel))
    word_card = _word_card(channel, cfg, lang, n, total, word)
    intro = re.sub(r"^\s*number\s+\w+[,.]?\s*", "", lang["narrator_intro"], flags=re.I).strip()
    return [
        {"kind": "narrator", "text": f"How do you say {word} in {cfg['name']}?", "spec": narrator,
         "card": _title_card(channel, word, f"in {cfg['name']}", cfg["colour"])},
        {"kind": "narrator", "text": intro, "spec": narrator, "card": word_card},
        {"kind": "native", "text": lang.get("tts_word") or f"{lang['native']}. {lang['native']}.", "spec": native,
         "caption": f"{lang['romanisation']}  ·  {lang['romanisation']}", "card": word_card},
        {"kind": "native", "text": lang.get("tts_example") or lang["example_native"], "spec": native,
         "caption": lang["example_romanised"], "card": _sentence_card(channel, cfg, lang, n, total, word)},
        {"kind": "narrator", "text": lang["narrator_wrap"], "spec": narrator, "card": _hook_card(channel, cfg, lang, n, total, word)},
        {"kind": "narrator", "text": f"Say it with me: {lang['romanisation']}. New word tomorrow.", "spec": narrator, "card": word_card},
    ]


# ---------- rendering ----------

def render_cards_video(timings: list[dict], audio: Path, srt: Path, out: Path, orientation: str,
                       channel: Channel, music_db: float = -24.0) -> Path:
    from .render import FONT_DIR, _caption_style, _check_black, _font, _music
    style = channel.style
    size = LANDSCAPE if orientation == "landscape" else PORTRAIT
    work = out.parent / f"{out.stem}_work"
    work.mkdir(parents=True, exist_ok=True)
    try:
        pngs: dict[str, Path] = {}
        clips = []
        total = timings[-1]["end"]
        for i, t in enumerate(timings):
            # Each card stays up through the silence gap until the next segment starts.
            until = timings[i + 1]["start"] if i + 1 < len(timings) else total
            card = t["segment"]["card"]
            key = json.dumps(card, sort_keys=True, ensure_ascii=False) + orientation
            if key not in pngs:
                pngs[key] = render_card(work / f"card_{len(pngs):03d}.png", size=size, bg=tuple(style.get("bg", (20, 14, 36))),
                                        accent=tuple(style.get("accent", (167, 139, 250))), colour=tuple(card["colour"]),
                                        kicker=card["kicker"], headline=card["headline"], headline_script=card.get("headline_script", "latin"),
                                        sub=card.get("sub", ""), sub2=card.get("sub2", ""), lines=card.get("lines"), footer=card.get("footer", ""),
                                        chips=[tuple(c) for c in card.get("chips", [])] or None,
                                        headline_scale=card.get("headline_scale", 1.0))
            sec = max(until - t["start"], 0.5)
            clips.append(card_clip(pngs[key], sec, work / f"seg_{t['index']:03d}.mp4", orientation))
        listing = work / "list.txt"
        listing.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
        visual = work / "visual.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(visual)], check=True)
        for i, frac in enumerate((0.08, 0.2, 0.35, 0.5, 0.65, 0.8)):
            clean = out.with_suffix(f".clean{i}.jpg") if i else out.with_suffix(".clean.jpg")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(1.0, total * frac):.2f}", "-i", str(visual), "-frames:v", "1", "-q:v", "2", str(clean)], check=True)
        srt_path = str(srt.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        fontsdir = f":fontsdir={FONT_DIR}" if _font() else ""
        vf = f"subtitles='{srt_path}':force_style='{_caption_style(orientation, style)}'{fontsdir}"
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(visual), "-i", str(audio)]
        music = _music()
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    f"[2:a]volume={music_db}dB[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-vf", vf, "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)
        _check_black(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    log.info("render[words]: %s", out)
    return out


def make_thumbnail(channel: Channel, data: dict, out: Path) -> Path:
    """Thumbnail audit 2026-11-19: the word must be readable at phone size and the translations are
    the promise, so three of them are drawn large in their own scripts on a bright saturated panel
    (Studio CTR was 0.8% on the old dark gradient with six tiny chips)."""
    from PIL import Image, ImageDraw
    from .cards import font, _text, _direction
    langs = languages(channel)
    picks = [(lang["native"], cfg["script"]) for cfg, lang in zip(langs, data["languages"])]
    # Prefer visually distinct scripts first so the card reads as "many languages" at a glance.
    order = sorted(range(len(picks)), key=lambda i: (picks[i][1] == "latin", i))
    picks = [picks[i] for i in order][:3]
    accent = tuple(channel.style.get("accent", (167, 139, 250)))
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), accent)
    d = ImageDraw.Draw(img)
    # Right panel: deep brand colour, strong edge against the saturated left.
    bg = tuple(channel.style.get("bg", (20, 14, 36)))
    d.rectangle((640, 0, w, h), fill=bg)
    d.rectangle((0, 0, w, 16), fill=(255, 255, 255))
    word = data["word"].upper()
    hf = font("latin", 150 if len(word) <= 6 else 118 if len(word) <= 9 else 92)
    for dx, dy in ((-5, -5), (5, -5), (-5, 5), (5, 5), (0, 7)):
        _text(d, (56 + dx, 150 + dy), word, hf, (0, 0, 0))
    _text(d, (56, 150), word, hf, (255, 255, 255))
    kf = font("latin", 44)
    _text(d, (60, 330), "IN 10 LANGUAGES", kf, (20, 14, 36))
    # Three translations, big, on the dark panel.
    y = 90
    for text, script in picks:
        f = font(script, 96 if len(text) <= 6 else 72)
        _text(d, (700, y), text, f, (255, 255, 255), script)
        y += 190
    ff = font("latin", 34)
    _text(d, (60, h - 80), channel.name, ff, (20, 14, 36))
    img.save(out, "JPEG", quality=90)
    return out


def long_description(channel: Channel, data: dict) -> str:
    langs = languages(channel)
    rows = [f"{cfg['name']}: {lang['native']} ({lang['romanisation']}) {lang.get('ipa', '')}".rstrip()
            for cfg, lang in zip(langs, data["languages"])]
    parts = [data["description"].strip(), f"{data['word'].upper()} in 10 languages:\n" + "\n".join(rows)]
    if channel.cfg.get("tts_attribution"):
        parts.append(channel.cfg["tts_attribution"])
    if channel.cfg.get("description_footer"):
        parts.append(channel.cfg["description_footer"])
    return "\n\n".join(parts)


def short_title(data: dict, cfg: dict, lang: dict, day: str | None = None, ab: bool = False) -> str:
    """Control: "Rice in Russian: ris". With channel.json `short_title_ab`, even-numbered days use the
    question stem YouTube autocomplete offers for every word ("how to say rice in ..."); all ten
    languages share the day's variant, so the comparison is day against day (growth log 2026-11-24).
    """
    word = data["word"].capitalize()
    if ab and day and int(day[-2:]) % 2 == 0:
        return f"How to Say {word} in {cfg['name']} ({lang['romanisation']})"[:100]
    return f"{word} in {cfg['name']}: {lang['romanisation']}"[:100]


# Native speakers search the other way round, in their own language (Studio search terms 2026-11-24:
# "hindi mein dudh kaise likhate hain", "chai ko hindi mein kya bolate hain", "cómo se dice leche en inglés").
# {w} is the English word, {r} the romanisation without accents.
NATIVE_QUERIES = {
    "hi": ["{w} ko hindi mein kya kehte hain", "hindi mein {r} kaise likhte hain", "{r} ko english mein kya kehte hain"],
    "ur": ["{w} ko urdu mein kya kehte hain", "{r} ko english mein kya kehte hain"],
    "es": ["cómo se dice {r} en inglés", "{w} en español"],
    "pt": ["como se diz {r} em inglês", "{w} em português"],
    "fr": ["comment dit-on {r} en anglais", "{w} en français"],
    "de": ["was heißt {r} auf englisch", "{w} auf deutsch"],
    "it": ["come si dice {r} in inglese", "{w} in italiano"],
}


def plain(text: str) -> str:
    """Romanisation as people type it: "dūdh" -> "dudh", "shuǐguǒ" -> "shuiguo"."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def short_tags(word: str, cfg: dict, lang: dict | None = None) -> list[str]:
    """Phrases from YouTube autocomplete (2026-11-24): "how to say egg in french", "egg in french pronunciation",
    plus the native-language questions in NATIVE_QUERIES and "<romanisation> in english" when the language is known."""
    name = cfg["name"]
    tags = [name, f"learn {name}", word, "word of the day", f"{word} in {name}", f"how to say {word} in {name}",
            f"{word} in {name} pronunciation", f"{name} word for {word}"]
    if lang and lang.get("romanisation"):
        r = plain(lang["romanisation"])
        tags += [q.format(w=word, r=r) for q in NATIVE_QUERIES.get(cfg.get("code", ""), [])]
        if r != word.lower():
            tags.append(f"{r} in english")
    return list(dict.fromkeys(tags))[:15]


def short_description(channel: Channel, data: dict, cfg: dict, lang: dict) -> str:
    return (f"How to say {data['word']} in {cfg['name']}: {lang['native']} ({lang['romanisation']}) {lang.get('ipa', '')}\n"
            f"{lang['example_native']}\n{lang['example_romanised']}\n{lang['example_english']}\n\n"
            f"Full episode, all 10 languages: {{LONG_URL}}\n{channel.cfg.get('description_footer', '')}\n#shorts #learn{cfg['name'].lower()}")


# ---------- production ----------

def _notes(issues, channel) -> dict:
    """Provenance in the shape retry.production_notes writes, always as a dict."""
    notes = json.loads(production_notes(issues, channel, "produce"))
    return notes if isinstance(notes, dict) else {"issues": notes}


def produce_episode(db, channel: Channel, *, dry_run=False, no_publish=False, privacy=None,
                    resume: str | None = None, word: str | None = None, bank: bool = False) -> dict:
    if channel.cfg.get("format") != "words":
        raise ValueError(f"channel {channel.key} is not a words-format channel")
    if db.setting("pipeline_paused", False) and not dry_run:
        log.info("words: pipeline paused")
        return None
    langs = languages(channel)
    today = datetime.now(timezone.utc).date().isoformat()
    claude = None if dry_run else Claude(db, channel=channel)
    if resume:
        content_id = resume
        row = db.one("content", {"id": content_id}) or {}
        word = row.get("topic") or content_id.split("-", 4)[-1]
        if row.get("status") == "killed":
            raise RuntimeError("Refusing to rebuild killed content")
        data = generate_episode(claude, db, channel, word, content_id) if claude else json.loads((OUT_DIR / content_id / "episode.json").read_text())
    elif dry_run:
        data = json.loads(FIXTURE.read_text())
        word = data["word"]
        content_id = f"{channel.key}-{today}-{slugify(word, 30)}"
    else:
        if bank:
            from .stockpile import preflight
            preflight(db)  # Drive space before paying for the episode
        # Parallel bank runs share the inventory: pick and claim the word (draft row) under one lock.
        from .stockpile import lock
        with lock(db, f"words_pick_{channel.key}", wait_seconds=600):
            word = pick_word(db, channel, word)
            content_id = f"{channel.key}-{today}-{slugify(word, 30)}"
            db.upsert("content", {"id": content_id, "channel": channel.key, "kind": "long", "topic": word,
                                  "title": f"{word.upper()} in 10 languages", "status": "draft"}, on="id")
            mark_used(db, channel, word)
        data = generate_episode(claude, db, channel, word, content_id)
    data = validate_episode(data, langs)
    out = OUT_DIR / content_id
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "episode.json", data)
    db.upsert("content", {"id": content_id, "channel": channel.key, "kind": "long", "topic": word,
                          "title": data["title"], "status": "draft"}, on="id")
    style_note = ("Visual style: intentional typographic word cards on a dark background with a coloured bar; "
                  "non-Latin scripts (Chinese, Devanagari, Nastaliq Urdu, Cyrillic) on the cards are expected. "
                  "Cards are the design, not placeholder footage.")

    # Long episode
    segs = long_segments(channel, data)
    tts = synthesize_segments(segs, out, name="voice")
    video = render_cards_video(tts["timings"], tts["audio"], tts["srt"], out / f"{content_id}.mp4", "landscape", channel)
    thumb = make_thumbnail(channel, data, out / f"{content_id}.jpg")
    narration = "\n".join(s["text"] for s in segs if s["kind"] == "narrator")
    desc = long_description(channel, data)
    db.update("content", {"id": content_id}, {
        "title": data["title"], "title_variants": data.get("title_variants", []), "description": desc,
        "script": narration, "tags": data.get("tags", [])[:15], "duration_sec": tts["duration"],
        "file_path": str(video), "thumbnail_path": str(thumb), "status": "rendered", "placeholder": False,
        "chapters": [{"title": cfg["name"], "sec": round(t["start"])} for cfg, t in zip(langs, [x for x in tts["timings"] if x["index"] in {1 + 4 * i for i in range(len(langs))}])],
    })
    qa = run_qa(claude, video, thumb, tts["duration"], content_id, out / "qa", vision=bool(claude), db=db,
                caption_text=narration, style_note=style_note)
    db.update("content", {"id": content_id}, {"qa_status": "passed" if qa["pass"] else "failed",
              "qa_notes": json.dumps({**_notes(qa["issues"], channel), "words_episode": data})})
    if not qa["pass"]:
        db.update("content", {"id": content_id}, {"status": "qa_failed"})
        raise RuntimeError(f"QA failed for {content_id}: {qa['issues']}")

    # One Short per language
    shorts = []
    for n, (cfg, lang) in enumerate(zip(langs, data["languages"]), 1):
        sid = f"{content_id}-short-{n:02d}"
        try:
            ssegs = short_segments(channel, data, cfg["code"])
            stts = synthesize_segments(ssegs, out, name=f"{sid}_voice")
            sfile = render_cards_video(stts["timings"], stts["audio"], stts["srt"], out / f"{sid}.mp4", "portrait", channel, music_db=-22.0)
        except Exception as exc:
            log.error("short %s failed: %s", sid, exc)
            continue
        snarr = "\n".join(s["text"] for s in ssegs if s["kind"] == "narrator")
        sqa = run_qa(claude, sfile, None, stts["duration"], sid, out / f"qa-{sid}", vision=bool(claude), db=db,
                     caption_text=snarr, style_note=style_note)
        db.upsert("content", {"id": sid, "channel": channel.key, "kind": "short", "parent_id": content_id,
                              "topic": word, "title": short_title(data, cfg, lang, today, bool(channel.cfg.get("short_title_ab"))), "file_path": str(sfile),
                              "description": short_description(channel, data, cfg, lang), "script": snarr,
                              "tags": short_tags(word, cfg, lang),
                              "duration_sec": stts["duration"], "placeholder": False,
                              "status": "rendered" if sqa["pass"] else "qa_failed",
                              "qa_status": "passed" if sqa["pass"] else "failed",
                              "qa_notes": production_notes(sqa["issues"], channel, "produce")}, on="id")
        if not sqa["pass"]:
            log.error("short %s failed QA: %s", sid, sqa["issues"])
            continue
        shorts.append({"id": sid, "file": str(sfile), "language": cfg["code"]})
    if not dry_run:
        mark_used(db, channel, word)
    result = {"content_id": content_id, "word": word, "video": str(video), "thumbnail": str(thumb),
              "shorts": [s["file"] for s in shorts], "title": data["title"]}
    if bank and not dry_run:
        from .stockpile import bank_bundle
        result["stockpile"] = bank_bundle(db, content_id, channel, claude=claude)
    elif not dry_run and not no_publish:
        from .publish import publish_all
        result["publications"] = publish_all(db, content_id, privacy or db.setting("publish_privacy", "private"), channel)
        if any(p.get("platform") == "youtube" and p.get("content_id") == content_id for p in result["publications"]):
            try:
                from .words_article import write_words_article
                write_words_article(db, content_id)
            except Exception as e:
                log.warning("article skipped for %s (%s)", content_id, type(e).__name__)
    write_json(out / "result.json", result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="tentongues", choices=Channel.keys())
    ap.add_argument("--dry-run", action="store_true", help="fixture episode, no model calls, no upload")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--privacy", choices=["private", "public", "unlisted"])
    ap.add_argument("--word", help="force a word from words.json (owner re-runs)")
    ap.add_argument("--resume", help="content id: re-render from the saved episode without a new model call")
    ap.add_argument("--bank", action="store_true", help="store the finished episode in the Drive stockpile, no publications")
    args = ap.parse_args()
    db = DB()
    channel = Channel(args.channel)
    # Bank runs log separately so the daily gap fill never mistakes them for the live run.
    run = db.insert("runs", {"workflow": "words-bank" if args.bank else "words", "channel": channel.key, "status": "running"})
    try:
        result = produce_episode(db, channel, dry_run=args.dry_run, no_publish=args.no_publish or not args.publish,
                                 privacy=args.privacy, resume=args.resume, word=args.word, bank=args.bank)
        from .publish import youtube
        expired = youtube.auth_failed(channel)
        db.update("runs", {"id": run["id"]}, {"status": "failed" if expired else "ok" if result else "skipped",
                  "finished_at": now_iso(), "log": json.dumps({"result": result, "error": youtube.auth_error(channel)} if expired else result)[:20000]})
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        db.update("runs", {"id": run["id"]}, {"status": "failed", "finished_at": now_iso(),
                  "log": json.dumps({"error": type(e).__name__, "reason": str(e)[:300]})})
        log.error("words failed: %s\n%s", e, traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
