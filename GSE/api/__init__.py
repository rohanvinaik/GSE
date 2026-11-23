"""
GSE API - Encoding and Decoding natural language to HDC vectors.

Usage:
    from GSE.api import GSEEncoder, GSEDecoder

    # Encode
    encoder = GSEEncoder()
    trace = encoder.encode("The dog is cuter than the cat")
    print(trace.to_json())

    # Decode
    decoder = GSEDecoder()
    semantics = decoder.decode(trace.vector)
    print(semantics.to_json())

    # Compare
    similarity = decoder.similarity(trace1.vector, trace2.vector)
    print(similarity.cosine)

    # Strict mode (raises exceptions instead of silent fallbacks)
    encoder = GSEEncoder(strict=True)
    try:
        trace = encoder.encode("xyzzy flurble")  # OOV words
    except OOVError as e:
        print(f"Unknown word: {e.word}")
"""

from GSE.api.decoder import GSEDecoder
from GSE.api.encoder import GSEEncoder
from GSE.api.errors import (
    DecodingError,
    EncodingError,
    GSEError,
    OOVError,
    OperatorError,
    PrimitiveError,
)
from GSE.api.trace import (
    AttributeExtraction,
    DecodedSemantics,
    EntityExtraction,
    OperationTrace,
    OperatorTrace,
    RelationExtraction,
    SimilarityResult,
    TokenTrace,
)

__all__ = [
    # Core classes
    "GSEEncoder",
    "GSEDecoder",
    # Trace types
    "TokenTrace",
    "OperatorTrace",
    "OperationTrace",
    "EntityExtraction",
    "AttributeExtraction",
    "RelationExtraction",
    "DecodedSemantics",
    "SimilarityResult",
    # Error types
    "GSEError",
    "OOVError",
    "EncodingError",
    "PrimitiveError",
    "OperatorError",
    "DecodingError",
]
