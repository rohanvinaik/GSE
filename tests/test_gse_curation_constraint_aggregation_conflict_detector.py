"""Manual contract tests for gse.curation.constraint_aggregation.conflict_detector."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.constraint_aggregation.conflict_detector import (
    BIPOLAR_PAIRS,
    BIPOLAR_PARTNER,
    detect_conflicts,
    get_conflict_summary,
    should_flag_for_review,
)
from gse.curation.constraint_aggregation.types import (
    ConflictRecord,
    ConstraintType,
    EvidenceStrength,
    SourceMapping,
)


def mk_sm(source="verbnet", primitive="GOOD", value=1):
    return SourceMapping(
        source_name=source,
        source_concept="X",
        target_primitive=primitive,
        target_value=value,
        constraint_type=ConstraintType.DEFINITIVE,
        evidence_strength=EvidenceStrength.STRONG,
    )


def mk_cr(conflict_type="value_disagreement", severity="major", primitive="GOOD"):
    return ConflictRecord(
        primitive=primitive,
        conflict_type=conflict_type,
        sources_positive=[],
        sources_negative=[],
        severity=severity,
        resolution_required=True,
    )


# ---------- BIPOLAR module data ----------

class TestBipolarPairs:
    def test_good_bad_present(self):
        assert ("GOOD", "BAD") in BIPOLAR_PAIRS

    def test_big_small_present(self):
        assert ("BIG", "SMALL") in BIPOLAR_PAIRS

    def test_count(self):
        assert len(BIPOLAR_PAIRS) == 11

    def test_partner_lookup_both_directions(self):
        assert BIPOLAR_PARTNER["GOOD"] == "BAD"
        assert BIPOLAR_PARTNER["BAD"] == "GOOD"

    def test_partner_covers_all_pairs(self):
        for p1, p2 in BIPOLAR_PAIRS:
            assert BIPOLAR_PARTNER[p1] == p2
            assert BIPOLAR_PARTNER[p2] == p1


# ---------- detect_conflicts ----------

class TestDetectConflicts:
    def test_empty_returns_empty(self):
        assert detect_conflicts({}) == []

    def test_no_evidence_skipped(self):
        assert detect_conflicts({"GOOD": []}) == []

    def test_all_positive_no_conflict(self):
        ev = {"X": [mk_sm(value=1), mk_sm(source="framenet", value=1)]}
        assert detect_conflicts(ev) == []

    def test_value_disagreement_major(self):
        ev = {
            "X": [
                mk_sm(source="verbnet", value=1),
                mk_sm(source="framenet", value=-1),
            ]
        }
        result = detect_conflicts(ev)
        assert len(result) == 1
        assert result[0].conflict_type == "value_disagreement"
        assert result[0].severity == "major"

    def test_sign_flip_critical(self):
        # Multiple on each side → critical sign_flip
        ev = {
            "X": [
                mk_sm(source="verbnet", value=1),
                mk_sm(source="framenet", value=1),
                mk_sm(source="propbank", value=-1),
                mk_sm(source="usas", value=-1),
            ]
        }
        result = detect_conflicts(ev)
        assert len(result) == 1
        assert result[0].conflict_type == "sign_flip"
        assert result[0].severity == "critical"

    def test_positive_sources_listed(self):
        ev = {
            "X": [mk_sm(source="A", value=1), mk_sm(source="B", value=-1)]
        }
        result = detect_conflicts(ev)
        assert "A" in result[0].sources_positive
        assert "B" in result[0].sources_negative

    def test_resolution_required_true(self):
        ev = {"X": [mk_sm(source="A", value=1), mk_sm(source="B", value=-1)]}
        result = detect_conflicts(ev)
        assert result[0].resolution_required is True

    def test_primitive_field_set(self):
        ev = {"FOO": [mk_sm(source="A", value=1), mk_sm(source="B", value=-1)]}
        result = detect_conflicts(ev)
        assert result[0].primitive == "FOO"

    def test_detail_string_format(self):
        ev = {"X": [mk_sm(source="A", value=1), mk_sm(source="B", value=-1)]}
        result = detect_conflicts(ev)
        assert "+1" in result[0].detail
        assert "-1" in result[0].detail

    def test_bipolar_violation_detected(self):
        ev = {
            "GOOD": [mk_sm(source="A", primitive="GOOD", value=1)],
            "BAD": [mk_sm(source="B", primitive="BAD", value=1)],
        }
        result = detect_conflicts(ev)
        violations = [c for c in result if c.conflict_type == "bipolar_violation"]
        assert len(violations) == 1
        assert violations[0].primitive == "GOOD/BAD"

    def test_bipolar_violation_only_when_both_positive(self):
        # One positive, one zero → no violation
        ev = {
            "GOOD": [mk_sm(source="A", primitive="GOOD", value=1)],
            "BAD": [mk_sm(source="B", primitive="BAD", value=0)],
        }
        result = detect_conflicts(ev)
        violations = [c for c in result if c.conflict_type == "bipolar_violation"]
        assert violations == []

    def test_bipolar_violation_sources(self):
        ev = {
            "GOOD": [mk_sm(source="A", primitive="GOOD", value=1)],
            "BAD": [mk_sm(source="B", primitive="BAD", value=1)],
        }
        result = detect_conflicts(ev)
        violations = [c for c in result if c.conflict_type == "bipolar_violation"]
        assert "A" in violations[0].sources_positive
        assert "B" in violations[0].sources_negative

    def test_bipolar_severity_major(self):
        ev = {
            "GOOD": [mk_sm(source="A", primitive="GOOD", value=1)],
            "BAD": [mk_sm(source="B", primitive="BAD", value=1)],
        }
        result = detect_conflicts(ev)
        violations = [c for c in result if c.conflict_type == "bipolar_violation"]
        assert violations[0].severity == "major"

    def test_bipolar_skipped_when_one_pair_member_missing(self):
        ev = {"GOOD": [mk_sm(primitive="GOOD", value=1)]}
        # No BAD entry → no violation
        result = detect_conflicts(ev)
        violations = [c for c in result if c.conflict_type == "bipolar_violation"]
        assert violations == []

    def test_only_one_pos_one_neg_major_not_critical(self):
        # Exactly 1 vs 1 — should be major value_disagreement
        ev = {"X": [mk_sm(source="A", value=1), mk_sm(source="B", value=-1)]}
        result = detect_conflicts(ev)
        assert result[0].severity == "major"
        assert result[0].conflict_type == "value_disagreement"

    def test_two_pos_one_neg_major(self):
        # 2 positive, 1 negative — sign_flip needs >1 on both, so major
        ev = {
            "X": [
                mk_sm(source="A", value=1),
                mk_sm(source="B", value=1),
                mk_sm(source="C", value=-1),
            ]
        }
        result = detect_conflicts(ev)
        assert result[0].severity == "major"
        assert result[0].conflict_type == "value_disagreement"


# ---------- should_flag_for_review ----------

class TestShouldFlagForReview:
    def test_no_conflicts_high_conf_no_flag(self):
        flag, reasons = should_flag_for_review([], 0.9)
        assert flag is False
        assert reasons == []

    def test_critical_conflict_flags(self):
        conflicts = [mk_cr(severity="critical")]
        flag, reasons = should_flag_for_review(conflicts, 0.9)
        assert flag is True
        assert any("critical" in r for r in reasons)

    def test_bipolar_violation_flags(self):
        conflicts = [mk_cr(conflict_type="bipolar_violation", severity="major")]
        flag, reasons = should_flag_for_review(conflicts, 0.9)
        assert flag is True
        assert any("Bipolar" in r for r in reasons)

    def test_low_confidence_flags(self):
        # 0.5 < 0.7 default
        flag, reasons = should_flag_for_review([], 0.5)
        assert flag is True
        assert any("Low confidence" in r for r in reasons)

    def test_high_confidence_no_flag(self):
        # confidence at threshold → not below, so no flag
        flag, reasons = should_flag_for_review([], 0.7)
        assert flag is False

    def test_below_threshold_flags(self):
        flag, _ = should_flag_for_review([], 0.69, min_confidence_threshold=0.7)
        assert flag is True

    def test_custom_threshold(self):
        # 0.85 < 0.9 → flag
        flag, _ = should_flag_for_review([], 0.85, min_confidence_threshold=0.9)
        assert flag is True

    def test_three_value_disagreements_flag(self):
        conflicts = [mk_cr() for _ in range(3)]
        flag, reasons = should_flag_for_review(conflicts, 0.9)
        assert flag is True
        assert any("value disagreements" in r for r in reasons)

    def test_two_value_disagreements_no_flag_by_count(self):
        # Only 2 → not enough by count rule (need >=3); should not flag from this rule
        conflicts = [mk_cr() for _ in range(2)]
        flag, reasons = should_flag_for_review(conflicts, 0.9)
        # Confidence is high, conflicts are "major" not critical, only 2 disagreements
        assert flag is False

    def test_sign_flip_flags(self):
        conflicts = [mk_cr(conflict_type="sign_flip", severity="critical")]
        flag, reasons = should_flag_for_review(conflicts, 0.9)
        assert flag is True
        assert any("Sign flip" in r for r in reasons)
        assert any("critical" in r for r in reasons)

    def test_bipolar_lists_primitive(self):
        c = ConflictRecord(
            primitive="GOOD/BAD",
            conflict_type="bipolar_violation",
            sources_positive=[], sources_negative=[],
            severity="major", resolution_required=True,
        )
        _, reasons = should_flag_for_review([c], 0.9)
        joined = " ".join(reasons)
        assert "GOOD/BAD" in joined

    def test_multiple_reasons(self):
        conflicts = [
            mk_cr(severity="critical"),
            mk_cr(conflict_type="bipolar_violation"),
        ]
        flag, reasons = should_flag_for_review(conflicts, 0.5)
        # Critical + Bipolar + Low conf → 3 reasons
        assert flag is True
        assert len(reasons) >= 3

    def test_low_confidence_format_two_decimals(self):
        # Pin the .2f format specifier - .50 not .5 or .500
        flag, reasons = should_flag_for_review([], 0.5)
        low_msgs = [r for r in reasons if r.startswith("Low confidence")]
        assert "Low confidence: 0.50" in low_msgs

    def test_low_confidence_rounds_correctly(self):
        # 0.123456 with .2f → 0.12
        _, reasons = should_flag_for_review([], 0.123456)
        low_msgs = [r for r in reasons if r.startswith("Low confidence")]
        assert "Low confidence: 0.12" in low_msgs

    def test_bipolar_join_format(self):
        # ', ' separator (with space) — pin exact format
        c1 = ConflictRecord(
            primitive="GOOD/BAD",
            conflict_type="bipolar_violation",
            sources_positive=[], sources_negative=[],
            severity="major", resolution_required=True,
        )
        c2 = ConflictRecord(
            primitive="BIG/SMALL",
            conflict_type="bipolar_violation",
            sources_positive=[], sources_negative=[],
            severity="major", resolution_required=True,
        )
        _, reasons = should_flag_for_review([c1, c2], 0.9)
        bipolar_msgs = [r for r in reasons if r.startswith("Bipolar")]
        assert "Bipolar violation(s): GOOD/BAD, BIG/SMALL" in bipolar_msgs

    def test_sign_flip_join_format(self):
        c1 = ConflictRecord(
            primitive="X",
            conflict_type="sign_flip",
            sources_positive=[], sources_negative=[],
            severity="critical", resolution_required=True,
        )
        c2 = ConflictRecord(
            primitive="Y",
            conflict_type="sign_flip",
            sources_positive=[], sources_negative=[],
            severity="critical", resolution_required=True,
        )
        _, reasons = should_flag_for_review([c1, c2], 0.9)
        sign_msgs = [r for r in reasons if r.startswith("Sign")]
        assert "Sign flip(s): X, Y" in sign_msgs

    def test_critical_count_in_reason(self):
        # 2 critical conflicts → "2 critical conflict(s)"
        conflicts = [mk_cr(severity="critical"), mk_cr(severity="critical")]
        _, reasons = should_flag_for_review(conflicts, 0.9)
        assert "2 critical conflict(s)" in reasons

    def test_value_disagreement_count_in_reason(self):
        # exactly 3 → "3 value disagreements"
        conflicts = [mk_cr() for _ in range(3)]
        _, reasons = should_flag_for_review(conflicts, 0.9)
        assert "3 value disagreements" in reasons

    def test_default_threshold_is_0_7(self):
        # Default threshold = 0.7; confidence 0.69 → flag, 0.70 → no flag
        flag_low, _ = should_flag_for_review([], 0.69)
        flag_hi, _ = should_flag_for_review([], 0.70)
        assert flag_low is True
        assert flag_hi is False


# ---------- get_conflict_summary ----------

class TestGetConflictSummary:
    def test_empty_returns_zero_struct(self):
        s = get_conflict_summary([])
        assert s["total"] == 0
        assert s["by_type"] == {}
        assert s["by_severity"] == {}
        assert s["primitives_affected"] == []

    def test_total_count(self):
        conflicts = [mk_cr(), mk_cr(), mk_cr()]
        s = get_conflict_summary(conflicts)
        assert s["total"] == 3

    def test_by_type_counts(self):
        conflicts = [
            mk_cr(conflict_type="value_disagreement"),
            mk_cr(conflict_type="value_disagreement"),
            mk_cr(conflict_type="sign_flip"),
        ]
        s = get_conflict_summary(conflicts)
        assert s["by_type"]["value_disagreement"] == 2
        assert s["by_type"]["sign_flip"] == 1

    def test_by_severity_counts(self):
        conflicts = [
            mk_cr(severity="major"),
            mk_cr(severity="critical"),
            mk_cr(severity="critical"),
        ]
        s = get_conflict_summary(conflicts)
        assert s["by_severity"]["major"] == 1
        assert s["by_severity"]["critical"] == 2

    def test_primitives_set_dedup(self):
        # Same primitive twice → set dedup
        conflicts = [mk_cr(primitive="GOOD"), mk_cr(primitive="GOOD"), mk_cr(primitive="BAD")]
        s = get_conflict_summary(conflicts)
        assert set(s["primitives_affected"]) == {"GOOD", "BAD"}

    def test_primitives_returns_list_type(self):
        s = get_conflict_summary([mk_cr()])
        assert isinstance(s["primitives_affected"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
