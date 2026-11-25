"""Homelab scheduler + watchdog for the faceless GitHub Actions workflows.

    python scheduler.py run                 # forever (the Docker service)
    python scheduler.py dispatch <job> [--dry-run]
    python scheduler.py selftest            # forced-failure retry ladder with a fake GitHub
    python scheduler.py jarvis-test         # one signed test alert
    python scheduler.py status              # open slots from the state file

Env (server env file, chmod 600): GITHUB_TOKEN, GITHUB_REPO, JARVIS_WEBHOOK_URL,
JARVIS_WEBHOOK_SECRET, OPS_STATE (default /data/state.json), OPS_DRY_RUN, OPS_LADDER_SCALE
(1 = real hours; 0.0167 makes 1 h one minute), OPS_TICK_SECONDS (default 60).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github import GitHub, GitHubError  # noqa: E402
import opslib  # noqa: E402
from opslib import DONE, FAILED, NONE, RUNNING, UTC  # noqa: E402

GRACE = timedelta(minutes=20)          # a slot first seen later than this was missed (server offline)
APPEAR = timedelta(minutes=10)         # a dispatched run must show up within this
WATCH_EVERY = timedelta(minutes=15)
MAX_CATCHUP = timedelta(hours=48)
CLOSE_AFTER = timedelta(days=4)


def log(msg: str) -> None:
    print(f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ} {msg}", flush=True)


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Jarvis:
    """Same signature as pipeline/publish/jarvis.py. Jarvis's webhook schema only takes
    publication events, so the alert is packed into content_id (job, slot, attempt, reason,
    run id); extra fields are ignored by today's Jarvis and kept for a future ops kind."""

    def __init__(self, url: str | None, secret: str | None, repo: str, post=None):
        self.url, self._secret, self.repo = url, secret, repo
        self.post = post or self._post
        self.sent: list[dict] = []

    def alert(self, job: opslib.Job | None, kind: str, attempt: str, reason: str,
              run: dict | None = None, slot: str | None = None) -> None:
        run_url = run.get("html_url") if run else None
        stamp = slot.split("@")[1].lower() if slot else ""
        parts = ["ops", job.key if job else "watchdog", stamp, kind, f"a{attempt.replace('/', 'of')}",
                 slug(reason)[:60], f"r{run['id']}" if run else ""]
        payload = {
            "id": time.time_ns() // 1000, "content_id": "-".join(p for p in parts if p)[:180].strip("-"),
            "channel": (job.inputs.get("channel") if job else None) or "futurework",
            "platform": "youtube", "status": "failed",
            "kind": "ops", "job": job.key if job else None, "slot": slot, "attempt": attempt,
            "reason": reason[:300], "run_url": run_url,
        }
        self.sent.append(payload)
        log(f"ALERT {kind} job={payload['job']} slot={slot} attempt={attempt} reason={reason} run={run_url}")
        if self.url and self._secret:
            self.post(payload)

    def _post(self, payload: dict) -> bool:
        import urllib.request
        body = json.dumps(payload, separators=(",", ":")).encode()
        ts = str(int(time.time()))
        sig = hmac.new(self._secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "X-Faceless-Timestamp": ts, "X-Faceless-Signature": sig})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                log(f"jarvis: HTTP {resp.status}")
                return 200 <= resp.status < 300
        except Exception as e:  # never log bodies: they can echo secrets
            log(f"jarvis: delivery failed ({type(e).__name__} {getattr(e, 'code', '')})")
            return False


class Scheduler:
    def __init__(self, gh, jarvis: Jarvis, state_path: Path, dry_run=False, scale=1.0, clock=None):
        self.gh, self.jarvis, self.path = gh, jarvis, state_path
        self.dry_run, self.scale = dry_run, scale
        self.clock = clock or (lambda: datetime.now(UTC))
        self.state = self._load()

    # ---- state ----
    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {"slots": {}, "cancelled": {}}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, sort_keys=True))
        tmp.replace(self.path)

    # ---- GitHub writes (respect dry run) ----
    def _write(self, what: str, fn, *args) -> None:
        if self.dry_run:
            log(f"DRY RUN: would {what}")
            return
        fn(*args)
        log(what)

    def dispatch(self, job: opslib.Job, slot: str) -> None:
        inputs = {**job.inputs, "slot": slot}
        self._write(f"dispatch {job.workflow} {json.dumps(inputs)}", self.gh.dispatch, job.workflow, inputs)

    # ---- main tick ----
    def tick(self) -> None:
        now = self.clock()
        last = self.state.get("last_tick")
        start = max(opslib.parse_time(last), now - MAX_CATCHUP) if last else now - timedelta(minutes=1)
        for job in opslib.JOBS:
            for fire in opslib.fires_between(job.cron, start, now):
                sid = opslib.slot_id(job.key, fire)
                self.state["slots"].setdefault(sid, {
                    "job": job.key, "retries": 0, "failures": [], "next_retry": None,
                    "dispatched_at": None, "retried_at": None, "missed": now - fire > GRACE})
        self.state["last_tick"] = iso(now)
        runs_cache: dict[str, list[dict]] = {}
        for sid, rec in sorted(self.state["slots"].items()):
            if rec.get("closed"):
                continue
            try:
                self._evaluate(sid, rec, now, runs_cache)
            except GitHubError as e:
                log(f"{sid}: GitHub read failed ({e}); will retry next tick")
        last_watch = self.state.get("last_watch")
        if not last_watch or now - opslib.parse_time(last_watch) >= WATCH_EVERY:
            try:
                self.watchdog(now)
                self.state["last_watch"] = iso(now)
            except GitHubError as e:
                log(f"watchdog: GitHub read failed ({e})")
        self._prune(now)
        self.save()

    def _runs(self, workflow: str, since: datetime, cache: dict) -> list[dict]:
        if workflow not in cache:
            cache[workflow] = self.gh.runs(workflow, iso(since))
        return cache[workflow]

    def _evaluate(self, sid: str, rec: dict, now: datetime, cache: dict) -> None:
        job = next(j for j in opslib.JOBS if j.key == rec["job"])
        fire = opslib.slot_time(sid)
        if now - fire > CLOSE_AFTER:
            rec["closed"] = "expired"
            return
        siblings = {j.key for j in opslib.jobs_for(job.workflow)}
        earliest = min(opslib.slot_time(s) for s, r in self.state["slots"].items()
                       if not r.get("closed") and r["job"] in siblings)
        runs = opslib.runs_for_slot(self._runs(job.workflow, earliest - timedelta(minutes=5), cache),
                                    job.workflow, sid)
        status, run = opslib.slot_status(runs, self.gh.jobs)
        if status == DONE:
            rec["closed"] = "done"
            log(f"{sid}: done by run {run['id']} (retries used {rec['retries']})")
            return
        if status == RUNNING:
            return
        if rec["next_retry"]:
            if now >= opslib.parse_time(rec["next_retry"]):
                self._retry(job, sid, rec, run, now)
            return
        if status == FAILED:
            key = f"{run['id']}:{run.get('run_attempt', 1)}"
            if key not in rec["failures"]:
                rec["retried_at"] = None
                self._failure(job, sid, rec, f"run concluded {run.get('conclusion')}", run, now, key)
            elif rec["retried_at"] and now - opslib.parse_time(rec["retried_at"]) > APPEAR:
                self._failure(job, sid, rec, "rerun never started", run, now, key + ":stale")
            return
        # NONE: nothing has run for this slot yet
        if rec["dispatched_at"]:
            if now - opslib.parse_time(rec["dispatched_at"]) > APPEAR:
                rec["dispatched_at"] = None
                self._failure(job, sid, rec, "dispatched run never appeared", None, now)
            return
        if rec.get("missed") and rec["retries"] == 0 and not rec["failures"]:
            self._failure(job, sid, rec, "server offline at slot", None, fire, "offline")
            if rec.get("next_retry") and now >= opslib.parse_time(rec["next_retry"]):
                self._retry(job, sid, rec, None, now)
            return
        try:
            self.dispatch(job, sid)
            rec["dispatched_at"] = iso(now)
        except GitHubError as e:
            self._failure(job, sid, rec, f"dispatch failed: {e}", None, now)

    def _failure(self, job, sid, rec, reason, run, at, key=None) -> None:
        rec["failures"].append(key or f"{reason}@{iso(at)}")
        nxt = opslib.next_retry_at(at, rec["retries"], self.scale)
        attempt = f"{rec['retries']}/4"
        if nxt is None:
            rec["closed"] = "exhausted"
            self.jarvis.alert(job, "exhausted", attempt,
                              f"{reason}; all 4 retries failed, GitHub cron fallback next slot", run, sid)
            return
        rec["next_retry"] = iso(nxt)
        self.jarvis.alert(job, "failed", attempt, f"{reason}; retry {rec['retries'] + 1}/4 at {iso(nxt)}", run, sid)

    def _retry(self, job, sid, rec, run, now) -> None:
        rec["retries"] += 1
        rec["next_retry"] = None
        n = f"{rec['retries']}/4"
        can_rerun = run is not None and run.get("status") == "completed" and run.get("conclusion") != "success"
        self.jarvis.alert(job, "retry", n, "rerunning failed jobs" if can_rerun else "dispatching", run, sid)
        try:
            if can_rerun:
                self._write(f"rerun failed jobs of run {run['id']}", self.gh.rerun_failed, run["id"])
                rec["retried_at"] = iso(now)
            else:
                self.dispatch(job, sid)
                rec["dispatched_at"] = iso(now)
        except GitHubError as e:
            self._failure(job, sid, rec, f"retry {n} failed: {e}", run, now)

    # ---- watchdog ----
    def watchdog(self, now: datetime) -> None:
        cancelled = self.state.setdefault("cancelled", {})
        for workflow, limit in opslib.watch_limits().items():
            for status in ("in_progress", "queued"):
                for run in self.gh.runs(workflow, status=status):
                    started = opslib.parse_time(run.get("run_started_at") or run["created_at"])
                    age = (now - started).total_seconds() / 60
                    if age <= limit:
                        continue
                    rid = str(run["id"])
                    force = rid in cancelled and now - opslib.parse_time(cancelled[rid]) > timedelta(minutes=10)
                    if rid in cancelled and not force:
                        continue
                    sid = opslib.run_slot(run, workflow)
                    job = next((j for j in opslib.JOBS if sid and j.key == sid.split("@")[0]), None)
                    reason = f"{workflow} {status} {int(age)} min > {limit} min limit; {'force-' if force else ''}cancelled"
                    try:
                        self._write(f"{'force-' if force else ''}cancel run {rid}", self.gh.cancel, run["id"], force)
                    except GitHubError as e:
                        reason += f" (cancel error: {e})"
                    cancelled[rid] = iso(now)
                    self.jarvis.alert(job, "stuck", "-", reason, run, sid)

    def _prune(self, now: datetime) -> None:
        for sid in [s for s, r in self.state["slots"].items()
                    if r.get("closed") and now - opslib.slot_time(s) > timedelta(days=14)]:
            del self.state["slots"][sid]
        cancelled = self.state.get("cancelled", {})
        for rid in [r for r, t in cancelled.items() if now - opslib.parse_time(t) > timedelta(days=3)]:
            del cancelled[rid]


# ---------- fake GitHub for selftest and unit tests ----------

class FakeGitHub:
    def __init__(self, fail_dispatches: int = 0):
        self.fail_dispatches, self.calls, self._runs, self._jobs, self._next = fail_dispatches, [], {}, {}, 1000

    def add_run(self, workflow, **run) -> dict:
        self._next += 1
        run = {"id": self._next, "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
               "run_attempt": 1, "created_at": "2026-01-01T00:00:00Z", "display_title": workflow,
               "html_url": f"https://github.com/x/y/actions/runs/{self._next}", **run}
        self._runs.setdefault(workflow, []).append(run)
        self._jobs[run["id"]] = [{"name": "guard", "conclusion": "success"},
                                 {"name": "work", "conclusion": run["conclusion"]}]
        return run

    def runs(self, workflow, since_iso=None, status=None):
        return [r for r in self._runs.get(workflow, []) if not status or r["status"] == status]

    def jobs(self, run_id):
        return self._jobs.get(run_id, [])

    def dispatch(self, workflow, inputs, ref="main"):
        self.calls.append(("dispatch", workflow, inputs))
        if self.fail_dispatches:
            self.fail_dispatches -= 1
            raise GitHubError(f"POST /actions/workflows/{workflow}/dispatches: HTTP 500")

    def rerun_failed(self, run_id):
        self.calls.append(("rerun", run_id))

    def cancel(self, run_id, force=False):
        self.calls.append(("cancel", run_id, force))


def selftest(jarvis: Jarvis, state_dir: Path) -> bool:
    """Forced failure: dispatch fails at the slot, retry 1/4 fires after the (scaled) 1 h."""
    scale = 1 / 60  # 1 h -> 1 min, whatever the service uses
    slot_at = datetime(2026, 11, 24, 6, 15, tzinfo=UTC)
    now = [slot_at - timedelta(seconds=30)]
    gh = FakeGitHub(fail_dispatches=1)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "selftest-state.json"
    path.unlink(missing_ok=True)
    s = Scheduler(gh, jarvis, path, scale=scale, clock=lambda: now[0])
    s.state["last_watch"] = iso(now[0] + timedelta(days=1))  # no watchdog in the selftest
    s.tick()
    now[0] = slot_at + timedelta(seconds=5)
    s.tick()  # sync slot due -> dispatch fails -> failure alert, retry 1/4 scheduled
    sid = opslib.slot_id("sync", slot_at)
    rec = s.state["slots"][sid]
    due = opslib.parse_time(rec["next_retry"])
    log(f"selftest: retry 1/4 scheduled {int((due - now[0]).total_seconds())} s after the failure")
    now[0] = due + timedelta(seconds=1)
    s.tick()  # retry 1/4 dispatches
    gh.add_run("sync.yml", display_title=f"sync slot {sid}", conclusion="success")
    now[0] += timedelta(minutes=1)
    s.tick()  # run succeeded -> slot done
    ok = (rec["retries"] == 1 and rec.get("closed") == "done"
          and [c[0] for c in gh.calls] == ["dispatch", "dispatch"]
          and [a["content_id"].split("-")[3] for a in jarvis.sent] == ["failed", "retry"])
    path.unlink(missing_ok=True)
    log(f"selftest: {'PASS' if ok else 'FAIL'} calls={gh.calls} alerts={[a['content_id'] for a in jarvis.sent]}")
    return ok


def build(dry_run: bool) -> Scheduler:
    repo = os.getenv("GITHUB_REPO", "MAmmaadTehseen/faceless-business")
    token = os.getenv("GITHUB_TOKEN")
    if not token and not dry_run:
        raise SystemExit("GITHUB_TOKEN missing (see docs/homelab.md); refusing to run without --dry-run")
    jarvis = Jarvis(os.getenv("JARVIS_WEBHOOK_URL"), os.getenv("JARVIS_WEBHOOK_SECRET"), repo)
    state = Path(os.getenv("OPS_STATE", "/data/state.json"))
    state.parent.mkdir(parents=True, exist_ok=True)
    return Scheduler(GitHub(repo, token or ""), jarvis, state, dry_run=dry_run,
                     scale=float(os.getenv("OPS_LADDER_SCALE") or 1))


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "run"
    dry = "--dry-run" in argv or os.getenv("OPS_DRY_RUN") == "1"
    if cmd == "selftest":
        repo = os.getenv("GITHUB_REPO", "MAmmaadTehseen/faceless-business")
        jarvis = Jarvis(os.getenv("JARVIS_WEBHOOK_URL"), os.getenv("JARVIS_WEBHOOK_SECRET"), repo)
        return 0 if selftest(jarvis, Path(os.getenv("OPS_STATE", "/data/state.json")).parent) else 1
    if cmd == "jarvis-test":
        url, secret = os.getenv("JARVIS_WEBHOOK_URL"), os.getenv("JARVIS_WEBHOOK_SECRET")
        if not url or not secret:
            print("JARVIS_WEBHOOK_URL / JARVIS_WEBHOOK_SECRET not set in the env file")
            return 2
        jarvis = Jarvis(url, secret, "")
        results = []
        jarvis.post = lambda p: results.append(Jarvis._post(jarvis, p))
        jarvis.alert(None, "test", "0/4", "homelab ops test alert")
        return 0 if results and results[0] else 1
    s = build(dry)
    if cmd == "dispatch":
        job = next(j for j in opslib.JOBS if j.key == argv[1])
        now = datetime.now(UTC)
        s.dispatch(job, opslib.slot_id(job.key, opslib.latest_fire(job.cron, now)))
        return 0
    if cmd == "status":
        for sid, rec in sorted(s.state["slots"].items()):
            print(sid, rec.get("closed") or "open", f"retries={rec['retries']}", rec.get("next_retry") or "")
        return 0
    if cmd == "run":
        tick = int(os.getenv("OPS_TICK_SECONDS") or 60)
        log(f"scheduler up: {len(opslib.JOBS)} jobs, dry_run={dry}, ladder_scale={s.scale}, tick={tick}s")
        while True:
            try:
                s.tick()
            except Exception as e:  # keep the service alive; details stay in the log
                log(f"tick error: {type(e).__name__}: {e}")
            time.sleep(tick)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
