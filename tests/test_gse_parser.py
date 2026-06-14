"""Manual contract tests for gse.parser (top-level spacy-based parser).

Tests cover the spacy-independent parts: dataclasses, dependency-graph
traversal, and the role-extraction logic. The Parser.parse method is
spacy-dependent and not directly tested in the LintGate analysis venv.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.parser import (
    DEP_TO_ROLE,
    POS,
    ParsedSentence,
    Parser,
    SemanticRole,
    Token,
)


def make_token(idx, surface=None, lemma=None, pos=POS.NOUN, dep="nsubj",
               head_idx=None, is_root=False):
    return Token(
        surface=surface or f"w{idx}",
        lemma=lemma or f"w{idx}",
        pos=pos,
        dep=dep,
        head_idx=head_idx if head_idx is not None else idx,
        idx=idx,
        is_root=is_root,
    )


class TestPOSEnum:
    def test_known_pos_values(self):
        assert POS.NOUN.value == "NOUN"
        assert POS.VERB.value == "VERB"
        assert POS.OTHER.value == "OTHER"

    def test_pos_count_at_least_thirteen(self):
        assert len(POS) >= 13


class TestTokenDataclass:
    def test_init_all_fields(self):
        t = Token(surface="dogs", lemma="dog", pos=POS.NOUN, dep="nsubj",
                  head_idx=2, idx=0, is_root=False)
        assert t.surface == "dogs"
        assert t.lemma == "dog"
        assert t.pos == POS.NOUN
        assert t.dep == "nsubj"
        assert t.head_idx == 2
        assert t.idx == 0
        assert t.is_root is False

    def test_root_token(self):
        t = Token(surface="ran", lemma="run", pos=POS.VERB, dep="ROOT",
                  head_idx=0, idx=0, is_root=True)
        assert t.is_root


class TestSemanticRoleDataclass:
    def test_init_all_fields(self):
        r = SemanticRole(role="agent", token_idx=0, confidence=0.9)
        assert r.role == "agent"
        assert r.token_idx == 0
        assert r.confidence == 0.9


class TestParsedSentenceGetDependents:
    def test_returns_tokens_with_matching_head(self):
        # Sentence: tokens 0, 1, 2 all depend on 1 (root)
        tokens = [
            make_token(0, head_idx=1),
            make_token(1, head_idx=1, is_root=True),
            make_token(2, head_idx=1),
        ]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=1)
        deps = ps.get_dependents(1)
        # Should return tokens 0 and 2 (NOT the self-reference at 1)
        idxs = {t.idx for t in deps}
        assert idxs == {0, 2}

    def test_root_self_reference_excluded(self):
        tokens = [make_token(0, head_idx=0, is_root=True)]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=0)
        assert ps.get_dependents(0) == []

    def test_no_dependents_returns_empty(self):
        # Two tokens: 0 is root, 1 depends on 0. Token 1 has no dependents itself.
        tokens = [
            make_token(0, head_idx=0, is_root=True),
            make_token(1, head_idx=0),
        ]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=0)
        assert ps.get_dependents(1) == []


class TestParsedSentenceBottomUpOrder:
    def test_single_token_returns_single_idx(self):
        tokens = [make_token(0, head_idx=0, is_root=True)]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=0)
        order = ps.bottom_up_order()
        assert order == [0]

    def test_post_order_children_first(self):
        # Tree: 0 (root), 1 depends on 0, 2 depends on 0
        # bottom_up_order should visit 1, 2 before 0
        tokens = [
            make_token(0, head_idx=0, is_root=True),
            make_token(1, head_idx=0),
            make_token(2, head_idx=0),
        ]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=0)
        order = ps.bottom_up_order()
        # Root should be last
        assert order[-1] == 0
        # Children come first
        assert set(order[:2]) == {1, 2}

    def test_deep_tree_correct_order(self):
        # Tree: 0 → 1 → 2 (0 is root, 1 depends on 0, 2 depends on 1)
        tokens = [
            make_token(0, head_idx=0, is_root=True),
            make_token(1, head_idx=0),
            make_token(2, head_idx=1),
        ]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=0)
        order = ps.bottom_up_order()
        # 2 must come before 1 (its parent), 1 before 0
        idx_2 = order.index(2)
        idx_1 = order.index(1)
        idx_0 = order.index(0)
        assert idx_2 < idx_1 < idx_0

    def test_empty_tokens(self):
        ps = ParsedSentence(text="", tokens=[], roles=[], root_idx=0)
        assert ps.bottom_up_order() == []

    def test_all_tokens_visited(self):
        tokens = [
            make_token(0, head_idx=0, is_root=True),
            make_token(1, head_idx=0),
            make_token(2, head_idx=1),
            make_token(3, head_idx=0),
        ]
        ps = ParsedSentence(text="x", tokens=tokens, roles=[], root_idx=0)
        order = ps.bottom_up_order()
        assert set(order) == {0, 1, 2, 3}


class TestDepToRoleMap:
    def test_nsubj_is_agent(self):
        assert DEP_TO_ROLE["nsubj"] == "agent"

    def test_nsubjpass_is_patient(self):
        assert DEP_TO_ROLE["nsubjpass"] == "patient"

    def test_dobj_is_patient(self):
        assert DEP_TO_ROLE["dobj"] == "patient"

    def test_obj_is_patient(self):
        assert DEP_TO_ROLE["obj"] == "patient"

    def test_iobj_is_recipient(self):
        assert DEP_TO_ROLE["iobj"] == "recipient"

    def test_amod_is_attribute(self):
        assert DEP_TO_ROLE["amod"] == "attribute"

    def test_advmod_is_manner(self):
        assert DEP_TO_ROLE["advmod"] == "manner"

    def test_aux_is_auxiliary(self):
        assert DEP_TO_ROLE["aux"] == "auxiliary"

    def test_unknown_dep_not_in_map(self):
        assert "xyzzy" not in DEP_TO_ROLE


class TestExtractRoles:
    def _make_parser(self):
        # Construct a Parser without invoking __init__ (avoids spacy load)
        p = Parser.__new__(Parser)
        return p

    def test_nsubj_extracts_agent(self):
        parser = self._make_parser()
        tokens = [make_token(0, dep="nsubj", head_idx=1)]
        roles = parser._extract_roles(tokens, root_idx=1)
        assert len(roles) == 1
        assert roles[0].role == "agent"
        assert roles[0].token_idx == 0
        assert roles[0].confidence == 0.9

    def test_nsubjpass_extracts_patient(self):
        parser = self._make_parser()
        tokens = [make_token(0, dep="nsubjpass", head_idx=1)]
        roles = parser._extract_roles(tokens, root_idx=1)
        assert roles[0].role == "patient"

    def test_unknown_dep_no_role(self):
        parser = self._make_parser()
        tokens = [make_token(0, dep="xyzzy", head_idx=1)]
        roles = parser._extract_roles(tokens, root_idx=1)
        assert roles == []

    @pytest.mark.parametrize("prep,expected_role", [
        ("for", "beneficiary"),
        ("to", "beneficiary"),
        ("with", "instrument"),
        ("in", "location"),
        ("at", "location"),
        ("on", "location"),
        ("from", "source"),
        ("by", "agent"),
    ])
    def test_pobj_with_preposition_lemma(self, prep, expected_role):
        parser = self._make_parser()
        tokens = [
            make_token(0, dep="prep", lemma=prep, head_idx=1),  # the prep itself
            make_token(1, dep="pobj", head_idx=0),              # the obj points back to prep
        ]
        roles = parser._extract_roles(tokens, root_idx=1)
        # Find role for token 1 (the pobj)
        pobj_role = next(r for r in roles if r.token_idx == 1)
        assert pobj_role.role == expected_role

    def test_pobj_with_unknown_preposition_keeps_default(self):
        parser = self._make_parser()
        tokens = [
            make_token(0, dep="prep", lemma="zxyzzy", head_idx=1),
            make_token(1, dep="pobj", head_idx=0),
        ]
        roles = parser._extract_roles(tokens, root_idx=1)
        pobj_role = next(r for r in roles if r.token_idx == 1)
        # No special handling → default "prep_object"
        assert pobj_role.role == "prep_object"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
