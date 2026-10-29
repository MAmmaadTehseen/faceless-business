# Plainsight Media

Next.js 15 App Router, TypeScript and Tailwind v4. Articles and channel pages revalidate every 600 seconds. Supabase reads use a server-only service client. No public database environment variables or client-side database code.

## Local checks

Run `npm install` and `npm run build` from `hub/`, then `npm start`. Without Supabase credentials the site shows empty article lists. With credentials, database errors fail visibly rather than silently pretending there are no articles.

## Deploy on Vercel

1. Run `supabase/migrations/003_articles.sql` in the Supabase SQL editor. RLS is enabled; the service role reads articles on the server.
2. Import this repository as a new Vercel project. Set **Root Directory** to `hub`, framework Next.js. Enable inclusion of files outside the root directory (shared `channels/*/channel.json` imports).
3. Add server environment variables `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` for the desired environments. Never prefix them with `NEXT_PUBLIC_`.
4. Deploy, add `hub.ammaad.online` under project Domains, and create the DNS CNAME `hub` pointing to the exact target Vercel supplies. Redeploy after changing environment variables.
5. Check `/`, `/c/futurework`, `/c/tradewinds`, `/c/escapevelocity`, `/about`, `/privacy`, and a generated `/a/<slug>`.

Channel names, descriptions, accents and shared YouTube/Instagram handles come directly from `../channels/<key>/channel.json`. Facebook handles are absent in those files: TODO set optional `HUB_FACEBOOK_URL_FUTUREWORK`, `HUB_FACEBOOK_URL_TRADEWINDS`, `HUB_FACEBOOK_URL_ESCAPEVELOCITY` to the real Page URLs in Vercel. Missing links are omitted. The hub Facebook Page itself remains an owner setup task.

## Article production

After a successful long YouTube upload, `pipeline.run_all` calls `pipeline.article` with a nonfatal error boundary. Claude uses the channel persona, medium effort, structured output and existing cost logging, guarded by the monthly budget. Private or scheduled video embeds may be unavailable until YouTube makes the video public; generating a blog article never changes video privacy or scheduling.

Backfill/retry a saved long script from the repository root:

```sh
.venv/bin/python -m pipeline.article <content_id>
```

Requires an existing long `content` row, `out/<id>/script.json`, Claude credentials and database configuration. Reruns reuse an existing article and refresh its YouTube ID without another Claude call. Slugs include the content ID for uniqueness. Dry runs create fixture articles with null `published_at` and no Claude call; these are hidden from the public site. Live articles get `published_at` on generation and become visible within 10 minutes. A later real invocation replaces a dry-run fixture article with a Claude article.
