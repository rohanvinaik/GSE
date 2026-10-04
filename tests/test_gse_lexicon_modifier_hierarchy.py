"""Manual contract tests for gse.lexicon.modifier_hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.lexicon.modifier_hierarchy import (
    ALL_MODIFIER_SCALES,
    CERTAINTY_WORDS,
    FREQUENCY_WORDS,
    INTENSITY_WORDS,
    QUANTITY_WORDS,
    get_all_modifiers,
    get_modifier_encoding,
)


class TestGetModifierEncoding:
    @pytest.mark.parametrize(
        "word,scale,direction,level",
        [
            ("very", "INTENSITY", 1, 2),
            ("extremely", "INTENSITY", 1, 4),
            ("slightly", "INTENSITY", -1, 3),
            ("absolutely", "INTENSITY", 1, 5),
            ("not at all", "INTENSITY", -1, 5),
            ("many", "QUANTITY", 1, 2),
            ("few", "QUANTITY", -1, 3),
            ("all", "QUANTITY", 1, 5),
            ("none", "QUANTITY", -1, 5),
            ("certainly", "CERTAINTY", 1, 4),
            ("maybe", "CERTAINTY", -1, 1),
            ("impossible", "CERTAINTY", -1, 5),
            ("often", "FREQUENCY", 1, 2),
            ("rarely", "FREQUENCY", -1, 4),
            ("always", "FREQUENCY", 1, 5),
            ("never", "FREQUENCY", -1, 5),
        ],
    )
    def test_known_words_return_correct_encoding(self, word, scale, direction, level):
        result = get_modifier_encoding(word)
        assert result == (scale, direction, level)

    def test_unknown_word_returns_none(self):
        assert get_modifier_encoding("zxqvbarbaz") is None

    def test_empty_string_returns_none(self):
        assert get_modifier_encoding("") is None

    def test_case_insensitive_lookup(self):
        assert get_modifier_encoding("VERY") == ("INTENSITY", 1, 2)
        assert get_modifier_encoding("Very") == ("INTENSITY", 1, 2)
        assert get_modifier_encoding("vErY") == ("INTENSITY", 1, 2)

    def test_returns_tuple(self):
        result = get_modifier_encoding("very")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_first_match_wins_across_scales(self):
        """If a word appears in multiple scales, the first one in iteration
        order should win (INTENSITY before QUANTITY before CERTAINTY before FREQUENCY).

        'absolutely' is in both INTENSITY and CERTAINTY — INTENSITY should win.
        """
        result = get_modifier_encoding("absolutely")
        assert result[0] == "INTENSITY"

    def test_a_little_in_intensity(self):
        """'a little' appears in both INTENSITY and QUANTITY — INTENSITY first."""
        result = get_modifier_encoding("a little")
        assert result[0] == "INTENSITY"


class TestGetAllModifiers:
    def test_returns_dict(self):
        result = get_all_modifiers()
        assert isinstance(result, dict)

    def test_intensity_words_present(self):
        result = get_all_modifiers()
        for w in ["very", "extremely", "slightly"]:
            assert w in result

    def test_quantity_words_present(self):
        result = get_all_modifiers()
        for w in ["many", "few", "all"]:
            assert w in result

    def test_certainty_words_present(self):
        result = get_all_modifiers()
        for w in ["certainly", "maybe", "probably"]:
            assert w in result

    def test_frequency_words_present(self):
        result = get_all_modifiers()
        for w in ["always", "never", "often"]:
            assert w in result

    def test_each_word_maps_to_scale_name(self):
        result = get_all_modifiers()
        scale_names = set(ALL_MODIFIER_SCALES.keys())
        for word, scale in result.items():
            assert scale in scale_names

    def test_count_matches_underlying_scales(self):
        """Total entries = sum of each scale's words (last-write-wins for duplicates)."""
        result = get_all_modifiers()
        # Some words appear in multiple scales; result uses the last-write
        # in iteration order. Confirm total is in plausible range.
        total_unique_words = set()
        for words_dict in ALL_MODIFIER_SCALES.values():
            total_unique_words.update(words_dict.keys())
        assert len(result) == len(total_unique_words)


class TestScaleStructure:
    """Validates that the underlying scale dicts have the expected shape."""

    @pytest.mark.parametrize(
        "scale_name,scale_dict",
        [
            ("INTENSITY", INTENSITY_WORDS),
            ("QUANTITY", QUANTITY_WORDS),
            ("CERTAINTY", CERTAINTY_WORDS),
            ("FREQUENCY", FREQUENCY_WORDS),
        ],
    )
    def test_each_word_has_direction_and_level(self, scale_name, scale_dict):
        for word, entry in scale_dict.items():
            assert "direction" in entry
            assert "level" in entry
            assert entry["direction"] in (-1, 1)
            assert 1 <= entry["level"] <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
