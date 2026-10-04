"""Tests for bipolar mutual-exclusion enforcement."""

from gse.curation.external_sources.bipolar_exclusion import (
    count_violations,
    enforce_bipolar_exclusion,
)


class TestNoConflict:
    def test_empty_decomposition_returns_empty(self):
        result = enforce_bipolar_exclusion({}, {})
        assert result.primitives == {}
        assert result.suppressions == []

    def test_non_bipolar_primitives_pass_through(self):
        decomp = {"FEEL": 1, "THINK": 1, "WANT": -1}
        confs = {"FEEL": 0.9, "THINK": 0.8, "WANT": 0.7}
        result = enforce_bipolar_exclusion(decomp, confs)
        assert result.primitives == decomp
        assert result.confidences == confs
        assert result.suppressions == []

    def test_single_pole_active_passes_through(self):
        # GOOD alone — no conflict
        result = enforce_bipolar_exclusion({"GOOD": 1}, {"GOOD": 0.9})
        assert result.primitives == {"GOOD": 1}
        assert result.suppressions == []

    def test_zero_value_entries_dropped_silently(self):
        # value=0 means "not active"; treat as absent
        result = enforce_bipolar_exclusion({"GOOD": 0, "BAD": 0}, {})
        assert result.primitives == {}
        assert result.suppressions == []


class TestConflictResolution:
    def test_both_poles_active_higher_confidence_wins(self):
        decomp = {"GOOD": 1, "BAD": 1}
        confs = {"GOOD": 0.9, "BAD": 0.4}
        result = enforce_bipolar_exclusion(decomp, confs)
        assert result.primitives == {"GOOD": 1}
        assert result.confidences == {"GOOD": 0.9}
        assert len(result.suppressions) == 1
        sup = result.suppressions[0]
        assert sup.kept == "GOOD"
        assert sup.dropped == "BAD"
        assert sup.kept_confidence == 0.9
        assert sup.dropped_confidence == 0.4
        assert sup.bipolar_pair == ("GOOD", "BAD")

    def test_negative_pole_wins_when_higher_confidence(self):
        decomp = {"GOOD": 1, "BAD": 1}
        confs = {"GOOD": 0.3, "BAD": 0.85}
        result = enforce_bipolar_exclusion(decomp, confs)
        assert result.primitives == {"BAD": 1}
        assert result.suppressions[0].kept == "BAD"
        assert result.suppressions[0].dropped == "GOOD"

    def test_tie_breaks_to_positive_pole_by_convention(self):
        decomp = {"GOOD": 1, "BAD": 1}
        confs = {"GOOD": 0.7, "BAD": 0.7}
        result = enforce_bipolar_exclusion(decomp, confs)
        # >= means positive wins on ties
        assert result.primitives == {"GOOD": 1}
        assert result.suppressions[0].kept == "GOOD"

    def test_missing_confidence_defaults_to_one(self):
        # Pre-cleanup tools may not have confidences yet
        decomp = {"BIG": 1, "SMALL": 1}
        result = enforce_bipolar_exclusion(decomp, None)
        # Both default to 1.0 → tie → positive (BIG) wins
        assert result.primitives == {"BIG": 1}

    def test_multiple_pairs_resolved_independently(self):
        # The "good" / "bad" anomaly from this session: SIZE axis activated
        # spuriously alongside the EVAL axis
        decomp = {"GOOD": 1, "BAD": -1, "BIG": -1, "SMALL": 1}
        confs = {"GOOD": 0.9, "BAD": 0.2, "BIG": 0.3, "SMALL": 0.85}
        result = enforce_bipolar_exclusion(decomp, confs)
        # GOOD wins EVAL (0.9 > 0.2); SMALL wins SIZE (0.85 > 0.3)
        assert result.primitives == {"GOOD": 1, "SMALL": 1}
        assert len(result.suppressions) == 2

    def test_the_near_far_case_from_investigation(self):
        # "near" lexicon had NEAR=+1 AND AWAY=+1 (DIRECTION pair) plus
        # WITH=+1 AND WITHOUT=+1 (ACCOMPANIMENT pair) — both NSM violations
        decomp = {
            "NEAR": 1,
            "FAR": -1,
            "TOWARD": 1,
            "AWAY": 1,  # DIRECTION conflict
            "WITH": 1,
            "WITHOUT": 1,  # ACCOMPANIMENT conflict
            "SIDE": 1,
        }
        confs = {
            "NEAR": 0.9,
            "FAR": 0.9,
            "TOWARD": 0.8,
            "AWAY": 0.3,
            "WITH": 0.6,
            "WITHOUT": 0.4,
            "SIDE": 0.7,
        }
        result = enforce_bipolar_exclusion(decomp, confs)
        # NEAR/FAR are -1/+1 — only one active (NEAR=+1, FAR=-1 means FAR is "active" too).
        # Wait: both nonzero → conflict. NEAR conf 0.9, FAR conf 0.9 → tie → NEAR (positive) wins.
        # Actually NEAR is positive pole of DISTANCE (NEAR is "pos" per BIPOLAR_PAIRS).
        # Both nonzero, equal conf → positive pole NEAR wins.
        assert "TOWARD" in result.primitives  # higher conf
        assert "AWAY" not in result.primitives
        assert "WITH" in result.primitives  # higher conf
        assert "WITHOUT" not in result.primitives
        assert "SIDE" in result.primitives  # not bipolar


class TestCountViolations:
    def test_no_violations(self):
        assert count_violations({"GOOD": 1, "FEEL": 1, "FAR": -1}) == 0

    def test_one_violation(self):
        assert count_violations({"GOOD": 1, "BAD": 1}) == 1

    def test_multiple_violations(self):
        # Three bipolar pairs all violated
        d = {
            "GOOD": 1,
            "BAD": 1,
            "BIG": 1,
            "SMALL": -1,
            "NEAR": 1,
            "FAR": -1,
        }
        assert count_violations(d) == 3

    def test_zero_values_not_counted_as_active(self):
        assert count_violations({"GOOD": 0, "BAD": 0}) == 0
        assert count_violations({"GOOD": 1, "BAD": 0}) == 0
