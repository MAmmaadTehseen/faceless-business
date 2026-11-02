# Global scope QA

Fixture verification: 2026-11-02. No live services, environment files or secrets used.

Shared scope parsing and precedence live in `src/lib/scope.ts`; server cookie access lives in `src/lib/server-scope.ts`. Explicit URL fields override saved cookie fields independently. Navigation retains both fields; Clear explicitly selects all channels and all platforms.

| Page | All channels / Instagram result |
| --- | --- |
| Home | 26,460 daily views = 4,410 + 8,820 + 13,230; platform publications, comments, attention and activity filtered. |
| Content | 15 items = 5 + 5 + 5; platform publication status and metrics; detail highlights Instagram and retains all uploads. Detail/back navigation retains scope. |
| Inbox | 9 pending comments = 3 + 3 + 3; mobile badge updates to 9 globally and 3 for Trade Winds. |
| Analytics | 264,600 period views = 44,100 + 88,200 + 132,300. All seven tabs checked. Hub and unsupported watch metrics show notices. Scoped CSV downloaded for platforms/channels/formats/categories/engagement; no watch column for Instagram. |
| Queue | Topics remain shared with a note; scheduled publication list follows Instagram scope. |
| Costs | Channel totals retained with a note explaining costs include all platforms. |
| Automation | Settings retained; scope persists. |

Every main page passed at 390×844, 1280×900 and 1440×900 in Comfortable and Compact density (42 page checks), with no document horizontal overflow. Screenshots and machine-readable results are generated under `qa/scope/`. Sidebar/bottom-tab URLs, selector independence, URL precedence, bare-link cookie fallback, clear/reset and detail/back scope were checked. Local Chrome instances close in `finally`; the fixture/dev server runner terminates its own process groups by PID, never shell-matching patterns.

Commands from repository root:

```sh
node dashboard/scripts/scope-test.cjs
python3 dashboard/scripts/mobile/scope-run.py
python3 dashboard/scripts/mobile/scope-run.py scope-interactions
NODE_OPTIONS="--require=$PWD/dashboard/scripts/mobile/without-env.cjs" npm --prefix dashboard run build
```

All passed. The environment loader shim prevents Next from opening local environment files. Browser QA uses the existing local Playwright dependency under `hub/node_modules` and `/usr/bin/google-chrome`; these must be installed to repeat it. The local QA bypass is GET-only and disabled in production. Both localhost spellings are allowed by the fixture browser network guard because Next development redirects normalize loopback hosts.

Unverified: production deployment, live Supabase/API data, large datasets beyond existing query limits, and real publishing or settings mutations. The fixture cost total is zero for the current month, so nonzero cost reconciliation was not exercised. No commits were made; unrelated pre-existing changes outside dashboard were left alone.
