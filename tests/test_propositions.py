"""One signed-propositions extraction (#15): every predicate with its ordered scopes, and status as the lossy projection.

Through the real encoder. The record keeps what the one-code status flattens: each scope's mode, the node that imposes
it (so a belief's attitude verb stays readable: factive "know" against "believe") and the field it governs.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import evaluate_tree, from_trace, resolve

# From the defining module, not the package re-export, so a test calls the function Detective patches.
from gse.symbolic.propositions import proposition_status, propositions


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
    # "cannot" is can + not: the negation is outermost, over the modal's own scope (#66), and it decides the status.
    assert (swim.status, _modes(swim)) == ("negated", ["negated", "possible"])


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
    ("sentence", "verb", "status"),
    [
        ("He knows that the door is open.", "know", "asserted"),
        ("She doesn't know that the door is open.", "know", "negated"),
    ],
)
def test_a_knowing_verb_is_asserted_or_negated_as_stated(encoder, sentence, verb, status):
    assert _with_verb(encoder, sentence, verb).status == status


@pytest.mark.parametrize(
    ("sentence", "status"),
    [
        # 00:21:44: an unnegated knowing commits its complement.
        ("He knows that the door is open.", "asserted"),
        # 00:28:45: "Not knowing" is the same as abstention on the question of truth.
        ("She doesn't know that the door is open.", "abstained"),
    ],
)
def test_a_knowing_commits_its_complement_and_a_denied_knowing_abstains(encoder, sentence, status):
    (door,) = [
        p
        for p in propositions(evaluate_tree(resolve(from_trace(encoder.encode(sentence)))))
        if p.kind == "TypeAssertion"
    ]
    assert door.status == status


def test_a_denied_belief_leaves_its_content_unknown(encoder):
    # 01:37:36: "The "not" applies to thinking … It's not about the truth value of the actual "X", which is unkown"
    props = propositions(
        evaluate_tree(resolve(from_trace(encoder.encode("Macbeth does not believe that Banquo saw him."))))
    )
    (believe,) = [p for p in props if getattr(p.node, "verb", None) == "believe"]
    (content,) = [p for p in props if p.node is believe.node.patient]
    assert (believe.status, content.status) == ("negated", "abstained")


@pytest.mark.parametrize(
    ("modes", "status"),
    [
        ([], "asserted"),
        (["negated"], "negated"),
        (["belief", "negated"], "belief"),  # "thinks she did not leave": the outermost scope wins
        (["asserted", "conditional"], "conditional"),
        # The knowability rulings: a negation over a believing or knowing verb leaves its content unknown.
        (["negated", "belief"], "abstained"),  # "I don't think X"
        (["negated", "epistemic"], "abstained"),  # "She doesn't know that X"
        (["negated", "epistemic", "negated"], "abstained"),  # "She doesn't know that he did not leave"
        (["negated", "conditional", "belief"], "abstained"),
        # A knowing is transparent: it commits its complement, whose own negation stays its own.
        (["epistemic"], "asserted"),  # "He knows that X"
        (["epistemic", "negated"], "negated"),  # "He knows that she did not leave"
        (["epistemic", "belief"], "belief"),  # "He knows that she believes X"
        (["conditional", "negated", "belief"], "conditional"),  # the outer barrier still wins
        (["negated", "irrealis"], "negated"),  # no ruling covers irrealis under a negation
    ],
)
def test_the_status_projection(modes, status):
    assert proposition_status(modes) == status
