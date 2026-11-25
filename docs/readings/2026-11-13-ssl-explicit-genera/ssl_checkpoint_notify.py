"""Notify locally about this run's delivery; never publish or infer acceptance."""

import fcntl
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]


def read(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None  # An in-progress receipt write is not a terminal outcome.


def notify(message):
    result = subprocess.run(
        ["osascript", "-e", "on run argv\ndisplay notification (item 1 of argv) with title \"GSE lexicon checkpoint\" sound name \"Glass\"\nend run", message],
        capture_output=True, text=True, timeout=20,
    )
    return {"exit_code": result.returncode, "stderr": result.stderr}


def main():
    status = NOTES / "ssl-checkpoint-notification-status.json"
    with (NOTES / "ssl-checkpoint-notification.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        enabled = notify("Completion watcher enabled. The checkpoint is not ready yet; you will receive a success or stopped-run notification.")
        status.write_text(json.dumps({"state": "WATCHING", "notification_request": enabled}))
        deadline = time.monotonic() + 21600
        while time.monotonic() < deadline:
            delivery = read(NOTES / "ssl-api-checkpoint-delivery.json")
            active = read(ROOT / "data/lexicon_active.json")
            supervisor = read(NOTES / "ssl-responses-supervisor-status.json")
            outcome = None
            if delivery and delivery.get("code") == "CHECKPOINT_PUBLISHED_VALIDATED":
                if delivery.get("active_pointer") == active and active:
                    outcome = ("CHECKPOINT_READY", "Ready: the validated lexicon checkpoint is active in GSE. Delivery details are in ssl-api-checkpoint-delivery.json.")
                else:
                    outcome = ("DELIVERY_POINTER_MISMATCH", "Checkpoint needs attention: delivery receipt and active lexicon disagree. Do not treat it as ready.")
            elif supervisor and supervisor.get("state") == "WORKER_REFUSED":
                outcome = ("RUN_STOPPED", "The lexicon run stopped before verified activation. The checkpoint is not ready; see the supervisor status report.")
            elif supervisor and supervisor.get("state") == "CONTINUING_AUTHORIZED_CHECKPOINT":
                stamp = datetime.fromisoformat(supervisor["at_utc"])
                if (datetime.now(timezone.utc) - stamp).total_seconds() > 300:
                    outcome = ("SUPERVISION_STALE", "Checkpoint supervision has stopped updating. Activation is unverified and needs attention.")
            if outcome:
                code, message = outcome
                result = notify(message)
                status.write_text(json.dumps({"state": code, "at_utc": datetime.now(timezone.utc).isoformat(), "notification_request": result}, indent=2))
                return
            time.sleep(15)
        result = notify("The checkpoint watcher reached its time limit without verified delivery. The checkpoint is not confirmed ready.")
        status.write_text(json.dumps({"state": "WATCH_TIMEOUT", "notification_request": result}))


if __name__ == "__main__":
    main()
