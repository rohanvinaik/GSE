"""Manual contract tests for gse.curation.validation.bipolar_validator."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.validation.bipolar_validator import (
    BipolarValidator,
    ValidationResult,
    validate_bipolar,
)

# ---------- ValidationResult ----------

class TestValidationResultDC:
    def test_defaults(self):
        r = ValidationResult(passed=True, validation_type="x")
        assert r.violations == []
        assert r.details == ""


# ---------- BipolarValidator ----------

@pytest.fixture
def validator():
    return BipolarValidator()


class TestValidate:
    def test_empty_decomposition_passes(self, validator):
        result = validator.validate({})
        assert result.passed is True

    def test_only_one_pole_passes(self, validator):
        result = validator.validate({"GOOD": 1})
        assert result.passed is True

    def test_both_poles_fails(self, validator):
        result = validator.validate({"GOOD": 1, "BAD": 1})
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0]["type"] == "bipolar_conflict"

    def test_violation_records_values(self, validator):
        result = validator.validate({"GOOD": 1, "BAD": -1})
        assert result.violations[0]["positive_value"] == 1
        assert result.violations[0]["negative_value"] == -1

    def test_multiple_violations(self, validator):
        result = validator.validate({
            "GOOD": 1, "BAD": 1,
            "BIG": 1, "SMALL": 1,
        })
        assert len(result.violations) == 2

    def test_validation_type_label(self, validator):
        result = validator.validate({})
        assert result.validation_type == "bipolar"


# ---------- fix_violations ----------

class TestFixViolations:
    def test_no_violations_no_fix(self, validator):
        d = {"GOOD": 1}
        fixed, fixes = validator.fix_violations(d)
        assert fixed == d
        assert fixes == []

    def test_zeros_negative_pole(self, validator):
        fixed, fixes = validator.fix_violations({"GOOD": 1, "BAD": 1})
        assert fixed["BAD"] == 0
        assert fixed["GOOD"] == 1
        assert len(fixes) == 1

    def test_original_dict_unchanged(self, validator):
        original = {"GOOD": 1, "BAD": 1}
        fixed, _ = validator.fix_violations(original)
        # Original dict not mutated
        assert original["BAD"] == 1


# ---------- canonicalize ----------

class TestCanonicalize:
    def test_negative_pole_only_converts(self, validator):
        canonical, conversions = validator.canonicalize({"BAD": 1})
        # BAD=+1 → GOOD=-1, BAD=0
        assert canonical["GOOD"] == -1
        assert canonical["BAD"] == 0
        assert len(conversions) == 1

    def test_negative_neg_value_converts(self, validator):
        canonical, _ = validator.canonicalize({"BAD": -1})
        assert canonical["GOOD"] == 1
        assert canonical["BAD"] == 0

    def test_positive_pole_present_no_convert(self, validator):
        canonical, conversions = validator.canonicalize({"GOOD": 1, "BAD": 1})
        # Positive present → don't convert
        assert canonical == {"GOOD": 1, "BAD": 1}
        assert conversions == []

    def test_empty_unchanged(self, validator):
        canonical, conversions = validator.canonicalize({})
        assert canonical == {}
        assert conversions == []


# ---------- validate_bipolar (convenience) ----------

class TestValidateBipolarFunction:
    def test_returns_result(self):
        r = validate_bipolar({"GOOD": 1, "BAD": 1})
        assert isinstance(r, ValidationResult)
        assert r.passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
