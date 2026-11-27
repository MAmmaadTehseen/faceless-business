"""Pure logic shared by the homelab scheduler and the Actions slot guard (stdlib only).

A *slot* is one scheduled firing of one job, e.g. ``sync@20261124T0615Z``. The homelab
server dispatches each slot with ``-f slot=<id>``; GitHub's own cron is the fallback. Both
paths map their run to the same slot id, and the guard lets only one run per slot work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
# Retry ladder after a failure: 1 h, 6 h, 12 h, 24 h (four retries, then GitHub cron fallback).
LADDER_HOURS = (1, 6, 12, 24)
GUARD_JOB = "guard"


@dataclass(frozen=True)
class Job:
    key: str            # slot prefix, unique
    workflow: str       # workflow file name
    cron: str           # identical to the workflow's schedule entry
    limit_min: int      # watchdog: cancel a run in progress longer than this
    inputs: dict = field(default_factory=dict)


# Must match the `schedule:` entries in .github/workflows (tests check this).
JOBS = (
    Job("produce-futurework", "produce.yml", "0 6 * * 1,3,5", 195, {"channel": "futurework"}),
    Job("produce-tradewinds", "produce.yml", "0 11 * * 2,4,6", 195, {"channel": "tradewinds"}),
    Job("produce-escapevelocity", "produce.yml", "0 16 * * 1,4,0", 195, {"channel": "escapevelocity"}),
    Job("words", "words.yml", "30 3 * * *", 1440),
    Job("shorts", "shorts.yml", "30 9 * * *", 75),
    Job("sync", "sync.yml", "15 */6 * * *", 75),
    Job("engage", "engage.yml", "45 */6 * * *", 30),
    Job("optimize", "optimize.yml", "30 9 * * *", 35),
    Job("review", "review.yml", "0 10 * * 0", 35),
    Job("recap", "recap.yml", "20 */6 * * *", 365),
)
# Watched for stuck runs only; bank keeps its own gated cron + chain, retry is owner-dispatched.
WATCH_ONLY = {"bank.yml": 365, "retry.yml": 60}


def watch_limits() -> dict[str, int]:
    limits = dict(WATCH_ONLY)
    for job in JOBS:
        limits[job.workflow] = max(limits.get(job.workflow, 0), job.limit_min)
    return limits


# ---------- cron (minute hour * * dow, the subset our workflows use) ----------

def _field(spec: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = map(int, part.split("-"))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


def _parse(cron: str):
    minute, hour, dom, month, dow = cron.split()
    if dom != "*" or month != "*":
        raise ValueError(f"unsupported cron: {cron}")
    days = {d % 7 for d in _field(dow, 0, 7)}  # cron: 0/7 = Sunday
    return _field(minute, 0, 59), _field(hour, 0, 23), days


def _matches(parsed, t: datetime) -> bool:
    minutes, hours, days = parsed
    return t.minute in minutes and t.hour in hours and (t.isoweekday() % 7) in days


def fires_between(cron: str, start: datetime, end: datetime) -> list[datetime]:
    """Fire times in (start, end]."""
    parsed = _parse(cron)
    t = start.astimezone(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    while t <= end:
        if _matches(parsed, t):
            out.append(t)
        t += timedelta(minutes=1)
    return out


def latest_fire(cron: str, at: datetime, lookback_days: int = 8) -> datetime | None:
    fires = fires_between(cron, at - timedelta(days=lookback_days), at)
    return fires[-1] if fires else None


def slot_id(job_key: str, when: datetime) -> str:
    return f"{job_key}@{when.astimezone(UTC):%Y%m%dT%H%MZ}"


def slot_time(slot: str) -> datetime:
    return datetime.strptime(slot.split("@", 1)[1], "%Y%m%dT%H%MZ").replace(tzinfo=UTC)


def jobs_for(workflow: str) -> list[Job]:
    return [j for j in JOBS if j.workflow == workflow]


# ---------- mapping GitHub runs to slots ----------

SLOT_IN_TITLE = re.compile(r"\bslot ([a-z0-9-]+@\d{8}T\d{4}Z)\b")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_slot(run: dict, workflow: str, schedule: str | None = None) -> str | None:
    """Slot a run belongs to: dispatched runs carry it in the title; cron runs map to
    the latest fire at or before their creation (of their own cron when known)."""
    m = SLOT_IN_TITLE.search(run.get("display_title") or "")
    if m:
        return m.group(1)
    if run.get("event") != "schedule":
        return None  # manual/dashboard dispatches are not slots
    created = parse_time(run["created_at"])
    best = None
    for job in jobs_for(workflow):
        if schedule and job.cron != schedule:
            continue
        fire = latest_fire(job.cron, created)
        if fire and (best is None or fire > best[1]):
            best = (job.key, fire)
    return slot_id(*best) if best else None


def runs_for_slot(runs: list[dict], workflow: str, slot: str) -> list[dict]:
    return [r for r in runs if run_slot(r, workflow) == slot]


def worked(run: dict, jobs: list[dict] | None) -> bool:
    """A successful run counts only if a non-guard job succeeded (a guard skip is not work)."""
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return False
    if jobs is None:
        return True
    return any(j.get("name") != GUARD_JOB and not j.get("name", "").startswith(GUARD_JOB + " ")
               and j.get("conclusion") == "success" for j in jobs)


def guard_should_skip(me_id: int, others: list[dict], jobs_of) -> tuple[bool, str]:
    """Run `me_id` exits early if another run of the same slot already did the work, or an
    earlier-created run (lower id) is still queued/running. Failed/cancelled runs don't block."""
    for run in sorted(others, key=lambda r: r["id"]):
        if run["id"] == me_id:
            continue
        if run.get("status") != "completed":
            if run["id"] < me_id:
                return True, f"earlier run {run['id']} for this slot is {run.get('status')}"
        elif run.get("conclusion") == "success" and worked(run, jobs_of(run["id"])):
            return True, f"run {run['id']} already succeeded for this slot"
    return False, "no other run owns this slot"


# ---------- slot status + retry ladder (used by the scheduler) ----------

DONE, RUNNING, FAILED, NONE = "done", "running", "failed", "none"


def slot_status(runs: list[dict], jobs_of) -> tuple[str, dict | None]:
    if not runs:
        return NONE, None
    ordered = sorted(runs, key=lambda r: r["id"])
    for run in ordered:
        if run.get("conclusion") == "success" and worked(run, jobs_of(run["id"])):
            return DONE, run
    active = [r for r in ordered if r.get("status") != "completed"]
    if active:
        return RUNNING, active[-1]
    real = [r for r in ordered if r.get("conclusion") != "success"]  # success here = guard skip
    return (FAILED, real[-1]) if real else (NONE, None)


def next_retry_at(failed_at: datetime, retries_used: int, scale: float = 1.0) -> datetime | None:
    """When retry number retries_used+1 is due, or None once all four were used."""
    if retries_used >= len(LADDER_HOURS):
        return None
    return failed_at + timedelta(hours=LADDER_HOURS[retries_used] * scale)
