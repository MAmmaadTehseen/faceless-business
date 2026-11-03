# Jarvis integration plan

Status: implemented locally 2026-11-03; owner setup pending. Implementation brief for Codex. Owner wants upload alerts, an hourly update and a daily summary in Jarvis (`/home/ammaad/Documents/jarvis`).

## Decision: direct connector, not MCP
Jarvis integrations are `Connector`s (`apps/api/src/connectors/`), running on Lambda with Web Push via `pushToAll`, and jobs via EventBridge. A native connector fits that design and adds no always-on server. An MCP server needs hosting, adds latency to a cold Lambda, and offers nothing until a second client needs it. Keep the summary function reusable so an MCP wrapper can be added later.

## Flow
1. Faceless dashboard (Vercel): new read-only `GET /api/jarvis/summary?window=1h|24h`, bearer token `JARVIS_READ_TOKEN`, constant-time compare, separate from owner login. Returns counts only: uploads by channel/platform, failures, queued, views/likes/comments delta, spend vs budget, pending comments, running jobs, last-event id. No secrets. Do not give Jarvis the Supabase service key.
2. Pipeline to Jarvis: after a publication goes live or fails (one helper in `pipeline/publish`), POST to Jarvis `POST /hooks/faceless`, HMAC-SHA256 signed with `JARVIS_WEBHOOK_SECRET` and timestamp (reject older than 5 minutes). Fire and forget with a short timeout: Jarvis failure must never fail an upload. Dedupe by publication id + status. Skip when env is unset.
3. Jarvis: `connectors/faceless.ts` with read tools `faceless_summary` and `faceless_recent_uploads`, so the owner can ask by voice. No write actions in this phase, so the gate is not involved. Webhook text is untrusted data, stored as an `InboxEvent` with connector "faceless", and pushed.
4. Jobs in `jobs.ts` + `infra/main.tf` schedules:
   - `faceless_hourly`: `rate(1 hour)`. Pushes only if something changed since last hour and only outside quiet hours (default 23:00-08:00 local); failures always push.
   - `faceless_daily`: `cron(0 22 * * ? *)` in the schedule timezone: uploads, views, top video, failures, spend, tomorrow's schedule.
   Summaries are templated, with no Claude call, so they stay free. Also add a one-line Faceless summary to the morning briefing.
5. Upload alerts: one push per upload would be noisy at ~6 uploads a day; collapse with the same push tag per channel, and batch uploads within 5 minutes. Link to `https://faceless.ammaad.online/content/<id>`.

## Settings
Jarvis env: `FACELESS_URL`, `FACELESS_READ_TOKEN`, `FACELESS_WEBHOOK_SECRET` through its existing secrets path. Faceless: `JARVIS_READ_TOKEN` in Vercel, `JARVIS_WEBHOOK_URL` + `JARVIS_WEBHOOK_SECRET` in GitHub secrets and all workflow env blocks. Owner sets the secrets; agents never print or commit them.

## Done means
Tests in both repos (signature, stale timestamp, token, dedupe, quiet hours, unchanged-hour silence, webhook failure not failing an upload, Jarvis tests per its CLAUDE.md), typechecks and builds pass, Terraform validates. Docs list the owner's secret and deploy steps. No commits or deploys by the agent.

## Implementation and semantics (2026-11-03)

Implemented locally in both repos; no deployment or migration has been performed.
The summary is read-only, `private, no-store`, and uses a dedicated bearer token.
It returns identifiers and aggregates only, including at most 20 recent uploads.
A publication marked `live` means uploaded successfully; a private scheduled YouTube
upload is not a claim that the video is already publicly visible.

Migration 015 adds `publications.status_changed_at` and a status-transition trigger.
Historical failures have unknown timestamps and are excluded from windowed failures;
live rows retain their original upload timestamp. Current queue, pending comments and
running jobs are snapshots. Spend covers the UTC calendar month; tomorrow's stored
publication slots are listed in UTC. Top video uses lifetime views across its platforms.
Audience growth uses the latest counter minus the last counter before the window;
old publications without a baseline contribute no delta until one is available.
There is no claimed growth between sync samples. Pagination avoids Supabase's default
1,000-row truncation. The idle fingerprint uses latest counter values, not sample times.

The Python helper signs `<unix seconds>.<exact JSON bytes>` with HMAC-SHA256;
headers are `X-Faceless-Timestamp` and `X-Faceless-Signature` (hex). Network timeout
is 1 second connect / 2 seconds read, with no retries and no response/error logging.
Missing configuration skips delivery. Delivery failure never fails an upload.
Terminal YouTube/Meta writes, owner-requested Meta retries, and the third queue-drain
failure invoke this helper.

Jarvis saves webhook events directly as rule-triaged untrusted InboxEvents without AI.
A conditional DynamoDB queue insert dedupes publication id + status for 30 days;
retries reuse the original event timestamp. Uploads flush every five minutes, grouped
by channel, with a stable `faceless-<channel>` push tag. Failures flush immediately.
Quiet hours use the existing Inbox settings (default 23:00–08:00 local); uploads wait,
failures bypass them. Conditional two-minute leases prevent concurrent flushes from
sending the same pending items. Failed push delivery leaves events pending for retry.
A crash after push acceptance but before the delivery marker can repeat a notification;
the stable tag collapses it. There is no durable sender outbox: missed webhooks still
appear in hourly/daily aggregate summaries. No write tools or gate exceptions were added.

## Exact owner steps (agents must not perform these)

1. In Supabase SQL Editor, apply `supabase/migrations/015_jarvis_publications.sql`
   as postgres after existing migrations through 014. Do this before new pipeline code
   runs. It adds no tables, policies or grants. Immediately run the required RLS check
   yourself from this repo, with owner-supplied URL and anon key already exported:
   ```bash
   python3 scripts/check_rls.py
   ```
   Require exit 0; supply `RLS_MEDIA_OBJECT` if requested by the checker. These are
   owner/live checks and were deliberately not run by the agent.
2. Generate two independent random values with your password manager: a read token
   and a webhook signing secret. Do not put either in a command argument, commit,
   chat message, or Terraform variable/state.
3. In Vercel → Faceless dashboard project → Settings → Environment Variables,
   add `JARVIS_READ_TOKEN` for Production, using the read token. Deploy the changed
   dashboard from root `dashboard` through your normal Vercel flow.
4. In AWS Systems Manager → Parameter Store (Jarvis's region), create/update these
   SecureString parameters using the console, outside Terraform:
   - `/jarvis/faceless/personal/url` = `https://faceless.ammaad.online`
   - `/jarvis/faceless/personal/read-token` = the same Vercel read token
   - `/jarvis/faceless/personal/webhook-secret` = the signing secret
   If your Terraform project name/SSM prefix differs from `jarvis`, use that existing
   prefix. The Lambda role already reads only its own prefix. No Supabase key is needed.
5. Review and commit the Jarvis changes yourself, then push to its normal branch/main
   deployment flow so CI publishes both Lambda bundles and the web app/service worker.
   For Terraform's archive inputs, build the bundles locally (this spends no Claude credits):
   ```bash
   cd /home/ammaad/Documents/jarvis
   JARVIS_SKIP_DOTENV=1 npm run build:lambda
   terraform -chdir=infra plan
   terraform -chdir=infra apply
   ```
   Review that the plan adds the three Faceless schedules and preserves the existing
   Lambda `ignore_changes` rules. Schedules are hourly, five-minute alert batching, and
   22:00 daily in the existing `tz_name`. No new IAM actions are required.
6. In Faceless GitHub → Settings → Secrets and variables → Actions, add:
   - `JARVIS_WEBHOOK_URL` = your existing **API Lambda function URL** plus
     `hooks/faceless` (exact resulting path `/hooks/faceless`; do not use the web origin)
   - `JARVIS_WEBHOOK_SECRET` = the same signing secret from step 4
   Review and commit/push the Faceless code yourself. The modified workflow env blocks
   pass both values to pipeline jobs. Local runs may use these names in the owner's
   local environment; agents must not read local secret files.
7. Open/reload the Jarvis PWA to activate its updated service worker. Existing push
   subscriptions work unchanged; enable push if not subscribed. No Inbox account setup
   is needed for Faceless. Ask “Faceless summary” or “recent Faceless uploads” after
   deployment; those voice turns use Jarvis's normal model budget. Verify a normal
   upload produces one batched channel notification within five minutes outside quiet
   hours; verify a real failure is immediate. Check hourly silence when unchanged and
   the daily summary at 22:00 local. Do not trigger a paid render just to test alerts.

## Local verification

No commits/deploys, secrets, live APIs, or Claude calls are needed for checks.
Python tests disable dotenv and external HTTP through `tests/conftest.py`:
```bash
PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests/test_jarvis.py tests/test_drain.py tests/test_schedule.py tests/test_upload_idempotency.py tests/test_youtube_quota.py tests/test_retry.py -q
cd dashboard && node --test test/jarvis-summary.test.cjs
```
Jarvis: use `JARVIS_SKIP_DOTENV=1`, fake AWS credentials or a local endpoint, and a
network-denying Node preload when running `npm test` / `npm run typecheck`. The two
existing DynamoDB Local suites skip if the local service is unavailable. Production
builds should run from a temporary copy excluding all `.env*` files, since Next/Vite
otherwise load dotenv independently of the application flag. Terraform `validate`
is local only; no plan/apply is part of the agent's verification.
