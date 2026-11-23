"""Real SQLite reader locks preserve journal state and yield named failure receipts."""

import json
import sqlite3
import sys

import pytest

from gse.curation.lexicon_builder import completion
from gse.curation.lexicon_builder.completion import CompletionDatabaseBusy, complete_dictionary
from gse.curation.lexicon_builder.engine import DomainRestriction
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.validation import validate_build


def dictionary(tmp_path, count=1):
    definitions, observations, restrictions = [], [], []
    for index in range(count):
        entry = f"entry:{index}"
        record = f"record:{index}"
        definitions.append(Definition(entry, entry, "verb", "explicit synthetic locking fixture"))
        observations.append(Observation(entry, "fixture", record, "fixture", {}, "lexical"))
        restrictions.extend(
            DomainRestriction(bank, (-1, 1) if bank == "GOOD" else (0,), "fixture", record, "fixture") for bank in BANKS
        )
    path = tmp_path / "locked.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions)), path)
    return path


def states(path):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT * FROM definition_states ORDER BY entry_id").fetchall()


class ReaderLockTransport:
    identity = "locked-fixture:pinned"

    def __init__(self, path, connect, hold_at="entry:0"):
        self.path, self.connect, self.hold_at = path, connect, hold_at
        self.readers = []
        self.calls = 0

    def pin(self):
        return {"model": self.identity, "digest": "a" * 64}

    def __call__(self, payload, schema):
        self.calls += 1
        if payload["entry_id"] == self.hold_at:
            reader = self.connect(self.path)
            reader.execute("BEGIN")
            reader.execute("SELECT * FROM definition_states").fetchone()
            self.readers.append(reader)
        return json.dumps({payload["bank"]: 1})

    def close(self):
        for reader in self.readers:
            reader.close()
        self.readers.clear()


def short_wait(monkeypatch):
    connect = sqlite3.connect

    def limited(*args, **kwargs):
        kwargs.setdefault("timeout", 0.05)
        return connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", limited)
    return connect


@pytest.mark.parametrize("sustained", [False, True])
def test_reader_blocks_acceptance_without_losing_running_receipt_then_explicit_retry(tmp_path, monkeypatch, sustained):
    path = dictionary(tmp_path)
    before = states(path)
    transport = ReaderLockTransport(path, short_wait(monkeypatch))
    try:
        with monkeypatch.context() as refusing_cleanup:
            refusing_cleanup.setattr(
                completion, "_refresh_coverage", lambda conn: pytest.fail("busy cleanup attempted another write")
            )
            with pytest.raises(CompletionDatabaseBusy) as caught:
                complete_dictionary(path, transport, 1, banks=("GOOD",), continue_cohorts=sustained)
        receipt = caught.value.receipt
        assert receipt["code"] == "COMPLETION_DATABASE_BUSY"
        assert receipt["phase"] == "ACCEPTANCE_COMMIT"
        assert receipt["model_calls"] == transport.calls == 1
        assert receipt["committed_outcomes"] == {}
        assert states(path) == before
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT code FROM completion_attempts").fetchone()[0] == "RUNNING"
            assert conn.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0] == 0
    finally:
        transport.close()
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    resumed = ReaderLockTransport(path, sqlite3.connect, hold_at="never")
    skipped = complete_dictionary(path, resumed, 1, banks=("GOOD",), continue_cohorts=sustained)
    assert resumed.calls == 0
    assert skipped["skipped_attempts"] == {"RUNNING": 1}
    assert states(path) == before
    retried = complete_dictionary(path, resumed, 1, banks=("GOOD",), continue_cohorts=sustained, retry=True)
    assert retried["outcomes"] == {"ASSIGNED": 1}
    assert resumed.calls == 1
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("sustained", [False, True])
def test_real_cli_writes_failure_receipt_and_exits_nonzero(tmp_path, monkeypatch, capsys, sustained):
    from gse.curation.cli import commands
    from gse.curation.lexicon_builder import residual

    path = dictionary(tmp_path)
    before = states(path)
    report = tmp_path / "failure.json"
    transport = ReaderLockTransport(path, short_wait(monkeypatch))
    monkeypatch.setattr(residual, "OllamaTransport", lambda *args, **kwargs: transport)
    arguments = [
        "gse",
        "--lexicon-db",
        str(path),
        "complete",
        "--priority",
        "constraint",
        "--model",
        transport.identity,
        "--max-model-calls",
        "1",
        "--bank",
        "GOOD",
        "--report",
        str(report),
    ]
    if sustained:
        arguments.append("--continue-cohorts")
    monkeypatch.setattr(sys, "argv", arguments)
    try:
        with pytest.raises(SystemExit) as caught:
            commands.main()
        assert caught.value.code == 1
        result = json.loads(capsys.readouterr().out)
        assert result == json.loads(report.read_text())
        assert result["phase"] == "ACCEPTANCE_COMMIT"
        assert result["model_calls"] == 1
        assert result["continue_cohorts"] is sustained
        assert result["pending_attempts"] == "COMMITTED_RUNNING_JOURNAL_IS_AUTHORITATIVE"
        assert states(path) == before
    finally:
        transport.close()


def test_busy_receipt_counts_only_already_committed_prefix(tmp_path, monkeypatch):
    path = dictionary(tmp_path, 2)
    transport = ReaderLockTransport(path, short_wait(monkeypatch), hold_at="entry:1")
    try:
        with pytest.raises(CompletionDatabaseBusy) as caught:
            complete_dictionary(path, transport, 2, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True)
        assert caught.value.receipt["committed_outcomes"] == {"ASSIGNED": 1}
        assert caught.value.receipt["model_calls"] == 2
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT entry_id,code FROM completion_attempts ORDER BY entry_id").fetchall() == [
                ("entry:0", "ASSIGNED"),
                ("entry:1", "RUNNING"),
            ]
    finally:
        transport.close()
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_other_sqlite_errors_are_not_mislabeled_busy(tmp_path, monkeypatch):
    path = dictionary(tmp_path)

    def failed(*args, **kwargs):
        raise sqlite3.OperationalError("unrelated fixture failure")

    monkeypatch.setattr(completion, "store_entry", failed)
    transport = ReaderLockTransport(path, sqlite3.connect, hold_at="never")
    with pytest.raises(sqlite3.OperationalError, match="unrelated fixture failure"):
        complete_dictionary(path, transport, 1, banks=("GOOD",))
