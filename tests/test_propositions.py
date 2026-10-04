"""One signed-propositions extraction (#15): every predicate with its ordered scopes, and status as the lossy projection.

Through the real encoder. The record keeps what the one-code status flattens: each scope's mode, the node that imposes
it (so a belief's attitude verb stays readable: factive "know" against "believe") and the field it governs.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import evaluate_tree, from_trace, proposition_status, propositions, resolve


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _with_verb(encoder, sentence, verb):
    found = [
        p
        for p in propositions(evaluate_tree(resolve(from_trace(encoder.encode(sentence)))))
        if getattr(p.node, "verb", None) == verb
    ]
    assert len(found) == 1, f"{verb!r} in {sentence!r}"
    return found[0]


def _modes(proposition):
    return [scope.mode for scope in proposition.scopes]


def test_a_plain_event_is_stated_outright(encoder):
    kill = _with_verb(encoder, "Macbeth killed Duncan.", "kill")
    assert (kill.status, kill.scopes) == ("asserted", ())


def test_a_negated_event_is_negated(encoder):
    swim = _with_verb(encoder, "Birds cannot swim.", "swim")
    assert (swim.status, _modes(swim)) == ("negated", ["negated"])


def test_a_belief_complement_keeps_its_attitude_verb_and_its_negation(encoder):
    sentence = "Macbeth believes that Banquo did not see him."
    assert _with_verb(encoder, sentence, "believe").status == "asserted"
    see = _with_verb(encoder, sentence, "see")
    assert (see.status, _modes(see)) == ("belief", ["belief", "negated"])
    assert (see.scopes[0].owner.verb, see.scopes[0].field) == ("believe", "patient")


def test_a_conditional_states_neither_arm(encoder):
    sentence = "If it rains, we stay."
    for verb, arm in (("rain", "antecedent"), ("stay", "consequent")):
        event = _with_verb(encoder, sentence, verb)
        assert (event.status, event.scopes[0].owner_kind, event.scopes[0].field) == ("conditional", "Conditional", arm)


@pytest.mark.parametrize(
    ("sentence", "matrix", "inner"),
    [("Haman plots to kill Mordecai.", "plot", "kill"), ("Mordecai refused to bow.", "refuse", "bow")],
)
def test_an_irrealis_inner_act_is_not_asserted(encoder, sentence, matrix, inner):
    assert _with_verb(encoder, sentence, matrix).status == "asserted"
    assert _with_verb(encoder, sentence, inner).status == "irrealis"


@pytest.mark.parametrize("tree", [None, "", "text", [], (), 0])
def test_nothing_to_walk_yields_nothing(tree):
    assert propositions(tree) == []


@pytest.mark.parametrize(
    ("modes", "status"),
    [
        ([], "asserted"),
        (["negated"], "negated"),
        (["belief", "negated"], "belief"),  # the outermost scope wins: lossy, kept in the scopes
        (["negated", "belief"], "negated"),  # "doesn't believe X": X is believed content, the code says negated
        (["asserted", "conditional"], "conditional"),
    ],
)
def test_the_status_projection_is_the_outermost_scope(modes, status):
    assert proposition_status(modes) == status
