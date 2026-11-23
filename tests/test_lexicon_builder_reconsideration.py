"""Real writer/replay tests for conservative, atomic model reconsideration."""

import json
import os
import sqlite3
import sys
from dataclasses import asdict
from typing import Any

import pytest

from GSE.curation.lexicon_builder import reconsideration as reconsider_module
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import Assertion, DomainRestriction
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.reconsideration import TABLE, reconsider
from GSE.curation.lexicon_builder.storage import read_entries
from GSE.curation.lexicon_builder.validation import validate_build
from scripts.reconsider_lexicon_model import main


class Transport:
    model = "synthetic-reconsideration-fixture"

    def __init__(self, value=1):
        self.value = value

    def __call__(self, payload, _schema):
        return json.dumps({payload["bank"]: self.value})


def built(tmp_path):
    """Explicit synthetic labels test mechanics, not real-word semantics."""
    path = tmp_path / "fixture.db"
    definitions = tuple(Definition(entry, entry, "verb", "synthetic definition") for entry in ("a", "b"))
    observations = tuple(
        Observation(entry, "fixture", f"native:{entry}", "fixture", {}, "lexical") for entry in ("a", "b")
    )
    observations += (
        Observation(None, "fixture", "candidate:a", "fixture", {"retained": "whole context"}, "lexical", ("a",)),
    )
    assertions = (Assertion("DO", 1, "fixture", "native:a", "fixture"),)
    restrictions = []
    for entry in ("a", "b"):
        for bank in BANKS:
            if bank in {"WANT", "BE", "LIKE"}:
                continue
            # These are supplied synthetic source restrictions, never defaults.
            value = 1 if bank in {"DO", "INTENSITY"} else 0
            restrictions.append(DomainRestriction(bank, (value,), "fixture", f"native:{entry}", "fixture"))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "gse.lexicon-rules/1",
                "anchors": {"a": [asdict(Assertion("INTENSITY", 1, "anchor:fixture", "anchor:a", "fixture"))]},
                "hierarchy": {"a": {"INTENSITY": 2}},
            }
        )
    )
    build_dictionary(
        EvidenceBundle(definitions, observations, assertions, (), tuple(restrictions)), path, manifest=manifest
    )
    for entry, bank in (("a", "WANT"), ("a", "BE"), ("a", "LIKE"), ("b", "WANT")):
        result = complete_dictionary(path, Transport(), 1, entry_ids=(entry,), banks=(bank,))
        assert result["outcomes"] == {"ASSIGNED": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    return path


def receipts(path):
    with sqlite3.connect(path) as conn:
        return {key: value for key, value in read_model_receipts(conn).items()}


def query(path, sql, args=()):
    with sqlite3.connect(path) as conn:
        return conn.execute(sql, args).fetchall()


def entries(path):
    with sqlite3.connect(path) as conn:
        return read_entries(conn)


def withdraw(path, request_id, **kwargs):
    return reconsider(
        path, request_id, convention="fixture/BE-own-state/1", reason="Explicit source-scope correction", **kwargs
    )


def test_middle_suffix_withdrawal_preserves_other_authority_and_replays(tmp_path):
    path = built(tmp_path)
    before_receipts = receipts(path)
    root = before_receipts["a"][1]["request_id"]
    before_entries = entries(path)
    untouched = {
        table: query(path, f"SELECT * FROM {table}")
        for table in (
            "source_observations",
            "builder_domain_restrictions",
            "completion_attempts",
            "completion_schedule",
            "completion_visits",
        )
    }
    before_bytes = path.read_bytes()
    dry = withdraw(path, root)
    assert dry["code"] == "DRY_RUN"
    assert path.read_bytes() == before_bytes
    assert dry["root_ordinal"] == 1
    assert dry["withdrawn_banks"] == ["BE", "LIKE"]
    assert dry["retained_same_definition_model_receipts"] == 1
    assert dry["after_domains"]["BE"] == [-1, 0, 1]
    assert "BE" not in dry["after_assignments"]
    assert not query(path, "SELECT name FROM sqlite_master WHERE name=?", (TABLE,))
    report = withdraw(path, root, apply=True, expected_snapshot=dry["snapshot_sha256"])
    assert report["code"] == "RECONSIDERED"
    assert report["post_local_replay"] == "LOCAL_REPLAY_VALIDATED"
    assert report["after_coverage"]["cells"]["unresolved"] == report["before_coverage"]["cells"]["unresolved"] + 2
    assert report["after_coverage"]["cells"]["explicit_zero"] == report["before_coverage"]["cells"]["explicit_zero"]
    assert receipts(path) == {"a": before_receipts["a"][:1], "b": before_receipts["b"]}
    after_entries = entries(path)
    assert after_entries[1] == before_entries[1]
    assert after_entries[0]["hierarchy"] == {"INTENSITY": 2}
    assert after_entries[0]["assignments"]["DO"] == 1
    assert after_entries[0]["assignments"]["WANT"] == 1
    for table, rows in untouched.items():
        assert sorted(query(path, f"SELECT * FROM {table}"), key=repr) == sorted(rows, key=repr)
    archived = json.loads(query(path, f"SELECT payload FROM {TABLE}")[0][0])
    assert archived["archived_receipts"] == [
        {"original_ordinal": i, "receipt": before_receipts["a"][i]} for i in (1, 2)
    ]
    assert [row["original_ordinal"] for row in archived["removed_assertions"]] == [3, 4]
    assert archived["convention"] == report["convention"]
    assert archived["reason"] == report["reason"]
    assert all(isinstance(row["receipt"]["request"]["observations"], list) for row in archived["archived_receipts"])
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    with pytest.raises(ValueError, match="ROOT_NOT_ACCEPTED_MODEL_REQUEST"):
        withdraw(path, root, apply=True)


def test_withdrawing_first_receipt_removes_entire_model_suffix(tmp_path):
    path = built(tmp_path)
    original = receipts(path)
    report = withdraw(path, original["a"][0]["request_id"], apply=True)
    assert report["withdrawn_banks"] == ["WANT", "BE", "LIKE"]
    assert "a" not in receipts(path)
    assert receipts(path)["b"] == original["b"]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("phase", ["store_entry", "_local_replay", "_refresh_coverage"])
def test_failure_after_mutation_rolls_back_archive_receipts_and_entry(tmp_path, monkeypatch, phase):
    path = built(tmp_path)
    root = receipts(path)["a"][1]["request_id"]
    before = path.read_bytes()
    original = getattr(reconsider_module, phase)

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("forced transaction failure")

    monkeypatch.setattr(reconsider_module, phase, fail)
    with pytest.raises(RuntimeError, match="forced transaction failure"):
        withdraw(path, root, apply=True)
    assert path.read_bytes() == before
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_changed_preflight_snapshot_refused(tmp_path, monkeypatch):
    path = built(tmp_path)
    root = receipts(path)["a"][1]["request_id"]
    original = reconsider_module.validate_build

    def racing(file):
        result = original(file)
        with sqlite3.connect(file) as conn:
            conn.execute("INSERT INTO builder_metadata VALUES ('other-writer','1')")
        return result

    monkeypatch.setattr(reconsider_module, "validate_build", racing)
    with pytest.raises(ValueError, match="RECONSIDERATION_SNAPSHOT_CHANGED"):
        withdraw(path, root, apply=True)
    assert len(receipts(path)["a"]) == 3
    assert not query(path, "SELECT name FROM sqlite_master WHERE name=?", (TABLE,))


def test_expected_snapshot_refuses_new_valid_suffix(tmp_path):
    path = built(tmp_path)
    root = receipts(path)["a"][1]["request_id"]
    dry = withdraw(path, root)
    # Removing a later accepted ruling changes the root's dependency snapshot.
    withdraw(path, receipts(path)["a"][2]["request_id"], apply=True)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="RECONSIDERATION_SNAPSHOT_CHANGED"):
        withdraw(path, root, apply=True, expected_snapshot=dry["snapshot_sha256"])
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("request_id", None, "INVALID_RECONSIDERATION_REQUEST_ID"),
        ("request_id", "x", "INVALID_RECONSIDERATION_REQUEST_ID"),
        ("request_id", "A" * 64, "INVALID_RECONSIDERATION_REQUEST_ID"),
        ("convention", None, "INVALID_RECONSIDERATION_CONVENTION"),
        ("convention", " ", "INVALID_RECONSIDERATION_CONVENTION"),
        ("reason", [], "INVALID_RECONSIDERATION_REASON"),
        ("reason", "", "INVALID_RECONSIDERATION_REASON"),
        ("apply", 1, "INVALID_RECONSIDERATION_APPLY"),
        ("expected_snapshot", "invalid", "INVALID_RECONSIDERATION_SNAPSHOT"),
    ],
)
def test_strict_input_rejection_never_creates_database(tmp_path, field, value, code):
    path = tmp_path / "missing.db"
    args: dict[str, Any] = {"request_id": "a" * 64, "convention": "fixture/1", "reason": "correction", "apply": True}
    args[field] = value
    with pytest.raises(ValueError, match=code):
        reconsider(path, **args)
    assert not path.exists()


def test_null_and_native_roots_cannot_be_withdrawn(tmp_path):
    path = built(tmp_path)
    complete_dictionary(path, Transport(None), 1, entry_ids=("b",), banks=("BE",))
    null_request = query(path, "SELECT request_id FROM completion_attempts WHERE code='ABSTAINED'")[0][0]
    for request_id in (null_request, "0" * 64):
        before = path.read_bytes()
        with pytest.raises(ValueError, match="ROOT_NOT_ACCEPTED_MODEL_REQUEST"):
            withdraw(path, request_id, apply=True)
        assert path.read_bytes() == before


def test_corrupted_build_refuses_before_archive_write(tmp_path):
    path = built(tmp_path)
    root = receipts(path)["a"][1]["request_id"]
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE primitive_values SET value=-1 WHERE primitive='DO'")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="RECONSIDERATION_REQUIRES_VALIDATED_BUILD"):
        withdraw(path, root, apply=True)
    assert path.read_bytes() == before


def test_archive_is_append_only_and_index_mismatch_is_detected(tmp_path):
    path = built(tmp_path)
    original = receipts(path)
    withdraw(path, original["a"][2]["request_id"], apply=True)
    with sqlite3.connect(path) as conn:
        for command in (
            f"UPDATE {TABLE} SET reason='changed'",
            f"DELETE FROM {TABLE}",
            f"INSERT OR REPLACE INTO {TABLE} SELECT * FROM {TABLE}",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="ARCHIVE_APPEND_ONLY"):
                conn.execute(command)
        # Simulate offline tampering, not an allowed application operation.
        conn.execute("DROP TRIGGER reconsideration_no_update")
        conn.execute(f"UPDATE {TABLE} SET reason='forged-index'")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="ARCHIVE_INDEX_MISMATCH"):
        withdraw(path, original["a"][1]["request_id"], apply=True)
    assert path.read_bytes() == before


def test_real_cli_defaults_to_dry_run_and_requires_explicit_apply(tmp_path, monkeypatch, capsys):
    path = built(tmp_path)
    root = receipts(path)["a"][1]["request_id"]
    report_path = tmp_path / "report.json"
    argv = [
        "reconsider_lexicon_model",
        "--lexicon-db",
        str(path),
        "--request-id",
        root,
        "--convention",
        "fixture/1",
        "--reason",
        "scope correction",
        "--report",
        str(report_path),
    ]
    before = path.read_bytes()
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 0
    dry = json.loads(report_path.read_text())
    assert dry["code"] == "DRY_RUN"
    assert path.read_bytes() == before
    monkeypatch.setattr(sys, "argv", argv + ["--apply", "--expected-snapshot", dry["snapshot_sha256"]])
    assert main() == 0
    assert json.loads(report_path.read_text())["code"] == "RECONSIDERED"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    capsys.readouterr()


def test_cli_refuses_database_hardlink_report(tmp_path, monkeypatch):
    path = built(tmp_path)
    report = tmp_path / "report.json"
    os.link(path, report)
    before = path.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconsider",
            "--lexicon-db",
            str(path),
            "--request-id",
            receipts(path)["a"][1]["request_id"],
            "--convention",
            "fixture/1",
            "--reason",
            "correction",
            "--report",
            str(report),
            "--apply",
        ],
    )
    with pytest.raises(ValueError, match="REPORT_CANNOT_OVERWRITE_DATABASE"):
        main()
    assert path.read_bytes() == before
