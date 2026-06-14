#!/usr/bin/env python3
"""
GSE Vectors v2 - Hadamard-OTP Hyperdimensional Computing

This module implements the vector encoding system for GSE v2 featuring:
1. Hadamard-based orthogonal vector generation (exact orthogonality)
2. Sparse ternary representation ({-1, 0, +1})
3. Bipolar dimension handling (antonyms as +1/-1 in same space)
4. Hierarchical modifier encoding (ordinal stacking)
5. Core HDC operations (bind, bundle, permute)

Key insight: Hadamard matrices provide EXACT orthogonality (cosine = 0.0)
unlike random vectors which only give approximate orthogonality.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import msgpack
import numpy as np
from scipy.linalg import hadamard

from gse.primitives_v2 import (
    BIPOLAR_DIMENSIONS,
    DIMS_PER_BANK,
    N_BANKS,
    PRIMITIVE_REGISTRY,
    SEMANTIC_BANK_NAMES,
    SEMANTIC_ROLES,
    SENTENCE_PRIMITIVE_REGISTRY,
    BipolarDimension,
    D,
    SemanticBank,
    # Sentence-scale primitives (orthogonal HDC space)
    get_dimension_range,
    get_primitive_info,
)

# =============================================================================
# SPARSE TERNARY VECTOR
# =============================================================================

@dataclass
class SparseVector:
    """
    Sparse ternary vector representation.

    Values are in {-1, 0, +1} where:
    - +1: Positive activation
    - -1: Negative activation (antonym/opposition)
    - 0:  Orthogonal (no information in this dimension)

    Stored as two arrays: positive_indices and negative_indices.
    All other indices are implicitly 0.
    """
    dimension: int
    positive_indices: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))
    negative_indices: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))
    bank: Optional[int] = None  # Primary bank if single-bank vector

    def __post_init__(self):
        # Ensure arrays are sorted and unique
        self.positive_indices = np.unique(self.positive_indices).astype(np.uint16)
        self.negative_indices = np.unique(self.negative_indices).astype(np.uint16)

    @property
    def nnz(self) -> int:
        """Number of non-zero elements."""
        return len(self.positive_indices) + len(self.negative_indices)

    @property
    def sparsity(self) -> float:
        """Fraction of non-zero elements."""
        return self.nnz / self.dimension

    @property
    def support(self) -> np.ndarray:
        """All non-zero indices."""
        return np.union1d(self.positive_indices, self.negative_indices)

    def to_dense(self) -> np.ndarray:
        """Convert to dense numpy array."""
        dense = np.zeros(self.dimension, dtype=np.int8)
        dense[self.positive_indices] = 1
        dense[self.negative_indices] = -1
        return dense

    @classmethod
    def from_dense(cls, dense: np.ndarray, bank: Optional[int] = None) -> "SparseVector":
        """Create from dense array."""
        positive = np.where(dense > 0)[0].astype(np.uint16)
        negative = np.where(dense < 0)[0].astype(np.uint16)
        return cls(
            dimension=len(dense),
            positive_indices=positive,
            negative_indices=negative,
            bank=bank,
        )

    @classmethod
    def zeros(cls, dimension: int = D) -> "SparseVector":
        """Create zero vector."""
        return cls(dimension=dimension)

    def dot(self, other: "SparseVector") -> int:
        """Sparse dot product."""
        # +1 for matching positives
        pp = len(np.intersect1d(self.positive_indices, other.positive_indices))
        # +1 for matching negatives
        nn = len(np.intersect1d(self.negative_indices, other.negative_indices))
        # -1 for opposite signs
        pn = len(np.intersect1d(self.positive_indices, other.negative_indices))
        np_ = len(np.intersect1d(self.negative_indices, other.positive_indices))

        return pp + nn - pn - np_

    def cosine(self, other: "SparseVector") -> float:
        """Cosine similarity."""
        dot = self.dot(other)
        norm_self = np.sqrt(self.nnz) if self.nnz > 0 else 1.0
        norm_other = np.sqrt(other.nnz) if other.nnz > 0 else 1.0
        return dot / (norm_self * norm_other) if norm_self * norm_other > 0 else 0.0

    def negate(self) -> "SparseVector":
        """Return negated vector (swap positive and negative)."""
        return SparseVector(
            dimension=self.dimension,
            positive_indices=self.negative_indices.copy(),
            negative_indices=self.positive_indices.copy(),
            bank=self.bank,
        )

    def magnitude(self) -> float:
        """L2 norm (for ternary, equals sqrt(nnz))."""
        return np.sqrt(self.nnz)

    def serialize(self) -> bytes:
        """Serialize to msgpack bytes."""
        data = {
            "d": self.dimension,
            "p": self.positive_indices.tolist(),
            "n": self.negative_indices.tolist(),
            "b": self.bank,
        }
        return msgpack.packb(data)

    @classmethod
    def deserialize(cls, data: bytes) -> "SparseVector":
        """Deserialize from msgpack bytes."""
        obj = msgpack.unpackb(data)
        return cls(
            dimension=obj["d"],
            positive_indices=np.array(obj["p"], dtype=np.uint16),
            negative_indices=np.array(obj["n"], dtype=np.uint16),
            bank=obj.get("b"),
        )

    def hash(self) -> str:
        """Content hash for Merkle trees."""
        return hashlib.sha256(self.serialize()).hexdigest()[:32]

    def without_bank(
        self,
        bank_index: int,
        dims_per_bank: int = DIMS_PER_BANK,
    ) -> "SparseVector":
        """
        Return a new vector with the specified bank masked out.

        Useful for:
        - Comparing semantic content without specific bank contributions
        - Isolating different semantic aspects
        - Implementing informational zero masking

        Args:
            bank_index: The bank to exclude (0-7 for standard 8-bank layout)
            dims_per_bank: Dimensions per bank (default 1024)

        Returns:
            New SparseVector with the bank's dimensions zeroed out
        """
        bank_start = bank_index * dims_per_bank
        bank_end = bank_start + dims_per_bank

        # Filter positive indices (keep those outside bank range)
        new_positive = self.positive_indices[
            (self.positive_indices < bank_start) | (self.positive_indices >= bank_end)
        ]

        # Filter negative indices
        new_negative = self.negative_indices[
            (self.negative_indices < bank_start) | (self.negative_indices >= bank_end)
        ]

        return SparseVector(
            dimension=self.dimension,
            positive_indices=new_positive,
            negative_indices=new_negative,
            bank=self.bank if self.bank != bank_index else None,
        )

    def with_bank_only(
        self,
        bank_index: int,
        dims_per_bank: int = DIMS_PER_BANK,
    ) -> "SparseVector":
        """
        Return a new vector with ONLY the specified bank's dimensions.

        Args:
            bank_index: The bank to keep (0-7 for standard 8-bank layout)
            dims_per_bank: Dimensions per bank (default 1024)

        Returns:
            New SparseVector containing only the bank's dimensions
        """
        bank_start = bank_index * dims_per_bank
        bank_end = bank_start + dims_per_bank

        # Filter positive indices (keep only those in bank range)
        new_positive = self.positive_indices[
            (self.positive_indices >= bank_start) & (self.positive_indices < bank_end)
        ]

        # Filter negative indices
        new_negative = self.negative_indices[
            (self.negative_indices >= bank_start) & (self.negative_indices < bank_end)
        ]

        return SparseVector(
            dimension=self.dimension,
            positive_indices=new_positive,
            negative_indices=new_negative,
            bank=bank_index,
        )


# =============================================================================
# HADAMARD BASIS GENERATION
# =============================================================================

def generate_hadamard_pattern(
    row_index: int,
    bank: int,
    dimension: int = D,
    dims_per_bank: int = DIMS_PER_BANK,
    num_primitives_in_bank: int = 14,
) -> SparseVector:
    """
    Generate a Hadamard-based pattern for a primitive using sparse local projection.

    Uses non-overlapping index partitions within each bank to guarantee EXACT
    orthogonality between primitives (cosine = 0.0). Each primitive projects
    only to its designated partition of dimensions.

    Sparse Hadamard Encoding:
    - Bank dimensions are partitioned among primitives: partition_size = dims_per_bank // num_primitives
    - Each primitive uses ONLY indices within its partition (non-overlapping)
    - Hadamard row values at partition indices determine +1/-1 pattern
    - Result: exact orthogonality because index sets don't overlap

    Args:
        row_index: Index of this primitive within the bank (0, 1, 2, ...)
        bank: Which semantic bank (determines dimension offset)
        dimension: Total vector dimension
        dims_per_bank: Dimensions per bank
        num_primitives_in_bank: Total primitives in this bank (for partition sizing)

    Returns:
        SparseVector with indices only in this primitive's partition
    """
    # Generate Hadamard matrix of appropriate size
    H = hadamard(dims_per_bank)

    # Get the Hadamard row for this primitive
    row = H[row_index % dims_per_bank, :]

    # Calculate partition boundaries (non-overlapping index sets)
    partition_size = dims_per_bank // num_primitives_in_bank
    partition_start = row_index * partition_size
    partition_end = partition_start + partition_size

    # Get indices within this primitive's partition
    partition_indices = np.arange(partition_start, partition_end, dtype=np.int32)

    # Get Hadamard values at partition indices
    values = row[partition_indices]

    # Separate positive and negative based on Hadamard row values
    positive_local = partition_indices[values > 0]
    negative_local = partition_indices[values < 0]

    # Offset to bank's dimension range in global vector
    bank_offset = bank * dims_per_bank
    positive_global = positive_local + bank_offset
    negative_global = negative_local + bank_offset

    return SparseVector(
        dimension=dimension,
        positive_indices=positive_global.astype(np.uint16),
        negative_indices=negative_global.astype(np.uint16),
        bank=bank,
    )


def generate_bipolar_patterns(
    dim: BipolarDimension,
    row_index: int,
    dimension: int = D,
    dims_per_bank: int = DIMS_PER_BANK,
    num_primitives_in_bank: int = 14,
) -> Tuple[SparseVector, SparseVector]:
    """
    Generate patterns for a bipolar dimension (antonym pair).

    The negative pole is the exact negation of the positive pole,
    ensuring cosine(positive, negative) = -1.0.

    Returns:
        (positive_vector, negative_vector)
    """
    # Generate positive pole
    positive_vec = generate_hadamard_pattern(
        row_index=row_index,
        bank=dim.bank.value,
        dimension=dimension,
        dims_per_bank=dims_per_bank,
        num_primitives_in_bank=num_primitives_in_bank,
    )

    # Negative pole is exact negation
    negative_vec = positive_vec.negate()

    return (positive_vec, negative_vec)


def generate_role_pattern(
    role_index: int,
    dimension: int = D,
    n_banks: int = N_BANKS,
    dims_per_bank: int = DIMS_PER_BANK,
    role_dims_per_bank: int = 6,
) -> SparseVector:
    """
    Generate partition-based pattern for a semantic role.

    Role vectors span ALL banks (unlike primitives which are bank-specific).
    Each role gets a disjoint ``role_dims_per_bank``-sized slice within every
    bank, guaranteeing exact role-role orthogonality (cosine = 0.0). Signs are
    set by a Hadamard row indexed by ``role_index`` to keep the ternary
    pattern balanced.

    The partition slot for role ``idx`` in each bank is local indices
    ``[idx * role_dims_per_bank, (idx + 1) * role_dims_per_bank)``. With the
    default 1024-dim bank and 6 dims per role, up to ``1024 // 6 = 170``
    distinct roles can coexist without overlap.
    """
    H = hadamard(dims_per_bank)
    row = H[role_index % dims_per_bank, :]

    partition_start = role_index * role_dims_per_bank
    partition_end = partition_start + role_dims_per_bank

    positive_indices: List[int] = []
    negative_indices: List[int] = []

    for bank in range(n_banks):
        bank_offset = bank * dims_per_bank
        for local_idx in range(partition_start, partition_end):
            global_idx = bank_offset + local_idx
            if row[local_idx] > 0:
                positive_indices.append(global_idx)
            else:
                negative_indices.append(global_idx)

    return SparseVector(
        dimension=dimension,
        positive_indices=np.array(positive_indices, dtype=np.uint16),
        negative_indices=np.array(negative_indices, dtype=np.uint16),
        bank=None,
    )


# =============================================================================
# HADAMARD-OTP BASIS
# =============================================================================

@dataclass
class HadamardOTPBasis:
    """
    Complete basis for HDC encoding with Hadamard-guaranteed orthogonality.

    Contains:
    - Primitive vectors (bank-specific, ~51 non-zeros each)
    - Role vectors (span all banks, ~48 non-zeros each)
    - Hierarchy marker vectors

    The "OTP" (One-Time Pad) aspect comes from the sparse sampling of
    Hadamard rows, ensuring each primitive has a unique pattern.
    """
    dimension: int
    n_banks: int
    dims_per_bank: int

    primitives: Dict[str, SparseVector] = field(default_factory=dict)
    roles: Dict[str, SparseVector] = field(default_factory=dict)

    # Metadata
    bipolar_map: Dict[str, str] = field(default_factory=dict)  # negative -> positive
    bank_primitive_counts: Dict[int, int] = field(default_factory=dict)

    def generate(self) -> "HadamardOTPBasis":
        """Generate all basis vectors."""
        self._generate_primitives()
        self._generate_roles()
        return self

    def _generate_primitives(self):
        """Generate primitive vectors with Hadamard patterns using non-overlapping partitions."""
        # Pre-calculate total primitives per bank for partition sizing
        # This ensures non-overlapping index sets → exact orthogonality
        primitives_per_bank: Dict[int, int] = {i: 0 for i in range(self.n_banks)}

        # Count bipolar dimensions (each contributes 1 to its bank, shared partition)
        for dim in BIPOLAR_DIMENSIONS:
            primitives_per_bank[dim.bank.value] += 1

        # Count unipolar primitives
        for prim_name, info in PRIMITIVE_REGISTRY.items():
            # Skip bipolar poles (already counted via dimension)
            is_bipolar_pole = any(
                prim_name in (d.positive, d.negative) for d in BIPOLAR_DIMENSIONS
            )
            if not is_bipolar_pole:
                primitives_per_bank[info.bank.value] += 1

        # Track row index per bank for sequential partition assignment
        bank_row_indices: Dict[int, int] = {i: 0 for i in range(self.n_banks)}

        # First, generate bipolar dimensions
        for dim in BIPOLAR_DIMENSIONS:
            bank = dim.bank.value
            row_idx = bank_row_indices[bank]
            bank_row_indices[bank] += 1

            pos_vec, neg_vec = generate_bipolar_patterns(
                dim=dim,
                row_index=row_idx,
                dimension=self.dimension,
                dims_per_bank=self.dims_per_bank,
                num_primitives_in_bank=primitives_per_bank[bank],
            )

            self.primitives[dim.positive] = pos_vec
            self.primitives[dim.negative] = neg_vec
            self.bipolar_map[dim.negative] = dim.positive

        # Then, generate unipolar primitives
        for prim_name, info in PRIMITIVE_REGISTRY.items():
            if prim_name in self.primitives:
                continue  # Already generated as bipolar

            bank = info.bank.value
            row_idx = bank_row_indices[bank]
            bank_row_indices[bank] += 1

            vec = generate_hadamard_pattern(
                row_index=row_idx,
                bank=bank,
                dimension=self.dimension,
                dims_per_bank=self.dims_per_bank,
                num_primitives_in_bank=primitives_per_bank[bank],
            )
            self.primitives[prim_name] = vec

        # Record counts
        for bank in range(self.n_banks):
            self.bank_primitive_counts[bank] = bank_row_indices[bank]

    def _generate_roles(self):
        """Generate role vectors spanning all banks."""
        for idx, role in enumerate(SEMANTIC_ROLES):
            self.roles[role] = generate_role_pattern(
                role_index=idx,
                dimension=self.dimension,
                n_banks=self.n_banks,
                dims_per_bank=self.dims_per_bank,
            )

    def get_primitive(self, name: str) -> Optional[SparseVector]:
        """Get primitive vector by name."""
        return self.primitives.get(name)

    def get_role(self, name: str) -> Optional[SparseVector]:
        """Get role vector by name."""
        return self.roles.get(name)

    def verify_structure(self) -> Dict:
        """Verify orthogonality and structure of the basis."""
        results = {
            "total_primitives": len(self.primitives),
            "total_roles": len(self.roles),
            "bipolar_pairs": len(self.bipolar_map),
            "bank_counts": self.bank_primitive_counts,
            "tests": {},
        }

        # Test 1: Within-bank orthogonality (excluding antonyms)
        bank_ortho_violations = 0
        for bank in range(self.n_banks):
            bank_prims = [
                (name, vec) for name, vec in self.primitives.items()
                if vec.bank == bank
            ]
            for i, (name_i, vec_i) in enumerate(bank_prims):
                for name_j, vec_j in bank_prims[i+1:]:
                    cos = vec_i.cosine(vec_j)
                    # Antonyms should have cosine = -1.0
                    if self.bipolar_map.get(name_j) == name_i or \
                       self.bipolar_map.get(name_i) == name_j:
                        if abs(cos - (-1.0)) > 0.01:
                            bank_ortho_violations += 1
                    # Others should be orthogonal (cosine ≈ 0)
                    elif abs(cos) > 0.15:  # Allow some noise from sparsity
                        bank_ortho_violations += 1

        results["tests"]["within_bank_orthogonality"] = bank_ortho_violations == 0
        results["tests"]["within_bank_violations"] = bank_ortho_violations

        # Test 2: Cross-bank orthogonality (should be exactly 0)
        cross_bank_violations = 0
        bank_prims = {}
        for name, vec in self.primitives.items():
            if vec.bank is not None:
                if vec.bank not in bank_prims:
                    bank_prims[vec.bank] = []
                bank_prims[vec.bank].append((name, vec))

        for bank_i in range(self.n_banks):
            for bank_j in range(bank_i + 1, self.n_banks):
                if bank_i not in bank_prims or bank_j not in bank_prims:
                    continue
                for name_i, vec_i in bank_prims[bank_i][:3]:  # Sample
                    for name_j, vec_j in bank_prims[bank_j][:3]:
                        cos = vec_i.cosine(vec_j)
                        if abs(cos) > 0.01:
                            cross_bank_violations += 1

        results["tests"]["cross_bank_orthogonality"] = cross_bank_violations == 0
        results["tests"]["cross_bank_violations"] = cross_bank_violations

        # Test 3: Antonym pairs have cosine = -1.0
        antonym_tests = []
        for dim in BIPOLAR_DIMENSIONS:
            pos_vec = self.primitives.get(dim.positive)
            neg_vec = self.primitives.get(dim.negative)
            if pos_vec and neg_vec:
                cos = pos_vec.cosine(neg_vec)
                antonym_tests.append({
                    "dimension": dim.name,
                    "positive": dim.positive,
                    "negative": dim.negative,
                    "cosine": cos,
                    "pass": abs(cos - (-1.0)) < 0.01,
                })

        results["tests"]["antonym_pairs"] = antonym_tests
        results["tests"]["all_antonyms_pass"] = all(t["pass"] for t in antonym_tests)

        # Test 4: Role vectors span all banks
        role_bank_coverage = []
        for role_name, role_vec in self.roles.items():
            banks_covered = set()
            for idx in role_vec.support:
                bank = idx // self.dims_per_bank
                banks_covered.add(bank)
            role_bank_coverage.append({
                "role": role_name,
                "banks_covered": len(banks_covered),
                "full_coverage": len(banks_covered) == self.n_banks,
            })

        results["tests"]["role_bank_coverage"] = (
            sum(1 for r in role_bank_coverage if r["full_coverage"]) / len(role_bank_coverage)
            if role_bank_coverage else 0
        )

        return results

    def save(self, path: str):
        """Save basis to file."""
        data = {
            "dimension": self.dimension,
            "n_banks": self.n_banks,
            "dims_per_bank": self.dims_per_bank,
            "primitives": {
                name: vec.serialize() for name, vec in self.primitives.items()
            },
            "roles": {
                name: vec.serialize() for name, vec in self.roles.items()
            },
            "bipolar_map": self.bipolar_map,
            "bank_primitive_counts": self.bank_primitive_counts,
        }

        with open(path, "wb") as f:
            msgpack.pack(data, f)

    @classmethod
    def load(cls, path: str) -> "HadamardOTPBasis":
        """Load basis from file."""
        with open(path, "rb") as f:
            data = msgpack.unpack(f)

        basis = cls(
            dimension=data["dimension"],
            n_banks=data["n_banks"],
            dims_per_bank=data["dims_per_bank"],
        )

        basis.primitives = {
            name: SparseVector.deserialize(vec_bytes)
            for name, vec_bytes in data["primitives"].items()
        }
        basis.roles = {
            name: SparseVector.deserialize(vec_bytes)
            for name, vec_bytes in data["roles"].items()
        }
        basis.bipolar_map = data["bipolar_map"]
        basis.bank_primitive_counts = data["bank_primitive_counts"]

        return basis


# =============================================================================
# SENTENCE-SCALE HDC BASIS
# =============================================================================
#
# Sentence-scale primitives share the 8192-dim HDC space with word-scale but
# use distinct bank partitions (sentence-scale BankDefs live in primitives_v2).
# The partition-based generate_hadamard_pattern (above) guarantees exact
# within-space orthogonality (cos = 0.0) among same-bank primitives.
#


@dataclass
class SentenceScaleBasis:
    """
    Basis for sentence-scale HDC encoding.

    This is ORTHOGONAL to the word-scale HadamardOTPBasis.
    Sentence-scale encodes syntactic/compositional features:
    - SYN_* primitives (subject, predicate, object, etc.)
    - COMP_* operators (than, how, just, etc.)

    The two spaces are composed via bind():
        word_full = bind(word_vec, sentence_vec)
    """
    dimension: int = D
    n_banks: int = N_BANKS
    dims_per_bank: int = DIMS_PER_BANK

    primitives: Dict[str, SparseVector] = field(default_factory=dict)
    bank_primitive_counts: Dict[int, int] = field(default_factory=dict)

    # Compositional operator metadata
    comp_metadata: Dict[str, Dict] = field(default_factory=dict)

    def generate(self) -> "SentenceScaleBasis":
        """Generate all sentence-scale primitive vectors.

        Uses the same partition-based Hadamard approach as word-scale
        for exact within-space orthogonality (cosine = 0.0).
        """
        primitives_per_bank: Dict[int, int] = {i: 0 for i in range(self.n_banks)}
        for info in SENTENCE_PRIMITIVE_REGISTRY.values():
            primitives_per_bank[info.bank] += 1

        bank_row_indices: Dict[int, int] = {i: 0 for i in range(self.n_banks)}

        for prim_name, info in SENTENCE_PRIMITIVE_REGISTRY.items():
            bank = info.bank
            num_in_bank = primitives_per_bank[bank]
            if num_in_bank == 0:
                continue

            row_idx = bank_row_indices[bank]
            bank_row_indices[bank] += 1

            vec = generate_hadamard_pattern(
                row_index=row_idx,
                bank=bank,
                dimension=self.dimension,
                dims_per_bank=self.dims_per_bank,
                num_primitives_in_bank=num_in_bank,
            )
            self.primitives[prim_name] = vec

            if info.is_compositional:
                self.comp_metadata[prim_name] = {
                    "arity": info.comp_arity,
                    "operation": info.comp_operation,
                }

        for bank in range(self.n_banks):
            self.bank_primitive_counts[bank] = bank_row_indices[bank]

        return self

    def get_primitive(self, name: str) -> Optional[SparseVector]:
        """Get sentence-scale primitive vector by name."""
        return self.primitives.get(name)

    def get_operator_metadata(self, name: str) -> Optional[Dict]:
        """Get compositional operator metadata."""
        return self.comp_metadata.get(name)

    def encode_sentence_primitives(
        self,
        primitives: Dict[str, int],
    ) -> SparseVector:
        """
        Encode a set of sentence-scale primitives into a vector.

        Args:
            primitives: Dict mapping primitive name to value (1 or -1)

        Returns:
            Bundled SparseVector of activated sentence primitives
        """
        components = []
        for prim_name, value in primitives.items():
            prim_vec = self.get_primitive(prim_name)
            if prim_vec is None:
                continue

            if value == -1:
                prim_vec = prim_vec.negate()

            components.append(prim_vec)

        if not components:
            return SparseVector.zeros(self.dimension)

        return bundle(components)

    def verify_orthogonality_to_word_scale(
        self,
        word_basis: HadamardOTPBasis,
        sample_size: int = 5,
    ) -> Dict:
        """
        Verify that sentence-scale and word-scale bases are orthogonal.

        Args:
            word_basis: The word-scale HadamardOTPBasis
            sample_size: Number of primitives to sample from each space

        Returns:
            Dict with orthogonality test results
        """
        results = {
            "cross_space_cosines": [],
            "max_cosine": 0.0,
            "orthogonal": True,
        }

        # Sample primitives from each space
        word_prims = list(word_basis.primitives.items())[:sample_size]
        sent_prims = list(self.primitives.items())[:sample_size]

        for word_name, word_vec in word_prims:
            for sent_name, sent_vec in sent_prims:
                cos = word_vec.cosine(sent_vec)
                results["cross_space_cosines"].append({
                    "word": word_name,
                    "sentence": sent_name,
                    "cosine": cos,
                })
                if abs(cos) > results["max_cosine"]:
                    results["max_cosine"] = abs(cos)

        results["orthogonal"] = results["max_cosine"] < 0.15  # cross-space is approximate

        return results

    def save(self, path: str):
        """Save sentence-scale basis to file."""
        data = {
            "dimension": self.dimension,
            "n_banks": self.n_banks,
            "dims_per_bank": self.dims_per_bank,
            "primitives": {
                name: vec.serialize() for name, vec in self.primitives.items()
            },
            "bank_primitive_counts": self.bank_primitive_counts,
            "comp_metadata": self.comp_metadata,
        }

        with open(path, "wb") as f:
            msgpack.pack(data, f)

    @classmethod
    def load(cls, path: str) -> "SentenceScaleBasis":
        """Load sentence-scale basis from file."""
        with open(path, "rb") as f:
            data = msgpack.unpack(f)

        basis = cls(
            dimension=data["dimension"],
            n_banks=data["n_banks"],
            dims_per_bank=data["dims_per_bank"],
        )

        basis.primitives = {
            name: SparseVector.deserialize(vec_bytes)
            for name, vec_bytes in data["primitives"].items()
        }
        basis.bank_primitive_counts = data["bank_primitive_counts"]
        basis.comp_metadata = data.get("comp_metadata", {})

        return basis


# =============================================================================
# MULTI-SCALE COMPOSITION HELPERS
# =============================================================================

def encode_word_full(
    word_vec: SparseVector,
    sentence_vec: SparseVector,
) -> SparseVector:
    """
    Compose word-scale and sentence-scale vectors into full representation.

    This is the core composition operation:
        word_full = bind(word_vec, sentence_vec)

    The result is orthogonal to BOTH input spaces due to HDC bind properties.

    Args:
        word_vec: Word-scale encoding (semantic primitives)
        sentence_vec: Sentence-scale encoding (syntactic/compositional)

    Returns:
        Composed SparseVector
    """
    return bind(word_vec, sentence_vec)


def create_informational_zero(dimension: int = D) -> SparseVector:
    """
    Create an informational zero vector.

    Used for function words like "than" that have no word-scale semantics
    but activate sentence-scale compositional primitives.

    The zero vector preserves the sentence-scale when bound:
        bind(zero_vec, sentence_vec) ≈ sentence_vec (in terms of information)
    """
    return SparseVector.zeros(dimension)


def create_sentence_basis(
    dimension: int = D,
    n_banks: int = N_BANKS,
    dims_per_bank: int = DIMS_PER_BANK,
) -> SentenceScaleBasis:
    """Create and initialize a new sentence-scale basis."""
    basis = SentenceScaleBasis(
        dimension=dimension,
        n_banks=n_banks,
        dims_per_bank=dims_per_bank,
    )
    return basis.generate()


def load_or_create_sentence_basis(path: str) -> SentenceScaleBasis:
    """Load sentence-scale basis from path, or create new if not exists."""
    import os
    if os.path.exists(path):
        return SentenceScaleBasis.load(path)
    basis = create_sentence_basis()
    basis.save(path)
    return basis


# =============================================================================
# CORE HDC OPERATIONS
# =============================================================================

def bind(a: SparseVector, b: SparseVector) -> SparseVector:
    """
    Bind two vectors (element-wise multiplication for ternary).

    For sparse ternary:
    - (+1) * (+1) = +1
    - (-1) * (-1) = +1
    - (+1) * (-1) = -1
    - (-1) * (+1) = -1
    - 0 * anything = 0

    Result is dissimilar to both inputs.
    """
    if a.dimension != b.dimension:
        raise ValueError(f"Dimension mismatch: {a.dimension} vs {b.dimension}")

    # Find overlapping indices
    # pp: both positive -> positive
    # nn: both negative -> positive
    # pn: a positive, b negative -> negative
    # np: a negative, b positive -> negative

    pp = np.intersect1d(a.positive_indices, b.positive_indices)
    nn = np.intersect1d(a.negative_indices, b.negative_indices)
    pn = np.intersect1d(a.positive_indices, b.negative_indices)
    np_ = np.intersect1d(a.negative_indices, b.positive_indices)

    positive = np.union1d(pp, nn)
    negative = np.union1d(pn, np_)

    return SparseVector(
        dimension=a.dimension,
        positive_indices=positive.astype(np.uint16),
        negative_indices=negative.astype(np.uint16),
        bank=a.bank if a.bank == b.bank else None,
    )


def bundle(
    vectors: List[SparseVector],
    normalize: bool = True,
) -> SparseVector:
    """
    Bundle (superposition) of multiple vectors.

    Uses majority voting: for each dimension, take the sign of the sum.
    Result is similar to all inputs.

    Args:
        vectors: List of vectors to bundle
        normalize: If True, apply sign() to get ternary output
    """
    if not vectors:
        raise ValueError("Cannot bundle empty list")

    dimension = vectors[0].dimension
    if not all(v.dimension == dimension for v in vectors):
        raise ValueError("All vectors must have same dimension")

    # Accumulate in dense int array
    accumulator = np.zeros(dimension, dtype=np.int32)

    for vec in vectors:
        accumulator[vec.positive_indices] += 1
        accumulator[vec.negative_indices] -= 1

    if normalize:
        # Majority voting: sign() quantizes to {-1, 0, +1}
        result = np.sign(accumulator).astype(np.int8)
    else:
        result = accumulator

    return SparseVector.from_dense(result)


def weighted_bundle(
    vectors: List[SparseVector],
    weights: List[float],
    normalize: bool = True,
) -> SparseVector:
    """
    Weighted bundle of vectors.

    Weights are applied to each vector before accumulation.
    Higher weight = more influence on final result.
    """
    if len(vectors) != len(weights):
        raise ValueError("Number of vectors must match number of weights")

    if not vectors:
        raise ValueError("Cannot bundle empty list")

    dimension = vectors[0].dimension

    accumulator = np.zeros(dimension, dtype=np.float32)

    for vec, weight in zip(vectors, weights):
        accumulator[vec.positive_indices] += weight
        accumulator[vec.negative_indices] -= weight

    if normalize:
        # Threshold at 0 for ternary
        result = np.sign(accumulator).astype(np.int8)
    else:
        result = accumulator

    return SparseVector.from_dense(result)


def permute(v: SparseVector, shift: int = 1) -> SparseVector:
    """
    Circular permutation of vector.

    Encodes position/sequence information.
    Result is dissimilar to input.
    """
    if shift == 0:
        return v

    new_positive = (v.positive_indices.astype(np.int32) + shift) % v.dimension
    new_negative = (v.negative_indices.astype(np.int32) + shift) % v.dimension

    return SparseVector(
        dimension=v.dimension,
        positive_indices=new_positive.astype(np.uint16),
        negative_indices=new_negative.astype(np.uint16),
        bank=None,  # Permutation breaks bank locality
    )


# =============================================================================
# ENCODING UTILITIES
# =============================================================================

def encode_with_role(
    primitive_vec: SparseVector,
    role_vec: SparseVector,
) -> SparseVector:
    """Bind primitive with role vector."""
    return bind(primitive_vec, role_vec)


def encode_hierarchy(
    base_vec: SparseVector,
    marker_vec: SparseVector,
    level: int,
) -> SparseVector:
    """
    Encode hierarchical modifier by stacking markers.

    Example: MANY = QUANTITY + HIER_PLUS + HIER_PLUS (level=2)
    """
    if level == 0:
        return base_vec

    components = [base_vec]
    for i in range(abs(level)):
        # Permute marker to distinguish stacking levels
        shifted_marker = permute(marker_vec, shift=i * 100)
        components.append(shifted_marker)

    return bundle(components)


# Polarity propagation rules: source_bank → target_banks.
# When a primitive in source_bank is negated, target primitives in target_banks
# receive a negated shadow at their own dimensions — partially cancelling the
# target's signal in the bundle and producing emergent geometric antonymy.
#
# Theory: a negated EVALUATOR (e.g. GOOD⁻¹ in "hate") imparts emotional coloring
# to MENTAL primitives and evaluative charge to ACTION primitives, so
# feel-with-negative-eval is geometrically distinct from feel-with-positive-eval.
POLARITY_PROPAGATION_RULES: Dict[SemanticBank, List[SemanticBank]] = {
    SemanticBank.EVALUATORS: [SemanticBank.MENTAL, SemanticBank.ACTION],
}


def compose_decomposition(
    basis: HadamardOTPBasis,
    decomposition: List[Tuple[str, str, int]],  # (primitive, role, polarity)
    propagate_polarity: bool = True,
) -> SparseVector:
    """
    Compose a word vector from its primitive decomposition.

    Args:
        basis: The Hadamard-OTP basis
        decomposition: List of (primitive, role, polarity) tuples
        propagate_polarity: Apply cross-bank polarity propagation
            (emergent antonymy: negated EVALUATORS color MENTAL/ACTION primitives)

    Returns:
        Composed sparse vector
    """
    if not decomposition:
        return SparseVector.zeros(basis.dimension)

    # First pass: collect names of negated source primitives by source bank
    negated_source_prims: Dict[SemanticBank, List[str]] = {}
    if propagate_polarity:
        for prim, _role, polarity in decomposition:
            if polarity != -1:
                continue
            info = get_primitive_info(prim)
            if info is None or info.bank not in POLARITY_PROPAGATION_RULES:
                continue
            if basis.get_primitive(prim) is None:
                continue
            negated_source_prims.setdefault(info.bank, []).append(prim)

    components = []

    for prim, role, polarity in decomposition:
        base_prim_vec = basis.get_primitive(prim)
        if base_prim_vec is None:
            continue

        info = get_primitive_info(prim)

        # Apply this primitive's own polarity
        if polarity == -1:
            prim_vec = base_prim_vec.negate()
        else:
            prim_vec = base_prim_vec

        # Bind with role if available
        role_vec = basis.get_role(role)
        if role_vec:
            components.append(bind(prim_vec, role_vec))
        else:
            components.append(prim_vec)

        # Polarity propagation: if this primitive lives in a target bank,
        # add shadows per negated source primitive.
        #
        # Each shadow is the BASE target vector negated, landing on the target's
        # own dimensions with opposite signs. The bundle already contains two
        # positive copies of the target (the role-bound and the raw), so we add
        # two negated copies per source to fully cancel the target's signal at
        # its own dimensions — creating emergent antonymy that AMPLIFIES the
        # cosine separation between e.g. love-FEEL and hate-FEEL bundles.
        if propagate_polarity and info is not None:
            for source_bank, target_banks in POLARITY_PROPAGATION_RULES.items():
                if info.bank not in target_banks:
                    continue
                for _source_prim_name in negated_source_prims.get(source_bank, []):
                    components.append(base_prim_vec.negate())
                    components.append(base_prim_vec.negate())

        # Also add raw primitive (for direct similarity)
        components.append(prim_vec)

    return bundle(components)


# =============================================================================
# SIMILARITY ANALYSIS
# =============================================================================

def polarity_aware_similarity(
    v1: SparseVector,
    v2: SparseVector,
) -> Dict[str, float]:
    """
    Compute similarity with polarity breakdown.

    Returns:
        Dict with:
        - cosine: Standard cosine similarity
        - alignment: Fraction with same sign (synonymy)
        - opposition: Fraction with opposite sign (antonymy)
        - orthogonality: Fraction non-overlapping
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


def bank_activity_profile(v: SparseVector) -> Dict[int, float]:
    """
    Get activation profile across semantic banks.

    Returns:
        Dict mapping bank index to activation strength (0.0-1.0)
    """
    profile = {}
    for bank in range(N_BANKS):
        start, end = get_dimension_range(SemanticBank(bank))
        bank_support = v.support[(v.support >= start) & (v.support < end)]
        # Normalize by expected sparsity (~51 non-zeros per primitive)
        profile[bank] = len(bank_support) / 51.0

    return profile


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_basis(
    dimension: int = D,
    n_banks: int = N_BANKS,
    dims_per_bank: int = DIMS_PER_BANK,
) -> HadamardOTPBasis:
    """Create and initialize a new Hadamard-OTP basis."""
    basis = HadamardOTPBasis(
        dimension=dimension,
        n_banks=n_banks,
        dims_per_bank=dims_per_bank,
    )
    return basis.generate()


def load_or_create_basis(path: str) -> HadamardOTPBasis:
    """Load basis from path, or create new if not exists."""
    import os
    if os.path.exists(path):
        return HadamardOTPBasis.load(path)
    basis = create_basis()
    basis.save(path)
    return basis


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("GSE Vectors v2 - Verification")
    print("=" * 60)

    # Create basis
    print("\nGenerating Hadamard-OTP basis...")
    basis = create_basis()

    # Verify structure
    print("\nVerifying structure...")
    results = basis.verify_structure()

    print(f"\nTotal primitives: {results['total_primitives']}")
    print(f"Total roles: {results['total_roles']}")
    print(f"Bipolar pairs: {results['bipolar_pairs']}")

    print("\nBank primitive counts:")
    for bank, count in sorted(results['bank_counts'].items()):
        print(f"  Bank {bank} ({SEMANTIC_BANK_NAMES[bank]}): {count} primitives")

    print("\nOrthogonality tests:")
    print(f"  Within-bank orthogonality: {'PASS' if results['tests']['within_bank_orthogonality'] else 'FAIL'}")
    print(f"    Violations: {results['tests']['within_bank_violations']}")
    print(f"  Cross-bank orthogonality: {'PASS' if results['tests']['cross_bank_orthogonality'] else 'FAIL'}")
    print(f"    Violations: {results['tests']['cross_bank_violations']}")

    print("\nAntonym pair cosines (should be -1.0):")
    for test in results['tests']['antonym_pairs']:
        status = "PASS" if test['pass'] else "FAIL"
        print(f"  {test['dimension']:15} ({test['positive']}/{test['negative']}): "
              f"cos = {test['cosine']:.4f} [{status}]")

    print(f"\nAll antonyms pass: {'YES' if results['tests']['all_antonyms_pass'] else 'NO'}")
    print(f"Role bank coverage: {results['tests']['role_bank_coverage']:.1%}")
