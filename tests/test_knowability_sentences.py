"""Knowability through the real entry point and its consumer (#125; the gaps a Codex audit of a1df536 named).

The founder, 2026-10-05: on "I don't think X" (01:37), "The "not" applies to thinking ... It's not about the truth value
of the actual "X", which is unkown"; on knowing (00:28:45), ""Not knowing" is the same as abstention on the question
of truth". know and realize commit their complement; a denied knowing or believing abstains on it.
"""

import importlib

import pytest

from gse.api import GSEEncoder
from gse.symbolic import KnowledgeBase, evaluate_tree, from_trace, resolve

propositions = importlib.import_module("gse.symbolic.propositions")


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _tree(encoder, sentence):
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


def _statuses(encoder, sentence):
    """Each proposition's status, keyed by its verb (or its kind when it has none)."""
    return {
        getattr(p.node, "verb", None) or type(p.node).__name__: propositions.proposition_status(
            [scope.mode for scope in p.scopes]
        )
        for p in propositions.propositions(_tree(encoder, sentence))
    }


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("I don't think that the door is open.", {"think": "negated", "TypeAssertion": "abstained"}),
        ("She realizes that the door is open.", {"realize": "asserted", "TypeAssertion": "asserted"}),
        ("She does not realize that the door is open.", {"realize": "negated", "TypeAssertion": "abstained"}),
        ("He knows that she did not leave.", {"know": "asserted", "leave": "negated"}),
    ],
)
def test_knowability_through_the_encoder(encoder, sentence, expected):
    assert _statuses(encoder, sentence) == expected


def test_a_thatless_denied_thinking_abstains(encoder):
    assert _statuses(encoder, "I don't think the door is open.").get("TypeAssertion") == "abstained"


def _kb(encoder, sentence):
    return KnowledgeBase.from_trees([_tree(encoder, sentence)])


def test_a_realizing_commits_its_content_to_the_knowledge_base(encoder):
    kb = _kb(encoder, "Macbeth realizes that Duncan is a traitor.")
    assert kb.is_a("duncan", "traitor").holds and kb.event("realize", "macbeth").holds


def test_a_denied_realizing_withholds_its_content_without_denying_it(encoder):
    kb = _kb(encoder, "Macbeth does not realize that Duncan is a traitor.")
    assert not kb.is_a("duncan", "traitor").holds
    assert sorted(kb._neg_facts) == [("realize", "macbeth", None)]  # only the realizing is denied


def test_a_knowing_commits_a_negated_content_as_a_negative_fact(encoder):
    kb = _kb(encoder, "Macbeth knows that Banquo did not leave.")
    assert ("leave", "banquo", None) in kb._neg_facts and kb.event("know", "macbeth").holds
