"""Manual contract tests for gse.curation.validation.coverage_checker."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.schema import ALL_PRIMITIVES
from gse.curation.validation.coverage_checker import (
    CoverageChecker,
    ValidationResult,
    ensure_full_coverage,
    validate_coverage,
)


@pytest.fixture
def checker():
    return CoverageChecker()


class TestInit:
    def test_loads_primitive_set(self, checker):
        assert checker.primitive_count == 72
        assert len(checker.all_primitives) == 72


class TestValidate:
    def test_empty_fails(self, checker):
        result = checker.validate({})
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0]["count"] == 72

    def test_full_coverage_passes(self, checker):
        # All 72 primitives present
        decomp = {p: 0 for p in ALL_PRIMITIVES}
        result = checker.validate(decomp)
        assert result.passed is True
        assert result.violations == []

    def test_partial_coverage_fails(self, checker):
        decomp = {p: 0 for p in ALL_PRIMITIVES[:10]}
        result = checker.validate(decomp)
        assert result.passed is False

    def test_validation_type(self, checker):
        result = checker.validate({})
        assert result.validation_type == "coverage"


class TestFillMissing:
    def test_fills_to_72_primitives(self, checker):
        decomp = {"GOOD": 1}
        complete = checker.fill_missing(decomp)
        assert len(complete) == 72
        assert complete["GOOD"] == 1

    def test_default_value_zero(self, checker):
        complete = checker.fill_missing({})
        for v in complete.values():
            assert v == 0

    def test_custom_default(self, checker):
        complete = checker.fill_missing({}, default_value=-1)
        assert complete["SOMEONE"] == -1


class TestGetCoverageStats:
    def test_empty_stats(self, checker):
        stats = checker.get_coverage_stats({})
        assert stats["present"] == 0
        assert stats["missing"] == 72
        assert stats["non_zero"] == 0

    def test_positive_count(self, checker):
        decomp = {"GOOD": 1, "BIG": 1, "SOMEONE": 1}
        stats = checker.get_coverage_stats(decomp)
        assert stats["present"] == 3
        assert stats["positive"] == 3
        assert stats["negative"] == 0

    def test_negative_count(self, checker):
        decomp = {"GOOD": -1, "BIG": -1}
        stats = checker.get_coverage_stats(decomp)
        assert stats["negative"] == 2

    def test_by_bank(self, checker):
        # GOOD/BIG in bank 2, SOMEONE in bank 0
        decomp = {"GOOD": 1, "BIG": 1, "SOMEONE": 1}
        stats = checker.get_coverage_stats(decomp)
        # Bank 2 has 2 present, Bank 0 has 1
        assert stats["by_bank"][2]["present"] == 2
        assert stats["by_bank"][0]["present"] == 1

    def test_bipolar_coverage(self, checker):
        # Both GOOD and BAD = full bipolar pair → 2/28 coverage
        decomp = {"GOOD": 1, "BAD": 0}
        stats = checker.get_coverage_stats(decomp)
        assert stats["bipolar_coverage"] == pytest.approx(2 / 28)


# ---------- convenience functions ----------


class TestValidateCoverageFunction:
    def test_works(self):
        r = validate_coverage({})
        assert isinstance(r, ValidationResult)


class TestEnsureFullCoverage:
    def test_returns_full_72(self):
        result = ensure_full_coverage({"GOOD": 1})
        assert len(result) == 72


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
