"""Manual contract tests for gse.curation.constraint_aggregation.types."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.constraint_aggregation.types import (
    ConflictRecord,
    ConstraintType,
    EvidenceStrength,
    PrimitiveConstraint,
    SourceMapping,
    WordConstraintProfile,
)

# ---------- ConstraintType ----------

class TestConstraintType:
    def test_definitive_value(self):
        assert ConstraintType.DEFINITIVE.value == "definitive"

    def test_inferential_value(self):
        assert ConstraintType.INFERENTIAL.value == "inferential"

    def test_correlational_value(self):
        assert ConstraintType.CORRELATIONAL.value == "correlational"

    def test_member_count(self):
        assert len(list(ConstraintType)) == 3

    def test_distinct_members(self):
        members = {m.value for m in ConstraintType}
        assert members == {"definitive", "inferential", "correlational"}


# ---------- EvidenceStrength ----------

class TestEvidenceStrength:
    def test_strong_value(self):
        assert EvidenceStrength.STRONG.value == 1.0

    def test_moderate_value(self):
        assert EvidenceStrength.MODERATE.value == 0.7

    def test_weak_value(self):
        assert EvidenceStrength.WEAK.value == 0.4

    def test_ordering_strong_gt_moderate(self):
        assert EvidenceStrength.STRONG.value > EvidenceStrength.MODERATE.value

    def test_ordering_moderate_gt_weak(self):
        assert EvidenceStrength.MODERATE.value > EvidenceStrength.WEAK.value

    def test_member_count(self):
        assert len(list(EvidenceStrength)) == 3


# ---------- SourceMapping ----------

def _make_mapping(**overrides):
    base = dict(
        source_name="verbnet",
        source_concept="Agent",
        target_primitive="SOMEONE",
        target_value=1,
        constraint_type=ConstraintType.DEFINITIVE,
        evidence_strength=EvidenceStrength.STRONG,
    )
    base.update(overrides)
    return SourceMapping(**base)


class TestSourceMapping:
    def test_construction(self):
        m = _make_mapping()
        assert m.source_name == "verbnet"
        assert m.source_concept == "Agent"
        assert m.target_primitive == "SOMEONE"
        assert m.target_value == 1
        assert m.constraint_type == ConstraintType.DEFINITIVE
        assert m.evidence_strength == EvidenceStrength.STRONG

    def test_default_conditions_is_none(self):
        assert _make_mapping().conditions is None

    def test_default_raw_value_is_none(self):
        assert _make_mapping().raw_value is None

    def test_optional_fields_set(self):
        m = _make_mapping(conditions="score > 0.65", raw_value=0.81)
        assert m.conditions == "score > 0.65"
        assert m.raw_value == 0.81

    def test_frozen(self):
        m = _make_mapping()
        with pytest.raises(Exception):
            m.source_name = "other"  # type: ignore[misc]

    def test_hash_uses_four_fields(self):
        m1 = _make_mapping()
        m2 = _make_mapping()
        assert hash(m1) == hash(m2)

    def test_hash_differs_on_source_name(self):
        m1 = _make_mapping()
        m2 = _make_mapping(source_name="nrc_vad")
        assert hash(m1) != hash(m2)

    def test_hash_differs_on_source_concept(self):
        m1 = _make_mapping()
        m2 = _make_mapping(source_concept="Patient")
        assert hash(m1) != hash(m2)

    def test_hash_differs_on_target_primitive(self):
        m1 = _make_mapping()
        m2 = _make_mapping(target_primitive="GOOD")
        assert hash(m1) != hash(m2)

    def test_hash_differs_on_target_value(self):
        m1 = _make_mapping(target_value=1)
        m2 = _make_mapping(target_value=-1)
        assert hash(m1) != hash(m2)

    def test_hash_independent_of_evidence_strength(self):
        m1 = _make_mapping(evidence_strength=EvidenceStrength.STRONG)
        m2 = _make_mapping(evidence_strength=EvidenceStrength.WEAK)
        assert hash(m1) == hash(m2)

    def test_hash_independent_of_constraint_type(self):
        m1 = _make_mapping(constraint_type=ConstraintType.DEFINITIVE)
        m2 = _make_mapping(constraint_type=ConstraintType.INFERENTIAL)
        assert hash(m1) == hash(m2)

    def test_hash_independent_of_conditions(self):
        m1 = _make_mapping(conditions=None)
        m2 = _make_mapping(conditions="x > 0")
        assert hash(m1) == hash(m2)

    def test_hash_independent_of_raw_value(self):
        m1 = _make_mapping(raw_value=None)
        m2 = _make_mapping(raw_value=0.5)
        assert hash(m1) == hash(m2)

    def test_set_dedup_uses_hash(self):
        m1 = _make_mapping(evidence_strength=EvidenceStrength.STRONG)
        m2 = _make_mapping(evidence_strength=EvidenceStrength.WEAK)
        # Same hash + equal under frozen dataclass equality? No — dataclass eq compares all fields.
        # So set should preserve both since they differ on evidence_strength
        assert len({m1, m2}) == 2

    def test_set_dedup_identical_mappings(self):
        m1 = _make_mapping()
        m2 = _make_mapping()
        assert len({m1, m2}) == 1


# ---------- PrimitiveConstraint ----------

def _make_constraint(**overrides):
    base = dict(
        primitive="GOOD",
        value=1,
        confidence=0.9,
        supporting_sources=["verbnet"],
        conflicting_sources=[],
        evidence_records=[_make_mapping()],
        status="auto_apply",
    )
    base.update(overrides)
    return PrimitiveConstraint(**base)


class TestPrimitiveConstraint:
    def test_construction(self):
        c = _make_constraint()
        assert c.primitive == "GOOD"
        assert c.value == 1
        assert c.confidence == 0.9
        assert c.supporting_sources == ["verbnet"]
        assert c.conflicting_sources == []
        assert c.status == "auto_apply"

    def test_has_conflict_when_conflicting_nonempty(self):
        c = _make_constraint(conflicting_sources=["nrc_vad"])
        assert c.has_conflict is True

    def test_has_conflict_false_when_empty(self):
        c = _make_constraint(conflicting_sources=[])
        assert c.has_conflict is False

    def test_is_unanimous_true(self):
        c = _make_constraint(supporting_sources=["a", "b"], conflicting_sources=[])
        assert c.is_unanimous is True

    def test_is_unanimous_false_when_conflict(self):
        c = _make_constraint(supporting_sources=["a"], conflicting_sources=["b"])
        assert c.is_unanimous is False

    def test_is_unanimous_false_when_no_supporting(self):
        c = _make_constraint(supporting_sources=[], conflicting_sources=[])
        assert c.is_unanimous is False

    def test_is_unanimous_requires_both_conditions(self):
        # supporting=[] and conflicting=[] should be False (no support, even though no conflict)
        c = _make_constraint(supporting_sources=[], conflicting_sources=[])
        assert c.is_unanimous is False
        # supporting nonempty + conflicting empty → True
        c = _make_constraint(supporting_sources=["x"], conflicting_sources=[])
        assert c.is_unanimous is True

    def test_negative_value(self):
        c = _make_constraint(value=-1)
        assert c.value == -1

    def test_zero_confidence(self):
        c = _make_constraint(confidence=0.0)
        assert c.confidence == 0.0


# ---------- ConflictRecord ----------

class TestConflictRecord:
    def test_construction(self):
        cr = ConflictRecord(
            primitive="GOOD",
            conflict_type="value_disagreement",
            sources_positive=["verbnet"],
            sources_negative=["nrc_vad"],
            severity="major",
            resolution_required=True,
        )
        assert cr.primitive == "GOOD"
        assert cr.conflict_type == "value_disagreement"
        assert cr.sources_positive == ["verbnet"]
        assert cr.sources_negative == ["nrc_vad"]
        assert cr.severity == "major"
        assert cr.resolution_required is True

    def test_default_detail_is_none(self):
        cr = ConflictRecord(
            primitive="X",
            conflict_type="sign_flip",
            sources_positive=[],
            sources_negative=[],
            severity="minor",
            resolution_required=False,
        )
        assert cr.detail is None

    def test_explicit_detail(self):
        cr = ConflictRecord(
            primitive="X",
            conflict_type="bipolar_violation",
            sources_positive=[],
            sources_negative=[],
            severity="critical",
            resolution_required=True,
            detail="GOOD and BAD both asserted",
        )
        assert cr.detail == "GOOD and BAD both asserted"


# ---------- WordConstraintProfile ----------

def _make_profile(**overrides):
    base = dict(
        word="dog",
        pos="NOUN",
        sources_checked=["verbnet", "nrc_vad"],
        sources_with_data=["verbnet"],
        constraints={},
        conflicts=[],
        overall_confidence=0.8,
        review_required=False,
        review_reasons=[],
    )
    base.update(overrides)
    return WordConstraintProfile(**base)


class TestWordConstraintProfile:
    def test_construction(self):
        p = _make_profile()
        assert p.word == "dog"
        assert p.pos == "NOUN"
        assert p.sources_checked == ["verbnet", "nrc_vad"]
        assert p.sources_with_data == ["verbnet"]
        assert p.constraints == {}
        assert p.conflicts == []
        assert p.overall_confidence == 0.8
        assert p.review_required is False
        assert p.review_reasons == []

    def test_default_raw_source_data_is_none(self):
        assert _make_profile().raw_source_data is None

    def test_pos_can_be_none(self):
        p = _make_profile(pos=None)
        assert p.pos is None

    # ----- get_auto_apply_constraints -----

    def test_get_auto_apply_empty(self):
        p = _make_profile(constraints={})
        assert p.get_auto_apply_constraints() == {}

    def test_get_auto_apply_filters_status(self):
        c_auto = _make_constraint(primitive="GOOD", value=1, status="auto_apply")
        c_review = _make_constraint(primitive="BIG", value=-1, status="flag_review")
        c_insuf = _make_constraint(primitive="SMALL", value=0, status="insufficient")
        p = _make_profile(constraints={"GOOD": c_auto, "BIG": c_review, "SMALL": c_insuf})
        result = p.get_auto_apply_constraints()
        assert result == {"GOOD": 1}

    def test_get_auto_apply_preserves_values(self):
        c1 = _make_constraint(primitive="GOOD", value=1, status="auto_apply")
        c2 = _make_constraint(primitive="BAD", value=-1, status="auto_apply")
        p = _make_profile(constraints={"GOOD": c1, "BAD": c2})
        result = p.get_auto_apply_constraints()
        assert result == {"GOOD": 1, "BAD": -1}

    def test_get_auto_apply_excludes_non_auto(self):
        c = _make_constraint(primitive="X", value=1, status="flag_review")
        p = _make_profile(constraints={"X": c})
        assert p.get_auto_apply_constraints() == {}

    # ----- get_review_candidates -----

    def test_get_review_candidates_empty(self):
        assert _make_profile(constraints={}).get_review_candidates() == []

    def test_get_review_candidates_includes_only_flag_review(self):
        c_auto = _make_constraint(primitive="GOOD", status="auto_apply")
        c_review = _make_constraint(
            primitive="BIG",
            value=-1,
            confidence=0.5,
            supporting_sources=["a"],
            conflicting_sources=["b"],
            status="flag_review",
        )
        p = _make_profile(constraints={"GOOD": c_auto, "BIG": c_review})
        candidates = p.get_review_candidates()
        assert len(candidates) == 1
        assert candidates[0]["primitive"] == "BIG"

    def test_review_candidate_reason_source_disagreement(self):
        c = _make_constraint(
            primitive="X",
            supporting_sources=["a"],
            conflicting_sources=["b"],
            status="flag_review",
        )
        p = _make_profile(constraints={"X": c})
        candidates = p.get_review_candidates()
        assert candidates[0]["reason"] == "Source disagreement"

    def test_review_candidate_reason_low_confidence(self):
        c = _make_constraint(
            primitive="X",
            supporting_sources=["a"],
            conflicting_sources=[],
            status="flag_review",
        )
        p = _make_profile(constraints={"X": c})
        candidates = p.get_review_candidates()
        assert candidates[0]["reason"] == "Low confidence"

    def test_review_candidate_full_fields(self):
        c = _make_constraint(
            primitive="GOOD",
            value=1,
            confidence=0.42,
            supporting_sources=["s1", "s2"],
            conflicting_sources=["c1"],
            status="flag_review",
        )
        p = _make_profile(constraints={"GOOD": c})
        cand = p.get_review_candidates()[0]
        assert cand["primitive"] == "GOOD"
        assert cand["proposed_value"] == 1
        assert cand["confidence"] == 0.42
        assert cand["supporting"] == ["s1", "s2"]
        assert cand["conflicting"] == ["c1"]
        assert cand["reason"] == "Source disagreement"

    # ----- summary -----

    def test_summary_empty(self):
        p = _make_profile(constraints={}, conflicts=[])
        s = p.summary()
        assert s["word"] == "dog"
        assert s["sources_with_data"] == 1
        assert s["total_constraints"] == 0
        assert s["auto_apply"] == 0
        assert s["flag_review"] == 0
        assert s["insufficient"] == 0
        assert s["conflicts"] == 0
        assert s["overall_confidence"] == 0.8
        assert s["review_required"] is False

    def test_summary_counts_each_status(self):
        c1 = _make_constraint(primitive="A", status="auto_apply")
        c2 = _make_constraint(primitive="B", status="auto_apply")
        c3 = _make_constraint(primitive="C", status="flag_review")
        c4 = _make_constraint(primitive="D", status="insufficient")
        p = _make_profile(constraints={"A": c1, "B": c2, "C": c3, "D": c4})
        s = p.summary()
        assert s["total_constraints"] == 4
        assert s["auto_apply"] == 2
        assert s["flag_review"] == 1
        assert s["insufficient"] == 1

    def test_summary_auto_apply_asymmetric(self):
        # Asymmetric count so == vs != on status produce different totals.
        # 3 auto_apply, 1 flag_review → auto_apply=3, not-auto=1
        c1 = _make_constraint(primitive="A", status="auto_apply")
        c2 = _make_constraint(primitive="B", status="auto_apply")
        c3 = _make_constraint(primitive="C", status="auto_apply")
        c4 = _make_constraint(primitive="D", status="flag_review")
        s = _make_profile(constraints={"A": c1, "B": c2, "C": c3, "D": c4}).summary()
        assert s["auto_apply"] == 3
        assert s["flag_review"] == 1
        assert s["insufficient"] == 0

    def test_summary_flag_review_asymmetric(self):
        # 1 auto_apply, 3 flag_review → distinguishes status=="flag_review" from !=
        c1 = _make_constraint(primitive="A", status="auto_apply")
        c2 = _make_constraint(primitive="B", status="flag_review")
        c3 = _make_constraint(primitive="C", status="flag_review")
        c4 = _make_constraint(primitive="D", status="flag_review")
        s = _make_profile(constraints={"A": c1, "B": c2, "C": c3, "D": c4}).summary()
        assert s["auto_apply"] == 1
        assert s["flag_review"] == 3

    def test_summary_counts_conflicts(self):
        conflict = ConflictRecord(
            primitive="X",
            conflict_type="sign_flip",
            sources_positive=[],
            sources_negative=[],
            severity="minor",
            resolution_required=False,
        )
        p = _make_profile(conflicts=[conflict, conflict])
        assert p.summary()["conflicts"] == 2

    def test_summary_sources_with_data_count(self):
        p = _make_profile(sources_with_data=["a", "b", "c"])
        assert p.summary()["sources_with_data"] == 3

    def test_summary_propagates_review_required(self):
        p = _make_profile(review_required=True)
        assert p.summary()["review_required"] is True

    def test_summary_propagates_overall_confidence(self):
        p = _make_profile(overall_confidence=0.123)
        assert p.summary()["overall_confidence"] == 0.123

    def test_summary_word_field(self):
        p = _make_profile(word="cat")
        assert p.summary()["word"] == "cat"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
