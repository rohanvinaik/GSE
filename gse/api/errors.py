#!/usr/bin/env python3
"""
GSE Error Hierarchy.

Provides explicit, typed exceptions for GSE operations.
These are used in strict mode; in default mode, the system
uses graceful fallbacks (zero vectors, empty dicts).
"""


class GSEError(Exception):
    """Base exception for all GSE errors."""
    pass


class OOVError(GSEError):
    """
    Raised when a word is not found in the lexicon.

    In default mode: Returns empty primitives ({}, {}, {})
    In strict mode: Raises this exception
    """
    def __init__(self, word: str):
        self.word = word
        super().__init__(f"Out-of-vocabulary word: '{word}'")


class EncodingError(GSEError):
    """
    Raised when encoding fails for a text input.

    In default mode: Returns zero vector
    In strict mode: Raises this exception
    """
    def __init__(self, text: str, reason: str):
        self.text = text
        self.reason = reason
        super().__init__(f"Encoding failed for '{text[:50]}...': {reason}")


class PrimitiveError(GSEError):
    """
    Raised when an invalid primitive is referenced.

    In default mode: Skips the invalid primitive
    In strict mode: Raises this exception
    """
    def __init__(self, primitive: str):
        self.primitive = primitive
        super().__init__(f"Invalid primitive: '{primitive}'")


class OperatorError(GSEError):
    """
    Raised when a compositional operator cannot be resolved.

    In default mode: Returns None for operator result
    In strict mode: Raises this exception
    """
    def __init__(self, operator: str, reason: str):
        self.operator = operator
        self.reason = reason
        super().__init__(f"Operator resolution failed for '{operator}': {reason}")


class DecodingError(GSEError):
    """
    Raised when decoding fails for a vector.
    """
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Decoding failed: {reason}")
