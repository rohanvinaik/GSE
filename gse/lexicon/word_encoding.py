"""
Word-level HDC encoding with grammatical metadata.

Design principles:
- Semantic primitives encode MEANING (similarity-relevant)
- Grammatical features encode FUNCTION (parsing-relevant, similarity-masked)
- Operator metadata enables Layer 3 parsing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, FrozenSet, Optional

if TYPE_CHECKING:
    from ..vectors_v2 import SparseVector


# ============================================================
# COMPONENT CLASSIFICATION
# ============================================================


class ComponentType(Enum):
    """What role does this word play in composition?"""

    ATOMIC = auto()  # Content word: receives operations (nouns, verbs, adjectives)
    OPERATOR = auto()  # Function word: performs operations (aux, det, neg, prep)
    HYBRID = auto()  # Context-dependent (e.g., "have" as main verb vs auxiliary)


# ============================================================
# OPERATOR TYPES
# ============================================================


class OperatorType(Enum):
    """For OPERATOR/HYBRID words, what kind of operation?"""

    SIGN = auto()  # Negator: not, un-, in-, never
    HIERARCHY = auto()  # Degree: very, extremely, slightly, barely
    AUXILIARY = auto()  # TAM: did, will, have, be (as aux)
    DETERMINER = auto()  # Reference: the, a, every, this
    PREPOSITION = auto()  # Relation: in, on, with, for
    CONJUNCTION = auto()  # Coordination: and, or, but
    COMPLEMENTIZER = auto()  # Embedding: that, whether, if


# ============================================================
# BINDING BEHAVIOR
# ============================================================


class BindingBehavior(Enum):
    """How does this operator find its arguments?"""

    GREEDY = auto()  # Binds to immediately adjacent compatible token
    LAZY = auto()  # Waits for specific target type, may skip tokens


# ============================================================
# GRAMMATICAL ROLES
# ============================================================


class GramRole(Enum):
    """Possible grammatical roles (for constraint propagation)"""

    NOUN = auto()
    VERB = auto()
    ADJ = auto()
    ADV = auto()
    DET = auto()
    PREP = auto()
    CONJ = auto()
    PRON = auto()
    AUX = auto()
    PARTICLE = auto()


# ============================================================
# GRAMMATICAL FEATURES (Informational Zeros)
# ============================================================


@dataclass(frozen=True)
class GrammaticalFeatures:
    """
    Features that are ENCODED but MASKED for word-level similarity.
    These participate only in sentence-level processing.

    All fields use None to indicate "unspecified" (true informational zero).
    Specific values indicate the feature is active for this word form.

    Example:
        "ran" -> GrammaticalFeatures(tense="PAST", aspect="SIMPLE")
        "run" -> GrammaticalFeatures()  # all None = base form
        semantic_similarity("ran", "run") == 1.0  # tense is masked

    Pronoun example:
        "he" -> GrammaticalFeatures(person=3, number="SINGULAR", gender="MASC", case="NOM")
        "she" -> GrammaticalFeatures(person=3, number="SINGULAR", gender="FEM", case="NOM")
        Both have SOMEONE=1 semantically; differ only in gram features.
    """

    # Verbal features
    tense: Optional[str] = None  # PAST, PRESENT, FUTURE
    aspect: Optional[str] = None  # SIMPLE, PROGRESSIVE, PERFECT
    mood: Optional[str] = None  # INDICATIVE, SUBJUNCTIVE, IMPERATIVE
    voice: Optional[str] = None  # ACTIVE, PASSIVE, MIDDLE

    # Nominal features
    person: Optional[int] = None  # 1, 2, 3
    number: Optional[str] = None  # SINGULAR, PLURAL
    gender: Optional[str] = None  # MASC, FEM, NEUT, COMMON
    case: Optional[str] = None  # NOM, ACC, GEN, DAT

    # Additional features
    definiteness: Optional[str] = None  # DEFINITE, INDEFINITE, DEMONSTRATIVE
    animacy: Optional[str] = None  # ANIMATE, INANIMATE
    reflexivity: Optional[str] = None  # REFLEXIVE, RECIPROCAL, NONE
    deixis: Optional[str] = None  # PROXIMAL, DISTAL, MEDIAL
    polarity: Optional[str] = None  # POSITIVE, NEGATIVE

    def is_empty(self) -> bool:
        """True if all features are unspecified."""
        return all(
            v is None
            for v in [
                self.tense,
                self.aspect,
                self.mood,
                self.voice,
                self.person,
                self.number,
                self.gender,
                self.case,
                self.definiteness,
                self.animacy,
                self.reflexivity,
                self.deixis,
                self.polarity,
            ]
        )

    def to_dict(self) -> Dict[str, any]:
        """Convert to dict, excluding None values."""
        return {
            k: v
            for k, v in {
                "tense": self.tense,
                "aspect": self.aspect,
                "mood": self.mood,
                "voice": self.voice,
                "person": self.person,
                "number": self.number,
                "gender": self.gender,
                "case": self.case,
                "definiteness": self.definiteness,
                "animacy": self.animacy,
                "reflexivity": self.reflexivity,
                "deixis": self.deixis,
                "polarity": self.polarity,
            }.items()
            if v is not None
        }


# ============================================================
# OPERATOR SPECIFICATION
# ============================================================


@dataclass(frozen=True)
class OperatorSpec:
    """
    For OPERATOR words, specifies behavior in Layer 3 parsing.

    The three-component operator model:
    - SIGN: Direction flag (-1/+1), consumed by next operator or atomic
    - HIERARCHY: Intensity modifier, consumes sign, acts on atomic
    - AUXILIARY: Feature transmitter, lazy binding to verb

    Examples:
        "not" -> OperatorSpec(op_type=SIGN, binding=GREEDY, sign_value=-1)
        "very" -> OperatorSpec(op_type=HIERARCHY, binding=GREEDY, hier_delta=+1)
        "did" -> OperatorSpec(op_type=AUXILIARY, binding=LAZY, transmits={"tense"})
    """

    op_type: OperatorType
    binding: BindingBehavior
    seeks: FrozenSet[GramRole] = field(
        default_factory=frozenset
    )  # What target types can this bind to?
    transmits: FrozenSet[str] = field(
        default_factory=frozenset
    )  # What features pass to target?

    # For SIGN operators
    sign_value: Optional[int] = None  # -1 for negators

    # For HIERARCHY operators
    hier_delta: Optional[int] = None  # +1 for "very", -1 for "slightly"


# ============================================================
# LEXEME ENTRY
# ============================================================


@dataclass
class LexemeEntry:
    """
    Complete lexicon entry for a word/morpheme.

    This is the core data structure for Layer 1. Each entry contains:
    - Identity (lemma + surface form)
    - Semantic content (HDC vector of primitives)
    - Grammatical metadata (features, roles)
    - Component classification (atomic/operator/hybrid)

    The semantic_vector encodes only the primitive meanings.
    Grammatical features are stored separately and masked during
    word-level similarity computation.
    """

    # Identity
    lemma: str  # Base form: "run"
    surface_form: str  # This form: "ran"

    # Semantic content (Layer 1 core)
    semantic_vector: "SparseVector"  # HDC encoding of primitives

    # Grammatical metadata (informational zeros)
    possible_roles: FrozenSet[GramRole]  # What roles can this word play?
    gram_features: GrammaticalFeatures  # Features for THIS surface form

    # Component classification
    component_type: ComponentType
    operator_spec: Optional[OperatorSpec] = None  # Only if OPERATOR/HYBRID

    def is_atomic(self) -> bool:
        """Check if this is a content word."""
        return self.component_type == ComponentType.ATOMIC

    def is_operator(self) -> bool:
        """Check if this is a function word."""
        return self.component_type == ComponentType.OPERATOR

    def is_hybrid(self) -> bool:
        """Check if this word can be either content or function."""
        return self.component_type == ComponentType.HYBRID

    def can_be_role(self, role: GramRole) -> bool:
        """Check if this word can fill the given grammatical role."""
        return role in self.possible_roles


# ============================================================
# PREDEFINED OPERATOR SPECIFICATIONS
# ============================================================

# Common operators with their specifications
PREDEFINED_OPERATORS: Dict[str, OperatorSpec] = {
    # SIGN operators (negators)
    "not": OperatorSpec(
        op_type=OperatorType.SIGN,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.VERB, GramRole.ADJ, GramRole.ADV}),
        sign_value=-1,
    ),
    "never": OperatorSpec(
        op_type=OperatorType.SIGN,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.VERB}),
        sign_value=-1,
    ),
    "no": OperatorSpec(
        op_type=OperatorType.SIGN,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.NOUN}),
        sign_value=-1,
    ),
    # HIERARCHY operators (degree modifiers)
    "very": OperatorSpec(
        op_type=OperatorType.HIERARCHY,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.ADJ, GramRole.ADV}),
        hier_delta=1,
    ),
    "extremely": OperatorSpec(
        op_type=OperatorType.HIERARCHY,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.ADJ, GramRole.ADV}),
        hier_delta=2,
    ),
    "slightly": OperatorSpec(
        op_type=OperatorType.HIERARCHY,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.ADJ, GramRole.ADV}),
        hier_delta=-1,
    ),
    "barely": OperatorSpec(
        op_type=OperatorType.HIERARCHY,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.ADJ, GramRole.ADV}),
        hier_delta=-2,
    ),
    # AUXILIARY operators (TAM)
    "did": OperatorSpec(
        op_type=OperatorType.AUXILIARY,
        binding=BindingBehavior.LAZY,
        seeks=frozenset({GramRole.VERB}),
        transmits=frozenset({"tense"}),
    ),
    "will": OperatorSpec(
        op_type=OperatorType.AUXILIARY,
        binding=BindingBehavior.LAZY,
        seeks=frozenset({GramRole.VERB}),
        transmits=frozenset({"tense"}),
    ),
    "have": OperatorSpec(
        op_type=OperatorType.AUXILIARY,
        binding=BindingBehavior.LAZY,
        seeks=frozenset({GramRole.VERB}),
        transmits=frozenset({"aspect"}),
    ),
    "has": OperatorSpec(
        op_type=OperatorType.AUXILIARY,
        binding=BindingBehavior.LAZY,
        seeks=frozenset({GramRole.VERB}),
        transmits=frozenset({"aspect", "person", "number"}),
    ),
    # DETERMINER operators
    "the": OperatorSpec(
        op_type=OperatorType.DETERMINER,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.NOUN, GramRole.ADJ}),
    ),
    "a": OperatorSpec(
        op_type=OperatorType.DETERMINER,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.NOUN, GramRole.ADJ}),
    ),
    "every": OperatorSpec(
        op_type=OperatorType.DETERMINER,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.NOUN, GramRole.ADJ}),
    ),
    "this": OperatorSpec(
        op_type=OperatorType.DETERMINER,
        binding=BindingBehavior.GREEDY,
        seeks=frozenset({GramRole.NOUN, GramRole.ADJ}),
    ),
}
