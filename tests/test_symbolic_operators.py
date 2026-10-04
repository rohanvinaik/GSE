"""Phase B2 tests — per-operator semantic functions.

Verifies each of the 10 dispatch functions produces the correct
Predicate type and content from the corresponding Op node. Plus
``evaluate_tree`` for nested operators.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    BoundaryCase,
    Causation,
    Comparison,
    Contrast,
    DegreeQuery,
    Equality,
    MinimalSufficiency,
    Op,
    SetRestriction,
    TypeQuery,
    UnknownOperation,
    evaluate,
    evaluate_tree,
    from_trace,
)
from gse.symbolic.expression import Atom


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _atom(lemma: str) -> Atom:
    return Atom(lemma=lemma, word_primitives={}, position=0)


# ---------------------------------------------------------------------------
# Per-operator unit tests using synthetic Op nodes
# ---------------------------------------------------------------------------


class TestSetDiffOperator:
    def test_returns_comparison(self):
        op = Op(primitive="COMP_THAN", operation="SET_DIFF", arity=2, args=[_atom("mike"), _atom("rex")])
        pred = evaluate(op)
        assert isinstance(pred, Comparison)
        assert pred.lhs.lemma == "mike"
        assert pred.rhs.lemma == "rex"
        assert pred.sign == +1


class TestBindEqOperator:
    def test_returns_equality(self):
        op = Op(primitive="COMP_AS", operation="BIND_EQ", arity=2, args=[_atom("mike"), _atom("rex")])
        pred = evaluate(op)
        assert isinstance(pred, Equality)
        assert pred.lhs.lemma == "mike"
        assert pred.rhs.lemma == "rex"


class TestDegreeQueryOperator:
    def test_returns_degree_query(self):
        op = Op(primitive="COMP_HOW", operation="DEGREE_QUERY", arity=1, args=[_atom("mike")])
        pred = evaluate(op)
        assert isinstance(pred, DegreeQuery)
        assert pred.entity.lemma == "mike"


class TestTypeQueryOperator:
    def test_returns_type_query(self):
        op = Op(primitive="COMP_WHAT", operation="TYPE_QUERY", arity=1, args=[_atom("mike")])
        pred = evaluate(op)
        assert isinstance(pred, TypeQuery)
        assert pred.entity.lemma == "mike"


class TestCardLowerOperator:
    def test_returns_minimal_sufficiency(self):
        op = Op(primitive="COMP_JUST", operation="CARD_LOWER", arity=2, args=[_atom("mustard"), _atom("ben")])
        pred = evaluate(op)
        assert isinstance(pred, MinimalSufficiency)
        assert pred.threshold.lemma == "mustard"
        assert pred.purpose.lemma == "ben"


class TestSetRestrictOperator:
    def test_returns_set_restriction(self):
        op = Op(primitive="COMP_ONLY", operation="SET_RESTRICT", arity=1, args=[_atom("mike")])
        pred = evaluate(op)
        assert isinstance(pred, SetRestriction)
        assert pred.member.lemma == "mike"


class TestScalarExtremeOperator:
    """EVEN is v1 placeholder per user decision — no scalar-extreme assertion."""

    def test_returns_boundary_case_placeholder(self):
        op = Op(primitive="COMP_EVEN", operation="SCALAR_EXTREME", arity=1, args=[_atom("mike")])
        pred = evaluate(op)
        assert isinstance(pred, BoundaryCase)
        assert pred.entity.lemma == "mike"
        assert "deferred" in pred.note.lower()

    def test_does_not_assert_universal(self):
        # v1 explicitly does NOT assert "all more-expected cases also satisfy
        # the predicate." Test the absence.
        op = Op(primitive="COMP_EVEN", operation="SCALAR_EXTREME", arity=1, args=[_atom("mike")])
        pred = evaluate(op)
        # BoundaryCase has no `universal` or `quantified` field — by
        # design. The placeholder is intentionally minimal.
        assert not hasattr(pred, "universal")
        assert not hasattr(pred, "quantified")


class TestContrastOperator:
    def test_returns_contrast(self):
        op = Op(primitive="COMP_BUT", operation="CONTRAST", arity=2, args=[_atom("sings"), _atom("runs")])
        pred = evaluate(op)
        assert isinstance(pred, Contrast)
        assert pred.left.lemma == "sings"
        assert pred.right.lemma == "runs"


class TestConsequenceOperator:
    """SO — left is cause, right is effect."""

    def test_so_makes_left_the_cause(self):
        op = Op(primitive="COMP_SO", operation="CONSEQUENCE", arity=2, args=[_atom("sang"), _atom("left")])
        pred = evaluate(op)
        assert isinstance(pred, Causation)
        assert pred.cause.lemma == "sang"
        assert pred.effect.lemma == "left"
        assert pred.conjunction == "so"


class TestCausalSourceOperator:
    """BECAUSE — left is effect, right is cause. Inverse of SO."""

    def test_because_swaps_direction(self):
        op = Op(primitive="COMP_BECAUSE", operation="CAUSAL_SOURCE", arity=2, args=[_atom("left"), _atom("sang")])
        pred = evaluate(op)
        assert isinstance(pred, Causation)
        # User spec: "X because Y" → Y is cause, X is effect.
        assert pred.cause.lemma == "sang"
        assert pred.effect.lemma == "left"
        assert pred.conjunction == "because"

    def test_because_equivalent_to_so_with_args_swapped(self):
        # User spec: "Equivalent to CONSEQUENCE with args swapped."
        because = evaluate(
            Op(primitive="COMP_BECAUSE", operation="CAUSAL_SOURCE", arity=2, args=[_atom("left"), _atom("sang")])
        )
        so = evaluate(Op(primitive="COMP_SO", operation="CONSEQUENCE", arity=2, args=[_atom("sang"), _atom("left")]))
        assert because.cause.lemma == so.cause.lemma
        assert because.effect.lemma == so.effect.lemma


# ---------------------------------------------------------------------------
# Arity errors
# ---------------------------------------------------------------------------


class TestArityErrors:
    def test_wrong_arity_raises(self):
        # SET_DIFF expects arity 2; pass arity=1
        op = Op(primitive="COMP_THAN", operation="SET_DIFF", arity=1, args=[_atom("mike")])
        with pytest.raises(ValueError, match="expects arity 2"):
            evaluate(op)

    def test_unknown_operation_raises(self):
        op = Op(primitive="FAKE", operation="DOES_NOT_EXIST", arity=2, args=[_atom("a"), _atom("b")])
        with pytest.raises(UnknownOperation):
            evaluate(op)


# ---------------------------------------------------------------------------
# Dispatch coverage — every COMP_METADATA entry has a dispatch
# ---------------------------------------------------------------------------


class TestDispatchCoverage:
    def test_all_comp_metadata_operations_have_dispatch(self):
        from gse.primitives_v2 import COMP_METADATA
        from gse.symbolic.operators import OPERATION_DISPATCH

        for prim, meta in COMP_METADATA.items():
            op_label = meta["operation"]
            assert op_label in OPERATION_DISPATCH, (
                f"COMP_METADATA[{prim}] declares operation {op_label!r} but no dispatch function exists"
            )


# ---------------------------------------------------------------------------
# End-to-end: encoded sentence → AST → Predicate
# ---------------------------------------------------------------------------


class TestEndToEndEvaluation:
    @pytest.mark.parametrize(
        "sentence,expected_predicate_type",
        [
            ("Mike is taller than Rex", Comparison),
            ("Mike is tall as Rex", Equality),
            ("How tall is Mike?", DegreeQuery),
            ("What is Mike?", TypeQuery),
            ("Mike has just enough food", MinimalSufficiency),
            ("Only Mike sings", SetRestriction),
            ("Even Mike sings", BoundaryCase),
            ("Mike sings but Rex runs", Contrast),
            ("Mike sang so Rex left", Causation),
            ("Mike left because Rex sang", Causation),
        ],
    )
    def test_encoded_sentence_evaluates_to_expected_predicate(self, encoder, sentence, expected_predicate_type):
        trace = encoder.encode(sentence)
        expr = from_trace(trace)
        pred = evaluate_tree(expr)
        assert isinstance(pred, expected_predicate_type), (
            f"{sentence!r} → {type(pred).__name__}, expected {expected_predicate_type.__name__}"
        )

    def test_so_and_because_distinguishable_by_conjunction(self, encoder):
        # Same effect/cause content, different conjunction direction
        so_pred = evaluate_tree(from_trace(encoder.encode("Mike sang so Rex left")))
        be_pred = evaluate_tree(from_trace(encoder.encode("Mike left because Rex sang")))
        assert isinstance(so_pred, Causation)
        assert isinstance(be_pred, Causation)
        assert so_pred.conjunction == "so"
        assert be_pred.conjunction == "because"


# ---------------------------------------------------------------------------
# evaluate_tree: non-Op nodes pass through
# ---------------------------------------------------------------------------


class TestEvaluateTreeLeaves:
    def test_atom_passes_through_unchanged(self):
        a = _atom("dog")
        assert evaluate_tree(a) is a

    def test_negation_of_atom_preserves_negation(self):
        from gse.symbolic.expression import Negation

        n = Negation(operand=_atom("good"))
        result = evaluate_tree(n)
        assert isinstance(result, Negation)
        assert isinstance(result.operand, Atom)
        assert result.operand.lemma == "good"
