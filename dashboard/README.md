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
