# Homelab dispatcher

GitHub's cron frequently skips or delays runs. The homelab laptop runs a small
Docker service (`ops/homelab/`) that dispatches every scheduled slot itself and
watches the runs; GitHub's own cron stays in place as a fallback.

## Slots

Each scheduled firing of a job is a slot id: `<job>@YYYYMMDDTHHMMZ`, e.g.
`sync@20261124T0615Z`. Dispatched runs carry the slot in their title
(`-f slot=<id>`); GitHub cron runs map to the latest fire of their own cron.
Both paths share the same slot id.

## Guard job rules

Every dispatched or cron run carries the slot, and a `guard` job inside the
workflow decides:

- a run exits early if an earlier-created run for the same slot is still
  queued or running, or if another run for the slot already did real work
  (a guard skip is not work);
- manual runs without a slot always proceed;
- a guard API error fails the run (fail closed).

## Retry ladder

Any failure (dispatch error, server offline at the slot, run failed or
cancelled, dispatched run never appeared) schedules a retry at 1 / 6 / 12 / 24
hours (`OPS_LADDER_SCALE` speeds this up in tests). Every failure and every
retry sends a Jarvis alert. After 4 retries the slot is left to the next
GitHub cron.

When a failed run exists the loop re-runs the failed job (`rerun-failed-jobs`);
otherwise it dispatches.

## Watchdog

Every 15 minutes the scheduler cancels runs past their limits:

| workflow | limit_min |
|---|---|
| produce.yml | 195 |
| words.yml | 165 |
| shorts.yml | 75 |
| sync.yml | 75 |
| engage.yml | 30 |
| optimize.yml | 35 |
| review.yml | 35 |
| recap.yml | 365 |
| bank.yml (watch-only) | 365 |
| retry.yml (watch-only) | 60 |

A run that ignores the cancel is force-cancelled after 10 more minutes.

## Jarvis limitation

Jarvis's webhook schema only accepts publication events, so ops alerts are
packed into `content_id` (job, slot, attempt, reason, run id). Follow-up: add
an `ops` kind in Jarvis so alerts get first-class fields.

## Deploy

```
rsync -a --exclude ops.env --exclude data ops/homelab/ homelab:~/faceless-ops/
ssh homelab 'cd ~/faceless-ops && docker compose up -d --build'
```

### Owner setup

1. Create a fine-grained token at
   https://github.com/settings/personal-access-tokens/new
   - Resource owner: MAmmaadTehseen
   - Only select repositories: faceless-business
   - Repository permissions: Actions — Read and write; Metadata — Read-only
   - Expiry: 1 year
2. `ssh homelab`
3. `cd ~/faceless-ops && cp ops.env.example ops.env && chmod 600 ops.env && nano ops.env`
4. Paste `GITHUB_TOKEN`, `JARVIS_WEBHOOK_URL`, `JARVIS_WEBHOOK_SECRET`
   (same values as the GitHub secrets).
5. `docker compose up -d --build`

No new `gh` secrets are needed.

## Tests

```
docker compose run --rm faceless-ops python scheduler.py selftest
docker compose run --rm faceless-ops python scheduler.py jarvis-test
docker compose run --rm faceless-ops python scheduler.py dispatch sync --dry-run
docker compose logs -f
```

Guard test — run twice; the second run's work job is skipped:

```
gh workflow run ops-guard-test.yml -f slot=guardtest@<YYYYMMDDTHHMMZ>
```

Unit tests: `pytest tests/test_homelab_ops.py`
