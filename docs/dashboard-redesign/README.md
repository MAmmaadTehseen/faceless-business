# Dashboard redesign and speed (2026-11-23)

Approved prototype: https://claude.ai/artifact/LMmmgReMhL3hV39VFJuszJ

## What changed
- Control-room theme (Big Shoulders / Schibsted Grotesk / JetBrains Mono, one red accent), light and dark
  (follows the phone; the half-moon button pins a choice in localStorage).
- Header: date range (6 h, 24 h, 7/28/90 days, all time, custom from/to) shared by every page through the
  `days` or `from`/`to` URL params (`dashboard/src/lib/range.ts`); sync pill; channel row and platform row.
  Filter changes show a top load bar and dim the page until the server answers.
- Today page lists what needs the owner (failed uploads, failed QA, paused pipeline, waiting comments,
  budget over 80%). Donut charts replace line charts on Today, Analytics, video detail and Automation quota.
- Content list is paginated on the server (30 per page).

## Refresh = sync
`POST /api/sync` dispatches `.github/workflows/sync.yml` on `main`: owner only, refused while a sync runs and
within 10 minutes of the last one. `GET /api/sync` reports the latest run; the first poll after a run finishes
clears the data cache (`revalidateTag("data")`). Pull down at the top of any page on the phone, or tap the pill.
Uses the existing Vercel `GITHUB_TOKEN` (needs Actions read and write on the repo, as the action buttons already do).

## Caching and egress
Server reads are cached with `unstable_cache` for 6 h under tag `data` (`dashboard/src/lib/cache.ts`), and cleared
by dashboard writes and by finished syncs. Pages select only the columns they show; `content.qa_notes`
(~16 KB per row) and `runs.log` are never fetched for lists. Metrics are read only for the compared period.

Measured on local production builds against the live Supabase project (seconds per page load):

| Page | Before | After, cold cache | After, warm cache |
|---|---|---|---|
| Home | 46 (290 first load) | 18 | 0.26 |
| Content | 54-60, 27 MB HTML | 0.3 (7 days) | 0.22, 160 KB HTML |
| Analytics 7 d / 90 d | 37-41 | 12 (90 d) | 0.3 |
| Queue | 39 | 0.5 | 0.5 |

One uncached home load used to download about 70 MB from Supabase (content `select *` three times plus
all 40,000 metric snapshots twice). Now a cold load is a few MB and warm loads read nothing.

Screenshots: `before-home-phone.jpg` (old site after 5 s, still loading), `after-*.jpg`.

## Follow-ups
- Frame and Argument and Ten Tongues have similar violet brand colours; the donuts would read better if one changed.
- A cold home load after each sync still takes ~18 s; a SQL view aggregating daily metrics would cut it further.
