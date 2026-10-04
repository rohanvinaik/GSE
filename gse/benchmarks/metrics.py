"""
Benchmark Evaluation Metrics

Statistical metrics for evaluating semantic similarity models:
- Spearman correlation with human judgments
- Bootstrap confidence intervals
- Antonym detection metrics
- ROC-AUC for antonym/synonym discrimination
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from gse.primitives_v2 import DIMS_PER_BANK, SemanticBank

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    rho: float  # Spearman correlation coefficient
    p_value: float  # Statistical significance
    ci_low: float  # 95% CI lower bound
    ci_high: float  # 95% CI upper bound
    n_pairs: int  # Number of pairs evaluated


@dataclass
class AntonymMetrics:
    """Metrics for antonym detection evaluation."""
    negative_rate: float  # Fraction with similarity < 0
    mean_similarity: float  # Mean similarity of antonyms
    std_similarity: float  # Std of similarities
    median_similarity: float
    min_similarity: float
    max_similarity: float


@dataclass
class DiscriminationMetrics:
    """Metrics for antonym/synonym discrimination."""
    auc: float  # Area under ROC curve
    accuracy: float  # Classification accuracy at optimal threshold
    optimal_threshold: float  # Threshold maximizing accuracy
    antonym_mean: float
    synonym_mean: float
    separation: float  # Cohen's d effect size


def spearman_correlation(
    predicted: List[float],
    human: List[float]
) -> Tuple[float, float]:
    """
    Compute Spearman rank correlation between predicted and human scores.

    Args:
        predicted: Model-predicted similarity scores
        human: Human similarity judgments

    Returns:
        Tuple of (rho, p_value)
    """
    if len(predicted) != len(human):
        raise ValueError("predicted and human must have same length")

    if len(predicted) < 3:
        logger.warning("Too few samples for correlation")
        return 0.0, 1.0

    # Filter out NaN values
    mask = ~(np.isnan(predicted) | np.isnan(human))
    pred_clean = np.array(predicted)[mask]
    human_clean = np.array(human)[mask]

    if len(pred_clean) < 3:
        return 0.0, 1.0

    rho, p_value = stats.spearmanr(pred_clean, human_clean)
    return float(rho), float(p_value)


def pearson_correlation(
    predicted: List[float],
    human: List[float]
) -> Tuple[float, float]:
    """
    Compute Pearson correlation coefficient.

    Args:
        predicted: Model-predicted similarity scores
        human: Human similarity judgments

    Returns:
        Tuple of (r, p_value)
    """
    if len(predicted) != len(human):
        raise ValueError("predicted and human must have same length")

    if len(predicted) < 3:
        return 0.0, 1.0

    mask = ~(np.isnan(predicted) | np.isnan(human))
    pred_clean = np.array(predicted)[mask]
    human_clean = np.array(human)[mask]

    if len(pred_clean) < 3:
        return 0.0, 1.0

    r, p_value = stats.pearsonr(pred_clean, human_clean)
    return float(r), float(p_value)


def bootstrap_confidence_interval(
    predicted: List[float],
    human: List[float],
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: Optional[int] = 42
) -> Tuple[float, float]:
    """
    Compute bootstrap confidence interval for Spearman correlation.

    Args:
        predicted: Model-predicted similarity scores
        human: Human similarity judgments
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (default 0.95 for 95% CI)
        seed: Random seed for reproducibility

    Returns:
        Tuple of (ci_low, ci_high)
    """
    rng = np.random.RandomState(seed)
    n = len(predicted)

    if n < 10:
        logger.warning("Too few samples for reliable bootstrap")
        rho, _ = spearman_correlation(predicted, human)
        return rho - 0.1, rho + 0.1

    pred_arr = np.array(predicted)
    human_arr = np.array(human)

    bootstrap_rhos = []
    for _ in range(n_bootstrap):
        # Sample with replacement
        indices = rng.choice(n, size=n, replace=True)
        boot_pred = pred_arr[indices]
        boot_human = human_arr[indices]

        # Compute correlation for this sample
        rho, _ = stats.spearmanr(boot_pred, boot_human)
        if not np.isnan(rho):
            bootstrap_rhos.append(rho)

    if len(bootstrap_rhos) < n_bootstrap * 0.9:
        logger.warning("Many bootstrap samples failed")

    # Compute percentile confidence interval
    alpha = 1 - confidence
    ci_low = np.percentile(bootstrap_rhos, alpha / 2 * 100)
    ci_high = np.percentile(bootstrap_rhos, (1 - alpha / 2) * 100)

    return float(ci_low), float(ci_high)


def correlation_with_ci(
    predicted: List[float],
    human: List[float],
    n_bootstrap: int = 1000
) -> CorrelationResult:
    """
    Compute Spearman correlation with confidence interval.

    Args:
        predicted: Model-predicted similarity scores
        human: Human similarity judgments
        n_bootstrap: Number of bootstrap samples

    Returns:
        CorrelationResult with rho, p_value, and 95% CI
    """
    rho, p_value = spearman_correlation(predicted, human)
    ci_low, ci_high = bootstrap_confidence_interval(predicted, human, n_bootstrap)

    return CorrelationResult(
        rho=rho,
        p_value=p_value,
        ci_low=ci_low,
        ci_high=ci_high,
        n_pairs=len(predicted),
    )


def antonym_detection_rate(similarities: List[float]) -> float:
    """
    Compute fraction of antonym pairs with negative similarity.

    This is the key metric for GSE's emergent antonymy claim:
    - GSE should achieve >80% negative rate
    - Distributional approaches typically achieve ~0%

    Args:
        similarities: List of similarity scores for antonym pairs

    Returns:
        Fraction with similarity < 0
    """
    if not similarities:
        return 0.0

    sims = np.array(similarities)
    negative_count = np.sum(sims < 0)
    return float(negative_count / len(sims))


def antonym_metrics(similarities: List[float]) -> AntonymMetrics:
    """
    Compute comprehensive antonym evaluation metrics.

    Args:
        similarities: List of similarity scores for antonym pairs

    Returns:
        AntonymMetrics with detailed statistics
    """
    if not similarities:
        return AntonymMetrics(
            negative_rate=0.0,
            mean_similarity=0.0,
            std_similarity=0.0,
            median_similarity=0.0,
            min_similarity=0.0,
            max_similarity=0.0,
        )

    sims = np.array(similarities)

    return AntonymMetrics(
        negative_rate=antonym_detection_rate(similarities),
        mean_similarity=float(np.mean(sims)),
        std_similarity=float(np.std(sims)),
        median_similarity=float(np.median(sims)),
        min_similarity=float(np.min(sims)),
        max_similarity=float(np.max(sims)),
    )


def antonym_synonym_auc(
    antonym_sims: List[float],
    synonym_sims: List[float]
) -> float:
    """
    Compute AUC for discriminating antonyms from synonyms.

    A good model should give antonyms lower similarity than synonyms.
    AUC measures how well similarity alone separates the two classes.

    Args:
        antonym_sims: Similarity scores for antonym pairs
        synonym_sims: Similarity scores for synonym pairs

    Returns:
        AUC score (0.5 = random, 1.0 = perfect separation)
    """
    from sklearn.metrics import roc_auc_score

    if not antonym_sims or not synonym_sims:
        return 0.5

    # Labels: 0 for antonyms (should have low similarity)
    # Labels: 1 for synonyms (should have high similarity)
    y_true = [0] * len(antonym_sims) + [1] * len(synonym_sims)
    y_scores = list(antonym_sims) + list(synonym_sims)

    try:
        auc = roc_auc_score(y_true, y_scores)
        return float(auc)
    except Exception as e:
        logger.warning(f"AUC computation failed: {e}")
        return 0.5


def discrimination_metrics(
    antonym_sims: List[float],
    synonym_sims: List[float]
) -> DiscriminationMetrics:
    """
    Compute comprehensive discrimination metrics.

    Args:
        antonym_sims: Similarity scores for antonym pairs
        synonym_sims: Similarity scores for synonym pairs

    Returns:
        DiscriminationMetrics with AUC, accuracy, and effect sizes
    """
    if not antonym_sims or not synonym_sims:
        return DiscriminationMetrics(
            auc=0.5,
            accuracy=0.5,
            optimal_threshold=0.0,
            antonym_mean=0.0,
            synonym_mean=0.0,
            separation=0.0,
        )

    ant_arr = np.array(antonym_sims)
    syn_arr = np.array(synonym_sims)

    # Mean statistics
    ant_mean = float(np.mean(ant_arr))
    syn_mean = float(np.mean(syn_arr))

    # Cohen's d effect size
    pooled_std = np.sqrt(
        (np.var(ant_arr) + np.var(syn_arr)) / 2
    )
    if pooled_std > 0:
        cohens_d = (syn_mean - ant_mean) / pooled_std
    else:
        cohens_d = 0.0

    # AUC
    auc = antonym_synonym_auc(antonym_sims, synonym_sims)

    # Find optimal threshold
    all_sims = np.concatenate([ant_arr, syn_arr])
    thresholds = np.percentile(all_sims, np.arange(0, 101, 5))

    best_acc = 0.0
    best_thresh = 0.0

    for thresh in thresholds:
        # Predict: below threshold = antonym, above = synonym
        ant_correct = np.sum(ant_arr < thresh)
        syn_correct = np.sum(syn_arr >= thresh)
        acc = (ant_correct + syn_correct) / (len(ant_arr) + len(syn_arr))

        if acc > best_acc:
            best_acc = acc
            best_thresh = thresh

    return DiscriminationMetrics(
        auc=auc,
        accuracy=float(best_acc),
        optimal_threshold=float(best_thresh),
        antonym_mean=ant_mean,
        synonym_mean=syn_mean,
        separation=float(cohens_d),
    )


def significance_test(
    model1_sims: List[float],
    model2_sims: List[float],
    human: List[float]
) -> Tuple[float, float]:
    """
    Test if model1 significantly outperforms model2.

    Uses Williams' test for dependent correlations.

    Args:
        model1_sims: Similarities from model 1
        model2_sims: Similarities from model 2
        human: Human judgments

    Returns:
        Tuple of (t_statistic, p_value)
    """
    r1, _ = spearman_correlation(model1_sims, human)
    r2, _ = spearman_correlation(model2_sims, human)
    r12, _ = spearman_correlation(model1_sims, model2_sims)

    n = len(human)

    # Williams' test
    det = (1 - r1**2 - r2**2 - r12**2 + 2*r1*r2*r12)
    if det <= 0:
        return 0.0, 1.0

    t = (r1 - r2) * np.sqrt(
        (n - 1) * (1 + r12) /
        (2 * ((n - 1) / (n - 3)) * det + 0.25 * (r1 + r2)**2 * (1 - r12)**3)
    )

    # Two-tailed p-value
    p_value = 2 * (1 - stats.t.cdf(abs(t), n - 3))

    return float(t), float(p_value)


def per_pos_correlation(
    predicted: List[float],
    human: List[float],
    pos_tags: List[str]
) -> dict:
    """
    Compute correlation separately for each part of speech.

    Useful for understanding where GSE performs well/poorly.

    Args:
        predicted: Model predictions
        human: Human judgments
        pos_tags: Part of speech for each pair

    Returns:
        Dictionary of POS -> CorrelationResult
    """
    from collections import defaultdict

    by_pos = defaultdict(lambda: {'pred': [], 'human': []})

    for pred, hum, pos in zip(predicted, human, pos_tags):
        if pos:
            by_pos[pos]['pred'].append(pred)
            by_pos[pos]['human'].append(hum)

    results = {}
    for pos, data in by_pos.items():
        if len(data['pred']) >= 10:
            rho, p = spearman_correlation(data['pred'], data['human'])
            results[pos] = {
                'rho': rho,
                'p_value': p,
                'n': len(data['pred'])
            }

    return results


# =============================================================================
# BANK-PROJECTED COSINE METRICS
# =============================================================================
#
# Two SparseVectors can be globally similar yet diverge sharply within one
# semantic bank. The bipolar primitive structure puts antonymy at the bank
# level: GOOD/BAD oppose in EVALUATORS, ABOVE/BELOW in SPATIAL, BEFORE/AFTER
# in TEMPORAL. Global cosine averages all 8 banks and therefore washes out
# single-bank opposition under shared context in the other 7 banks.
#
# These metrics expose the per-bank structure so antonym detection can ask
# "do they oppose in *some* bank?" rather than "do they oppose globally?"


@dataclass
class BankCosineSignature:
    """Per-bank cosine breakdown for a SparseVector pair."""
    per_bank: Dict[str, Optional[float]]  # bank name -> cosine (None if empty either side)
    global_cosine: float
    min_bank_name: Optional[str]  # bank where cosine is most negative
    min_bank_cosine: float        # the most-negative bank cosine, or global if none populated


def bank_cosine_signature(v1, v2, dims_per_bank: int = DIMS_PER_BANK) -> BankCosineSignature:
    """Project both vectors onto each SemanticBank and report per-bank cosine.

    Args:
        v1, v2: SparseVectors (must support ``cosine`` and ``with_bank_only``).
        dims_per_bank: Per-bank dimension count for the projection.

    Returns:
        BankCosineSignature with per-bank cosines plus the global and
        most-negative-bank summaries.
    """
    per_bank: Dict[str, Optional[float]] = {}
    most_negative = (None, float("inf"))
    for bank in SemanticBank:
        b1 = v1.with_bank_only(bank.value, dims_per_bank)
        b2 = v2.with_bank_only(bank.value, dims_per_bank)
        if b1.nnz == 0 or b2.nnz == 0:
            per_bank[bank.name] = None
            continue
        cos = b1.cosine(b2)
        per_bank[bank.name] = cos
        if cos < most_negative[1]:
            most_negative = (bank.name, cos)

    global_cos = v1.cosine(v2)
    min_name, min_cos = most_negative
    if min_name is None:
        min_cos = global_cos

    return BankCosineSignature(
        per_bank=per_bank,
        global_cosine=global_cos,
        min_bank_name=min_name,
        min_bank_cosine=min_cos,
    )


def min_bank_cosine(v1, v2, dims_per_bank: int = DIMS_PER_BANK) -> float:
    """Most-negative bank-projected cosine (architecture-aligned antonymy score).

    For an antonym pair, the bipolar dimension's bank should produce a
    strongly negative cosine even when the global cosine is positive due to
    shared context in unrelated banks. This function returns that minimum.

    Returns ``global_cosine`` if no bank has activations on both sides.
    """
    return bank_cosine_signature(v1, v2, dims_per_bank).min_bank_cosine
