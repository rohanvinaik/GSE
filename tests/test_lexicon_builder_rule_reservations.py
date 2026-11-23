"""An unresolved audit is not an opposing sign; exact scope can reserve it."""

import json
import sqlite3
from copy import deepcopy
from dataclasses import replace

import pytest
from test_lexicon_builder_joint_revisions import REVIEW
from test_lexicon_builder_source_guard_migration import SyntheticTransport, states
from test_lexicon_epoch import native

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation, _record_id
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.residual import _request_id
from gse.curation.lexicon_builder.reviewed_export import export_reviewed_input
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from gse.curation.lexicon_builder.rule_admission import admit_records
from gse.curation.lexicon_builder.rule_history import digest
from gse.curation.lexicon_builder.rule_migration import migrate_revision
from gse.curation.lexicon_builder.rule_reservations import reservation_source
from gse.curation.lexicon_builder.rule_revisions import RESERVATION_FORMAT, validate_revision_shape
from gse.curation.lexicon_builder.validation import validate_build


def packet(tmp_path, source_kind):
    pairs = []
    for lemma in ("seed", "audit", "reserved"):
        definition, observation = native(lemma, "state.n.02")
        gloss = "The state of being ready."
        definition = replace(definition, definition=gloss)
        observation = replace(observation, features={**observation.features, "definition": gloss})
        if lemma == "reserved" and source_kind == "wiktionary":
            identity = "wiktionary:reserved-fixture"
            definition = Definition(identity, lemma, "noun", gloss)
            features = {
                "identity_scheme": "gse.wiktionary-native-leaf/1", "entry_id": identity, "lemma": lemma,
                "word": lemma, "pos": "noun", "native_id": "reserved-fixture", "definition": gloss,
                "native_sense": {"glosses": [gloss]},
            }
            observation = Observation(
                identity, "wiktionary", _record_id("wiktionary", lemma, features), "wiktionary", features, "lexical", (identity,)
            )
        pairs.append((definition, observation))
    definitions, observations = zip(*pairs)
    source = tmp_path / "source.db"
    build_dictionary(EvidenceBundle(definitions, observations, (), ()), source)
    seed, audit_id, reserved = (definition.entry_id for definition in definitions)
    complete_dictionary(source, SyntheticTransport(1), 1, entry_ids=(seed,), banks=("BE",))
    with sqlite3.connect(source) as conn:
        receipt = read_model_receipts(conn)[seed][0]
    selection = {
        "format": "gse.reviewed-pattern-selection/1", "discovery_entry_ids": [seed],
        "audit_entry_ids": [audit_id, reserved],
        "reviews": [{"request_id": receipt["request_id"], "review": {
            **REVIEW, "code": "ACCEPTED", "receipt_sha256": _request_id(receipt),
        }}],
        "guarded_candidates": [{
            "antecedent": None, "consequent": ["BE", 1],
            "guards": [["pos", "noun"], ["native_noun_frame:stative_being", "true"]], "absent_evidence": [],
            "warrant": {
                "warrant_id": "synthetic:stative", "kind": "DEFINITIONAL_DERIVATION", "source_refs": ["synthetic:test"],
                "statement": "Synthetic rule tests data flow only.", "review_id": "synthetic:rule", "reviewer": "fixture",
            },
        }],
    }
    raw = export_reviewed_input(source, selection)["input"]

    class Transport:
        identity = "synthetic:reservation-audit"

        def __call__(self, payload, schema):
            return json.dumps({"BE": None if payload["entry_id"] == reserved else 1})

    parent = run_workflow_input(raw, Transport(), max_calls=2)
    abstention = next(a for a in parent["candidates"][0]["audits"] if a["entry_id"] == reserved)
    child = deepcopy(raw)
    child["audit_entry_ids"] = [audit_id]
    child["guarded_candidates"][0]["warrant"]["required_reservation_ids"] = [reserved]
    child = export_reviewed_input(source, {
        **selection, "audit_entry_ids": [audit_id], "guarded_candidates": child["guarded_candidates"],
    })["input"]
    tested = run_workflow_input(child, Transport(), max_calls=1)
    [candidate] = tested["candidates"]
    admission = admit_records(child, tested, {
        **REVIEW, "decision": "APPROVE_DEFINITIONAL_RULE", "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
    })
    with sqlite3.connect(source) as conn:
        witness = digest(reservation_source(conn, reserved))
    reservation = {
        **REVIEW, "rule_id": candidate["relation"]["rule_id"], "entry_id": reserved,
        "source_sha256": witness, "bank": "BE", "audit": abstention,
    }
    revision = {
        "format": RESERVATION_FORMAT, "baseline_version": admission["baseline_version"],
        "admissions": [admission], "retirements": [], "exceptions": [], "reservations": [reservation],
    }
    return source, revision, seed, audit_id, reserved


@pytest.mark.parametrize("source_kind", ["wordnet", "wiktionary"])
def test_reserved_unknown_survives_propagation_and_later_independent_teaching(tmp_path, source_kind):
    source, revision, seed, audited, reserved = packet(tmp_path, source_kind)
    before = source.read_bytes()
    output = tmp_path / "candidate.db"
    result = migrate_revision(source, output, revision)
    assert source.read_bytes() == before
    assert result["postflight"]["code"] == "REPLAY_VALIDATED"
    assert states(output)[audited]["domains"]["BE"] == [1]
    assert states(output)[seed]["domains"]["BE"] == [1]
    assert states(output)[reserved]["domains"]["BE"] == [-1, 0, 1]
    assert result["reviewed_reservations"][0]["code"] == "REVIEWED_UNRESOLVED_RESERVATION"
    assert result["reviewed_exceptions"] == []
    complete_dictionary(output, SyntheticTransport(0), 1, entry_ids=(reserved,), banks=("BE",))
    assert states(output)[reserved]["domains"]["BE"] == [0]
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("defect", ["signed", "wrong_request", "wrong_source", "missing", "schema", "known", "duplicate", "malformed"])
def test_reservation_cannot_turn_an_invalid_or_signed_audit_into_uncertainty(tmp_path, defect):
    source, revision, _, _, _ = packet(tmp_path, "wiktionary")
    review = revision["reservations"][0]
    if defect == "signed":
        review["audit"]["raw_output"] = '{"BE":0}'
    elif defect == "wrong_request":
        review["audit"]["request_id"] = "other"
    elif defect == "wrong_source":
        review["source_sha256"] = "stale"
    elif defect == "missing":
        revision["reservations"] = []
    elif defect == "schema":
        review["audit"]["schema"]["additionalProperties"] = True
    elif defect == "known":
        review["audit"]["request"]["known"]["BE"] = 1
        review["audit"]["request_id"] = _request_id(review["audit"]["request"])
    elif defect == "duplicate":
        revision["reservations"].append(deepcopy(review))
    else:
        review["audit"]["raw_output"] = '{"BE":null,"BE":null}'
    output = tmp_path / "invalid.db"
    with pytest.raises(ValueError):
        migrate_revision(source, output, revision)
    assert not output.exists()


@pytest.mark.parametrize("value", [None, [], {}, True])
def test_revision_version_boundary_refuses_malformed_format(value):
    with pytest.raises(ValueError, match="INVALID_RULE_REVISION"):
        validate_revision_shape({"format": value, "baseline_version": "", "admissions": [], "retirements": [], "exceptions": []})
