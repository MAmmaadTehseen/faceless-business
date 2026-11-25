"""Actions guard: let only one run per scheduled slot do the work.

Runs as the `guard` job of each scheduled workflow and writes proceed=true|false to
$GITHUB_OUTPUT. A run without a slot (manual or dashboard dispatch) always proceeds.
GitHub API errors fail the job (the homelab ladder retries it) rather than risk a duplicate.
Env: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_EVENT_NAME, WORKFLOW_FILE,
SLOT_INPUT (inputs.slot), SCHEDULE (github.event.schedule).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github import GitHub  # noqa: E402
import opslib  # noqa: E402


def decide(gh, workflow: str, run_id: int, event: str, slot_input: str, schedule: str) -> tuple[bool, str, str | None]:
    me = {"id": run_id, "event": event, "display_title": f"slot {slot_input}" if slot_input else "",
          "created_at": datetime.now(opslib.UTC).isoformat()}
    slot = slot_input or (opslib.run_slot(me, workflow, schedule or None) if event == "schedule" else None)
    if not slot:
        return True, "not a scheduled slot", None
    since = opslib.slot_time(slot) - timedelta(minutes=5)
    others = opslib.runs_for_slot(gh.runs(workflow, since.strftime("%Y-%m-%dT%H:%M:%SZ")), workflow, slot)
    skip, why = opslib.guard_should_skip(run_id, others, gh.jobs)
    return not skip, why, slot


def main() -> int:
    gh = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    proceed, why, slot = decide(gh, os.environ["WORKFLOW_FILE"], int(os.environ["GITHUB_RUN_ID"]),
                                os.environ.get("GITHUB_EVENT_NAME", ""), os.environ.get("SLOT_INPUT", ""),
                                os.environ.get("SCHEDULE", ""))
    print(f"slot={slot} proceed={proceed}: {why}")
    if not proceed:
        print(f"::notice::Exiting early: {why}")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as out:
        out.write(f"proceed={'true' if proceed else 'false'}\nslot={slot or ''}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
