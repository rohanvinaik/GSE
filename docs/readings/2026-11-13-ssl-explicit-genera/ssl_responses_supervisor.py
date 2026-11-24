"""Continue the authorized API workers from recorded outcomes until delivery.

This is the current job's local process supervisor, not a scheduled automation.
It does not infer semantic success, replay tools, handle credentials or publish.
The existing production publication and workload gates remain authoritative.
"""

import fcntl
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOTES = Path(__file__).resolve().parent
OWNED = "/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/owned-run"
ROLES = ("controller", "runtime")


def read(path):
    """Read a complete structured receipt; absent is explicitly unavailable."""
    return json.loads(path.read_text()) if path.exists() else None


def redirect(role, status):
    """Resume only exact completed responses whose tool outcomes are all saved."""
    response_file = NOTES / f"ssl-responses-{role}-{status['turns']:03d}-response.json"
    response = read(response_file)
    if not response or response.get("id") != status.get("response_id"):
        raise RuntimeError("RESPONSE_IDENTITY_UNAVAILABLE")
    if response.get("status") != "completed":
        raise RuntimeError("RESPONSE_INCOMPLETE_DO_NOT_RETRY")
    for item in response.get("output", []):
        if item.get("type") == "function_call":
            outcome = NOTES / f"ssl-responses-{role}-{status['turns']:03d}-{item['call_id']}-output.json"
            if not outcome.is_file():
                raise RuntimeError("TOOL_OUTCOME_UNRECORDED_DO_NOT_REPEAT")
    (NOTES / f"ssl-responses-{role}-redirect.json").write_text(
        json.dumps({"response_id": response["id"], "last_response_file": str(response_file)}, indent=2)
    )
    steering_file = NOTES / f"ssl-responses-{role}-steering.json"
    steering = read(steering_file)
    steering.pop("budget_launcher_handoff", None)
    steering["budgeted_continuation"] = {
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "instruction": (
            "Technical launcher handoff completed. Continue the owner-authorized checkpoint task now, "
            "under the shared budget guard. Read the recovery contract in the existing formal design. "
            "Do not stop again for a launcher handoff or wait for root approval. Fix the actual critical "
            "failure, preserve all semantic/replay/workload gates, and complete your consumer receipt. "
            "Coordinate via the existing A/B receipts; never repeat a completed model/service question."
        ),
    }
    steering_file.write_text(json.dumps(steering, ensure_ascii=False, indent=2) + "\n")


def main():
    processes = {}
    launches = dict.fromkeys(ROLES, 0)
    started = time.monotonic()
    state_file = NOTES / "ssl-responses-supervisor-status.json"
    with (NOTES / "ssl-responses-supervisor.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while time.monotonic() - started < 21600:
            delivery = read(NOTES / "ssl-api-checkpoint-delivery.json")
            active = read(ROOT / "data/lexicon_active.json")
            if delivery and delivery.get("code") == "CHECKPOINT_PUBLISHED_VALIDATED":
                if delivery.get("active_pointer") != active:
                    raise RuntimeError("DELIVERY_ACTIVE_POINTER_MISMATCH")
                state_file.write_text(json.dumps({"state": "DELIVERY_RECORDED", "receipt": delivery}, indent=2))
                return 0
            states = {}
            for role in ROLES:
                status = read(NOTES / f"ssl-responses-{role}-status.json")
                if not status:
                    raise RuntimeError("WORKER_STATUS_UNAVAILABLE")
                states[role] = {key: status.get(key) for key in ("state", "turns", "response_id")}
                if role in processes and processes[role].poll() is None:
                    continue
                if status["state"] in {"RUNNING", "STARTING", "RESUMING_FOR_USER_CHECKPOINT_PRIORITY"}:
                    # Legacy process predates this supervisor: await its explicit safe handoff.
                    continue
                if status["state"] not in {"FINISHED", "API_TURN_BUDGET_REACHED", "WALL_BUDGET_REACHED"}:
                    state_file.write_text(
                        json.dumps({"state": "WORKER_REFUSED", "role": role, "worker": status}, indent=2)
                    )
                    return 2
                complete = read(NOTES / f"ssl-api-{role}-checkpoint-complete.json")
                if complete and complete.get("code") == "ROLE_CHECKPOINT_COMPLETE":
                    continue
                if launches[role] >= 6:
                    raise RuntimeError("SUPERVISOR_RESUME_LIMIT_REACHED")
                redirect(role, status)
                launches[role] += 1
                logfile = NOTES / f"ssl-responses-{role}-budgeted-{launches[role]:02d}.log"
                with logfile.open("a") as stream:
                    logfile.chmod(0o600)
                    processes[role] = subprocess.Popen(
                        [
                            OWNED,
                            "--label",
                            f"gse-ssl-{role}-budgeted",
                            "--timeout",
                            "14430",
                            "--",
                            str(ROOT / ".venv/bin/python"),
                            str(NOTES / "ssl_responses_worker.py"),
                            role,
                            "--resume",
                        ],
                        cwd=ROOT,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                    )
            state_file.write_text(
                json.dumps(
                    {
                        "state": "CONTINUING_AUTHORIZED_CHECKPOINT",
                        "at_utc": datetime.now(timezone.utc).isoformat(),
                        "workers": states,
                        "launches": launches,
                        "budget": read(NOTES / "ssl-responses-continuation-cost.json"),
                        "finish_receipt": str(NOTES / "ssl-api-checkpoint-delivery.json"),
                    },
                    indent=2,
                )
            )
            time.sleep(15)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
