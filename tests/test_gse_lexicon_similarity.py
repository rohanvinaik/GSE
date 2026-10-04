"""Manual contract tests for gse.lexicon.similarity."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.lexicon.similarity import (
    bank_masked_similarity,
    full_similarity,
    polarity_analysis,
    semantic_similarity,
    without_banks,
)
from gse.vectors_v2 import SparseVector


def make_vec(positive=(), negative=(), dimension=8192):
    return SparseVector(
        dimension=dimension,
        positive_indices=np.array(positive, dtype=np.uint16),
        negative_indices=np.array(negative, dtype=np.uint16),
    )


# ============================================================
# semantic_similarity / full_similarity
# ============================================================


class TestSemanticSimilarity:
    def test_identical_vectors_cosine_one(self):
        v = make_vec(positive=[1, 2, 3])
        assert abs(semantic_similarity(v, v) - 1.0) < 1e-6

    def test_negated_vector_cosine_minus_one(self):
        v1 = make_vec(positive=[1, 2, 3])
        v2 = make_vec(negative=[1, 2, 3])
        assert abs(semantic_similarity(v1, v2) - (-1.0)) < 1e-6

    def test_disjoint_vectors_cosine_zero(self):
        v1 = make_vec(positive=[1, 2, 3])
        v2 = make_vec(positive=[100, 101, 102])
        assert abs(semantic_similarity(v1, v2)) < 1e-6

    def test_returns_float(self):
        v = make_vec(positive=[1])
        result = semantic_similarity(v, v)
        assert isinstance(result, float)


class TestFullSimilarity:
    """At word level, full_similarity is identical to semantic_similarity."""

    def test_identical_to_semantic_for_word_vecs(self):
        v1 = make_vec(positive=[1, 5, 10], negative=[20, 30])
        v2 = make_vec(positive=[1, 5, 11], negative=[20, 31])
        assert full_similarity(v1, v2) == semantic_similarity(v1, v2)

    def test_identical_vectors_cosine_one(self):
        v = make_vec(positive=[1, 2, 3])
        assert abs(full_similarity(v, v) - 1.0) < 1e-6


# ============================================================
# without_banks
# ============================================================


class TestWithoutBanks:
    def test_excluded_bank_removed(self):
        # Bank 0: dims 0-1023, Bank 1: dims 1024-2047
        v = make_vec(positive=[0, 5, 1024, 1500], negative=[10, 1100])
        result = without_banks(v, exclude_banks={0}, dims_per_bank=1024)
        # Bank 0 dims (0, 5, 10) should be excluded
        assert 0 not in result.positive_indices
        assert 5 not in result.positive_indices
        assert 10 not in result.negative_indices
        # Bank 1 dims (1024, 1500, 1100) should remain
        assert 1024 in result.positive_indices
        assert 1500 in result.positive_indices
        assert 1100 in result.negative_indices

    def test_excluded_multiple_banks(self):
        v = make_vec(positive=[0, 1024, 2048, 3072])  # banks 0, 1, 2, 3
        result = without_banks(v, exclude_banks={0, 2}, dims_per_bank=1024)
        assert 0 not in result.positive_indices
        assert 2048 not in result.positive_indices
        assert 1024 in result.positive_indices
        assert 3072 in result.positive_indices

    def test_empty_exclude_returns_same_indices(self):
        v = make_vec(positive=[1, 100, 1024], negative=[50, 1500])
        result = without_banks(v, exclude_banks=set(), dims_per_bank=1024)
        assert set(result.positive_indices) == {1, 100, 1024}
        assert set(result.negative_indices) == {50, 1500}

    def test_exclude_all_banks_empty_result(self):
        v = make_vec(positive=[0, 1024])
        result = without_banks(v, exclude_banks={0, 1}, dims_per_bank=1024)
        assert len(result.positive_indices) == 0
        assert len(result.negative_indices) == 0

    def test_dimension_preserved(self):
        v = make_vec(positive=[0], dimension=8192)
        result = without_banks(v, exclude_banks={0}, dims_per_bank=1024)
        assert result.dimension == 8192

    def test_bank_attr_cleared_when_excluded(self):
        v = SparseVector(
            dimension=8192,
            positive_indices=np.array([0], dtype=np.uint16),
            negative_indices=np.array([], dtype=np.uint16),
            bank=0,
        )
        result = without_banks(v, exclude_banks={0}, dims_per_bank=1024)
        assert result.bank is None

    def test_bank_attr_preserved_when_not_excluded(self):
        v = SparseVector(
            dimension=8192,
            positive_indices=np.array([1024], dtype=np.uint16),
            negative_indices=np.array([], dtype=np.uint16),
            bank=1,
        )
        result = without_banks(v, exclude_banks={0}, dims_per_bank=1024)
        assert result.bank == 1


# ============================================================
# bank_masked_similarity
# ============================================================


class TestBankMaskedSimilarity:
    def test_excluding_irrelevant_bank_preserves_similarity(self):
        # v1 and v2 differ only in bank 0; if we exclude bank 0, they're identical
        v1 = make_vec(positive=[0, 1024, 2048])
        v2 = make_vec(positive=[100, 1024, 2048])
        result = bank_masked_similarity(v1, v2, exclude_banks={0}, dims_per_bank=1024)
        assert abs(result - 1.0) < 1e-6

    def test_excluding_no_banks_equals_full_similarity(self):
        v1 = make_vec(positive=[1, 100, 1024])
        v2 = make_vec(positive=[1, 100, 1024])
        masked = bank_masked_similarity(v1, v2, exclude_banks=set(), dims_per_bank=1024)
        full = semantic_similarity(v1, v2)
        assert abs(masked - full) < 1e-6

    def test_identical_vectors_remain_identical(self):
        v = make_vec(positive=[0, 100, 2048])
        assert abs(bank_masked_similarity(v, v, exclude_banks={1}, dims_per_bank=1024) - 1.0) < 1e-6

    def test_negation_preserved_after_mask(self):
        v1 = make_vec(positive=[1024, 2048])
        v2 = make_vec(negative=[1024, 2048])
        result = bank_masked_similarity(v1, v2, exclude_banks={0}, dims_per_bank=1024)
        # Excluding bank 0 doesn't change banks 1, 2 — should still be -1
        assert abs(result - (-1.0)) < 1e-6


# ============================================================
# polarity_analysis
# ============================================================


class TestPolarityAnalysis:
    def test_empty_vectors_returns_orthogonality_one(self):
        v1 = make_vec()
        v2 = make_vec()
        result = polarity_analysis(v1, v2)
        assert result["cosine"] == 0.0
        assert result["alignment"] == 0.0
        assert result["opposition"] == 0.0
        assert result["orthogonality"] == 1.0

    def test_identical_vectors_alignment_one(self):
        v = make_vec(positive=[1, 2, 3])
        result = polarity_analysis(v, v)
        assert abs(result["cosine"] - 1.0) < 1e-6
        assert abs(result["alignment"] - 1.0) < 1e-6
        assert result["opposition"] == 0.0

    def test_negated_vectors_opposition_one(self):
        v1 = make_vec(positive=[1, 2, 3])
        v2 = make_vec(negative=[1, 2, 3])
        result = polarity_analysis(v1, v2)
        assert abs(result["cosine"] - (-1.0)) < 1e-6
        assert result["alignment"] == 0.0
        assert abs(result["opposition"] - 1.0) < 1e-6

    def test_disjoint_vectors_orthogonality_one(self):
        v1 = make_vec(positive=[1, 2, 3])
        v2 = make_vec(positive=[100, 200, 300])
        result = polarity_analysis(v1, v2)
        assert result["orthogonality"] == 1.0
        assert result["alignment"] == 0.0
        assert result["opposition"] == 0.0

    def test_partial_overlap(self):
        v1 = make_vec(positive=[1, 2, 3])
        v2 = make_vec(positive=[2, 3, 4])
        # overlap={2,3}, union={1,2,3,4}, both positive → alignment = 2/4 = 0.5
        result = polarity_analysis(v1, v2)
        assert result["alignment"] == pytest.approx(0.5)
        assert result["opposition"] == 0.0
        assert result["orthogonality"] == pytest.approx(0.5)

    def test_partial_opposition(self):
        v1 = make_vec(positive=[1, 2, 3])
        v2 = make_vec(positive=[1], negative=[2, 3])
        # overlap={1,2,3}, union={1,2,3}, 1 same-sign, 2 opposite
        result = polarity_analysis(v1, v2)
        assert result["alignment"] == pytest.approx(1 / 3)
        assert result["opposition"] == pytest.approx(2 / 3)
        assert result["orthogonality"] == pytest.approx(0.0)

    def test_returns_dict_with_required_keys(self):
        v1 = make_vec(positive=[1])
        v2 = make_vec(positive=[1])
        result = polarity_analysis(v1, v2)
        assert set(result.keys()) == {"cosine", "alignment", "opposition", "orthogonality"}

    def test_empty_vectors_exact_zero_alignment(self):
        """Catches VALUE mutation on the empty-union 'alignment: 0.0'."""
        result = polarity_analysis(make_vec(), make_vec())
        assert result["alignment"] == 0.0

    def test_empty_vectors_exact_zero_opposition(self):
        """Catches VALUE mutation on the empty-union 'opposition: 0.0'."""
        result = polarity_analysis(make_vec(), make_vec())
        assert result["opposition"] == 0.0

    def test_empty_vectors_exact_zero_cosine(self):
        """Catches VALUE mutation on the empty-union 'cosine: 0.0'."""
        result = polarity_analysis(make_vec(), make_vec())
        assert result["cosine"] == 0.0

    def test_empty_vectors_exact_one_orthogonality(self):
        """Catches VALUE mutation on the empty-union 'orthogonality: 1.0'."""
        result = polarity_analysis(make_vec(), make_vec())
        assert result["orthogonality"] == 1.0

    def test_alignment_opposition_orthogonality_sum_to_one(self):
        """For any non-empty pair, alignment + opposition + orthogonality == 1."""
        for positive_a, positive_b, neg_b in [
            ([1, 2], [1, 2], []),
            ([1, 2, 3], [2, 3], []),
            ([1, 2, 3], [], [1, 2, 3]),
            ([1, 2, 3], [1], [2, 3]),
        ]:
            v1 = make_vec(positive=positive_a)
            v2 = make_vec(positive=positive_b, negative=neg_b)
            result = polarity_analysis(v1, v2)
            total = result["alignment"] + result["opposition"] + result["orthogonality"]
            assert abs(total - 1.0) < 1e-9, f"Sum should be 1.0, got {total}"

    def test_orthogonality_formula_exact(self):
        """orthogonality = 1 - overlap/union. Test exact value to catch the '1' constant."""
        v1 = make_vec(positive=[1, 2])
        v2 = make_vec(positive=[2, 3])
        # overlap={2}, union={1,2,3}, orthogonality = 1 - 1/3 = 2/3
        result = polarity_analysis(v1, v2)
        assert result["orthogonality"] == pytest.approx(2 / 3)

    def test_alignment_fraction_exact(self):
        """alignment is same_sign/union. Test exact fraction."""
        v1 = make_vec(positive=[1, 2, 3, 4])
        v2 = make_vec(positive=[1, 2, 3, 4])
        # all overlap, all same sign → alignment = 4/4 = 1
        result = polarity_analysis(v1, v2)
        assert result["alignment"] == 1.0

    def test_opposition_fraction_exact(self):
        """opposition is opposite_sign/union."""
        v1 = make_vec(positive=[1, 2, 3, 4])
        v2 = make_vec(negative=[1, 2, 3, 4])
        # all overlap, all opposite sign → opposition = 4/4 = 1
        result = polarity_analysis(v1, v2)
        assert result["opposition"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
