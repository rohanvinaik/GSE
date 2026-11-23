"""
Similarity functions with grammatical masking.

Design principles:
- semantic_similarity: Compares semantic content only (primitives)
- full_similarity: Includes all dimensions (for sentence-level comparisons)

Key insight for informational zeros:
- Word vectors encode ONLY semantic primitives
- "ran" and "run" have IDENTICAL semantic_vectors
- Grammatical features (tense, aspect) are stored as metadata in GrammaticalFeatures
- Result: semantic_similarity("ran", "run") == 1.0 naturally
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Set

import numpy as np

if TYPE_CHECKING:
    from ..vectors_v2 import SparseVector


def semantic_similarity(v1: "SparseVector", v2: "SparseVector") -> float:
    """
    Cosine similarity over SEMANTIC dimensions only.

    For word-level comparisons, this is the standard cosine since
    word vectors contain only semantic primitives.

    Grammatical features are stored as metadata (GrammaticalFeatures),
    NOT encoded in the vector dimensions.

    Result: similarity("ran", "run") == 1.0
    (because they share the same lemma-level semantic_vector)

    Args:
        v1: First sparse vector
        v2: Second sparse vector

    Returns:
        Cosine similarity in [-1.0, 1.0]
    """
    return v1.cosine(v2)


def full_similarity(v1: "SparseVector", v2: "SparseVector") -> float:
    """
    Cosine similarity over ALL dimensions including grammatical.

    For word-level vectors, this is identical to semantic_similarity
    since grammatical features are metadata, not dimensions.

    For sentence-level vectors (after composition), this may differ
    if grammatical features are encoded during composition.

    Args:
        v1: First sparse vector
        v2: Second sparse vector

    Returns:
        Cosine similarity in [-1.0, 1.0]
    """
    return v1.cosine(v2)


def bank_masked_similarity(
    v1: "SparseVector",
    v2: "SparseVector",
    exclude_banks: Set[int],
    dims_per_bank: int = 1024,
) -> float:
    """
    Cosine similarity excluding specific banks.

    Useful for sentence-level analysis where you want to:
    - Compare semantic content without temporal features
    - Isolate specific semantic aspects

    Args:
        v1: First sparse vector
        v2: Second sparse vector
        exclude_banks: Set of bank indices to exclude (0-7 for standard 8-bank layout)
        dims_per_bank: Dimensions per bank (default 1024)

    Returns:
        Cosine similarity excluding specified banks
    """
    v1_filtered = without_banks(v1, exclude_banks, dims_per_bank)
    v2_filtered = without_banks(v2, exclude_banks, dims_per_bank)
    return v1_filtered.cosine(v2_filtered)


def without_banks(
    v: "SparseVector",
    exclude_banks: Set[int],
    dims_per_bank: int = 1024,
) -> "SparseVector":
    """
    Create a new vector with specified banks masked out.

    This is a utility function for bank-specific analysis.
    For standard word-level similarity, use semantic_similarity() directly.

    Args:
        v: Input sparse vector
        exclude_banks: Set of bank indices to exclude
        dims_per_bank: Dimensions per bank

    Returns:
        New SparseVector with excluded banks zeroed out
    """
    from ..vectors_v2 import SparseVector

    # Filter positive indices
    new_positive = []
    for idx in v.positive_indices:
        bank = idx // dims_per_bank
        if bank not in exclude_banks:
            new_positive.append(idx)

    # Filter negative indices
    new_negative = []
    for idx in v.negative_indices:
        bank = idx // dims_per_bank
        if bank not in exclude_banks:
            new_negative.append(idx)

    return SparseVector(
        dimension=v.dimension,
        positive_indices=np.array(new_positive, dtype=np.uint16),
        negative_indices=np.array(new_negative, dtype=np.uint16),
        bank=v.bank if v.bank not in exclude_banks else None,
    )


def polarity_analysis(
    v1: "SparseVector",
    v2: "SparseVector",
) -> dict:
    """
    Detailed similarity analysis with polarity breakdown.

    Useful for understanding WHY two words are similar/different:
    - alignment: shared positive/negative dimensions (synonymy signal)
    - opposition: opposite signs in same dimension (antonymy signal)
    - orthogonality: no overlap (unrelated concepts)

    Args:
        v1: First sparse vector
        v2: Second sparse vector

    Returns:
        Dict with cosine, alignment, opposition, orthogonality scores
    """
    support1 = set(v1.support.tolist())
    support2 = set(v2.support.tolist())

    overlap = support1 & support2
    union = support1 | support2

    if not union:
        return {
            "cosine": 0.0,
            "alignment": 0.0,
            "opposition": 0.0,
            "orthogonality": 1.0,
        }

    # Count same-sign and opposite-sign overlaps
    dense1 = v1.to_dense()
    dense2 = v2.to_dense()

    same_sign = 0
    opposite_sign = 0
    for idx in overlap:
        if dense1[idx] == dense2[idx]:
            same_sign += 1
        else:
            opposite_sign += 1

    return {
        "cosine": v1.cosine(v2),
        "alignment": same_sign / len(union) if union else 0.0,
        "opposition": opposite_sign / len(union) if union else 0.0,
        "orthogonality": 1 - len(overlap) / len(union) if union else 1.0,
    }
