"""
The Event base predicate — verb roleframes (Must-have #1 from the walker).

A plain verb clause becomes Event(verb, agent, patient); and crucially a
*sub*-clause survives as an Event instead of collapsing to its salient entity,
so a Causation carries cause/effect as nested predicate envelopes.
"""

import json

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    emit,
    evaluate_tree,
    from_dict,
    from_trace,
    predicates,
    resolve,
    to_dict,
)
from gse.symbolic.predicates import Causation, Event


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _pipe(encoder, s):
    return evaluate_tree(resolve(from_trace(encoder.encode(s))))


def test_transitive_clause_is_event(encoder):
    tree = _pipe(encoder, "Duncan rewarded Macbeth")
    assert isinstance(tree, Event)
    assert tree.verb == "reward"
    assert tree.agent.head.lemma == "duncan"
    assert tree.patient.head.lemma == "macbeth"


def test_intransitive_clause_has_no_patient(encoder):
    tree = _pipe(encoder, "Rex barks")
    assert isinstance(tree, Event) and tree.verb == "bark"
    assert tree.agent.head.lemma == "rex"
    assert tree.patient is None


def test_causation_carries_nested_events(encoder):
    # Must-have #1: cause/effect are predicate envelopes, not collapsed entities.
    tree = _pipe(encoder, "Duncan rewarded Macbeth because Duncan became happy")
    assert isinstance(tree, Causation)
    assert isinstance(tree.cause, Event) and isinstance(tree.effect, Event)
    assert tree.effect.verb == "reward"          # "Duncan rewarded Macbeth" survives
    assert tree.cause.verb == "become"           # "Duncan became happy" survives


def test_event_emits_roleframe_envelope(encoder):
    node = emit(_pipe(encoder, "Duncan rewarded Macbeth"))
    assert node == {"op": "EVENT", "args": ["duncan", "macbeth"],
                    "features": {"verb": "reward"}}
    # intransitive: no patient arg
    bark = emit(_pipe(encoder, "Rex barks"))
    assert bark["op"] == "EVENT" and bark["args"] == ["rex"]


def test_causation_emits_nested_event_args(encoder):
    node = emit(_pipe(encoder, "Duncan rewarded Macbeth because Duncan became happy"))
    assert node["op"] == "CAUSATION"
    assert all(isinstance(a, dict) and a["op"] == "EVENT" for a in node["args"])


def test_event_round_trips_json(encoder):
    tree = _pipe(encoder, "Duncan rewarded Macbeth")
    back = from_dict(to_dict(tree))
    assert isinstance(back, Event) and back.verb == "reward"
    assert json.loads(json.dumps(to_dict(tree)))["_kind"] == "Event"


def test_predicates_query_finds_event(encoder):
    preds = predicates(_pipe(encoder, "Duncan rewarded Macbeth because Duncan became happy"))
    names = [type(p).__name__ for p in preds]
    assert "Causation" in names and names.count("Event") == 2
