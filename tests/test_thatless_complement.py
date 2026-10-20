"""#114 (the rest): a clausal complement opened without "that" reads exactly like one opened with it.

Through the real entry point (encoder -> from_trace -> resolve -> evaluate_tree -> propositions), each proposition's
status for a that-less sentence equals the status for its "that" twin: the content of an attitude verb is a belief,
a denied thinking leaves it abstained, an epistemic verb's content is asserted. A verb followed by no full clause
opens no complement. The table tests pin the pure decision ``thatless_complement``.
"""

import importlib

import pytest

from gse.api import GSEEncoder
from gse.api.encoder import thatless_complement
from gse.symbolic import evaluate_tree, from_trace, resolve

propositions = importlib.import_module("gse.symbolic.propositions")


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _statuses(encoder, sentence):
    tree = evaluate_tree(resolve(from_trace(encoder.encode(sentence))))
    return {
        getattr(p.node, "verb", None) or type(p.node).__name__: propositions.proposition_status(
            [scope.mode for scope in p.scopes]
        )
        for p in propositions.propositions(tree)
    }


@pytest.mark.parametrize(
    ("thatless", "with_that"),
    [
        ("I don't think the door is open.", "I don't think that the door is open."),
        ("I think the door is open.", "I think that the door is open."),
        ("She knows the cell divides.", "She knows that the cell divides."),
        ("We believe these results hold.", "We believe that these results hold."),
    ],
)
def test_flip_a_thatless_complement_reads_like_its_that_twin(encoder, thatless, with_that):
    assert _statuses(encoder, thatless) == _statuses(encoder, with_that)


def test_flip_a_thatless_attitude_complement_is_a_belief(encoder):
    assert _statuses(encoder, "I think the door is open.").get("TypeAssertion") == "belief"


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("I think it.", {"think": "asserted"}),
        ("I know the answer.", {"know": "asserted"}),
        ("I think about the door.", {"think": "asserted"}),
        ("I feel the cold air.", {"feel": "asserted"}),
    ],
)
def test_guard_no_full_clause_opens_no_complement(encoder, sentence, expected):
    assert _statuses(encoder, sentence) == expected


@pytest.mark.parametrize(
    ("verb", "nxt", "roles", "code"),
    [
        ("say", "the", ["OPENER", "NOMINAL", "PREDICATE"], "NOT_A_COMPLEMENT_VERB"),
        ("", "that", [], "NOT_A_COMPLEMENT_VERB"),
        ("say", "that", ["OTHER", "NOMINAL", "PREDICATE"], "NOT_A_COMPLEMENT_VERB"),
        ("think", "that", ["OTHER", "OPENER", "NOMINAL", "PREDICATE"], "THAT"),
        ("think", "the", ["OPENER", "NOMINAL", "PREDICATE", "OPENER"], "COMPLEMENT"),
        ("believe", "cells", ["NOMINAL", "PREDICATE"], "COMPLEMENT"),
        ("know", "the", ["OPENER", "OPENER", "NOMINAL", "PREDICATE"], "COMPLEMENT"),
        ("think", "it", ["NOMINAL"], "NO_PREDICATE"),
        ("know", "the", ["OPENER", "NOMINAL"], "NO_PREDICATE"),
        ("think", "about", ["OTHER", "OPENER", "NOMINAL"], "NO_SUBJECT"),
        ("think", "the", ["OPENER", "OPENER"], "NO_SUBJECT"),
        ("think", ".", [], "NO_SUBJECT"),
        ("expect", "the", ["OPENER", "NOMINAL", "OTHER", "OTHER"], "NO_PREDICATE"),
    ],
)
def test_table_thatless_complement(verb, nxt, roles, code):
    assert thatless_complement(verb, nxt, roles) == code
