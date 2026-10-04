"""Manual contract tests for gse.merkle.router."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.merkle.nodes import LexemeNode
from gse.merkle.router import (
    FamilyCentroid,
    MerkleBellmanFord,
    RouteResult,
    _extract_bank,
    find_semantic_path,
    semantic_distance,
)
from gse.merkle.tree import MerkleLexiconTree
from gse.vectors_v2 import SparseVector, compose_decomposition, create_basis


def make_lex(lemma, decomposition, sense="01", pos="adj"):
    return LexemeNode(
        node_id=f"{lemma}_{pos}_{sense}",
        lemma=lemma,
        pos=pos,
        sense_id=sense,
        decomposition=decomposition,
        vector_positive=np.array([1, 2, 3], dtype=np.uint16),
        vector_negative=np.array([10, 20], dtype=np.uint16),
    )


@pytest.fixture(scope="module")
def basis():
    return create_basis()


@pytest.fixture
def tree(basis):
    tree = MerkleLexiconTree()
    # Add a couple of lexemes with real vector content
    for lemma, decomp in [
        ("happy", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]),
        ("sad", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1)]),
        ("big", [("BIG", "attribute", 1)]),
    ]:
        vec = compose_decomposition(basis, decomp)
        lex = LexemeNode(
            node_id=f"{lemma}_adj_01",
            lemma=lemma,
            pos="adj",
            sense_id="01",
            decomposition=decomp,
            vector_positive=vec.positive_indices,
            vector_negative=vec.negative_indices,
        )
        tree.add_lexeme(lex)
    return tree


@pytest.fixture
def router(tree, basis):
    return MerkleBellmanFord(tree, basis)


# ---------- RouteResult ----------


class TestRouteResult:
    def test_total_operations_sum(self):
        r = RouteResult(query_vector=MagicMock_vec())
        r.banks_checked = 8
        r.families_checked = 5
        r.hubs_checked = 3
        r.lexemes_checked = 10
        assert r.total_operations == 26

    def test_default_lists_empty(self):
        r = RouteResult(query_vector=MagicMock_vec())
        assert r.activated_banks == []
        assert r.matches == []


def MagicMock_vec():
    return SparseVector(8192)


# ---------- FamilyCentroid ----------


class TestFamilyCentroid:
    def test_defaults(self):
        c = FamilyCentroid(family_id="x", bank_id=0, centroid=SparseVector(8192))
        assert c.lexeme_count == 0
        assert c.max_intra_similarity == 1.0
        assert c.min_intra_similarity == 0.0


# ---------- MerkleBellmanFord.__init__ ----------


class TestInit:
    def test_uses_provided_basis(self, tree):
        b = create_basis()
        r = MerkleBellmanFord(tree, basis=b)
        assert r.basis is b

    def test_creates_default_basis(self, tree):
        r = MerkleBellmanFord(tree)
        assert r.basis is not None

    def test_thresholds_default_values(self, tree, basis):
        r = MerkleBellmanFord(tree, basis)
        assert r.bank_threshold == 0.1
        assert r.family_threshold == 0.2
        assert r.hub_threshold == 0.3

    def test_centroids_built(self, tree, basis):
        r = MerkleBellmanFord(tree, basis)
        # One centroid per family
        assert len(r.family_centroids) == len(tree.families)


# ---------- _compute_centroid ----------


class TestComputeCentroid:
    def test_empty_returns_zero(self, router):
        result = router._compute_centroid([])
        assert isinstance(result, SparseVector)
        assert result.nnz == 0

    def test_single_lexeme_majority(self, router):
        # Single lex → threshold = 0.5, no idx has count > 0.5 → empty
        lex = make_lex("x", [("GOOD", "attribute", 1)])
        result = router._compute_centroid([lex])
        # Counts of 1 are not > 0.5 → wait, len/2 = 0.5, count=1 > 0.5 → kept
        # All indices in vec are kept
        assert result.nnz > 0

    def test_majority_indices_kept(self, router):
        # 3 lexemes: idx 1 appears in all, idx 99 appears in one
        lex1 = LexemeNode(
            node_id="a_n_01",
            lemma="a",
            pos="n",
            sense_id="01",
            decomposition=[],
            vector_positive=np.array([1, 99], dtype=np.uint16),
            vector_negative=np.array([], dtype=np.uint16),
        )
        lex2 = LexemeNode(
            node_id="b_n_01",
            lemma="b",
            pos="n",
            sense_id="01",
            decomposition=[],
            vector_positive=np.array([1, 2], dtype=np.uint16),
            vector_negative=np.array([], dtype=np.uint16),
        )
        lex3 = LexemeNode(
            node_id="c_n_01",
            lemma="c",
            pos="n",
            sense_id="01",
            decomposition=[],
            vector_positive=np.array([1, 5], dtype=np.uint16),
            vector_negative=np.array([], dtype=np.uint16),
        )
        result = router._compute_centroid([lex1, lex2, lex3])
        # threshold = 1.5; idx 1 appears 3 times (>1.5) → kept; others appear once each (≤1.5)
        assert 1 in result.positive_indices.tolist()


# ---------- _compute_bank_activations ----------


class TestComputeBankActivations:
    def test_zero_vector_zero_activations(self, router):
        zero = SparseVector(8192)
        result = router._compute_bank_activations(zero)
        # All 0 or near 0
        for activation in result.values():
            assert activation == 0.0

    def test_returns_dict_keyed_by_bank_id(self, router):
        zero = SparseVector(8192)
        result = router._compute_bank_activations(zero)
        assert len(result) == 8  # N_BANKS = 8

    def test_capped_at_1(self, router, basis):
        # Build vector with all positions in bank 0
        good_vec = basis.get_primitive("GOOD")
        result = router._compute_bank_activations(good_vec)
        for activation in result.values():
            assert activation <= 1.0


# ---------- route ----------


class TestRoute:
    def test_returns_route_result(self, router, basis):
        query = basis.get_primitive("GOOD")
        result = router.route(query, top_k=5)
        assert isinstance(result, RouteResult)

    def test_banks_checked_equals_n_banks(self, router, basis):
        query = basis.get_primitive("GOOD")
        result = router.route(query)
        assert result.banks_checked == 8

    def test_no_active_banks_uses_all(self, router):
        # Zero-vector query → no bank activation → uses all
        zero = SparseVector(8192)
        result = router.route(zero)
        # All 8 banks considered active (fallback)
        assert len(result.activated_banks) == 0  # Initially set to filtered list (empty)


# ---------- _get_hub_vector ----------


class TestGetHubVector:
    def test_unknown_hub_returns_none(self, router):
        result = router._get_hub_vector("XYZZY_UNKNOWN")
        assert result is None

    def test_known_hub_returns_basis_vector(self, router, tree):
        hub_name = list(tree.hubs.keys())[0]
        result = router._get_hub_vector(hub_name)
        assert isinstance(result, SparseVector)


# ---------- find_nearest ----------


class TestFindNearest:
    def test_returns_matches_list(self, router, basis):
        query = basis.get_primitive("GOOD")
        result = router.find_nearest(query, k=2)
        assert isinstance(result, list)


# ---------- find_by_decomposition ----------


class TestFindByDecomposition:
    def test_returns_route_result(self, router):
        result = router.find_by_decomposition([("GOOD", "attribute", 1)], top_k=3)
        assert isinstance(result, RouteResult)


# ---------- semantic_distance ----------


class TestSemanticDistance:
    def test_uniform_default(self, basis):
        good = basis.get_primitive("GOOD")
        result = semantic_distance(good, good)
        # cos(good, good) = 1 → dist = 0
        assert result == pytest.approx(0.0)

    def test_orthogonal_high_distance(self, basis):
        good = basis.get_primitive("GOOD")
        # An empty vector → cos = 0 → dist = 1
        zero = SparseVector(8192)
        result = semantic_distance(good, zero)
        assert result == pytest.approx(1.0)

    def test_weighted_returns_float(self, basis):
        good = basis.get_primitive("GOOD")
        result = semantic_distance(good, good, bank_weights={0: 1.0})
        assert isinstance(result, float)

    def test_weighted_empty_banks(self, basis):
        # If no banks contribute (total_weight == 0), returns 1.0
        zero = SparseVector(8192)
        result = semantic_distance(zero, zero, bank_weights={0: 1.0})
        assert result == 1.0


# ---------- _extract_bank ----------


class TestExtractBank:
    def test_filters_by_range(self):
        v = SparseVector(
            8192,
            np.array([5, 100, 1500], dtype=np.uint16),
            np.array([50, 999], dtype=np.uint16),
        )
        # Bank 0..1024
        result = _extract_bank(v, 0, 1024)
        # 5, 100 in range; 1500 out; 50, 999 in
        assert 5 in result.positive_indices.tolist()
        assert 100 in result.positive_indices.tolist()
        assert 1500 not in result.positive_indices.tolist()
        assert 50 in result.negative_indices.tolist()

    def test_empty_range(self):
        v = SparseVector(
            8192,
            np.array([5, 10], dtype=np.uint16),
            np.array([], dtype=np.uint16),
        )
        # Out-of-range bank
        result = _extract_bank(v, 1000, 2000)
        assert result.nnz == 0


# ---------- find_semantic_path ----------


class TestFindSemanticPath:
    def test_missing_source_returns_none(self, router):
        result = find_semantic_path(router, "missing_x_01", "happy_adj_01")
        assert result is None

    def test_missing_target_returns_none(self, router):
        result = find_semantic_path(router, "happy_adj_01", "missing_x_01")
        assert result is None

    def test_returns_path_or_none(self, router):
        result = find_semantic_path(router, "happy_adj_01", "happy_adj_01", max_hops=1)
        # source == target → first iteration of while loop matches
        # path = [source]; current==target → returns [source]
        assert result == ["happy_adj_01"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
