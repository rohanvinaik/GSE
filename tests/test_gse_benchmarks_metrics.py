"""Manual contract tests for gse.benchmarks.metrics."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.benchmarks.metrics import (
    CorrelationResult,
    DiscriminationMetrics,
    antonym_detection_rate,
    antonym_metrics,
    antonym_synonym_auc,
    bootstrap_confidence_interval,
    correlation_with_ci,
    discrimination_metrics,
    pearson_correlation,
    per_pos_correlation,
    significance_test,
    spearman_correlation,
)


class TestSpearmanCorrelation:
    def test_perfect_positive(self):
        rho, p = spearman_correlation([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0, 3.0, 4.0, 5.0])
        assert rho == pytest.approx(1.0)

    def test_perfect_negative(self):
        rho, p = spearman_correlation([1.0, 2.0, 3.0, 4.0, 5.0], [5.0, 4.0, 3.0, 2.0, 1.0])
        assert rho == pytest.approx(-1.0)

    def test_mismatched_length_raises(self):
        with pytest.raises(ValueError, match="same length"):
            spearman_correlation([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_too_few_samples_returns_zero(self):
        rho, p = spearman_correlation([1.0, 2.0], [1.0, 2.0])
        assert rho == 0.0
        assert p == 1.0

    def test_nan_filtered(self):
        # Even with NaN, the non-NaN points form perfect correlation
        rho, p = spearman_correlation([1.0, 2.0, 3.0, float("nan"), 5.0], [1.0, 2.0, 3.0, 4.0, 5.0])
        # Non-NaN: (1,1), (2,2), (3,3), (5,5) → perfect rank correlation
        assert rho == pytest.approx(1.0)

    def test_too_few_after_filter(self):
        # Only 2 non-NaN pairs after filtering
        rho, p = spearman_correlation(
            [1.0, 2.0, float("nan"), float("nan"), float("nan")], [1.0, 2.0, float("nan"), float("nan"), float("nan")]
        )
        assert rho == 0.0


class TestPearsonCorrelation:
    def test_perfect_positive(self):
        r, p = pearson_correlation([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0, 3.0, 4.0, 5.0])
        assert r == pytest.approx(1.0)

    def test_perfect_negative(self):
        r, p = pearson_correlation([1.0, 2.0, 3.0, 4.0, 5.0], [5.0, 4.0, 3.0, 2.0, 1.0])
        assert r == pytest.approx(-1.0)

    def test_mismatched_length_raises(self):
        with pytest.raises(ValueError):
            pearson_correlation([1.0], [1.0, 2.0])

    def test_too_few_samples(self):
        r, p = pearson_correlation([1.0, 2.0], [3.0, 4.0])
        assert r == 0.0
        assert p == 1.0


class TestBootstrapConfidenceInterval:
    def test_returns_tuple(self):
        pred = list(range(20))
        human = list(range(20))
        low, high = bootstrap_confidence_interval(pred, human, n_bootstrap=100, seed=42)
        assert isinstance(low, float)
        assert isinstance(high, float)

    def test_perfect_correlation_narrow_ci(self):
        # Perfect correlation → CI should be tight around 1.0
        pred = list(range(20))
        human = list(range(20))
        low, high = bootstrap_confidence_interval(pred, human, n_bootstrap=100, seed=42)
        assert low <= high
        assert high <= 1.01  # allowing small numerical error

    def test_too_few_samples_returns_approximate(self):
        pred = [1.0, 2.0, 3.0]
        human = [1.0, 2.0, 3.0]
        low, high = bootstrap_confidence_interval(pred, human)
        # Too few samples → returns rho ± 0.1
        assert low < high

    def test_deterministic_with_seed(self):
        pred = list(range(20))
        human = [x + (x % 3) * 0.5 for x in range(20)]
        r1 = bootstrap_confidence_interval(pred, human, n_bootstrap=100, seed=42)
        r2 = bootstrap_confidence_interval(pred, human, n_bootstrap=100, seed=42)
        assert r1 == r2


class TestCorrelationWithCI:
    def test_returns_correlation_result(self):
        pred = [float(x) for x in range(15)]
        human = [float(x) for x in range(15)]
        result = correlation_with_ci(pred, human, n_bootstrap=50)
        assert isinstance(result, CorrelationResult)

    def test_n_pairs_correct(self):
        pred = [float(x) for x in range(15)]
        human = [float(x) for x in range(15)]
        result = correlation_with_ci(pred, human, n_bootstrap=50)
        assert result.n_pairs == 15


class TestAntonymDetectionRate:
    def test_all_negative_returns_one(self):
        assert antonym_detection_rate([-0.5, -0.3, -0.8]) == 1.0

    def test_all_positive_returns_zero(self):
        assert antonym_detection_rate([0.5, 0.3, 0.8]) == 0.0

    def test_mixed_returns_fraction(self):
        result = antonym_detection_rate([-0.5, -0.3, 0.5, 0.7])
        assert result == 0.5

    def test_empty_returns_zero(self):
        assert antonym_detection_rate([]) == 0.0

    def test_zero_not_counted_as_negative(self):
        # < 0 strictly excludes 0
        result = antonym_detection_rate([0.0, -0.1, 0.1])
        assert result == pytest.approx(1 / 3)


class TestAntonymMetrics:
    def test_empty_returns_zeros(self):
        m = antonym_metrics([])
        assert m.negative_rate == 0.0
        assert m.mean_similarity == 0.0
        assert m.std_similarity == 0.0
        assert m.median_similarity == 0.0
        assert m.min_similarity == 0.0
        assert m.max_similarity == 0.0

    def test_populated(self):
        sims = [-0.5, -0.3, -0.8, 0.2]
        m = antonym_metrics(sims)
        assert m.negative_rate == 0.75
        assert m.min_similarity == -0.8
        assert m.max_similarity == 0.2
        assert m.mean_similarity == pytest.approx(np.mean(sims))


class TestAntonymSynonymAUC:
    def test_perfect_discrimination(self):
        # Antonyms always lower than synonyms
        ant = [-0.5, -0.3, -0.8]
        syn = [0.5, 0.3, 0.8]
        auc = antonym_synonym_auc(ant, syn)
        assert auc == pytest.approx(1.0)

    def test_reverse_discrimination(self):
        # Antonyms have higher similarity than synonyms (bad model)
        ant = [0.8, 0.7, 0.9]
        syn = [0.1, 0.2, 0.3]
        auc = antonym_synonym_auc(ant, syn)
        assert auc == pytest.approx(0.0)

    def test_empty_lists_return_half(self):
        assert antonym_synonym_auc([], []) == 0.5
        assert antonym_synonym_auc([0.1], []) == 0.5
        assert antonym_synonym_auc([], [0.1]) == 0.5


class TestDiscriminationMetrics:
    def test_returns_metrics_object(self):
        ant = [-0.5, -0.3, -0.8]
        syn = [0.5, 0.3, 0.8]
        m = discrimination_metrics(ant, syn)
        assert isinstance(m, DiscriminationMetrics)

    def test_empty_returns_default(self):
        m = discrimination_metrics([], [])
        assert m.auc == 0.5
        assert m.accuracy == 0.5
        assert m.separation == 0.0

    def test_perfect_separation_high_auc(self):
        ant = [-0.5, -0.4, -0.6]
        syn = [0.5, 0.4, 0.6]
        m = discrimination_metrics(ant, syn)
        assert m.auc == 1.0
        assert m.separation > 0  # positive Cohen's d

    def test_means_computed(self):
        ant = [-0.5, -0.3]
        syn = [0.5, 0.3]
        m = discrimination_metrics(ant, syn)
        assert m.antonym_mean == pytest.approx(-0.4)
        assert m.synonym_mean == pytest.approx(0.4)


class TestSignificanceTest:
    def test_returns_tuple(self):
        m1 = list(range(20))
        m2 = [x + 0.1 for x in range(20)]
        human = list(range(20))
        t, p = significance_test(m1, m2, human)
        assert isinstance(t, float)
        assert isinstance(p, float)

    def test_identical_models_low_t(self):
        m1 = list(range(20))
        m2 = list(range(20))
        human = list(range(20))
        t, p = significance_test(m1, m2, human)
        # Identical models → t close to 0, p close to 1
        assert abs(t) < 1.0


class TestPerPosCorrelation:
    def test_returns_dict(self):
        pred = [1.0, 2.0, 3.0, 4.0, 5.0]
        human = [1.0, 2.0, 3.0, 4.0, 5.0]
        pos = ["n", "n", "v", "v", "v"]
        result = per_pos_correlation(pred, human, pos)
        assert isinstance(result, dict)

    def test_per_pos_correlation_computed(self):
        pred = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        human = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        pos = ["n", "n", "n", "v", "v", "v"]
        result = per_pos_correlation(pred, human, pos)
        # Both POS groups should have rho == 1.0
        if "n" in result:
            assert result["n"].rho == pytest.approx(1.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
