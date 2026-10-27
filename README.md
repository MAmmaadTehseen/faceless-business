# Faceless content business

Fully automated faceless channel: Claude writes, free tools render, GitHub Actions publishes to YouTube (long + Shorts) and
Instagram/Facebook Reels, and a dashboard shows every piece of content across platforms with comments you can answer by hand or on autopilot.

Monthly cost: Claude API only (budget guard defaults to $95). Everything else is free tier.

```
persona/     the clone: beliefs.md (fill this in), style.md, formulas.md, examples/
pipeline/    ideate -> script -> tts -> footage -> render -> thumbnail -> qa -> shorts -> publish ; sync, engage, optimize, review
dashboard/   Next.js app (Vercel free tier) over the Supabase database
supabase/    schema.sql
.github/     produce (2x daily), sync (6h), engage (6h), optimize (daily), weekly-review
scripts/     youtube_auth.py, meta_token.py
niche_research.py   one-off niche scoring report
```

## Local run (no accounts needed)

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python -m pipeline.run_all --dry-run
```
Produces `out/<id>/` with the long mp4, two vertical Shorts, a thumbnail and `script.json`, using a fixture script and
placeholder footage. Needs ffmpeg installed.

## Setup (one time, about 2 hours)

1. **Claude**: put `ANTHROPIC_API_KEY` in `.env` (copy `.env.example`).
2. **Persona**: fill in `persona/beliefs.md`. This is the single biggest quality lever.
3. **Niche**: `python niche_research.py` writes `data/niche_report.md`. Pick one, set `niche_keywords` in the dashboard (or the settings table).
4. **Pexels**: free key at pexels.com/api -> `PEXELS_API_KEY`.
5. **Supabase**: new project (free) -> SQL editor -> paste `supabase/schema.sql` -> run. Copy Project URL and service_role key.
   Storage: a public bucket named `media` is created automatically for Reels hosting.
6. **YouTube**: follow the docstring in `scripts/youtube_auth.py`. Then in Google Cloud submit the *YouTube API Services compliance audit*
   (required before API uploads can be public) and the quota extension form. Until the audit passes, uploads are private + scheduled.
   In YouTube Studio: verify the channel phone number (needed for custom thumbnails) and set upload defaults.
7. **Meta**: follow the docstring in `scripts/meta_token.py`. Optional; skip to publish only on YouTube.
8. **GitHub**: push this repo (public = unlimited Actions minutes). Add every value from `.env.example` as a repository secret.
   Run the `produce` workflow once by hand with privacy `private`, check the result in YouTube Studio, then let the crons run.
9. **Dashboard**: see `dashboard/README.md` (Vercel, root directory `dashboard`, same env vars plus `DASHBOARD_PASSWORD` and `DASHBOARD_SECRET`).

## Real local run

```bash
.venv/bin/python -m pipeline.run_all --no-publish        # Claude + Pexels, renders only
.venv/bin/python -m pipeline.run_all --publish            # uploads with the privacy from settings
.venv/bin/python -m pipeline.sync && .venv/bin/python -m pipeline.engage
```

## How the money side works

Only YouTube pays creators in Pakistan directly; RPM follows the viewer's country, so the channel targets US/UK/CA/AU English viewers.
Instagram and Facebook are traffic funnels. Expect no revenue for roughly six months; the Partner Program needs 1,000 subscribers and
4,000 public watch hours (or 10M Shorts views in 90 days). At the threshold: apply in Studio, add your bank in AdSense, fill the W-8BEN.

## Policy guardrails built in

Title filter blocks income promises and medical claims. Persona red lines forbid advice framing. QA rejects black frames, missing
captions, watermarks. Uploads set `containsSyntheticMedia` so the AI disclosure is honest. Only each platform's own API is used, never
third-party schedulers.
