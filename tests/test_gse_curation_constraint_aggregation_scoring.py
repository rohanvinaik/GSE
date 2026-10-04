"""Manual contract tests for gse.curation.constraint_aggregation.scoring."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.constraint_aggregation.scoring import (
    calculate_constraint_confidence,
    calculate_overall_word_confidence,
    confidence_to_status,
)
from gse.curation.constraint_aggregation.types import (
    ConstraintType,
    EvidenceStrength,
    PrimitiveConstraint,
    SourceMapping,
)


def mk_sm(source_name="verbnet", strength=EvidenceStrength.STRONG):
    return SourceMapping(
        source_name=source_name,
        source_concept="X",
        target_primitive="GOOD",
        target_value=1,
        constraint_type=ConstraintType.DEFINITIVE,
        evidence_strength=strength,
    )


def mk_pc(confidence=0.9, conflicting=None, status="auto_apply"):
    return PrimitiveConstraint(
        primitive="GOOD",
        value=1,
        confidence=confidence,
        supporting_sources=["verbnet"],
        conflicting_sources=conflicting or [],
        evidence_records=[],
        status=status,
    )


# ---------- calculate_constraint_confidence ----------


class TestCalculateConstraintConfidence:
    def test_no_evidence_returns_zero(self):
        assert calculate_constraint_confidence([], []) == 0.0

    def test_pure_support_high_confidence(self):
        result = calculate_constraint_confidence([mk_sm()], [])
        assert result > 0.5

    def test_pure_conflict_low_confidence(self):
        result = calculate_constraint_confidence([], [mk_sm()])
        # raw = (0 - x)/x = -1 → (-1+1)/2 = 0
        assert result == 0.0

    def test_returns_float(self):
        result = calculate_constraint_confidence([mk_sm()], [])
        assert isinstance(result, float)

    def test_rounded_to_three_places(self):
        result = calculate_constraint_confidence([mk_sm()], [])
        # Check decimal rounding
        s = repr(result)
        if "." in s:
            decimals = s.split(".")[1]
            assert len(decimals) <= 3

    def test_unknown_source_uses_default_half(self):
        # Unknown source gets 0.5 reliability
        m = SourceMapping(
            source_name="UNKNOWN_SOURCE",
            source_concept="X",
            target_primitive="GOOD",
            target_value=1,
            constraint_type=ConstraintType.DEFINITIVE,
            evidence_strength=EvidenceStrength.STRONG,
        )
        result = calculate_constraint_confidence([m], [])
        # raw = (0.5 - 0)/0.5 = 1 → (1+1)/2 = 1.0 (then with no bonus since 1 unique)
        assert result == 1.0

    def test_override_reliability(self):
        custom = {"verbnet": 0.1}
        result = calculate_constraint_confidence([mk_sm()], [], source_reliability=custom)
        # All-support, override applied → still 1.0 before bonus
        assert result == 1.0

    def test_source_bonus_three_sources_no_conflict(self):
        # 3 unique sources → bonus = min(0.1*2, 0.2) = 0.2
        sources = [mk_sm(source_name="verbnet"), mk_sm(source_name="framenet"), mk_sm(source_name="propbank")]
        result = calculate_constraint_confidence(sources, [])
        # base = 1.0, plus bonus capped at 1.0
        assert result == 1.0

    def test_source_bonus_only_with_no_conflict(self):
        # With a conflict, source bonus is NOT applied
        support = [mk_sm(source_name="verbnet"), mk_sm(source_name="framenet")]
        conflict = [mk_sm(source_name="propbank")]
        # Just verify result is < 1.0 (conflict penalty applies)
        result = calculate_constraint_confidence(support, conflict)
        assert result < 1.0

    def test_conflict_penalty_applied(self):
        # Equal weights → raw=0 → 0.5, then conflict_ratio=0.5 → 0.5*(1-0.25)=0.375
        support = [mk_sm()]
        conflict = [mk_sm()]
        result = calculate_constraint_confidence(support, conflict)
        # Confidence should be reduced from 0.5
        assert result < 0.5
        assert result > 0.0

    def test_unique_source_dedup(self):
        # Two evidence records from same source → unique_supporting = 1, no bonus
        evidence = [mk_sm(source_name="verbnet"), mk_sm(source_name="verbnet")]
        result = calculate_constraint_confidence(evidence, [])
        assert result == 1.0  # base capped at 1.0, no extra bonus

    def test_source_bonus_two_unique_sources(self):
        # 2 unique sources → bonus = min(0.1 * 1, 0.2) = 0.1
        # base = 1.0 → capped at 1.0
        result = calculate_constraint_confidence([mk_sm(source_name="verbnet"), mk_sm(source_name="framenet")], [])
        assert result == 1.0


# ---------- calculate_overall_word_confidence ----------


class TestCalculateOverallWordConfidence:
    def test_empty_constraints_returns_zero(self):
        assert calculate_overall_word_confidence({}, []) == 0.0

    def test_all_zero_confidences_returns_zero(self):
        constraints = {"GOOD": mk_pc(confidence=0.0)}
        assert calculate_overall_word_confidence(constraints, ["verbnet"]) == 0.0

    def test_returns_float_in_range(self):
        constraints = {"GOOD": mk_pc(confidence=0.8)}
        result = calculate_overall_word_confidence(constraints, ["verbnet"])
        assert 0.0 <= result <= 1.0

    def test_high_confidence_high_coverage(self):
        # 11/11 sources → coverage=1.0, factor=1.0; confidence=0.9; no conflicts
        constraints = {"GOOD": mk_pc(confidence=0.9)}
        sources = [f"s{i}" for i in range(11)]
        result = calculate_overall_word_confidence(constraints, sources, total_sources=11)
        assert result == pytest.approx(0.9, abs=0.001)

    def test_coverage_factor_floor(self):
        # 0 sources → coverage=0, factor=0.5; conf=1.0 → result=0.5
        constraints = {"GOOD": mk_pc(confidence=1.0)}
        result = calculate_overall_word_confidence(constraints, [], total_sources=11)
        assert result == pytest.approx(0.5, abs=0.001)

    def test_excludes_zero_confidence_from_avg(self):
        constraints = {
            "GOOD": mk_pc(confidence=0.8),
            "BAD": mk_pc(confidence=0.0),  # excluded
        }
        # avg = 0.8 (only GOOD counted)
        result = calculate_overall_word_confidence(constraints, ["verbnet"] * 11, total_sources=11)
        assert result == pytest.approx(0.8, abs=0.001)

    def test_conflict_penalty(self):
        # 1 of 2 constraints has conflict → conflict_count/len = 0.5
        # conflict_penalty = 1 - 0.5*0.3 = 0.85
        c1 = mk_pc(confidence=1.0, conflicting=[])
        c2 = mk_pc(confidence=1.0, conflicting=["x"])
        constraints = {"A": c1, "B": c2}
        result = calculate_overall_word_confidence(constraints, [f"s{i}" for i in range(11)], total_sources=11)
        # avg=1.0, factor=1.0, penalty=0.85 → 0.85
        assert result == pytest.approx(0.85, abs=0.001)

    def test_clamps_above_one(self):
        # Even with high inputs, result clamped to 1.0
        constraints = {"GOOD": mk_pc(confidence=1.0)}
        result = calculate_overall_word_confidence(constraints, [f"s{i}" for i in range(11)], total_sources=11)
        assert result <= 1.0

    def test_returns_zero_when_all_have_zero_conf(self):
        constraints = {
            "A": mk_pc(confidence=0.0),
            "B": mk_pc(confidence=0.0),
        }
        result = calculate_overall_word_confidence(constraints, ["verbnet"])
        assert result == 0.0

    def test_rounded_to_three(self):
        constraints = {"GOOD": mk_pc(confidence=0.777)}
        result = calculate_overall_word_confidence(constraints, [f"s{i}" for i in range(11)], total_sources=11)
        s = repr(result)
        if "." in s:
            decimals = s.split(".")[1]
            assert len(decimals) <= 3


# ---------- confidence_to_status ----------


class TestConfidenceToStatus:
    def test_conflict_always_flag_review(self):
        assert confidence_to_status(0.99, has_conflict=True) == "flag_review"

    def test_conflict_flag_review_even_when_low(self):
        assert confidence_to_status(0.1, has_conflict=True) == "flag_review"

    def test_high_confidence_no_conflict_auto_apply(self):
        assert confidence_to_status(0.9, has_conflict=False) == "auto_apply"

    def test_at_min_auto_apply_threshold(self):
        # confidence >= 0.8 → auto_apply
        assert confidence_to_status(0.8, has_conflict=False) == "auto_apply"

    def test_just_below_min_auto_apply(self):
        # 0.79 → not auto_apply, but above min_sufficient=0.3 → flag_review
        assert confidence_to_status(0.79, has_conflict=False) == "flag_review"

    def test_low_confidence_insufficient(self):
        # below min_sufficient
        assert confidence_to_status(0.2, has_conflict=False) == "insufficient"

    def test_at_min_sufficient_boundary(self):
        # confidence == 0.3 → not insufficient (uses strict <), goes to flag_review
        assert confidence_to_status(0.3, has_conflict=False) == "flag_review"

    def test_just_below_min_sufficient(self):
        assert confidence_to_status(0.299, has_conflict=False) == "insufficient"

    def test_medium_confidence_flag_review(self):
        # Between sufficient and auto_apply
        assert confidence_to_status(0.5, has_conflict=False) == "flag_review"

    def test_zero_confidence_insufficient(self):
        assert confidence_to_status(0.0, has_conflict=False) == "insufficient"

    def test_custom_thresholds(self):
        # min_auto_apply=0.9 → 0.85 not auto_apply
        assert confidence_to_status(0.85, has_conflict=False, min_auto_apply=0.9) == "flag_review"

    def test_custom_min_sufficient(self):
        # raise min_sufficient to 0.5 → 0.4 becomes insufficient
        assert confidence_to_status(0.4, has_conflict=False, min_sufficient=0.5) == "insufficient"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
