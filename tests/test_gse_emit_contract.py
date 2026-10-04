"""
Stage-1 emit-contract tests (docs/RESOLVED_STRUCTURE_DESIGN.md M1).

Assert the Genesis-facing {op, args, features} envelope (adapter-spec §5)
reproduces the §4 predicate→Innerese mapping targets and stays JSON-safe.
"""

import json

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    CONTRACT_VERSION,
    emit,
    emit_contract,
    emit_json,
    evaluate_tree,
    from_trace,
    resolve,
)


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _emit(encoder, sentence):
    tree = evaluate_tree(resolve(from_trace(encoder.encode(sentence))))
    return emit(tree)


def test_type_assertion_maps_to_type_assert(encoder):
    # §4.1 "X is a Y" → TYPE_ASSERT(entity, kind)
    node = _emit(encoder, "Spot is a dog")
    assert node["op"] == "TYPE_ASSERT"
    assert node["args"] == ["spot", "dog"]


def test_comparison_carries_sign_feature(encoder):
    # §4.2 comparison → COMPARISON with a sign feature
    node = _emit(encoder, "The dog is cuter than the cat")
    assert node["op"] == "COMPARISON"
    assert "dog" in node["args"][0]
    assert "cat" in node["args"][1]
    assert node["features"]["sign"] in (+1, -1)


def test_causation_is_recursive(encoder):
    # §4.3 cause/effect are themselves clause-subtrees, not atoms
    node = _emit(encoder, "Rex barks because the dog is cuter than the cat")
    assert node["op"] == "CAUSATION"
    assert node["features"]["conjunction"] == "because"
    # One side must be a nested predicate envelope (the comparison).
    nested = [a for a in node["args"] if isinstance(a, dict)]
    assert any(n["op"] == "COMPARISON" for n in nested)


def test_relative_clause_maps_to_rel_restrict(encoder):
    # §4.4 antecedent restricted by an embedded clause
    node = _emit(encoder, "The dog that barks is cuter than the cat")
    # REL_RESTRICT appears somewhere in the tree (it wraps the antecedent).
    blob = json.dumps(node)
    assert "REL_RESTRICT" in blob


def test_control_maps_to_control(encoder):
    # §4.5 nested roleframes — inner act is object of the outer
    node = _emit(encoder, "Lady Macbeth persuaded Macbeth to kill the king")
    blob = json.dumps(node)
    assert "CONTROL" in blob


def test_coordination_maps_to_coord(encoder):
    # §4.6 a sequence of conjuncts as the shared subject
    node = _emit(encoder, "Spot and Rex are dogs")
    blob = json.dumps(node)
    assert "COORD" in blob


def test_contract_envelope_is_versioned_and_json_safe(encoder):
    tree = evaluate_tree(resolve(from_trace(
        encoder.encode("Rex barks because the dog is cuter than the cat"))))
    contract = emit_contract(tree)
    assert contract["contract_version"] == CONTRACT_VERSION
    # Round-trips through JSON unchanged (the wire format the bridge reads).
    s = emit_json(tree)
    assert json.loads(s) == contract


def test_emit_is_total_over_all_demo_sentences(encoder):
    # Every showcase sentence emits without raising and stays JSON-safe.
    sentences = [
        "The dog is cuter than the cat",
        "Spot is a dog",
        "Spot and Rex are dogs",
        "Rex barks because the dog is cuter than the cat",
        "The dog that barks is cuter than the cat",
        "Lady Macbeth persuaded Macbeth to kill the king",
        "Mike wants to leave because Rex barks",
    ]
    for s in sentences:
        json.dumps(emit_contract(
            evaluate_tree(resolve(from_trace(encoder.encode(s))))))
