# AGENTS.md — handoff for any coding agent (Codex, Claude, human)

Read this first. It is the single source of truth for state that is not obvious from the code.
Owner: Ammaad (Pakistan). Budget: ~$100/month Claude API credits, nothing else paid.

## What this is
A fully automated faceless content business: three YouTube channels, each with its own
Instagram account and Facebook Page, plus (planned) one hub Facebook Page and one blog site.
Python pipeline runs on GitHub Actions; Next.js dashboard on Vercel at https://faceless.ammaad.online.

| key | channel | niche | voice (Kokoro) | accent RGB | schedule (UTC) |
|---|---|---|---|---|---|
| futurework | Future Work Explained | AI and the future of work | am_michael | 251,191,36 | Mon/Wed/Fri 06:00 |
| tradewinds | Trade Winds Report | global power and economics | bm_george (lang b) | 231,196,122 | Tue/Thu/Sat 11:00 |
| escapevelocity | Escape Velocity | space and frontier science | af_heart | 34,211,238 | Mon/Thu/Sun 16:00 |

Per-channel config lives in `channels/<key>/channel.json`, persona in `beliefs.md` + `style.md`,
shared formulas in `persona/formulas.md`. Brand assets in `assets/brand/<key>/` (regenerate: `python scripts/brand.py all`).

## Run it
```
uv venv .venv --python 3.12 && .venv/bin/pip install -r requirements.txt   # system python has no pip
cp .env.example .env                                                      # fill keys; never commit .env
DB_BACKEND=sqlite TTS_BACKEND=edge .venv/bin/python -m pipeline.run_all --dry-run --channel tradewinds
.venv/bin/python -m pipeline.run_all --publish --privacy private --channel futurework
```
Flags: `--dry-run --placeholder --publish --no-publish --privacy X --count N --resume <id> --channel <key>`.
Publishing refuses placeholder footage. Content ids are `<channel>-<date>-<slug>`.

Cloud: `gh workflow run produce.yml -f channel=<key> -f privacy=private`. Workflows: produce (3 crons,
one per channel), sync (6h), engage (6h), optimize (daily), review (weekly).

## Hard rules (do not break)
- Secrets only in local `.env`, GitHub Actions secrets, Vercel env. Never print them, never commit them.
- TTS on GitHub runners must be Kokoro (`TTS_BACKEND=kokoro`); edge-tts is blocked from datacenter IPs.
  Install CPU torch from the PyTorch CPU index before `kokoro`, or uv pulls CUDA wheels and times out.
- Claude structured-output schemas: no `minItems` > 1, no `maxItems`; put limits in the prompt.
- YouTube Analytics API has no impressions/CTR; the `ctr` column holds averageViewPercentage and the
  optimizer compares views/day to the channel median.
- Uploads set `containsSyntheticMedia: true` and stay private + scheduled until Google's API compliance audit passes.
- Titles: `BANNED_TITLE` regex in `pipeline/script.py` blocks income/medical/"while you sleep" claims. Keep it.
- Two placeholder Shorts already on YouTube are intentionally kept (status `killed` in DB). Do not delete.
- Budget guard stops at $95 month-to-date (`CostGuard` in `pipeline/common.py`). Every Claude call logs to `costs`.
- Each Instagram account needs its own Facebook Page; Meta env is `META_<NAME>_<CHANNELKEY>`.
- YouTube's 2026 inauthentic-content rule: channels must stay distinct (voice, style, persona, schedule).

## Current state (2026-10-29)
Done: pipeline end to end (one private long video + 2 Shorts on Future Work), Supabase schema + channel
migration applied, dashboard live with owner/reviewer roles and channel switcher, three YouTube channels
created and branded, `YT_REFRESH_TOKEN`, `_TRADEWINDS`, `_ESCAPEVELOCITY` in `.env`, Facebook Pages for
all three, Instagram profiles branded, Meta app has all needed permissions.

Open, in order:
1. GitHub secrets still lack `YT_REFRESH_TOKEN_TRADEWINDS` and `YT_REFRESH_TOKEN_ESCAPEVELOCITY`
   (owner must run `gh secret set` from `.env`; agents are not allowed to). Until then only futurework can publish from the cloud.
2. Meta: link each Instagram account to its Page (blocked by a temporary Facebook restriction on 2026-10-29),
   then Graph API Explorer user token -> `python scripts/meta_token.py APP_ID APP_SECRET TOKEN` -> nine
   `META_*_<KEY>` values into `.env` -> GitHub secrets -> Vercel env. The old un-suffixed META values are invalid.
3. YouTube API compliance audit + quota form SUBMITTED 2026-10-29 (project 6170817069, 10k general + 16k videos.insert/day;
   reviewer login `reviewer` / `DASHBOARD_REVIEWER_PASSWORD`). Awaiting Google's email reply. Evidence in `docs/evidence/`.
4. Hub: Plainsight Media implemented in `hub/` (Next.js 15, ISR, server-only Supabase reads),
   with channel pages, Markdown articles, YouTube embeds, about/privacy pages. `pipeline/article.py`
   converts long scripts via Claude after successful YouTube upload; dry runs create fixture articles without API calls.
   Owner: run `supabase/migrations/003_articles.sql`, create a Vercel project with root `hub`,
   add SUPABASE_URL + SUPABASE_SERVICE_KEY, and CNAME hub.ammaad.online to Vercel's supplied target.
   Optional Facebook URL overrides are documented in `hub/README.md`; hub Facebook Page still needs creation.
5. Phase 2: TikTok (funnel only, no payout in Pakistan). X skipped.

## Where things are
`pipeline/` (common, db, ideate, script, tts, footage, render, thumbnail, shorts, qa, publish/{youtube,meta},
run_all, sync, engage, optimize, review) · `dashboard/` (Next.js 15, root dir on Vercel = `dashboard`) ·
`supabase/schema.sql` + `migrations/` · `scripts/` (youtube_auth, meta_token, brand) · `docs/setup/channel-setup-brief.md`
(full manual account-setup procedure) · `docs/privacy.html` (GitHub Pages privacy policy) · `.env.example` (every variable).
