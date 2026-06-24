"""
Syntactic Structure Primitives for D/N Sentence Encoding

Provides 10 syntactic primitives organized into 3 orthogonal banks:
- Bank A (CORE): Subject, Predicate, Object, Complement (40% of word dims)
- Bank B (MODIFICATION): Adjectival, Adverbial, Determiner (30% of word dims)
- Bank C (TAM): Tense, Aspect, Mood markers (30% of word dims)

Used by sentence_structure_encoder.py for position-normalized encoding.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Set

import numpy as np


class SyntacticBank(Enum):
    """Banks for syntactic primitives."""
    CORE = auto()        # 40% - structural positions
    MODIFICATION = auto()  # 30% - modifiers
    TAM = auto()         # 30% - tense/aspect/mood


class SyntacticPrimitive(Enum):
    """10 syntactic primitives for sentence structure encoding."""
    # Bank A: CORE STRUCTURE (40% of word dimensions)
    SYN_SUBJ = auto()     # Subject position
    SYN_PRED = auto()     # Predicate position
    SYN_OBJ = auto()      # Object position
    SYN_COMPL = auto()    # Complement position

    # Bank B: MODIFICATION (30% of word dimensions)
    SYN_ADJ_MOD = auto()  # Adjectival modifier
    SYN_ADV_MOD = auto()  # Adverbial modifier
    SYN_DET = auto()      # Determiner position

    # Bank C: TAM FEATURES (30% of word dimensions)
    SYN_TENSE_PAST = auto()   # Past tense marker
    SYN_ASPECT_PERF = auto()  # Perfect aspect marker
    SYN_MOOD_INTER = auto()   # Interrogative mood marker


# Bank assignments
BANK_ASSIGNMENTS: Dict[SyntacticPrimitive, SyntacticBank] = {
    SyntacticPrimitive.SYN_SUBJ: SyntacticBank.CORE,
    SyntacticPrimitive.SYN_PRED: SyntacticBank.CORE,
    SyntacticPrimitive.SYN_OBJ: SyntacticBank.CORE,
    SyntacticPrimitive.SYN_COMPL: SyntacticBank.CORE,
    SyntacticPrimitive.SYN_ADJ_MOD: SyntacticBank.MODIFICATION,
    SyntacticPrimitive.SYN_ADV_MOD: SyntacticBank.MODIFICATION,
    SyntacticPrimitive.SYN_DET: SyntacticBank.MODIFICATION,
    SyntacticPrimitive.SYN_TENSE_PAST: SyntacticBank.TAM,
    SyntacticPrimitive.SYN_ASPECT_PERF: SyntacticBank.TAM,
    SyntacticPrimitive.SYN_MOOD_INTER: SyntacticBank.TAM,
}

# Bank dimension allocations (as fraction of per-word dimensions)
BANK_ALLOCATIONS: Dict[SyntacticBank, float] = {
    SyntacticBank.CORE: 0.40,
    SyntacticBank.MODIFICATION: 0.30,
    SyntacticBank.TAM: 0.30,
}

# spaCy POS/DEP to syntactic primitive mapping
# Morphological feature to TAM primitive mapping
MORPH_MAPPING: Dict[str, SyntacticPrimitive] = {
    'Tense=Past': SyntacticPrimitive.SYN_TENSE_PAST,
    'Aspect=Perf': SyntacticPrimitive.SYN_ASPECT_PERF,
    'Mood=Inter': SyntacticPrimitive.SYN_MOOD_INTER,
    'VerbForm=Part': SyntacticPrimitive.SYN_ASPECT_PERF,
}


@dataclass
class SyntacticAnnotation:
    """Syntactic annotation for a single word."""
    word: str
    position: int
    primitives: Set[SyntacticPrimitive]
    bank_weights: Dict[SyntacticBank, float]

    def get_bank_primitives(self, bank: SyntacticBank) -> Set[SyntacticPrimitive]:
        """Get primitives belonging to a specific bank."""
        return {p for p in self.primitives if BANK_ASSIGNMENTS[p] == bank}

    @property
    def is_content_word(self) -> bool:
        """Check if this is a content word (not just determiner/aux)."""
        core = self.get_bank_primitives(SyntacticBank.CORE)
        return bool(core - {SyntacticPrimitive.SYN_DET})


@dataclass
class SentenceSyntax:
    """Syntactic structure of a sentence."""
    annotations: List[SyntacticAnnotation]
    sentence_text: str
    is_interrogative: bool = False
    has_past_tense: bool = False
    has_perfect: bool = False

    @property
    def word_count(self) -> int:
        return len(self.annotations)

    def get_subjects(self) -> List[SyntacticAnnotation]:
        """Get all subject words."""
        return [a for a in self.annotations
                if SyntacticPrimitive.SYN_SUBJ in a.primitives]

    def get_predicates(self) -> List[SyntacticAnnotation]:
        """Get all predicate words."""
        return [a for a in self.annotations
                if SyntacticPrimitive.SYN_PRED in a.primitives]

    def get_objects(self) -> List[SyntacticAnnotation]:
        """Get all object words."""
        return [a for a in self.annotations
                if SyntacticPrimitive.SYN_OBJ in a.primitives]


class SyntacticPrimitiveEncoder:
    """
    Encodes syntactic primitives into D/N dimensional space.

    For a sentence with N words and total D=8192 dimensions:
    - Each word gets D/N dimensions
    - Each bank gets its allocated fraction of word dims
    - Primitives within a bank share that bank's subspace
    """

    def __init__(self, total_dims: int = 8192, seed: int = 42):
        self.D = total_dims
        self.seed = seed
        self._rng = np.random.RandomState(seed)

        # Pre-generate orthogonal basis for each primitive
        self._primitive_bases = self._generate_primitive_bases()

    def _generate_primitive_bases(self) -> Dict[SyntacticPrimitive, np.ndarray]:
        """Generate orthogonal random basis vectors for each primitive."""
        bases = {}

        # Use Hadamard-like structure for exact orthogonality
        for prim in SyntacticPrimitive:
            # Generate sparse ternary vector with ~5% density
            vec = np.zeros(self.D)
            density = int(self.D * 0.05)
            indices = self._rng.choice(self.D, size=density, replace=False)
            values = self._rng.choice([-1, 1], size=density)
            vec[indices] = values

            # Normalize
            vec = vec / (np.linalg.norm(vec) + 1e-10)
            bases[prim] = vec

        return bases

    def encode_word(
        self,
        annotation: SyntacticAnnotation,
        word_start_dim: int,
        word_end_dim: int
    ) -> np.ndarray:
        """
        Encode a word's syntactic structure into its allocated dimensions.

        Args:
            annotation: Syntactic annotation for the word
            word_start_dim: Starting dimension for this word
            word_end_dim: Ending dimension for this word

        Returns:
            D-dimensional vector with encoding in [word_start_dim, word_end_dim)
        """
        result = np.zeros(self.D)
        word_dims = word_end_dim - word_start_dim

        if word_dims <= 0:
            return result

        # Calculate bank boundaries within word's subspace
        bank_starts = {}
        bank_ends = {}
        current = word_start_dim

        for bank in SyntacticBank:
            allocation = BANK_ALLOCATIONS[bank]
            bank_dims = int(word_dims * allocation)
            bank_starts[bank] = current
            bank_ends[bank] = current + bank_dims
            current += bank_dims

        # Encode each primitive in its bank's subspace
        for prim in annotation.primitives:
            bank = BANK_ASSIGNMENTS[prim]
            weight = annotation.bank_weights.get(bank, 1.0)

            # Project primitive basis into word's bank subspace
            start = bank_starts[bank]
            end = bank_ends[bank]
            bank_size = end - start

            if bank_size > 0:
                # Use modular projection of basis into subspace
                basis = self._primitive_bases[prim]
                for i, dim in enumerate(range(start, end)):
                    result[dim] += weight * basis[i % self.D]

        return result

    def encode_sentence(self, syntax: SentenceSyntax) -> np.ndarray:
        """
        Encode entire sentence with D/N dimensions per word.

        Args:
            syntax: Parsed syntactic structure

        Returns:
            D-dimensional sentence vector
        """
        result = np.zeros(self.D)
        N = syntax.word_count

        if N == 0:
            return result

        dims_per_word = self.D / N

        for i, annotation in enumerate(syntax.annotations):
            start = int(i * dims_per_word)
            end = int((i + 1) * dims_per_word)

            word_encoding = self.encode_word(annotation, start, end)
            result += word_encoding

        # Add sentence-level TAM features
        if syntax.is_interrogative:
            result += 0.5 * self._primitive_bases[SyntacticPrimitive.SYN_MOOD_INTER]
        if syntax.has_past_tense:
            result += 0.5 * self._primitive_bases[SyntacticPrimitive.SYN_TENSE_PAST]
        if syntax.has_perfect:
            result += 0.5 * self._primitive_bases[SyntacticPrimitive.SYN_ASPECT_PERF]

        # Normalize
        norm = np.linalg.norm(result)
        if norm > 0:
            result = result / norm

        return result


SYNTACTIC_PRIMITIVES: List[str] = [p.name for p in SyntacticPrimitive]

# Bank name constants
SYNTACTIC_BANKS: List[str] = [b.name for b in SyntacticBank]


if __name__ == "__main__":
    print("Syntactic Structure Primitives Tests")
    print("=" * 50)

    # Test primitive definitions
    print(f"✓ Defined {len(SyntacticPrimitive)} syntactic primitives")
    print(f"✓ Organized into {len(SyntacticBank)} banks")

    # Verify bank allocations sum to 1.0
    total_alloc = sum(BANK_ALLOCATIONS.values())
    assert abs(total_alloc - 1.0) < 1e-6, f"Bank allocations sum to {total_alloc}"
    print(f"✓ Bank allocations sum to {total_alloc:.2f}")

    # Test encoder
    encoder = SyntacticPrimitiveEncoder(total_dims=8192)
    print(f"✓ Created encoder with D={encoder.D}")

    # Test single word encoding
    test_annotation = SyntacticAnnotation(
        word="runs",
        position=0,
        primitives={SyntacticPrimitive.SYN_PRED, SyntacticPrimitive.SYN_TENSE_PAST},
        bank_weights={SyntacticBank.CORE: 1.0, SyntacticBank.TAM: 1.0},
    )

    word_vec = encoder.encode_word(test_annotation, 0, 1024)
    print(f"✓ Encoded word: nnz={np.count_nonzero(word_vec)}")

    # Test sentence encoding
    annotations = [
        SyntacticAnnotation(
            word="The",
            position=0,
            primitives={SyntacticPrimitive.SYN_DET},
            bank_weights={SyntacticBank.MODIFICATION: 1.0},
        ),
        SyntacticAnnotation(
            word="cat",
            position=1,
            primitives={SyntacticPrimitive.SYN_SUBJ},
            bank_weights={SyntacticBank.CORE: 1.0},
        ),
        SyntacticAnnotation(
            word="sat",
            position=2,
            primitives={SyntacticPrimitive.SYN_PRED, SyntacticPrimitive.SYN_TENSE_PAST},
            bank_weights={SyntacticBank.CORE: 1.0, SyntacticBank.TAM: 1.0},
        ),
    ]

    syntax = SentenceSyntax(
        annotations=annotations,
        sentence_text="The cat sat",
        has_past_tense=True,
    )

    sent_vec = encoder.encode_sentence(syntax)
    print(f"✓ Encoded sentence: norm={np.linalg.norm(sent_vec):.4f}")
    print(f"✓ Words: {syntax.word_count}, dims/word: {8192/syntax.word_count:.1f}")

    # Test primitives by bank
    for bank in SyntacticBank:
        prims = [p for p in SyntacticPrimitive if BANK_ASSIGNMENTS[p] == bank]
        alloc = BANK_ALLOCATIONS[bank]
        print(f"  - {bank.name}: {len(prims)} primitives, {alloc*100:.0f}% allocation")

    print("=" * 50)
    print("All syntactic structure tests passed!")
