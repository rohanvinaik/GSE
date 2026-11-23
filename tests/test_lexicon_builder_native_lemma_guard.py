"""Exact native lemma scope; synthetic rules test wiring, not linguistic gold."""

import copy
import json
import sqlite3
from dataclasses import asdict, replace

import pytest
from test_lexicon_builder_lexical_context import native as ancestry_native

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.engine import Relation
from gse.curation.lexicon_builder.evidence import EvidenceBundle
from gse.curation.lexicon_builder.foundation import (
    BANKS,
    lexical_context,
    projection_relations,
    valid_lexical_guard,
    validate_lexical_guards,
)
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.residual import _request_id, build_request
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.reviewed_export import export_reviewed_input
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow
from gse.curation.lexicon_builder.rule_migration import migrate_rule
from gse.curation.lexicon_builder.storage import read_entries
from gse.curation.lexicon_builder.validation import validate_build

NATIVE = "wordnet_native_lemma"
ANCESTOR = "wordnet_ancestor:linear_unit.n.01"


def native(lemma="inch", *, names=None, synset="inch.n.01"):
    definition, observation = ancestry_native(lemma, synset=synset)
    return definition, replace(
        observation, features={**observation.features, "lemma_names": [lemma] if names is None else names}
    )


def rule(*guards, bank="QUANTITY"):
    return Relation(
        "fixture:native-spelling",
        (bank,),
        ((1,),),
        ("synthetic:test-only",),
        approved=True,
        guards=guards or ((NATIVE, "true"),),
    )


@pytest.mark.parametrize("serialized", [False, True])
@pytest.mark.parametrize("names", [["INCH"], ["unit", "inch"]])
def test_guard_accepts_complete_exact_native_names_only_when_requested(serialized, names):
    definition, observation = native(names=names)
    if serialized:
        definition, observation = asdict(definition), asdict(observation)
    assert lexical_context(definition, (observation,), (rule(),)) == {"pos": "noun", NATIVE: "true"}
    assert lexical_context(definition, (observation,), ()) == {"pos": "noun"}
    assert lexical_context(definition, (observation,), (rule((ANCESTOR, "true")),)) == {"pos": "noun", ANCESTOR: "true"}
    # Preserve the public validator's original ancestry-name return contract.
    assert validate_lexical_guards((rule(),)) == ()
    assert validate_lexical_guards((rule((ANCESTOR, "true"), (NATIVE, "true")),)) == ("linear_unit.n.01",)


def test_lexical_context_accepts_tuple_native_names_before_json_serialization():
    definition, observation = native()
    raw = asdict(observation)
    raw["features"]["lemma_names"] = ("inch",)
    assert lexical_context(definition, (raw,), (rule(),)) == {"pos": "noun", NATIVE: "true"}


@pytest.mark.parametrize(
    "lemma,names,expected",
    [
        ("nautical mile", ["nautical_mile"], True),
        ("NAUTICAL_MILE", ["nautical mile"], True),
        ("STRASSE", ["straße"], True),
        ("as", ["angstrom", "A"], False),
        ("ms", ["meter", "m"], False),
        ("inches", ["inch"], False),
        ("inch", [" inch "], False),
    ],
)
def test_only_casefold_and_underscore_space_normalization(lemma, names, expected):
    definition, observation = native(lemma, names=names)
    context = lexical_context(definition, (observation,), (rule(),))
    assert context == ({"pos": "noun", NATIVE: "true"} if expected else {"pos": "noun"})


@pytest.mark.parametrize(
    "names",
    [None, [], (), "inch", {"inch": True}, [""], [" "], ["inch", ""], ["inch", None], ["inch", True], ["inch", 1]],
)
def test_missing_or_partly_malformed_names_abstain_without_changing_ancestry(names):
    definition, observation = native()
    raw = asdict(observation)
    if names is None:
        raw["features"].pop("lemma_names")
    else:
        raw["features"]["lemma_names"] = names
    assert lexical_context(definition, (raw,), (rule((ANCESTOR, "true"), (NATIVE, "true")),)) == {
        "pos": "noun",
        ANCESTOR: "true",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_id", None),
        ("entry_id", "foreign"),
        ("record_id", "foreign"),
        ("source", "candidate_wordnet"),
        ("scope", "association"),
        ("scope", "world"),
        ("scope", "source_structure"),
        ("features", None),
    ],
)
def test_native_lemma_requires_same_exact_ancestry_witness(field, value):
    definition, observation = native()
    raw = asdict(observation)
    raw[field] = value
    assert lexical_context(definition, (raw,), (rule(),)) == {"pos": "noun"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("lemma", "other"),
        ("definition", "Different sense."),
        ("pos", "verb"),
        ("synset_name", "foot.n.01"),
        ("hypernym_paths", []),
        ("hypernym_paths", [["linear_unit.n.01"]]),
        ("hypernym_paths", [["linear_unit.n.01", "inch.n.01", "inch.n.01"]]),
    ],
)
def test_malformed_complete_source_cannot_be_repaired_by_native_lemma_label(field, value):
    definition, observation = native()
    raw = asdict(observation)
    raw["features"][field] = value
    assert lexical_context(definition, (raw,), (rule(),)) == {"pos": "noun"}


def test_ancestry_and_lemma_names_cannot_be_joined_from_different_witnesses():
    definition, observation = native(names=["other"])
    malformed = asdict(observation)
    malformed["features"]["lemma_names"] = ["inch"]
    malformed["features"]["hypernym_paths"] = []
    assert lexical_context(definition, (observation, malformed), (rule(),)) == {"pos": "noun"}
    assert lexical_context(definition, (), (rule(),)) == {"pos": "noun"}


@pytest.mark.parametrize("value", ["false", "TRUE", "1", "", True, None])
def test_only_literal_true_guard_value_is_supported(value):
    assert not valid_lexical_guard(NATIVE, value)
    if isinstance(value, str):
        with pytest.raises(ValueError, match="UNSUPPORTED_LEXICAL_GUARD"):
            validate_lexical_guards((rule((NATIVE, value)),))


def test_historical_ancestry_context_and_request_are_unchanged():
    definition, observation = native()
    relations = projection_relations() + (rule((ANCESTOR, "true")),)
    old_context = {"pos": "noun", ANCESTOR: "true"}
    current_context = lexical_context(definition, (observation,), relations)
    assert current_context == old_context
    resolution = resolve_dictionary(BANKS, (), relations, old_context)
    old = build_request(
        definition.entry_id,
        "WANT",
        resolution,
        (asdict(observation),),
        definition=definition,
        relations=relations,
        context=old_context,
    )
    current = build_request(
        definition.entry_id,
        "WANT",
        resolution,
        (asdict(observation),),
        definition=definition,
        relations=relations,
        context=current_context,
    )
    assert current.payload() == old.payload() and current.request_id == old.request_id


class Transport:
    identity = "synthetic-native-lemma-scope-only"

    def __init__(self, value):
        self.value, self.requests = value, []

    def __call__(self, payload, _schema):
        self.requests.append(copy.deepcopy(payload))
        return json.dumps({payload["bank"]: self.value})

    def callable_batch(self, items):
        return tuple(self(payload, schema) for payload, schema in items)


def states(path):
    with sqlite3.connect(path) as conn:
        return {row["entry_id"]: row for row in read_entries(conn)}


def built(tmp_path, *, transport=None):
    exact, exact_source = native()
    derived, derived_source = native("as", names=["angstrom", "A"], synset="angstrom.n.01")
    manifest = tmp_path / "rule.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "gse.lexicon-rules/1",
                "relations": [asdict(rule())],
                "prime_entries": {"nsm:v20:want": [exact.entry_id]},
            }
        )
    )
    path = tmp_path / "native.db"
    build_dictionary(
        EvidenceBundle((exact, derived), (exact_source, derived_source), (), ()),
        path,
        manifest=manifest,
        transport=transport,
        max_model_calls=2 if transport else 0,
    )
    return path, exact, derived


def test_native_only_guard_real_build_catalog_and_replay(tmp_path):
    path, exact, derived = built(tmp_path)
    rows = states(path)
    assert rows[exact.entry_id]["assignments"]["QUANTITY"] == 1
    assert rows[derived.entry_id]["domains"]["QUANTITY"] == [-1, 0, 1]
    assert "QUANTITY" not in rows[derived.entry_id]["assignments"]
    with sqlite3.connect(path) as conn:
        catalog = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='catalog'").fetchone()[0])
    linked = next(unit for unit in catalog["units"] if unit["unit_id"] == "nsm:v20:want")["definitions"][0]
    assert linked["assignments"]["QUANTITY"] == 1
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_removed_native_lemma_witness_invalidates_guarded_assignment(tmp_path):
    path, exact, _ = built(tmp_path)
    with sqlite3.connect(path) as conn:
        row = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE record_id=?", (exact.entry_id,)).fetchone()[0]
        )
        row["features"]["lemma_names"] = ["different_native_name"]
        conn.execute("UPDATE source_observations SET payload=? WHERE record_id=?", (json.dumps(row), exact.entry_id))
    replay = validate_build(path)
    assert replay["code"] != "REPLAY_VALIDATED"
    assert replay["entries_mismatched"] > 0


@pytest.mark.parametrize("batch_size", [1, 2])
def test_completion_paths_include_native_only_guard_and_keep_derived_unknown(tmp_path, batch_size):
    path, exact, derived = built(tmp_path)
    transport = Transport(0)
    result = complete_dictionary(
        path, transport, 2, entry_ids=(exact.entry_id, derived.entry_id), banks=("BE",), batch_size=batch_size
    )
    assert result["outcomes"] == {"ASSIGNED": 2}
    requests = {item["entry_id"]: item for item in transport.requests}
    assert requests[exact.entry_id]["scaffold"]["context"] == {"pos": "noun", NATIVE: "true"}
    assert requests[derived.entry_id]["scaffold"]["context"] == {"pos": "noun"}
    assert states(path)[derived.entry_id]["domains"]["QUANTITY"] == [-1, 0, 1]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_inline_build_model_context_uses_native_guard_when_requested(tmp_path):
    transport = Transport(None)
    path, exact, derived = built(tmp_path, transport=transport)
    assert transport.requests
    for request in transport.requests:
        expected = {"pos": "noun", NATIVE: "true"} if request["entry_id"] == exact.entry_id else {"pos": "noun"}
        assert request["scaffold"]["context"] == expected
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("combined_ancestry", [False, True])
def test_real_export_audit_migration_preserves_derived_historical_receipt(tmp_path, combined_ancestry):
    pairs = [
        native("inch"),
        native("yard", synset="yard.n.01"),
        native("foot", synset="foot.n.02"),
        native("as", names=["angstrom", "A"], synset="angstrom.n.01"),
    ]
    discovery, audit, unit, derived = (pair[0] for pair in pairs)
    # An old ancestry-only rule is deliberately blocked on noun fixtures.
    baseline = replace(rule(("pos", "verb"), (ANCESTOR, "true"), bank="BE"), rule_id="fixture:old-ancestry-only")
    manifest = tmp_path / "baseline.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "gse.lexicon-rules/1",
                "relations": [asdict(baseline)],
                "prime_entries": {"nsm:v20:want": [unit.entry_id]},
            }
        )
    )
    source = tmp_path / "source.db"
    build_dictionary(
        EvidenceBundle(tuple(p[0] for p in pairs), tuple(p[1] for p in pairs), (), ()), source, manifest=manifest
    )
    for definition, value in ((discovery, 1), (unit, 0), (derived, 0)):
        result = complete_dictionary(source, Transport(value), 1, entry_ids=(definition.entry_id,), banks=("QUANTITY",))
        assert result["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(source) as conn:
        originals = {entry: copy.deepcopy(rows) for entry, rows in read_model_receipts(conn).items()}
    receipt = originals[discovery.entry_id][0]
    guards = [[NATIVE, "true"]] + ([[ANCESTOR, "true"]] if combined_ancestry else [])
    selection = {
        "format": "gse.reviewed-pattern-selection/1",
        "discovery_entry_ids": [discovery.entry_id],
        "audit_entry_ids": [audit.entry_id, derived.entry_id],
        "reviews": [
            {
                "request_id": receipt["request_id"],
                "review": {
                    "review_id": "synthetic-native-spelling-review",
                    "reviewer": "test-fixture",
                    "code": "ACCEPTED",
                    "receipt_sha256": _request_id(receipt),
                    "source_refs": ["synthetic:scope-only"],
                    "rationale": "Synthetic fixture authority; no linguistic claim.",
                },
            }
        ],
        "guarded_candidates": [
            {
                "antecedent": None,
                "consequent": ["QUANTITY", 1],
                "guards": guards,
                "absent_evidence": [],
                "warrant": {
                    "warrant_id": "synthetic-native-spelling-law",
                    "kind": "DEFINITIONAL_DERIVATION",
                    "source_refs": ["synthetic:scope-only"],
                    "statement": "Synthetic source-scope wiring fixture.",
                    "review_id": "synthetic-law-review",
                    "reviewer": "test-fixture",
                },
            }
        ],
    }
    before = source.read_bytes()
    exported = export_reviewed_input(source, selection)
    assert source.read_bytes() == before
    assert all(NATIVE not in item["context"] for item in exported["input"]["entries"])
    input_path, audit_path = tmp_path / "input.json", tmp_path / "audit.json"
    input_path.write_text(json.dumps(exported["input"]))
    transport = Transport(1)
    audited = run_workflow(input_path, transport, max_calls=1)
    candidate = audited["candidates"][0]
    assert candidate["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    assert candidate["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "GUARD_NOT_MET": 1}
    assert NATIVE not in transport.requests[0]["scaffold"]["context"]  # Tested guard never leaks into the question.
    assert candidate["relation"]["approved"] is False
    # Out-of-scope probes are evidence of the boundary, not admission audits.
    # The existing admission gate requires every selected audit to agree.
    selection["audit_entry_ids"] = [audit.entry_id]
    exported = export_reviewed_input(source, selection)
    input_path.write_text(json.dumps(exported["input"]))
    audited = run_workflow(input_path, Transport(1), max_calls=1)
    candidate = audited["candidates"][0]
    assert candidate["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
    audit_path.write_text(json.dumps(audited))
    review = {
        "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "synthetic-admission",
        "reviewer": "test-fixture",
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "rationale": "Synthetic migration test only.",
        "source_refs": ["synthetic:scope-only"],
    }
    output = tmp_path / "migrated.db"
    migrated = migrate_rule(source, output, input_path, audit_path, review)
    assert source.read_bytes() == before
    assert migrated["archived_model_receipts"] == 2 and migrated["retained_model_receipts"] == 1
    assert migrated["postflight"]["code"] == "REPLAY_VALIDATED"
    rows = states(output)
    for definition in (discovery, audit, unit):
        assert rows[definition.entry_id]["assignments"]["QUANTITY"] == 1
    assert (
        rows[derived.entry_id]["assignments"]["QUANTITY"] == 0
    )  # Retained explicit historical ruling, not a new zero.
    with sqlite3.connect(output) as conn:
        retained = read_model_receipts(conn)
        assert retained[derived.entry_id] == originals[derived.entry_id]
        assert retained[derived.entry_id][0]["request"]["scaffold"]["context"] == {"pos": "noun", ANCESTOR: "true"}
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"
