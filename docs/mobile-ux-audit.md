# Mobile UX audit — 2 November 2026

Continuation inspection: only dashboard/tsconfig.json was modified; preserved. No prior
mobile-ux-audit.md existed. Existing dashboard/qa and hub/design-review screenshots
were retained. New baseline captures use local invented data, Chrome device metrics,
touch input and deviceScaleFactor 3 at 390×844. No environment files are loaded.

## Before: concrete issues to fix

| Screen | Current issue at 390px |
| --- | --- |
| Dashboard shell | Scope expands in header; two header rows and bottom tabs consume too much height. Tablet switches prematurely to sidebar. More lacks focus containment/swipe dismissal. |
| Home | Five attention rows, stacked channel cards, runs follow channels; hero has no sparkline. Run menus expand inline. |
| Content | Search hidden with filters; filter overlay lacks accessible dialog semantics and dismissal. Thumbnails disappear in one mobile rule. |
| Video | Overview, Shorts, Comments and Details form one long page. No compact scroll title. |
| Inbox | Reply drawer does not track visual viewport/keyboard; composer is in scroll flow. |
| Analytics | Hover value overlay competes with chart; mobile report rows expose multiple concerns. |
| Queue | Topic actions inline; day strip lacks snap behavior. |
| Costs | Small ledger controls/text; budget context needs readable mobile spacing. |
| Automation | Dense settings require larger inputs and grouped spacing. |
| Login | Verify password manager fields and remove autofocus. |
| Hub shell | Large header; theme target too small; does not hide on downward scroll. |
| Hub home | Large masthead delays lead story; all cards use image-above layout. No channel chip strip. |
| Hub channel | Large channel header; mobile archive should read as a clean list. |
| Hub article | No mobile TOC; long byline; h1 needs mobile scale; no near-end share/next bar. |
| Hub about/privacy | Check long links, minimum text and navigation targets. |

Baseline screenshots: dashboard/qa/mobile/before-*.png and
hub/design-review/mobile/before-*.png (ignored QA artifacts).

## Verification and after

Implementation and measured checks will be recorded below as completed. Screenshots
are evidence of local fixtures, not live account data. Physical-device keyboard,
Safari safe-area behavior and real network vitals require separate device testing.

## After: screen-by-screen

| Screen | Result |
| --- | --- |
| Dashboard shell | One 52px scope row; channels and platforms in a modal sheet. Home / Content / Inbox / Analytics / More remain through 1023px; Inbox has unread count and More has active selection. Sheets trap/restore focus, lock scrolling, close on backdrop/Escape, and dismiss by swiping their handle. |
| Home | 24h views, honestly labelled seven-day comparison and sparkline; 2×2 supporting stats; three attention items; runs before channels; channel cards snap with next-card peek. Mobile run actions use a sheet; desktop menus remain. Missing subscriber metrics and exact publish time can be expanded. |
| Content | Visible search and one Filters trigger with active count. 80×45 thumbnails, two-line titles, one status and views; Load more after 20 rows. Empty view has Clear filters. Trends/export disclosure retains chart, CSV, extra metrics and recovery actions. |
| Video | Overview / Shorts / Comments / Details segments; compact fixed title after scrolling, with tabs in page flow to keep chrome small. Four hero metrics form a 2×2 grid. Shorts expand in place. Failed upload rows explain connection, capacity, media or account issues; raw response is under Details; Retry/Rebuild spans the row. Desktop retains all sections. |
| Inbox | Conversations retain explicit Reply and Dismiss. Reply opens a full-screen view with a prefilled draft; composer tracks visualViewport height and offset and stays above the simulated keyboard. Send remains in the bottom area. Flag reasons expand on tap. |
| Analytics | Scrollable section segments and time chips; 200px charts, touch readout above the chart and series chips. Floating hover cards and scaled axis text are removed on touch layouts; extra report metrics remain disclosed. Overview chart stays visible. |
| Queue | Seven-day snap strip; Scheduled expands to exact time; topic overflow opens a sheet with priority/kill actions. Desktop inline actions remain. |
| Costs | Budget bar and existing projections/ledger retained; links, inputs and chart date sliders meet touch size through tablet/landscape. |
| Automation | Existing grouped settings retained; toggles on right with 44px interactive geometry, 16px fields, comfortable spacing and density-independent touch controls. |
| Login | No autofocus; named password field with current-password autocomplete; large submit action positioned lower on the screen. |
| Hub shell | Compact 60px header with 44px theme control, hides downward and returns upward; reading progress remains separate. Touch disables decorative cursor/tilt/parallax, FAQ height animation and theme snapshot animation. |
| Hub home | Compact promise and snapping channel links; lead story is visible in the first viewport; following stories use title-left/thumbnail-right rows. Server-rendered lead image/title remain visible at first paint. |
| Hub channel | Compact header, archive list on phones and useful two-column layout on tablets; subscription, RSS and pagination retained. |
| Hub article | 18px prose / 1.65 line height, 20px gutters, approximately 30px h1, short single-line byline. Distinct answer/takeaways; inline collapsible TOC plus floating sheet; full-bleed video; near-end Share/Next bar; 48px FAQ targets. Long links wrap and wide tables scroll within the prose. |
| Hub About / Privacy | Article-width reading retained, larger navigation targets and wrapping verified. |

After evidence: `dashboard/qa/mobile/final-*-390.png`,
`dashboard/qa/mobile/final-analytics-*.png`,
`dashboard/qa/mobile/after-*-390-dark.png`, and
`hub/design-review/mobile/final-*-390.png` / `after-*-390-{light,dark}.png`.
Full-page and desktop screenshots are retained alongside them. All screenshot/output
folders are gitignored; baseline files and earlier QA work were preserved.

## Automated results

- **189 route/theme/viewport cases: pass, zero failures.** Chrome with touch,
  mobile device metrics and deviceScaleFactor **3**. Shapes: 320×844, 360×844,
  390×844, 430×844, 768×1024, 844×390 landscape, and 1440×900 desktop. Includes
  every Analytics tab, empty Content and empty Video. Hub runs in light and dark.
  Visible interactive targets fail below 44×44 CSS px; text fails below 12px;
  any horizontal page overflow or application error fails the run.
- **42 additional Analytics cases: pass.** All seven tabs at six touch shapes,
  rerun after restoring the overview chart and Content report disclosure.
- **16 stress cases: pass.** Both densities at 320/390/768/1440, with deliberately
  long titles, unbroken links and wide table fixture content: no page overflow.
- **16 interaction assertions: pass.** Scope/More/run/filter opening and dismissal,
  filter application, prefilled reply, simulated 400px visual viewport, mocked Send,
  Short disclosure, readable failure, mocked Retry, inline TOC, TOC sheet swipe,
  near-end actions and Article/FAQ/Video/canonical SEO presence.
- Additional final review passes focus containment, actual channel/platform selection,
  dashboard-sheet swipe, Queue overflow and mocked priority action, Content CSV
  availability, touch chart readout, and header scroll-direction behavior.
- **CLS 0 on all 13 final local 390px route samples**, observed before stress
  mutations. This is local fixture evidence, not a field Core Web Vitals claim.
- **Both `npm run build` commands pass**, including TypeScript validation.
  Builds and QA use a Node preload that disables environment-file loading.
- `git diff --check` passes for this task's scope. No commits, credentials or
  environment-file changes. No additional production dependencies.

Reproduce from repository root: `python3 dashboard/scripts/mobile/run.py`.
See `dashboard/scripts/mobile/README.md`. The scripts use invented data only and
intercept publishing/reply actions; they do not call real account mutation APIs.

## Limits and physical-device checks

No physical phone was available. Safari keyboard animation, iOS home-indicator/notch
safe areas, native share-sheet behavior and real haptics remain unverified on hardware.
The smaller visual viewport is simulated; real keyboard behavior must still be checked.
Local CLS samples do not establish production LCP/INP or performance on a slow network.
Live platform retry success, real reply delivery, account permissions and production
analytics data were intentionally outside fixture UI verification. Existing SEO routes,
server rendering, metadata and tracking/facade integration remain in place.

Cleanup confirmed: both QA dev servers, the fixture server and supervisor are stopped
(ports 4340/4341/43992/4349 refuse connections). Chrome was closed by the browser
suites' finally blocks; no Playwright profile/artifact directories remain in `/tmp`.
Unrelated concurrent workspace changes outside dashboard/hub were left untouched.
