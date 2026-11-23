"""Pin exact support counts for the event-bank learning measurement."""

from importlib import import_module

import pytest

from gse.curation.lexicon_builder.engine import Assertion, Relation, propagate
from gse.curation.lexicon_builder.grounded_rules import implication_rows

support_count = import_module(
    "docs.readings.2026-11-13-ssl-explicit-genera.coherence_020"
).support_count

BANKS = ("CAUSE", "DO", "HAPPEN", "MOVE", "SAY")
EVENTS = tuple(
    Relation(
        "event:" + bank, (bank, "HAPPEN"),
        implication_rows(((bank, 1),), ("HAPPEN", 1)), ("fixture:event",), "conditional", True,
    )
    for bank in ("CAUSE", "DO", "MOVE")
)
EXPRESSION = Relation(
    "expression", ("SAY", "DO"), implication_rows((("SAY", 1),), ("DO", 1)),
    ("fixture:expression",), "conditional", True,
)


def assertion(bank, value):
    return Assertion(bank, value, "fixture", "fixture:" + bank, "native", "lexical")


def test_known_speech_restricts_existing_correlated_event_support():
    # HAPPEN=1 admits 27 event triples; each other sign admits eight.
    before = propagate(BANKS, (assertion("SAY", 1),), EVENTS)
    after = propagate(BANKS, (assertion("SAY", 1),), (*EVENTS, EXPRESSION))
    assert support_count(before) == 27 + 2 * 8 == 43
    assert support_count(after) == 3 * 3 == 9
    assert after.domains["DO"] == after.domains["HAPPEN"] == frozenset({1})


def test_unknown_speech_gains_joint_information_without_singletons():
    before = propagate(BANKS, (), EVENTS)
    after = propagate(BANKS, (), (*EVENTS, EXPRESSION))
    assert support_count(before) == 3 * 43 == 129
    assert support_count(after) == 2 * 43 + 9 == 95
    assert before.domains == after.domains
    assert all(values == frozenset({-1, 0, 1}) for values in after.domains.values())


def test_explicit_speech_zero_preserves_event_freedom():
    state = propagate(BANKS, (assertion("SAY", 0),), (*EVENTS, EXPRESSION))
    assert support_count(state) == 43
    assert state.domains["SAY"] == frozenset({0})
    assert state.domains["DO"] == frozenset({-1, 0, 1})


def test_unknown_scope_does_not_activate_expression_prior():
    guarded = Relation(
        "guarded-expression", EXPRESSION.banks, EXPRESSION.allowed_rows,
        ("fixture:guarded-expression",), "conditional", True, (("scope", "witnessed"),),
    )
    state = propagate(BANKS, (), (*EVENTS, guarded), {})
    assert support_count(state) == 129
    assert state.domains["DO"] == frozenset({-1, 0, 1})


def test_conflict_never_receives_a_support_measurement():
    state = propagate(BANKS, (assertion("DO", 1), assertion("HAPPEN", 0)), EVENTS)
    with pytest.raises(ValueError, match="INCOMPLETE_SUPPORT"):
        support_count(state)


def test_limited_search_never_receives_an_exact_support_measurement():
    state = propagate(BANKS, (), EVENTS, max_joint_assignments=1)
    with pytest.raises(ValueError, match="INCOMPLETE_SUPPORT"):
        support_count(state)
