Run from the repository root after installing dependencies in both apps:

    python3 dashboard/scripts/mobile/run.py

Requires system `google-chrome` and hub's existing Playwright dev dependency.
Ports 4340, 4341 and 43992 must be free. The runner uses invented PostgREST records,
opt-in hub previews and a local QA signing placeholder. It blocks Next's environment
file loader and never opens `.env`. Sends/retries are intercepted in the browser.

Checks fail on horizontal page overflow, rendered text below 12px or visible
interactive targets below 44×44px at touch sizes. Both hub themes, portrait sizes,
landscape, tablet and desktop are captured. Results/screenshots are ignored under
`dashboard/qa/mobile/` and `hub/design-review/mobile/`. Physical-device keyboard and
Safari behavior still require testing on hardware. The runner closes all processes
it starts in `finally`; browser checks also close Chrome in `finally`.
