"""Exact native ancestry controls rule scope, never invents a bank assignment."""

import json
import sqlite3
from copy import deepcopy
from dataclasses import asdict, replace
from urllib.parse import quote

import pytest

from GSE.curation.lexicon_builder.catalog import catalog_report
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import Relation
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import (
    BANKS,
    definition_context,
    lexical_context,
    load_manifest,
    projection_relations,
    valid_lexical_guard,
)
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.residual import build_request
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.validation import validate_build

GUARD = "wordnet_ancestor:linear_unit.n.01"


def native(lemma="inch", *, synset="inch.n.01", pos="noun"):
    entry = f"wordnet:{quote(lemma, safe='')}:{quote(synset, safe='')}"
    definition = Definition(entry, lemma, pos, "Synthetic exact definition for scope testing.", (entry,))
    observation = Observation(
        entry,
        "wordnet_hierarchy",
        entry,
        "wordnet",
        {
            "lemma": lemma,
            "synset_name": synset,
            "pos": pos,
            "definition": definition.definition,
            "hypernym_paths": [["entity.n.01", "linear_unit.n.01", synset]],
            "lexname": "noun.quantity",
            "taxonomy_proposals": [],
            "native_records": [],
        },
        "lexical",
        (entry,),
    )
    return definition, observation


def scoped_rule(guard=GUARD, value="true"):
    # Deliberately synthetic relation: this fixture does not propose a semantic law.
    return Relation(
        "fixture:ancestry-scope",
        ("WANT",),
        ((0,),),
        ("test:synthetic-scope-only",),
        approved=True,
        guards=((guard, value),),
    )


@pytest.mark.parametrize("serialized", [False, True])
def test_exact_witness_adds_only_requested_membership(serialized):
    definition, observation = native()
    if serialized:
        definition, observation = asdict(definition), asdict(observation)
    assert lexical_context(definition, (observation,), (scoped_rule(),)) == {"pos": "noun", GUARD: "true"}
    assert lexical_context(definition, (observation,), ()) == {"pos": "noun"}
    outside = scoped_rule("wordnet_ancestor:animal.n.01")
    assert lexical_context(definition, (observation,), (outside,)) == {"pos": "noun"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_id", None),
        ("entry_id", "wordnet:other:inch.n.01"),
        ("record_id", "wordnet:other:inch.n.01"),
        ("source", "candidate_wordnet"),
        ("scope", "association"),
        ("features", None),
        ("features", {}),
    ],
)
def test_nonexact_observation_never_activates_guard(field, value):
    definition, observation = native()
    raw = asdict(observation)
    raw[field] = value
    assert lexical_context(definition, (raw,), (scoped_rule(),)) == {"pos": "noun"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("lemma", "foot"),
        ("definition", "A different sense, even with the same spelling."),
        ("definition", None),
        ("pos", "verb"),
        ("synset_name", "inch.n.1"),
        ("synset_name", "foot.n.01"),
        ("hypernym_paths", None),
        ("hypernym_paths", []),
        ("hypernym_paths", [[]]),
        ("hypernym_paths", ["entity.n.01"]),
        ("hypernym_paths", [["linear_unit.n.01"]]),
        ("hypernym_paths", [["linear_unit.n.1", "inch.n.01"]]),
        ("hypernym_paths", [[None, "inch.n.01"]]),
        ("hypernym_paths", [["linear_unit.n.01", "inch.n.01", "inch.n.01"]]),
        ("hypernym_paths", [["linear_unit.v.01", "inch.n.01"]]),
        ("hypernym_paths", [["linear_unit.n.01", "inch.n.01"], ["wrong.n.01"]]),
    ],
)
def test_malformed_or_inconsistent_native_feature_abstains(field, value):
    definition, observation = native()
    raw = asdict(observation)
    raw["features"][field] = value
    assert lexical_context(definition, (raw,), (scoped_rule(),)) == {"pos": "noun"}


def test_definition_identity_and_full_gloss_are_binding():
    definition, observation = native()
    for changed in (
        replace(definition, lemma="foot"),
        replace(definition, entry_id="authored:inch"),
        replace(definition, definition=definition.definition + " Extra content."),
        replace(definition, definition=""),
        replace(definition, pos="verb"),
    ):
        assert lexical_context(changed, (observation,), (scoped_rule(),)) == definition_context(changed.pos)
    assert lexical_context(definition, (), (scoped_rule(),)) == {"pos": "noun"}


def test_canonical_lemma_alias_and_pos_alias_remain_exact_source_backed():
    definition, observation = native("measuring inch", pos="n")
    assert "%20" in definition.entry_id
    # A synonym's lemma need not equal the synset's canonical lemma.
    assert lexical_context(replace(definition, pos="noun"), (observation,), (scoped_rule(),))[GUARD] == "true"
    aliased = replace(definition, entry_id=definition.entry_id.replace("%20", " "))
    assert GUARD not in lexical_context(aliased, (replace(observation, entry_id=aliased.entry_id),), (scoped_rule(),))


@pytest.mark.parametrize(
    "key,value",
    [
        ("wordnet_ancestor", "linear_unit.n.01"),
        ("wordnet_ancestor:", "true"),
        ("wordnet_ancestor:linear_unit.n.1", "true"),
        ("wordnet_ancestor:linear_unit.n.001", "true"),
        ("wordnet_ancestor:linear_unit.x.01", "true"),
        ("wordnet_ancestor:linear unit.n.01", "true"),
        (GUARD, "false"),
        (GUARD, "TRUE"),
        ("lexname", "noun.quantity"),
    ],
)
def test_unsupported_guard_schema_refused_before_output_creation(tmp_path, key, value):
    assert not valid_lexical_guard(key, value)
    manifest = tmp_path / "bad-rule.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "relations": [asdict(scoped_rule(key, value))]}))
    with pytest.raises(ValueError, match="UNSUPPORTED_LEXICAL_GUARD"):
        load_manifest(manifest)
    output = tmp_path / "never-created.db"
    with pytest.raises(ValueError, match="UNSUPPORTED_LEXICAL_GUARD"):
        build_dictionary(EvidenceBundle((), (), (), ()), output, manifest=manifest)
    assert not output.exists()
    with pytest.raises(ValueError, match="UNSUPPORTED_LEXICAL_GUARD"):
        catalog_report({}, (), (scoped_rule(key, value),))


def test_nonstring_guard_schema_is_false():
    for key, value in ((None, "true"), (GUARD, True), (GUARD, None), ([], "true")):
        assert not valid_lexical_guard(key, value)


def test_unused_source_details_do_not_change_legacy_request_identity():
    definition, observation = native()
    relations = projection_relations()
    context = definition_context(definition.pos)
    resolution = resolve_dictionary(BANKS, (), relations, context)
    old = build_request(
        definition.entry_id,
        "WANT",
        resolution,
        (asdict(observation),),
        definition=definition,
        relations=relations,
        context=context,
    )
    current = build_request(
        definition.entry_id,
        "WANT",
        resolution,
        (asdict(observation),),
        definition=definition,
        relations=relations,
        context=lexical_context(definition, (observation,), relations),
    )
    assert old.request_id == current.request_id
    assert old.payload() == current.payload()


class Transport:
    identity = "fixture:exact-ancestry-context"

    def __init__(self, answer=None):
        self.requests = []
        self.answer = answer

    def __call__(self, payload, schema):
        self.requests.append(deepcopy(payload))
        return json.dumps({payload["bank"]: self.answer})

    def callable_batch(self, items):
        return tuple(self(payload, schema) for payload, schema in items)


def build_fixture(tmp_path, *, transport=None):
    definition, observation = native()
    manifest = tmp_path / "rules.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "GSE.lexicon-rules/1",
                "relations": [asdict(scoped_rule())],
                "prime_entries": {"nsm:v20:want": [definition.entry_id]},
            }
        )
    )
    path = tmp_path / "scope.db"
    build_dictionary(
        EvidenceBundle((definition,), (observation,), (), ()),
        path,
        manifest=manifest,
        transport=transport,
        max_model_calls=int(transport is not None),
    )
    return path, definition


def test_symbolic_build_and_native_catalog_use_exact_witness_without_transport(tmp_path):
    path, definition = build_fixture(tmp_path)
    with sqlite3.connect(path) as conn:
        domains = json.loads(conn.execute("SELECT domains FROM definition_states").fetchone()[0])
        catalog = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='catalog'").fetchone()[0])
    assert domains["WANT"] == [0]
    assert domains["BE"] == [-1, 0, 1]
    linked = next(unit for unit in catalog["units"] if unit["unit_id"] == "nsm:v20:want")["definitions"][0]
    assert linked["entry_id"] == definition.entry_id
    assert linked["assignments"]["WANT"] == 0
    assert linked["domains"]["BE"] == [-1, 0, 1]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("batch_size", [1, 2])
def test_completion_both_dispatch_paths_use_scope_and_preserve_unknowns(tmp_path, batch_size):
    path, _ = build_fixture(tmp_path)
    transport = Transport(1)
    report = complete_dictionary(path, transport, 1, banks=("BE",), batch_size=batch_size)
    assert report["outcomes"] == {"ASSIGNED": 1}
    assert transport.requests[0]["known"]["WANT"] == 0
    assert transport.requests[0]["scaffold"]["context"] == {"pos": "noun", GUARD: "true"}
    with sqlite3.connect(path) as conn:
        domains = json.loads(conn.execute("SELECT domains FROM definition_states").fetchone()[0])
    assert domains["BE"] == [1]
    assert domains["THINK"] == [-1, 0, 1]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_build_time_model_path_receives_same_scope(tmp_path):
    transport = Transport()
    path, _ = build_fixture(tmp_path, transport=transport)
    assert transport.requests[0]["scaffold"]["context"] == {"pos": "noun", GUARD: "true"}
    assert transport.requests[0]["known"]["WANT"] == 0
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
