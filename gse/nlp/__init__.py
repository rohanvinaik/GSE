"""
GSE NLP Integration Layer.

The deterministic native front-end (gse.nlp.native) + the sentence-scale HDC
primitive schema (UD/AMR/TAM mappings) the encoder reads. spaCy was retired.
"""

from .sentence_parser import (
    AMR_TO_PRIMITIVES,
    DEP_TO_SYNTACTIC,
    FUNCTION_WORD_OPERATORS,
    MORPH_TO_TAM,
    ParsedSentence,
    SentencePrimitiveAssignment,
)

__all__ = [
    "SentencePrimitiveAssignment",
    "ParsedSentence",
    "FUNCTION_WORD_OPERATORS",
    "DEP_TO_SYNTACTIC",
    "MORPH_TO_TAM",
    "AMR_TO_PRIMITIVES",
]
