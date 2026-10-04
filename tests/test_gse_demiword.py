"""
Demi-words — a multi-token nominal slot resolved as one unit (Stage 2 / M-DW).

The structure (one nominal slot, no coordination) decides the span is one unit;
identity keys off the whole span, so "Lady Macbeth" stays distinct from a bare
"Macbeth" even before either grounds.
"""

import json

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    emit,
    evaluate_tree,
    from_dict,
    from_trace,
    resolve,
    resolve_references,
    to_dict,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Control
from gse.symbolic.resolution import Entity


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def test_compound_proper_name_is_one_demiword(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Lady Macbeth sang"))))
    # "Lady Macbeth" → one Entity whose span is the whole demi-word.
    assert isinstance(tree.agent, Entity)
    assert tree.agent.span == ("lady", "macbeth")


def test_demiword_distinct_from_bare_head(encoder):
    tree = evaluate_tree(resolve(from_trace(
        encoder.encode("Lady Macbeth persuaded Macbeth to kill the king"))))
    r = resolve_references(tree)
    assert isinstance(r, Control)
    # "Lady Macbeth" (subject) ≠ "Macbeth" (controller): distinct ids.
    assert r.subject.entity_id != r.controller.entity_id
    assert r.subject.span == ("lady", "macbeth")
    # …and the inner act's agent is the controller (same id), not the subject.
    assert r.inner.agent.entity_id == r.controller.entity_id


def test_demiword_emits_full_span(encoder):
    node = emit(evaluate_tree(resolve(from_trace(encoder.encode("Lady Macbeth sang")))))
    assert node["op"] == "EVENT"
    assert node["args"][0] == "lady macbeth"      # not bare "macbeth"


def test_single_token_has_no_span(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Macbeth sang"))))
    assert tree.agent.span == ()


def test_span_round_trips_serialization():
    e = Entity(head=Atom(lemma="macbeth", word_primitives={}, role=None, position=1, pos="PROPN"),
               span=("lady", "macbeth"))
    back = from_dict(to_dict(e))
    assert back.span == ("lady", "macbeth")
    assert json.loads(json.dumps(to_dict(e)))["span"] == ["lady", "macbeth"]


# -- part B: a matched span grounds to its own dictionary entry --------------

from pathlib import Path  # noqa: E402

_DB = Path("data/genealogy.db")


@pytest.mark.skipif(not _DB.exists(), reason="genealogy.db not built")
def test_demiword_grounds_via_span(encoder):
    from gse.symbolic import GenealogyStore

    with GenealogyStore() as store:
        tree = resolve_references(
            evaluate_tree(resolve(from_trace(encoder.encode("Mike likes ice cream")))), store)
        node = emit(tree)
        ic = [r for r in _all_refs(node) if r["lemma"] == "ice cream"]
        assert ic and ic[0]["type_thread"][-1] == "ice_cream"   # the MWE entry, not "cream"


@pytest.mark.skipif(not _DB.exists(), reason="genealogy.db not built")
def test_lexicalized_adj_noun_promotes_to_demiword(encoder):
    # "hot dog" is a WordNet MWE → promoted to one unit (span set); "big dog" is
    # not lexicalized → stays compositional. WordNet's lexicalization is the gate.
    from gse.symbolic import GenealogyStore

    def first_entity(tree, store):
        from gse.symbolic import entities
        return entities(resolve_references(tree, store))

    with GenealogyStore() as store:
        hot = evaluate_tree(resolve(from_trace(encoder.encode("Mike ate a hot dog"))))
        hot_ents = first_entity(hot, store)
        assert any(e.span == ("hot", "dog") for e in hot_ents)     # promoted

        big = evaluate_tree(resolve(from_trace(encoder.encode("Mike saw a big dog"))))
        big_ents = first_entity(big, store)
        assert all(e.span != ("big", "dog") for e in big_ents)     # not promoted


def _all_refs(node, out=None):
    out = [] if out is None else out
    if isinstance(node, dict):
        if "entity_id" in node:
            out.append(node)
        for v in node.values():
            _all_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            _all_refs(v, out)
    return out
