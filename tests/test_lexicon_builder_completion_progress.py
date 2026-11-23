"""Progress reports committed decisions without opening another database scan."""

import json
import sqlite3
import sys

import pytest
from test_lexicon_builder_completion_sessions import Transport, dictionary

from gse.curation.lexicon_builder.completion import complete_dictionary


def test_progress_follows_commit_and_preserves_unknown_abstentions(tmp_path):
    path = dictionary(tmp_path, 2)
    events = []

    def progress(event):
        events.append(event)
        if event.get("code"):
            with sqlite3.connect(path) as conn:
                count = conn.execute("SELECT count(*) FROM completion_attempts WHERE code!='RUNNING'").fetchone()[0]
            assert count == sum(event["committed_outcomes"].values())

    transport = Transport(lambda payload: 1 if payload["entry_id"] == "entry:0" else None)
    report = complete_dictionary(path, transport, 2, banks=("GOOD",), progress=progress)
    assert events[0]["phase"] == "PREFLIGHT"
    committed = [event for event in events if event.get("code")]
    assert [event["code"] for event in committed] == ["ASSIGNED", "ABSTAINED"]
    assert committed[-1]["model_calls"] == 2
    assert all(event["dictionary_status"] == "NOT_RECOUNTED" for event in events)
    assert report["dictionary_cells"]["unresolved"] == 1


def test_progress_option_rejects_noncallable_before_database_access(tmp_path):
    with pytest.raises(ValueError, match="INVALID_COMPLETION_OPTIONS"):
        complete_dictionary(tmp_path / "absent.db", Transport(), 1, progress=True)


def test_cli_progress_is_json_on_stderr_and_summary_stays_on_stdout(tmp_path, monkeypatch, capsys):
    from gse.curation.cli import commands
    from gse.curation.lexicon_builder import residual

    path = dictionary(tmp_path, 1)
    monkeypatch.setattr(residual, "OllamaTransport", lambda *args, **kwargs: Transport())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gse",
            "--lexicon-db",
            str(path),
            "complete",
            "--priority",
            "constraint",
            "--model",
            "fixture",
            "--max-model-calls",
            "1",
            "--bank",
            "GOOD",
            "--progress",
        ],
    )
    commands.main()
    output = capsys.readouterr()
    assert json.loads(output.out)["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    events = [json.loads(line) for line in output.err.splitlines()]
    assert events[-1]["code"] == "ASSIGNED"
    assert events[-1]["committed_outcomes"] == {"ASSIGNED": 1}
