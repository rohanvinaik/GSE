"""Scope-gate mechanism fixtures; model answers here are not semantic gold."""

import json
import sqlite3

import pytest

from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.evidence import EvidenceBundle, _closed_class_definitions
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.publication import publication_readiness
from GSE.curation.lexicon_builder.reconsideration import reconsider
from GSE.curation.lexicon_builder.validation import validate_build


class PositiveFixtureTransport:
    model = "scope-gate-fixture"

    def __call__(self, payload, schema):
        return json.dumps({payload["bank"]: 1})


@pytest.fixture
def historical_candidate(tmp_path, monkeypatch):
    """Create an accepted historical ruling before the current scope check."""
    from GSE.curation.lexicon_builder import scope_admission

    definitions, observations, assertions = _closed_class_definitions(GSEClosedClassParser())
    entry_id = "gse_closed_class:pronoun:you"
    other_id = "gse_closed_class:modal:can"
    native = tuple(row for row in observations.values() if row.entry_id in {entry_id, other_id})
    record_ids = {row.record_id for row in native}
    bundle = EvidenceBundle(
        (definitions[entry_id], definitions[other_id]),
        native,
        tuple(row for row in assertions if row.record_id in record_ids),
        (),
    )
    path = tmp_path / "candidate.db"
    build_dictionary(bundle, path)
    with monkeypatch.context() as patch:
        patch.setattr(scope_admission, "model_scope_admission", lambda *args: {"code": "NOT_APPLICABLE"})
        completed = complete_dictionary(path, PositiveFixtureTransport(), 2, banks=("BE",))
    assert completed["model_calls"] == 2
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    return path, entry_id


def test_incomplete_historical_reference_ruling_blocks_current_publication(historical_candidate):
    path, entry_id = historical_candidate
    report = publication_readiness(path)
    assert "INCOMPLETE_DEFINITIONS" in report["blockers"]
    assert "MODEL_SCOPE_UNJUSTIFIED" in report["blockers"]
    audit = report["model_scope_audit"]
    assert audit["code"] == "SCOPE_UNJUSTIFIED"
    assert audit["outcomes"] == {"NOT_APPLICABLE": 1, "SCOPE_UNJUSTIFIED": 1}
    assert audit["not_applicable_is_semantic_approval"] is False
    reference = next(row for row in audit["records"] if row["entry_id"] == entry_id)
    assert reference["admission"]["reason"] == "ENTITY_REFERENCE_ALONE_DOES_NOT_JUSTIFY_POSITIVE_BE"
    assert reference["admission"]["exact_native_record_ids"]
    assert reference["bank"] == "BE" and reference["value"] == 1
    assert report["replay"]["code"] == "NOT_RUN_INCOMPLETE_CANDIDATE"


def test_archived_rulings_are_excluded_and_unrelated_active_ruling_remains(historical_candidate):
    path, entry_id = historical_candidate
    with sqlite3.connect(path) as conn:
        request_id = conn.execute(
            "SELECT request_id FROM accepted_model_receipts WHERE entry_id=?", (entry_id,)
        ).fetchone()[0]
    reconsider(path, request_id, convention="fixture scope review", reason="fixture reference-only scope", apply=True)
    report = publication_readiness(path)
    assert "MODEL_SCOPE_UNJUSTIFIED" not in report["blockers"]
    assert "INCOMPLETE_DEFINITIONS" in report["blockers"]
    audit = report["model_scope_audit"]
    assert audit["code"] == "NO_SCOPE_REJECTION"
    assert audit["scope"] == "ACTIVE_MODEL_RECEIPTS_ONLY"
    assert [row["entry_id"] for row in audit["records"]] == ["gse_closed_class:modal:can"]
    assert audit["records"][0]["admission"]["code"] == "NOT_APPLICABLE"
    assert audit["records"][0]["admission"]["reason"] == "NOT_NATIVE_PRONOUN_REFERENCE_ROLE"
    assert audit["not_applicable_is_semantic_approval"] is False
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_reconsideration_archive").fetchone()[0] == 1


def test_malformed_active_receipt_names_scope_audit_failure(historical_candidate):
    path, _ = historical_candidate
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE accepted_model_receipts SET payload='{}'")
    report = publication_readiness(path)
    assert "MODEL_SCOPE_AUDIT_INVALID_RECEIPT" in report["blockers"]
    assert report["model_scope_audit"]["code"] == "INVALID_MODEL_RECEIPT"
    assert report["model_scope_audit"]["reason"] == "INVALID_MODEL_RECEIPT_STORED_REQUEST"


def test_actual_cli_reports_scope_block_even_when_incomplete(historical_candidate, monkeypatch, capsys):
    from GSE.curation.cli.commands import main

    path, _ = historical_candidate
    monkeypatch.setattr("sys.argv", ["lexicon", "--lexicon-db", str(path), "publish"])
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 2
    report = json.loads(capsys.readouterr().out)
    assert "MODEL_SCOPE_UNJUSTIFIED" in report["blockers"]
    assert len(report["model_scope_audit"]["records"]) == 2
