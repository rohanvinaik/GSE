"""
KnowledgeBase asserts only what a sentence asserts (#7).

The defect: ``KnowledgeBase.from_trees`` flattened every tree through ``queries.predicates()`` and
ingested each Event it reached as a fact. A negated clause nested below the root became a
POSITIVE fact; an irrealis control verb's inner act ("refused to bow") and an attitude verb's
complement ("believes that Duncan is a traitor") were asserted; and a conditional with a negated
side became a positive rule ("if Rex does not bark, Mike leaves" → bark ⇒ leave), which then
derived conclusions the text contradicts.

The fix ingests each tree by its assertion modality (``gse.symbolic.modality.assertion_mode``),
the same decision the narrative skeleton applies. These tests drive the real pipeline and read
the knowledge base through its public queries.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import KnowledgeBase, evaluate_tree, from_trace, resolve


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _kb(encoder, *sentences):
    return KnowledgeBase.from_trees([evaluate_tree(resolve(from_trace(encoder.encode(s)))) for s in sentences])


def test_nested_negation_is_a_negative_fact_not_a_positive_one(encoder):
    kb = _kb(encoder, "Rex barks because Mike did not leave")
    assert not kb.event("leave", "mike").holds
    assert ("leave", "mike", None) in kb._neg_facts
    assert kb.event("bark", "rex").holds  # the asserted clause still lands


def test_negative_implicative_inner_act_is_not_asserted(encoder):
    assert not _kb(encoder, "Mordecai refused to bow").event("bow", "mordecai").holds


def test_desiderative_inner_act_is_not_asserted(encoder):
    assert not _kb(encoder, "Haman plots to kill the king").event("kill", "haman", "king").holds


def test_belief_complement_is_not_asserted_but_the_belief_is(encoder):
    kb = _kb(encoder, "Macbeth believes that Duncan is a traitor")
    assert not kb.is_a("duncan", "traitor").holds
    assert kb.event("believe", "macbeth").holds


def test_completive_control_still_asserts_the_caused_act(encoder):
    # persuade/order/force: the story convention asserts the inner act — unchanged by the fix.
    assert _kb(encoder, "Lady Macbeth persuaded Macbeth to kill the king").event("kill", "macbeth", "king").holds


def test_positive_conditional_still_licenses_modus_ponens(encoder):
    assert _kb(encoder, "If Rex barks, Mike leaves", "Rex barks").event("leave", "mike").holds


def test_negated_antecedent_does_not_become_a_positive_rule(encoder):
    # Before the fix: rule (rex bark ⇒ mike leave), so "Rex barks" derived "Mike leaves".
    assert not _kb(encoder, "If Rex does not bark, Mike leaves", "Rex barks").event("leave", "mike").holds


def test_negated_consequent_does_not_become_a_positive_rule(encoder):
    # Before the fix: rule (rex bark ⇒ mike leave) — the exact opposite of the sentence.
    assert not _kb(encoder, "If Rex barks, Mike does not leave", "Rex barks").event("leave", "mike").holds


def test_conditional_clauses_are_not_asserted_as_facts(encoder):
    kb = _kb(encoder, "If Rex barks, Mike leaves")
    assert not kb.event("bark", "rex").holds
    assert not kb.event("leave", "mike").holds
