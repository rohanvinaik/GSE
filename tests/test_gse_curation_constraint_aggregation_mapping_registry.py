"""Manual contract tests for gse.curation.constraint_aggregation.mapping_registry."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.constraint_aggregation.mapping_registry import (
    SOURCE_PRIMITIVE_COVERAGE,
    SOURCE_RELIABILITY,
    get_all_covered_primitives,
    get_evidence_strength,
    get_mapping_for_source,
    get_primitive_constraint_type,
    get_sources_for_primitive,
)
from gse.curation.constraint_aggregation.types import (
    ConstraintType,
    EvidenceStrength,
    SourceMapping,
)

# ---------- SOURCE_RELIABILITY ----------

class TestSourceReliability:
    def test_verbnet_high(self):
        assert SOURCE_RELIABILITY["verbnet"] == 0.85

    def test_framenet_high(self):
        assert SOURCE_RELIABILITY["framenet"] == 0.85

    def test_conceptnet_lower(self):
        assert SOURCE_RELIABILITY["conceptnet"] == 0.65

    def test_all_values_in_unit_range(self):
        for v in SOURCE_RELIABILITY.values():
            assert 0.0 <= v <= 1.0

    def test_contains_expected_sources(self):
        # Spot-check membership
        for s in ("verbnet", "framenet", "propbank", "usas", "nrc_vad",
                  "concreteness", "wiktionary", "conceptnet"):
            assert s in SOURCE_RELIABILITY


# ---------- SOURCE_PRIMITIVE_COVERAGE ----------

class TestSourcePrimitiveCoverage:
    def test_verbnet_has_definitive_someone(self):
        assert "SOMEONE" in SOURCE_PRIMITIVE_COVERAGE["verbnet"]["definitive"]

    def test_wiktionary_has_empty_definitive(self):
        assert SOURCE_PRIMITIVE_COVERAGE["wiktionary"]["definitive"] == []

    def test_sentiwordnet_inferential_empty(self):
        assert SOURCE_PRIMITIVE_COVERAGE["sentiwordnet"]["inferential"] == []

    def test_nrc_vad_definitive_good(self):
        assert SOURCE_PRIMITIVE_COVERAGE["nrc_vad"]["definitive"] == ["GOOD"]


# ---------- get_primitive_constraint_type ----------

class TestGetPrimitiveConstraintType:
    def test_definitive_match(self):
        # SOMEONE is definitive for verbnet
        assert get_primitive_constraint_type("verbnet", "SOMEONE") == ConstraintType.DEFINITIVE

    def test_inferential_match(self):
        # WANT is inferential for verbnet
        assert get_primitive_constraint_type("verbnet", "WANT") == ConstraintType.INFERENTIAL

    def test_unknown_primitive_returns_correlational(self):
        # ZZZ not in verbnet coverage
        assert get_primitive_constraint_type("verbnet", "ZZZ") == ConstraintType.CORRELATIONAL

    def test_unknown_source_returns_correlational(self):
        assert get_primitive_constraint_type("nonexistent_source", "GOOD") == ConstraintType.CORRELATIONAL

    def test_definitive_takes_priority_over_inferential(self):
        # FEEL is definitive for nrc_emotion
        assert get_primitive_constraint_type("nrc_emotion", "FEEL") == ConstraintType.DEFINITIVE

    def test_inferential_not_in_definitive(self):
        # For nrc_emotion, GOOD is inferential (not definitive)
        assert get_primitive_constraint_type("nrc_emotion", "GOOD") == ConstraintType.INFERENTIAL


# ---------- get_evidence_strength ----------

class TestGetEvidenceStrength:
    def test_definitive_strong(self):
        assert get_evidence_strength(ConstraintType.DEFINITIVE) == EvidenceStrength.STRONG

    def test_inferential_moderate(self):
        assert get_evidence_strength(ConstraintType.INFERENTIAL) == EvidenceStrength.MODERATE

    def test_correlational_weak(self):
        assert get_evidence_strength(ConstraintType.CORRELATIONAL) == EvidenceStrength.WEAK

    def test_all_three_distinct(self):
        a = get_evidence_strength(ConstraintType.DEFINITIVE)
        b = get_evidence_strength(ConstraintType.INFERENTIAL)
        c = get_evidence_strength(ConstraintType.CORRELATIONAL)
        assert a != b
        assert b != c
        assert a != c


# ---------- get_mapping_for_source ----------

class TestGetMappingForSource:
    def test_returns_source_mapping(self):
        m = get_mapping_for_source("verbnet", "SOMEONE", 1)
        assert isinstance(m, SourceMapping)

    def test_target_primitive_propagates(self):
        m = get_mapping_for_source("verbnet", "GOOD", 1)
        assert m.target_primitive == "GOOD"

    def test_target_value_propagates(self):
        m = get_mapping_for_source("verbnet", "GOOD", -1)
        assert m.target_value == -1

    def test_source_name_propagates(self):
        m = get_mapping_for_source("verbnet", "GOOD", 1)
        assert m.source_name == "verbnet"

    def test_default_source_concept_format(self):
        m = get_mapping_for_source("verbnet", "SOMEONE", 1)
        assert m.source_concept == "verbnet_SOMEONE"

    def test_explicit_source_concept_overrides(self):
        m = get_mapping_for_source("verbnet", "SOMEONE", 1, source_concept="Agent")
        assert m.source_concept == "Agent"

    def test_definitive_gets_strong(self):
        # SOMEONE definitive in verbnet
        m = get_mapping_for_source("verbnet", "SOMEONE", 1)
        assert m.constraint_type == ConstraintType.DEFINITIVE
        assert m.evidence_strength == EvidenceStrength.STRONG

    def test_inferential_gets_moderate(self):
        # WANT inferential in verbnet
        m = get_mapping_for_source("verbnet", "WANT", 1)
        assert m.constraint_type == ConstraintType.INFERENTIAL
        assert m.evidence_strength == EvidenceStrength.MODERATE

    def test_unknown_gets_correlational_weak(self):
        m = get_mapping_for_source("verbnet", "ZZZUNKNOWN", 1)
        assert m.constraint_type == ConstraintType.CORRELATIONAL
        assert m.evidence_strength == EvidenceStrength.WEAK

    def test_raw_value_propagates(self):
        m = get_mapping_for_source("verbnet", "GOOD", 1, raw_value=0.83)
        assert m.raw_value == 0.83

    def test_conditions_propagates(self):
        m = get_mapping_for_source("verbnet", "GOOD", 1, conditions="score > 0.5")
        assert m.conditions == "score > 0.5"

    def test_defaults_none(self):
        m = get_mapping_for_source("verbnet", "GOOD", 1)
        assert m.raw_value is None
        assert m.conditions is None

    def test_empty_source_concept_falsy_triggers_default(self):
        # Empty string is falsy → falls through to default
        m = get_mapping_for_source("verbnet", "GOOD", 1, source_concept="")
        assert m.source_concept == "verbnet_GOOD"


# ---------- get_all_covered_primitives ----------

class TestGetAllCoveredPrimitives:
    def test_returns_set(self):
        result = get_all_covered_primitives("verbnet")
        assert isinstance(result, set)

    def test_union_of_def_and_inf(self):
        result = get_all_covered_primitives("verbnet")
        # SOMEONE definitive, WANT inferential — both present
        assert "SOMEONE" in result
        assert "WANT" in result

    def test_unknown_source_empty(self):
        assert get_all_covered_primitives("nonexistent") == set()

    def test_count_matches_definitive_plus_inferential_unique(self):
        cov = SOURCE_PRIMITIVE_COVERAGE["verbnet"]
        expected = set(cov["definitive"]) | set(cov["inferential"])
        assert get_all_covered_primitives("verbnet") == expected

    def test_sentiwordnet_only_definitive(self):
        # sentiwordnet has empty inferential
        result = get_all_covered_primitives("sentiwordnet")
        assert result == {"GOOD"}

    def test_wiktionary_only_inferential(self):
        # wiktionary has empty definitive
        result = get_all_covered_primitives("wiktionary")
        assert "DO" in result
        # Empty definitive means result equals just inferential set
        assert result == set(SOURCE_PRIMITIVE_COVERAGE["wiktionary"]["inferential"])


# ---------- get_sources_for_primitive ----------

class TestGetSourcesForPrimitive:
    def test_returns_list(self):
        assert isinstance(get_sources_for_primitive("GOOD"), list)

    def test_good_has_multiple_sources(self):
        sources = get_sources_for_primitive("GOOD")
        # GOOD appears in many sources
        assert "verbnet" in sources
        assert "nrc_vad" in sources
        assert "sentiwordnet" in sources

    def test_unknown_primitive_empty(self):
        assert get_sources_for_primitive("ZZZ_NEVER_USED") == []

    def test_someone_in_verbnet(self):
        sources = get_sources_for_primitive("SOMEONE")
        assert "verbnet" in sources

    def test_includes_inferential_sources(self):
        # WANT is inferential in verbnet → should still appear
        sources = get_sources_for_primitive("WANT")
        assert "verbnet" in sources

    def test_excludes_sources_without_primitive(self):
        # sentiwordnet only covers GOOD — should not appear for MOVE
        sources = get_sources_for_primitive("MOVE")
        assert "sentiwordnet" not in sources


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
