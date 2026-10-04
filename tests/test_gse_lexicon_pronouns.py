"""Manual contract tests for gse.lexicon.pronouns."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.lexicon.pronouns import (
    PRONOUN_ENCODINGS,
    get_all_pronouns,
    get_pronoun_encoding,
    is_pronoun,
)

# ---------- PRONOUN_ENCODINGS table ----------

class TestPronounEncodings:
    def test_i_first_person_nom_animate(self):
        i = PRONOUN_ENCODINGS["i"]
        assert i["primitives"] == {"SOMEONE": 1}
        assert i["gram"]["person"] == 1
        assert i["gram"]["case"] == "NOM"
        assert i["animacy"] == "ANIMATE"

    def test_me_accusative(self):
        assert PRONOUN_ENCODINGS["me"]["gram"]["case"] == "ACC"

    def test_my_genitive(self):
        assert PRONOUN_ENCODINGS["my"]["gram"]["case"] == "GEN"

    def test_myself_reflexive(self):
        assert PRONOUN_ENCODINGS["myself"]["gram"]["reflexivity"] == "REFLEXIVE"

    def test_we_plural(self):
        assert PRONOUN_ENCODINGS["we"]["gram"]["number"] == "PLURAL"

    def test_you_no_number(self):
        # English "you" is number-ambiguous
        assert "number" not in PRONOUN_ENCODINGS["you"]["gram"]

    def test_he_masculine(self):
        h = PRONOUN_ENCODINGS["he"]
        assert h["gram"]["gender"] == "MASC"
        assert h["gram"]["person"] == 3

    def test_she_feminine(self):
        assert PRONOUN_ENCODINGS["she"]["gram"]["gender"] == "FEM"

    def test_it_inanimate(self):
        it = PRONOUN_ENCODINGS["it"]
        assert it["primitives"] == {"SOMETHING": 1}
        assert it["animacy"] == "INANIMATE"
        assert it["gram"]["gender"] == "NEUT"

    def test_they_plural_animate(self):
        t = PRONOUN_ENCODINGS["they"]
        assert t["primitives"] == {"SOMEONE": 1}
        assert t["gram"]["number"] == "PLURAL"

    def test_who_interrogative_animate(self):
        w = PRONOUN_ENCODINGS["who"]
        assert w["is_interrogative"] is True
        assert w["primitives"] == {"SOMEONE": 1}

    def test_what_interrogative_inanimate(self):
        w = PRONOUN_ENCODINGS["what"]
        assert w["is_interrogative"] is True
        assert w["primitives"] == {"SOMETHING": 1}

    def test_nothing_negative_polarity(self):
        n = PRONOUN_ENCODINGS["nothing"]
        assert n["gram"]["polarity"] == "NEGATIVE"

    def test_this_proximal_deixis(self):
        assert PRONOUN_ENCODINGS["this"]["gram"]["deixis"] == "PROXIMAL"

    def test_those_distal_plural(self):
        t = PRONOUN_ENCODINGS["those"]
        assert t["gram"]["deixis"] == "DISTAL"
        assert t["gram"]["number"] == "PLURAL"

    def test_each_other_reciprocal(self):
        e = PRONOUN_ENCODINGS["each other"]
        assert e["gram"]["reflexivity"] == "RECIPROCAL"


# ---------- get_pronoun_encoding ----------

class TestGetPronounEncoding:
    def test_known_lowercase(self):
        result = get_pronoun_encoding("i")
        assert result["gram"]["person"] == 1

    def test_uppercase_normalized(self):
        # Function does .lower() internally
        result = get_pronoun_encoding("I")
        assert result is not None
        assert result["gram"]["person"] == 1

    def test_mixed_case(self):
        assert get_pronoun_encoding("She") is not None

    def test_unknown_returns_none(self):
        assert get_pronoun_encoding("xyzzy") is None

    def test_empty_returns_none(self):
        assert get_pronoun_encoding("") is None

    def test_multi_word_pronoun(self):
        # "no one" is a defined pronoun
        result = get_pronoun_encoding("no one")
        assert result is not None
        assert result["gram"]["polarity"] == "NEGATIVE"


# ---------- is_pronoun ----------

class TestIsPronoun:
    def test_known_pronoun_true(self):
        assert is_pronoun("she") is True

    def test_uppercase_normalized(self):
        assert is_pronoun("SHE") is True

    def test_unknown_returns_false(self):
        assert is_pronoun("xyzzy") is False

    def test_empty_returns_false(self):
        assert is_pronoun("") is False

    def test_multi_word(self):
        assert is_pronoun("each other") is True


# ---------- get_all_pronouns ----------

class TestGetAllPronouns:
    def test_returns_list(self):
        result = get_all_pronouns()
        assert isinstance(result, list)

    def test_includes_common_pronouns(self):
        result = get_all_pronouns()
        for p in ["i", "you", "he", "she", "it", "they", "we"]:
            assert p in result

    def test_count_matches_dict(self):
        assert len(get_all_pronouns()) == len(PRONOUN_ENCODINGS)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
