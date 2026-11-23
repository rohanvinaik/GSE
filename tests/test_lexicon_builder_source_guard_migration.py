"""Adversarial source-guard migration, with synthetic semantics and model stubs.

These fixtures test authority and historical replay. They do not establish a
linguistic rule about linear units or supply semantic gold for production.
"""

import copy
import json
import sqlite3
from dataclasses import asdict, replace

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import Assertion, Relation
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import (
    WORDNET_OTHER_SYNSET_PREFIX,
    WORDNET_OUTSIDE_ANCESTOR_PREFIX,
    lexical_context,
)
from GSE.curation.lexicon_builder.model_receipts import _context_digest, read_model_receipts
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.reconsideration import reconsider
from GSE.curation.lexicon_builder.residual import _request_id
from GSE.curation.lexicon_builder.reviewed_export import export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow
from GSE.curation.lexicon_builder.rule_admission import admit_rule
from GSE.curation.lexicon_builder.rule_migration import migrate_rule
from GSE.curation.lexicon_builder.storage import read_entries
from GSE.curation.lexicon_builder.validation import validate_build

UNIT = "wordnet:foot:foot.n.02"
HOMOGRAPH = "wordnet:foot:foot.n.01"
CANDIDATE = "wordnet:foot:foot.n.03"
DISCOVERY = "wordnet:inch:inch.n.01"
AUDIT = "wordnet:yard:yard.n.01"
ANCESTOR = "wordnet_ancestor:linear_unit.n.01"
SHARED = "wordnet_ancestor:entity.n.01"


class SyntheticTransport:
    identity = "synthetic-source-guard-migration-test-not-semantic-gold"

    def __init__(self, value):
        self.value = value

    def __call__(self, payload, schema):
        assert set(schema["properties"]) == {payload["bank"]}
        return json.dumps({payload["bank"]: self.value})


def native_definition(entry, *, unit):
    _, lemma, synset = entry.split(":", 2)
    definition = Definition(entry, lemma, "noun", f"Synthetic {'unit' if unit else 'nonunit'} sense {synset}.")
    features = {
        "lemma": lemma,
        "synset_name": synset,
        "pos": "noun",
        "definition": definition.definition,
        "lexname": "noun.quantity" if unit else "noun.body",
        "hypernym_paths": [["entity.n.01", "linear_unit.n.01" if unit else "body_part.n.01", synset]],
        "taxonomy_proposals": [],
        "native_records": [],
    }
    observation = Observation(entry, "wordnet_hierarchy", entry, "wordnet", features, "lexical", (entry,))
    return definition, observation


def source_guard_packet(tmp_path, *, redundant_shared_guard=False):
    path = tmp_path / "source.db"
    pairs = [native_definition(entry, unit=entry != HOMOGRAPH) for entry in (UNIT, HOMOGRAPH, DISCOVERY, AUDIT)]
    candidate, _ = native_definition(CANDIDATE, unit=False)
    _, unresolved = native_definition("wordnet:foot:foot.n.04", unit=True)
    unresolved = replace(unresolved, entry_id=None, candidate_entry_ids=(CANDIDATE,))
    definitions = tuple(pair[0] for pair in pairs) + (candidate,)
    observations = tuple(pair[1] for pair in pairs) + (unresolved,)
    native_zero = Assertion("ALIVE", 0, "wordnet_hierarchy", UNIT, "wordnet")
    build_dictionary(EvidenceBundle(definitions, observations, (native_zero,), ()), path)
    for entry, bank, value in (
        (UNIT, "WANT", 1),
        (UNIT, "BE", 0),
        (HOMOGRAPH, "WANT", 1),
        (CANDIDATE, "WANT", 1),
        (DISCOVERY, "WANT", 0),
    ):
        result = complete_dictionary(path, SyntheticTransport(value), 1, entry_ids=(entry,), banks=(bank,))
        assert result["outcomes"] == {"ASSIGNED": 1}, result
    with sqlite3.connect(path) as conn:
        receipt = read_model_receipts(conn)[DISCOVERY][0]
    guards = [["pos", "noun"], [ANCESTOR, "true"]]
    if redundant_shared_guard:
        guards.append([SHARED, "true"])
    selection = {
        "format": "gse.reviewed-pattern-selection/1",
        "discovery_entry_ids": [DISCOVERY],
        "audit_entry_ids": [AUDIT],
        "reviews": [
            {
                "request_id": receipt["request_id"],
                "review": {
                    "review_id": "synthetic-source-cell-review",
                    "reviewer": "test-fixture",
                    "code": "ACCEPTED",
                    "receipt_sha256": _request_id(receipt),
                    "source_refs": ["synthetic:source-guard-test-only"],
                    "rationale": "Synthetic authority for wiring tests, not linguistic gold.",
                },
            }
        ],
        "guarded_candidates": [
            {
                "antecedent": None,
                "consequent": ["WANT", 0],
                "guards": guards,
                "absent_evidence": [],
                "warrant": {
                    "warrant_id": "synthetic-source-guard-law",
                    "kind": "DEFINITIONAL_DERIVATION",
                    "source_refs": ["synthetic:source-guard-test-only"],
                    "statement": "Synthetic ancestry-scoped zero used only to test migration authority.",
                    "review_id": "synthetic-source-law-review",
                    "reviewer": "test-fixture",
                },
            }
        ],
    }
    exported = export_reviewed_input(path, selection)
    input_path, audit_path = tmp_path / "input.json", tmp_path / "audit.json"
    input_path.write_text(json.dumps(exported["input"]))
    audit = run_workflow(input_path, SyntheticTransport(0), max_calls=1)
    audit_path.write_text(json.dumps(audit))
    proposed = audit["candidates"][0]
    review = {
        "rule_id": proposed["relation"]["rule_id"],
        "warrant_sha256": proposed["warrant_sha256"],
        "review_id": "synthetic-source-admission",
        "reviewer": "test-fixture",
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "rationale": "Synthetic migration test, not a production semantic convention.",
        "source_refs": ["synthetic:source-guard-test-only"],
    }
    admission = admit_rule(input_path, audit_path, review)
    assert admission["relation"]["approved"] is True
    return path, input_path, audit_path, review


def states(path):
    with sqlite3.connect(path) as conn:
        return {row["entry_id"]: row for row in read_entries(conn)}


def test_source_guard_end_to_end_archives_only_exact_unit_chains(tmp_path):
    path, input_path, audit_path, review = source_guard_packet(tmp_path)
    before = path.read_bytes()
    with sqlite3.connect(path) as conn:
        original = {entry: copy.deepcopy(rows) for entry, rows in read_model_receipts(conn).items()}
    output = tmp_path / "migrated.db"
    migrated = migrate_rule(path, output, input_path, audit_path, review)
    assert path.read_bytes() == before
    assert migrated["postflight"]["code"] == "REPLAY_VALIDATED"
    assert migrated["archived_model_receipts"] == 3
    assert migrated["retained_model_receipts"] == 2
    rows = states(output)
    assert rows[UNIT]["assignments"]["WANT"] == 0
    assert rows[UNIT]["assignments"]["ALIVE"] == 0
    assert rows[UNIT]["domains"]["BE"] == rows[UNIT]["domains"]["FEEL"] == [-1, 0, 1]
    assert rows[HOMOGRAPH]["assignments"]["WANT"] == 1
    assert rows[CANDIDATE]["assignments"]["WANT"] == 1
    assert rows[AUDIT]["assignments"]["WANT"] == 0
    with sqlite3.connect(output) as conn:
        retained = read_model_receipts(conn)
        assert set(retained) == {HOMOGRAPH, CANDIDATE}
        assert retained[HOMOGRAPH] == original[HOMOGRAPH]
        assert retained[CANDIDATE] == original[CANDIDATE]
        event = json.loads(conn.execute("SELECT payload FROM rule_migrations").fetchone()[0])
        archived = {row["definition"]["entry_id"]: row for row in event["archived"]}
        assert archived[UNIT]["receipts"] == list(original[UNIT])
        assert [r["assertion"]["bank"] for r in archived[UNIT]["receipts"]] == ["WANT", "BE"]
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


def test_historical_homograph_receipt_uses_original_context_not_new_rule_context(tmp_path):
    path, input_path, audit_path, review = source_guard_packet(tmp_path, redundant_shared_guard=True)
    output = tmp_path / "migrated.db"
    migrate_rule(path, output, input_path, audit_path, review)
    with sqlite3.connect(output) as conn:
        old_receipt = read_model_receipts(conn)[HOMOGRAPH][0]
    assert old_receipt["request"]["scaffold"]["context"] == {"pos": "noun"}
    definition, observation = native_definition(HOMOGRAPH, unit=False)
    new_rule = Relation(
        "synthetic-context-probe",
        ("WANT",),
        ((0,),),
        ("synthetic:test-only",),
        approved=True,
        guards=(("pos", "noun"), (ANCESTOR, "true"), (SHARED, "true")),
    )
    current = lexical_context(definition, (observation,), (new_rule,))
    assert current == {"pos": "noun", SHARED: "true"}
    assert current != old_receipt["request"]["scaffold"]["context"]
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


def test_new_receipts_and_reconsideration_replay_after_source_guard_migration(tmp_path):
    path, input_path, audit_path, review = source_guard_packet(tmp_path)
    output = tmp_path / "migrated.db"
    migrate_rule(path, output, input_path, audit_path, review)
    for bank in ("FEEL", "BE"):
        result = complete_dictionary(output, SyntheticTransport(0), 1, entry_ids=(UNIT,), banks=(bank,))
        assert result["outcomes"] == {"ASSIGNED": 1}, result
    with sqlite3.connect(output) as conn:
        receipts = read_model_receipts(conn)[UNIT]
    assert [r["assertion"]["bank"] for r in receipts] == ["FEEL", "BE"]
    assert all(r["request"]["scaffold"]["context"][ANCESTOR] == "true" for r in receipts)
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"
    withdrawn = reconsider(
        output,
        receipts[0]["request_id"],
        convention="SYNTHETIC_TEST_RECONSIDERATION",
        reason="Synthetic new-context chain withdrawal; no semantic decision.",
        apply=True,
    )
    assert withdrawn["code"] == "RECONSIDERED"
    assert withdrawn["withdrawn_banks"] == ["FEEL", "BE"]
    rows = states(output)
    assert rows[UNIT]["assignments"]["WANT"] == rows[UNIT]["assignments"]["ALIVE"] == 0
    assert rows[UNIT]["domains"]["FEEL"] == rows[UNIT]["domains"]["BE"] == [-1, 0, 1]
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize(
    "defect", ["candidate_only", "wrong_entry", "wrong_record", "association", "wrong_definition", "truncated_path"]
)
def test_complete_exact_native_witness_required_for_guard(defect):
    definition, observation = native_definition(UNIT, unit=True)
    raw = asdict(observation)
    if defect == "candidate_only":
        raw["entry_id"] = None
    elif defect == "wrong_entry":
        raw["entry_id"] = HOMOGRAPH
    elif defect == "wrong_record":
        raw["record_id"] = HOMOGRAPH
    elif defect == "association":
        raw["scope"] = "association"
    elif defect == "wrong_definition":
        raw["features"]["definition"] = "Different lexical meaning."
    else:
        raw["features"]["hypernym_paths"][0].pop()
    rule = Relation(
        "synthetic-scope",
        ("WANT",),
        ((0,),),
        ("synthetic:test-only",),
        approved=True,
        guards=(("pos", "noun"), (ANCESTOR, "true")),
    )
    assert lexical_context(definition, (raw,), (rule,)) == {"pos": "noun"}


def test_complement_guards_require_witness_and_distinguish_self_from_ancestor(tmp_path):
    definition, observation = native_definition(UNIT, unit=True)
    outside = WORDNET_OUTSIDE_ANCESTOR_PREFIX + "body_part.n.01"
    other = WORDNET_OTHER_SYNSET_PREFIX + "linear_unit.n.01"
    rule = Relation(
        "synthetic-complement",
        ("WANT",),
        ((0,),),
        ("synthetic:test-only",),
        authority="conditional",
        approved=True,
        guards=((outside, "true"), (other, "true")),
    )
    assert lexical_context(definition, (), (rule,)) == {"pos": "noun"}
    candidate = replace(observation, entry_id=None)
    assert lexical_context(definition, (candidate,), (rule,)) == {"pos": "noun"}
    assert lexical_context(definition, (observation,), (rule,)) == {"pos": "noun", outside: "true", other: "true"}
    root, root_observation = native_definition("wordnet:linear_unit:linear_unit.n.01", unit=False)
    root_observation = replace(
        root_observation,
        features={**root_observation.features, "hypernym_paths": [["entity.n.01", "linear_unit.n.01"]]},
    )
    assert lexical_context(root, (root_observation,), (rule,)) == {"pos": "noun", outside: "true"}
    with_other_ancestor = replace(
        observation,
        features={
            **observation.features,
            "hypernym_paths": [
                *observation.features["hypernym_paths"],
                ["entity.n.01", "body_part.n.01", "foot.n.02"],
            ],
        },
    )
    assert lexical_context(definition, (with_other_ancestor,), (rule,)) == {"pos": "noun", other: "true"}
    path = tmp_path / "complement.db"
    manifest = tmp_path / "complement.json"
    manifest.write_text(json.dumps({"format": "gse.lexicon-rules/1", "relations": [asdict(rule)]}))
    build_dictionary(
        EvidenceBundle((definition, root), (observation, root_observation), (), ()), path, manifest=manifest
    )
    assert states(path)[UNIT]["domains"]["WANT"] == [0]
    assert states(path)[root.entry_id]["domains"]["WANT"] == [-1, 0, 1]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_removed_native_ancestry_cannot_leave_migrated_assignment_valid(tmp_path):
    path, input_path, audit_path, review = source_guard_packet(tmp_path)
    output = tmp_path / "migrated.db"
    migrate_rule(path, output, input_path, audit_path, review)
    with sqlite3.connect(output) as conn:
        raw = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE record_id=?", (AUDIT,)).fetchone()[0]
        )
        raw["features"]["hypernym_paths"] = [["entity.n.01", "yard.n.01"]]
        conn.execute("UPDATE source_observations SET payload=? WHERE record_id=?", (json.dumps(raw), AUDIT))
    replay = validate_build(output)
    assert replay["code"] != "REPLAY_VALIDATED"
    assert replay["entries_mismatched"] > 0


def test_tampered_historical_request_context_is_rejected(tmp_path):
    path, input_path, audit_path, review = source_guard_packet(tmp_path, redundant_shared_guard=True)
    output = tmp_path / "migrated.db"
    migrate_rule(path, output, input_path, audit_path, review)
    with sqlite3.connect(output) as conn:
        new_context = {"pos": "noun", SHARED: "true"}
        context_digest = _context_digest(new_context)
        conn.execute(
            "INSERT OR IGNORE INTO model_receipt_contexts VALUES (?,?)",
            (context_digest, json.dumps(new_context)),
        )
        conn.execute(
            "UPDATE accepted_model_receipts SET payload=json_set(payload,'$.request.scaffold.context',?) WHERE entry_id=?",
            (context_digest, HOMOGRAPH),
        )
    with pytest.raises(ValueError, match="MODEL_RULE_BINDING_MISMATCH"):
        validate_build(output)
