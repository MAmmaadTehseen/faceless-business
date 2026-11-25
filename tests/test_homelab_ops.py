"""Tests for ops/homelab (opslib + scheduler): pure logic, fake GitHub, no network."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "homelab"))

import opslib, scheduler

ROOT = Path(__file__).resolve().parents[1]
UTC = opslib.UTC


def test_next_retry_ladder():
    failed_at = datetime(2026, 11, 24, 6, 15, tzinfo=UTC)
    for retries_used, hours in enumerate((1, 6, 12, 24)):
        assert opslib.next_retry_at(failed_at, retries_used) == failed_at + timedelta(hours=hours)
    assert opslib.next_retry_at(failed_at, 4) is None


def test_job_crons_appear_verbatim_in_workflows():
    for job in opslib.JOBS:
        text = (ROOT / ".github" / "workflows" / job.workflow).read_text()
        assert job.cron in text, f"{job.key}: cron {job.cron!r} missing from {job.workflow}"


def test_run_slot_reads_slot_from_display_title():
    run = {"id": 5, "event": "workflow_dispatch", "display_title": "sync slot sync@20261124T0615Z"}
    assert opslib.run_slot(run, "sync.yml") == "sync@20261124T0615Z"


def test_run_slot_maps_cron_run_to_matching_produce_job():
    # 2026-11-24T16:07:00Z: which produce job owns it is answered with opslib's own cron math.
    created = opslib.parse_time("2026-11-24T16:07:00Z")
    tradewinds_fire = opslib.latest_fire("0 11 * * 2,4,6", created)  # Tue/Thu/Sat 11:00
    assert tradewinds_fire == datetime(2026, 11, 24, 11, 0, tzinfo=UTC)  # so the day is a Tuesday
    run = {"id": 6, "event": "schedule", "created_at": "2026-11-24T16:07:00Z",
           "display_title": "Trade Winds Report"}
    slot = opslib.run_slot(run, "produce.yml")
    assert slot == opslib.slot_id("produce-tradewinds", tradewinds_fire)
    assert slot == "produce-tradewinds@20261124T1100Z"


def test_guard_should_skip():
    me = 10
    # earlier run still queued/running -> skip
    assert opslib.guard_should_skip(me, [{"id": 9, "status": "in_progress"}], lambda rid: [])[0] is True
    # later run in progress -> proceed
    assert opslib.guard_should_skip(me, [{"id": 11, "status": "in_progress"}], lambda rid: [])[0] is False
    # successful run whose jobs include a non-guard success -> skip
    done = {"id": 8, "status": "completed", "conclusion": "success"}
    jobs = lambda rid: [{"name": "guard", "conclusion": "success"},
                        {"name": "produce", "conclusion": "success"}]
    assert opslib.guard_should_skip(me, [done], jobs)[0] is True
    # success whose only successful job is the guard -> proceed (a guard skip is not work)
    guard_only = lambda rid: [{"name": "guard", "conclusion": "success"}]
    assert opslib.guard_should_skip(me, [done], guard_only)[0] is False
    # failed run -> proceed
    failed = {"id": 8, "status": "completed", "conclusion": "failure"}
    assert opslib.guard_should_skip(me, [failed], lambda rid: [])[0] is False


def test_scheduler_failed_dispatch_sets_one_hour_retry(tmp_path):
    slot_at = datetime(2026, 11, 24, 6, 15, tzinfo=UTC)  # a sync slot (fires */6 hours at :15)
    now = [slot_at + timedelta(seconds=5)]
    gh = scheduler.FakeGitHub(fail_dispatches=1)
    jarvis = scheduler.Jarvis(None, None, "r")
    s = scheduler.Scheduler(gh, jarvis, tmp_path / "state.json", clock=lambda: now[0])
    s.state["last_watch"] = scheduler.iso(now[0] + timedelta(days=1))  # keep the watchdog out

    failed_at = now[0]
    s.tick()  # sync slot due -> dispatch fails -> "failed" alert, retry 1/4 scheduled
    sid = opslib.slot_id("sync", slot_at)
    rec = s.state["slots"][sid]
    assert rec["next_retry"] == scheduler.iso(failed_at + timedelta(hours=1))
    assert len(jarvis.sent) == 1
    assert jarvis.sent[0]["content_id"].split("-")[3] == "failed"
    assert jarvis.sent[0]["attempt"] == "0/4"
    assert [c[0] for c in gh.calls] == ["dispatch"]

    now[0] = slot_at + timedelta(minutes=4)  # still before the retry hour
    s.tick()
    assert gh.calls == [("dispatch", "sync.yml", {"slot": sid})]  # nothing new dispatched
    assert len(jarvis.sent) == 1
    assert rec["next_retry"] == scheduler.iso(failed_at + timedelta(hours=1))
    assert (tmp_path / "state.json").exists()
