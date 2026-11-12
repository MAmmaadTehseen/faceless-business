# Evergreen stockpile: owner setup and operation

Normal produce/Shorts jobs keep their existing behavior. Banking is separate and automatic
release defaults to off. No database migration or extra paid service is required.
A bundle means one long video and exactly four child Shorts, or one standalone Short.
Release rate is **bundles per channel per UTC day**, not individual upload attempts.
A long bundle needs capacity for five YouTube uploads; both existing quota reserves apply.

## Owner setup

1. In the existing Google Cloud OAuth project, enable **Google Drive API**. Configure the
   consent screen for the owner Google account. Use the existing `YT_CLIENT_ID` and
   `YT_CLIENT_SECRET`. The Drive grant requests **only**
   `https://www.googleapis.com/auth/drive.file`, with incremental authorization disabled.
   Do not replace any YouTube refresh token. An app left in Testing can have short-lived
   refresh tokens; review its publishing status before the stockpiling period.
2. Privately run:

   ```bash
   .venv/bin/python scripts/youtube_auth.py url drive
   .venv/bin/python scripts/youtube_auth.py token "<full localhost redirect URL>" drive
   ```

   Open the URL as the owner of the 100 GB Drive plan. These owner-run commands read
   local OAuth configuration and save `GDRIVE_REFRESH_TOKEN` in local `.env`; the token
   is never printed. Do not paste the redirect into shared logs/chat.
3. Owner: copy the saved token into the repository's Actions secret
   **GDRIVE_REFRESH_TOKEN**, using GitHub Settings > Secrets and variables > Actions.
   Existing **YT_CLIENT_ID**, **YT_CLIENT_SECRET**, **LUNAROUTE_API_KEY**,
   **SUPABASE_URL**, **SUPABASE_SERVICE_KEY**, and footage secrets must already exist.
   Sync also needs the existing per-channel YouTube/Meta credentials. No Drive token is
   needed on Vercel; its card reads only database metadata.
4. Generate inventories using the owner-run script (these commands call LunaRoute and
   write settings). The script creates `channels/<key>/evergreen.json`; no topics were
   generated during the offline implementation. Each generation accepts only 60–80
   distinct topics after checking all existing channel titles/topics and the inventory.

   ```bash
   LLM_PROVIDER=lunaroute .venv/bin/python scripts/generate_evergreen.py --channel futurework
   LLM_PROVIDER=lunaroute .venv/bin/python scripts/generate_evergreen.py --channel tradewinds
   LLM_PROVIDER=lunaroute .venv/bin/python scripts/generate_evergreen.py --channel escapevelocity
   ```

   Review the generated JSON. The authoritative runner copy is the corresponding
   `evergreen_topics_<channel>` setting, so committing topic files is unnecessary.
   To correct topics or add more specific verified source URLs before production, edit
   that JSON setting as well. Every entry has `topic`, `angle`, and `source_urls`.
   Sources initially use four primary-source domains per niche. Source fetch failures
   or insufficient evidence must fail script/article validation; never bypass QA to fill
   the inventory. Topics explain durable mechanisms, not today's news or forecasts.
   `evergreen_used_<channel>_<topic-slug>` markers and full content history prevent reuse
   across fresh runners. A failed production still consumes its topic to prevent buying
   the same script again accidentally.
5. Deploy these source changes through the owner's usual process. Nothing has been
   committed, pushed, deployed, enabled, or written to live services by the coding agent.

## Start and stop

Test one finished bundle manually:

```bash
gh workflow run bank.yml -f channel=futurework -f count=1
```

Local equivalents (with owner credentials configured):

```bash
LLM_PROVIDER=lunaroute TTS_BACKEND=kokoro .venv/bin/python -m pipeline.run_all --bank --channel futurework --count 1
LLM_PROVIDER=lunaroute TTS_BACKEND=kokoro .venv/bin/python -m pipeline.shorts_daily --bank --channel futurework
```

Bank mode refuses placeholders. It runs the normal voice, footage, rendering, long and
Short QA plus article generation, but makes no YouTube or Meta publications. All four
Shorts must finish and pass. Article text is prepared without publishing it to the hub.

In existing settings storage (Supabase `settings` table), upsert these JSON values:

| key | JSON value | meaning |
| --- | --- | --- |
| `bank_mode_enabled` | `true` | allow hourly scheduled banking |
| `bank_until` | `"2026-11-24"` | inclusive UTC date; choose your actual last paid day |
| `banked_release_per_day` | `0` | automatic release off until explicitly enabled |

The example cutoff covers November 12–24 inclusive (13 calendar days); confirm the plan's
actual expiry. Missing/invalid cutoff or a string `"true"` fails the scheduled gate closed.
At minute 45 each hour, all three channels are eligible for one bundle each. Workflow
runs serialize globally, with at most **two** channel bank jobs active and one per channel.
Long jobs can delay later cron runs; GitHub keeps only a limited pending concurrency queue.
Manual dispatch accepts channel/all and count 1–10 and intentionally bypasses the scheduled
banking toggle/cutoff. `pipeline_paused` still applies to both banking and release.

To stop future scheduled banking, set `bank_mode_enabled` to JSON `false` (or move the
cutoff into the past). Already running jobs finish; cancel their Actions runs if an
immediate stop is needed. Canceling may leave a recovery lock, described below. Normal
daily production continues. To stop automatic release, set `banked_release_per_day` to 0.

## Storage and release

Private app-created folders:

```text
Faceless Stockpile/<channel>/<content-id>/
  <long and short mp4s, thumbnail, captions, narration, QA/production JSON>
  manifest.json
Faceless Stockpile/released/<content-id>/
```

The manifest contains content IDs/parent relationships, titles, descriptions with parent
URL placeholders, tags, category, synthetic-media disclosure, the prepared article,
QA checkpoints, file IDs, byte lengths and SHA-256 checksums. Captions are retained for
recovery; YouTube publication behavior remains the existing pipeline's behavior.
Drive resumable uploads retry interrupted chunks and compare server MD5/size before
checkpointing. Release verifies SHA-256 on downloads. Local files are retained; Actions
runners are ephemeral, and three-day workflow artifacts provide recovery checkpoints.
Files are never automatically deleted from Drive, including failed staging uploads.

Banking checks space before ideation with a conservative 2 GiB production allowance,
and again using the exact bundle size before upload. It stops before consuming the last
5 GiB; Drive/account quota includes other Google storage use. Uploads are serialized by
a database lock across the two bank production slots. External owner uploads can still
change available space. Unknown quota fails closed. No partial bundle is marked banked.
Partial staging files can remain after transport failures; local/media checkpoints remain
in the workflow artifact. Completed files are reusable by name + matching checksum.

Release manually, oldest banked bundle first:

```bash
.venv/bin/python -m pipeline.release_banked --channel futurework --max 1
```

Manual release is explicit authorization and works even with automatic rate 0. To enable
automatic release, set `banked_release_per_day` to a positive JSON integer, e.g. `1`.
The existing six-hour sync workflow releases after normal queue drain/sync, only when both
quota buckets have room. Starts are counted per bundle/channel/UTC day and persisted before
upload; reruns do not reset the rate. An unfinished start may be resumed without consuming
a second rate slot. Quota races still use the existing atomic publisher reservations and
queue storage; daily normal uploads retain the same behavior and reserves.

Release calls no models. The long video's remote ID must be known before its Shorts
start, so parent URLs are preserved. Existing scheduler slots, synthetic-media disclosure,
private-until-audit behavior, optional YouTube promotion, idempotency/uncertainty guards
and Reels behavior all come from the normal publisher. The article is saved only after
all bundle YouTube IDs exist. Then the folder moves to `released/`; it is never deleted.
Partial releases remain discoverable even when individual rows are already `published`.
A failed article save or folder move retries using existing IDs, without re-uploading.
Uncertain uploads must go through the existing reconciliation process before another try.

The dashboard overview shows a read-only card per channel: banked long/Short counts,
remaining days at the bundle release rate, and unreleased banked bytes. Shared account
usage has its measurement timestamp; it is a cached quota reading, not a live Drive call.
Released files still occupy Drive space and are excluded from banked counts.

## Recovery and concurrency

Run only one inventory generator per channel. Banking workflow concurrency handles channel
production; do not run a competing local bank production for the same channel.
`stockpile_lock_drive_upload` serializes bundle storage and
`stockpile_lock_release_<channel>` serializes releases, including local/manual invocations.
A killed runner leaves its settings lock intentionally fail-closed. **After confirming no
matching runner/process remains active**, the owner can remove just that lock row from
settings and retry. Do not remove a live worker's lock.

If production finished but banking failed, download its retained workflow artifact and
restore it into `out/<content-id>/`. With the channel's existing content rows intact, the
owner can complete storage without repeating models or rendering:

```bash
.venv/bin/python -c 'from pipeline.db import DB; from pipeline.common import Channel; from pipeline.stockpile import bank_bundle; bank_bundle(DB(), "<content-id>", Channel("futurework"))'
```

The saved `bank-article.json` avoids another article call. If it is absent, article generation
is still necessary. Missing/failed Shorts must be repaired through the existing recovery
process first; no incomplete bundle can be banked. Never overwrite a completed stockpile
checkpoint; release it using `pipeline.release_banked`.

Implementation references: [Drive resumable uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads),
[Drive checksum metadata](https://developers.google.com/workspace/drive/api/reference/rest/v3/files),
[quota reads with drive.file](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get).
