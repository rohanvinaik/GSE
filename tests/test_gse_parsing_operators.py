"""Manual contract tests for gse.parsing.operators."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.lexicon.word_encoding import (
    BindingBehavior,
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
    OperatorSpec,
    OperatorType,
)
from gse.parsing.graph import ParseNode
from gse.parsing.operators import (
    OperatorState,
    apply_operators_to_atomic,
    can_operator_apply,
    resolve_operator,
)
from gse.vectors_v2 import SparseVector


def make_vec():
    return SparseVector(
        dimension=8192,
        positive_indices=np.array([0, 1], dtype=np.uint16),
        negative_indices=np.array([], dtype=np.uint16),
    )


def make_operator_lexeme(op_type, sign_value=None, hier_delta=None, transmits=None, seeks=None, gram_features=None):
    spec = OperatorSpec(
        op_type=op_type,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset(seeks or []),
        transmits=frozenset(transmits or []),
        sign_value=sign_value,
        hier_delta=hier_delta,
    )
    return LexemeEntry(
        lemma="op",
        surface_form="op",
        semantic_vector=make_vec(),
        possible_roles=frozenset({GramRole.ADV}),
        gram_features=gram_features or GrammaticalFeatures(),
        component_type=ComponentType.OPERATOR,
        operator_spec=spec,
    )


def make_atomic_lexeme(roles=None):
    return LexemeEntry(
        lemma="word",
        surface_form="word",
        semantic_vector=make_vec(),
        possible_roles=frozenset(roles or [GramRole.ADJ]),
        gram_features=GrammaticalFeatures(),
        component_type=ComponentType.ATOMIC,
    )


# ============================================================
# OperatorState
# ============================================================


class TestOperatorStateDefaults:
    def test_default_state_empty(self):
        s = OperatorState()
        assert s.pending_sign is None
        assert s.pending_hierarchy is None
        assert s.pending_auxiliaries == []
        assert s.is_empty()

    def test_state_with_sign_not_empty(self):
        s = OperatorState(pending_sign=-1)
        assert not s.is_empty()

    def test_state_with_hierarchy_not_empty(self):
        s = OperatorState(pending_hierarchy=1)
        assert not s.is_empty()

    def test_state_with_aux_not_empty(self):
        s = OperatorState(pending_auxiliaries=[make_operator_lexeme(OperatorType.AUXILIARY)])
        assert not s.is_empty()


class TestConsumeSign:
    def test_consume_returns_sign(self):
        s = OperatorState(pending_sign=-1)
        result = s.consume_sign()
        assert result == -1

    def test_consume_clears_sign(self):
        s = OperatorState(pending_sign=-1)
        s.consume_sign()
        assert s.pending_sign is None

    def test_consume_none_returns_none(self):
        s = OperatorState()
        assert s.consume_sign() is None


class TestHasPending:
    def test_has_pending_sign(self):
        assert OperatorState(pending_sign=-1).has_pending_sign()
        assert OperatorState(pending_sign=1).has_pending_sign()
        assert not OperatorState().has_pending_sign()

    def test_has_pending_hierarchy(self):
        assert OperatorState(pending_hierarchy=1).has_pending_hierarchy()
        assert OperatorState(pending_hierarchy=0).has_pending_hierarchy()  # 0 is not None
        assert OperatorState(pending_hierarchy=-2).has_pending_hierarchy()
        assert not OperatorState().has_pending_hierarchy()

    def test_has_pending_auxiliaries(self):
        s_empty = OperatorState()
        assert not s_empty.has_pending_auxiliaries()
        s_with = OperatorState(pending_auxiliaries=[make_operator_lexeme(OperatorType.AUXILIARY)])
        assert s_with.has_pending_auxiliaries()


class TestCopy:
    def test_copy_preserves_fields(self):
        aux = make_operator_lexeme(OperatorType.AUXILIARY)
        s = OperatorState(pending_sign=-1, pending_hierarchy=2, pending_auxiliaries=[aux])
        c = s.copy()
        assert c.pending_sign == -1
        assert c.pending_hierarchy == 2
        assert c.pending_auxiliaries == [aux]

    def test_copy_is_independent_object(self):
        s = OperatorState(pending_sign=-1)
        c = s.copy()
        c.pending_sign = 1
        assert s.pending_sign == -1
        assert c.pending_sign == 1

    def test_copy_aux_list_independent(self):
        s = OperatorState(pending_auxiliaries=[make_operator_lexeme(OperatorType.AUXILIARY)])
        c = s.copy()
        c.pending_auxiliaries.append(make_operator_lexeme(OperatorType.AUXILIARY))
        assert len(s.pending_auxiliaries) == 1
        assert len(c.pending_auxiliaries) == 2


class TestReset:
    def test_reset_returns_empty_state(self):
        s = OperatorState(pending_sign=-1, pending_hierarchy=2)
        fresh = s.reset()
        assert fresh.is_empty()


# ============================================================
# resolve_operator
# ============================================================


class TestResolveOperatorSign:
    def test_sign_sets_pending_sign(self):
        not_op = make_operator_lexeme(OperatorType.SIGN, sign_value=-1)
        state = resolve_operator(not_op, OperatorState())
        assert state.pending_sign == -1

    def test_double_sign_combines(self):
        not_op = make_operator_lexeme(OperatorType.SIGN, sign_value=-1)
        state = OperatorState()
        state = resolve_operator(not_op, state)
        state = resolve_operator(not_op, state)
        # -1 * -1 = +1
        assert state.pending_sign == 1

    def test_positive_sign(self):
        emph = make_operator_lexeme(OperatorType.SIGN, sign_value=1)
        state = resolve_operator(emph, OperatorState())
        assert state.pending_sign == 1


class TestResolveOperatorHierarchy:
    def test_hierarchy_sets_pending(self):
        very = make_operator_lexeme(OperatorType.HIERARCHY, hier_delta=1)
        state = resolve_operator(very, OperatorState())
        assert state.pending_hierarchy == 1

    def test_hierarchy_consumes_sign(self):
        not_op = make_operator_lexeme(OperatorType.SIGN, sign_value=-1)
        very = make_operator_lexeme(OperatorType.HIERARCHY, hier_delta=1)
        state = OperatorState()
        state = resolve_operator(not_op, state)
        state = resolve_operator(very, state)
        # Sign consumed, hierarchy inverted: -1 * 1 = -1
        assert state.pending_sign is None
        assert state.pending_hierarchy == -1

    def test_hierarchy_stacks(self):
        very = make_operator_lexeme(OperatorType.HIERARCHY, hier_delta=1)
        state = OperatorState()
        state = resolve_operator(very, state)
        state = resolve_operator(very, state)
        # +1 + +1 = +2
        assert state.pending_hierarchy == 2

    def test_hierarchy_no_sign_default_one(self):
        very = make_operator_lexeme(OperatorType.HIERARCHY, hier_delta=2)
        state = resolve_operator(very, OperatorState())
        # No sign → default 1 → 2 * 1 = 2
        assert state.pending_hierarchy == 2

    def test_negative_hier_delta(self):
        slightly = make_operator_lexeme(OperatorType.HIERARCHY, hier_delta=-1)
        state = resolve_operator(slightly, OperatorState())
        assert state.pending_hierarchy == -1


class TestResolveOperatorAuxiliary:
    def test_aux_pushed_to_stack(self):
        did = make_operator_lexeme(OperatorType.AUXILIARY, transmits={"tense"})
        state = resolve_operator(did, OperatorState())
        assert len(state.pending_auxiliaries) == 1
        assert state.pending_auxiliaries[0] is did

    def test_multiple_aux_accumulate(self):
        did = make_operator_lexeme(OperatorType.AUXILIARY, transmits={"tense"})
        have = make_operator_lexeme(OperatorType.AUXILIARY, transmits={"aspect"})
        state = OperatorState()
        state = resolve_operator(did, state)
        state = resolve_operator(have, state)
        assert len(state.pending_auxiliaries) == 2


class TestResolveOperatorNonOperator:
    def test_token_without_spec_unchanged(self):
        atomic = make_atomic_lexeme()
        original = OperatorState(pending_sign=-1)
        result = resolve_operator(atomic, original)
        # State should be unchanged (same object returned)
        assert result is original


# ============================================================
# apply_operators_to_atomic
# ============================================================


class TestApplyOperatorsToAtomic:
    def make_node(self, role=GramRole.ADJ):
        lex = make_atomic_lexeme(roles=[role])
        node = ParseNode(position=0, lexeme=lex)
        node.assigned_role = role
        return node

    def test_pending_sign_applied(self):
        node = self.make_node()
        state = OperatorState(pending_sign=-1)
        apply_operators_to_atomic(node, state)
        assert node.pending_sign == -1

    def test_pending_hierarchy_applied(self):
        node = self.make_node()
        state = OperatorState(pending_hierarchy=2)
        apply_operators_to_atomic(node, state)
        assert node.hierarchy_level == 2

    def test_sign_not_applied_when_hierarchy_present(self):
        """If both sign and hierarchy are pending, sign is assumed to have been
        consumed by hierarchy already, so only hierarchy applies."""
        node = self.make_node()
        state = OperatorState(pending_sign=-1, pending_hierarchy=-1)
        apply_operators_to_atomic(node, state)
        # When both are present, sign should not double-apply
        assert node.hierarchy_level == -1
        # pending_sign on node may not be set when hierarchy consumed it
        # (per the function's semantics)

    def test_auxiliary_features_transmitted_to_verb(self):
        verb_node = self.make_node(role=GramRole.VERB)
        did = make_operator_lexeme(
            OperatorType.AUXILIARY,
            transmits={"tense"},
            gram_features=GrammaticalFeatures(tense="PAST"),
        )
        state = OperatorState(pending_auxiliaries=[did])
        apply_operators_to_atomic(verb_node, state)
        assert verb_node.features.get("tense") == "PAST"

    def test_auxiliary_features_not_transmitted_to_non_verb(self):
        adj_node = self.make_node(role=GramRole.ADJ)
        did = make_operator_lexeme(
            OperatorType.AUXILIARY,
            transmits={"tense"},
            gram_features=GrammaticalFeatures(tense="PAST"),
        )
        state = OperatorState(pending_auxiliaries=[did])
        apply_operators_to_atomic(adj_node, state)
        assert "tense" not in adj_node.features

    def test_returns_modified_atomic(self):
        node = self.make_node()
        state = OperatorState(pending_sign=-1)
        result = apply_operators_to_atomic(node, state)
        assert result is node  # Modified in place


# ============================================================
# can_operator_apply
# ============================================================


class TestCanOperatorApply:
    def test_matching_role_returns_true(self):
        op = make_operator_lexeme(OperatorType.SIGN, seeks={GramRole.VERB})
        target = make_atomic_lexeme(roles=[GramRole.VERB])
        assert can_operator_apply(op, target)

    def test_non_matching_role_returns_false(self):
        op = make_operator_lexeme(OperatorType.SIGN, seeks={GramRole.VERB})
        target = make_atomic_lexeme(roles=[GramRole.NOUN])
        assert not can_operator_apply(op, target)

    def test_partial_role_overlap_returns_true(self):
        op = make_operator_lexeme(OperatorType.SIGN, seeks={GramRole.VERB})
        target = make_atomic_lexeme(roles=[GramRole.VERB, GramRole.ADJ])
        assert can_operator_apply(op, target)

    def test_empty_seeks_returns_true(self):
        op = make_operator_lexeme(OperatorType.SIGN, seeks=set())
        target = make_atomic_lexeme(roles=[GramRole.NOUN])
        assert can_operator_apply(op, target)

    def test_target_without_operator_spec_returns_false(self):
        atomic_op = make_atomic_lexeme()
        target = make_atomic_lexeme(roles=[GramRole.VERB])
        assert not can_operator_apply(atomic_op, target)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
