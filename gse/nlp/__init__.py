"""
GSE NLP Integration Layer.

Bridges established NLP resources (spaCy, AMR, CCG) to sentence-scale HDC primitives.
Based on formal semantics research (Montague 1973, Steedman 2000, etc.).
"""

from .sentence_parser import (
    AMR_TO_PRIMITIVES,
    DEP_TO_SYNTACTIC,
    FUNCTION_WORD_OPERATORS,
    MORPH_TO_TAM,
    LexiconSentencePrimitivePopulator,
    ParsedSentence,
    SentencePrimitiveAssignment,
    SentencePrimitiveParser,
)

__all__ = [
    "SentencePrimitiveParser",
    "SentencePrimitiveAssignment",
    "ParsedSentence",
    "LexiconSentencePrimitivePopulator",
    "FUNCTION_WORD_OPERATORS",
    "DEP_TO_SYNTACTIC",
    "MORPH_TO_TAM",
    "AMR_TO_PRIMITIVES",
]
