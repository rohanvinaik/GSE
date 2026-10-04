"""Manual contract tests for gse.lexicon.word_encoding.

LintGate classified all 6 functions as manual_contract:
- GrammaticalFeatures.is_empty
- GrammaticalFeatures.to_dict
- LexemeEntry.is_atomic / is_operator / is_hybrid / can_be_role
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.lexicon.word_encoding import (
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
)
from gse.vectors_v2 import SparseVector


def make_vector(nnz: int = 4) -> SparseVector:
    return SparseVector(
        dimension=8192,
        positive_indices=np.array(list(range(nnz)), dtype=np.uint16),
        negative_indices=np.array([], dtype=np.uint16),
    )


def make_lexeme(component_type=ComponentType.ATOMIC, roles=None):
    return LexemeEntry(
        lemma="run",
        surface_form="ran",
        semantic_vector=make_vector(),
        possible_roles=frozenset([GramRole.VERB] if roles is None else roles),
        gram_features=GrammaticalFeatures(),
        component_type=component_type,
    )


# ============================================================
# GrammaticalFeatures.is_empty
# ============================================================

class TestGrammaticalFeaturesIsEmpty:
    def test_all_none_is_empty(self):
        f = GrammaticalFeatures()
        assert f.is_empty()

    @pytest.mark.parametrize("field_name,value", [
        ("tense", "PAST"),
        ("aspect", "PROGRESSIVE"),
        ("mood", "SUBJUNCTIVE"),
        ("voice", "PASSIVE"),
        ("person", 1),
        ("number", "PLURAL"),
        ("gender", "FEM"),
        ("case", "ACC"),
        ("definiteness", "DEFINITE"),
        ("animacy", "ANIMATE"),
        ("reflexivity", "REFLEXIVE"),
        ("deixis", "PROXIMAL"),
        ("polarity", "NEGATIVE"),
    ])
    def test_any_single_field_set_makes_not_empty(self, field_name, value):
        f = GrammaticalFeatures(**{field_name: value})
        assert not f.is_empty(), f"Field {field_name}={value} should make features non-empty"

    def test_multiple_fields_not_empty(self):
        f = GrammaticalFeatures(tense="PAST", person=3, number="SINGULAR")
        assert not f.is_empty()


# ============================================================
# GrammaticalFeatures.to_dict
# ============================================================

class TestGrammaticalFeaturesToDict:
    def test_empty_returns_empty_dict(self):
        f = GrammaticalFeatures()
        assert f.to_dict() == {}

    @pytest.mark.parametrize("field_name,value", [
        ("tense", "PAST"),
        ("aspect", "SIMPLE"),
        ("mood", "INDICATIVE"),
        ("voice", "ACTIVE"),
        ("person", 3),
        ("number", "SINGULAR"),
        ("gender", "MASC"),
        ("case", "NOM"),
        ("definiteness", "INDEFINITE"),
        ("animacy", "INANIMATE"),
        ("reflexivity", "NONE"),
        ("deixis", "DISTAL"),
        ("polarity", "POSITIVE"),
    ])
    def test_single_field_appears_in_dict(self, field_name, value):
        f = GrammaticalFeatures(**{field_name: value})
        d = f.to_dict()
        assert d == {field_name: value}

    def test_multiple_fields_all_appear(self):
        f = GrammaticalFeatures(tense="PAST", person=3, number="SINGULAR", gender="MASC")
        d = f.to_dict()
        assert d == {
            "tense": "PAST",
            "person": 3,
            "number": "SINGULAR",
            "gender": "MASC",
        }

    def test_none_fields_excluded(self):
        f = GrammaticalFeatures(tense="PAST")
        d = f.to_dict()
        # Only tense should be present; other 12 fields are None and excluded
        assert d == {"tense": "PAST"}
        for k in ["aspect", "mood", "voice", "person", "number", "gender", "case",
                  "definiteness", "animacy", "reflexivity", "deixis", "polarity"]:
            assert k not in d


# ============================================================
# LexemeEntry.is_atomic
# ============================================================

class TestLexemeEntryIsAtomic:
    def test_atomic_returns_true(self):
        lex = make_lexeme(component_type=ComponentType.ATOMIC)
        assert lex.is_atomic()

    def test_operator_returns_false(self):
        lex = make_lexeme(component_type=ComponentType.OPERATOR)
        assert not lex.is_atomic()

    def test_hybrid_returns_false(self):
        lex = make_lexeme(component_type=ComponentType.HYBRID)
        assert not lex.is_atomic()


class TestLexemeEntryIsOperator:
    def test_operator_returns_true(self):
        lex = make_lexeme(component_type=ComponentType.OPERATOR)
        assert lex.is_operator()

    def test_atomic_returns_false(self):
        lex = make_lexeme(component_type=ComponentType.ATOMIC)
        assert not lex.is_operator()

    def test_hybrid_returns_false(self):
        lex = make_lexeme(component_type=ComponentType.HYBRID)
        assert not lex.is_operator()


class TestLexemeEntryIsHybrid:
    def test_hybrid_returns_true(self):
        lex = make_lexeme(component_type=ComponentType.HYBRID)
        assert lex.is_hybrid()

    def test_atomic_returns_false(self):
        lex = make_lexeme(component_type=ComponentType.ATOMIC)
        assert not lex.is_hybrid()

    def test_operator_returns_false(self):
        lex = make_lexeme(component_type=ComponentType.OPERATOR)
        assert not lex.is_hybrid()


# ============================================================
# LexemeEntry.can_be_role
# ============================================================

class TestLexemeEntryCanBeRole:
    def test_in_roles_returns_true(self):
        lex = make_lexeme(roles=[GramRole.VERB])
        assert lex.can_be_role(GramRole.VERB)

    def test_not_in_roles_returns_false(self):
        lex = make_lexeme(roles=[GramRole.VERB])
        assert not lex.can_be_role(GramRole.NOUN)

    def test_multiple_roles_any_membership_true(self):
        lex = make_lexeme(roles=[GramRole.NOUN, GramRole.ADJ])
        assert lex.can_be_role(GramRole.NOUN)
        assert lex.can_be_role(GramRole.ADJ)
        assert not lex.can_be_role(GramRole.VERB)

    def test_empty_roles_always_false(self):
        lex = make_lexeme(roles=[])
        # frozenset() in possible_roles, any role check should be False
        for r in GramRole:
            assert not lex.can_be_role(r)

    @pytest.mark.parametrize("role", list(GramRole))
    def test_each_role_membership_exact(self, role):
        """For each role, lexeme with only that role can_be_role(role) is True,
        all other roles are False."""
        lex = make_lexeme(roles=[role])
        assert lex.can_be_role(role)
        for other in GramRole:
            if other != role:
                assert not lex.can_be_role(other)


# ============================================================
# Integration consistency (one of three predicates is true)
# ============================================================

class TestComponentTypeMutualExclusion:
    @pytest.mark.parametrize("ct", [ComponentType.ATOMIC, ComponentType.OPERATOR, ComponentType.HYBRID])
    def test_exactly_one_predicate_true(self, ct):
        lex = make_lexeme(component_type=ct)
        results = [lex.is_atomic(), lex.is_operator(), lex.is_hybrid()]
        assert sum(results) == 1, f"Expected exactly one True, got {results} for {ct}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
