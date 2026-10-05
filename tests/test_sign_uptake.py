"""Where a negation's sign lands (#112): sentence_architecture.md L27, L45, L66 — a negation is a direction, taken by the
nearest operator or atomic after it — and how the signs landing on one node compose."""

import pytest

from gse.api import GSEEncoder
from gse.symbolic.expression import _sign_owners, node_polarity, sign_uptake


@pytest.mark.parametrize(
    ("negation", "kinds", "code"),
    [
        # an atomic takes it: "did not run" (SA L60), across function words and bare adverbs
        ("particle", ["content"], "content"),
        ("particle", ["gap", "pass", "content"], "content"),  # "not to the end"
        ("determiner", ["content"], "content"),  # "no idea"
        # an operator takes it: its own token, reached across determiners only, or the head it compares on
        ("particle", ["trigger"], "operator"),  # "not only"
        ("particle", ["pass", "trigger"], "operator"),  # "not the only"
        ("particle", ["head"], "operator"),  # "isn't cuter than" (SA L141)
        ("particle", ["gap", "head"], "operator"),  # "isn't really cuter than"
        ("determiner", ["head"], "operator"),  # "no more information than"
        # an intensifier takes it as its direction: "not very good" is Hier(-1)[GOOD] (SA L39-45)
        ("particle", ["hierarchy", "content"], "hierarchy"),
        # nothing can take it: no node is negated rather than a wrong one
        ("particle", [], "none"),  # "I hope not."
        ("particle", ["pass"], "none"),
        ("particle", ["gap", "trigger"], "none"),  # "not sure if": the if-clause is not negated
        ("determiner", ["trigger"], "none"),  # "start with no as a default": no determiner at all
    ],
)
def test_the_first_token_that_can_take_the_sign_takes_it(negation, kinds, code):
    assert sign_uptake(negation, kinds) == code


@pytest.mark.parametrize(
    ("negations", "polarity"),
    [
        ([], "affirmed"),
        (["not"], "negated"),
        (["not", "never"], "affirmed"),  # "He never did not answer": two signs cancel
        (["not", "not", "no"], "negated"),
        (["neither", "nor"], "negated"),  # "Neither John nor Mary came": one correlative negation
        (["nor"], "negated"),
        (["not", "nor"], "negated"),  # "He did not come, nor did she": nor continues the not
    ],
)
def test_signs_compose_and_a_correlative_negates_once(negations, polarity):
    assert node_polarity(negations) == polarity


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


@pytest.mark.parametrize(
    ("sentence", "negation", "code", "taker"),
    [
        ("Banquo did not see Macbeth.", "not", "content", "see"),
        ("Mike's dog isn't cuter than Rex.", "n't", "operator", "than"),
        ("Cells aren't just bright.", "n't", "operator", "just"),
        ("He left not because he was angry.", "not", "operator", "because"),
        ("The food was not very good.", "not", "hierarchy", "very"),  # the intensifier the encoder bound to good
        ("These members aren't really meant to be resolvers.", "n't", "content", "meant"),  # really is bound to nothing
        ("I think this doesn't work.", "n't", "content", "work"),
        ("No, I went home.", "No", "none", None),  # a sign never crosses punctuation
    ],
)
def test_a_negation_lands_on_the_token_after_it_that_can_take_it(encoder, sentence, negation, code, taker):
    tokens = encoder.encode(sentence).tokens
    by_position = {t.position: t for t in tokens}
    position = next(t.position for t in tokens if t.token == negation)
    landed, owner, _ = _sign_owners(tokens)[position]
    assert landed == code
    assert (by_position[owner].token if owner >= 0 else None) == taker
