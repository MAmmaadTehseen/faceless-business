# Dashboard redesign review

Design contract: [DESIGN.md](DESIGN.md). Work is confined to `dashboard/`; no commits were made.

| Page | Simplified presentation |
| --- | --- |
| Home | Replaced the repeated metric grids with a 24-hour views hero and four supporting stats. Limited attention to five items. Quiet channel cards contain three numbers and a neutral sparkline; production actions live in Run menus. Upload errors are disclosed; recent published content is limited to five. |
| Analytics | Four metrics, one period selector, underline tabs, one filter toolbar, full-width chart and alternating table rows. Series selection lives in the first column. Metric definitions and secondary Hub channel comparisons are disclosed. |
| Content | Title-led rows with status and selected-platform metrics. Dates, QA, categories, other platform links and numbers live in Details. The chart is opt-in; sorting, chart inspection and CSV (including creation dates) remain available. |
| Inbox | Avatar, author, time and two-line comment previews. Video/platform context is disclosed. Reply editing uses a desktop drawer or mobile sheet with Escape, focus containment and focus return. Sent conversations are dimmed. |
| Queue | Seven-day topic-plan strip, title-first rows, disclosed source/priority/timestamps. Add-topic form is disclosed. Priority and kill controls appear on hover and remain available on touch and keyboard focus. |
| Costs | One month-to-date/budget hero and projection, neutral channel bars and a plain step table. Channel CSV/table, individual-content costs and run timestamps/logs are disclosed. |
| Automation | One pipeline state, grouped settings, descriptive toggles and disclosed upload limits; removed nested surface styling. |
| Login | Centred brand and password group. Existing policy links are retained. |
| Privacy / Terms | Shared typography, neutral headings/links and accessible link targets; policy copy is unchanged. |

Comfortable / Compact is shared between header instances and persisted in localStorage. Row minimums are 44/36px and card padding 20/12px; touch controls stay at least 44px.

## Local verification

- `npm run dev`, existing read-only `DASHBOARD_QA_BYPASS`, local fixture database and throwaway environment values.
- 64 viewport captures: 16 route/tab variants × 390×844 / 1440×900 × both densities, plus full-page captures and drawer/sheet captures. Files are gitignored under `qa/redesign/`.
- Reviewed screen captures against the design contract, including mobile overflow, secondary metadata, surface noise, status treatment and table width.
- Automated matrix: no horizontal overflow, application errors, text below 12px or tables above six columns.
- Touch audit: no visible interactive targets below 44×44px at mobile width in either density.
- Read-only interaction checks: filter-on-change, platform drill-down, row disclosure, chart selection, analytics periods, mobile More navigation, density reload persistence, drawer/sheet opening and Escape/focus return.
- Final `npm run build` passed with zero type errors; `git diff --check` passed. Chrome, the dev server and its supervisor were stopped and their ports checked closed. Evidence: `qa/redesign/build.log` and `qa/redesign/cleanup.json`.

## Limits

Subscriber gains and stage/ETA progress are not in the existing dashboard data; no replacement values were fabricated. Home shows running states using existing run rows. Queue dates remain the existing cron-based topic estimates, explicitly labelled as plans rather than confirmed publications. Seven-day comparisons are shown where existing analytics provides them; historical state deltas were not added to operational pages.

No live workflows, uploads, replies, likes, queue mutations or settings saves were executed. Production PWA installation/offline behaviour and live external media were not exercised; PWA code, manifests and service worker are unchanged.

The first build invoked Next's default loader, which automatically loaded the existing `.env.local`. Its contents were not inspected, printed or changed. All subsequent dev/build validation disabled environment-file loading and used throwaway values.
