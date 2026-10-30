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

Requires an existing long `content` row, `out/<id>/script.json`, Claude credentials and database configuration. Reruns reuse an existing article and refresh its YouTube ID without another Claude call. New slugs are short and use numeric collision suffixes; existing slugs are preserved. Dry runs create fixture articles with null `published_at` and no Claude call; these are hidden from the public site. Live articles get `published_at` on generation and become visible within 10 minutes. A later real invocation replaces a dry-run fixture article with a Claude article.

The hub includes a first-party, cookie-free tracker (`public/t.js`) that sends page views, visible-time heartbeats, scroll milestones and link/embed interactions to `/api/t`. It respects Do Not Track and Global Privacy Control, skips known bots, and stores only daily visitor hashes rather than IPs. Sessions use in-memory IDs, with no browser storage. Apply `supabase/migrations/008_hub_events.sql` before use; the dashboard Hub tab reads server-side aggregates. Set optional `HUB_HASH_SALT` to a private random value in the hub server environment; a constant fallback is available, and the UTC date rotates identifiers daily. The route silently returns 204 when Supabase is unconfigured. Rate limits are per warm server instance (120 events per visitor per minute); embed clicks record facade activation (with iframe focus as a fallback), not confirmed video plays. URLs exclude query strings and fragments. Avoid putting personal information in URL paths or campaign names.

## Search, sharing and feeds

Set optional `NEXT_PUBLIC_SITE_URL` to the public origin (default `https://hub.ammaad.online`, no trailing slash). All canonical URLs, English hreflang links, feeds, sitemap and structured data use it. Page URLs omit trailing slashes; Next.js redirects slash variants. Home and channel shares use the static `/opengraph-image`; articles generate a 1200×630 PNG at `/a/<slug>/opengraph-image`. Twitter cards use the same images. System fonts render immediately without downloads or font swapping.

Apply `supabase/migrations/009_hub_seo.sql` before deploying the article producer: it adds `summary_for_og` and `updated_at` plus an update trigger. Existing records fall back to publication time until modified. Existing slugs stay unchanged; new slugs are at most 60 characters and resolve collisions with a numeric suffix. Excerpts longer than 160 characters get a word-boundary sharing summary without another model call.

RSS is available at `/feed.xml` and `/c/<key>/feed.xml`; pages advertise the relevant feed. `/sitemap.xml` includes public pages and published articles, refreshed every 10 minutes. `/robots.txt` permits crawling while excluding `/api`. Articles expose Article, BreadcrumbList, FAQPage (where present) and VideoObject (where a video exists) structured data. Video upload dates currently use the article publication time because the article table has no separate YouTube upload timestamp. Related articles and previous/next links stay within the channel.

For Google Search Console:

1. Add a **URL-prefix property** matching the configured public origin. Choose HTML tag verification and copy only its `content` value into the server environment variable `GOOGLE_SITE_VERIFICATION` on Vercel. Redeploy, confirm the meta tag in page source, and click Verify. Alternatively use a Domain property and Google's DNS TXT verification; that does not need this variable.
2. Submit `https://hub.ammaad.online/sitemap.xml` (or your configured origin) in **Sitemaps**. Use URL Inspection on a published article to test live rendering and request indexing. Monitor indexing and structured-data reports; submission does not guarantee indexing.
3. General blog articles are [not eligible for Google's Indexing API](https://developers.google.com/search/apis/indexing-api/v3/quickstart) (reserved for supported job/live-stream pages); use the sitemap and URL Inspection instead.

Security headers deny framing of the hub while permitting outgoing YouTube privacy-enhanced embeds. Compressed responses and Next-managed immutable build assets retain framework caching; public image/font assets receive a one-day cache. The lite video facade reserves its aspect ratio and loads the iframe only on activation. The tracker records that activation as `youtube_embed` and avoids counting the subsequent iframe focus again; browser privacy opt-outs still apply.

### Editorial design verification

`DESIGN.md` defines the typography, palette, page structure and component rules.
Source Serif 4 is vendored under its OFL license and served by `next/font/local`
(preloaded, `display: swap`), so builds do not depend on Google Fonts availability.

For a credential-free local preview with 42 test articles, run:

```sh
SUPABASE_URL='' SUPABASE_SERVICE_KEY='' HUB_PREVIEW_FIXTURES=1 GOOGLE_SITE_VERIFICATION=local-check npm run dev
node scripts/check-seo.mjs http://localhost:3000 preview-story-0
```

Fixture mode is disabled in production. The SEO script expects the fixture article's
FAQ and video and an explicit verification value; it never reads credentials.

For Chrome screenshots and interaction assertions, install Playwright in a temporary
location, then set `PLAYWRIGHT_MODULE` to that package directory and run
`node scripts/check-design.cjs` from `hub/` while the fixture dev server runs on port
3100. The script uses `/usr/bin/google-chrome`; change that path for other machines.
Results and review limits are in `design-review/README.md`.

### Article images

Apply `supabase/migrations/013_article_image.sql` before deploying the article writer.
It adds nullable `articles.thumbnail_path`; existing rows continue to work without
backfilling. The writer uploads the saved long video's thumbnail to the existing
public `media` bucket at `articles/<content-id>/thumbnail.jpg`, including on cheap
reruns of an already published article. Missing files or Storage errors preserve the
previous path. Dry runs never upload. Re-running `python -m pipeline.article <id>`
can backfill an article when its local render artifacts are still available.

The hub prefers that image, then verified YouTube maxres/hqdefault thumbnails,
then the article OG route and local channel artwork. Availability checks are cached
for ten minutes; an on-error chain also covers assets disappearing after render.
Among the twelve most recent articles, home chooses the first with a verified
editorial image before falling back to the newest story's generated artwork.
The migration is additive; this change does not apply it or alter bucket policies.
After applying it, run the RLS check required by the root AGENTS.md.
