"""
Layer 1: Lexicon - Word-level HDC encoding with grammatical metadata.

Design principles:
- Semantic primitives encode MEANING (similarity-relevant)
- Grammatical features encode FUNCTION (parsing-relevant, similarity-masked)
- Operator metadata enables Layer 3 parsing
"""

from .similarity import full_similarity, semantic_similarity
from .word_encoding import (
    BindingBehavior,
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
    OperatorSpec,
    OperatorType,
)

__all__ = [
    "ComponentType",
    "OperatorType",
    "BindingBehavior",
    "GramRole",
    "GrammaticalFeatures",
    "OperatorSpec",
    "LexemeEntry",
    "semantic_similarity",
    "full_similarity",
]
