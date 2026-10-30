# Editorial motion and image review — 30 October 2026

The lead image now prefers a persisted pipeline thumbnail in public media, then
YouTube maxres, YouTube hqdefault, the article's generated OG route and local channel
artwork. Missing or invalid video IDs never produce YouTube requests. Only the
configured public media origin and YouTube are probed. Availability is coalesced
within a worker and cached for ten minutes across server renders. A client error
chain, including a hydration-time failed-image check, handles disappearing assets.
The lead is the newest of twelve recent candidates with a verified editorial image,
falling back to the newest story when none has one. Only the recent candidates and
the three displayed stories per channel need image resolution.

Article cards render synchronously after image resolution. This avoids streaming
individual cards into already-painted empty tracks. Main reserves a viewport while
server content resolves, so the footer cannot initially paint above pending content.
Grid tracks and children have zero minimums, deks wrap, and image frames reserve
aspect ratios with cover fitting. The 1335px secondary column remains within the
viewport. Migration 013 adds nullable `articles.thumbnail_path`; the schema mirrors
it. The article writer uploads the existing renderer/QA thumbnail on ordinary and
cheap reruns, preserves the old path on missing media or upload failure and never
uploads in dry runs. No migration was applied and no live credentials were used.

## Motion and accessibility

- Opaque, masked masthead headline lines with a stagger and delayed dek entrance;
  CSS ambient gradient and static SVG noise. The LCP headline is never hidden.
- Channel-directed image wipes, CSS view-timeline parallax and article hero settling;
  cover frames clip overscan. Hover adds image scale, shine, underline and pointer tilt.
  Generated OG/channel artwork keeps its typography safe area: it receives wipes,
  shine and tilt while photo-only zoom/parallax is skipped.
- Section counters and rules, below-fold paragraph entrances, evidence rule/content
  reveals, quote scaling, sequential takeaway ticks and a spring-shaped TOC marker.
- Native shared card/image/title View Transitions, with an ordinary-link fade fallback.
  Theme switching retains its circular transition and persisted accessible control.
- Fine-pointer cursor dot and magnetic masthead links; pointer work is event-driven
  and rAF-throttled. No continuous JavaScript frame loop or scroll listener.
- FAQ height expands and closes with a short spring-shaped animation after explicit
  interaction. It completes within the recent-input exclusion window for CLS.
- Reading progress morphs into an ink completion capsule / back-to-top control
  through a single native transform animation; no prose geometry changes.
- Motion's `motion/react-mini` drives scoped tactile button animations. The previous
  LazyMotion/domAnimation feature download is no longer required. CSS and native
  browser APIs handle the other effects; motion timing is centralized in motion.ts
  and CSS custom properties.
- Reduced motion disables animations, transitions, smooth scrolling and the cursor.
  Touch/coarse pointers receive neither cursor nor magnetic/tilt effects. Runtime
  preference changes cancel active animations. Content remains readable without JS.

The owner-requested ambient gradient and FAQ height spring supersede the older
no-gradient and instant-FAQ-height design rules. DESIGN.md records these exceptions.

## Local vitals

Chrome 155, unthrottled local `npm run dev`, opt-in fixtures, warmed routes/images,
web-vitals 6.2.3. Values below are medians of four ordinary-motion samples per route:
390/1440px × light/dark. The full run also includes reduced motion (24 scenarios).
Theme interactions are measured on every route and FAQ interaction on articles.
All 24 final samples report CLS 0. Intermediate probe/streaming experiments were
discarded; final measurements use the worker cache, synchronous cards and mini entry.

| Route | LCP before → after (ms) | CLS before → after | INP before → after (ms) |
| --- | ---: | ---: | ---: |
| Home | 280 → 316 | 0 → 0 | 36 → 52 |
| Channel | 350 → 420 | 0 → 0 | 36 → 32 |
| Article | 460 → 318 | 0 → 0 | 36 → 36 |

These are development diagnostics, not field Core Web Vitals or a production SLA.
Raw results: `design-review/motion-baseline-vitals.json` and
`design-review/motion-final6-vitals.json`; the latter also retains layout-shift sources.
The final measurement run had no concurrent browser/build QA jobs or source edits.

## Production JavaScript

Next 15.5.28 production builds pass without application environment files.
The comparison counts the union of layout/route manifests once per chunk,
gzip-compressed, plus all unique async feature chunks in
react-loadable-manifest.json (KiB = 1024 bytes).

| Route | Initial before | Initial after | Total before | Total after | Total change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Home | 128.14 | 118.27 | 145.38 | 118.27 | -27.11 |
| Channel | 128.14 | 118.27 | 145.38 | 118.27 | -27.11 |
| Article | 131.26 | 118.71 | 148.50 | 118.71 | -29.79 |

The previous 17.23 KiB asynchronous feature download is eliminated. Article total
transfer decreases by 29.79 KiB, comfortably within the +35 KiB budget. The size
script enforces that budget against total transfer. Raw measurements are retained
in design-review/motion-js.json; build logs are motion-baseline-build.log and
motion-final6-build.log. Playwright/web-vitals stay development-only dependencies.

## Responsive and behavioral verification

The matrix covers home, Future Work channel and article, light/dark and
ordinary/reduced motion at 320, 375, 390, 768, 1024, 1280, 1335, 1366, 1440, 1536
and 1920px: 132 full-page PNGs. The script checks document scrollWidth against
innerWidth and each visible element's bounds. Overscanned images are intersected
with their explicit clipping ancestors, so intended cover/parallax overscan is not
mistaken for visible overflow. Fixed elements are included. Next's development
portal is excluded from the editorial checks and screenshots. Every image decodes. Static full-page artifacts freeze offscreen masks at their
revealed state after the live bounds checks, so all editorial images remain visible
in the exported PNG; live/reduced motion and interactions are tested separately.

Final overflow results (12 cases per width: three routes × two themes × two
motion preferences):

| Width | Document / element bounds |
| ---: | --- |
| 320 | PASS 12/12 |
| 375 | PASS 12/12 |
| 390 | PASS 12/12 |
| 768 | PASS 12/12 |
| 1024 | PASS 12/12 |
| 1280 | PASS 12/12 |
| 1335 | PASS 12/12 |
| 1366 | PASS 12/12 |
| 1440 | PASS 12/12 |
| 1536 | PASS 12/12 |
| 1920 | PASS 12/12 |

Raw results: design-review/editorial-overflow.json. QA ports 3137, 3138 and 3139
were verified closed after cleanup; every browser is closed in its finally block.

The interaction script exercises actual native router/theme transitions, session-only
brand opening, FAQ close, reserved video dimensions, unsupported-timeline observer
progress/TOC and forced YouTube/OG failures recovering to local branded artwork.
The server image checks cover absent IDs, maxres/hqdefault failures, stored thumbnail
preference and URL allowlisting. Offline thumbnail checks cover renderer filenames,
thumbnail.jpg, dry runs, missing media and failed-upload preservation.

SEO checks cover metadata, canonical/alternate URLs, Article/FAQ/Breadcrumb/Video
JSON-LD, analytics, verification sentinel, feeds, sitemap, robots, OG images and
archive pagination. The article unit suite passes (10 tests, 8 subtests).

## Reproduction and cleanup

The QA runner copies the hub to a disposable /tmp tree, excluding `.env*`, `.vercel`,
node_modules and build/review artifacts. Existing installed dependencies are linked.
Fixtures are explicitly opt-in and disabled by production builds. It starts the dev
server in its own process group; every Playwright browser closes in `finally`, and
the server group stops before building. All started dev/browser processes are cleaned
up. No commits, environment-file modifications, live DB changes or paid API calls.
The initial existing Python unit-suite invocation imported common.py, which
automatically loads the repository .env. No values were printed or modified. The
suite was rerun in a disposable copy without environment files and with dotenv
loading explicitly disabled. The hub QA copies exclude environment files throughout.

From hub/, preserve a baseline build before making changes:

```sh
MOTION_PHASE=baseline python3 scripts/run-motion-qa.py
# Make changes, then run the complete final matrix:
MOTION_PHASE=after python3 scripts/run-motion-qa.py
node scripts/check-motion-size.cjs /tmp/plainsight-motion-baseline-qa /tmp/plainsight-motion-after-qa
node scripts/check-article-images.cjs
python3 scripts/check-article-thumbnail.py
```

The baseline runner snapshots the current source; it no longer silently replaces
selected files from Git HEAD. MOTION_PORT can select a different local port. The
final run here uses phase final6; its build/dev logs and screenshots remain in the
ignored design-review/ directory. No screen recording is required.
