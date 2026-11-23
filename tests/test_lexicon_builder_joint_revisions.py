"""Joint migrations preserve local witnesses and refuse interacting contradictions."""

import json
import sqlite3

import pytest
from test_lexicon_builder_source_guard_migration import (
    AUDIT,
    DISCOVERY,
    HOMOGRAPH,
    UNIT,
    SyntheticTransport,
    source_guard_packet,
    states,
)

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.residual import _request_id
from gse.curation.lexicon_builder.reviewed_export import export_reviewed_input
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from gse.curation.lexicon_builder.rule_admission import admit_records, admit_rule
from gse.curation.lexicon_builder.rule_history import digest
from gse.curation.lexicon_builder.rule_migration import migrate_revision
from gse.curation.lexicon_builder.rule_revisions import FORMAT, exception_source
from gse.curation.lexicon_builder.validation import validate_build

REVIEW = {
    "review_id": "fixture-review",
    "reviewer": "fixture",
    "rationale": "Synthetic witness for migration behavior.",
    "source_refs": ["synthetic:joint-revision"],
}


def _revision(version, *, admissions=(), retirements=(), exceptions=()):
    return {
        "format": FORMAT,
        "baseline_version": version,
        "admissions": list(admissions),
        "retirements": list(retirements),
        "exceptions": list(exceptions),
    }


def test_in_scope_exception_retains_opposition_and_retirement_reopens_only_derived_cells(tmp_path):
    source, input_path, audit_path, review = source_guard_packet(tmp_path)
    raw = json.loads(input_path.read_text())
    raw["guarded_candidates"][0]["warrant"]["required_exception_ids"] = [UNIT]
    audit = run_workflow_input(raw, SyntheticTransport(0), max_calls=1)
    [candidate] = audit["candidates"]
    review = {**review, "rule_id": candidate["relation"]["rule_id"], "warrant_sha256": candidate["warrant_sha256"]}
    admission = admit_records(raw, audit, review)
    with pytest.raises(ValueError, match="REQUIRED_REVISION_EXCEPTION_MISSING"):
        migrate_revision(
            source, tmp_path / "missing-exception.db", _revision(admission["baseline_version"], admissions=[admission])
        )
    with sqlite3.connect(source) as conn:
        source_hash = digest(exception_source(conn, UNIT))
        receipts = read_model_receipts(conn)[UNIT]
    exception = {
        **REVIEW,
        "rule_id": review["rule_id"],
        "entry_id": UNIT,
        "source_sha256": source_hash,
        "counterexample": {"WANT": 1},
    }
    revised = tmp_path / "revised.db"
    result = migrate_revision(
        source, revised, _revision(admission["baseline_version"], admissions=[admission], exceptions=[exception])
    )
    assert result["postflight"]["code"] == "REPLAY_VALIDATED"
    assert result["reviewed_exceptions"][0]["after_domains"] == {"WANT": [1]}
    assert states(revised)[AUDIT]["domains"]["WANT"] == [0]
    assert states(revised)[HOMOGRAPH]["domains"]["WANT"] == [1]
    with sqlite3.connect(revised) as conn:
        assert read_model_receipts(conn)[UNIT] == receipts
        relations = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
    compiled = next(rule for rule in relations if rule["rule_id"] == review["rule_id"])
    retired = tmp_path / "retired.db"
    result = migrate_revision(
        revised,
        retired,
        _revision(
            result["to_version"],
            retirements=[
                {
                    **REVIEW,
                    "rule_id": compiled["rule_id"],
                    "rule_sha256": digest(compiled),
                }
            ],
        ),
    )
    assert result["to_version"] == admission["baseline_version"]
    assert result["postflight"]["complete_search"]
    assert states(retired)[AUDIT]["domains"]["WANT"] == [-1, 0, 1]
    assert states(retired)[DISCOVERY]["domains"]["WANT"] == [-1, 0, 1]
    assert states(retired)[UNIT]["domains"]["WANT"] == [1]
    assert validate_build(retired)["code"] == "REPLAY_VALIDATED"


def test_joint_conflict_refuses_atomic_output_even_with_two_passing_audits(tmp_path):
    source, input_path, audit_path, review = source_guard_packet(tmp_path)
    first = admit_rule(input_path, audit_path, review)
    with sqlite3.connect(source) as conn:
        receipt = read_model_receipts(conn)[UNIT][0]
    proposal = json.loads(input_path.read_text())["guarded_candidates"][0]
    proposal["consequent"] = ["WANT", 1]
    raw = export_reviewed_input(
        source,
        {
            "format": "gse.reviewed-pattern-selection/1",
            "discovery_entry_ids": [UNIT],
            "audit_entry_ids": [AUDIT],
            "reviews": [
                {
                    "request_id": receipt["request_id"],
                    "review": {
                        **REVIEW,
                        "code": "ACCEPTED",
                        "receipt_sha256": _request_id(receipt),
                    },
                }
            ],
            "guarded_candidates": [proposal],
        },
    )["input"]
    audit = run_workflow_input(raw, SyntheticTransport(1), max_calls=1)
    [candidate] = audit["candidates"]
    second = admit_records(
        raw,
        audit,
        {
            **review,
            "rule_id": candidate["relation"]["rule_id"],
            "warrant_sha256": candidate["warrant_sha256"],
        },
    )
    output = tmp_path / "conflicted.db"
    with pytest.raises(ValueError, match="MIGRATION_RULE_SCOPE_COUNTEREXAMPLE"):
        migrate_revision(source, output, _revision(first["baseline_version"], admissions=[first, second]))
    assert not output.exists()
    assert validate_build(source)["code"] == "REPLAY_VALIDATED"


def test_local_exception_requires_current_opposing_witness(tmp_path):
    source, input_path, audit_path, review = source_guard_packet(tmp_path)
    admission = admit_rule(input_path, audit_path, review)
    with sqlite3.connect(source) as conn:
        source_hash = digest(exception_source(conn, UNIT))
    valid = {
        **REVIEW,
        "rule_id": review["rule_id"],
        "entry_id": UNIT,
        "source_sha256": source_hash,
        "counterexample": {"WANT": 1},
    }
    for exception, error in (
        ({**valid, "source_sha256": "stale"}, "REVISION_EXCEPTION_SOURCE_CHANGED"),
        ({**valid, "counterexample": {"WANT": 0}}, "REVISION_EXCEPTION_DOES_NOT_OPPOSE_RULE"),
        ({**valid, "counterexample": {"WANT": False}}, "INVALID_REVISION_COUNTEREXAMPLE"),
    ):
        with pytest.raises(ValueError, match=error):
            migrate_revision(
                source,
                tmp_path / "invalid.db",
                _revision(
                    admission["baseline_version"],
                    admissions=[admission],
                    exceptions=[exception],
                ),
            )
    assert not (tmp_path / "invalid.db").exists()


def test_reviewed_exception_reopens_bad_model_cell_and_retains_earlier_receipts(tmp_path):
    source, input_path, _, review = source_guard_packet(tmp_path)
    for entry in (UNIT, DISCOVERY):
        report = complete_dictionary(source, SyntheticTransport(0), 1, entry_ids=(entry,), banks=("BODY",))
        assert report["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(source) as conn:
        receipts = read_model_receipts(conn)
        witness = digest(exception_source(conn, UNIT))
    good = receipts[DISCOVERY][-1]
    bad = receipts[UNIT][-1]
    proposal = json.loads(input_path.read_text())["guarded_candidates"][0]
    proposal["consequent"] = ["BODY", 0]
    raw = export_reviewed_input(
        source,
        {
            "format": "gse.reviewed-pattern-selection/1",
            "discovery_entry_ids": [DISCOVERY],
            "audit_entry_ids": [AUDIT],
            "reviews": [
                {
                    "request_id": good["request_id"],
                    "review": {
                        **REVIEW,
                        "code": "ACCEPTED",
                        "receipt_sha256": _request_id(good),
                    },
                }
            ],
            "guarded_candidates": [proposal],
        },
    )["input"]
    audit = run_workflow_input(raw, SyntheticTransport(0), max_calls=1)
    [candidate] = audit["candidates"]
    admission = admit_records(
        raw,
        audit,
        {
            **review,
            "rule_id": candidate["relation"]["rule_id"],
            "warrant_sha256": candidate["warrant_sha256"],
        },
    )
    exception = {
        **REVIEW,
        "rule_id": candidate["relation"]["rule_id"],
        "entry_id": UNIT,
        "source_sha256": witness,
        "counterexample": {"BODY": 1},
        "withdraw_model_receipt_sha256": digest(bad),
    }
    output = tmp_path / "reopened.db"
    result = migrate_revision(
        source, output, _revision(admission["baseline_version"], admissions=[admission], exceptions=[exception])
    )
    assert result["postflight"]["complete_search"]
    assert result["reviewed_exceptions"][0]["reviewed_model_withdrawals"] == [bad["request_id"]]
    assert states(output)[UNIT]["domains"]["BODY"] == [-1, 0, 1]
    assert states(output)[UNIT]["domains"]["WANT"] == [1]
    assert states(output)[UNIT]["domains"]["BE"] == [0]
    with sqlite3.connect(output) as conn:
        assert read_model_receipts(conn)[UNIT] == receipts[UNIT][:-1]
