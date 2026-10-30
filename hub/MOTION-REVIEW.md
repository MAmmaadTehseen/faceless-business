# Motion review — 30 October 2026

The editorial layout, server rendering, metadata/JSON-LD generators, feeds, sitemap,
OG routes, tracking and privacy-enhanced video facade remain intact. Theme switching
now has a 40px round icon button, a 20px sun/moon, accessible action labels and a
native tooltip. The icon retracts/crossfades using transforms and opacity; a native
circular View Transition reveals the new theme. System preference applies until
an explicit choice, which persists across visits.

Motion includes a session-only eye opening, lead entrance, secondary stagger,
scroll reveals, card lift/zoom/accent rules, server-rendered headline word reveals,
reading progress, TOC tracking, evidence entrances, FAQ answer entrances/exits,
one-shot play-button pulse, channel-rule draw, link/focus/press feedback and shared
article image/title transitions. Unsupported native APIs retain ordinary navigation.
Reduced motion disables animations, transitions and smooth scrolling. No scroll
listeners, continuous JS frame loop, Lenis, layout animation or persistent
`will-change` layers are added. See DESIGN.md for the library rationale and tokens.
FAQ height changes instantly: only its answer's opacity/transform animate, resolving
the requested height effect in favor of the stricter performance rule.

## JavaScript

Next 15.5.28 production builds passed, without application environment files.
The raw `next build` First Load JS rows (kB) are:

| Route | Before | After |
| --- | ---: | ---: |
| Home | 111 | 111 |
| Channel | 111 | 111 |
| Article | 113 | 130 |

Those page rows do not fully attribute the shared layout island. The following
more complete totals gzip each unique JS chunk in the **union of layout and route
build manifests**, counting each once (KiB = 1024 bytes):

| Route | Before | After | Added |
| --- | ---: | ---: | ---: |
| Home | 111.40 | 128.15 | 16.75 |
| Channel | 111.40 | 128.15 | 16.75 |
| Article | 112.68 | 131.27 | 18.59 |

The initial article increase is below the +25 KiB target. LazyMotion also fetches
17.23 KiB asynchronously (17.10 KiB domAnimation plus a 0.13 KiB wrapper). This is
additional transfer, excluded from Next's initial-route figures; total additional
article transfer after hydration is about 35.82 KiB. `motion/react-m` avoids the
larger initial bundle produced by the proxy export. Playwright and web-vitals are
dev dependencies and are never imported by the application.

## Local vitals

Chrome 155.0.8059.79, unthrottled local `npm run dev`, opt-in fixture data,
warmed routes/images, web-vitals 6.2.3. Each median uses four ordinary-motion
samples: 390/1440px × light/dark. Theme-button interactions are included; article
samples also include a FAQ interaction. The raw JSON retains all 24 combinations,
including channel pages and reduced motion. No source edits or concurrent builds
occurred during the final measured run.

| Route | LCP before → after (ms) | CLS before → after | INP before → after (ms) |
| --- | ---: | ---: | ---: |
| Home | 246 → 348 | 0 → 0 | 0* → 40 |
| Article | 340 → 328 | 0 → 0 | 24 → 36 |

*Zero means no qualifying event duration was reported (below the observer's 16ms
threshold), rather than proof of zero input latency. These small local samples
are development diagnostics, not field Core Web Vitals or production guarantees.
An earlier cold/HMR-contaminated run was discarded; the stored results above use
the same warmup protocol for both versions.

## Verification and artifacts

- 24 final full-page screenshots: home/channel/article × 390/1440 × light/dark ×
  ordinary/reduced motion. Every image decoded; no horizontal overflow or client
  exceptions. The screenshots omit Next's development-only overlay.
- Reduced-motion checks found no running animations. Card hover lifts 2px; eye
  opening does not repeat on session reload. Real native router and theme View
  Transitions, FAQ close, stable video-facade dimensions and section-observer
  fallback all passed.
- Existing `scripts/check-seo.mjs` passed before and after: canonical
  metadata, OG/Twitter, verification sentinel, Article/FAQ/Breadcrumb/Video JSON-LD,
  analytics, robots, sitemap, feeds, OG endpoints and archive pagination.
- Chrome console probe found only Next's image-priority warning for the shared
  sample-video thumbnail used by fixtures; it found no client exceptions or
  hydration errors. Fixture thumbnails are not production editorial assets.
- Each browser closes in `finally`; the QA runner stops the dev server's entire
  process group before building. No live services, credentials or migrations
  were used, and no commits were made.

Artifacts are local in the existing ignored `design-review/` directory:
`motion-*-vitals.json`, `motion-js.json`, `motion-*-build.log` and
`motion-{home,channel,article}-{390,1440}-{light,dark}[-reduced].png`.

Reproduce from `hub/` with installed npm dependencies and local Chrome:

```sh
MOTION_PHASE=before python3 scripts/run-motion-qa.py
MOTION_PHASE=after python3 scripts/run-motion-qa.py
node scripts/check-motion-size.cjs /tmp/plainsight-motion-before-qa /tmp/plainsight-motion-after-qa
```

The before runner restores the five original changed application files from Git
HEAD in its disposable copy. Both runners exclude `.env*` and `.vercel` when
copying the app. Production builds deliberately disable fixture content.
