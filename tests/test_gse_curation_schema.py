"""Manual contract tests for gse.curation.schema."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.schema import (
    ALL_PRIMITIVES,
    BANK_0_PRIMITIVES,
    BANK_2_PRIMITIVES,
    BANK_7_PRIMITIVES,
    BIPOLAR_PAIRS,
    BIPOLAR_PARTNER,
    BIPOLAR_PRIMITIVES,
    CERTAINTY_HIERARCHY,
    INTENSITY_HIERARCHY,
    PRIMITIVE_TO_BANK,
    QUANTITY_HIERARCHY,
    SCHEMA,
    get_bipolar_partner,
    get_primitive_bank,
    is_bipolar_primitive,
    validate_primitive_name,
)

# ---------- Constants ----------


class TestAllPrimitives:
    def test_count_is_72(self):
        assert len(ALL_PRIMITIVES) == 72

    def test_no_duplicates(self):
        assert len(set(ALL_PRIMITIVES)) == 72

    def test_includes_known_primitives(self):
        for p in ["GOOD", "BAD", "BIG", "SMALL", "THINK", "FEEL"]:
            assert p in ALL_PRIMITIVES


class TestBankPrimitives:
    def test_bank_0_has_substantives(self):
        assert "SOMEONE" in BANK_0_PRIMITIVES
        assert "SOMETHING" in BANK_0_PRIMITIVES

    def test_bank_2_has_evaluators(self):
        assert "GOOD" in BANK_2_PRIMITIVES
        assert "BAD" in BANK_2_PRIMITIVES

    def test_bank_7_has_logical(self):
        assert "NOT" in BANK_7_PRIMITIVES
        assert "TRUE" in BANK_7_PRIMITIVES


class TestPrimitiveToBank:
    def test_someone_in_bank_0(self):
        assert PRIMITIVE_TO_BANK["SOMEONE"] == 0

    def test_good_in_bank_2(self):
        assert PRIMITIVE_TO_BANK["GOOD"] == 2

    def test_not_in_bank_7(self):
        assert PRIMITIVE_TO_BANK["NOT"] == 7

    def test_all_primitives_have_bank(self):
        for p in ALL_PRIMITIVES:
            assert p in PRIMITIVE_TO_BANK


class TestBipolarPairs:
    def test_count_is_14(self):
        assert len(BIPOLAR_PAIRS) == 14

    def test_good_bad_pair(self):
        assert ("GOOD", "BAD") in BIPOLAR_PAIRS

    def test_big_small_pair(self):
        assert ("BIG", "SMALL") in BIPOLAR_PAIRS

    def test_all_pairs_are_2_tuples(self):
        for p in BIPOLAR_PAIRS:
            assert isinstance(p, tuple)
            assert len(p) == 2


class TestBipolarPartner:
    def test_good_partner_bad(self):
        assert BIPOLAR_PARTNER["GOOD"] == "BAD"

    def test_bad_partner_good(self):
        # Reverse direction also indexed
        assert BIPOLAR_PARTNER["BAD"] == "GOOD"

    def test_non_bipolar_not_in_dict(self):
        # SOMETHING is not bipolar
        assert "SOMETHING" not in BIPOLAR_PARTNER


class TestBipolarPrimitives:
    def test_count_is_28(self):
        # 14 pairs × 2 = 28 primitives
        assert len(BIPOLAR_PRIMITIVES) == 28

    def test_good_and_bad_both(self):
        assert "GOOD" in BIPOLAR_PRIMITIVES
        assert "BAD" in BIPOLAR_PRIMITIVES

    def test_someone_not_bipolar(self):
        assert "SOMEONE" not in BIPOLAR_PRIMITIVES


class TestHierarchies:
    def test_quantity_centered_at_middle(self):
        assert QUANTITY_HIERARCHY["MIDDLE"] == 0
        assert QUANTITY_HIERARCHY["NONE"] == -3
        assert QUANTITY_HIERARCHY["ALL"] == 3

    def test_intensity_centered_at_moderate(self):
        assert INTENSITY_HIERARCHY["MODERATE"] == 0
        assert INTENSITY_HIERARCHY["BARELY"] == -2

    def test_certainty_levels(self):
        assert CERTAINTY_HIERARCHY["IMPOSSIBLE"] == -3
        assert CERTAINTY_HIERARCHY["CERTAIN"] == 3


class TestSchema:
    def test_schema_string_contains_tables(self):
        assert "CREATE TABLE IF NOT EXISTS lexemes" in SCHEMA
        assert "CREATE TABLE IF NOT EXISTS primitive_values" in SCHEMA
        assert "CREATE TABLE IF NOT EXISTS validation_results" in SCHEMA

    def test_schema_has_indices(self):
        assert "CREATE INDEX IF NOT EXISTS idx_lexemes_lemma" in SCHEMA


# ---------- get_primitive_bank ----------


class TestGetPrimitiveBank:
    def test_known_primitive(self):
        assert get_primitive_bank("GOOD") == 2

    def test_unknown_returns_neg1(self):
        assert get_primitive_bank("XYZZY") == -1


# ---------- is_bipolar_primitive ----------


class TestIsBipolarPrimitive:
    def test_bipolar_true(self):
        assert is_bipolar_primitive("GOOD") is True

    def test_non_bipolar_false(self):
        assert is_bipolar_primitive("THINK") is False

    def test_unknown_false(self):
        assert is_bipolar_primitive("XYZZY") is False


# ---------- get_bipolar_partner ----------


class TestGetBipolarPartner:
    def test_known(self):
        assert get_bipolar_partner("GOOD") == "BAD"
        assert get_bipolar_partner("BAD") == "GOOD"

    def test_unknown_returns_none(self):
        assert get_bipolar_partner("THINK") is None
        assert get_bipolar_partner("XYZZY") is None


# ---------- validate_primitive_name ----------


class TestValidatePrimitiveName:
    def test_known_true(self):
        assert validate_primitive_name("GOOD") is True
        assert validate_primitive_name("THINK") is True

    def test_unknown_false(self):
        assert validate_primitive_name("XYZZY") is False

    def test_lowercase_false(self):
        # Primitives are uppercase
        assert validate_primitive_name("good") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
