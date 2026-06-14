"""
GSE Scales Module (v2)

Provides syntactic structure encoding for D/N sentence analysis:
- SyntacticPrimitive: 10 primitives for sentence structure
- SyntacticBank: 3 orthogonal banks (CORE, MODIFICATION, TAM)
- SyntacticPrimitiveEncoder: D/N dimensional encoder
- parse_spacy_sentence: spaCy integration
"""

from .syntactic_structure import (
    BANK_ALLOCATIONS,
    BANK_ASSIGNMENTS,
    MORPH_MAPPING,
    SPACY_DEP_MAPPING,
    SYNTACTIC_BANKS,
    SYNTACTIC_PRIMITIVES,
    SentenceSyntax,
    SyntacticAnnotation,
    SyntacticBank,
    SyntacticPrimitive,
    SyntacticPrimitiveEncoder,
    parse_spacy_sentence,
)

__all__ = [
    # Enums
    "SyntacticPrimitive",
    "SyntacticBank",
    # Dataclasses
    "SyntacticAnnotation",
    "SentenceSyntax",
    # Encoder
    "SyntacticPrimitiveEncoder",
    # Parser
    "parse_spacy_sentence",
    # Constants
    "BANK_ASSIGNMENTS",
    "BANK_ALLOCATIONS",
    "SPACY_DEP_MAPPING",
    "MORPH_MAPPING",
    "SYNTACTIC_PRIMITIVES",
    "SYNTACTIC_BANKS",
]
