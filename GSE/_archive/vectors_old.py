import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import msgpack

@dataclass
class SparseVector:
    """
    Sparse ternary vector representation.
    Only stores indices of non-zero elements for efficiency.
    """
    dimension: int
    positive_indices: np.ndarray  # dtype=uint16
    negative_indices: np.ndarray  # dtype=uint16
    
    def __eq__(self, other):
        if not isinstance(other, SparseVector):
            return NotImplemented
        return (self.dimension == other.dimension and 
                np.array_equal(self.positive_indices, other.positive_indices) and 
                np.array_equal(self.negative_indices, other.negative_indices))

    @property
    def nnz(self) -> int:
        """Number of non-zero elements."""
        return len(self.positive_indices) + len(self.negative_indices)
    
    @property
    def sparsity(self) -> float:
        """Fraction of non-zero elements."""
        return self.nnz / self.dimension
    
    def to_dense(self) -> np.ndarray:
        """Convert to dense numpy array."""
        v = np.zeros(self.dimension, dtype=np.int8)
        v[self.positive_indices] = 1
        v[self.negative_indices] = -1
        return v
    
    @classmethod
    def from_dense(cls, v: np.ndarray) -> 'SparseVector':
        """Create from dense numpy array."""
        return cls(
            dimension=len(v),
            positive_indices=np.where(v > 0)[0].astype(np.uint16),
            negative_indices=np.where(v < 0)[0].astype(np.uint16)
        )
    
    @classmethod
    def random(cls, dimension: int, nnz: int, seed: Optional[int] = None) -> 'SparseVector':
        """Generate random sparse ternary vector."""
        rng = np.random.default_rng(seed)
        indices = rng.choice(dimension, nnz, replace=False)
        # Sort indices to ensure deterministic order if needed, or just splitting
        # Splitting indices into positive and negative
        half = nnz // 2
        # It's better to sort the indices for consistency in storage and potentially faster operations if we relied on sorted properties, 
        # but the spec just slices. 
        # However, to ensure __eq__ works reliably, we should probably sort them.
        # The spec code:
        # positive_indices=indices[:half].astype(np.uint16),
        # negative_indices=indices[half:].astype(np.uint16)
        # Let's stick to the spec but maybe sort them for canonical representation?
        # The spec doesn't explicitly sort, but standard sparse vector implementations usually benefit from sorted indices.
        # I'll sort them.
        
        pos_indices = np.sort(indices[:half]).astype(np.uint16)
        neg_indices = np.sort(indices[half:]).astype(np.uint16)
        
        return cls(
            dimension=dimension,
            positive_indices=pos_indices,
            negative_indices=neg_indices
        )
    
    def dot(self, other: 'SparseVector') -> int:
        """Efficient sparse dot product."""
        # +1 * +1 = +1
        pp = len(np.intersect1d(self.positive_indices, other.positive_indices))
        # -1 * -1 = +1
        nn = len(np.intersect1d(self.negative_indices, other.negative_indices))
        # +1 * -1 = -1
        pn = len(np.intersect1d(self.positive_indices, other.negative_indices))
        # -1 * +1 = -1
        np_ = len(np.intersect1d(self.negative_indices, other.positive_indices))
        
        return pp + nn - pn - np_
    
    def cosine(self, other: 'SparseVector') -> float:
        """Cosine similarity."""
        dot_product = self.dot(other)
        norm_self = np.sqrt(self.nnz)
        norm_other = np.sqrt(other.nnz)
        if norm_self * norm_other == 0:
            return 0.0
        return dot_product / (norm_self * norm_other)
    
    def serialize(self) -> bytes:
        """Serialize to bytes."""
        return msgpack.packb({
            'd': self.dimension,
            'p': self.positive_indices.tobytes(),
            'n': self.negative_indices.tobytes()
        })
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'SparseVector':
        """Deserialize from bytes."""
        obj = msgpack.unpackb(data)
        return cls(
            dimension=obj['d'],
            positive_indices=np.frombuffer(obj['p'], dtype=np.uint16),
            negative_indices=np.frombuffer(obj['n'], dtype=np.uint16)
        )


def bind(a: SparseVector, b: SparseVector) -> SparseVector:
    """
    Binding operation: element-wise multiplication.
    Creates a vector dissimilar to both inputs.
    Used for: predication, role-filler binding
    """
    assert a.dimension == b.dimension
    
    # For ternary vectors: 
    # (+1) * (+1) = +1, (-1) * (-1) = +1
    # (+1) * (-1) = -1, (-1) * (+1) = -1
    # anything * 0 = 0
    
    # Positive result: (++ or --)
    new_pos = np.union1d(
        np.intersect1d(a.positive_indices, b.positive_indices),
        np.intersect1d(a.negative_indices, b.negative_indices)
    ).astype(np.uint16)
    
    # Negative result: (+- or -+)
    new_neg = np.union1d(
        np.intersect1d(a.positive_indices, b.negative_indices),
        np.intersect1d(a.negative_indices, b.positive_indices)
    ).astype(np.uint16)
    
    # Ensure sorted (union1d does this)
    
    return SparseVector(
        dimension=a.dimension,
        positive_indices=new_pos,
        negative_indices=new_neg
    )


def bundle(vectors: List[SparseVector], normalize: bool = True) -> SparseVector:
    """
    Bundling operation: element-wise addition with majority vote.
    Creates a vector similar to all inputs.
    Used for: collecting role-fillers, representing sets
    """
    if not vectors:
        raise ValueError("Cannot bundle empty list")
    
    dimension = vectors[0].dimension
    
    # Sum all vectors
    accumulator = np.zeros(dimension, dtype=np.int32)
    for v in vectors:
        accumulator[v.positive_indices] += 1
        accumulator[v.negative_indices] -= 1
    
    # Threshold to ternary
    if normalize:
        # Take sign, breaking ties randomly
        # np.sign returns -1, 0, 1
        # For ties (0), we need to decide. 
        # The spec says "Handle ties (zeros in sum) - leave as zero"
        # np.sign(0) is 0, so that works.
        result = np.sign(accumulator)
    else:
        result = accumulator
    
    return SparseVector.from_dense(result.astype(np.int8))


def permute(v: SparseVector, n: int = 1) -> SparseVector:
    """
    Permutation operation: circular shift of indices.
    Creates a vector dissimilar to input.
    Used for: encoding sequence position
    """
    d = v.dimension
    # We need to sort indices after permutation if we want to maintain the invariant
    new_pos = np.sort(((v.positive_indices.astype(np.int32) + n) % d)).astype(np.uint16)
    new_neg = np.sort(((v.negative_indices.astype(np.int32) + n) % d)).astype(np.uint16)
    
    return SparseVector(
        dimension=d,
        positive_indices=new_pos,
        negative_indices=new_neg
    )


class PrimitiveBasis:
    """
    The fundamental basis vectors for semantic primitives.
    These are generated once and remain fixed.

    Implements STRUCTURED SEMANTIC DIMENSIONS per GSE theory:
    - Antonymic pairs (GOOD/BAD, BIG/SMALL) share identical random components
    - But have OPPOSITE signs on polarity dimensions
    - This enables antonym detection via sign flip on specific dimensions
    """

    # Semantic dimension allocations (per GSE theory Section 4.2.2)
    POLARITY_DIMS = range(0, 50)       # Sign flip for antonym pairs
    VALENCE_DIMS = range(50, 100)      # +positive/-positive evaluation
    SIZE_DIMS = range(100, 150)        # +big/-big scale
    QUANTITY_DIMS = range(150, 200)    # +much/-little amount
    TEMPORAL_DIMS = range(200, 250)    # +long/-short time
    SPATIAL_DIMS = range(250, 300)     # +far/-near distance
    VERTICAL_DIMS = range(300, 350)    # +above/-below position

    # Antonymic primitive pairs with their structured dimensions
    ANTONYM_PAIRS = {
        # (positive_term, negative_term): dimension_range
        ('GOOD', 'BAD'): 'VALENCE_DIMS',
        ('BIG', 'SMALL'): 'SIZE_DIMS',
        ('MUCH', 'LITTLE'): 'QUANTITY_DIMS',
        ('LONG_TIME', 'SHORT_TIME'): 'TEMPORAL_DIMS',
        ('FAR', 'NEAR'): 'SPATIAL_DIMS',
        ('ABOVE', 'BELOW'): 'VERTICAL_DIMS',
    }

    def __init__(self, dimension: int = 10000, sparsity: float = 0.1, seed: int = 42):
        self.dimension = dimension
        self.nnz = int(dimension * sparsity)
        self.seed = seed
        self.primitives: Dict[str, SparseVector] = {}
        self.roles: Dict[str, SparseVector] = {}

    def _generate_antonym_pair(self, term1: str, term2: str, polarity_dims: range, seed_offset: int):
        """
        Generate an antonym pair with shared structure and opposite polarity.

        Both vectors will be IDENTICAL except on the polarity dimensions,
        where they have opposite signs. This implements the GSE principle:
        "antonyms are encodings in vector space that are perfectly aligned
        in most dimensions, but a perfect sign flip in exactly one dimension"
        """
        rng = np.random.default_rng(self.seed + seed_offset)

        # Determine which term is "positive" (arbitrary but consistent)
        pos_term, neg_term = (term1, term2) if term1 < term2 else (term2, term1)

        # Generate the base random structure (shared by both)
        # Reserve some dimensions for the polarity signal
        polarity_dim_set = set(polarity_dims)
        non_polarity_dims = [d for d in range(self.dimension) if d not in polarity_dim_set]

        # Number of non-zero elements to place in non-polarity dimensions
        # Leave room for polarity signal
        polarity_nnz = min(20, len(polarity_dims) // 2)  # ~20 elements in polarity region
        random_nnz = self.nnz - polarity_nnz

        # Select random indices for shared structure
        random_indices = rng.choice(non_polarity_dims, min(random_nnz, len(non_polarity_dims)), replace=False)
        half = len(random_indices) // 2
        shared_pos = np.sort(random_indices[:half]).astype(np.uint16)
        shared_neg = np.sort(random_indices[half:]).astype(np.uint16)

        # Select polarity indices (within the designated polarity dimension range)
        polarity_indices = rng.choice(list(polarity_dims), polarity_nnz, replace=False)
        polarity_indices = np.sort(polarity_indices).astype(np.uint16)

        # Create positive term: shared structure + positive polarity signal
        pos_positive = np.concatenate([shared_pos, polarity_indices])
        pos_positive = np.sort(pos_positive).astype(np.uint16)
        pos_negative = shared_neg

        # Create negative term: shared structure + NEGATIVE polarity signal (sign flip!)
        neg_positive = shared_pos
        neg_negative = np.concatenate([shared_neg, polarity_indices])
        neg_negative = np.sort(neg_negative).astype(np.uint16)

        self.primitives[pos_term] = SparseVector(
            dimension=self.dimension,
            positive_indices=pos_positive,
            negative_indices=pos_negative
        )

        self.primitives[neg_term] = SparseVector(
            dimension=self.dimension,
            positive_indices=neg_positive,
            negative_indices=neg_negative
        )
    
    @classmethod
    def generate(cls, primitive_names: List[str], role_names: List[str],
                 dimension: int = 10000, sparsity: float = 0.1, seed: int = 42) -> 'PrimitiveBasis':
        """Factory method to create and populate a PrimitiveBasis."""
        basis = cls(dimension=dimension, sparsity=sparsity, seed=seed)
        # Call the instance method (which is confusingly also named generate)
        basis._generate_vectors(primitive_names, role_names)
        return basis

    # Dimensions reserved for semantic polarity (binding should preserve these)
    RESERVED_POLARITY_DIMS = set(range(50, 350))  # All structured semantic dimensions

    def _generate_vectors(self, primitive_names: List[str], role_names: List[str]):
        """Internal method that does the actual vector generation."""
        # Build lookup for antonym relationships
        antonym_map = {}  # maps each term to (partner, is_positive, dim_range)
        for (pos_term, neg_term), dim_name in self.ANTONYM_PAIRS.items():
            dim_range = getattr(self, dim_name)
            antonym_map[pos_term] = (neg_term, True, dim_range)
            antonym_map[neg_term] = (pos_term, False, dim_range)

        # Track which antonyms we've already generated
        generated_antonyms = set()

        all_names = primitive_names + role_names

        for i, name in enumerate(all_names):
            if name in generated_antonyms:
                continue  # Already generated with partner

            if name in antonym_map and name in primitive_names:
                # Generate antonym pair together
                partner, is_positive, dim_range = antonym_map[name]

                if partner in primitive_names:
                    self._generate_antonym_pair(name, partner, dim_range, i)
                    generated_antonyms.add(name)
                    generated_antonyms.add(partner)
                else:
                    # Partner not in list, generate normally
                    vec = SparseVector.random(self.dimension, self.nnz, seed=self.seed + i)
                    self.primitives[name] = vec
            elif name in role_names:
                # Role vectors: AVOID polarity dimensions to preserve polarity under binding
                # When we bind primitive⊗role, if role[i]=0, the polarity is preserved at dim i
                vec = self._generate_role_vector(i)
                self.roles[name] = vec
            else:
                # Normal primitive generation
                vec = SparseVector.random(self.dimension, self.nnz, seed=self.seed + i)
                self.primitives[name] = vec

    def _generate_role_vector(self, seed_offset: int) -> SparseVector:
        """
        Generate a role vector that AVOIDS polarity dimensions.

        By having 0s in the polarity dimension range, when we bind primitive⊗role,
        the polarity structure of the primitive is preserved at those dimensions.
        (Because x * 0 = 0, but we want x * 1 = x)

        Actually, we want roles to have +1 in polarity dims so binding PRESERVES
        the primitive's value there. x * 1 = x.
        """
        rng = np.random.default_rng(self.seed + seed_offset + 1000)

        # Dimensions outside the polarity range
        non_polarity_dims = [d for d in range(self.dimension) if d not in self.RESERVED_POLARITY_DIMS]

        # Generate random values in non-polarity dimensions
        random_nnz = self.nnz
        random_indices = rng.choice(non_polarity_dims, min(random_nnz, len(non_polarity_dims)), replace=False)
        half = len(random_indices) // 2
        pos_indices = np.sort(random_indices[:half]).astype(np.uint16)
        neg_indices = np.sort(random_indices[half:]).astype(np.uint16)

        # Add +1 in ALL polarity dimensions so binding preserves polarity structure
        # This is key: if role[i] = +1, then (prim ⊗ role)[i] = prim[i] * 1 = prim[i]
        polarity_pos = np.array(sorted(self.RESERVED_POLARITY_DIMS), dtype=np.uint16)
        all_pos = np.sort(np.concatenate([pos_indices, polarity_pos])).astype(np.uint16)

        return SparseVector(
            dimension=self.dimension,
            positive_indices=all_pos,
            negative_indices=neg_indices
        )

    def _verify_orthogonality(self, threshold: float = 0.1):
        """Verify all basis vectors are quasi-orthogonal."""
        all_vecs = list(self.primitives.values()) + list(self.roles.values())
        all_names = list(self.primitives.keys()) + list(self.roles.keys())

        max_sim = 0.0
        for i, v1 in enumerate(all_vecs):
            for j, v2 in enumerate(all_vecs):
                if i < j:
                    sim = abs(v1.cosine(v2))
                    if sim > max_sim:
                        max_sim = sim
                    if sim > threshold:
                        print(f"Warning: {all_names[i]} and {all_names[j]} have similarity {sim:.3f}")

        print(f"Max pairwise similarity: {max_sim:.4f}")

    def check_antonym_structure(self, term1: str, term2: str) -> dict:
        """
        Check if two primitives have proper antonym structure.

        Returns a dict with:
        - overall_similarity: cosine similarity
        - polarity_flip: True if they have opposite signs on polarity dims
        - shared_structure: similarity excluding polarity dimensions
        """
        if term1 not in self.primitives or term2 not in self.primitives:
            return {'error': 'Terms not found in primitives'}

        v1 = self.primitives[term1]
        v2 = self.primitives[term2]

        overall_sim = v1.cosine(v2)

        # Check for polarity flip on structured dimensions
        dense1 = v1.to_dense()
        dense2 = v2.to_dense()

        # Find which dimension range applies
        dim_range = None
        for (t1, t2), dim_name in self.ANTONYM_PAIRS.items():
            if (term1 == t1 and term2 == t2) or (term1 == t2 and term2 == t1):
                dim_range = getattr(self, dim_name)
                break

        if dim_range is None:
            return {
                'overall_similarity': overall_sim,
                'is_antonym_pair': False,
                'note': 'Not a registered antonym pair'
            }

        # Check polarity region
        polarity1 = dense1[list(dim_range)]
        polarity2 = dense2[list(dim_range)]

        # They should have opposite signs where non-zero
        flip_count = np.sum((polarity1 * polarity2) < 0)
        same_count = np.sum((polarity1 * polarity2) > 0)

        return {
            'overall_similarity': overall_sim,
            'is_antonym_pair': True,
            'polarity_flip_count': int(flip_count),
            'polarity_same_count': int(same_count),
            'has_proper_structure': flip_count > 0 and same_count == 0
        }
    
    def save(self, path: str):
        """Save basis to file."""
        data = {
            'dimension': self.dimension,
            'nnz': self.nnz,
            'seed': self.seed,
            'primitives': {k: v.serialize() for k, v in self.primitives.items()},
            'roles': {k: v.serialize() for k, v in self.roles.items()}
        }
        with open(path, 'wb') as f:
            msgpack.pack(data, f)
    
    @classmethod
    def load(cls, path: str) -> 'PrimitiveBasis':
        """Load basis from file."""
        with open(path, 'rb') as f:
            data = msgpack.unpack(f)
        
        basis = cls(data['dimension'], data['nnz'] / data['dimension'], data['seed'])
        basis.primitives = {k: SparseVector.deserialize(v) for k, v in data['primitives'].items()}
        basis.roles = {k: SparseVector.deserialize(v) for k, v in data['roles'].items()}
        return basis
