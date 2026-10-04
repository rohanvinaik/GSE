"""
Tests for polarity propagation in compose_decomposition.

Verifies the emergent antonymy mechanism: a negated EVALUATOR (e.g. GOOD⁻¹)
colors MENTAL/ACTION primitives in the same decomposition so that
"feel-with-negative-eval" is geometrically distinct from "feel-with-positive-eval".

Theory anchor (Wierzbicka NSM):
    hate = {FEEL, GOOD⁻¹, WANT⁻¹, SOMEONE}
    love = {FEEL, GOOD,    WANT,    SOMEONE}
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.primitives_v2 import SemanticBank
from gse.vectors_v2 import (
    POLARITY_PROPAGATION_RULES,
    compose_decomposition,
    create_basis,
)


@pytest.fixture(scope="module")
def basis():
    return create_basis()


class TestPropagationRules:
    """The propagation rule table must encode EVALUATORS → MENTAL/ACTION."""

    def test_evaluators_is_source(self):
        assert SemanticBank.EVALUATORS in POLARITY_PROPAGATION_RULES

    def test_mental_is_target_of_evaluators(self):
        targets = POLARITY_PROPAGATION_RULES[SemanticBank.EVALUATORS]
        assert SemanticBank.MENTAL in targets

    def test_action_is_target_of_evaluators(self):
        targets = POLARITY_PROPAGATION_RULES[SemanticBank.EVALUATORS]
        assert SemanticBank.ACTION in targets


class TestPropagationGeometry:
    """Polarity propagation should change vector geometry meaningfully."""

    def test_propagation_changes_mental_when_evaluator_negated(self, basis):
        """FEEL+GOOD⁻¹ with propagation should differ from FEEL+GOOD⁻¹ without."""
        decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", -1),
        ]

        with_prop = compose_decomposition(basis, decomp, propagate_polarity=True)
        without_prop = compose_decomposition(basis, decomp, propagate_polarity=False)

        cos = with_prop.cosine(without_prop)
        assert cos < 1.0, "Propagation should produce a different vector"
        assert cos > 0.3, f"But still aligned with the un-propagated version (got {cos:.3f})"

    def test_no_change_when_no_negation(self, basis):
        """If no EVALUATOR is negated, propagation is a no-op."""
        decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", 1),
        ]

        with_prop = compose_decomposition(basis, decomp, propagate_polarity=True)
        without_prop = compose_decomposition(basis, decomp, propagate_polarity=False)

        cos = with_prop.cosine(without_prop)
        assert cos == pytest.approx(1.0, abs=1e-6), (
            f"No-negation decomposition should be identical (got cos={cos:.6f})"
        )

    def test_no_change_when_no_mental_or_action(self, basis):
        """If decomposition has no MENTAL/ACTION primitives, propagation is a no-op."""
        decomp = [
            ("SOMEONE", "experiencer", 1),  # SUBSTANTIVES
            ("GOOD", "evaluation", -1),     # negated EVALUATOR, but no target
        ]

        with_prop = compose_decomposition(basis, decomp, propagate_polarity=True)
        without_prop = compose_decomposition(basis, decomp, propagate_polarity=False)

        cos = with_prop.cosine(without_prop)
        assert cos == pytest.approx(1.0, abs=1e-6), (
            "SUBSTANTIVES is not a propagation target — should be identical"
        )

    def test_no_change_when_evaluator_positive(self, basis):
        """Only negated EVALUATORS propagate; positive ones do not."""
        decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", 1),  # positive — no propagation
        ]

        with_prop = compose_decomposition(basis, decomp, propagate_polarity=True)
        without_prop = compose_decomposition(basis, decomp, propagate_polarity=False)

        cos = with_prop.cosine(without_prop)
        assert cos == pytest.approx(1.0, abs=1e-6)


class TestEmergentAntonymy:
    """
    Propagation should widen the gap between hate-like and love-like
    decompositions, not collapse it.
    """

    def test_hate_vs_love_more_distinct_with_propagation(self, basis):
        """
        hate = {FEEL, GOOD⁻¹, WANT⁻¹, SOMEONE}
        love = {FEEL, GOOD,    WANT,    SOMEONE}

        With propagation, hate and love should be MORE distinct (lower cosine)
        than without — because FEEL gets colored by the negated evaluator.
        """
        hate_decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", -1),
            ("WANT", "intent", -1),
            ("SOMEONE", "object", 1),
        ]
        love_decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", 1),
            ("WANT", "intent", 1),
            ("SOMEONE", "object", 1),
        ]

        hate_with = compose_decomposition(basis, hate_decomp, propagate_polarity=True)
        love_with = compose_decomposition(basis, love_decomp, propagate_polarity=True)
        hate_without = compose_decomposition(basis, hate_decomp, propagate_polarity=False)
        love_without = compose_decomposition(basis, love_decomp, propagate_polarity=False)

        cos_with = hate_with.cosine(love_with)
        cos_without = hate_without.cosine(love_without)

        assert cos_with < cos_without, (
            f"Propagation should widen hate/love gap. "
            f"with={cos_with:.3f}, without={cos_without:.3f}"
        )

    def test_synonym_gap_preserved(self, basis):
        """Two positive-evaluation compositions should remain close with propagation."""
        positive_a = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", 1),
        ]
        positive_b = [
            ("FEEL", "state", 1),
            ("GOOD", "evaluation", 1),
        ]

        vec_a = compose_decomposition(basis, positive_a, propagate_polarity=True)
        vec_b = compose_decomposition(basis, positive_b, propagate_polarity=True)

        cos = vec_a.cosine(vec_b)
        assert cos > 0.4, (
            f"Same-polarity compositions should remain similar (cos={cos:.3f})"
        )

    def test_propagation_on_action_bank(self, basis):
        """ACTION bank should also receive propagation (DO, HAPPEN, etc.)."""
        positive = [
            ("DO", "agent_action", 1),
            ("GOOD", "evaluation", 1),
        ]
        negative = [
            ("DO", "agent_action", 1),
            ("GOOD", "evaluation", -1),  # action is evaluated badly
        ]

        with_prop_pos = compose_decomposition(basis, positive, propagate_polarity=True)
        with_prop_neg = compose_decomposition(basis, negative, propagate_polarity=True)
        without_prop_neg = compose_decomposition(basis, negative, propagate_polarity=False)

        cos_with = with_prop_pos.cosine(with_prop_neg)
        cos_without = with_prop_pos.cosine(without_prop_neg)

        assert cos_with < cos_without, (
            f"ACTION bank should also receive propagation. "
            f"with={cos_with:.3f}, without={cos_without:.3f}"
        )


class TestBackwardCompatibility:
    """Existing call sites should still work without the new parameter."""

    def test_default_enables_propagation(self, basis):
        decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", -1),
        ]

        default = compose_decomposition(basis, decomp)
        explicit = compose_decomposition(basis, decomp, propagate_polarity=True)

        cos = default.cosine(explicit)
        assert cos == pytest.approx(1.0, abs=1e-6), (
            "Default should be propagate_polarity=True"
        )

    def test_can_disable_propagation(self, basis):
        decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", -1),
        ]
        result = compose_decomposition(basis, decomp, propagate_polarity=False)
        assert result.nnz > 0

    def test_empty_decomposition_returns_zero(self, basis):
        result = compose_decomposition(basis, [])
        assert result.nnz == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
