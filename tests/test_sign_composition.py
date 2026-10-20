"""Two signs on one node cancel, for an operator and for a correlative; a quotation mark is no gap (#112, part B).

sentence_architecture.md L27: a negation is a direction, not an operation, so the signs that land on one node compose,
and two cancel. node_polarity's own rule: neither...nor is one sign; a nor beside another negation continues it.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from gse.symbolic.expression import _sign_owners, node_polarity


@pytest.mark.parametrize(
    ("negations", "polarity"),
    [
        ([], "affirmed"),
        (["not"], "negated"),
        (["not", "not"], "affirmed"),
        (["neither", "nor"], "negated"),
        (["neither"], "negated"),
        (["nor"], "negated"),
        (["not", "nor"], "negated"),
        (["neither", "nor", "not"], "affirmed"),
        (["neither", "not"], "affirmed"),
        (["never", "not", "nor"], "affirmed"),
        (["neither", "nor", "not", "never"], "negated"),
    ],
)
def test_signs_on_one_node_compose(negations, polarity):
    assert node_polarity(negations) == polarity


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _top(encoder, sentence):
    return emit_contract(evaluate_tree(resolve(from_trace(encoder.encode(sentence)))))["predicate"]


def test_two_signs_on_one_comparison_cancel(encoder):
    assert _top(encoder, "Mike's dog is not not cuter than Rex.")["op"] == "COMPARISON"


def test_one_sign_on_a_comparison_negates_it(encoder):
    top = _top(encoder, "Mike's dog is not cuter than Rex.")
    assert top["op"] == "NOT" and top["args"][0]["op"] == "COMPARISON"


def _landing(encoder, sentence, negation):
    tokens = sorted(encoder.encode(sentence).tokens, key=lambda t: t.position)
    for position, (code, owner, _lemma) in _sign_owners(tokens).items():
        if tokens[position].token.lower() == negation:
            return code, (tokens[owner].lemma if owner >= 0 else None)
    raise AssertionError(f"no {negation!r} in {sentence!r}")


def test_a_quotation_mark_is_no_gap(encoder):
    assert _landing(encoder, 'Not "combine them all into one" but take the information.', "not") == (
        "content",
        "combine",
    )


def test_other_punctuation_still_stops_a_sign(encoder):
    assert _landing(encoder, "He did not, and she left.", "not") == ("none", None)
