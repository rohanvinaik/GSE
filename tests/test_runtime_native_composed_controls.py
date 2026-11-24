"""Development regressions through actual native encoder and composed consumers.

The three reported failures and subsequently inspected cases are development,
not a fresh final holdout or evidence of full workload acceptance.
"""

import pytest

from GSE.api import GSEEncoder
from GSE.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from GSE.symbolic.expression import Negation
from GSE.symbolic.predicates import Event, Temporal, TypeAssertion
from GSE.symbolic.queries import is_logically_equal_to


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as instance:
        instance.conn.execute("PRAGMA query_only=ON")
        yield instance


def compose(encoder, text):
    return evaluate_tree(resolve(from_trace(encoder.encode(text))))


def test_spatial_opposites_reach_query_and_emitted_contract(encoder):
    above = compose(encoder, "The bird is above the tree.")
    below = compose(encoder, "The bird is below the tree.")
    assert isinstance(above, Event) and isinstance(below, Event)
    assert (above.verb, below.verb) == ("above", "below")
    assert above.agent.head.lemma == below.agent.head.lemma == "bird"
    assert above.patient.head.lemma == below.patient.head.lemma == "tree"
    assert not is_logically_equal_to(above, below)
    assert emit_contract(above)["predicate"]["features"]["verb"] == "above"
    assert emit_contract(below)["predicate"]["features"]["verb"] == "below"
    negated = compose(encoder, "The bird is not above the tree.")
    assert isinstance(negated, Negation) and negated.operand.verb == "above"


@pytest.mark.parametrize("linker,anchor", [("before", "dawn"), ("after", "noon"), ("after", "winter")])
def test_native_time_typed_nominal_is_setting_not_patient(encoder, linker, anchor):
    tree = compose(encoder, f"Alice arrived {linker} {anchor}.")
    assert isinstance(tree, Temporal) and tree.conjunction == linker
    assert tree.setting.head.lemma == anchor
    assert isinstance(tree.event, Event) and tree.event.verb == "arrive"
    assert tree.event.agent.head.lemma == "alice" and tree.event.patient is None
    assert emit_contract(tree)["predicate"]["features"]["conjunction"] == linker


@pytest.mark.parametrize("linker", ["before", "after"])
def test_existing_clausal_temporal_arguments_remain_events(encoder, linker):
    tree = compose(encoder, f"Alice arrived {linker} Bob left.")
    assert isinstance(tree, Temporal) and tree.conjunction == linker
    assert isinstance(tree.setting, Event) and tree.setting.verb == "leave"
    assert isinstance(tree.event, Event) and tree.event.verb == "arrive"


def test_non_time_anchor_cannot_become_temporal_from_preposition_alone(encoder):
    assert not isinstance(compose(encoder, "Alice stood before the king."), Temporal)


def test_native_chemical_identity_survives_nominal_copula_and_emission(encoder):
    trace = encoder.encode("He is an inert gas.")
    assert trace.tokens[0].lexical_evidence["selected_record"]["entry_id"] == "wordnet:he:helium.n.01"
    gas = next(t for t in trace.tokens if t.lemma == "gas")
    assert gas.pos == "NOUN" and "SYN_COMPL" in gas.sent_primitives
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, TypeAssertion)
    assert tree.entity.head.lemma == "he"
    assert emit_contract(tree)["predicate"]["op"] == "TYPE_ASSERT"


@pytest.mark.parametrize(
    "text,verb", [("He gases the room.", "gas"), ("He is moving.", "move"), ("He was killed.", "kill")]
)
def test_nominal_copula_repair_does_not_override_main_progressive_or_passive_verb(encoder, text, verb):
    tree = compose(encoder, text)
    assert isinstance(tree, Event) and tree.verb == verb
