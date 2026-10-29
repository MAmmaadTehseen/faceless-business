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
one per channel), shorts (daily 09:30 UTC, all three channels), sync (6h), engage (6h), optimize (daily), review (weekly).

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
- Budget guard stops at the `monthly_budget_usd` setting (default $100, set on the Automation page) (`CostGuard` in `pipeline/common.py`). Every Claude call logs to `costs`.
- Instagram uses the "Instagram API with Instagram Login" (graph.instagram.com, `IG_ACCESS_TOKEN_<KEY>` 60-day user token,
  refreshed by sync into the settings table as `ig_token_<key>`); Facebook Pages use graph.facebook.com with `META_ACCESS_TOKEN_<KEY>`.
  No Page-to-Instagram link is required. Reels publish only when publish_privacy is public.
- YouTube's 2026 inauthentic-content rule: channels must stay distinct (voice, style, persona, schedule).

- Each long video requests four distinct-angle Shorts (channel `shorts_per_long: 4`); each Short gets its own QA including vision on real footage.
- YouTube quotas are shared across channels in two independent UTC-day buckets:
  `youtube_uploads_per_day=100` (one per videos.insert attempt, with 2 reserved for retries),
  and `youtube_quota_units_per_day=10000` (50 per thumbnail/update/reply, with 1000 reserved
  for sync/engage reads). Atomic reservations check both buckets and retain failed/uncertain
  attempts; uploads do not consume general units. Uploads queue if either bucket is full.
  Sync drains each channel's queue oldest-first every 6h. Public Meta Reels still publish immediately.
  Queued files live in private Supabase Storage `youtube-queue`, so fresh runners can drain them.
  Apply migration 004 then `supabase/migrations/010_quota_uploads.sql` before deploying;
  migration 010 is required for existing databases as well.
  The dashboard's `youtube_quota_units_per_day` field stays; `youtube_uploads_per_day` exists
  as a setting. TODO for the next dashboard job: add its dashboard field.
- `python -m pipeline.shorts_daily --channel <key>` produces one standalone Short daily using the
  channel persona/voice, 14-day topic avoidance, and CostGuard estimate $0.30; supports `--dry-run`,
  `--placeholder`, `--no-publish`, `--privacy`. `.github/workflows/shorts.yml` runs all channels at 09:30 UTC.

## Current state (2026-10-29)
Done: pipeline end to end (one private long video + 2 Shorts on Future Work), Supabase schema + channel
migration applied, dashboard live with owner/reviewer roles and channel switcher, three YouTube channels
created and branded, `YT_REFRESH_TOKEN`, `_TRADEWINDS`, `_ESCAPEVELOCITY` in `.env`, Facebook Pages for
all three, Instagram profiles branded, Meta app has all needed permissions.

Open, in order:
1. GitHub secrets still lack `YT_REFRESH_TOKEN_TRADEWINDS` and `YT_REFRESH_TOKEN_ESCAPEVELOCITY`
   (owner must run `gh secret set` from `.env`; agents are not allowed to). Until then only futurework can publish from the cloud.
2. Meta: DONE 2026-10-29 via Instagram Login API. Owner must sync IG_ACCESS_TOKEN_<KEY> + META_IG_USER_ID_<KEY> + IG_APP_ID to GitHub secrets.
3. YouTube API compliance audit + quota form SUBMITTED 2026-10-29 (project 6170817069, 10k general + 16k videos.insert/day;
   reviewer login `reviewer` / `DASHBOARD_REVIEWER_PASSWORD`). Awaiting Google's email reply. Evidence in `docs/evidence/`.
4. Hub: Plainsight Media implemented in `hub/` (Next.js 15, ISR, server-only Supabase reads),
   with channel pages, Markdown articles, YouTube embeds, about/privacy pages. `pipeline/article.py`
   converts long scripts via Claude after successful YouTube upload; dry runs create fixture articles without API calls.
   Owner: run `supabase/migrations/003_articles.sql`, create a Vercel project with root `hub`,
   add SUPABASE_URL + SUPABASE_SERVICE_KEY, and CNAME hub.ammaad.online to Vercel's supplied target.
   Optional Facebook URL overrides are documented in `hub/README.md`; hub Facebook Page still needs creation.
5. Phase 2: TikTok (funnel only, no payout in Pakistan). X skipped.

## TODO (owner-approved, not started; give to Codex)
- Dashboard: live progress for runs in flight. Show each running produce/shorts job as a card with stage (ideate, script, voice, footage, render, QA, upload, article), percent done and an estimated time left based on median durations of past runs; progress bar on Content and home. Source: `runs` table rows (pipeline writes stage + timestamp per step) and/or GitHub Actions run status via /api/actions.
- Comments: fetch reply threads (YouTube `commentThreads.list` part=snippet,replies; IG/FB replies) so viewer replies to our
  replies are seen; continue a thread for at most 3 turns.
- Replies: when a comment suggests a topic, add it to that channel's `topic_queue` (added_by "comment", priority +5)
  and acknowledge it in the reply. Add `suggested_topic` (nullable) to REPLY_SCHEMA in pipeline/engage.py.
- Reply quality: at least two sentences with one concrete useful thought; personal hardship (layoff, illness, money
  trouble) is held for owner review instead of auto-sent.
- Retry: failed YouTube uploads and failed replies get re-queued with an attempt counter, max 3 tries across syncs.
- Hub: create the second Vercel project for hub.ammaad.online (root `hub`, include files outside root,
  SUPABASE_URL + SUPABASE_SERVICE_KEY) and the `hub` CNAME. Hub Facebook Page "Plainsight Media".
- Hub SEO owner setup: apply migration 009, configure Search Console verification and submit /sitemap.xml
  (see hub/README.md). Expect little organic traffic for 3-6 months on a new domain.
- Instagram token refresh warned "grant type not supported" on day 1; re-check after 2026-11-05 (tokens expire 2026-12-28).

## Where things are
App icons generated by `scripts/icons.py` into `hub/public/` and `dashboard/public/`.
Hub first-party analytics: `hub_events` (migration 008); dashboard `/analytics` Hub tab.
`pipeline/` (common, db, ideate, script, tts, footage, render, thumbnail, shorts, qa, publish/{youtube,meta},
run_all, sync, engage, optimize, review) · `dashboard/` (Next.js 15, root dir on Vercel = `dashboard`) ·
`supabase/schema.sql` + `migrations/` · `scripts/` (youtube_auth, meta_token, brand) · `docs/setup/channel-setup-brief.md`
(full manual account-setup procedure) · `docs/privacy.html` (GitHub Pages privacy policy) · `.env.example` (every variable).

Blog writing rules live in `persona/blog-rules.md`; transferable video script writing rules live in `persona/formulas.md`.

## Hub SEO
Hub includes sitemap/robots, canonical and English alternate URLs, page metadata and Twitter cards, static shared OG artwork and dynamic article OG PNGs, Article/FAQ/Breadcrumb/Video JSON-LD, RSS (global and per channel), related and previous/next stories, next/image thumbnails and a tracked lite YouTube facade. URLs omit trailing slashes; `NEXT_PUBLIC_SITE_URL` defaults to https://hub.ammaad.online. Optional `GOOGLE_SITE_VERIFICATION` supports Search Console. Apply `supabase/migrations/009_hub_seo.sql` for sharing summaries and modification dates. New article slugs are at most 60 characters; existing URLs are preserved. Setup and verification instructions: `hub/README.md`.


## RLS regression check
Apply `supabase/migrations/011_rls_hardening.sql` as postgres after migrations 002–010.
Hosted postgres may lack ownership of managed Storage tables; migration 011 skips denied Storage changes with NOTICEs containing exact SQL to apply through Storage > Policies (storage policy UI), and the youtube-queue bucket must be set private in the dashboard when its update is denied.
Run `python3 scripts/check_rls.py` after **every migration**, with `SUPABASE_URL` and
owner-supplied `SUPABASE_ANON_KEY` exported in your shell. The script never reads `.env`
or uses a service key. Missing configuration exits 2; failed or unverified checks exit 1.
Set `RLS_MEDIA_OBJECT` to an existing bucket-relative media path (e.g. `channel/video.mp4`)
if automatic root listing cannot find a file, so the credential-free public GET is tested.
Only unique probe rows/objects are mutated; if access is unexpectedly allowed, check for
leftover `rls-probe-` data. Empty Storage lists/deletes can be successful HTTP responses
under RLS and are accepted only when they return no objects; this does not prove grants
are absent. Review database ACLs/policies as well. The anon check does not test the
`authenticated` role or discover live-only tables; the migration handles all public objects.
