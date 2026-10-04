"""Manual contract tests for gse.lexicon.function_words."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.lexicon.function_words import (
    CONJUNCTION_ENCODINGS,
    DETERMINER_ENCODINGS,
    PREPOSITION_ENCODINGS,
    get_conjunction_encoding,
    get_determiner_encoding,
    get_preposition_encoding,
)

# ---------- DETERMINER_ENCODINGS ----------


class TestDeterminerEncodings:
    def test_the_definite(self):
        assert DETERMINER_ENCODINGS["the"] == {"definiteness": "DEFINITE"}

    def test_a_indefinite_singular(self):
        d = DETERMINER_ENCODINGS["a"]
        assert d["definiteness"] == "INDEFINITE"
        assert d["number"] == "SINGULAR"

    def test_this_demonstrative_proximal(self):
        d = DETERMINER_ENCODINGS["this"]
        assert d["definiteness"] == "DEMONSTRATIVE"
        assert d["deixis"] == "PROXIMAL"
        assert d["number"] == "SINGULAR"

    def test_those_demonstrative_distal_plural(self):
        d = DETERMINER_ENCODINGS["those"]
        assert d["deixis"] == "DISTAL"
        assert d["number"] == "PLURAL"

    def test_every_universal(self):
        d = DETERMINER_ENCODINGS["every"]
        assert d["definiteness"] == "UNIVERSAL"

    def test_no_negative_polarity(self):
        d = DETERMINER_ENCODINGS["no"]
        assert d["polarity"] == "NEGATIVE"

    def test_his_possessive_masc(self):
        d = DETERMINER_ENCODINGS["his"]
        assert d["definiteness"] == "POSSESSIVE"
        assert d["person"] == 3
        assert d["gender"] == "MASC"

    def test_her_possessive_fem(self):
        assert DETERMINER_ENCODINGS["her"]["gender"] == "FEM"

    def test_its_possessive_neut(self):
        assert DETERMINER_ENCODINGS["its"]["gender"] == "NEUT"


# ---------- CONJUNCTION_ENCODINGS ----------


class TestConjunctionEncodings:
    def test_and_additive(self):
        c = CONJUNCTION_ENCODINGS["and"]
        assert c["clause_relation"] == "ADDITIVE"

    def test_or_disjunctive(self):
        assert CONJUNCTION_ENCODINGS["or"]["coord_type"] == "DISJUNCTIVE"

    def test_but_adversative(self):
        assert CONJUNCTION_ENCODINGS["but"]["coord_type"] == "ADVERSATIVE"

    def test_nor_negative(self):
        c = CONJUNCTION_ENCODINGS["nor"]
        assert c["polarity"] == "NEGATIVE"
        assert c["clause_relation"] == "NEGATIVE_ADDITIVE"

    def test_when_simultaneous(self):
        c = CONJUNCTION_ENCODINGS["when"]
        assert c["temporal_type"] == "SIMULTANEOUS"

    def test_after_posterior(self):
        assert CONJUNCTION_ENCODINGS["after"]["temporal_type"] == "POSTERIOR"

    def test_because_causal_reason(self):
        c = CONJUNCTION_ENCODINGS["because"]
        assert c["clause_relation"] == "CAUSAL"
        assert c["causal_type"] == "REASON"

    def test_if_conditional_hypothetical(self):
        c = CONJUNCTION_ENCODINGS["if"]
        assert c["conditional_type"] == "HYPOTHETICAL"

    def test_unless_negative_conditional(self):
        assert CONJUNCTION_ENCODINGS["unless"]["conditional_type"] == "NEGATIVE"

    def test_that_complement_declarative(self):
        c = CONJUNCTION_ENCODINGS["that"]
        assert c["complement_type"] == "DECLARATIVE"


# ---------- PREPOSITION_ENCODINGS ----------


class TestPrepositionEncodings:
    def test_in_containment_duration(self):
        p = PREPOSITION_ENCODINGS["in"]
        assert p["spatial_type"] == "CONTAINMENT"
        assert p["temporal_type"] == "DURATION"

    def test_on_surface(self):
        assert PREPOSITION_ENCODINGS["on"]["spatial_type"] == "SURFACE"

    def test_under_below(self):
        assert PREPOSITION_ENCODINGS["under"]["spatial_type"] == "BELOW"

    def test_to_goal(self):
        assert PREPOSITION_ENCODINGS["to"]["spatial_type"] == "GOAL"

    def test_from_source(self):
        assert PREPOSITION_ENCODINGS["from"]["spatial_type"] == "SOURCE"

    def test_through_path(self):
        assert PREPOSITION_ENCODINGS["through"]["spatial_type"] == "PATH"

    def test_without_negative_accompaniment(self):
        p = PREPOSITION_ENCODINGS["without"]
        assert p["relation_type"] == "ACCOMPANIMENT"
        assert p["polarity"] == "NEGATIVE"

    def test_during_duration(self):
        assert PREPOSITION_ENCODINGS["during"]["temporal_type"] == "DURATION"


# ---------- get_determiner_encoding ----------


class TestGetDeterminerEncoding:
    def test_known_word(self):
        assert get_determiner_encoding("the") == {"definiteness": "DEFINITE"}

    def test_case_insensitive(self):
        assert get_determiner_encoding("THE") == {"definiteness": "DEFINITE"}
        assert get_determiner_encoding("The") == {"definiteness": "DEFINITE"}

    def test_unknown_returns_none(self):
        assert get_determiner_encoding("xyzzy") is None

    def test_empty_string_returns_none(self):
        assert get_determiner_encoding("") is None


# ---------- get_conjunction_encoding ----------


class TestGetConjunctionEncoding:
    def test_known_word(self):
        result = get_conjunction_encoding("and")
        assert result["clause_relation"] == "ADDITIVE"

    def test_case_insensitive(self):
        assert get_conjunction_encoding("AND")["clause_relation"] == "ADDITIVE"

    def test_unknown_returns_none(self):
        assert get_conjunction_encoding("xyzzy") is None

    def test_multi_word_lowercase_lookup(self):
        # "even though" is in encoding with space
        result = get_conjunction_encoding("even though")
        assert result is not None
        assert result["clause_relation"] == "CONCESSIVE"


# ---------- get_preposition_encoding ----------


class TestGetPrepositionEncoding:
    def test_known_word(self):
        result = get_preposition_encoding("in")
        assert result["spatial_type"] == "CONTAINMENT"

    def test_case_insensitive(self):
        assert get_preposition_encoding("UNDER")["spatial_type"] == "BELOW"

    def test_unknown_returns_none(self):
        assert get_preposition_encoding("xyzzy") is None

    def test_multi_word(self):
        # "away from" is multi-word preposition
        result = get_preposition_encoding("away from")
        assert result is not None
        assert result["spatial_type"] == "DIRECTION_OPPOSITE"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
