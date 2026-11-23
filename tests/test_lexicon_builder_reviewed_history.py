"""Reviewed old/new receipt prefixes survive an unaffected rule migration."""

import sqlite3
from copy import deepcopy

import pytest
from test_lexicon_builder_rule_migration import Transport, packet

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.residual import _request_id
from gse.curation.lexicon_builder.reviewed_export import export_reviewed_input
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from gse.curation.lexicon_builder.rule_history import digest
from gse.curation.lexicon_builder.rule_migration import migrate_rule


def migrated_input(tmp_path):
    source, input_path, audit_path, review = packet(tmp_path)
    migrated = tmp_path / "migrated.db"
    migrate_rule(source, migrated, input_path, audit_path, review)
    # b is a noun, outside the added verb rule. Its old WANT receipt remains;
    # this new SEE receipt is asked under the current rule inventory.
    complete_dictionary(migrated, Transport(0), 1, entry_ids=("b",), banks=("SEE",))
    with sqlite3.connect(migrated) as conn:
        receipts = read_model_receipts(conn)["b"]
        reviews = [
            {
                "request_id": receipt["request_id"],
                "review": {
                    "review_id": "synthetic-history:" + receipt["request_id"],
                    "reviewer": "test-fixture",
                    "code": "ACCEPTED",
                    "receipt_sha256": _request_id(receipt),
                    "source_refs": ["synthetic:test-only"],
                    "rationale": "Synthetic historical replay fixture only.",
                },
            }
            for receipt in receipts
        ]
    selection = {
        "format": "gse.reviewed-pattern-selection/1",
        "discovery_entry_ids": ["c"],
        "audit_entry_ids": ["b"],
        "reviews": reviews,
        "guarded_candidates": [
            {
                "antecedent": ["SEE", 0],
                "consequent": ["KNOW", 0],
                "guards": [["pos", "noun"]],
                "absent_evidence": [],
                "warrant": {
                    "warrant_id": "synthetic-history-law",
                    "kind": "DEFINITIONAL_DERIVATION",
                    "source_refs": ["synthetic:test-only"],
                    "statement": "Synthetic historical audit fixture only.",
                    "review_id": "synthetic-law-review",
                    "reviewer": "test-fixture",
                },
            }
        ],
    }
    before = migrated.read_bytes()
    exported = export_reviewed_input(migrated, selection)
    assert migrated.read_bytes() == before
    assert exported["selected_provenance"] == "REPLAY_VALIDATED"
    return exported["input"]


def test_reviewed_prefix_replays_old_then_current_rules_and_audits_under_current(tmp_path):
    raw = migrated_input(tmp_path)
    history = raw["rule_history"]
    assert history["format"] == "gse.reviewed-pattern-history/1"
    assert len(history["bindings"]) == 1
    assert len(history["versions"]) == 2
    assert len(raw["rulings"]) == 2
    report = run_workflow_input(raw, Transport(0), max_calls=1)
    candidate = report["candidates"][0]
    assert candidate["staging"][0]["code"] == "STAGED_ONLY"
    assert candidate["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
    question = candidate["audits"][0]["request"]
    assert question["known"]["SEE"] == question["known"]["WANT"] == 0
    requested_rules = {rule["rule_id"]: rule for rule in question["scaffold"]["approved_relations"]}
    current_rules = {rule["rule_id"]: rule for rule in raw["relations"] if rule["approved"]}
    assert requested_rules.keys() == current_rules.keys()
    for identity, rule in current_rules.items():
        assert {key: requested_rules[identity][key] for key in rule} == rule
    newly_added = next(rule for rule in requested_rules.values() if rule["guards"] == [["pos", "verb"]])
    assert newly_added["disposition"] == "BLOCKED"
    assert report["lexicon_writes"] is False


def test_missing_historical_binding_cannot_silently_reinterpret_old_request(tmp_path):
    raw = migrated_input(tmp_path)
    del raw["rule_history"]
    report = run_workflow_input(raw, Transport(0), max_calls=1)
    assert report["candidates"][0]["audit_outcomes"] == {"ANTECEDENT_BASELINE_MISMATCH": 1}
    assert report["model_calls"] == 0


@pytest.mark.parametrize(
    "target,code",
    [
        ("version", "RULE_VERSION_HASH_MISMATCH"),
        ("receipt", "MODEL_RULE_BINDING_MISMATCH"),
        ("entry", "MODEL_RULE_BINDING_MISMATCH"),
        ("binding", "UNKNOWN_PATTERN_RULE_BINDING"),
    ],
)
def test_historical_input_hash_and_identity_tampering_is_refused(tmp_path, target, code):
    raw = migrated_input(tmp_path)
    history = raw["rule_history"]
    binding = history["bindings"][0]
    if target == "version":
        history["versions"][0]["relations"] = []
    elif target == "receipt":
        binding["receipt_sha256"] = "0" * 64
    elif target == "entry":
        binding["entry_id"] = "c"
    else:
        binding["request_id"] = "unknown"
    with pytest.raises(ValueError, match=code):
        run_workflow_input(raw, Transport(0), max_calls=1)


def test_history_cannot_keep_receipt_inside_new_rule_scope(tmp_path):
    raw = migrated_input(tmp_path)
    history = raw["rule_history"]
    current = history["current_version"]
    original_version = history["bindings"][0]["version"]
    original_ids = {
        r["rule_id"]
        for version in history["versions"]
        if version["version"] == original_version
        for r in version["relations"]
    }
    # Rehashing a changed current set does not evade the semantic scope check.
    added = next(rule for rule in raw["relations"] if rule["rule_id"] not in original_ids)
    added["guards"] = [["pos", "noun"]]
    new_version = digest(raw["relations"])
    for version in history["versions"]:
        if version["version"] == current:
            version.update(version=new_version, relations=deepcopy(raw["relations"]))
    history["current_version"] = new_version
    with pytest.raises(ValueError, match="HISTORICAL_MODEL_CONTEXT_AFFECTED"):
        run_workflow_input(raw, Transport(0), max_calls=1)


def test_nonadditive_historical_rules_cannot_be_rehashed_into_authority(tmp_path):
    raw = migrated_input(tmp_path)
    history = raw["rule_history"]
    binding = history["bindings"][0]
    original = next(version for version in history["versions"] if version["version"] == binding["version"])
    original["relations"][0]["provenance"].append("invented")
    original["version"] = digest(original["relations"])
    binding["version"] = original["version"]
    with pytest.raises(ValueError, match="NONADDITIVE_RULE_HISTORY"):
        run_workflow_input(raw, Transport(0), max_calls=1)
