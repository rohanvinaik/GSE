"""A modal auxiliary qualifies its event: "He might leave" is stated as possible, never as a fact (#66).

The clause builder reads the primes of the auxiliaries before the verb (the lexicon's, never the spelling) onto the
event, and the proposition walk projects them through ``modality.modal_force``. Driven through the real entry point.
"""

import logging

import pytest

from gse.api import GSEEncoder
from gse.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from gse.symbolic.modality import modal_force, modal_primes
from gse.symbolic.propositions import propositions
from gse.symbolic.serialization import from_dict, to_dict

logging.disable(logging.CRITICAL)


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _tree(encoder, sentence):
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


@pytest.mark.parametrize(
    ("sentence", "modal", "status"),
    [
        ("He might leave.", ["MAYBE"], "possible"),
        ("He may leave.", ["MAYBE"], "possible"),
        ("He would leave.", ["MAYBE"], "possible"),
        ("He can leave.", ["CAN"], "possible"),
        ("He could leave.", ["CAN"], "possible"),
        ("He must leave.", ["MUST"], "necessary"),
        ("He should leave.", ["MUST"], "necessary"),
    ],
)
def test_a_modal_event_is_not_asserted(encoder, sentence, modal, status):
    tree = _tree(encoder, sentence)
    assert emit_contract(tree)["predicate"]["features"]["modal"] == modal
    assert [(p.kind, p.status) for p in propositions(tree)] == [("Event", status)]


@pytest.mark.parametrize(
    "sentence",
    ["He leaves.", "He has left.", "He is leaving.", "He did leave.", "He will leave.", "He shall leave."],
)
def test_a_plain_clause_stays_asserted_with_an_unchanged_contract(encoder, sentence):
    tree = _tree(encoder, sentence)
    assert "modal" not in emit_contract(tree)["predicate"]["features"]
    assert [(p.kind, p.status) for p in propositions(tree)] == [("Event", "asserted")]


@pytest.mark.parametrize(
    ("sentence", "modal", "statuses"),
    [
        ("This should be clear.", ["MUST"], [("TypeAssertion", "necessary")]),
        ("It might be a dog.", ["MAYBE"], [("TypeAssertion", "possible")]),
        ("He should try to leave.", ["MUST"], [("Control", "necessary"), ("Event", "necessary")]),
        ("He might want to leave.", ["MAYBE"], [("Control", "possible"), ("Event", "possible")]),
    ],
)
def test_a_copular_or_control_clause_carries_its_modal(encoder, sentence, modal, statuses):
    tree = _tree(encoder, sentence)
    assert emit_contract(tree)["predicate"]["features"]["modal"] == modal
    assert [(p.kind, p.status) for p in propositions(tree)] == statuses


@pytest.mark.parametrize(("sentence", "kind"), [("Spot is a dog.", "TypeAssertion"), ("This cannot be true.", "NOT")])
def test_a_plain_or_negated_copula_keeps_its_status(encoder, sentence, kind):
    tree = _tree(encoder, sentence)
    statuses = [p.status for p in propositions(tree)]
    assert statuses == (["asserted"] if kind == "TypeAssertion" else ["negated"])


def test_a_content_verb_of_wanting_is_not_a_modal(encoder):
    statuses = [(p.kind, p.status) for p in propositions(_tree(encoder, "He wants to leave."))]
    assert statuses == [("Control", "asserted"), ("Event", "irrealis")]


def test_a_negation_outside_the_modal_wins(encoder):
    tree = _tree(encoder, "He might not leave.")
    assert emit_contract(tree)["predicate"]["args"][0]["features"]["modal"] == ["MAYBE"]
    assert [(p.kind, p.status) for p in propositions(tree)] == [("Event", "negated")]


def test_a_relative_clause_keeps_its_own_modal(encoder):
    statuses = [(p.kind, p.status) for p in propositions(_tree(encoder, "The king who might leave smiled."))]
    assert statuses == [("Event", "asserted"), ("RelativeRestriction", "asserted"), ("Event", "possible")]


@pytest.mark.parametrize("sentence", ["He might leave.", "He should leave.", "The king who might leave smiled."])
def test_the_modal_survives_serialization(encoder, sentence):
    tree = _tree(encoder, sentence)
    assert from_dict(to_dict(tree)) == tree


@pytest.mark.parametrize(
    ("aux_primes", "expected"),
    [
        ([], ()),
        ([{"MAYBE": 1}], ("MAYBE",)),
        ([{"MAYBE": 1}, {"HAVE": 1}], ("MAYBE",)),
        ([{"HAVE": 1}], ()),
        ([{"GOOD": 1, "WANT": 1}], ()),  # evaluation and volition are not modality (Bank 7)
        ([{"CAN": 1}, {"CAN": 1}], ("CAN",)),
        ([{"MAYBE": 0}, {"MUST": -1}], ()),
        (["not a map", None, {"MUST": 1}], ("MUST",)),
        ([{"CAN": "yes"}], ()),
    ],
)
def test_table_modal_primes(aux_primes, expected):
    assert modal_primes(aux_primes) == expected


@pytest.mark.parametrize(
    ("primes", "expected"),
    [
        ("", "asserted"),
        ("MAYBE", "possible"),
        ("CAN", "possible"),
        ("MUST", "necessary"),
        ("GOOD,WANT", "asserted"),
        ("WANT", "asserted"),
        ("MUST,MAYBE", "possible"),
        ("GOOD,MUST", "necessary"),
        (" MAYBE ", "possible"),
        ("HAVE", "asserted"),
    ],
)
def test_table_modal_force(primes, expected):
    assert modal_force(primes) == expected


# Direct calls that reach each branch of the clause-modal attachment (Detective's ask for _with_clause_modal).
def _token(lemma, pos, primes, position):
    from gse.api.trace import TokenTrace

    return TokenTrace(
        token=lemma, lemma=lemma, pos=pos, position=position, word_primitives=primes, sent_primitives={},
        word_vec_nnz=0, sent_vec_nnz=0, full_vec_nnz=0, is_operator=False, comp_primitive=None,
        comp_operation=None, comp_arity=0,
    )  # fmt: skip


_MIGHT_BE = [
    _token("it", "PRON", {"SOMETHING": 1}, 0),
    _token("might", "AUX", {"MAYBE": 1}, 1),
    _token("be", "AUX", {"BE": 1}, 2),
]
_IS = [_token("it", "PRON", {"SOMETHING": 1}, 0), _token("be", "AUX", {"BE": 1}, 1)]


def _copula(modal=()):
    from gse.symbolic.expression import Atom, Op

    return Op(primitive="COPULA", operation="TYPE_ASSERT", arity=2, args=[Atom(lemma="it"), Atom(lemma="dog")],
              modal=modal)  # fmt: skip


def test_the_clause_modal_lands_on_a_bare_op():
    from gse.symbolic.expression import _with_clause_modal

    assert _with_clause_modal(_copula(), _MIGHT_BE).modal == ("MAYBE",)


def test_the_clause_modal_lands_inside_a_negation():
    from gse.symbolic.expression import Negation, _with_clause_modal

    out = _with_clause_modal(Negation(operand=_copula()), _MIGHT_BE)
    assert isinstance(out, Negation) and out.operand.modal == ("MAYBE",)


def test_an_op_that_already_has_a_modal_keeps_it():
    from gse.symbolic.expression import _with_clause_modal

    assert _with_clause_modal(_copula(("CAN",)), _MIGHT_BE).modal == ("CAN",)


def test_a_clause_without_a_modal_auxiliary_is_unchanged():
    from gse.symbolic.expression import _with_clause_modal

    op = _copula()
    assert _with_clause_modal(op, _IS) is op


def test_a_leaf_or_a_negated_leaf_is_unchanged():
    from gse.symbolic.expression import Atom, Negation, _with_clause_modal

    leaf = Atom(lemma="it")
    assert _with_clause_modal(leaf, _MIGHT_BE) is leaf
    negated_leaf = Negation(operand=leaf)
    assert _with_clause_modal(negated_leaf, _MIGHT_BE) is negated_leaf


@pytest.mark.parametrize(
    ("sentence", "inner"),
    [
        ("I think he should leave.", ("leave", ["MUST"], "belief")),
        ("I think that he should leave.", ("leave", ["MUST"], "belief")),
        ("She knows he could leave.", ("leave", ["CAN"], "possible")),
        ("I think he left.", ("leave", [], "belief")),
    ],
)
def test_a_complement_keeps_its_modal(encoder, sentence, inner):
    """The complement builder drops its modal auxiliaries to build the event; their primes still qualify it. Under a
    belief the believing is the outer scope ("belief"); under a knowing, which commits, the modal decides."""
    last = propositions(_tree(encoder, sentence))[-1]
    assert (last.node.verb, list(last.node.modal), last.status) == inner
