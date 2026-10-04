"""
Logical inference — transitive closure over the clause graph (inference.py).

Type-syllogism over TypeAssertion + ordering over Comparison, with derivation
chains and direction-refusal. Hand-built trees make the graph logic
deterministic; the real encoder confirms it end-to-end on an LSAT-style problem.
"""


import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    KnowledgeBase,
    evaluate_tree,
    from_trace,
    resolve,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Comparison, TypeAssertion
from gse.symbolic.resolution import Entity


def _e(lemma):
    return Entity(head=Atom(lemma=lemma, word_primitives={}, role=None, position=0, pos="NOUN"))


def _isa(x, y):
    return TypeAssertion(entity=_e(x), kind=_e(y))


def _gt(x, y, sign=1):
    return Comparison(lhs=_e(x), rhs=_e(y), sign=sign, axis="size")


# -- mechanism (hand-built) -------------------------------------------------


def test_type_syllogism_with_chain():
    kb = KnowledgeBase.from_trees([_isa("bing", "woodle"), _isa("woodle", "zoodle"),
                                   _isa("zoodle", "floop")])
    d = kb.is_a("bing", "floop")
    assert d.holds
    assert d.chain == ("bing", "woodle", "zoodle", "floop")


def test_direction_not_entailed():
    kb = KnowledgeBase.from_trees([_isa("bing", "woodle"), _isa("woodle", "floop")])
    assert kb.is_a("bing", "floop").holds
    assert not kb.is_a("floop", "bing").holds        # no false positive


def test_ordering_transitivity_and_direction():
    kb = KnowledgeBase.from_trees([_gt("snib", "wug"), _gt("wug", "glonk")])
    up = kb.greater("snib", "glonk")
    assert up.holds and up.chain == ("snib", "wug", "glonk")
    assert not kb.greater("glonk", "snib").holds     # direction respected


def test_negative_sign_flips_ordering():
    # "snib is smaller than wug" → sign -1 → wug > snib
    kb = KnowledgeBase.from_trees([_gt("snib", "wug", sign=-1), _gt("wug", "glonk")])
    assert kb.greater("wug", "snib").holds
    assert not kb.greater("snib", "wug").holds


def test_unrelated_not_entailed():
    kb = KnowledgeBase.from_trees([_isa("a", "b"), _isa("c", "d")])
    assert not kb.is_a("a", "d").holds


def test_inference_is_deterministic():
    facts = [_isa("bing", "woodle"), _isa("woodle", "zoodle"), _isa("zoodle", "floop")]
    a = KnowledgeBase.from_trees(facts).is_a("bing", "floop")
    b = KnowledgeBase.from_trees(facts).is_a("bing", "floop")
    assert a.chain == b.chain


# -- end-to-end: a real LSAT-style problem ----------------------------------


def test_end_to_end_syllogism_and_ordering():
    premises = [
        "All woodles are zoodles",
        "All zoodles are floops",
        "Bing is a woodle",
        "A snib is bigger than a wug",
        "A wug is bigger than a glonk",
    ]
    with GSEEncoder() as enc:
        trees = [evaluate_tree(resolve(from_trace(enc.encode(s)))) for s in premises]
        kb = KnowledgeBase.from_trees(trees)
        assert kb.is_a("bing", "floop").holds
        assert kb.is_a("bing", "floop").chain == ("bing", "woodle", "zoodle", "floop")
        assert not kb.is_a("floop", "bing").holds
        assert kb.greater("snib", "glonk").holds
        assert not kb.greater("glonk", "snib").holds


# -- modus ponens over Conditional rules (2026-07-01) ------------------------


@pytest.fixture(scope="module")
def policy_kb():
    premises = [
        "Alice is a member.",
        "Bob is a member.",
        "If a member misses the payment then the member loses the vote.",
        "If a member loses the vote then the member leaves the board.",
        "Alice missed the payment.",
        "Carol did not miss the payment.",
    ]
    with GSEEncoder() as enc:
        trees = [evaluate_tree(resolve(from_trace(enc.encode(s)))) for s in premises]
    return KnowledgeBase.from_trees(trees)


def test_modus_ponens_fires_through_isa_binding(policy_kb):
    d = policy_kb.event("lose", "alice", "vote")
    assert d.holds
    assert "fact: alice miss payment" in d.chain[0]      # the antecedent's proof
    assert any("rule:" in step for step in d.chain)      # the rule is cited


def test_rule_chaining_two_steps(policy_kb):
    d = policy_kb.event("leave", "alice", "board")
    assert d.holds
    assert sum(1 for step in d.chain if step.startswith("rule:")) == 2


def test_no_fact_no_firing(policy_kb):
    assert not policy_kb.event("lose", "bob", "vote").holds     # member, but no fact
    assert not policy_kb.event("leave", "bob", "board").holds


def test_negated_fact_is_not_asserted(policy_kb):
    # "Carol did not miss the payment" must neither assert the fact nor fire the rule
    assert not policy_kb.event("miss", "carol", "payment").holds
    assert not policy_kb.event("lose", "carol", "vote").holds


def test_event_query_deterministic(policy_kb):
    a = policy_kb.event("leave", "alice", "board")
    b = policy_kb.event("leave", "alice", "board")
    assert a == b


# -- world-grounded reasoning: type_thread harvest + generic-patient binding --


def _et(lemma, thread=()):
    return Entity(head=Atom(lemma=lemma, word_primitives={}, role=None, position=0,
                            pos="PROPN"), type_thread=tuple(thread))


def test_resolved_thread_becomes_isa_edges():
    from gse.symbolic.predicates import Event
    ev = Event(verb="lead", agent=_et("napoleon", ("Thing", "Agent", "Person")),
               patient=_et("france", ("Thing", "Place", "Country")))
    kb = KnowledgeBase.from_trees([ev])
    d = kb.is_a("napoleon", "person")
    assert d.holds and d.chain == ("napoleon", "person")
    assert kb.is_a("france", "country").holds
    assert not kb.is_a("napoleon", "country").holds


def test_rule_binds_generic_patient_through_isa():
    from gse.symbolic.predicates import Conditional, Event

    def _plain(lemma):
        return Entity(head=Atom(lemma=lemma, word_primitives={}, role=None,
                                position=0, pos="NOUN"))

    rule = Conditional(
        antecedent=Event(verb="lead", agent=_plain("person"), patient=_plain("country")),
        consequent=Event(verb="command", agent=_plain("person"), patient=_plain("army")))
    fact = Event(verb="lead",
                 agent=_et("napoleon", ("Thing", "Agent", "Person")),
                 patient=_et("france", ("Thing", "Place", "Country")))
    kb = KnowledgeBase.from_trees([rule, fact])
    d = kb.event("command", "napoleon", "army")
    assert d.holds
    assert any("france" in step for step in d.chain)     # the patient binding is cited
    # a country is not a person: the rule must refuse to bind france as its subject
    assert not kb.event("command", "france", "army").holds
