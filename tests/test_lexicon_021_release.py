"""The round finisher preserves unique audits and blocks out-of-scope releases."""

import gzip
import importlib
import json
import sqlite3

import pytest

finish = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.finish_vertebrate_021")


@pytest.fixture
def retirement(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    (tmp_path / "ssl-explicit-genera/retired-audit").mkdir(parents=True)
    source, witness, previous = (tmp_path / name for name in ("work.db", "active.db", "previous.db"))
    for path in (source, witness):
        with sqlite3.connect(path) as c:
            c.executescript("""
                CREATE TABLE source_observations(record_id TEXT PRIMARY KEY,entry_id TEXT,source TEXT,family TEXT,scope TEXT,payload TEXT);
                CREATE TABLE lexemes(id INTEGER PRIMARY KEY,lemma TEXT,pos TEXT,sense_id TEXT,gloss TEXT,source TEXT);
                CREATE TABLE definition_states(entry_id TEXT PRIMARY KEY,lexeme_id INTEGER);
                CREATE TABLE audit_receipts(id TEXT PRIMARY KEY,details TEXT);
            """)
    with sqlite3.connect(source) as c:
        c.execute("INSERT INTO audit_receipts VALUES (?,?)", ("only-in-work", "evidence"))
    previous.write_bytes(b"previous release")
    (notes / "021-approved-source-context.json").write_text(json.dumps({"observations": []}))
    monkeypatch.setattr(finish, "NOTES", notes)
    monkeypatch.setattr(finish, "DESTINATION", witness)
    monkeypatch.setattr(finish, "BASE", previous)
    monkeypatch.setattr(finish.round_.helpers, "no_open_handles", lambda _: None)
    return source, witness, previous, {"sha256": finish.fingerprint(witness)}


def test_retire_preserves_unique_audit_before_removing_work(retirement):
    source, witness, previous, release = retirement
    receipt = finish.retire(source, release)
    assert not source.exists() and witness.exists() and previous.read_bytes() == b"previous release"
    assert receipt["unique_audit_rows"] == {"audit_receipts": 1}
    with gzip.open(receipt["audit_archive"], "rt") as stream:
        archived = json.load(stream)
    assert archived["tables"]["audit_receipts"]["rows"] == [["only-in-work", "evidence"]]
    assert finish.retire(source, release) == receipt


@pytest.mark.parametrize("which", [1, 2])
def test_retire_never_removes_active_or_previous(retirement, which):
    path = retirement[which]
    before = path.read_bytes()
    with pytest.raises(ValueError, match="PROTECTS_ACTIVE_AND_ROLLBACK"):
        finish.retire(path, retirement[3])
    assert path.read_bytes() == before


def test_retire_refuses_unpreserved_source_records(retirement):
    source, witness, _, release = retirement
    with sqlite3.connect(witness) as c:
        c.execute("INSERT INTO source_observations VALUES ('extra','entry','source','family','lexical','{}')")
    release["sha256"] = finish.fingerprint(witness)
    with pytest.raises(ValueError, match="SOURCE_STREAM_MISMATCH"):
        finish.retire(source, release)
    assert source.exists()


def test_retire_refuses_a_busy_snapshot(retirement, monkeypatch):
    def busy(_):
        raise ValueError("STILL_IN_USE")

    monkeypatch.setattr(finish.round_.helpers, "no_open_handles", busy)
    with pytest.raises(ValueError, match="STILL_IN_USE"):
        finish.retire(retirement[0], retirement[3])
    assert retirement[0].exists()


def test_retire_closes_its_own_connections_before_checking_handles(retirement, monkeypatch):
    original = sqlite3.connect
    connections = []

    def track(*args, **kwargs):
        connection = original(*args, **kwargs)
        connections.append(connection)
        return connection

    def check_closed(_):
        assert len(connections) == 2
        for connection in connections:
            with pytest.raises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    monkeypatch.setattr(finish.sqlite3, "connect", track)
    monkeypatch.setattr(finish.round_.helpers, "no_open_handles", check_closed)
    finish.retire(retirement[0], retirement[3])


def test_release_gate_rejects_a_domain_change_outside_the_stage(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.db"
    candidate.write_bytes(b"candidate")
    (tmp_path / "021-approved-population-stage.json").write_text(
        json.dumps(
            {
                "changes": [
                    {"entry_id": "in-scope", "bank": "BODY", "before": [-1, 0, 1], "after": [1]},
                ]
            }
        )
    )
    monkeypatch.setattr(finish, "NOTES", tmp_path)
    monkeypatch.setattr(finish.round_, "verify_sources", lambda: None)
    monkeypatch.setattr(
        finish,
        "exact_delta",
        lambda *_: (
            401596,
            [
                {"entry_id": "out-of-scope", "bank": "BODY", "before": [-1, 0, 1], "after": [1]},
            ],
        ),
    )
    result = {
        "epochs": [{"code": "RULE_ADMITTED", "audit_outcomes": {"MODEL_AGREEMENT": 4}}],
        "typed_questions_used": 5,
        "reopened_cells": 0,
        "replay": {"code": "REPLAY_VALIDATED", "complete_search": True},
        "candidate": str(candidate),
        "candidate_sha256": finish.fingerprint(candidate),
        "new_cells": 1,
    }
    with pytest.raises(ValueError, match="DELTA_DIFFERS_FROM_FULL_STAGE"):
        finish.verify_candidate(result)
