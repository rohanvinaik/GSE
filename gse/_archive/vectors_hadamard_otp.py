# gse/vectors_hadamard_otp.py
"""
Hadamard-OTP Vector Architecture for GSE

Synthesizes insights from:
1. OTP Theory: Informational zeros, geometric encoding
2. GenomeVault HDC: Multi-bank structure, Hadamard patterns, 3D storage
3. GSE Requirements: Primitives, roles, composition

Architecture:
- D = 8,192 dimensions (2^13, optimal for Hadamard)
- 8 semantic banks × 1,024 dims each
- Hadamard patterns guarantee orthogonality within banks
- Cross-bank roles guarantee non-empty binding
- Antonyms are exact negations (cosine = -1.0)

Key Properties:
- Perfect orthogonality (Hadamard, not random)
- Semantic structure (banks = NSM categories)
- Guaranteed binding (~51 non-zeros)
- Two-level decode (bank → primitive)
- Efficient 3D storage with compression
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Set
from enum import IntEnum
import msgpack

# Lazy import for Hadamard matrix
_hadamard_cache = {}


def get_hadamard(n: int) -> np.ndarray:
    """Get or generate Hadamard matrix of size n."""
    if n not in _hadamard_cache:
        from scipy.linalg import hadamard
        _hadamard_cache[n] = hadamard(n)
    return _hadamard_cache[n]


# =============================================================================
# CONFIGURATION
# =============================================================================

D = 8192  # Total dimensions (2^13)
N_BANKS = 8  # Semantic banks
DIMS_PER_BANK = D // N_BANKS  # 1024

N_ROLES = 20
ROLE_DIMS_PER_BANK = DIMS_PER_BANK // N_ROLES  # 51 (with 4 leftover)


class SemanticBank(IntEnum):
    """Semantic categories as banks (following NSM)."""
    SUBSTANTIVES = 0   # I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY, KIND, PART
    DETERMINERS = 1    # THIS, SAME, OTHER, ONE, TWO, SOME, ALL, MUCH, LITTLE
    EVALUATORS = 2     # GOOD, BAD, BIG, SMALL, VERY, MORE, LIKE
    MENTAL = 3         # THINK, KNOW, WANT, FEEL, SEE, HEAR
    ACTION = 4         # SAY, DO, HAPPEN, MOVE, BE, HAVE, EXIST, LIVE, DIE, TRUE, WORDS
    TEMPORAL = 5       # WHEN, NOW, BEFORE, AFTER, LONG_TIME, SHORT_TIME, MOMENT
    SPATIAL = 6        # WHERE, HERE, ABOVE, BELOW, FAR, NEAR, INSIDE, SIDE, TOUCH
    LOGICAL = 7        # NOT, MAYBE, CAN, BECAUSE, IF


# Primitive to bank assignment
PRIMITIVE_BANKS: Dict[str, SemanticBank] = {
    # Bank 0: Substantives (things, persons)
    "I": SemanticBank.SUBSTANTIVES,
    "YOU": SemanticBank.SUBSTANTIVES,
    "SOMEONE": SemanticBank.SUBSTANTIVES,
    "SOMETHING": SemanticBank.SUBSTANTIVES,
    "PEOPLE": SemanticBank.SUBSTANTIVES,
    "BODY": SemanticBank.SUBSTANTIVES,
    "KIND": SemanticBank.SUBSTANTIVES,
    "PART": SemanticBank.SUBSTANTIVES,
    
    # Bank 1: Determiners/Quantifiers
    "THIS": SemanticBank.DETERMINERS,
    "SAME": SemanticBank.DETERMINERS,
    "OTHER": SemanticBank.DETERMINERS,
    "ONE": SemanticBank.DETERMINERS,
    "TWO": SemanticBank.DETERMINERS,
    "SOME": SemanticBank.DETERMINERS,
    "ALL": SemanticBank.DETERMINERS,
    "MUCH": SemanticBank.DETERMINERS,
    "LITTLE": SemanticBank.DETERMINERS,
    
    # Bank 2: Evaluators
    "GOOD": SemanticBank.EVALUATORS,
    "BAD": SemanticBank.EVALUATORS,
    "BIG": SemanticBank.EVALUATORS,
    "SMALL": SemanticBank.EVALUATORS,
    "VERY": SemanticBank.EVALUATORS,
    "MORE": SemanticBank.EVALUATORS,
    "LIKE": SemanticBank.EVALUATORS,
    
    # Bank 3: Mental predicates
    "THINK": SemanticBank.MENTAL,
    "KNOW": SemanticBank.MENTAL,
    "WANT": SemanticBank.MENTAL,
    "FEEL": SemanticBank.MENTAL,
    "SEE": SemanticBank.MENTAL,
    "HEAR": SemanticBank.MENTAL,
    
    # Bank 4: Action/State predicates
    "SAY": SemanticBank.ACTION,
    "WORDS": SemanticBank.ACTION,
    "TRUE": SemanticBank.ACTION,
    "DO": SemanticBank.ACTION,
    "HAPPEN": SemanticBank.ACTION,
    "MOVE": SemanticBank.ACTION,
    "BE": SemanticBank.ACTION,
    "HAVE": SemanticBank.ACTION,
    "EXIST": SemanticBank.ACTION,
    "LIVE": SemanticBank.ACTION,
    "DIE": SemanticBank.ACTION,
    
    # Bank 5: Temporal
    "WHEN": SemanticBank.TEMPORAL,
    "NOW": SemanticBank.TEMPORAL,
    "BEFORE": SemanticBank.TEMPORAL,
    "AFTER": SemanticBank.TEMPORAL,
    "LONG_TIME": SemanticBank.TEMPORAL,
    "SHORT_TIME": SemanticBank.TEMPORAL,
    "MOMENT": SemanticBank.TEMPORAL,
    
    # Bank 6: Spatial
    "WHERE": SemanticBank.SPATIAL,
    "HERE": SemanticBank.SPATIAL,
    "ABOVE": SemanticBank.SPATIAL,
    "BELOW": SemanticBank.SPATIAL,
    "FAR": SemanticBank.SPATIAL,
    "NEAR": SemanticBank.SPATIAL,
    "INSIDE": SemanticBank.SPATIAL,
    "SIDE": SemanticBank.SPATIAL,
    "TOUCH": SemanticBank.SPATIAL,
    
    # Bank 7: Logical/Relational
    "NOT": SemanticBank.LOGICAL,
    "MAYBE": SemanticBank.LOGICAL,
    "CAN": SemanticBank.LOGICAL,
    "BECAUSE": SemanticBank.LOGICAL,
    "IF": SemanticBank.LOGICAL,
}

# Antonym pairs - these get exact negation
ANTONYM_PAIRS = [
    ("GOOD", "BAD"),
    ("BIG", "SMALL"),
    ("MUCH", "LITTLE"),
    ("LONG_TIME", "SHORT_TIME"),
    ("FAR", "NEAR"),
    ("ABOVE", "BELOW"),
    ("BEFORE", "AFTER"),
    ("LIVE", "DIE"),
]


# =============================================================================
# SPARSE VECTOR CLASS
# =============================================================================

@dataclass
class SparseVector:
    """Sparse ternary vector with bank metadata."""
    dimension: int
    positive_indices: np.ndarray
    negative_indices: np.ndarray
    bank: Optional[int] = None
    
    def __post_init__(self):
        if not isinstance(self.positive_indices, np.ndarray):
            self.positive_indices = np.array(self.positive_indices, dtype=np.uint16)
        if not isinstance(self.negative_indices, np.ndarray):
            self.negative_indices = np.array(self.negative_indices, dtype=np.uint16)
        self.positive_indices = np.sort(self.positive_indices)
        self.negative_indices = np.sort(self.negative_indices)
    
    def __eq__(self, other):
        if not isinstance(other, SparseVector):
            return NotImplemented
        return (self.dimension == other.dimension and
                np.array_equal(self.positive_indices, other.positive_indices) and
                np.array_equal(self.negative_indices, other.negative_indices))
    
    @property
    def nnz(self) -> int:
        return len(self.positive_indices) + len(self.negative_indices)
    
    @property
    def sparsity(self) -> float:
        return self.nnz / self.dimension
    
    @property
    def support(self) -> np.ndarray:
        return np.union1d(self.positive_indices, self.negative_indices)
    
    def to_dense(self) -> np.ndarray:
        v = np.zeros(self.dimension, dtype=np.int8)
        v[self.positive_indices] = 1
        v[self.negative_indices] = -1
        return v
    
    @classmethod
    def from_dense(cls, v: np.ndarray, bank: Optional[int] = None) -> 'SparseVector':
        return cls(
            dimension=len(v),
            positive_indices=np.where(v > 0)[0].astype(np.uint16),
            negative_indices=np.where(v < 0)[0].astype(np.uint16),
            bank=bank
        )
    
    @classmethod
    def zeros(cls, dimension: int) -> 'SparseVector':
        return cls(dimension, np.array([], dtype=np.uint16), np.array([], dtype=np.uint16))
    
    def dot(self, other: 'SparseVector') -> int:
        pp = len(np.intersect1d(self.positive_indices, other.positive_indices, assume_unique=True))
        nn = len(np.intersect1d(self.negative_indices, other.negative_indices, assume_unique=True))
        pn = len(np.intersect1d(self.positive_indices, other.negative_indices, assume_unique=True))
        np_ = len(np.intersect1d(self.negative_indices, other.positive_indices, assume_unique=True))
        return pp + nn - pn - np_
    
    def cosine(self, other: 'SparseVector') -> float:
        dot = self.dot(other)
        norm_self = np.sqrt(self.nnz)
        norm_other = np.sqrt(other.nnz)
        if norm_self * norm_other == 0:
            return 0.0
        return dot / (norm_self * norm_other)
    
    def serialize(self) -> bytes:
        return msgpack.packb({
            'd': self.dimension,
            'p': self.positive_indices.tobytes(),
            'n': self.negative_indices.tobytes(),
            'b': self.bank
        })
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'SparseVector':
        obj = msgpack.unpackb(data)
        return cls(
            dimension=obj['d'],
            positive_indices=np.frombuffer(obj['p'], dtype=np.uint16).copy(),
            negative_indices=np.frombuffer(obj['n'], dtype=np.uint16).copy(),
            bank=obj.get('b')
        )


# =============================================================================
# HADAMARD PATTERN GENERATION
# =============================================================================

def hadamard_row(idx: int, size: int) -> np.ndarray:
    """
    Get a row from the Hadamard matrix.
    
    Hadamard matrices have the property H @ H.T = n*I,
    meaning all rows are mutually orthogonal.
    """
    H = get_hadamard(size)
    return H[idx % size, :].astype(np.int8)


def generate_primitive_vector(
    name: str,
    bank: int,
    idx_in_bank: int,
    is_antonym_negative: bool = False,
    dimension: int = D,
    dims_per_bank: int = DIMS_PER_BANK
) -> SparseVector:
    """
    Generate primitive vector using Hadamard pattern in its bank.
    
    Args:
        name: Primitive name (for documentation)
        bank: Which semantic bank (0-7)
        idx_in_bank: Index within bank (for Hadamard row selection)
        is_antonym_negative: If True, negate the pattern (for antonym pairs)
        dimension: Total vector dimension
        dims_per_bank: Dimensions per bank
    
    Returns:
        SparseVector with non-zeros only in this bank's dimensions
    """
    vec = np.zeros(dimension, dtype=np.int8)
    
    bank_start = bank * dims_per_bank
    bank_end = bank_start + dims_per_bank
    
    # Get Hadamard pattern
    pattern = hadamard_row(idx_in_bank, dims_per_bank)
    
    # Negate for antonym's negative member
    if is_antonym_negative:
        pattern = -pattern
    
    vec[bank_start:bank_end] = pattern
    
    return SparseVector.from_dense(vec, bank=bank)


def generate_role_vector(
    role_idx: int,
    dimension: int = D,
    n_banks: int = N_BANKS,
    dims_per_bank: int = DIMS_PER_BANK,
    role_dims_per_bank: int = ROLE_DIMS_PER_BANK
) -> SparseVector:
    """
    Generate role vector spanning ALL banks.

    Each role is a "column" that slices through all semantic banks,
    ensuring binding with ANY primitive produces non-empty result.

    Args:
        role_idx: Role index (0 to N_ROLES-1)
        dimension: Total vector dimension
        n_banks: Number of semantic banks
        dims_per_bank: Dimensions per bank
        role_dims_per_bank: Role dimensions within each bank

    Returns:
        SparseVector with non-zeros in role's column across all banks
    """
    vec = np.zeros(dimension, dtype=np.int8)

    # Get a Hadamard matrix of bank size (1024 = 2^10, power of 2)
    # Then slice out the role's portion
    H = get_hadamard(dims_per_bank)

    for bank in range(n_banks):
        bank_start = bank * dims_per_bank
        role_start = bank_start + role_idx * role_dims_per_bank
        role_end = min(role_start + role_dims_per_bank, bank_start + dims_per_bank)

        if role_end <= role_start:
            continue

        pattern_size = role_end - role_start

        # Use different Hadamard row per bank for uniqueness
        # Slice from the full bank-sized Hadamard matrix
        row_idx = (bank + role_idx * n_banks) % dims_per_bank
        pattern = H[row_idx, role_idx * role_dims_per_bank : role_idx * role_dims_per_bank + pattern_size]
        vec[role_start:role_end] = np.sign(pattern).astype(np.int8)

    return SparseVector.from_dense(vec)


# =============================================================================
# OPERATIONS
# =============================================================================

def bind(a: SparseVector, b: SparseVector) -> SparseVector:
    """
    Binding operation: element-wise multiplication.
    
    For Hadamard-OTP vectors:
    - Primitive (single bank) × Role (all banks) → non-zeros in primitive's bank only
    - Result has ~51 non-zeros (role_dims_per_bank)
    """
    assert a.dimension == b.dimension
    
    new_pos = np.union1d(
        np.intersect1d(a.positive_indices, b.positive_indices, assume_unique=True),
        np.intersect1d(a.negative_indices, b.negative_indices, assume_unique=True)
    )
    
    new_neg = np.union1d(
        np.intersect1d(a.positive_indices, b.negative_indices, assume_unique=True),
        np.intersect1d(a.negative_indices, b.positive_indices, assume_unique=True)
    )
    
    # Inherit bank from the more specific vector (primitive)
    bank = a.bank if a.bank is not None else b.bank
    
    return SparseVector(
        dimension=a.dimension,
        positive_indices=new_pos.astype(np.uint16),
        negative_indices=new_neg.astype(np.uint16),
        bank=bank
    )


def bundle(vectors: List[SparseVector], normalize: bool = True) -> SparseVector:
    """
    Bundling operation: element-wise sum with majority vote.
    
    This is the accumulation + sign paradigm from GenomeVault:
    1. Accumulate as int32 to prevent overflow
    2. Apply sign() to quantize to ternary
    3. Magnitude is recovered at query time
    """
    if not vectors:
        raise ValueError("Cannot bundle empty list")
    
    dimension = vectors[0].dimension
    accumulator = np.zeros(dimension, dtype=np.int32)
    
    for v in vectors:
        accumulator[v.positive_indices] += 1
        accumulator[v.negative_indices] -= 1
    
    if normalize:
        result = np.sign(accumulator).astype(np.int8)
    else:
        result = accumulator.astype(np.int8)
    
    return SparseVector.from_dense(result)


def permute(v: SparseVector, n: int = 1) -> SparseVector:
    """Circular permutation for position encoding."""
    d = v.dimension
    new_pos = ((v.positive_indices.astype(np.int32) + n) % d).astype(np.uint16)
    new_neg = ((v.negative_indices.astype(np.int32) + n) % d).astype(np.uint16)
    
    return SparseVector(
        dimension=d,
        positive_indices=np.sort(new_pos),
        negative_indices=np.sort(new_neg),
        bank=v.bank
    )


# =============================================================================
# DECODING (Two-Level: Bank → Primitive)
# =============================================================================

def get_bank_magnitude(v: SparseVector, bank: int, dims_per_bank: int = DIMS_PER_BANK) -> float:
    """Get magnitude of signal in a specific bank."""
    bank_start = bank * dims_per_bank
    bank_end = bank_start + dims_per_bank
    
    # Count non-zeros in bank range
    support = v.support
    in_bank = np.sum((support >= bank_start) & (support < bank_end))
    
    return float(in_bank)


def decode_dominant_bank(v: SparseVector, n_banks: int = N_BANKS, dims_per_bank: int = DIMS_PER_BANK) -> int:
    """Find which bank has the strongest signal."""
    magnitudes = [get_bank_magnitude(v, bank, dims_per_bank) for bank in range(n_banks)]
    return int(np.argmax(magnitudes))


def get_bank_similarities(
    v: SparseVector,
    bank: int,
    primitive_vectors: Dict[str, SparseVector],
    primitive_to_bank: Dict[str, int],
    dims_per_bank: int = DIMS_PER_BANK
) -> Dict[str, float]:
    """Get similarities to all primitives in a specific bank."""
    bank_start = bank * dims_per_bank
    bank_end = bank_start + dims_per_bank
    
    # Extract bank slice as dense for dot products
    dense = v.to_dense()
    bank_slice = dense[bank_start:bank_end].astype(np.float32)
    
    similarities = {}
    for name, prim_bank in primitive_to_bank.items():
        if prim_bank == bank:
            prim_vec = primitive_vectors[name]
            prim_dense = prim_vec.to_dense()[bank_start:bank_end].astype(np.float32)
            sim = np.dot(bank_slice, prim_dense)
            similarities[name] = float(sim)
    
    return similarities


# =============================================================================
# HADAMARD-OTP BASIS CLASS
# =============================================================================

class HadamardOTPBasis:
    """
    Hadamard-OTP basis for GSE primitives and roles.
    
    Uses:
    - Hadamard matrices for guaranteed orthogonality
    - Semantic banks for category structure
    - Exact negation for antonyms
    - Cross-bank roles for guaranteed binding
    """
    
    def __init__(self, dimension: int = D, n_banks: int = N_BANKS):
        self.dimension = dimension
        self.n_banks = n_banks
        self.dims_per_bank = dimension // n_banks
        self.role_dims_per_bank = self.dims_per_bank // N_ROLES
        
        self.primitives: Dict[str, SparseVector] = {}
        self.roles: Dict[str, SparseVector] = {}
        self.primitive_to_bank: Dict[str, int] = {}
        self.bank_to_primitives: Dict[int, List[str]] = {i: [] for i in range(n_banks)}
        self.role_to_idx: Dict[str, int] = {}
        self.idx_to_role: Dict[int, str] = {}
    
    def generate(self, primitive_names: List[str], role_names: List[str]) -> 'HadamardOTPBasis':
        """Generate all primitive and role vectors."""
        
        # Build antonym lookup
        antonym_partner = {}
        for pos, neg in ANTONYM_PAIRS:
            antonym_partner[pos] = (neg, False)  # pos gets normal pattern
            antonym_partner[neg] = (pos, True)   # neg gets negated pattern
        
        # Track indices per bank
        bank_indices: Dict[int, int] = {i: 0 for i in range(self.n_banks)}
        generated = set()
        
        for name in primitive_names:
            if name in generated:
                continue
            
            if name not in PRIMITIVE_BANKS:
                print(f"Warning: {name} not in PRIMITIVE_BANKS, skipping")
                continue
            
            bank = PRIMITIVE_BANKS[name]
            idx = bank_indices[bank]
            
            if name in antonym_partner:
                partner, is_negative = antonym_partner[name]
                
                if partner in primitive_names and partner not in generated:
                    # Generate pair together using same Hadamard row
                    pos_name = partner if is_negative else name
                    neg_name = name if is_negative else partner
                    
                    self.primitives[pos_name] = generate_primitive_vector(
                        pos_name, bank, idx, is_antonym_negative=False,
                        dimension=self.dimension, dims_per_bank=self.dims_per_bank
                    )
                    self.primitives[neg_name] = generate_primitive_vector(
                        neg_name, bank, idx, is_antonym_negative=True,
                        dimension=self.dimension, dims_per_bank=self.dims_per_bank
                    )
                    
                    self.primitive_to_bank[pos_name] = bank
                    self.primitive_to_bank[neg_name] = bank
                    self.bank_to_primitives[bank].extend([pos_name, neg_name])
                    
                    generated.add(pos_name)
                    generated.add(neg_name)
                    bank_indices[bank] += 1
                    continue
            
            # Normal primitive
            self.primitives[name] = generate_primitive_vector(
                name, bank, idx,
                dimension=self.dimension, dims_per_bank=self.dims_per_bank
            )
            self.primitive_to_bank[name] = bank
            self.bank_to_primitives[bank].append(name)
            generated.add(name)
            bank_indices[bank] += 1
        
        # Generate roles
        for role_idx, name in enumerate(role_names):
            self.roles[name] = generate_role_vector(
                role_idx,
                dimension=self.dimension,
                n_banks=self.n_banks,
                dims_per_bank=self.dims_per_bank,
                role_dims_per_bank=self.role_dims_per_bank
            )
            self.role_to_idx[name] = role_idx
            self.idx_to_role[role_idx] = name
        
        return self
    
    def verify_structure(self) -> Dict:
        """Comprehensive verification of the Hadamard-OTP structure."""
        results = {}
        
        # 1. Within-bank orthogonality (excluding antonym pairs)
        within_bank_max = 0.0
        within_bank_violations = []
        
        for bank in range(self.n_banks):
            prims = self.bank_to_primitives[bank]
            for i, n1 in enumerate(prims):
                for j, n2 in enumerate(prims):
                    if i < j:
                        v1, v2 = self.primitives[n1], self.primitives[n2]
                        sim = v1.cosine(v2)
                        
                        # Check if antonym pair
                        is_antonym = any((n1, n2) == p or (n2, n1) == p for p in ANTONYM_PAIRS)
                        
                        if is_antonym:
                            # Should be exactly -1.0
                            if sim > -0.99:
                                within_bank_violations.append((n1, n2, sim, "antonym not -1"))
                        else:
                            # Should be exactly 0.0
                            if abs(sim) > 0.01:
                                within_bank_violations.append((n1, n2, sim, "not orthogonal"))
                            if abs(sim) > within_bank_max:
                                within_bank_max = abs(sim)
        
        results['within_bank_max_similarity'] = within_bank_max
        results['within_bank_violations'] = within_bank_violations
        
        # 2. Cross-bank orthogonality (should be exactly 0)
        cross_bank_max = 0.0
        cross_bank_violations = []
        
        all_prims = list(self.primitives.items())
        for i, (n1, v1) in enumerate(all_prims):
            for j, (n2, v2) in enumerate(all_prims):
                if i < j:
                    b1 = self.primitive_to_bank.get(n1)
                    b2 = self.primitive_to_bank.get(n2)
                    if b1 != b2:
                        sim = abs(v1.cosine(v2))
                        if sim > 0.01:
                            cross_bank_violations.append((n1, n2, sim))
                        if sim > cross_bank_max:
                            cross_bank_max = sim
        
        results['cross_bank_max_similarity'] = cross_bank_max
        results['cross_bank_violations'] = cross_bank_violations
        
        # 3. Role orthogonality
        role_max = 0.0
        all_roles = list(self.roles.items())
        for i, (n1, v1) in enumerate(all_roles):
            for j, (n2, v2) in enumerate(all_roles):
                if i < j:
                    sim = abs(v1.cosine(v2))
                    if sim > role_max:
                        role_max = sim
        
        results['max_role_similarity'] = role_max
        
        # 4. Antonym structure
        antonym_results = []
        for pos, neg in ANTONYM_PAIRS:
            if pos in self.primitives and neg in self.primitives:
                sim = self.primitives[pos].cosine(self.primitives[neg])
                antonym_results.append({
                    'pair': (pos, neg),
                    'similarity': sim,
                    'is_exact_negation': sim < -0.99
                })
        
        results['antonym_structure'] = antonym_results
        
        # 5. Binding produces non-empty results
        binding_tests = []
        test_prims = list(self.primitives.keys())[:5]
        test_roles = list(self.roles.keys())[:5]
        
        for prim_name in test_prims:
            for role_name in test_roles:
                bound = bind(self.primitives[prim_name], self.roles[role_name])
                binding_tests.append({
                    'primitive': prim_name,
                    'role': role_name,
                    'nnz': bound.nnz,
                    'expected_nnz': self.role_dims_per_bank,
                    'bank': bound.bank
                })
        
        results['binding_tests'] = binding_tests
        
        # 6. Summary statistics
        results['summary'] = {
            'n_primitives': len(self.primitives),
            'n_roles': len(self.roles),
            'n_banks': self.n_banks,
            'dims_per_bank': self.dims_per_bank,
            'role_dims_per_bank': self.role_dims_per_bank,
            'primitive_nnz': self.dims_per_bank,  # Full bank is non-zero
            'role_nnz': self.role_dims_per_bank * self.n_banks,
            'binding_nnz': self.role_dims_per_bank,
        }
        
        return results
    
    def decode_composed(self, composed: SparseVector) -> List[Tuple[str, str, float]]:
        """
        Decode a composed vector to extract (primitive, role, confidence) tuples.
        
        Uses two-level decode:
        1. Find banks with significant signal
        2. Within each bank, find best-matching primitive
        """
        results = []
        
        # Get magnitude per bank
        bank_mags = [(bank, get_bank_magnitude(composed, bank, self.dims_per_bank))
                     for bank in range(self.n_banks)]
        bank_mags.sort(key=lambda x: -x[1])
        
        # Process banks with significant signal
        for bank, mag in bank_mags:
            if mag < 1:  # No signal
                continue
            
            # Get similarities to primitives in this bank
            sims = get_bank_similarities(
                composed, bank, self.primitives, self.primitive_to_bank, self.dims_per_bank
            )
            
            if not sims:
                continue
            
            # Find best match
            best_prim = max(sims, key=lambda k: abs(sims[k]))
            confidence = sims[best_prim]
            
            # Try to identify role by looking at which dimensions are active
            # This is approximate - in full system we'd use unbinding
            results.append((best_prim, "unknown", confidence))
        
        return results
    
    def save(self, path: str):
        """Save basis to file."""
        data = {
            'dimension': self.dimension,
            'n_banks': self.n_banks,
            'primitives': {k: v.serialize() for k, v in self.primitives.items()},
            'roles': {k: v.serialize() for k, v in self.roles.items()},
            'primitive_to_bank': {k: int(v) for k, v in self.primitive_to_bank.items()},
            'role_to_idx': self.role_to_idx,
        }
        with open(path, 'wb') as f:
            msgpack.pack(data, f)
    
    @classmethod
    def load(cls, path: str) -> 'HadamardOTPBasis':
        """Load basis from file."""
        with open(path, 'rb') as f:
            data = msgpack.unpack(f)
        
        basis = cls(data['dimension'], data['n_banks'])
        basis.primitives = {k: SparseVector.deserialize(v) for k, v in data['primitives'].items()}
        basis.roles = {k: SparseVector.deserialize(v) for k, v in data['roles'].items()}
        basis.primitive_to_bank = data['primitive_to_bank']
        basis.role_to_idx = data['role_to_idx']
        basis.idx_to_role = {v: k for k, v in basis.role_to_idx.items()}
        
        # Rebuild bank_to_primitives
        basis.bank_to_primitives = {i: [] for i in range(basis.n_banks)}
        for name, bank in basis.primitive_to_bank.items():
            basis.bank_to_primitives[bank].append(name)
        
        return basis


# =============================================================================
# COMPATIBILITY
# =============================================================================

PrimitiveBasis = HadamardOTPBasis


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    from gse.primitives import PRIMITIVES, ROLES
    
    print("=" * 70)
    print("Hadamard-OTP Architecture Test")
    print("=" * 70)
    
    # Generate basis
    print("\n1. Generating Hadamard-OTP basis...")
    basis = HadamardOTPBasis().generate(PRIMITIVES, ROLES)
    print(f"   Generated {len(basis.primitives)} primitives, {len(basis.roles)} roles")
    
    # Show bank distribution
    print("\n2. Semantic bank distribution:")
    for bank in range(N_BANKS):
        prims = basis.bank_to_primitives[bank]
        print(f"   Bank {bank} ({SemanticBank(bank).name:12s}): {prims}")
    
    # Verify structure
    print("\n3. Verifying Hadamard structure...")
    results = basis.verify_structure()
    
    print(f"   Within-bank max similarity: {results['within_bank_max_similarity']:.6f}")
    print(f"   Cross-bank max similarity: {results['cross_bank_max_similarity']:.6f}")
    print(f"   Role max similarity: {results['max_role_similarity']:.6f}")
    
    if results['within_bank_violations']:
        print(f"   ⚠ Within-bank violations: {results['within_bank_violations'][:3]}")
    else:
        print(f"   ✓ No within-bank violations")
    
    if results['cross_bank_violations']:
        print(f"   ⚠ Cross-bank violations: {results['cross_bank_violations'][:3]}")
    else:
        print(f"   ✓ No cross-bank violations (perfect orthogonality)")
    
    # Antonym structure
    print("\n4. Antonym structure (should be ~-1.0):")
    for item in results['antonym_structure']:
        status = "✓" if item['is_exact_negation'] else "✗"
        print(f"   {status} {item['pair'][0]}/{item['pair'][1]}: {item['similarity']:.4f}")
    
    # Binding tests
    print("\n5. Binding non-zeros (should be ~51):")
    for test in results['binding_tests'][:5]:
        print(f"   bind({test['primitive']}, {test['role']}): "
              f"{test['nnz']} nnz (expected {test['expected_nnz']}), bank={test['bank']}")
    
    # Bundling test
    print("\n6. Bundling test:")
    bound1 = bind(basis.primitives["SOMEONE"], basis.roles["agent"])
    bound2 = bind(basis.primitives["DO"], basis.roles["action"])
    bound3 = bind(basis.primitives["SOMETHING"], basis.roles["patient"])
    
    bundled = bundle([bound1, bound2, bound3])
    print(f"   Bundle of 3 bindings: {bundled.nnz} non-zeros")
    print(f"   Similarity to bound1: {bundled.cosine(bound1):.4f}")
    print(f"   Similarity to bound2: {bundled.cosine(bound2):.4f}")
    print(f"   Similarity to bound3: {bundled.cosine(bound3):.4f}")
    
    # Summary
    print("\n7. Architecture summary:")
    s = results['summary']
    print(f"   Total dimensions: {basis.dimension}")
    print(f"   Banks: {s['n_banks']} (semantic categories)")
    print(f"   Dims per bank: {s['dims_per_bank']}")
    print(f"   Primitive nnz: {s['primitive_nnz']} ({100*s['primitive_nnz']/basis.dimension:.1f}%)")
    print(f"   Role nnz: {s['role_nnz']} ({100*s['role_nnz']/basis.dimension:.1f}%)")
    print(f"   Binding nnz: {s['binding_nnz']} ({100*s['binding_nnz']/basis.dimension:.2f}%)")
    
    print("\n" + "=" * 70)
    print("✓ All tests complete!")
    print("=" * 70)
