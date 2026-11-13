# Local film reviews

This opt-in tool accepts a movie on your laptop and produces an original narrated
cinematic recap (hook, the story told in present tense, a short verdict) and four
hook-driven Shorts, with our own narration burned in as upper-case word groups. **Rights basis is the owner's
responsibility.** Selecting a basis does not establish copyright permission;
check the licence covers excerpts, adaptations, distribution and any audio bed.

Nothing is added to scheduled workflows. Its config is deliberately named
`channels/filmreview/local.json` so automatic channel discovery cannot pick it up. No hosted database migrations are needed.
Existing Vercel dashboard routes are unchanged; `/recap` and `/api/recap` return 404
on Vercel even if LOCAL_RECAP=1. No video source is served to the browser.

## Setup and run

Use Python 3.12, the repository `.venv`, Node and ffmpeg/ffprobe. Install the usual
requirements first, then the local transcription dependency:

```bash
.venv/bin/pip install faster-whisper
# CPU torch must be installed before Kokoro (never install CUDA wheels):
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install kokoro soundfile
cd dashboard
npm install
LOCAL_RECAP=1 npm run dev -- --hostname 127.0.0.1
```

Open http://127.0.0.1:3000/recap. **Keep the server bound to 127.0.0.1.**
Do not expose it through a proxy, tunnel or LAN bind. This section uses loopback
and same-origin checks instead of dashboard login. It rejects forwarded requests
and foreign origins; LOCAL_RECAP is never sufficient to enable it on Vercel.

The worker uses `faster-whisper` CPU/int8 (`small`; override RECAP_WHISPER_MODEL),
ffmpeg scene cuts and offline Kokoro. Initial model downloads require internet
and disk space. Claude is used only after Generate (or paid Regenerate); local
validation and estimation do not call it. Supply ANTHROPIC_API_KEY using your
normal local configuration. Costs go through the usual Claude costs log and
CostGuard, using the local SQLite database and its monthly_budget_usd setting.
The estimate is not a hard price cap. Local spend is not combined with hosted
Supabase spend; account for any simultaneous cloud work in the local budget.

Paste an absolute video path, title and year. Choose public domain, Creative
Commons (licence and URL), written permission (note), or own work. Validate to
save `out/recap/<id>/rights.json` and see the cost estimate. Click Generate to
start paid work. The page polls stage progress; keep its project URL to reopen.
The film transcript stays local except as evidence sent to Claude along with
sampled scene frames to ground criticism and scene selection.

The long review is 16:9 and 5–9 minutes. Shorts are 9:16 and below 60 seconds.
Both reframes keep the upper 80% of the picture so subtitles burned into a source
stay out of frame; the long video is then letterboxed, Shorts are centre-cropped
to fill 9:16. No source audio is included unless the explicit low bed setting is
selected; the low bed is the original source audio mixed underneath narration.
The only burned-in text is our own narration (three-word upper-case groups, under
1.6 s each, `on_screen.srt`); the film's own text is never burned in. No flips,
speed/pitch changes or detection-evasion effects are used. The YouTube caption
track (`captions.srt`) contains the new narration only. The voice is Kokoro
`am_fenrir` at +8% (set in `channels/filmreview/local.json`). All five pieces undergo existing probe, temporal and vision checks; vision
failure blocks approval. Duration violations stop generation for regeneration.

Review every video, its script and QA, edit title/description, then save, approve
or discard. Regenerate rebuilds only the selected piece and clears approval.
Uploaded pieces are immutable. Upload acts only on approved, QA-passed pieces
with a rights record. Upload the long review before its Shorts. A private upload
with publishAt will become public at its assigned calendar time: private here is
the initial API privacy, not a promise of indefinite privacy.

## Running from the terminal (no dashboard)

Set the provider so the owner's Claude credits are not spent, use the local SQLite
database, and force Kokoro. Nothing in these commands uploads.

```bash
export RECAP_LOCAL_DB=1 LLM_PROVIDER=lunaroute TTS_BACKEND=kokoro
# single film: create, then generate
printf '%s' '{"path":"/abs/film.mkv","title":"Film","year":2026,"rights":{"basis":"own work"}}' \
  | .venv/bin/python -m pipeline.recap.worker create          # prints state with "id"
.venv/bin/python -m pipeline.recap.worker generate --id <id>   # transcribe, script, voice, render, QA
.venv/bin/python -m pipeline.recap.worker rerender --id <id>   # re-render from saved script and narration
.venv/bin/python -m pipeline.recap.worker regenerate --id <id> --piece short2
```

Outputs: `out/recap/<id>/{long,short1..4}/video.mp4`, `thumbnail.jpg`, `captions.srt`,
`on_screen.srt`, `shots.json` (which film scene is on screen when, used to map QA
findings to scenes) and `state.json` (status, QA per piece). Workers log to stdout
before the final JSON line; take the last line when parsing.

## Batch mode (folder of films)

`pipeline.recap.batch` scans the top level of one folder (subfolders are ignored),
registers each video in `recap_films`, and processes approved films one at a time.
Title and year come from the filename (`Title 2026 ... .mkv`); files without a
year are listed as `needs rights` and never processed. Duplicates are detected by a
content hash (size plus three sampled megabytes) and by title+year or near-identical
duration; `possible duplicate` rows wait for confirm/skip. Rights come from a
`<file>.rights.json` sidecar, a `rights.json` sheet keyed by filename in the folder,
or the per-film edit below. Re-running the batch never redoes a film whose project
reached review (`already processed`); a failed film is retried only after `retry`.

```bash
export RECAP_LOCAL_DB=1 LLM_PROVIDER=lunaroute TTS_BACKEND=kokoro
.venv/bin/python -m pipeline.recap.batch --folder ~/Videos                 # scan only, prints JSON
printf '%s' '{"id":"<film id>","rights":{"basis":"own work"}}' \
  | .venv/bin/python -m pipeline.recap.batch --folder ~/Videos --edit     # set rights for one film
.venv/bin/python -m pipeline.recap.batch --folder ~/Videos --approve      # approve all "new" films and run
.venv/bin/python -m pipeline.recap.batch --folder ~/Videos --run          # resume an approved batch
printf '%s' '{"id":"<film id>","retry":true}' | .venv/bin/python -m pipeline.recap.batch --folder ~/Videos --edit
```

Edit decisions: `{"decision":"confirm"}` processes a possible duplicate, `{"decision":"skip"}`
skips it. A batch holds one folder-wide lock, so two batches never run at once.
The dashboard `/recap` page drives the same commands.

## Dedicated channel token (owner action)

Create a dedicated YouTube channel for Frame and Argument (or edit its local
name/handle in channels/filmreview/local.json). Enable YouTube Data and Analytics
APIs in your Google project, configure a Desktop OAuth client, and set local
YT_CLIENT_ID and YT_CLIENT_SECRET. The existing authorization helper requests
`youtube.force-ssl`, which permits captions.insert:

```bash
.venv/bin/python scripts/youtube_auth.py url filmreview
# Sign in as the dedicated channel. After consent, copy the localhost redirect URL.
.venv/bin/python scripts/youtube_auth.py token '<redirect URL>' filmreview
```

The second command is for the owner to run: it writes YT_REFRESH_TOKEN_FILMREVIEW
to local `.env`. Never paste the token into the dashboard or commit it. No GitHub
secret or cron is needed. Missing configuration is reported on Upload.

Uploads reuse the existing publication idempotency/quota guard, synthetic-media
flag and private scheduled upload. Filmreview has a local calendar: Tue/Fri/Sun
17:00 UTC; child Shorts on following days at 19:00 UTC. Occupied slots and three
publications per day are respected, with at least one hour's lead time. The new
calendar is confined to the local tool. Captions use captions.insert after the
video ID is saved; retries reconcile named tracks and do not reupload the video.
Quota exhaustion retains local media for retry. Keep local project files until
all uploads and captions are complete. Existing shared quota reservations apply.
No Meta accounts are configured for this channel; this private-only tool does not
publish Reels (Reels require public publishing).

A crashed upload with an uncertain outcome needs Studio reconciliation before
retry, as with the normal uploader. A crashed dashboard can leave a `launch` file:
stop its worker before deleting that one project's launch file. Do not delete an
active job's lock or outputs. Generated intermediates and media stay under the
already ignored `out/` directory; delete old projects manually when finished.

## Verification without paid calls

```bash
timeout 240 .venv/bin/python -m pytest tests -q
cd dashboard && npm run build
```

`tests/test_recap.py` generates a short lavfi source and runs the real local
assembly/captions/thumbnail/QA path, with Claude, Whisper and Kokoro mocked and
small render dimensions. Tests make no Claude, YouTube or Meta requests.

Spend and the film registry use the hosted database, so they count toward the monthly budget and the record of finished films survives restarts. Apply `supabase/migrations/014_recap_films.sql` first. Set `RECAP_LOCAL_DB=1` to use local SQLite instead.
