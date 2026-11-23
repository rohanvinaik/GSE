"""
GSE Benchmark Module (v2)

Provides dataset loading and metrics for evaluating GSE.
Note: baselines and evaluator are being updated for v2 pipeline.
"""

from .datasets import (
    PRIMITIVE_ANTONYM_PAIRS,
    SYNONYM_PAIRS,
    BenchmarkDataset,
    SentencePair,
    WordPair,
    get_all_datasets,
    load_custom_antonyms,
    load_custom_synonyms,
    load_simlex999,
    load_sts_benchmark,
    load_wordsim353,
)
from .metrics import (
    AntonymMetrics,
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

__all__ = [
    # Dataset loaders
    "BenchmarkDataset",
    "WordPair",
    "SentencePair",
    "load_simlex999",
    "load_wordsim353",
    "load_sts_benchmark",
    "load_custom_antonyms",
    "load_custom_synonyms",
    "get_all_datasets",
    "PRIMITIVE_ANTONYM_PAIRS",
    "SYNONYM_PAIRS",
    # Metrics
    "spearman_correlation",
    "pearson_correlation",
    "bootstrap_confidence_interval",
    "correlation_with_ci",
    "antonym_detection_rate",
    "antonym_metrics",
    "antonym_synonym_auc",
    "discrimination_metrics",
    "significance_test",
    "per_pos_correlation",
    "CorrelationResult",
    "AntonymMetrics",
    "DiscriminationMetrics",
]
