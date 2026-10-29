# Faceless dashboard

Single-user Next.js 15 dashboard over the Supabase tables in `../supabase/schema.sql`.

## Deploy to Vercel
1. Push this repository to GitHub (the `dashboard/` folder lives inside the monorepo).
2. In Vercel, click "Add New Project" and import the repository.
3. Under "Root Directory", click Edit and set it to `dashboard`.
4. Framework preset: Next.js (auto-detected). Leave build/output settings default.
5. Add the environment variables from `.env.example`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DASHBOARD_PASSWORD`, `DASHBOARD_SECRET`.
6. Add the platform credentials: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `META_ACCESS_TOKEN` (needed only for Send / Like in the inbox).
7. Generate `DASHBOARD_SECRET` with `openssl rand -hex 32`; it signs the login cookie.
8. Click Deploy. Open the URL on your phone, log in with `DASHBOARD_PASSWORD`.
9. Local dev: copy `.env.example` to `.env.local`, fill it in, then `npm install && npm run dev`.
10. The service-role key is only ever read in server components and route handlers; never prefix it with `NEXT_PUBLIC_`.

## Custom domain (faceless.ammaad.online)
1. Vercel project -> Settings -> Domains -> Add `faceless.ammaad.online`.
2. At the DNS provider for ammaad.online add a CNAME record: name `faceless`, value `cname.vercel-dns.com`, TTL auto.
3. Wait for Vercel to show "Valid Configuration" (usually under 10 minutes). HTTPS is issued automatically.
4. The session cookie lasts 3 days; after that the dashboard asks for the password again.

## Operations and analytics

Apply `supabase/migrations/005_analytics.sql` before sending owner replies from
the updated inbox. It adds `comments.reply_text`; automatic replies with no saved
text display as “replied automatically”. The dashboard checks the column before
sending to avoid replying when persistence is unavailable.

Optional server-only `GITHUB_TOKEN` enables owner workflow buttons. Give the token
Actions write access to `MAmmaadTehseen/faceless-business`; it is never returned to
the browser. Without it, controls are disabled. Produce and standalone Shorts
request private uploads while the API audit is pending.

Analytics uses the actual `metrics.captured_at` column. Views, likes and comments
are changes between cumulative snapshots, clamped to zero on counter resets.
First observations include activity before the first snapshot, and daily points
show when growth was observed, not necessarily when views occurred. Watch % is
weighted by view growth using each publication's latest averageViewPercentage
(`ctr`); it cannot reconstruct exact period retention. Subscriber gains are
unavailable because the schema does not store them. Dates display in UTC.
