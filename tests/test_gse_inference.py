"""
Logical inference — transitive closure over the clause graph (inference.py).

Type-syllogism over TypeAssertion + ordering over Comparison, with derivation
chains and direction-refusal. Hand-built trees make the graph logic
deterministic; the real encoder confirms it end-to-end on an LSAT-style problem.
"""

from pathlib import Path

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
