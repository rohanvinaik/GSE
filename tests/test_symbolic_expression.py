"""Phase B1 tests — AST node types + from_trace builder.

Verifies the structural transformation from OperationTrace into a typed
Expression tree. No semantics tested here (that's B2/B3).
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic.expression import (
    Atom,
    Negation,
    Op,
    Phrase,
    from_trace,
)


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


class TestAstNodes:
    """Smoke tests on the node dataclasses themselves."""

    def test_atom_holds_lemma_and_primitives(self):
        a = Atom(lemma="dog", word_primitives={"ALIVE": 1, "BODY": 1})
        assert a.lemma == "dog"
        assert a.word_primitives["ALIVE"] == 1

    def test_atom_is_hashable(self):
        # Frozen dataclass + custom __hash__
        a = Atom(lemma="dog", word_primitives={"ALIVE": 1})
        b = Atom(lemma="dog", word_primitives={"ALIVE": 1})
        assert hash(a) == hash(b)

    def test_phrase_carries_atom_list(self):
        p = Phrase(atoms=[Atom("a"), Atom("b")])
        assert len(p.atoms) == 2

    def test_negation_wraps_an_expression(self):
        n = Negation(operand=Atom("good"))
        assert isinstance(n.operand, Atom)
        assert n.operand.lemma == "good"

    def test_op_has_operation_and_args(self):
        a = Atom("dog")
        b = Atom("cat")
        op = Op(primitive="COMP_THAN", operation="SET_DIFF", arity=2, args=[a, b])
        assert op.operation == "SET_DIFF"
        assert op.arity == 2
        assert op.args == [a, b]


class TestFromTraceNoOperators:
    """Sentences without compositional operators should produce Atoms/Phrases."""

    def test_single_word_returns_atom(self, encoder):
        trace = encoder.encode("dog")
        expr = from_trace(trace)
        assert isinstance(expr, Atom)
        assert expr.lemma == "dog"

    def test_multi_word_returns_phrase(self, encoder):
        trace = encoder.encode("the dog ran fast")
        expr = from_trace(trace)
        assert isinstance(expr, Phrase)
        # spaCy lemmatizes "ran" to "run"
        lemmas = {a.lemma for a in expr.atoms}
        assert {"dog", "run"} <= lemmas


class TestFromTraceComparisonOperator:
    """A sentence with COMP_THAN should produce an Op node."""

    def test_than_lifts_to_set_diff_op(self, encoder):
        trace = encoder.encode("Mike is taller than Rex")
        expr = from_trace(trace)
        assert isinstance(expr, Op)
        assert expr.primitive == "COMP_THAN"
        assert expr.operation == "SET_DIFF"
        assert expr.arity == 2
        assert len(expr.args) == 2

    def test_than_args_have_mike_and_rex(self, encoder):
        trace = encoder.encode("Mike is taller than Rex")
        expr = from_trace(trace)
        assert isinstance(expr, Op)
        # Collect all lemmas across both args (handles Phrase or Atom)
        def _lemmas(e):
            if isinstance(e, Atom):
                return {e.lemma}
            if isinstance(e, Phrase):
                return {a.lemma for a in e.atoms}
            if isinstance(e, Negation):
                return _lemmas(e.operand)
            if isinstance(e, Op):
                out = set()
                for a in e.args:
                    out |= _lemmas(a)
                return out
            return set()

        all_lemmas = set()
        for a in expr.args:
            all_lemmas |= _lemmas(a)
        assert "mike" in all_lemmas
        assert "rex" in all_lemmas


class TestFromTraceAllCompOperators:
    """All 10 operators should lift cleanly with correct operation labels."""

    @pytest.mark.parametrize("sentence,expected_primitive,expected_operation,expected_arity", [
        ("Mike is taller than Rex",          "COMP_THAN",   "SET_DIFF",       2),
        ("Mike is tall as Rex",              "COMP_AS",     "BIND_EQ",        2),
        ("How tall is Mike?",                "COMP_HOW",    "DEGREE_QUERY",   1),
        ("What is Mike?",                    "COMP_WHAT",   "TYPE_QUERY",     1),
        ("Mike has just enough food",        "COMP_JUST",   "CARD_LOWER",     2),
        ("Only Mike sings",                  "COMP_ONLY",   "SET_RESTRICT",   1),
        ("Even Mike sings",                  "COMP_EVEN",   "SCALAR_EXTREME", 1),
        ("Mike sings but Rex runs",          "COMP_BUT",    "CONTRAST",       2),
        ("Mike sang so Rex left",            "COMP_SO",     "CONSEQUENCE",    2),
        ("Mike left because Rex sang",       "COMP_BECAUSE","CAUSAL_SOURCE",  2),
    ])
    def test_operator_lifts_with_correct_label(
        self, encoder, sentence, expected_primitive, expected_operation, expected_arity
    ):
        trace = encoder.encode(sentence)
        expr = from_trace(trace)
        # Find the Op in the AST (may be nested if there are multiple operators)
        op = _find_op(expr, expected_primitive)
        assert op is not None, (
            f"No Op({expected_primitive}) found in AST built from {sentence!r}"
        )
        assert op.operation == expected_operation
        assert op.arity == expected_arity


class TestFromTraceNegation:
    """Sentences with NOT should produce Negation nodes in the AST."""

    def test_not_run_wraps_run_atom_in_negation(self, encoder):
        # Test "He did not run" — encoder should pull NOT into arg span
        # of some operator, OR the bare phrase should include negation
        # at the top level.
        trace = encoder.encode("Mike did not run")
        expr = from_trace(trace)
        # No COMP_* operator here — should be a Phrase or a Negation
        assert _contains_negation(expr) or _contains_lemma(expr, "not"), (
            f"NOT not surfaced in AST for 'Mike did not run': {expr!r}"
        )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _find_op(expr, primitive_name):
    """Locate an Op node by primitive name anywhere in the tree."""
    if isinstance(expr, Op):
        if expr.primitive == primitive_name:
            return expr
        for a in expr.args:
            found = _find_op(a, primitive_name)
            if found is not None:
                return found
    elif isinstance(expr, Negation):
        return _find_op(expr.operand, primitive_name)
    return None


def _contains_negation(expr):
    if isinstance(expr, Negation):
        return True
    if isinstance(expr, Op):
        return any(_contains_negation(a) for a in expr.args)
    return False


def _contains_lemma(expr, lemma):
    if isinstance(expr, Atom):
        return expr.lemma == lemma
    if isinstance(expr, Phrase):
        return any(a.lemma == lemma for a in expr.atoms)
    if isinstance(expr, Negation):
        return _contains_lemma(expr.operand, lemma)
    if isinstance(expr, Op):
        return any(_contains_lemma(a, lemma) for a in expr.args)
    return False
