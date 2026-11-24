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

from importlib import import_module
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from GSE.api.decoder import GSEDecoder
    from GSE.api.encoder import GSEEncoder

# The encoder and decoder load on first use (PEP 562). The symbolic layer imports
# the trace types from this package, and the encoder uses the symbolic layer, so
# importing them here eagerly made every trace-type import a cycle through the encoder.
_LAZY = {"GSEDecoder": "GSE.api.decoder", "GSEEncoder": "GSE.api.encoder"}


def __getattr__(name: str):
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(_LAZY[name]), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


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
