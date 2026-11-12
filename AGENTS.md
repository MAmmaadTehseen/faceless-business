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

Resume a QA-blocked cloud render within its artifact's 3-day retention. QA runs again before
publishing; the channel is inferred from the content id and the long video is not re-rendered:
```bash
RESUME_ID='<content-id>' ARTIFACT_RUN_ID='<original-github-run-id>'
gh workflow run produce.yml -f resume_id="$RESUME_ID" -f artifact_run_id="$ARTIFACT_RUN_ID" -f privacy=private
```
Add `-f rerender=true` to rebuild the long video and Shorts from saved scripts/shot queries (`--resume <id> --rerender` locally); retained narration is reused.

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
  attempts; uploads do not consume general units. Queueing is quota-only: uploads proceed
  immediately when both buckets have room, even with other queued or recent publications;
  the calendar controls publish_at, not when files upload. Uploads queue only when a bucket
  cannot reserve capacity. Sync drains each channel oldest-first every 6h and stops on quota
  exhaustion. Unrestorable media or other raised drain errors increment drain_attempts in
  the publication error JSON; the row stays queued until its third failure, then becomes
  failed. Drain continues past these rows so later uploads are not starved.
  Run `python -m pipeline.sync --drain-only --channel <key>` to drain without other sync work.
  Public Meta Reels still publish immediately.
  Queued files live in private Supabase Storage `youtube-queue`, so fresh runners can drain them.
  Apply migration 004 then `supabase/migrations/010_quota_uploads.sql` before deploying;
  migration 010 is required for existing databases as well.
  The dashboard's `youtube_quota_units_per_day` field stays; `youtube_uploads_per_day` exists
  as a setting. TODO for the next dashboard job: add its dashboard field.
- `python -m pipeline.shorts_daily --channel <key>` produces one standalone Short daily using the
  channel persona/voice, 14-day topic avoidance, and CostGuard estimate $0.30; supports `--dry-run`,
  `--placeholder`, `--no-publish`, `--privacy`. `.github/workflows/shorts.yml` runs all channels at 09:30 UTC.

**Publish schedule.** All slots are UTC and at least one hour after scheduling time.
Long videos take the next available channel cron slot shown in the table above, skipping
occupied long-video days. Four child Shorts run on the four following days, one per day
at `channel.json` key `shorts_hour_utc` (defaults: futurework 13, tradewinds 15,
escapevelocity 18). Standalone Shorts use `daily_short_hour_utc` (default 20 for every
channel). `shorts_per_long` is set to 4 in all three channel configs (Channel fallback: 2). Taken slots are skipped and a maximum of three
YouTube publications per channel per UTC day pushes overflow forward; long videos still
use their next cron day. Live and queued publications occupy slots; failed rows do not.
The cron days/hours are fixed by channel in the scheduler and match `schedule.days` and
`schedule.utc_hour` in channel.json; those schedule fields are not scheduler overrides.

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
- LinkedIn: one automated daily post per channel from its own Company Page, official API only (organization posting needs LinkedIn app approval; owner creates Pages and app first).
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

## Instagram cross-promotion (2026-11-05)
- Caption mentions are opt-in: shared setting `cross_mentions_enabled` must be JSON boolean
  `true` (default false). Owner must verify and fill `instagram_handle` per channel; blank
  handles are skipped and YouTube `handle` is never used as an Instagram identity.
- Config keys `cross_mention_keywords` + `cross_mention_line` select one sister account by
  deterministic title overlap, without Claude calls. Only Instagram captions change.
  Require three successful unmentioned Reels since the last mention (also at startup).
  Normal publishing and manual retries share the helper. Successful Instagram publication
  `error` may contain JSON `cross_mention` audit metadata; retain it on replay/maintenance.
- Collab support for Instagram Login remains unclear in official docs; no collaborators
  parameter, invitation automation or Collab feature is implemented. A stray
  `collab_posts_enabled` setting has no effect. Research, limits, caveats and owner setup:
  `docs/instagram-collab.md`. Serialize publishers per account for the approximate rate cap;
  mentions fail closed at 1,000 Short rows pending paginated history support.

## YouTube cross-promotion (2026-11-05)
- New uploads only, including queue drains. Shared settings `yt_description_links_enabled`
  and `yt_playlists_enabled` require JSON boolean `true`; both default false. No backfill.
- `pipeline/publish/youtube_promotion.py` reuses Instagram's word-boundary overlap scorer.
  Descriptions include an existing published hub article (parent article for child Shorts)
  and at most one overlapping sister's explicit `youtube_url` from channel.json. Missing
  URLs are skipped. Whole links are appended only when they fit the 4,900 UTF-8-byte
  pipeline limit; existing descriptions are not shortened to make room. URL checks
  prevent duplicate links. No model calls.
- After an article is saved, eligible newly uploaded long videos and child Shorts have
  their descriptions refreshed using `videos.list` (1 unit) and, only when changed,
  `videos.update` (50 units). Updates send only writable snippet fields; status is omitted,
  preserving privacy, synthetic-media disclosure and scheduled `publishAt`. Eligibility
  uses settings `yt_links_new_<video-id>` written only on new successful uploads while enabled.
- Each channel config has four `topic_playlists` (key, title, cross_mention_keywords).
  Only long videos with title overlap enter the best match, at most one playlist per
  video. Creation is lazy and PRIVATE (50 units), insertion costs 50 units. IDs live in
  `yt_playlist_<channel>_<key>` settings; `yt_playlist_video_<video-id>` retains insertion
  attempts to avoid duplicates on uncertain failures. Serialize publishers per channel
  to avoid competing first-time playlist creation. Failed/uncertain optional operations
  are skipped, not automatically retried; they never fail publishing or article saving.
- All extra API calls use existing quota reservations and respect the general reserve;
  insufficient quota skips optional work. Initial description links cost no extra units.
- Owner: verify `youtube_url` and playlist keywords in each channel.json; ensure hub
  articles are publicly served at https://hub.ammaad.online/a/<slug>; enable either setting
  independently as a JSON boolean in existing settings storage. Review created private
  playlists in Studio and make them public when ready. No migration or new secrets needed.
  Turning settings on does not modify older uploads. Existing upload compliance rules apply.

## Publication incident recovery (2026-11-09)
- Pipeline publication writes must never send `status_changed_at`; migration 015's database
  trigger owns that field. Alert bookkeeping and webhook failures must not block core writes.
- OAuth refresh failures open a process-local circuit per channel (selecting the channel again
  does not reset it). Affected unstarted uploads queue with `reason: youtube_auth_expired`,
  without `upload_uncertain`. Produce/Shorts runs retain one safe re-authorisation diagnostic.
- Sync reconciles uncertain YouTube publications before draining. It reads the channel's uploads
  playlist using quota reservations, never `search.list`. A unique matching title with an upload
  timestamp compatible with the attempt restores its
  remote ID. An authenticated, complete scan with no matching title permits queueing only after
  24 hours from `attempted_at` (legacy fallback: publication `created_at`). Unknown age, ambiguous
  titles, incomplete scans and unavailable auth retain uncertainty and prohibit re-upload.
- Owner recovery: check Google Auth Platform > Audience publishing status (Testing can cause
  7-day refresh tokens); run `python scripts/youtube_auth.py steps <channel>` for exact commands.
  Explicit `futurework` correctly targets `YT_REFRESH_TOKEN`; other channel keys use uppercase
  suffixes. Tokens are saved locally, never printed. Only the owner updates Actions secrets.
- Owner: after re-authorising, run `python scripts/reconcile_uploads.py --dry-run` and review
  decisions before `--apply`; these commands never upload. Dry-run leaves publications/content
  unchanged but records consumed API read quota. Then sync can drain safely. No database migration
  is needed for these code fixes; apply pending migrations separately and run the RLS check.
- Weekly review keeps a seven-day `persona-review` artifact and pushes persona changes with
  fetch/rebase retries. Commit/push failures are nonfatal after a successful review.

## Lost queue media recovery (2026-11-10)
- Every new YouTube queue transition persists media before writing `queued`; storage
  failure must never produce a new queued row without recoverable media. Production
  upload claims also checkpoint media so uncertain outcomes remain recoverable.
- Artifact-free recovery: `gh workflow run produce.yml -f resume_id=<content-id> -f rebuild=true -f privacy=private`
  (`python -m pipeline.run_all --resume <id> --rebuild --publish --privacy private` locally).
  Rebuild uses DB production metadata, regenerates Kokoro narration and footage, renders
  and reruns QA. It makes no script, topic or article Claude calls. Existing remote IDs
  and uncertain-upload guards remain authoritative. Standalone daily Shorts are supported.
- Full long-video production metadata is retained as `rebuild_script` in `content.qa_notes`;
  daily Shorts retain `daily_script`. Legacy `paid_script` checkpoints are also accepted.
  Legacy narration-only `content.script` cannot recover absent shot queries/Short scripts;
  rebuild fails explicitly rather than inventing them or buying another script.
- `PYTHON_DOTENV_DISABLED=1 python scripts/recover_lost_media.py --dry-run` checks queued
  YouTube files through existing restore locations and prints one rebuild command per
  parent (or standalone Short). Requires explicitly exported Supabase configuration;
  never loads `.env`, never dispatches workflows. `--apply` only resets `drain_attempts`
  for unrestorable queued rows, retaining other error metadata and queue status.
- Shorts workflow artifacts now retain script/narration checkpoints even if validation
  fails before rendering. Run 42688434967 rejected 164/202-word daily scripts against
  the 120–160-word limit; keep validation and saved paid responses for owner correction.

## Model provider switching (2026-11-11)
- `Claude` remains the shared interface. `LLM_PROVIDER` defaults to `anthropic`;
  `lunaroute` requires environment-only `LUNAROUTE_API_KEY` and optional
  `LUNAROUTE_BASE_URL` (default https://gw.lunaroute.com). Never fall back across providers.
- LunaRoute uses Messages image blocks, prompted JSON + local schema validation and
  one repair; it receives no Anthropic beta/fallback/server-tool parameters.
- LunaRoute costs rows use model `lunaroute/<model>` and zero marginal USD, including
  repair and failed HTTP attempts. LunaRoute vision errors fail QA closed. CostGuard uses zero estimates but checks budget; the independent
  `LLM_MAX_CALLS_PER_CLIENT` default 100 counts requests/retries/repairs per instance.
- Research supplies ideation news and bounded HTTP source text. Only supplied sources
  may be cited. Saved scripts retain `supplied_sources`; article evidence URLs must
  belong to that list. Legacy scripts require verified source metadata first.
- Owner configures Actions variable `LLM_PROVIDER`, secret `LUNAROUTE_API_KEY`, optional
  variable `LUNAROUTE_BASE_URL`. Per-step overrides and public API sources/limits:
  `docs/llm-providers.md`. Owner-only comparison: `scripts/llm_compare.py`; do not run
  automatically or in tests. Tests mock model and source HTTP, never read `.env`.

## LunaRoute streaming (2026-11-12)
- Messages requests use SSE (`stream: true`) at the same `/v1/messages` endpoint.
  Text deltas only become output; thinking/pings count as activity. Require message_stop;
  merge usage/stop reason from message events. Keep fenced JSON, refusal/max_tokens
  handling and one schema repair. Non-SSE success retries with stream=false only.
- Connect timeout 10s, idle read timeout 120s, overall deadline 40 minutes across
  retries/repairs. Connection/stream failures retry once before completion, with
  attempt logging/cost rows; no provider fallback. Tests use mocked SSE only.

## Evergreen stockpile (2026-11-12)
- Owner-run `scripts/generate_evergreen.py --channel <key>` (LunaRoute only) creates
  60–80 deduplicated topics in `channels/<key>/evergreen.json` and durable
  `evergreen_topics_<key>` settings. Durable per-topic used markers avoid runner repeats.
  Generation was not run by the coding agent; owner must populate inventories first.
- `pipeline.run_all --bank --channel <key>` requires real footage, passed long QA and
  every child Short that passed QA (failed children remain qa_failed with findings); `pipeline.shorts_daily --bank` banks a standalone Short.
  No publications or published hub article are created. Prepared article + release
  manifest/media go to app-created private Google Drive folders; complete bundles become
  `banked` atomically. IDs/checksums/checkpoints live in `qa_notes.stockpile`. No migration.
- Drive uses only drive.file, `GDRIVE_REFRESH_TOKEN` + existing YT client credentials.
  Owner: `scripts/youtube_auth.py url drive`, then `token "<redirect>" drive`; token saved
  locally, never printed. Owner alone sets the Actions secret. Keep 5 GiB free; preflight
  adds a conservative 2 GiB production allowance. Verified local media is retained.
- `pipeline.release_banked --channel <key> --max N` reuses normal YouTube publisher without
  model calls; downloads verify SHA-256. Long ID precedes children. Save prepared article
  after all YouTube IDs, then move folder to `Faceless Stockpile/released/`, never delete.
  Partial releases remain discoverable; existing uncertainty guards prohibit duplicates.
- `bank.yml`: hourly cron gated by JSON boolean `bank_mode_enabled` (default false) and
  inclusive ISO `bank_until`; manual dispatch intentionally bypasses those two gates.
  Global workflow concurrency + matrix max-parallel 2 caps bank jobs at two overall.
  Sync releases after normal sync only when `banked_release_per_day` > 0 (default 0),
  counting bundles per channel per UTC day, with existing quota reserves/calendar.
- Cross-runner settings locks fail closed after crashes. Owner may remove only
  `stockpile_lock_drive_upload` / `stockpile_lock_release_<key>` after verifying no live
  operation owns them. Setup, recovery, settings and exact commands: `docs/stockpile.md`.
  Dashboard Stockpile card is read-only and uses cached Drive quota; no Vercel Drive secret.

## Caption-aware QA (2026-11-12)
- All video QA callers supply narration as caption_text. Matching burned-in words are
  expected captions; only physically frame-cropped letters should be flagged as captions.
- Blocking caption/overlay findings downgrade to logged minor notes when narration is
  supplied, except cropping/cut-off, illegible/unreadable text, third-party watermarks/logos,
  nudity, gore, black frames and misleading claims. Strict QA still rejects minor findings.
