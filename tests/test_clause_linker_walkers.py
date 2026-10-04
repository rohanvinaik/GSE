"""
Clause-linking predicates are visible to every walker, end to end (#3).

The defect: a tree rooted in a ClauseCoordination ("and"), Conditional ("if") or Temporal
("when/while/after/before") was opaque. ``predicates()`` and ``entities()`` returned nothing, the
knowledge base ingested nothing, ``substitute()`` changed nothing, and ``resolve_references``
never entered a Temporal — so the Genesis-facing emit contract carried no entity ids or type
threads for a when-clause. These tests drive the real pipeline (encode → from_trace → resolve →
evaluate_tree), the same path the emit contract and the knowledge base consume.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    KnowledgeBase,
    clauses,
    entity_lemmas,
    evaluate_tree,
    from_trace,
    is_argument_swap_of,
    predicates,
    resolve,
    substitute,
)
from gse.symbolic.coherence import emit_contract_with_coherence


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _tree(encoder, sentence):
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


def _kinds(nodes):
    return [type(n).__name__ for n in nodes]


def _entity_refs(contract):
    """Every {entity_id, lemma, …} reference anywhere in an emit contract."""
    out, stack = [], [contract]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "entity_id" in node:
                out.append(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return out


def test_clause_coordination_is_walked(encoder):
    tree = _tree(encoder, "Alice ran and Bob walked")
    assert type(tree).__name__ == "ClauseCoordination"
    assert _kinds(predicates(tree)) == ["ClauseCoordination", "Event", "Event"]
    assert set(entity_lemmas(tree)) == {"alice", "bob"}
    assert clauses(tree) == [tree]
    assert "zorble" in entity_lemmas(substitute(tree, {"alice": "zorble"}))


def test_clause_coordination_asserts_both_clauses(encoder):
    kb = KnowledgeBase.from_trees([_tree(encoder, "Alice ran and Bob walked")])
    assert kb.event("run", "alice").holds
    assert kb.event("walk", "bob").holds


def test_temporal_is_walked(encoder):
    tree = _tree(encoder, "When the war started, France declared independence")
    assert type(tree).__name__ == "Temporal"
    assert _kinds(predicates(tree)) == ["Temporal", "Event", "Event"]
    assert set(entity_lemmas(tree)) == {"war", "france", "independence"}
    assert clauses(tree) == [tree]


def test_temporal_asserts_both_clauses(encoder):
    kb = KnowledgeBase.from_trees([_tree(encoder, "When the war started, France declared independence")])
    assert kb.event("start", "war").holds
    assert kb.event("declare", "france", "independence").holds


def test_emit_contract_grounds_entities_under_a_temporal(encoder):
    contract = emit_contract_with_coherence(encoder, "When the war started, France declared independence")
    refs = {ref["lemma"]: ref for ref in _entity_refs(contract)}
    assert contract["contract_version"] == "2.0"
    assert set(refs) == {"war", "france", "independence"}
    assert all(ref["entity_id"] for ref in refs.values())
    assert refs["war"]["type_thread"] and refs["france"]["type_thread"]


def test_conditional_is_walked(encoder):
    tree = _tree(encoder, "If Rex barks, Mike leaves")
    assert type(tree).__name__ == "Conditional"
    assert _kinds(predicates(tree)) == ["Conditional", "Event", "Event"]
    assert set(entity_lemmas(tree)) == {"rex", "mike"}
    assert "zorble" in entity_lemmas(substitute(tree, {"rex": "zorble"}))


def test_conditional_converse_is_an_argument_swap(encoder):
    a = _tree(encoder, "If Rex barks, Mike leaves")
    b = _tree(encoder, "If Mike leaves, Rex barks")
    assert is_argument_swap_of(a, b)
