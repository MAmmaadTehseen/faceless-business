# Ten Tongues: the language-learning channel (key `tentongues`)

One everyday English word a day, taught in ten languages. Each episode produces one long video
(about five minutes), ten vertical Shorts (one per language) and keeps per-language YouTube
playlists filled. Visuals are typographic cards, not stock footage. Everything runs on the
existing pipeline (DB, QA, quota, scheduler, YouTube/Meta publishers) with one new module.

## 1. R&D decisions

### Format
- Episode = one word. Long video: intro, ten fixed-order language blocks (narrator intro, native
  voice says the word twice, native voice says one example sentence, narrator gives a memory hook
  and one cultural note), recap outro. Shorts: the same block per language, 30 to 45 seconds,
  titled "Water in Spanish: agua" so the title names the language (playlist matching and search).
- One structured model call per episode (`pipeline/words.py`, schema `WORDS_SCHEMA`), through the
  shared `Claude` interface, so LunaRoute (GLM 5.3) and Anthropic both work. Cost estimate 0.60 USD
  on Anthropic; CostGuard checks it. No web search is needed: the content is dictionary knowledge.
- Everything else (TTS, cards, render, QA, publish) is free, local to the runner.

### Languages chosen (ordered by speakers, Ethnologue 2025 totals)
Top ten languages by total speakers after English are Mandarin, Hindi, Spanish, Arabic, French,
Bengali, Portuguese, Russian, Urdu, Indonesian. The launch set keeps eight of them and swaps two
whose only free TTS has unclear licences (see table) for two Kokoro-native languages with strong
search demand:

| # | Language | Script on card | TTS | Licence |
|---|---|---|---|---|
| 1 | Mandarin | Chinese (Noto Sans CJK) | Kokoro `z` / `zf_xiaoxiao` (needs `misaki[zh]`); fallback Piper `zh_CN-chaowen-medium` | Apache 2.0; Piper voice CC0 |
| 2 | Hindi | Devanagari | Kokoro `h` / `hf_alpha` | Apache 2.0 |
| 3 | Spanish | Latin | Kokoro `e` / `ef_dora` | Apache 2.0 |
| 4 | French | Latin | Kokoro `f` / `ff_siwis` | Apache 2.0 (SIWIS CC BY) |
| 5 | Bengali | Bengali | Piper `bn_BD-google-medium` (speaker 0) | OpenSLR 37 CC BY-SA 4.0 + CMU; attribution line in every description |
| 6 | Portuguese | Latin | Kokoro `p` / `pf_dora` | Apache 2.0 |
| 7 | Russian | Cyrillic | Piper `ru_RU-denis-medium` | CC0 |
| 8 | Urdu | Nastaliq (Noto Nastaliq Urdu) | Piper `ur_PK-fasih-medium` | MIT |
| 9 | Japanese | Japanese (Noto Sans CJK) | Kokoro `j` / `jf_alpha` (needs fugashi + unidic-lite + pyopenjtalk-plus) | Apache 2.0 |
| 10 | Italian | Latin | Kokoro `i` / `if_sara` | Apache 2.0 |

Deferred, swap in by editing `languages` and `topic_playlists` in `channels/tentongues/channel.json`:
- **Arabic**: the only Piper voice (`ar_JO-kareem`) says "License: See URL" and the dataset
  repository has no licence file. Kokoro has no Arabic. Not used until a licence is confirmed.
- **Indonesian**: Piper `id_ID-news_tts` points at a Kaggle page for its licence; unclear.
- Rejected engines: Meta MMS-TTS (CC BY-NC), Coqui XTTS (CPML, non-commercial), Fish/F5 (NC
  weights), Piper Hindi voices (CC BY-NC-SA), Piper `ru_RU-ruslan` (CC BY-NC-SA), `ru_RU-irina`
  (unknown), Piper Japanese (CC BY-NC-SA), Piper `zh_CN-xiao_ya` (non-commercial), edge-tts
  (blocked from datacenter IPs). Indic Parler-TTS (Apache 2.0, Bengali and Urdu) was not needed
  and is heavier than the runner budget.
- Piper itself is GPL-3.0 code; running it to make audio does not place the audio under GPL.
  Kokoro is Apache 2.0. All voices above are verified from each `MODEL_CARD` on
  `rhasspy/piper-voices` and Kokoro's `VOICES.md` (2026-11-13).

Local verification (2026-11-13): Spanish, French, Hindi, Italian, Portuguese and English via
Kokoro, Russian, Urdu and Bengali via Piper all synthesized correctly on CPU (Piper under two
seconds per sentence). Kokoro's non-English pipelines return no word timestamps, so native
segments get one caption for the whole segment (romanisation), while the English narrator keeps
word-by-word captions.

### Visual design
- `pipeline/cards.py` draws cards with Pillow + raqm (libfribidi/harfbuzz shaping for Nastaliq,
  Devanagari, Bengali). Per card: coloured language bar, kicker ("3 / 10 · Spanish · WATER"),
  the word in its native script very large, romanisation in the language colour, IPA, then an
  example sentence or the memory hook and cultural note. Each language has its own colour
  (`languages[].colour`); the channel accent is violet (167,139,250) on a dark aubergine
  background, distinct from the other three channels.
- Cards become 30 fps clips with a slow zoom (`card_clip`) so QA's freeze detector sees motion.
- Captions: the narrator's English is burned in word by word; native-language segments burn the
  romanisation. The native script lives on the card, so both scripts are visible at once.
- Thumbnail: a 1280x720 card with the word, "in 10 languages" and five native spellings.
- Fonts: Noto per script (`fonts-noto-core`, `fonts-noto-cjk`, `fonts-noto-extra` on the runner);
  missing fonts fall back to DejaVu with a warning.

### Persona and voice
- Narrator: Kokoro `af_bella` (grade A-, US female), slowed 4 percent. Distinct from
  `am_michael`, `bm_george` and `af_heart`. Persona in `channels/tentongues/beliefs.md` and
  `style.md`: patient polyglot teacher, honest that the audio is synthetic, no accent claims.
- Name "Ten Tongues", handle `@tentongues`, tagline "One everyday English word a day, taught in
  ten languages." Owner must confirm the handle is free when creating the channel.

### Schedule and word choice
- Workflow `words.yml` runs daily at 03:30 UTC. The long video is scheduled for 07:00 UTC the same
  day; the ten Shorts go out hourly from 09:00 to 18:00 UTC the same day (`shorts_same_day`,
  `shorts_hour_utc: 9`, `shorts_spacing_hours: 1`, `max_youtube_per_day: 12`). Daily quota use: 11
  uploads plus up to 11 playlist inserts (50 units each) and one thumbnail, well inside both buckets.
- Word inventory: `channels/tentongues/words.json` (292 everyday words in themed order). The next
  unused word is taken in order; used words are recorded in the setting `words_used_tentongues`
  and also inferred from existing long-video `content.topic` rows, so a wiped setting cannot cause
  repeats. `--word <w>` forces a word (owner re-runs). Add words to the file before it runs out.

## 2. What was built

| Path | Purpose |
|---|---|
| `channels/tentongues/{channel.json,beliefs.md,style.md,words.json}` | Config (languages, TTS, playlists, calendar), persona, inventory |
| `pipeline/words.py` | Episode generation, validation, segment plans, card video render, thumbnail, QA, publish; CLI |
| `pipeline/words_tts.py` | Per-segment multilingual TTS (Kokoro language codes, Piper, edge-tts fallback), joined audio, mixed SRT |
| `pipeline/cards.py` | Typographic cards (Pillow + raqm, Noto fonts) and zoom clips |
| `pipeline/publish/__init__.py` | `channel_calendar()`: original three keep their fixed days; new channels read `schedule` from channel.json; same-day hourly Shorts and per-channel daily cap |
| `pipeline/publish/youtube_promotion.py` | Shorts join playlists when `playlists_for_shorts` is true (title keyword overlap, existing lazy private playlist creation) |
| `pipeline/qa.py` | Optional `style_note` so vision QA knows cards are the design |
| `.github/workflows/words.yml` | Daily cron + dispatch (channel, privacy, word, resume_id, artifact_run_id) |
| `scripts/brand.py`, `assets/brand/tentongues/` | Brand kit (avatar, banner, cover, watermark, card) |
| `scripts/youtube_auth.py` | Accepts `tentongues` |
| `dashboard/src/lib/{channels,types,categories,analytics}.ts`, queue page, settings form and API | Channel switcher, per-channel keywords, categories, calendar |
| `data/fixture_words.json` | Dry-run episode for "water" in all ten languages |
| `tests/test_words.py` | Inventory, validation, segment plans, SRT, cards for every script, calendar, playlists |

Workflows `sync`, `engage`, `optimize`, `retry` now pass the `*_TENTONGUES` secrets so draining,
comments, title optimisation and retries cover the new channel (they already loop over
`Channel.keys()`). No database migration: `content.channel` is free text and no table enumerates
channel keys. The hub (`hub/`) is unchanged because this channel writes no articles.

## 3. Run it

```bash
# Dry run: fixture episode, no model calls, renders long + 10 Shorts to out/
DB_BACKEND=sqlite TTS_BACKEND=kokoro .venv/bin/python -m pipeline.words --channel tentongues --dry-run

# Real episode without uploading
.venv/bin/python -m pipeline.words --channel tentongues --no-publish

# Daily production
.venv/bin/python -m pipeline.words --channel tentongues --publish --privacy private

# Re-render a saved episode (out/<id>/episode.json) without a new model call
.venv/bin/python -m pipeline.words --channel tentongues --resume tentongues-2026-11-13-water
```

Local requirements beyond `requirements.txt`: `kokoro soundfile piper-tts "misaki[zh]"` and for
Japanese `fugashi jaconv mojimoji unidic-lite pyopenjtalk-plus` (unidic-lite avoids a 1 GB dictionary download)
(`pyopenjtalk-plus` ships wheels; plain `pyopenjtalk` needs cmake and make). Piper voices download
on first use into `data/piper` (`PIPER_VOICES_DIR` overrides; the workflow caches `.piper`).
`TTS_BACKEND=edge` works locally for every language (edge voices are in `channel.json`).
Gotcha: espeak-ng truncates its data path at about 160 characters and then aborts the process
(`Error processing file '.../lib//phontab'`). Keep the virtualenv at a short path; a symlink does
not help because Python resolves the real prefix.

Cloud: `gh workflow run words.yml -f privacy=private` (add `-f word=bread` to force a word).
Resume after a QA block: `gh workflow run words.yml -f resume_id=<content-id> -f artifact_run_id=<run-id>`.

## 4. Owner setup (one-time)

1. **YouTube channel**: create a brand channel "Ten Tongues", handle `@tentongues` (check it is
   free; update `handle` and `youtube_url` in `channel.json` if not). Upload
   `assets/brand/tentongues/avatar-800.png`, `youtube-banner-2560x1440.png`, `watermark-150.png`.
   Description: the tagline plus "Narration and pronunciation audio are AI-generated." Category
   Education (the uploader uses `category_id` 27). Not made for kids. Upload defaults: private.
2. **OAuth**: `.venv/bin/python scripts/youtube_auth.py steps tentongues`, then `url tentongues`,
   authorise with the new channel selected, then `token "<redirect url>" tentongues`. The token is
   saved to `.env` as `YT_REFRESH_TOKEN_TENTONGUES`, never printed.
3. **Instagram + Facebook**: create an Instagram account and a Facebook Page named Ten Tongues
   (use `facebook-cover-1640x624.png`, `profile-card-1080.png`). Follow
   `docs/setup/channel-setup-brief.md` for the Instagram Login API token and Page token, then
   fill `IG_ACCESS_TOKEN_TENTONGUES`, `META_IG_USER_ID_TENTONGUES`, `META_ACCESS_TOKEN_TENTONGUES`,
   `META_PAGE_ID_TENTONGUES` in `.env`. Put the Instagram handle into `instagram_handle` in
   `channel.json` if cross-mentions are wanted. Reels only publish when `publish_privacy` is public.
4. **GitHub Actions secrets** (names only; values come from `.env`, set by the owner):
   ```bash
   gh secret set YT_REFRESH_TOKEN_TENTONGUES
   gh secret set META_ACCESS_TOKEN_TENTONGUES
   gh secret set META_PAGE_ID_TENTONGUES
   gh secret set META_IG_USER_ID_TENTONGUES
   gh secret set IG_ACCESS_TOKEN_TENTONGUES
   ```
   Existing shared secrets (Supabase, YouTube client, LLM provider) are reused.
5. **Vercel** (dashboard): add the same five variables so the dashboard can read the channel; the
   channel switcher already lists Ten Tongues.
6. **Enable**: set `yt_playlists_enabled` to JSON `true` in settings so the eleven playlists are
   created (private) on first upload; make them public in Studio when ready. Optionally
   `yt_description_links_enabled`. Keep `publish_privacy` private until the API compliance audit
   passes (same rule as the other channels).
7. **First run**: `gh workflow run words.yml -f privacy=private`, then check the three-day artifact
   `words-tentongues-<run id>` and the Content page. Review the Bengali and Urdu pronunciation
   yourself; swap voices in `channel.json` if a different Piper speaker sounds better
   (`ur_PK-aegis_female-medium` is also MIT; Bengali has 16 speakers via `speaker`).

## 5. Known limits and follow-ups
- Pronunciation is synthetic; every description says so and tells viewers to check with a native
  speaker. Kokoro's Hindi, Portuguese and Italian voices are grade C; Mandarin voices are grade D.
- No articles or hub pages for this channel. If wanted later, `pipeline/article.py` would need a
  words-aware template.
- Arabic and Indonesian wait on licence confirmation (see section 1). Adding a language means one
  `languages[]` entry, one `topic_playlists[]` entry and a fixture entry; the schema and prompt
  adapt automatically because they are built from the configured list.
- The model call is validated locally (all ten codes, Latin romanisation, policy titles); a bad
  response is saved as `out/<id>/episode.json` and in `content.qa_notes.words_episode` so a rerun
  never pays twice. Fix the JSON by hand and `--resume` to continue.
