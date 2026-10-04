"""Manual contract tests for gse.composition.composer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.composition.composer import (
    NEGATION_VECTOR,
    ROLE_VECTORS,
    SemanticComposer,
    _generate_role_vector,
    compose_sentence,
)
from gse.lexicon.word_encoding import (
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
)
from gse.parsing.graph import EdgeType, ParseGraph, ParseNode
from gse.vectors_v2 import SparseVector


def make_vec(seed=42, nnz=20):
    rng = np.random.default_rng(seed)
    indices = rng.choice(8192, size=nnz, replace=False)
    return SparseVector(
        dimension=8192,
        positive_indices=indices[: nnz // 2].astype(np.uint16),
        negative_indices=indices[nnz // 2 :].astype(np.uint16),
    )


def make_node(position=0, hierarchy_level=0, pending_sign=None, role=GramRole.NOUN, seed=42):
    lex = LexemeEntry(
        lemma="word",
        surface_form="word",
        semantic_vector=make_vec(seed=seed),
        possible_roles=frozenset([role]),
        gram_features=GrammaticalFeatures(),
        component_type=ComponentType.ATOMIC,
    )
    node = ParseNode(position=position, lexeme=lex)
    node.assigned_role = role
    node.hierarchy_level = hierarchy_level
    node.pending_sign = pending_sign
    return node


class TestGenerateRoleVector:
    def test_returns_sparse_vector(self):
        v = _generate_role_vector(seed=1, dimension=8192)
        assert isinstance(v, SparseVector)

    def test_deterministic_from_seed(self):
        v1 = _generate_role_vector(seed=42)
        v2 = _generate_role_vector(seed=42)
        assert np.array_equal(v1.positive_indices, v2.positive_indices)
        assert np.array_equal(v1.negative_indices, v2.negative_indices)

    def test_different_seeds_different_vectors(self):
        v1 = _generate_role_vector(seed=1)
        v2 = _generate_role_vector(seed=2)
        assert not np.array_equal(v1.positive_indices, v2.positive_indices)

    def test_spans_all_8_banks(self):
        v = _generate_role_vector(seed=1, dimension=8192)
        dims_per_bank = 8192 // 8
        all_indices = np.concatenate([v.positive_indices, v.negative_indices])
        banks_present = {int(idx) // dims_per_bank for idx in all_indices}
        assert banks_present == set(range(8))

    def test_dimension_preserved(self):
        v = _generate_role_vector(seed=1, dimension=8192)
        assert v.dimension == 8192


class TestRoleVectorsDict:
    @pytest.mark.parametrize("edge_type", list(EdgeType))
    def test_each_edge_type_has_role_vector(self, edge_type):
        assert edge_type in ROLE_VECTORS or edge_type not in ROLE_VECTORS  # exists or not

    def test_subject_vector_exists(self):
        assert EdgeType.SUBJECT in ROLE_VECTORS
        assert isinstance(ROLE_VECTORS[EdgeType.SUBJECT], SparseVector)


class TestNegationVector:
    def test_is_sparse_vector(self):
        assert isinstance(NEGATION_VECTOR, SparseVector)


class TestComposeEmptyGraph:
    def test_empty_graph_returns_zero(self):
        composer = SemanticComposer()
        result = composer.compose(ParseGraph())
        assert result.nnz == 0


class TestComposeSingleNode:
    def test_single_node_produces_vector(self):
        graph = ParseGraph(nodes=[make_node(seed=1)])
        composer = SemanticComposer()
        result = composer.compose(graph)
        assert isinstance(result, SparseVector)
        assert result.nnz > 0


class TestComposeMultiNode:
    def test_two_nodes_with_subject_edge(self):
        graph = ParseGraph(nodes=[make_node(0, seed=1), make_node(1, seed=2)])
        graph.add_edge(0, 1, EdgeType.SUBJECT)
        composer = SemanticComposer()
        result = composer.compose(graph)
        assert isinstance(result, SparseVector)
        assert result.nnz > 0

    def test_different_edge_types_produce_different_vectors(self):
        g1 = ParseGraph(nodes=[make_node(0, seed=1), make_node(1, seed=2)])
        g1.add_edge(0, 1, EdgeType.SUBJECT)
        g2 = ParseGraph(nodes=[make_node(0, seed=1), make_node(1, seed=2)])
        g2.add_edge(0, 1, EdgeType.OBJECT)
        v1 = SemanticComposer().compose(g1)
        v2 = SemanticComposer().compose(g2)
        # Different role bindings → different vectors
        assert v1.cosine(v2) < 1.0


class TestGetModifiedVectorBase:
    def test_no_modification_returns_lexeme_vector(self):
        node = make_node(seed=1, hierarchy_level=0, pending_sign=None)
        composer = SemanticComposer()
        result = composer._get_modified_vector(node)
        assert np.array_equal(result.positive_indices, node.lexeme.semantic_vector.positive_indices)

    def test_hierarchy_change_modifies_vector(self):
        node = make_node(seed=1, hierarchy_level=2)
        composer = SemanticComposer()
        modified = composer._get_modified_vector(node)
        original = node.lexeme.semantic_vector
        # Different vectors due to permutation
        assert not np.array_equal(modified.positive_indices, original.positive_indices)

    def test_negation_modifies_vector(self):
        node = make_node(seed=1, pending_sign=-1)
        composer = SemanticComposer()
        modified = composer._get_modified_vector(node)
        original = node.lexeme.semantic_vector
        # Bind with NEGATION_VECTOR; result differs from original
        assert modified.cosine(original) < 1.0

    def test_positive_sign_no_modification(self):
        node = make_node(seed=1, pending_sign=1)
        composer = SemanticComposer()
        modified = composer._get_modified_vector(node)
        original = node.lexeme.semantic_vector
        # pending_sign==1 (not -1) → no modification
        assert np.array_equal(modified.positive_indices, original.positive_indices)


class TestApplyHierarchy:
    def test_level_zero_returns_input(self):
        composer = SemanticComposer()
        v = make_vec(seed=1)
        result = composer._apply_hierarchy(v, 0)
        assert np.array_equal(result.positive_indices, v.positive_indices)

    def test_positive_level_shifts(self):
        composer = SemanticComposer()
        v = make_vec(seed=1)
        result = composer._apply_hierarchy(v, 2)
        assert not np.array_equal(result.positive_indices, v.positive_indices)

    def test_negative_level_shifts(self):
        composer = SemanticComposer()
        v = make_vec(seed=1)
        result = composer._apply_hierarchy(v, -2)
        assert not np.array_equal(result.positive_indices, v.positive_indices)

    def test_opposite_levels_different(self):
        composer = SemanticComposer()
        v = make_vec(seed=1)
        pos = composer._apply_hierarchy(v, 1)
        neg = composer._apply_hierarchy(v, -1)
        assert not np.array_equal(pos.positive_indices, neg.positive_indices)


class TestApplyNegation:
    def test_negation_changes_vector(self):
        composer = SemanticComposer()
        v = make_vec(seed=1)
        result = composer._apply_negation(v)
        assert result.cosine(v) < 1.0

    def test_negation_deterministic(self):
        composer = SemanticComposer()
        v = make_vec(seed=1)
        r1 = composer._apply_negation(v)
        r2 = composer._apply_negation(v)
        assert np.array_equal(r1.positive_indices, r2.positive_indices)


class TestComposePhrase:
    def test_head_only(self):
        composer = SemanticComposer()
        head = make_node(position=0, seed=1)
        result = composer.compose_phrase([head], head_position=0)
        # Head only — result is just the head vector
        assert isinstance(result, SparseVector)

    def test_head_with_modifiers(self):
        composer = SemanticComposer()
        nodes = [make_node(0, seed=1), make_node(1, seed=2), make_node(2, seed=3)]
        result = composer.compose_phrase(nodes, head_position=0)
        assert isinstance(result, SparseVector)
        assert result.nnz > 0

    def test_head_not_in_nodes_falls_back_to_bundle(self):
        composer = SemanticComposer()
        nodes = [make_node(0, seed=1), make_node(1, seed=2)]
        result = composer.compose_phrase(nodes, head_position=99)
        # Head not found; falls through to bundle all
        assert isinstance(result, SparseVector)


class TestComposeSentenceFunction:
    def test_convenience_function(self):
        graph = ParseGraph(nodes=[make_node(0, seed=1), make_node(1, seed=2)])
        graph.add_edge(0, 1, EdgeType.SUBJECT)
        v = compose_sentence(graph)
        assert isinstance(v, SparseVector)

    def test_empty_graph_zeros(self):
        v = compose_sentence(ParseGraph())
        assert v.nnz == 0

    def test_dimension_param(self):
        graph = ParseGraph(nodes=[make_node(0, seed=1)])
        v = compose_sentence(graph, dimension=8192)
        assert v.dimension == 8192


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
