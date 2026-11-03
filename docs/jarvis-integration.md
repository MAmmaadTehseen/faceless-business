# Jarvis integration plan

Status: planned 2026-11-03. Implementation brief for Codex. Owner wants upload alerts, an hourly update and a daily summary in Jarvis (`/home/ammaad/Documents/jarvis`).

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
