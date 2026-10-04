"""`kill` stops the continuous multi-model audit the way Ctrl+C does.

`scripts/multi_model_audit.py --continuous` runs under `nohup … &` and is stopped with `kill`. SIGTERM's default
action ends the process without running `finally` blocks or exit hooks, so the auditor's database stayed open and
the Ollama models it used stayed loaded for the server's keep-alive window. The script now routes SIGTERM into
the Ctrl+C path; this drives the real `run_continuous_audit` in a child process (the HTTP layer and the auditor
stubbed), kills it during its sleep, and checks that it closed the auditor and unloaded its model.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CHILD = r"""
import sys
from unittest import mock

sys.path.insert(0, "scripts")


def fake_post(url, json=None, timeout=None):
    if json and "keep_alive" in json:
        print("UNLOAD", json["model"], json["keep_alive"], flush=True)
    return mock.Mock(status_code=200, json=lambda: {"response": "YES"})


mock.patch("requests.post", side_effect=fake_post).start()

import multi_model_audit as audit


class StubAuditor:
    def __init__(self, db_path, models):
        self.issues, self.models = [], models

    def run_audit(self, limit=None, start_rank=1):
        audit.query_model(self.models[0], "hi")  # a successful call registers the model

    def generate_report(self, path):
        with open(path, "w") as fh:
            fh.write("report")

    def close(self):
        print("CLOSED", flush=True)


audit.MultiModelAuditor = StubAuditor
audit.run_continuous_audit(db_path="unused.db", output_dir=sys.argv[1], models=["stub:1b"], sleep_between_passes=60)
"""


def test_sigterm_closes_the_auditor_and_unloads_its_models(tmp_path):
    child = subprocess.Popen(
        [sys.executable, "-c", CHILD, str(tmp_path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 30
    while not (tmp_path / "pass_0001.md").exists():  # the first pass's report is written before the sleep
        assert child.poll() is None, child.communicate()
        assert time.monotonic() < deadline, "the first pass never finished"
        time.sleep(0.05)
    child.send_signal(signal.SIGTERM)
    out, err = child.communicate(timeout=30)
    assert child.returncode == 0, err
    assert "CLOSED" in out.splitlines()
    assert "UNLOAD stub:1b 0" in out.splitlines()
