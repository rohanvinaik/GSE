"""Real export/audit/admission/migration boundary; synthetic semantics only."""

import json
import sqlite3

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.residual import _request_id
from GSE.curation.lexicon_builder.reviewed_export import export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow
from GSE.curation.lexicon_builder.rule_admission import admit_rule
from GSE.curation.lexicon_builder.rule_migration import migrate_rule
from GSE.curation.lexicon_builder.storage import read_entries
from GSE.curation.lexicon_builder.validation import validate_build
from scripts.migrate_lexicon_rule import main


class Transport:
    identity = "synthetic-rule-migration-test"

    def __init__(self, value=1):
        self.value = value

    def __call__(self, payload, schema):
        return json.dumps({payload["bank"]: self.value})


def packet(tmp_path):
    path = tmp_path / "source.db"
    definitions = tuple(
        Definition(x, x, "noun" if x == "b" else "verb", "synthetic test definition") for x in ("a", "b", "c", "d", "h")
    )
    observations = tuple(
        Observation(d.entry_id, "wordnet_hierarchy", d.entry_id, "taxonomy", {}, "lexical") for d in definitions
    )
    native = (Assertion("ALIVE", 0, "wordnet_hierarchy", "a", "taxonomy"),)
    build_dictionary(EvidenceBundle(definitions, observations, native, ()), path)
    for entry, bank, value in (("a", "WANT", -1), ("a", "BE", 0), ("b", "WANT", 0), ("d", "WANT", 1)):
        report = complete_dictionary(path, Transport(value), 1, entry_ids=(entry,), banks=(bank,))
        assert report["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(path) as conn:
        receipt = read_model_receipts(conn)["d"][0]
    selection = {
        "format": "gse.reviewed-pattern-selection/1",
        "discovery_entry_ids": ["d"],
        "audit_entry_ids": ["h"],
        "reviews": [
            {
                "request_id": receipt["request_id"],
                "review": {
                    "review_id": "synthetic-review",
                    "reviewer": "test-fixture",
                    "code": "ACCEPTED",
                    "receipt_sha256": _request_id(receipt),
                    "source_refs": ["synthetic:test-only"],
                    "rationale": "Fixture authority, not linguistic gold.",
                },
            }
        ],
        "guarded_candidates": [
            {
                "antecedent": None,
                "consequent": ["WANT", 1],
                "guards": [["pos", "verb"]],
                "absent_evidence": [],
                "warrant": {
                    "warrant_id": "synthetic-law",
                    "kind": "DEFINITIONAL_DERIVATION",
                    "source_refs": ["synthetic:test-only"],
                    "statement": "Synthetic fixture only.",
                    "review_id": "fixture-law-review",
                    "reviewer": "test-fixture",
                },
            }
        ],
    }
    exported = export_reviewed_input(path, selection)
    input_path, audit_path = tmp_path / "input.json", tmp_path / "audit.json"
    input_path.write_text(json.dumps(exported["input"]))
    audit = run_workflow(input_path, Transport(), max_calls=1)
    audit_path.write_text(json.dumps(audit))
    candidate = audit["candidates"][0]
    review = {
        "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "synthetic-admission",
        "reviewer": "test-fixture",
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "rationale": "Synthetic migration fixture, not a real word rule.",
        "source_refs": ["synthetic:test-only"],
    }
    return path, input_path, audit_path, review


def entries(path):
    with sqlite3.connect(path) as conn:
        return {row["entry_id"]: row for row in read_entries(conn)}


def test_real_cli_migration_archives_affected_chain_preserves_unaffected_and_unknown(tmp_path, monkeypatch):
    path, input_path, audit_path, review = packet(tmp_path)
    output, report_path, review_path = (tmp_path / name for name in ("migrated.db", "report.json", "review.json"))
    review_path.write_text(json.dumps(review))
    before = path.read_bytes()
    monkeypatch.setattr(
        "sys.argv",
        [
            "migrate",
            "--candidate",
            str(path),
            "--output",
            str(output),
            "--input",
            str(input_path),
            "--audit",
            str(audit_path),
            "--review",
            str(review_path),
            "--report",
            str(report_path),
        ],
    )
    assert main() == 0
    result = json.loads(report_path.read_text())
    assert result["archived_model_receipts"] == 3
    assert result["retained_model_receipts"] == 1
    assert result["postflight"]["code"] == "REPLAY_VALIDATED"
    assert result["active_pointer_changed"] is False
    assert path.read_bytes() == before
    states = entries(output)
    assert states["a"]["assignments"]["WANT"] == 1
    assert states["a"]["assignments"]["ALIVE"] == 0
    assert states["a"]["domains"]["BE"] == [-1, 0, 1]
    assert states["a"]["domains"]["FEEL"] == [-1, 0, 1]
    assert states["b"]["assignments"]["WANT"] == 0
    with sqlite3.connect(output) as conn:
        assert set(read_model_receipts(conn)) == {"b"}
        event = json.loads(conn.execute("SELECT payload FROM rule_migrations").fetchone()[0])
        assert [a["assertion"]["bank"] for a in event["archived"][0]["receipts"]] == ["WANT", "BE"]
        for table in ("rule_versions", "model_rule_versions", "rule_migrations"):
            with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
                conn.execute(f"DELETE FROM {table}")
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"
    complete_dictionary(output, Transport(0), 1, entry_ids=("a",), banks=("BE",))
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("target", ["audit", "review", "input"])
def test_tampered_admission_never_creates_output(tmp_path, target):
    path, input_path, audit_path, review = packet(tmp_path)
    if target == "review":
        review["warrant_sha256"] = "0" * 64
    else:
        file = audit_path if target == "audit" else input_path
        raw = json.loads(file.read_text())
        if target == "audit":
            raw["candidates"][0]["audits"][0]["raw_output"] = '{"WANT":0}'
        else:
            raw["entries"][0]["definition"]["definition"] = "tampered source"
        file.write_text(json.dumps(raw))
    output = tmp_path / "failed.db"
    before = path.read_bytes()
    with pytest.raises(ValueError):
        migrate_rule(path, output, input_path, audit_path, review)
    assert path.read_bytes() == before
    assert not output.exists()


def test_unreviewed_or_abstained_audit_cannot_be_admitted(tmp_path):
    _, input_path, audit_path, review = packet(tmp_path)
    audit_path.write_text(json.dumps(run_workflow(input_path, Transport(None), max_calls=1)))
    with pytest.raises(ValueError, match="AUDIT_INCOMPLETE"):
        admit_rule(input_path, audit_path, review)


def test_corpus_counterexample_refuses_entire_migration(tmp_path):
    path, input_path, audit_path, review = packet(tmp_path)
    # New hard source evidence outside discovery/audit defeats the synthetic law.
    with sqlite3.connect(path) as conn:
        from GSE.curation.lexicon_builder.completion import _entry
        from GSE.curation.lexicon_builder.foundation import BANKS, definition_context
        from GSE.curation.lexicon_builder.resolution import resolve_dictionary
        from GSE.curation.lexicon_builder.storage import store_entry
        from GSE.curation.lexicon_builder.validation import _metadata, _relations

        definition, assertions, restrictions, hierarchy = _entry(conn, "c")
        assertions = assertions + (Assertion("WANT", -1, "wordnet_hierarchy", "c", "taxonomy"),)
        resolved = resolve_dictionary(
            BANKS,
            assertions,
            _relations(_metadata(conn, "relations")),
            definition_context("verb"),
            evidence_banks=BANKS,
        )
        store_entry(conn, definition, resolved, assertions, hierarchy, domain_restrictions=restrictions)
    preflight = validate_build(path)
    assert preflight["code"] == "REPLAY_VALIDATED", preflight["mismatches"]
    output = tmp_path / "failed.db"
    with pytest.raises(ValueError, match="SCOPE_COUNTEREXAMPLE"):
        migrate_rule(path, output, input_path, audit_path, review)
    assert not output.exists()
    assert not list(tmp_path.glob(".gse-migration-*"))


def test_existing_destination_and_missing_candidate_are_refused(tmp_path):
    path, input_path, audit_path, review = packet(tmp_path)
    with pytest.raises(ValueError, match="OUTPUT_MUST_BE_NEW"):
        migrate_rule(path, path, input_path, audit_path, review)
    with pytest.raises(ValueError, match="BUILD_NOT_FOUND"):
        migrate_rule(tmp_path / "missing.db", tmp_path / "new.db", input_path, audit_path, review)


def test_tampered_historical_rule_version_is_rejected(tmp_path):
    path, input_path, audit_path, review = packet(tmp_path)
    output = tmp_path / "new.db"
    migrate_rule(path, output, input_path, audit_path, review)
    with sqlite3.connect(output) as conn:
        conn.execute("DROP TRIGGER rule_versions_no_update")
        conn.execute("UPDATE rule_versions SET payload='[]'")
    with pytest.raises(ValueError, match="VERSION_HASH_MISMATCH"):
        validate_build(output)
