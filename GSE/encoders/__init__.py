"""
GSE Encoders Module (v2)

Provides multi-scale encoding for the constraint cascade:
- Word → Sentence → Paragraph → Text → Document

Encoders:
- SentenceStructureEncoder: D/N positional encoding for sentences
- ParagraphStructureEncoder: Coherence relations and gestalt detection
- TextStructureEncoder: Genre, register, and domain detection
"""

from .paragraph_structure_encoder import (
    CoherenceRelation,
    GestaltPoint,
    GestaltType,
    IntensityTrajectory,
    ParagraphEncoding,
    ParagraphStructure,
    ParagraphStructureEncoder,
    SentenceInfo,
    encode_paragraph,
    get_paragraph_encoder,
)
from .sentence_structure_encoder import (
    CORE_STRUCTURE_PRIMITIVES,
    MODIFICATION_PRIMITIVES,
    TAM_FEATURE_PRIMITIVES,
    SentenceStructureEncoder,
    SentenceVectorMetadata,
    SyntacticBank,
    WordPosition,
    encode_simple_sentence,
)
from .text_structure_encoder import (
    DocumentEntity,
    Domain,
    Genre,
    Register,
    TextEncoding,
    TextStructure,
    TextStructureEncoder,
    encode_text,
    get_text_encoder,
)

__all__ = [
    # Sentence encoder
    "SentenceStructureEncoder",
    "SentenceVectorMetadata",
    "WordPosition",
    "encode_simple_sentence",
    "SyntacticBank",
    "CORE_STRUCTURE_PRIMITIVES",
    "MODIFICATION_PRIMITIVES",
    "TAM_FEATURE_PRIMITIVES",
    # Paragraph encoder
    "ParagraphStructureEncoder",
    "ParagraphEncoding",
    "ParagraphStructure",
    "CoherenceRelation",
    "GestaltType",
    "GestaltPoint",
    "IntensityTrajectory",
    "SentenceInfo",
    "encode_paragraph",
    "get_paragraph_encoder",
    # Text encoder
    "TextStructureEncoder",
    "TextEncoding",
    "TextStructure",
    "Genre",
    "Register",
    "Domain",
    "DocumentEntity",
    "encode_text",
    "get_text_encoder",
]
