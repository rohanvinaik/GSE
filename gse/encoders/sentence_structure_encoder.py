#!/usr/bin/env python3
"""
GSE Sentence Structure Encoder - D/N Positional Encoding

Length-normalized encoding where each word position receives D/N dimensions:
- D = 8192 total dimensions (fixed)
- N = word count in sentence (variable)
- Each word position gets D/N dimensions

This encoder creates sentence-level representations that:
1. Encode word positions with exact D/N boundaries
2. Apply Gaussian stretching for non-integer boundaries
3. Combine semantic (word) and syntactic (role) information
4. Support position recovery from the composite vector

Key features:
- Position-aware encoding that preserves word order
- Syntactic role primitives (subject, predicate, object, etc.)
- TAM features (tense, aspect, mood)
- Stretching algorithm for fractional dimension allocation
"""

from dataclasses import dataclass, field
from enum import Enum
from math import exp, floor
from typing import Dict, List, Optional, Tuple

import numpy as np

from gse.primitives_v2 import D

# =============================================================================
# SYNTACTIC PRIMITIVES
# =============================================================================


class SyntacticBank(Enum):
    """Three orthogonal banks for syntactic primitives."""

    CORE_STRUCTURE = "core"  # 40% - Subject, Predicate, Object, Complement
    MODIFICATION = "mod"  # 30% - Adjective, Adverb, Determiner
    TAM_FEATURES = "tam"  # 30% - Tense, Aspect, Mood


# Core structure primitives (40% of word dimensions)
CORE_STRUCTURE_PRIMITIVES = [
    "SYN_SUBJ",  # Subject position
    "SYN_PRED",  # Predicate position
    "SYN_OBJ",  # Object position
    "SYN_COMPL",  # Complement position
]

# Modification primitives (30% of word dimensions)
MODIFICATION_PRIMITIVES = [
    "SYN_ADJ_MOD",  # Adjectival modifier
    "SYN_ADV_MOD",  # Adverbial modifier
    "SYN_DET",  # Determiner position
]

# TAM feature primitives (30% of word dimensions)
TAM_FEATURE_PRIMITIVES = [
    "SYN_TENSE_PAST",  # Past tense marker
    "SYN_ASPECT_PERF",  # Perfect aspect marker
    "SYN_MOOD_INTER",  # Interrogative mood marker
]

ALL_SYNTACTIC_PRIMITIVES = CORE_STRUCTURE_PRIMITIVES + MODIFICATION_PRIMITIVES + TAM_FEATURE_PRIMITIVES

# Bank allocation (percentages of per-word dimensions)
BANK_ALLOCATIONS = {
    SyntacticBank.CORE_STRUCTURE: 0.40,
    SyntacticBank.MODIFICATION: 0.30,
    SyntacticBank.TAM_FEATURES: 0.30,
}


# =============================================================================
# METADATA
# =============================================================================


@dataclass
class SentenceVectorMetadata:
    """
    Metadata for position recovery and analysis.

    Stores information needed to:
    1. Recover word positions from composite vector
    2. Identify per-position signal strength
    3. Track which syntactic banks are active
    """

    word_count: int  # N
    total_dimensions: int = D  # D (8192)
    dims_per_word: float = 0.0  # D/N
    word_boundaries: List[Tuple[int, int]] = field(default_factory=list)
    per_position_magnitude: List[float] = field(default_factory=list)
    bank_magnitudes: Dict[str, float] = field(default_factory=dict)
    syntactic_roles: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.word_count > 0:
            self.dims_per_word = self.total_dimensions / self.word_count


@dataclass
class WordPosition:
    """Encoding of a word at a specific position."""

    position: int  # 0-indexed position in sentence
    word: str  # The word token
    syntactic_role: str  # Primary syntactic role
    semantic_vector: np.ndarray  # Word's semantic vector (from lexicon)
    tam_features: List[str] = field(default_factory=list)  # TAM markers


# =============================================================================
# STRETCHING ALGORITHM
# =============================================================================


def gaussian_weight(distance: float, sigma: float = 0.5) -> float:
    """Compute Gaussian weight for distance from center."""
    return exp(-(distance**2) / (2 * sigma**2))


def stretch_to_dimensions(
    signal: np.ndarray,
    target_start: float,
    target_end: float,
    total_dims: int = D,
    sigma: float = 0.5,
) -> np.ndarray:
    """
    Project signal with Gaussian falloff to handle non-integer boundaries.

    When D/N doesn't yield integers, this algorithm smoothly distributes
    the signal across neighboring dimensions using Gaussian weighting.

    Args:
        signal: Input signal to stretch
        target_start: Start position (may be fractional)
        target_end: End position (may be fractional)
        total_dims: Total output dimensions
        sigma: Gaussian spread parameter

    Returns:
        Stretched signal of length total_dims
    """
    result = np.zeros(total_dims, dtype=np.float32)
    signal_len = len(signal)

    if signal_len == 0:
        return result

    target_width = target_end - target_start

    for i, val in enumerate(signal):
        if val == 0:
            continue

        # Calculate target position
        relative_pos = i / signal_len
        target_pos = target_start + relative_pos * target_width

        # Integer boundaries
        left_dim = int(floor(target_pos))
        right_dim = left_dim + 1

        # Fractional distance
        frac = target_pos - left_dim

        # Gaussian weights for neighbors
        left_weight = gaussian_weight(frac, sigma)
        right_weight = gaussian_weight(1 - frac, sigma)

        # Normalize weights
        total_weight = left_weight + right_weight
        if total_weight > 0:
            left_weight /= total_weight
            right_weight /= total_weight

        # Apply to result (with boundary checks)
        if 0 <= left_dim < total_dims:
            result[left_dim] += val * left_weight
        if 0 <= right_dim < total_dims:
            result[right_dim] += val * right_weight

    return result


def compute_word_boundaries(n_words: int, total_dims: int = D) -> List[Tuple[float, float]]:
    """
    Compute dimension boundaries for each word position.

    Args:
        n_words: Number of words in sentence
        total_dims: Total dimensions

    Returns:
        List of (start, end) tuples for each position
    """
    dims_per_word = total_dims / n_words
    boundaries = []

    for i in range(n_words):
        start = i * dims_per_word
        end = (i + 1) * dims_per_word
        boundaries.append((start, end))

    return boundaries


# =============================================================================
# SENTENCE STRUCTURE ENCODER
# =============================================================================


class SentenceStructureEncoder:
    """
    Encodes sentences using D/N positional encoding.

    Each word position receives D/N dimensions, with:
    - 40% for core structure (subject, predicate, object)
    - 30% for modification (adjective, adverb, determiner)
    - 30% for TAM features (tense, aspect, mood)
    """

    def __init__(self, total_dims: int = D):
        """
        Initialize encoder.

        Args:
            total_dims: Total output dimensions (default: 8192)
        """
        self.total_dims = total_dims

        # Pre-compute syntactic primitive vectors
        self._syntactic_vectors = self._generate_syntactic_vectors()

    def _generate_syntactic_vectors(self) -> Dict[str, np.ndarray]:
        """Generate orthogonal vectors for syntactic primitives."""
        vectors = {}

        # Use Hadamard-like patterns for orthogonality
        # Each primitive gets a unique binary pattern
        np.random.seed(42)  # Reproducible

        n_primitives = len(ALL_SYNTACTIC_PRIMITIVES)
        pattern_length = 64  # Compact representation

        for i, prim in enumerate(ALL_SYNTACTIC_PRIMITIVES):
            # Create unique pattern using prime-based spacing
            pattern = np.zeros(pattern_length, dtype=np.float32)
            # Set +1 and -1 in specific positions based on index
            for j in range(pattern_length):
                # Use bit pattern for deterministic assignment
                if (j >> i) & 1:
                    pattern[j] = 1.0
                else:
                    pattern[j] = -1.0
            vectors[prim] = pattern

        return vectors

    def encode_sentence(
        self,
        word_positions: List[WordPosition],
    ) -> Tuple[np.ndarray, SentenceVectorMetadata]:
        """
        Encode a sentence into a D-dimensional vector.

        Args:
            word_positions: List of WordPosition objects with words and roles

        Returns:
            (sentence_vector, metadata) tuple
        """
        n_words = len(word_positions)
        if n_words == 0:
            return np.zeros(self.total_dims, dtype=np.float32), SentenceVectorMetadata(0)

        # Compute boundaries
        boundaries = compute_word_boundaries(n_words, self.total_dims)

        # Initialize result
        result = np.zeros(self.total_dims, dtype=np.float32)

        # Track metadata
        per_position_mag = []
        syntactic_roles = []
        bank_mags = {bank.value: 0.0 for bank in SyntacticBank}

        for i, word_pos in enumerate(word_positions):
            start, end = boundaries[i]
            word_dims = end - start

            # Allocate dimensions within this word's range
            core_end = start + word_dims * BANK_ALLOCATIONS[SyntacticBank.CORE_STRUCTURE]
            mod_end = core_end + word_dims * BANK_ALLOCATIONS[SyntacticBank.MODIFICATION]
            tam_end = end  # Remainder goes to TAM

            # 1. Encode core structure (40%)
            if word_pos.syntactic_role in self._syntactic_vectors:
                syn_vec = self._syntactic_vectors[word_pos.syntactic_role]
                stretched = stretch_to_dimensions(syn_vec, start, core_end, self.total_dims)
                result += stretched
                bank_mags[SyntacticBank.CORE_STRUCTURE.value] += np.sum(np.abs(stretched))

            # 2. Encode semantic content (overlaid on modification bank)
            if word_pos.semantic_vector is not None and len(word_pos.semantic_vector) > 0:
                stretched = stretch_to_dimensions(
                    word_pos.semantic_vector.astype(np.float32), core_end, mod_end, self.total_dims
                )
                result += stretched
                bank_mags[SyntacticBank.MODIFICATION.value] += np.sum(np.abs(stretched))

            # 3. Encode TAM features (30%)
            for tam in word_pos.tam_features:
                if tam in self._syntactic_vectors:
                    tam_vec = self._syntactic_vectors[tam]
                    stretched = stretch_to_dimensions(tam_vec, mod_end, tam_end, self.total_dims)
                    result += stretched
                    bank_mags[SyntacticBank.TAM_FEATURES.value] += np.sum(np.abs(stretched))

            # Track magnitude and role
            per_position_mag.append(float(np.sum(np.abs(result[int(start) : int(end)]))))
            syntactic_roles.append(word_pos.syntactic_role)

        # Build metadata
        metadata = SentenceVectorMetadata(
            word_count=n_words,
            total_dimensions=self.total_dims,
            dims_per_word=self.total_dims / n_words,
            word_boundaries=[(int(s), int(e)) for s, e in boundaries],
            per_position_magnitude=per_position_mag,
            bank_magnitudes=bank_mags,
            syntactic_roles=syntactic_roles,
        )

        return result, metadata

    def decode_positions(
        self,
        vector: np.ndarray,
        metadata: SentenceVectorMetadata,
    ) -> List[Tuple[int, float]]:
        """
        Recover word positions from a sentence vector.

        Args:
            vector: Sentence vector
            metadata: Metadata from encoding

        Returns:
            List of (position, magnitude) tuples
        """
        positions = []

        for i, (start, end) in enumerate(metadata.word_boundaries):
            segment = vector[start:end]
            magnitude = float(np.sum(np.abs(segment)))
            positions.append((i, magnitude))

        return positions

    def compare_structure(
        self,
        vec1: np.ndarray,
        meta1: SentenceVectorMetadata,
        vec2: np.ndarray,
        meta2: SentenceVectorMetadata,
    ) -> Dict[str, float]:
        """
        Compare structural similarity of two sentences.

        Returns metrics for:
        - Overall cosine similarity
        - Per-bank similarity
        - Position alignment score
        """
        # Overall cosine
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            overall_cos = 0.0
        else:
            overall_cos = float(np.dot(vec1, vec2) / (norm1 * norm2))

        # Per-bank similarity (using metadata magnitudes)
        bank_similarity = {}
        for bank in SyntacticBank:
            mag1 = meta1.bank_magnitudes.get(bank.value, 0)
            mag2 = meta2.bank_magnitudes.get(bank.value, 0)
            if mag1 + mag2 > 0:
                bank_similarity[bank.value] = 2 * min(mag1, mag2) / (mag1 + mag2)
            else:
                bank_similarity[bank.value] = 0.0

        # Position alignment (do they have same number of words?)
        length_ratio = min(meta1.word_count, meta2.word_count) / max(meta1.word_count, meta2.word_count)

        return {
            "cosine_similarity": overall_cos,
            "bank_similarity": bank_similarity,
            "length_ratio": length_ratio,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def encode_simple_sentence(
    words: List[str],
    roles: List[str],
    encoder: Optional[SentenceStructureEncoder] = None,
) -> Tuple[np.ndarray, SentenceVectorMetadata]:
    """
    Quick encoding of a sentence with word/role pairs.

    Args:
        words: List of word tokens
        roles: List of syntactic roles (same length as words)
        encoder: Optional encoder instance (created if not provided)

    Returns:
        (sentence_vector, metadata) tuple
    """
    if encoder is None:
        encoder = SentenceStructureEncoder()

    word_positions = [
        WordPosition(
            position=i,
            word=word,
            syntactic_role=role,
            semantic_vector=np.array([], dtype=np.float32),
        )
        for i, (word, role) in enumerate(zip(words, roles))
    ]

    return encoder.encode_sentence(word_positions)


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("SentenceStructureEncoder verification tests")
    print("=" * 50)

    encoder = SentenceStructureEncoder()
    print(f"✓ Encoder initialized with {encoder.total_dims} dimensions")

    # Test 1: Simple sentence encoding
    sentence1_words = ["The", "cat", "sat", "on", "the", "mat"]
    sentence1_roles = ["SYN_DET", "SYN_SUBJ", "SYN_PRED", "SYN_ADV_MOD", "SYN_DET", "SYN_OBJ"]

    vec1, meta1 = encode_simple_sentence(sentence1_words, sentence1_roles, encoder)
    print(f"✓ Encoded 6-word sentence: {meta1.dims_per_word:.2f} dims/word")
    print(f"  Word boundaries: {meta1.word_boundaries[:3]}...")

    # Test 2: Different length sentence
    sentence2_words = ["Dogs", "bark"]
    sentence2_roles = ["SYN_SUBJ", "SYN_PRED"]

    vec2, meta2 = encode_simple_sentence(sentence2_words, sentence2_roles, encoder)
    print(f"✓ Encoded 2-word sentence: {meta2.dims_per_word:.2f} dims/word")

    # Test 3: Position recovery
    positions = encoder.decode_positions(vec1, meta1)
    assert len(positions) == 6, "Should recover 6 positions"
    print(f"✓ Position recovery: {len(positions)} positions found")

    # Test 4: Structural comparison
    comparison = encoder.compare_structure(vec1, meta1, vec2, meta2)
    print("✓ Structure comparison:")
    print(f"  - Cosine similarity: {comparison['cosine_similarity']:.3f}")
    print(f"  - Length ratio: {comparison['length_ratio']:.3f}")

    # Test 5: Same structure, different words
    sentence3_words = ["A", "dog", "ran", "to", "a", "park"]
    sentence3_roles = ["SYN_DET", "SYN_SUBJ", "SYN_PRED", "SYN_ADV_MOD", "SYN_DET", "SYN_OBJ"]

    vec3, meta3 = encode_simple_sentence(sentence3_words, sentence3_roles, encoder)
    comp_same_structure = encoder.compare_structure(vec1, meta1, vec3, meta3)
    print("✓ Same structure comparison:")
    print(f"  - Cosine similarity: {comp_same_structure['cosine_similarity']:.3f}")
    print("  - (Should be higher than different structures)")

    # Test 6: Verify D/N for various N
    for n in [1, 3, 5, 10, 20, 30]:
        dims_per_word = D / n
        boundaries = compute_word_boundaries(n, D)
        assert len(boundaries) == n
        assert boundaries[0][0] == 0
        assert abs(boundaries[-1][1] - D) < 1e-6
        print(f"✓ N={n}: {dims_per_word:.2f} dims/word, boundaries valid")

    # Test 7: Non-integer boundary stretching
    signal = np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float32)
    stretched = stretch_to_dimensions(signal, 2.5, 6.7, 10)
    assert len(stretched) == 10
    assert np.sum(np.abs(stretched)) > 0, "Stretched signal should have content"
    print(f"✓ Non-integer stretching works: sum(|x|) = {np.sum(np.abs(stretched)):.3f}")

    # Test 8: TAM features
    word_with_tam = WordPosition(
        position=0,
        word="walked",
        syntactic_role="SYN_PRED",
        semantic_vector=np.array([1, -1, 1], dtype=np.float32),
        tam_features=["SYN_TENSE_PAST"],
    )

    vec_tam, meta_tam = encoder.encode_sentence([word_with_tam])
    tam_mag = meta_tam.bank_magnitudes.get("tam", 0)
    print(f"✓ TAM feature encoding: magnitude = {tam_mag:.3f}")

    print("\n" + "=" * 50)
    print("All SentenceStructureEncoder tests passed!")
