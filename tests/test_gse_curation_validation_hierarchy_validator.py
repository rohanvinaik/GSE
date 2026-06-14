"""Manual contract tests for gse.curation.validation.hierarchy_validator."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.validation.hierarchy_validator import (
    HierarchyValidator,
    ValidationResult,
    validate_hierarchy,
)


@pytest.fixture
def validator():
    return HierarchyValidator()


# ---------- validate ----------

class TestValidate:
    def test_empty_passes(self, validator):
        result = validator.validate({})
        assert result.passed is True

    def test_hier_plus_and_minus_conflict(self, validator):
        result = validator.validate({"HIER_PLUS": 1, "HIER_MINUS": 1})
        assert result.passed is False
        # First violation is hierarchy_conflict; orphan markers also flagged
        types = [v["type"] for v in result.violations]
        assert "hierarchy_conflict" in types

    def test_orphan_markers_with_no_base(self, validator):
        # HIER_PLUS without QUANTITY/INTENSITY/CERTAINTY base
        result = validator.validate({"HIER_PLUS": 1})
        types = [v["type"] for v in result.violations]
        assert "orphaned_markers" in types

    def test_base_active_with_marker_ok(self, validator):
        result = validator.validate({"QUANTITY": 1, "HIER_PLUS": 1})
        # Has active base, only HIER_PLUS marker → no conflict
        assert result.passed is True

    def test_validation_type(self, validator):
        result = validator.validate({})
        assert result.validation_type == "hierarchy"


# ---------- infer_hierarchy_level ----------

class TestInferHierarchyLevel:
    def test_no_active_base_empty(self, validator):
        levels = validator.infer_hierarchy_level({})
        assert levels == {}

    def test_hier_plus_positive_level(self, validator):
        levels = validator.infer_hierarchy_level({
            "QUANTITY": 1, "HIER_PLUS": 2,
        })
        assert levels["QUANTITY"] == 2

    def test_hier_minus_negative_level(self, validator):
        levels = validator.infer_hierarchy_level({
            "INTENSITY": 1, "HIER_MINUS": 1,
        })
        assert levels["INTENSITY"] == -1

    def test_no_markers_neutral_level(self, validator):
        levels = validator.infer_hierarchy_level({"CERTAINTY": 1})
        assert levels["CERTAINTY"] == 0


# ---------- get_hierarchy_word ----------

class TestGetHierarchyWord:
    def test_quantity_levels(self, validator):
        assert validator.get_hierarchy_word("QUANTITY", 0) == "MIDDLE"
        assert validator.get_hierarchy_word("QUANTITY", 3) == "ALL"
        assert validator.get_hierarchy_word("QUANTITY", -3) == "NONE"

    def test_intensity_levels(self, validator):
        assert validator.get_hierarchy_word("INTENSITY", 0) == "MODERATE"
        assert validator.get_hierarchy_word("INTENSITY", -2) == "BARELY"

    def test_certainty_levels(self, validator):
        assert validator.get_hierarchy_word("CERTAINTY", -3) == "IMPOSSIBLE"
        assert validator.get_hierarchy_word("CERTAINTY", 3) == "CERTAIN"

    def test_unknown_base_returns_label(self, validator):
        result = validator.get_hierarchy_word("UNKNOWN", 2)
        # Falls through to default label
        assert "UNKNOWN" in result
        assert "+2" in result

    def test_invalid_level_returns_label(self, validator):
        # No level 99 in any hierarchy
        result = validator.get_hierarchy_word("QUANTITY", 99)
        assert "QUANTITY" in result


# ---------- validate_hierarchy ----------

class TestValidateHierarchyFunction:
    def test_works(self):
        r = validate_hierarchy({"HIER_PLUS": 1, "HIER_MINUS": 1})
        assert isinstance(r, ValidationResult)
        assert r.passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
