#!/usr/bin/env python3
"""
GSE API Data Structures.

Defines the OperationTrace and DecodedSemantics dataclasses that represent
the full encoding/decoding pipeline in a JSON-serializable format.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TokenTrace:
    """Trace for a single token encoding."""

    token: str
    lemma: str
    pos: str
    position: int

    # Primitives from lexicon
    word_primitives: Dict[str, int]
    sent_primitives: Dict[str, int]

    # Vector stats (not full vectors - too large for JSON)
    word_vec_nnz: int
    sent_vec_nnz: int
    full_vec_nnz: int

    # Compositional operator info
    is_operator: bool = False
    comp_primitive: Optional[str] = None
    comp_operation: Optional[str] = None
    comp_arity: int = 0

    # Source lookup is independent of its possibly composed/absorbed signature.
    # Defaults retain compatibility with traces serialized before this channel.
    lexicon_status: Optional[str] = None
    lexical_evidence: Dict = field(default_factory=dict)
    negation_evidence: Dict = field(default_factory=dict)
    operator_tier: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OperatorTrace:
    """Trace for compositional operator resolution."""

    primitive: str  # COMP_THAN
    operation: str  # SET_DIFF
    position: int  # Token position
    arity: int  # 2
    arg1_tokens: List[int]  # [1, 3] (dog, cuter)
    arg2_tokens: List[int]  # [6] (cat)
    arg1_lemmas: List[str]  # ["dog", "cuter"]
    arg2_lemmas: List[str]  # ["cat"]
    result_nnz: int

    def to_dict(self) -> Dict:
        return asdict(self)

    def get_content_args(self) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """Get content word arguments (filter out function words)."""
        function_words = {"the", "a", "an", "be", "is", "are", "was", "were"}
        arg1 = tuple(lemma for lemma in self.arg1_lemmas if lemma not in function_words)
        arg2 = tuple(lemma for lemma in self.arg2_lemmas if lemma not in function_words)
        return (arg1, arg2)

    def structurally_equals(self, other: "OperatorTrace") -> bool:
        """Check if two operators have identical logical structure."""
        return self.operation == other.operation and self.get_content_args() == other.get_content_args()

    def get_entity_args(self) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """Get entity arguments only (filter out function words AND properties)."""
        # Properties are typically adjectives/adverbs with these lemmas
        non_entities = {
            "the",
            "a",
            "an",
            "be",
            "is",
            "are",
            "was",
            "were",
            "cut",
            "cute",
            "big",
            "small",
            "tall",
            "short",
            "fast",
            "slow",
            "good",
            "bad",
            "more",
            "less",
        }
        arg1 = tuple(lemma for lemma in self.arg1_lemmas if lemma not in non_entities)
        arg2 = tuple(lemma for lemma in self.arg2_lemmas if lemma not in non_entities)
        return (arg1, arg2)

    def is_argument_swap_of(self, other: "OperatorTrace") -> bool:
        """
        Check if this operator is an argument-swapped version of other.

        Compares the ENTITIES being compared, ignoring the property.
        "dog cuter than cat" is argument-swap of "cat cuter than dog"
        """
        if self.operation != other.operation:
            return False
        my_entities = self.get_entity_args()
        other_entities = other.get_entity_args()
        # Check if entities are swapped
        return my_entities[0] == other_entities[1] and my_entities[1] == other_entities[0]


@dataclass
class ClauseSpan:
    """One clause's token range within a multi-clause sentence.

    Emitted by the encoder's segmentation pre-pass (see
    ``docs/COMPLEX_SENTENCE_DESIGN.md`` §3) and consumed by
    :func:`gse.symbolic.expression.from_trace` to build correctly-nested ASTs.

    ``token_start`` is inclusive, ``token_end`` exclusive. ``operator_indices``
    are indices into :attr:`OperationTrace.operators` for the *within-clause*
    operators whose result belongs to this clause (clause-linking operators are
    the glue *between* spans and are not listed in any span).
    """

    clause_id: int
    token_start: int
    token_end: int
    operator_indices: List[int] = field(default_factory=list)

    # Embedding (M2b/M2c). ``kind`` is "sequential" for a top-level clause split
    # at a because/so boundary; "relative" for a who/which/that clause; "control"
    # for a 'to' complement. Embedded clauses carry ``parent_id`` (the clause
    # they nest inside) and ``attaches_to_token`` (the antecedent / controller
    # token position in the parent). See docs/COMPLEX_SENTENCE_DESIGN.md §M2.
    kind: str = "sequential"
    parent_id: Optional[int] = None
    attaches_to_token: Optional[int] = None
    # For a relative clause: which gap the relativizer fills ("subject"/"object"),
    # read from the relativizer's dep — lets the restriction bind the antecedent
    # into the gap. None for non-relative spans or an unresolved relativizer.
    gap_role: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OperationTrace:
    """Complete trace of encoding operations."""

    input_text: str
    tokens: List[TokenTrace]
    operators: List[OperatorTrace]

    # Final bundle info
    final_nnz: int
    sparsity: float

    # Primitive activations in final vector (cosine vs each primitive)
    word_primitive_activations: Dict[str, float]
    sent_primitive_activations: Dict[str, float]

    # Vector hash for reproducibility verification
    vector_hash: str

    # Metadata
    version: str = "1.0"
    deterministic: bool = True

    # Clause segmentation (multi-clause sentences only). Empty for single-clause
    # inputs, which keeps their serialized traces byte-identical to pre-clause
    # GSE. Populated only when ≥1 clause-linking operator splits the sentence.
    clauses: List[ClauseSpan] = field(default_factory=list)

    # The actual vector (not serialized to JSON)
    _vector: Any = field(default=None, repr=False)

    @property
    def vector(self):
        return self._vector

    @vector.setter
    def vector(self, v):
        self._vector = v

    def to_dict(self) -> Dict:
        """Convert to dictionary (excluding vector)."""
        d = {
            "version": self.version,
            "input_text": self.input_text,
            "tokens": [t.to_dict() for t in self.tokens],
            "operators": [o.to_dict() for o in self.operators],
            "final_nnz": self.final_nnz,
            "sparsity": self.sparsity,
            "word_primitive_activations": self.word_primitive_activations,
            "sent_primitive_activations": self.sent_primitive_activations,
            "vector_hash": self.vector_hash,
            "deterministic": self.deterministic,
        }
        # Only emit clauses for multi-clause sentences, so single-clause traces
        # stay byte-identical to pre-clause GSE.
        if self.clauses:
            d["clauses"] = [c.to_dict() for c in self.clauses]
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON (excluding vector)."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: Dict) -> "OperationTrace":
        """Create from dictionary."""
        return cls(
            input_text=d["input_text"],
            tokens=[TokenTrace(**t) for t in d["tokens"]],
            operators=[OperatorTrace(**o) for o in d["operators"]],
            final_nnz=d["final_nnz"],
            sparsity=d["sparsity"],
            word_primitive_activations=d["word_primitive_activations"],
            sent_primitive_activations=d["sent_primitive_activations"],
            vector_hash=d["vector_hash"],
            version=d.get("version", "1.0"),
            deterministic=d.get("deterministic", True),
            clauses=[ClauseSpan(**c) for c in d.get("clauses", [])],
        )

    @classmethod
    def from_json(cls, json_str: str) -> "OperationTrace":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def logical_equals(self, other: "OperationTrace") -> bool:
        """
        Check if two traces have identical logical structure.

        This compares the set-theoretic operations, not just HDC similarity.
        Two sentences with similar content but different argument order
        will return False here (correctly distinguishing them logically).
        """
        if len(self.operators) != len(other.operators):
            return False
        for op1, op2 in zip(self.operators, other.operators):
            if not op1.structurally_equals(op2):
                return False
        return True

    def is_argument_swap_of(self, other: "OperationTrace") -> bool:
        """
        Check if this trace is an argument-swapped version of other.

        Example: "dog is cuter than cat" vs "cat is cuter than dog"
        These are argument swaps - same operation, reversed arguments.
        """
        if len(self.operators) != len(other.operators):
            return False
        for op1, op2 in zip(self.operators, other.operators):
            if not op1.is_argument_swap_of(op2):
                return False
        return True


# =============================================================================
# DECODED SEMANTICS
# =============================================================================


@dataclass
class EntityExtraction:
    """Extracted entity from vector."""

    lemma: str
    pos: str
    confidence: float
    primitives: List[str]  # Active primitives for this entity

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttributeExtraction:
    """Extracted attribute from vector."""

    attribute: str  # "positive_quality", "large_size", etc.
    polarity: int  # +1 or -1
    intensity: float  # 0.0 to 1.0
    source_primitive: str  # GOOD, BAD, BIG, SMALL

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RelationExtraction:
    """Extracted relation from vector."""

    relation: str  # "COMP_THAN", etc.
    confidence: float
    operation: str  # "SET_DIFF", etc.
    arg1_candidates: List[str]
    arg2_candidates: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DecodedSemantics:
    """Complete decoded semantics from a vector."""

    entities: List[EntityExtraction]
    attributes: List[AttributeExtraction]
    relations: List[RelationExtraction]

    # Nearest lexemes from database
    nearest_lexemes: List[Tuple[str, float]]

    # Bank activity profile
    bank_activations: Dict[str, float]

    # Raw primitive activations
    primitive_activations: Dict[str, float]

    def to_dict(self) -> Dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "attributes": [a.to_dict() for a in self.attributes],
            "relations": [r.to_dict() for r in self.relations],
            "nearest_lexemes": self.nearest_lexemes,
            "bank_activations": self.bank_activations,
            "primitive_activations": self.primitive_activations,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# SIMILARITY RESULT
# =============================================================================


@dataclass
class SimilarityResult:
    """Result of comparing two vectors."""

    sentence1: str
    sentence2: str
    cosine: float
    alignment: float  # Same-sign overlap
    opposition: float  # Opposite-sign overlap
    orthogonality: float  # Non-overlap

    shared_primitives: List[str]
    different_primitives: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
