"""Manual contract tests for gse.curation.constraint_aggregation.engine."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.constraint_aggregation.engine import (
    ConstraintAggregationEngine,
    test_word,
)

# ``test_word`` is a convenience function on the engine, not a test; its ``test_``
# prefix makes pytest collect it as a module-level test ("fixture 'word' not found").
# Mark it non-collectable so it stays importable for the TestTestWord suite below.
test_word.__test__ = False
from gse.curation.constraint_aggregation.types import (
    PrimitiveConstraint,
    WordConstraintProfile,
)


class FakeParser:
    """In-memory parser stub used to exercise the engine without external sources."""

    def __init__(self, primitives_map=None, entries_count=0):
        # primitives_map: dict[word -> dict[primitive -> value]]
        self.primitives_map = primitives_map or {}
        self.entries = list(range(entries_count))
        self.closed = False

    def load(self):
        return True

    def to_primitives(self, word):
        return self.primitives_map.get(word, {})

    def close(self):
        self.closed = True


# ---------- __init__ ----------


class TestInit:
    def test_default_min_auto_apply(self):
        e = ConstraintAggregationEngine()
        assert e.min_auto_apply_confidence == 0.8

    def test_default_include_large(self):
        e = ConstraintAggregationEngine()
        assert e.include_large_sources is True

    def test_custom_threshold(self):
        e = ConstraintAggregationEngine(min_auto_apply_confidence=0.95)
        assert e.min_auto_apply_confidence == 0.95

    def test_include_large_false(self):
        e = ConstraintAggregationEngine(include_large_sources=False)
        assert e.include_large_sources is False

    def test_parsers_empty(self):
        assert ConstraintAggregationEngine().parsers == {}

    def test_loaded_false(self):
        assert ConstraintAggregationEngine()._loaded is False


# ---------- collect_raw_source_data ----------


class TestCollectRawSourceData:
    def test_empty_parsers(self):
        e = ConstraintAggregationEngine()
        assert e.collect_raw_source_data("dog") == {}

    def test_collects_active_primitives(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1, "BAD": 0}})
        result = e.collect_raw_source_data("dog")
        assert result == {"verbnet": "SOMEONE=1"}

    def test_skips_zero_values(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser({"dog": {"BAD": 0, "GOOD": 0}})
        # All zero → no active → source omitted
        assert e.collect_raw_source_data("dog") == {}

    def test_multiple_active_joined(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1, "BIG": -1}})
        result = e.collect_raw_source_data("dog")
        # Order may vary depending on dict iteration; check both pieces present
        assert "verbnet" in result
        assert "SOMEONE=1" in result["verbnet"]
        assert "BIG=-1" in result["verbnet"]

    def test_swallows_parser_exception(self):
        e = ConstraintAggregationEngine()
        bad = MagicMock()
        bad.to_primitives.side_effect = RuntimeError("boom")
        e.parsers["broken"] = bad
        # Should not raise
        assert e.collect_raw_source_data("dog") == {}

    def test_no_word_in_map(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser({"cat": {"X": 1}})
        assert e.collect_raw_source_data("dog") == {}


# ---------- collect_evidence ----------


class TestCollectEvidence:
    def test_auto_loads(self):
        e = ConstraintAggregationEngine()
        with patch.object(e, "load_sources") as mock_load:
            mock_load.side_effect = lambda: setattr(e, "_loaded", True)
            e.collect_evidence("dog")
            mock_load.assert_called_once()

    def test_no_auto_load_when_loaded(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        with patch.object(e, "load_sources") as mock_load:
            e.collect_evidence("dog")
            mock_load.assert_not_called()

    def test_empty_when_no_parsers(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        assert e.collect_evidence("dog") == {}

    def test_collects_mapping(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1}})
        result = e.collect_evidence("dog")
        assert "SOMEONE" in result
        assert len(result["SOMEONE"]) == 1
        assert result["SOMEONE"][0].source_name == "verbnet"
        assert result["SOMEONE"][0].target_primitive == "SOMEONE"
        assert result["SOMEONE"][0].target_value == 1

    def test_skips_zero_value(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 0}})
        assert e.collect_evidence("dog") == {}

    def test_source_concept_format(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1}})
        result = e.collect_evidence("dog")
        assert result["SOMEONE"][0].source_concept == "verbnet:SOMEONE"

    def test_handles_parser_exception(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        bad = MagicMock()
        bad.to_primitives.side_effect = RuntimeError("boom")
        e.parsers["broken"] = bad
        assert e.collect_evidence("dog") == {}

    def test_multiple_sources_same_primitive(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1}})
        e.parsers["framenet"] = FakeParser({"dog": {"SOMEONE": 1}})
        result = e.collect_evidence("dog")
        assert len(result["SOMEONE"]) == 2

    def test_negative_value_preserved(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"GOOD": -1}})
        result = e.collect_evidence("dog")
        assert result["GOOD"][0].target_value == -1


# ---------- aggregate_constraints ----------


class TestAggregateConstraints:
    def test_returns_profile(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1}})
        result = e.aggregate_constraints("dog")
        assert isinstance(result, WordConstraintProfile)

    def test_word_field(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({})
        result = e.aggregate_constraints("dog")
        assert result.word == "dog"

    def test_pos_is_none(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({})
        assert e.aggregate_constraints("dog").pos is None

    def test_sources_checked_lists_loaded_parsers(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({})
        e.parsers["framenet"] = FakeParser({})
        result = e.aggregate_constraints("dog")
        assert set(result.sources_checked) == {"verbnet", "framenet"}

    def test_positive_majority(self):
        # 2 positive, 1 negative → final_value=+1
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["s1"] = FakeParser({"dog": {"GOOD": 1}})
        e.parsers["s2"] = FakeParser({"dog": {"GOOD": 1}})
        e.parsers["s3"] = FakeParser({"dog": {"GOOD": -1}})
        result = e.aggregate_constraints("dog")
        assert result.constraints["GOOD"].value == 1
        assert "s1" in result.constraints["GOOD"].supporting_sources
        assert "s3" in result.constraints["GOOD"].conflicting_sources

    def test_negative_majority(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["s1"] = FakeParser({"dog": {"GOOD": -1}})
        e.parsers["s2"] = FakeParser({"dog": {"GOOD": -1}})
        e.parsers["s3"] = FakeParser({"dog": {"GOOD": 1}})
        result = e.aggregate_constraints("dog")
        assert result.constraints["GOOD"].value == -1

    def test_tie_uses_strength_tiebreaker(self):
        # 1 positive (verbnet=strong via DEFINITIVE), 1 negative (sentiwordnet=strong)
        # Tied count → strength tiebreak. SOMEONE definitive in verbnet, not in sentiwordnet
        # → verbnet=STRONG (1.0), sentiwordnet=WEAK (0.4 — since SOMEONE not in coverage)
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"SOMEONE": 1}})
        e.parsers["sentiwordnet"] = FakeParser({"dog": {"SOMEONE": -1}})
        result = e.aggregate_constraints("dog")
        # Strength tiebreak favors verbnet (pos)
        assert result.constraints["SOMEONE"].value == 1

    def test_tie_negative_wins_when_stronger(self):
        # Tied count, but negative side has higher strength
        # GOOD: nrc_vad=DEFINITIVE, sentiwordnet=DEFINITIVE → both STRONG
        # If pos_strength >= neg_strength → positive wins (the >= branch)
        # To make negative win we need neg_strength > pos_strength strictly
        # Setting: pos has weak source (SOMEONE on sentiwordnet → CORRELATIONAL → WEAK)
        #          neg has strong source (GOOD on nrc_vad → DEFINITIVE → STRONG)
        # But primitives must match for it to be a tie scenario...
        # Use: pos=conceptnet (correlational for GOOD), neg=nrc_vad (definitive for GOOD)
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["concreteness"] = FakeParser({"dog": {"GOOD": 1}})  # GOOD not covered → WEAK
        e.parsers["nrc_vad"] = FakeParser({"dog": {"GOOD": -1}})  # GOOD definitive → STRONG
        result = e.aggregate_constraints("dog")
        # Neg has higher strength → final value -1
        assert result.constraints["GOOD"].value == -1

    def test_no_evidence_no_constraints(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["s1"] = FakeParser({})
        result = e.aggregate_constraints("dog")
        assert result.constraints == {}

    def test_sources_with_data_excludes_empty(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["yes"] = FakeParser({"dog": {"GOOD": 1}})
        e.parsers["no"] = FakeParser({})
        result = e.aggregate_constraints("dog")
        assert "yes" in result.sources_with_data
        assert "no" not in result.sources_with_data

    def test_evidence_records_attached(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.parsers["verbnet"] = FakeParser({"dog": {"GOOD": 1}})
        result = e.aggregate_constraints("dog")
        assert len(result.constraints["GOOD"].evidence_records) == 1


# ---------- get_sources_for_primitive ----------


class TestGetSourcesForPrimitive:
    def test_returns_list(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser()
        assert isinstance(e.get_sources_for_primitive("SOMEONE"), list)

    def test_filters_to_loaded_only(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser()
        # Other sources not loaded — even if they cover SOMEONE, shouldn't appear
        result = e.get_sources_for_primitive("SOMEONE")
        assert "verbnet" in result
        assert "framenet" not in result

    def test_empty_when_no_parsers(self):
        e = ConstraintAggregationEngine()
        assert e.get_sources_for_primitive("SOMEONE") == []

    def test_unknown_primitive_empty(self):
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser()
        assert e.get_sources_for_primitive("ZZZ_UNKNOWN") == []

    def test_includes_inferential(self):
        # WANT is inferential in verbnet → should still appear
        e = ConstraintAggregationEngine()
        e.parsers["verbnet"] = FakeParser()
        assert "verbnet" in e.get_sources_for_primitive("WANT")


# ---------- close ----------


class TestClose:
    def test_calls_parser_close(self):
        e = ConstraintAggregationEngine()
        p1 = FakeParser()
        e.parsers["x"] = p1
        e.close()
        assert p1.closed is True

    def test_clears_parsers(self):
        e = ConstraintAggregationEngine()
        e.parsers["x"] = FakeParser()
        e.close()
        assert e.parsers == {}

    def test_resets_loaded(self):
        e = ConstraintAggregationEngine()
        e._loaded = True
        e.close()
        assert e._loaded is False

    def test_skips_when_no_close_method(self):
        e = ConstraintAggregationEngine()
        parser_no_close = object()  # bare object — has no .close
        e.parsers["x"] = parser_no_close
        # Should not raise
        e.close()
        assert e.parsers == {}


# ---------- test_word convenience ----------


class TestTestWord:
    def test_returns_profile(self, capsys):
        # Patch the engine class to use mock parsers
        with patch("gse.curation.constraint_aggregation.engine.ConstraintAggregationEngine") as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.aggregate_constraints.return_value = WordConstraintProfile(
                word="run",
                pos=None,
                sources_checked=[],
                sources_with_data=[],
                constraints={},
                conflicts=[],
                overall_confidence=0.5,
                review_required=False,
                review_reasons=[],
            )
            result = test_word("run", verbose=False)
            assert isinstance(result, WordConstraintProfile)
            assert result.word == "run"

    def test_verbose_prints(self, capsys):
        with patch("gse.curation.constraint_aggregation.engine.ConstraintAggregationEngine") as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.aggregate_constraints.return_value = WordConstraintProfile(
                word="run",
                pos=None,
                sources_checked=[],
                sources_with_data=["verbnet"],
                constraints={
                    "GOOD": PrimitiveConstraint(
                        primitive="GOOD",
                        value=1,
                        confidence=0.9,
                        supporting_sources=["verbnet"],
                        conflicting_sources=[],
                        evidence_records=[],
                        status="auto_apply",
                    ),
                },
                conflicts=[],
                overall_confidence=0.9,
                review_required=True,
                review_reasons=["test"],
            )
            test_word("run", verbose=True)
            captured = capsys.readouterr()
            assert "run" in captured.out
            assert "GOOD" in captured.out

    def test_calls_aggregate(self):
        with patch("gse.curation.constraint_aggregation.engine.ConstraintAggregationEngine") as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.aggregate_constraints.return_value = WordConstraintProfile(
                word="run",
                pos=None,
                sources_checked=[],
                sources_with_data=[],
                constraints={},
                conflicts=[],
                overall_confidence=0.0,
                review_required=False,
                review_reasons=[],
            )
            test_word("run", verbose=False)
            mock_engine.aggregate_constraints.assert_called_once_with("run")

    def test_uses_no_large_sources(self):
        with patch("gse.curation.constraint_aggregation.engine.ConstraintAggregationEngine") as MockEngine:
            mock_engine = MockEngine.return_value
            mock_engine.aggregate_constraints.return_value = WordConstraintProfile(
                word="run",
                pos=None,
                sources_checked=[],
                sources_with_data=[],
                constraints={},
                conflicts=[],
                overall_confidence=0.0,
                review_required=False,
                review_reasons=[],
            )
            test_word("run", verbose=False)
            MockEngine.assert_called_with(include_large_sources=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
