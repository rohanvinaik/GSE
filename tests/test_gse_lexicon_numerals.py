"""Manual contract tests for gse.lexicon.numerals."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.lexicon.numerals import (
    NUMERAL_ENCODINGS,
    get_all_numerals,
    get_numeral_encoding,
    is_numeral,
    validate_mutual_transparency,
)


class TestGetNumeralEncoding:
    @pytest.mark.parametrize("word,expected_keys", [
        ("0", {"primitives", "hierarchy", "quantity_type"}),
        ("zero", {"primitives", "hierarchy", "quantity_type"}),
        ("1", {"primitives", "hierarchy", "quantity_type"}),
        ("one", {"primitives", "hierarchy", "quantity_type"}),
        ("two", {"primitives", "hierarchy", "quantity_type"}),
        ("first", {"primitives", "hierarchy", "quantity_type"}),
        ("half", {"primitives", "hierarchy", "quantity_type"}),
        ("double", {"primitives", "hierarchy", "quantity_type"}),
    ])
    def test_known_numerals_return_dict_with_keys(self, word, expected_keys):
        result = get_numeral_encoding(word)
        assert result is not None
        assert set(result.keys()) == expected_keys

    def test_unknown_word_returns_none(self):
        assert get_numeral_encoding("zxqv") is None

    def test_case_insensitive(self):
        result = get_numeral_encoding("ONE")
        assert result is not None
        assert result["primitives"].get("SING") == 1

    def test_zero_has_zero_primitive(self):
        result = get_numeral_encoding("zero")
        assert result["primitives"].get("ZERO") == 1

    def test_one_has_sing_and_one(self):
        result = get_numeral_encoding("one")
        assert result["primitives"].get("SING") == 1
        assert result["primitives"].get("ONE") == 1

    def test_two_has_sing_plur_two(self):
        result = get_numeral_encoding("two")
        assert result["primitives"].get("SING") == 1
        assert result["primitives"].get("PLUR") == 1
        assert result["primitives"].get("TWO") == 1

    def test_cardinal_quantity_type(self):
        result = get_numeral_encoding("five")
        assert result["quantity_type"] == "cardinal"

    def test_ordinal_quantity_type(self):
        result = get_numeral_encoding("first")
        assert result["quantity_type"] == "ordinal"

    def test_fraction_quantity_type(self):
        result = get_numeral_encoding("half")
        assert result["quantity_type"] == "fraction"

    def test_multiplier_quantity_type(self):
        result = get_numeral_encoding("double")
        assert result["quantity_type"] == "multiplier"

    def test_article_quantity_type(self):
        result = get_numeral_encoding("a")
        assert result["quantity_type"] == "article"

    def test_quantifier_quantity_type(self):
        result = get_numeral_encoding("many")
        assert result["quantity_type"] == "quantifier"


class TestIsNumeral:
    @pytest.mark.parametrize("word", [
        "0", "1", "one", "two", "three", "first", "half", "many", "all", "none",
    ])
    def test_known_numerals_return_true(self, word):
        assert is_numeral(word)

    @pytest.mark.parametrize("word", ["dog", "cat", "happy", "zxqv", ""])
    def test_unknown_words_return_false(self, word):
        assert not is_numeral(word)

    def test_case_insensitive(self):
        assert is_numeral("ONE")
        assert is_numeral("First")


class TestGetAllNumerals:
    def test_returns_list(self):
        result = get_all_numerals()
        assert isinstance(result, list)

    def test_contains_known_numerals(self):
        result = get_all_numerals()
        for w in ["0", "1", "one", "two", "first", "half", "many"]:
            assert w in result

    def test_length_matches_encoding_dict(self):
        result = get_all_numerals()
        assert len(result) == len(NUMERAL_ENCODINGS)


class TestValidateMutualTransparency:
    def test_zero_only_is_valid(self):
        assert validate_mutual_transparency({"ZERO": 1})

    def test_sing_only_is_valid(self):
        assert validate_mutual_transparency({"SING": 1})

    def test_plur_only_is_valid(self):
        assert validate_mutual_transparency({"PLUR": 1})

    def test_sing_and_plur_is_valid(self):
        assert validate_mutual_transparency({"SING": 1, "PLUR": 1})

    def test_empty_is_valid(self):
        assert validate_mutual_transparency({})

    def test_zero_and_sing_is_invalid(self):
        assert not validate_mutual_transparency({"ZERO": 1, "SING": 1})

    def test_zero_and_plur_is_invalid(self):
        assert not validate_mutual_transparency({"ZERO": 1, "PLUR": 1})

    def test_zero_and_both_is_invalid(self):
        assert not validate_mutual_transparency({"ZERO": 1, "SING": 1, "PLUR": 1})

    def test_zero_with_sing_zero_is_valid(self):
        """ZERO=1 with SING=0 (absent or zero) is valid."""
        assert validate_mutual_transparency({"ZERO": 1, "SING": 0})

    def test_zero_with_plur_zero_is_valid(self):
        assert validate_mutual_transparency({"ZERO": 1, "PLUR": 0})

    def test_unrelated_primitives_pass_through(self):
        """Primitives other than SING/PLUR/ZERO don't affect validation."""
        assert validate_mutual_transparency({"SING": 1, "NUMBER": 1, "ONE": 1})
        assert not validate_mutual_transparency({"ZERO": 1, "SING": 1, "NUMBER": 1})

    def test_all_predefined_encodings_satisfy_invariant(self):
        """Every numeral in the dict should satisfy the mutual transparency rule."""
        for word, encoding in NUMERAL_ENCODINGS.items():
            primitives = encoding["primitives"]
            assert validate_mutual_transparency(primitives), \
                f"Numeral '{word}' violates mutual transparency: {primitives}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
