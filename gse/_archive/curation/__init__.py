"""
GSE Semantic Data Curation Module

Provides tools for curating training data based on cognitive complexity
measured through GSE semantic bank activations.

Key insight: Training data that activates multiple semantic banks
("cognitively complex" text) leads to more efficient model learning
than random or perplexity-based selection.

This module implements the data curation pipeline for Experiment 3
of the GSE paper, connecting to Tinker for distillation training.

Core components:
- cognitive_complexity.py: Compute complexity from bank activations
- corpus_scorer.py: Batch process and score corpora
- curator.py: Select high-value training data
- tinker_export.py: Export in Tinker training format
"""

from .cognitive_complexity import (
    CognitiveComplexityScore,
    compute_cognitive_complexity,
    compute_cross_bank_interaction,
    score_document,
)
from .corpus_scorer import (
    CorpusScorer,
    DocumentScore,
)
from .curator import (
    SemanticCurator,
    CurationMethod,
)
from .tinker_export import (
    export_for_tinker,
    TinkerTrainingConfig,
)

__all__ = [
    # Complexity scoring
    'CognitiveComplexityScore',
    'compute_cognitive_complexity',
    'compute_cross_bank_interaction',
    'score_document',
    # Corpus scoring
    'CorpusScorer',
    'DocumentScore',
    # Curation
    'SemanticCurator',
    'CurationMethod',
    # Tinker export
    'export_for_tinker',
    'TinkerTrainingConfig',
]
