"""Ring 2 probes of GSE's reading through the real encoder: the sentence layer of the voice-profiler fix set.

The companion of test_reading_probes.py (Ring 1), in its own file so the two rings' writers never share one. Each case
is a constructed sentence stated as the reading GSE owes; a case GSE does not read yet is a strict xfail naming its
issue, and the fix that lands it takes the marker off in the same commit. Unmarked cases are guards. Ring 2 builds on
Ring 1, so a case may also need a Ring 1 fix (e.g. a sentence-initial imperative is first un-named by #94). Every
xfail names ``raises=AssertionError``: only the stated reading failing satisfies it, never an unrelated crash.
"""

import dataclasses
import json

import pytest

from gse.api import GSEEncoder
from gse.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from gse.symbolic.modality import assertion_mode


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _tree(encoder, sentence):
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


def _contract(encoder, sentence):
    return emit_contract(_tree(encoder, sentence))["predicate"]


def _ops(node):
    """Every operator node of a contract, outermost first."""
    if isinstance(node, list):
        return [op for item in node for op in _ops(item)]
    if not isinstance(node, dict):
        return []
    return [node, *_ops(node.get("args", []))]


def _verbs(encoder, sentence):
    return {op.get("features", {}).get("verb") for op in _ops(_contract(encoder, sentence)) if op.get("op") == "EVENT"}


def _marks(encoder, sentence):
    """Every sentence-scale mark any token of the sentence carries."""
    return {mark for t in encoder.encode(sentence).tokens for mark in (t.sent_primitives or {})}


# ── tense, mood and voice marks ───────────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#85 F-tense: an irregular past carries no tense")
def test_an_irregular_past_is_past(encoder):
    assert "SYN_TENSE_PAST" in _marks(encoder, "He took the key.")


def test_a_regular_past_is_past(encoder):
    assert "SYN_TENSE_PAST" in _marks(encoder, "Macbeth killed Duncan.")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#103 E-tam: no future or question mark is ever emitted")
def test_a_future_question_is_marked(encoder):
    assert {"SYN_TENSE_FUT", "SYN_MOOD_INTER"} <= _marks(encoder, "Will he come?")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#103 E-tam: no imperative mark is ever emitted")
def test_an_imperative_is_marked(encoder):
    assert "SYN_MOOD_IMPER" in _marks(encoder, "Close the door.")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#76 F-passive: a passive carries no voice mark")
def test_a_passive_is_marked(encoder):
    assert any("VOICE_PASS" in mark for mark in _marks(encoder, "Duncan was killed by Macbeth."))


# ── predicates: false ones out, real ones in ──────────────────────────────────────────────────────────────


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#82 F-plural-verb: a base verb after a noun subject is tagged NOUN"
)
@pytest.mark.parametrize(
    ("sentence", "verb"), [("These cells divide.", "divide"), ("The dividing cell split.", "split")]
)
def test_a_verb_after_a_noun_subject_is_the_predicate(encoder, sentence, verb):
    assert verb in _verbs(encoder, sentence)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#84 F-oov-verb: an unknown word is never a verb")
def test_an_unknown_verb_is_still_a_predicate(encoder):
    assert _verbs(encoder, "The wug blibbed the dax.") - {None}


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#83 F-promote: a compound member is promoted to a verb")
def test_a_compound_member_is_not_a_predicate(encoder):
    assert not _verbs(encoder, "Genesis is a Story Understanding System.") & {"understand", "understanding"}


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#92 F-closed-gaps: degree 'so' is read as a consequence link"
)
def test_degree_so_links_nothing(encoder):
    assert "CAUSATION" not in {op.get("op") for op in _ops(_contract(encoder, "It was so good."))}


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#115 S-operator-event: a within-clause operator replaces the clause's event",
)
def test_an_operator_keeps_its_clause_event(encoder):
    assert "validate" in _verbs(encoder, "You can even validate it by hand.")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#116 S-unary: WHAT and ONLY take the empty left window")
def test_a_unary_operator_takes_its_operand(encoder):
    queries = [op for op in _ops(_contract(encoder, "What is a dog?")) if op.get("op") == "TYPE_QUERY"]
    assert queries and "dog" in json.dumps(queries[0].get("args"))
    assert "sleep" in _verbs(encoder, "Only the king slept.")


# ── clause linking and status ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#100 E-if-when: 'wonder if' is read as a conditional")
def test_wonder_if_is_a_complement_not_a_conditional(encoder):
    assert "IMPLIES" not in {op.get("op") for op in _ops(_contract(encoder, "I wonder if he left."))}


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#101 E-fronted: a fronted 'if' without a comma gives a one-armed conditional",
)
def test_a_fronted_conditional_has_both_arms(encoder):
    conditionals = [op for op in _ops(_contract(encoder, "If it rains we stay.")) if op.get("op") == "IMPLIES"]
    assert conditionals
    arms = [arm.get("features", {}).get("verb") for arm in conditionals[0]["args"] if isinstance(arm, dict)]
    assert sorted(arms) == ["rain", "stay"]


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#131 S-contrast: CONTRAST stays within-clause and keeps no events"
)
def test_a_contrast_keeps_both_clauses(encoder):
    assert {"come", "leave"} <= _verbs(encoder, "He came, but she left.")


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="#114 S-embedded: a complement under a coordinated verb is dropped"
)
def test_an_embedded_clause_is_kept(encoder):
    assert "leave" in _verbs(encoder, "He laughed and said that she left.")


def _negated(encoder, sentence):
    """Each node a NOT wraps in the sentence's contract, as (op, verb)."""
    return [
        (op["args"][0].get("op"), op["args"][0].get("features", {}).get("verb"))
        for op in _ops(_contract(encoder, sentence))
        if op.get("op") == "NOT" and op.get("args") and isinstance(op["args"][0], dict)
    ]


@pytest.mark.parametrize(
    ("sentence", "negated"),
    [
        ("Mike's dog isn't cuter than Rex.", [("COMPARISON", None)]),  # SA L141: the comparison takes the sign
        ("Rex doesn't run faster than Mike.", [("COMPARISON", None)]),
        ("Cells aren't just universally bright.", [("MIN_SUFFICIENCY", None)]),
        ("He left not because he was angry.", [("CAUSATION", None)]),  # he left; the because is denied
        ("He did not decide to go.", [("CONTROL", "decide")]),
        ("He decided not to go.", [("EVENT", "go")]),  # the inner act, never decide
        ("The man who never smiled left the town.", [("EVENT", "smile")]),  # the relative's own event
        ("She doesn't know that the door is open.", [("EVENT", "know")]),
        ("I think this doesn't work.", []),  # n't is work's, never think's; work waits for its own clause
        ("No, I went home.", []),  # a sign never crosses punctuation
        ("He never did not answer.", []),  # two signs cancel
        ("Neither John nor Mary came.", [("EVENT", "come")]),  # one correlative negation
    ],
)
def test_a_negation_negates_the_node_that_takes_its_sign(encoder, sentence, negated):
    assert _negated(encoder, sentence) == negated


def test_a_negated_matrix_keeps_its_complement(encoder):
    (know,) = [
        op for op in _ops(_contract(encoder, "She doesn't know that the door is open.")) if op.get("op") == "EVENT"
    ]
    assert any(isinstance(arg, dict) and arg.get("op") == "TYPE_ASSERT" for arg in know["args"])


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#88 F-pred-adj: after 'was not' the adjective is tagged ADV, so the copula has no complement",
)
def test_a_negated_predicate_adjective_is_a_negated_assertion(encoder):
    assert _negated(encoder, "The food was not good.") == [("TYPE_ASSERT", None)]


def test_a_negated_belief_complement_is_believed_not_asserted(encoder):
    tree = _tree(encoder, "Macbeth believes that Banquo did not see him.")
    stack, beliefs = [tree], []
    while stack:
        node = stack.pop()
        if isinstance(node, (list, tuple)):
            stack.extend(node)
        elif dataclasses.is_dataclass(node) and not isinstance(node, type):
            if type(node).__name__ == "Event" and getattr(node, "verb", None) == "believe":
                beliefs.append(node)
            stack.extend(getattr(node, f.name) for f in dataclasses.fields(node))
    assert beliefs
    assert assertion_mode("Event", "believe", type(beliefs[0].patient).__name__) == "belief"
