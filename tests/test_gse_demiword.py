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
