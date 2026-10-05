#!/usr/bin/env python3
"""
GSE Primitives v2 - Geometrically-Optimized Semantic Encoding

This module defines the redesigned primitive system featuring:
1. Collapsed antonym dimensions (+1/-1 in same dimension)
2. Hierarchical ordinal modifiers (no arbitrary scalars)
3. 8 semantic banks with ~45 total primitives

The key innovation is treating antonyms as BIPOLAR dimensions where
GOOD/BAD occupy the same dimensional space with opposite signs,
achieving perfect geometric opposition (cosine = -1.0).
"""

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Set, Tuple

from gse.scale_definition import BankDef, ScaleDefinition

# =============================================================================
# CORE CONSTANTS
# =============================================================================

D = 8192  # Total dimension (2^13, optimal for Hadamard)
N_BANKS = 8  # Number of semantic banks
DIMS_PER_BANK = D // N_BANKS  # 1024 dims per bank


class Scale(Enum):
    """Processing scales in the constraint cascade."""

    TEXT = "text"  # Document-level: genre, register, domain
    PARAGRAPH = "paragraph"  # Discourse-level: relations, flow
    SENTENCE = "sentence"  # Grammatical: structure, roles
    WORD = "word"  # Semantic: NSM primitives


# =============================================================================
# SEMANTIC BANKS
# =============================================================================


class SemanticBank(IntEnum):
    """The 8 semantic banks, each with 1024 dimensions."""

    SUBSTANTIVES = 0  # Entities and reference
    QUANTITY = 1  # Amount and cardinality (with hierarchy)
    EVALUATORS = 2  # Value and magnitude judgments (bipolar)
    MENTAL = 3  # Cognitive and perceptual states
    ACTION = 4  # Events, states, and existence
    TEMPORAL = 5  # Time relations and duration (bipolar)
    SPATIAL = 6  # Location and spatial relations (bipolar)
    LOGICAL = 7  # Modality, causation, hierarchy markers


SEMANTIC_BANK_NAMES = {
    0: "SUBSTANTIVES",
    1: "QUANTITY",
    2: "EVALUATORS",
    3: "MENTAL",
    4: "ACTION",
    5: "TEMPORAL",
    6: "SPATIAL",
    7: "LOGICAL",
}


# =============================================================================
# BIPOLAR (ANTONYM) DIMENSIONS
# =============================================================================


@dataclass(frozen=True)
class BipolarDimension:
    """
    A bipolar dimension where antonyms occupy the same space with opposite signs.

    Example: EVALUATION dimension
        - GOOD encodes as +1 in these dimensions
        - BAD encodes as -1 in these dimensions
        - cos(GOOD, BAD) = -1.0 (perfect opposition)
    """

    name: str  # Dimension name (e.g., "EVALUATION")
    positive: str  # Positive pole label (e.g., "GOOD")
    negative: str  # Negative pole label (e.g., "BAD")
    bank: SemanticBank  # Which bank this belongs to

    def get_polarity(self, primitive: str) -> int:
        """Get polarity (+1, -1, or 0 if not this dimension)."""
        if primitive == self.positive:
            return 1
        elif primitive == self.negative:
            return -1
        return 0


# The 14 true antonym pairs collapsed as bipolar dimensions
BIPOLAR_DIMENSIONS: List[BipolarDimension] = [
    # Bank 0: SUBSTANTIVES
    BipolarDimension("IDENTITY", "SAME", "OTHER", SemanticBank.SUBSTANTIVES),
    # Bank 2: EVALUATORS
    BipolarDimension("EVALUATION", "GOOD", "BAD", SemanticBank.EVALUATORS),
    BipolarDimension("SIZE", "BIG", "SMALL", SemanticBank.EVALUATORS),
    # Bank 4: ACTION
    BipolarDimension("VITALITY", "ALIVE", "DEAD", SemanticBank.ACTION),
    # Bank 5: TEMPORAL
    BipolarDimension("DURATION", "LONG_TIME", "SHORT_TIME", SemanticBank.TEMPORAL),
    BipolarDimension("TEMPORAL_ORDER", "BEFORE", "AFTER", SemanticBank.TEMPORAL),
    BipolarDimension("TEMPORAL_REF", "THEN", "NOW", SemanticBank.TEMPORAL),
    BipolarDimension("TEMPORAL_BOUND", "START", "END", SemanticBank.TEMPORAL),
    # Bank 6: SPATIAL
    BipolarDimension("VERTICAL", "ABOVE", "BELOW", SemanticBank.SPATIAL),
    BipolarDimension("DISTANCE", "FAR", "NEAR", SemanticBank.SPATIAL),
    BipolarDimension("CONTAINMENT", "OUTSIDE", "INSIDE", SemanticBank.SPATIAL),
    BipolarDimension("DIRECTION", "TOWARD", "AWAY", SemanticBank.SPATIAL),
    BipolarDimension("ACCOMPANIMENT", "WITH", "WITHOUT", SemanticBank.SPATIAL),
    # Bank 7: LOGICAL
    BipolarDimension("TRUTH", "TRUE", "FALSE", SemanticBank.LOGICAL),
]

# Quick lookup: primitive name -> BipolarDimension
BIPOLAR_LOOKUP: Dict[str, BipolarDimension] = {}
for dim in BIPOLAR_DIMENSIONS:
    BIPOLAR_LOOKUP[dim.positive] = dim
    BIPOLAR_LOOKUP[dim.negative] = dim

# Set of all bipolar primitive names (both poles)
BIPOLAR_PRIMITIVES: Set[str] = set()
for dim in BIPOLAR_DIMENSIONS:
    BIPOLAR_PRIMITIVES.add(dim.positive)
    BIPOLAR_PRIMITIVES.add(dim.negative)


def is_bipolar(primitive: str) -> bool:
    """Check if a primitive is part of a bipolar dimension."""
    return primitive in BIPOLAR_PRIMITIVES


def get_bipolar_dimension(primitive: str) -> Optional[BipolarDimension]:
    """Get the bipolar dimension for a primitive, if any."""
    return BIPOLAR_LOOKUP.get(primitive)


def get_canonical_pole(primitive: str) -> Tuple[str, int]:
    """
    Get canonical (positive) form and polarity for a primitive.

    Returns:
        (canonical_name, polarity) where polarity is +1 or -1
        For non-bipolar primitives, returns (primitive, +1)
    """
    dim = get_bipolar_dimension(primitive)
    if dim is None:
        return (primitive, 1)
    return (dim.positive, dim.get_polarity(primitive))


def literal_valence(signature: Dict[str, int]) -> int:
    """A word's literal valence, -1, 0 or +1: the sign its signature gives the EVALUATION dimension (GOOD/BAD).

    Read on the canonical pole, so a row stored on the negative pole reads right before canonical form (#55) rewrites
    the rows: BAD +1 counts as GOOD -1, and a row holding both GOOD +1 and BAD +1 nets to 0. Valence is literal by
    definition (#155; Rohan, 2026-10-04 23:05 UTC): it is what a word's definition encodes, and the affect lexicons
    are not its source. This is the one valence law; #54 moves the other copies onto it.
    """
    total = 0
    for primitive, value in signature.items():
        canonical, pole = get_canonical_pole(primitive)
        if canonical == "GOOD" and value:
            total += pole if value > 0 else -pole
    return (total > 0) - (total < 0)


def negate_decomposition(primitives: Dict[str, int]) -> Dict[str, int]:
    """Selective bipolar negation — the HDC face of word-scale negation.

    Negation (``un-``/``dis-``/``in-`` … and the standalone ``NOT`` flip) inverts
    a word's evaluative *poles* but leaves its non-evaluative content intact:
    ``dislike = NOT(like)`` flips ONLY the {GOOD,BAD}-style bipolar axes;
    intensity and the unipolar primes (DO, KNOW, FEEL, SOMETHING …) are
    preserved (vision §IV-D). This is therefore NOT the blanket
    ``SparseVector.negate()`` (which swaps every index, wrongly flipping unipolar
    primes too) — it operates on the primitive *decomposition* and only touches
    bipolar dimensions.

    Each bipolar pole is first canonicalized to its positive pole, then its sign
    is flipped — so the lexicon's dual convention is handled uniformly:
    ``happy={GOOD:+1}`` → ``{GOOD:-1}`` and ``bad={BAD:+1}`` → ``{GOOD:+1}``
    both come out right.
    """
    out: Dict[str, int] = {}
    for prim, value in primitives.items():
        if prim in BIPOLAR_PRIMITIVES:
            canon, polarity = get_canonical_pole(prim)  # canon = positive pole
            out[canon] = out.get(canon, 0) - (value * polarity)
        else:
            out[prim] = value
    return out


# =============================================================================
# HIERARCHICAL MODIFIERS
# =============================================================================


@dataclass(frozen=True)
class HierarchyLevel:
    """A level in an ordinal hierarchy."""

    name: str  # English word (e.g., "MANY")
    level: int  # Ordinal level (-3 to +3)
    markers: int  # Number of HIER_PLUS or HIER_MINUS markers


class HierarchyType(Enum):
    """Types of hierarchical encoding."""

    QUANTITY = "quantity"  # Amount/cardinality
    INTENSITY = "intensity"  # Degree/strength
    CERTAINTY = "certainty"  # Epistemic modality


# Quantity Hierarchy (7 levels, middle-anchored)
# Encoding: base QUANTITY + N hierarchy markers
QUANTITY_HIERARCHY: Dict[str, HierarchyLevel] = {
    "NONE": HierarchyLevel("NONE", -3, 3),  # [−][−][−][QUANTITY]
    "FEW": HierarchyLevel("FEW", -2, 2),  # [−][−][QUANTITY]
    "SOME": HierarchyLevel("SOME", -1, 1),  # [−][QUANTITY]
    "MIDDLE": HierarchyLevel("MIDDLE", 0, 0),  # [QUANTITY]
    "MORE": HierarchyLevel("MORE", 1, 1),  # [+][QUANTITY]
    "MANY": HierarchyLevel("MANY", 2, 2),  # [+][+][QUANTITY]
    "ALL": HierarchyLevel("ALL", 3, 3),  # [+][+][+][QUANTITY]
}

# Intensity Hierarchy (5 levels)
INTENSITY_HIERARCHY: Dict[str, HierarchyLevel] = {
    "BARELY": HierarchyLevel("BARELY", -2, 2),  # [−][−][INTENSITY]
    "SLIGHTLY": HierarchyLevel("SLIGHTLY", -1, 1),  # [−][INTENSITY]
    "MODERATE": HierarchyLevel("MODERATE", 0, 0),  # [INTENSITY]
    "VERY": HierarchyLevel("VERY", 1, 1),  # [+][INTENSITY]
    "EXTREMELY": HierarchyLevel("EXTREMELY", 2, 2),  # [+][+][INTENSITY]
}

# Certainty Hierarchy (7 levels, epistemic modality)
# Encoding: base CERTAINTY + N hierarchy markers
CERTAINTY_HIERARCHY: Dict[str, HierarchyLevel] = {
    "IMPOSSIBLE": HierarchyLevel("IMPOSSIBLE", -3, 3),  # [−][−][−][CERTAINTY]
    "UNLIKELY": HierarchyLevel("UNLIKELY", -2, 2),  # [−][−][CERTAINTY]
    "DOUBTFUL": HierarchyLevel("DOUBTFUL", -1, 1),  # [−][CERTAINTY]
    "POSSIBLE": HierarchyLevel("POSSIBLE", 0, 0),  # [CERTAINTY] (= MAYBE)
    "PROBABLE": HierarchyLevel("PROBABLE", 1, 1),  # [+][CERTAINTY]
    "LIKELY": HierarchyLevel("LIKELY", 2, 2),  # [+][+][CERTAINTY]
    "CERTAIN": HierarchyLevel("CERTAIN", 3, 3),  # [+][+][+][CERTAINTY]
}

# Combined hierarchy lookup
ALL_HIERARCHY_LEVELS: Dict[str, Tuple[HierarchyType, HierarchyLevel]] = {}
for name, level in QUANTITY_HIERARCHY.items():
    ALL_HIERARCHY_LEVELS[name] = (HierarchyType.QUANTITY, level)
for name, level in INTENSITY_HIERARCHY.items():
    ALL_HIERARCHY_LEVELS[name] = (HierarchyType.INTENSITY, level)
for name, level in CERTAINTY_HIERARCHY.items():
    ALL_HIERARCHY_LEVELS[name] = (HierarchyType.CERTAINTY, level)


def is_hierarchy_modifier(primitive: str) -> bool:
    """Check if a primitive is a hierarchical modifier."""
    return primitive in ALL_HIERARCHY_LEVELS


def get_hierarchy_encoding(modifier: str) -> Optional[Tuple[str, int, int]]:
    """
    Get the hierarchy encoding for a modifier.

    Returns:
        (base_primitive, level, marker_count) or None

    Example:
        get_hierarchy_encoding("MANY") -> ("QUANTITY", 2, 2)
        Meaning: QUANTITY base + 2 positive markers
    """
    if modifier not in ALL_HIERARCHY_LEVELS:
        return None

    hier_type, level = ALL_HIERARCHY_LEVELS[modifier]

    if hier_type == HierarchyType.QUANTITY:
        base = "QUANTITY"
    elif hier_type == HierarchyType.INTENSITY:
        base = "INTENSITY"
    else:  # HierarchyType.CERTAINTY
        base = "CERTAINTY"

    return (base, level.level, level.markers)


# =============================================================================
# UNIPOLAR PRIMITIVES (No antonym)
# =============================================================================

# Bank 0: SUBSTANTIVES (7 unipolar + 1 bipolar dimension)
BANK_0_UNIPOLAR = [
    "I",  # First person
    "YOU",  # Second person
    "SOMEONE",  # Animate entity
    "SOMETHING",  # Inanimate entity
    "PEOPLE",  # Collective animate
    "BODY",  # Physical embodiment
    "KIND",  # Category/type
    "PART",  # Part-whole relation
]

# Bank 1: QUANTITY (2 cardinal + 1 base + 1 category)
BANK_1_UNIPOLAR = [
    "ONE",  # Singular
    "TWO",  # Dual (minimal plural)
    "QUANTITY",  # Base for hierarchy
    "NUMBER",  # Category marker for all numerals
]

# Bank 2: EVALUATORS - all bipolar (no unipolar)
BANK_2_UNIPOLAR: List[str] = []

# Bank 3: MENTAL (7 unipolar)
BANK_3_UNIPOLAR = [
    "THINK",  # Cognitive processing
    "KNOW",  # Epistemic state
    "WANT",  # Volition
    "FEEL",  # Affective/sensory
    "SEE",  # Visual perception
    "HEAR",  # Auditory perception
    "INFER",  # Epistemic inference - draw conclusion from evidence
]

# Bank 4: ACTION (8 unipolar)
BANK_4_UNIPOLAR = [
    "SAY",  # Speech act
    "WORDS",  # Linguistic content
    "DO",  # Agentive action
    "HAPPEN",  # Non-agentive event
    "MOVE",  # Change of location
    "BE",  # Stative existence
    "HAVE",  # Possession
    "EXIST",  # Ontological status
]

# Bank 5: TEMPORAL (1 unipolar + 3 bipolar)
BANK_5_UNIPOLAR = [
    "MOMENT",  # Punctual time
    "WHEN",  # Temporal deixis
]

# Bank 6: SPATIAL (3 unipolar + 3 bipolar)
BANK_6_UNIPOLAR = [
    "WHERE",  # Spatial deixis
    "HERE",  # Proximal location
    "SIDE",  # Lateral relation
    "TOUCH",  # Contact relation
]

# Bank 7: LOGICAL (7 unipolar + hierarchy + 1 bipolar)
BANK_7_UNIPOLAR = [
    "NOT",  # Negation
    "MAYBE",  # Epistemic possibility (= POSSIBLE anchor in CERTAINTY hierarchy)
    "CAN",  # Ability/possibility
    "MUST",  # Deontic necessity/obligation
    "BECAUSE",  # Retrospective causation/reasoning
    "CAUSE",  # Force dynamics - agentive causation (distinct from BECAUSE)
    "IF",  # Conditionality
    "LIKE",  # Similarity
    "HIER_PLUS",  # Positive hierarchy marker [+]
    "HIER_MINUS",  # Negative hierarchy marker [−]
    "INTENSITY",  # Base for intensity hierarchy
    "CERTAINTY",  # Base for certainty hierarchy
]


# =============================================================================
# COMPLETE PRIMITIVE REGISTRY
# =============================================================================


@dataclass
class PrimitiveInfo:
    """Full information about a primitive."""

    name: str
    bank: SemanticBank
    is_bipolar: bool = False
    bipolar_dim: Optional[str] = None  # Dimension name if bipolar
    is_hierarchy_base: bool = False
    is_hierarchy_marker: bool = False


def _build_primitive_registry() -> Dict[str, PrimitiveInfo]:
    """Build complete primitive registry."""
    registry: Dict[str, PrimitiveInfo] = {}

    # Add unipolar primitives
    bank_primitives = [
        (SemanticBank.SUBSTANTIVES, BANK_0_UNIPOLAR),
        (SemanticBank.QUANTITY, BANK_1_UNIPOLAR),
        (SemanticBank.EVALUATORS, BANK_2_UNIPOLAR),
        (SemanticBank.MENTAL, BANK_3_UNIPOLAR),
        (SemanticBank.ACTION, BANK_4_UNIPOLAR),
        (SemanticBank.TEMPORAL, BANK_5_UNIPOLAR),
        (SemanticBank.SPATIAL, BANK_6_UNIPOLAR),
        (SemanticBank.LOGICAL, BANK_7_UNIPOLAR),
    ]

    for bank, primitives in bank_primitives:
        for prim in primitives:
            is_hier_base = prim in ("QUANTITY", "INTENSITY", "CERTAINTY")
            is_hier_marker = prim in ("HIER_PLUS", "HIER_MINUS")
            registry[prim] = PrimitiveInfo(
                name=prim,
                bank=bank,
                is_bipolar=False,
                is_hierarchy_base=is_hier_base,
                is_hierarchy_marker=is_hier_marker,
            )

    # Add bipolar primitives (both poles)
    for dim in BIPOLAR_DIMENSIONS:
        registry[dim.positive] = PrimitiveInfo(
            name=dim.positive,
            bank=dim.bank,
            is_bipolar=True,
            bipolar_dim=dim.name,
        )
        registry[dim.negative] = PrimitiveInfo(
            name=dim.negative,
            bank=dim.bank,
            is_bipolar=True,
            bipolar_dim=dim.name,
        )

    return registry


PRIMITIVE_REGISTRY: Dict[str, PrimitiveInfo] = _build_primitive_registry()


def get_all_primitives() -> List[str]:
    """Get list of all primitive names."""
    return list(PRIMITIVE_REGISTRY.keys())


def get_primitive_info(name: str) -> Optional[PrimitiveInfo]:
    """Get info about a primitive."""
    return PRIMITIVE_REGISTRY.get(name)


def get_bank_primitives(bank: SemanticBank) -> List[str]:
    """Get all primitives in a bank."""
    return [name for name, info in PRIMITIVE_REGISTRY.items() if info.bank == bank]


# =============================================================================
# HUB PRIMITIVES (for learning networks)
# =============================================================================

# 24 hub primitives representing bank families (for WordScaleNetwork)
HUB_PRIMITIVES = [
    # Bank 0: SUBSTANTIVES (3 hubs)
    "SOMEONE",
    "SOMETHING",
    "PART",
    # Bank 1: QUANTITY (2 hubs)
    "QUANTITY",
    "ONE",
    # Bank 2: EVALUATORS (2 hubs - bipolar positive poles)
    "GOOD",
    "BIG",
    # Bank 3: MENTAL (4 hubs)
    "THINK",
    "KNOW",
    "FEEL",
    "WANT",
    # Bank 4: ACTION (4 hubs)
    "DO",
    "HAPPEN",
    "BE",
    "MOVE",
    # Bank 5: TEMPORAL (3 hubs)
    "BEFORE",
    "MOMENT",
    "WHEN",
    # Bank 6: SPATIAL (3 hubs)
    "WHERE",
    "ABOVE",
    "FAR",
    # Bank 7: LOGICAL (3 hubs)
    "NOT",
    "CAN",
    "BECAUSE",
]


# =============================================================================
# PRIMITIVE FAMILIES (for Merkle tree clustering)
# =============================================================================

PRIMITIVE_FAMILIES = {
    # Bank 0: SUBSTANTIVES (3 families)
    "entity_animate": {
        "bank": SemanticBank.SUBSTANTIVES,
        "primitives": ["I", "YOU", "SOMEONE", "PEOPLE", "BODY"],
        "hub": "SOMEONE",
    },
    "entity_inanimate": {
        "bank": SemanticBank.SUBSTANTIVES,
        "primitives": ["SOMETHING", "KIND", "PART"],
        "hub": "SOMETHING",
    },
    "reference": {
        "bank": SemanticBank.SUBSTANTIVES,
        "primitives": ["SAME", "OTHER"],  # Bipolar IDENTITY
        "hub": "PART",
    },
    # Bank 1: QUANTITY (2 families)
    "quantity_cardinal": {
        "bank": SemanticBank.QUANTITY,
        "primitives": ["ONE", "TWO"],
        "hub": "ONE",
    },
    "quantity_scalar": {
        "bank": SemanticBank.QUANTITY,
        "primitives": ["QUANTITY"],  # + hierarchy levels
        "hub": "QUANTITY",
    },
    # Bank 2: EVALUATORS (2 families)
    "evaluation_valence": {
        "bank": SemanticBank.EVALUATORS,
        "primitives": ["GOOD", "BAD"],  # Bipolar EVALUATION
        "hub": "GOOD",
    },
    "evaluation_magnitude": {
        "bank": SemanticBank.EVALUATORS,
        "primitives": ["BIG", "SMALL"],  # Bipolar SIZE
        "hub": "BIG",
    },
    # Bank 3: MENTAL (2 families)
    "mental_cognitive": {
        "bank": SemanticBank.MENTAL,
        "primitives": ["THINK", "KNOW", "INFER"],
        "hub": "THINK",
    },
    "mental_affective": {
        "bank": SemanticBank.MENTAL,
        "primitives": ["WANT", "FEEL", "SEE", "HEAR"],
        "hub": "FEEL",
    },
    # Bank 4: ACTION (2 families)
    "action_dynamic": {
        "bank": SemanticBank.ACTION,
        "primitives": ["DO", "HAPPEN", "MOVE", "SAY"],
        "hub": "DO",
    },
    "state_existence": {
        "bank": SemanticBank.ACTION,
        "primitives": ["BE", "HAVE", "EXIST", "WORDS", "ALIVE", "DEAD"],
        "hub": "BE",
    },
    # Bank 5: TEMPORAL (2 families)
    "temporal_relations": {
        "bank": SemanticBank.TEMPORAL,
        "primitives": ["BEFORE", "AFTER", "THEN", "NOW", "START", "END"],  # Bipolar
        "hub": "BEFORE",
    },
    "temporal_duration": {
        "bank": SemanticBank.TEMPORAL,
        "primitives": ["LONG_TIME", "SHORT_TIME", "MOMENT", "WHEN"],
        "hub": "MOMENT",
    },
    # Bank 6: SPATIAL (2 families)
    "spatial_location": {
        "bank": SemanticBank.SPATIAL,
        "primitives": ["WHERE", "HERE", "INSIDE", "OUTSIDE", "WITH", "WITHOUT"],
        "hub": "WHERE",
    },
    "spatial_relation": {
        "bank": SemanticBank.SPATIAL,
        "primitives": ["ABOVE", "BELOW", "FAR", "NEAR", "SIDE", "TOUCH", "TOWARD", "AWAY"],
        "hub": "ABOVE",
    },
    # Bank 7: LOGICAL (2 families)
    "logical_modal": {
        "bank": SemanticBank.LOGICAL,
        "primitives": ["NOT", "MAYBE", "CAN", "MUST", "IF", "TRUE", "FALSE"],
        "hub": "NOT",
    },
    "logical_causal": {
        "bank": SemanticBank.LOGICAL,
        "primitives": ["BECAUSE", "CAUSE", "LIKE"],
        "hub": "BECAUSE",
    },
}


# =============================================================================
# SEMANTIC ROLES
# =============================================================================

SEMANTIC_ROLES = [
    # Core thematic roles
    "agent",  # Initiator of action
    "patient",  # Affected by action
    "experiencer",  # Mental state bearer
    "theme",  # Entity in motion/location
    "recipient",  # Receiver
    "beneficiary",  # Benefits from action
    "instrument",  # Tool used
    "source",  # Origin
    "goal",  # Destination
    "location",  # Where
    # Descriptive roles
    "attribute",  # Property
    "manner",  # How
    "time",  # When
    "cause",  # Why
    "result",  # Outcome
    "action",  # The action itself
    "state",  # Static condition
    "evaluation",  # Value judgment
    "intention",  # Purpose
    "content",  # Propositional content
    # Modifier roles
    "degree",  # Intensity level
    "quantity",  # Amount
    "relation",  # Connection type
    "property",  # Characteristic
    "possessor",  # Owner
]


# =============================================================================
# ACTIVATION AND DECOMPOSITION
# =============================================================================


class Polarity(IntEnum):
    """Polarity for primitive activation."""

    POSITIVE = 1
    NEGATIVE = -1
    NEUTRAL = 0


@dataclass
class PrimitiveActivation:
    """An activation of a primitive with role and polarity."""

    primitive: str
    role: str
    polarity: Polarity = Polarity.POSITIVE
    hierarchy_level: int = 0  # For hierarchical modifiers

    def __hash__(self):
        return hash((self.primitive, self.role, self.polarity, self.hierarchy_level))


def canonicalize_activation(activation: PrimitiveActivation) -> PrimitiveActivation:
    """
    Canonicalize an activation to use positive poles for bipolar dimensions.

    Example:
        (BAD, "evaluation", +1) -> (GOOD, "evaluation", -1)
        (SMALL, "attribute", +1) -> (BIG, "attribute", -1)
    """
    dim = get_bipolar_dimension(activation.primitive)

    if dim is None:
        # Not bipolar, return as-is
        return activation

    # Get polarity of this pole
    pole_polarity = dim.get_polarity(activation.primitive)

    if pole_polarity == 1:
        # Already positive pole
        return activation

    # Negative pole - canonicalize to positive and flip polarity
    new_polarity = Polarity(-int(activation.polarity))

    return PrimitiveActivation(
        primitive=dim.positive,
        role=activation.role,
        polarity=new_polarity,
        hierarchy_level=activation.hierarchy_level,
    )


def expand_hierarchy_activation(
    modifier: str,
    role: str = "degree",
) -> List[PrimitiveActivation]:
    """
    Expand a hierarchical modifier into base + marker activations.

    Example:
        expand_hierarchy_activation("MANY") ->
        [
            (QUANTITY, "degree", +1, 0),
            (HIER_PLUS, "degree", +1, 1),
            (HIER_PLUS, "degree", +1, 2),
        ]
    """
    encoding = get_hierarchy_encoding(modifier)
    if encoding is None:
        return []

    base, level, marker_count = encoding
    activations = []

    # Add base primitive
    activations.append(
        PrimitiveActivation(
            primitive=base,
            role=role,
            polarity=Polarity.POSITIVE,
            hierarchy_level=0,
        )
    )

    # Add hierarchy markers
    marker = "HIER_PLUS" if level > 0 else "HIER_MINUS"
    for i in range(marker_count):
        activations.append(
            PrimitiveActivation(
                primitive=marker,
                role=role,
                polarity=Polarity.POSITIVE,
                hierarchy_level=i + 1,
            )
        )

    return activations


# =============================================================================
# MULTI-SCALE DEFINITIONS (text, paragraph, sentence)
#
# Each scale is defined via ScaleDefinition (Genesis Atom pattern from DGA).
# The data lives here; the infrastructure is parameterized in scale_definition.py.
# Backward-compatible exports are generated at the bottom of each section.
# (BankDef / ScaleDefinition are imported at the top; scale_definition imports nothing from gse.)
# =============================================================================

# Compositional operator metadata for sentence-scale
COMP_METADATA = {
    "COMP_THAN": {"arity": 2, "operation": "SET_DIFF"},
    "COMP_AS": {"arity": 2, "operation": "BIND_EQ"},
    "COMP_HOW": {"arity": 1, "operation": "DEGREE_QUERY"},
    "COMP_WHAT": {"arity": 1, "operation": "TYPE_QUERY"},
    "COMP_JUST": {"arity": 2, "operation": "CARD_LOWER"},
    "COMP_ONLY": {"arity": 1, "operation": "SET_RESTRICT"},
    "COMP_EVEN": {"arity": 1, "operation": "SCALAR_EXTREME"},
    "COMP_BUT": {"arity": 2, "operation": "CONTRAST"},
    "COMP_SO": {"arity": 2, "operation": "CONSEQUENCE"},
    "COMP_BECAUSE": {"arity": 2, "operation": "CAUSAL_SOURCE"},
}

# --- TEXT SCALE ---

TEXT_SCALE = ScaleDefinition(
    name="text",
    banks=[
        BankDef("GENRE", ["NARRATIVE", "EXPOSITORY", "ARGUMENTATIVE", "DESCRIPTIVE"]),
        BankDef("REGISTER", ["FORMAL", "INFORMAL", "TECHNICAL", "CONVERSATIONAL"]),
        BankDef("DOMAIN", ["ACADEMIC", "COMMERCIAL", "PERSONAL", "INSTITUTIONAL"]),
        BankDef("STRUCTURE", []),
        BankDef("AUDIENCE", []),
        BankDef("PURPOSE", []),
        BankDef("STYLE", []),
        BankDef("RESERVED_TEXT", []),
    ],
    hub_primitives=["NARRATIVE", "FORMAL", "ACADEMIC"],
    families={
        "genre": {"primitives": ["NARRATIVE", "EXPOSITORY", "ARGUMENTATIVE", "DESCRIPTIVE"], "hub": "NARRATIVE"},
        "register": {"primitives": ["FORMAL", "INFORMAL", "TECHNICAL", "CONVERSATIONAL"], "hub": "FORMAL"},
        "domain": {"primitives": ["ACADEMIC", "COMMERCIAL", "PERSONAL", "INSTITUTIONAL"], "hub": "ACADEMIC"},
    },
)

TextBank = TEXT_SCALE.bank_enum
TEXT_BANK_NAMES = TEXT_SCALE.bank_names
TEXT_PRIMITIVES = TEXT_SCALE.all_primitive_names
TEXT_PRIMITIVE_REGISTRY = TEXT_SCALE.primitive_registry
TEXT_HUB_PRIMITIVES = TEXT_SCALE.hub_primitives
TEXT_PRIMITIVE_FAMILIES = TEXT_SCALE.families


def get_text_primitive_info(name: str):
    return TEXT_SCALE.get_primitive_info(name)


def get_text_bank_primitives(bank) -> List[str]:
    return TEXT_SCALE.get_bank_primitives(int(bank))


# --- PARAGRAPH SCALE ---

PARAGRAPH_SCALE = ScaleDefinition(
    name="paragraph",
    banks=[
        BankDef("RHETORICAL", ["TOPIC_INTRO", "CONTINUATION", "ELABORATION", "CONTRAST"]),
        BankDef("CAUSAL", ["CAUSE", "EFFECT"]),
        BankDef("EXEMPLIFICATION", ["EXAMPLE", "SUMMARY"]),
        BankDef("FLOW", ["SHIFT", "RETURN", "PARALLEL", "SEQUENCE"]),
        BankDef("INTENTIONAL", ["CLAIM", "EVIDENCE", "CONCESSION"]),
        BankDef("COHERENCE", []),
        BankDef("GESTALT", []),
        BankDef("RESERVED_PARA", []),
    ],
    hub_primitives=["ELABORATION", "CAUSE", "EXAMPLE", "SEQUENCE", "CLAIM"],
    families={
        "rhetorical": {"primitives": ["TOPIC_INTRO", "CONTINUATION", "ELABORATION", "CONTRAST"], "hub": "ELABORATION"},
        "causal": {"primitives": ["CAUSE", "EFFECT"], "hub": "CAUSE"},
        "exemplification": {"primitives": ["EXAMPLE", "SUMMARY"], "hub": "EXAMPLE"},
        "flow": {"primitives": ["SHIFT", "RETURN", "PARALLEL", "SEQUENCE"], "hub": "SEQUENCE"},
        "intentional": {"primitives": ["CLAIM", "EVIDENCE", "CONCESSION"], "hub": "CLAIM"},
    },
)

ParagraphBank = PARAGRAPH_SCALE.bank_enum
PARAGRAPH_BANK_NAMES = PARAGRAPH_SCALE.bank_names
PARAGRAPH_PRIMITIVES = PARAGRAPH_SCALE.all_primitive_names
PARAGRAPH_PRIMITIVE_REGISTRY = PARAGRAPH_SCALE.primitive_registry
PARAGRAPH_HUB_PRIMITIVES = PARAGRAPH_SCALE.hub_primitives
PARAGRAPH_PRIMITIVE_FAMILIES = PARAGRAPH_SCALE.families


def get_paragraph_primitive_info(name: str):
    return PARAGRAPH_SCALE.get_primitive_info(name)


def get_paragraph_bank_primitives(bank) -> List[str]:
    return PARAGRAPH_SCALE.get_bank_primitives(int(bank))


# --- SENTENCE SCALE ---

SENTENCE_SCALE = ScaleDefinition(
    name="sentence",
    banks=[
        BankDef("CORE_STRUCTURE", ["SYN_SUBJ", "SYN_PRED", "SYN_OBJ", "SYN_COMPL"]),
        BankDef("MODIFICATION", ["SYN_ADJ_MOD", "SYN_ADV_MOD", "SYN_DET"]),
        BankDef(
            "TAM",
            [
                "SYN_TENSE_PAST",
                "SYN_TENSE_PRES",
                "SYN_TENSE_FUT",
                "SYN_ASPECT_PERF",
                "SYN_ASPECT_PROG",
                "SYN_MOOD_INTER",
                "SYN_MOOD_IMPER",
            ],
        ),
        BankDef(
            "COMPARISON", ["COMP_THAN", "COMP_AS"], metadata={p: COMP_METADATA[p] for p in ["COMP_THAN", "COMP_AS"]}
        ),
        BankDef(
            "QUANTIFICATION",
            ["COMP_HOW", "COMP_WHAT"],
            metadata={p: COMP_METADATA[p] for p in ["COMP_HOW", "COMP_WHAT"]},
        ),
        BankDef(
            "CONSTRAINT",
            ["COMP_JUST", "COMP_ONLY", "COMP_EVEN"],
            metadata={p: COMP_METADATA[p] for p in ["COMP_JUST", "COMP_ONLY", "COMP_EVEN"]},
        ),
        BankDef(
            "DISCOURSE",
            ["COMP_BUT", "COMP_SO", "COMP_BECAUSE"],
            metadata={p: COMP_METADATA[p] for p in ["COMP_BUT", "COMP_SO", "COMP_BECAUSE"]},
        ),
        BankDef("RESERVED", []),
    ],
)

SentenceBank = SENTENCE_SCALE.bank_enum
SENTENCE_BANK_NAMES = SENTENCE_SCALE.bank_names
SENTENCE_PRIMITIVES = SENTENCE_SCALE.all_primitive_names


@dataclass
class SentencePrimitiveInfo:
    """Sentence-scale primitive with compositional operator metadata."""

    name: str
    bank: int
    category: str
    is_compositional: bool = False
    comp_arity: int = 0
    comp_operation: Optional[str] = None


def _build_sentence_registry() -> Dict[str, SentencePrimitiveInfo]:
    registry: Dict[str, SentencePrimitiveInfo] = {}
    for name, info in SENTENCE_SCALE.primitive_registry.items():
        meta = info.metadata
        is_comp = name.startswith("COMP_")
        registry[name] = SentencePrimitiveInfo(
            name=name,
            bank=info.bank_index,
            category=info.bank_name,
            is_compositional=is_comp,
            comp_arity=meta.get("arity", 0),
            comp_operation=meta.get("operation"),
        )
    return registry


SENTENCE_PRIMITIVE_REGISTRY: Dict[str, SentencePrimitiveInfo] = _build_sentence_registry()


def get_sentence_primitive_info(name: str) -> Optional[SentencePrimitiveInfo]:
    return SENTENCE_PRIMITIVE_REGISTRY.get(name)


def get_sentence_bank_primitives(bank) -> List[str]:
    return SENTENCE_SCALE.get_bank_primitives(int(bank))


def is_compositional_operator(primitive: str) -> bool:
    info = SENTENCE_PRIMITIVE_REGISTRY.get(primitive)
    return info.is_compositional if info else False


def get_compositional_metadata(primitive: str) -> Optional[Tuple[int, str]]:
    info = SENTENCE_PRIMITIVE_REGISTRY.get(primitive)
    if info and info.is_compositional:
        return (info.comp_arity, info.comp_operation)
    return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_bank_for_primitive(primitive: str) -> Optional[SemanticBank]:
    """Get the semantic bank for a primitive."""
    info = get_primitive_info(primitive)
    return info.bank if info else None


def get_dimension_range(bank: SemanticBank) -> Tuple[int, int]:
    """Get the dimension range [start, end) for a bank."""
    start = bank.value * DIMS_PER_BANK
    end = start + DIMS_PER_BANK
    return (start, end)


def count_primitives() -> Dict[str, int]:
    """Count primitives by category."""
    counts = {
        "total": len(PRIMITIVE_REGISTRY),
        "bipolar_dimensions": len(BIPOLAR_DIMENSIONS),
        "bipolar_primitives": len(BIPOLAR_PRIMITIVES),
        "unipolar_primitives": len(PRIMITIVE_REGISTRY) - len(BIPOLAR_PRIMITIVES),
        "hierarchy_bases": 3,  # QUANTITY, INTENSITY, CERTAINTY
        "hierarchy_markers": 2,  # HIER_PLUS, HIER_MINUS
        "hub_primitives": len(HUB_PRIMITIVES),
        "primitive_families": len(PRIMITIVE_FAMILIES),
    }

    for bank in SemanticBank:
        counts[f"bank_{bank.value}_{bank.name.lower()}"] = len(get_bank_primitives(bank))

    return counts


# =============================================================================
# SUMMARY
# =============================================================================

if __name__ == "__main__":
    print("GSE Primitives v2 - Summary")
    print("=" * 50)

    counts = count_primitives()
    print(f"\nTotal primitives: {counts['total']}")
    print(f"  - Bipolar dimensions: {counts['bipolar_dimensions']}")
    print(f"  - Bipolar primitives: {counts['bipolar_primitives']}")
    print(f"  - Unipolar primitives: {counts['unipolar_primitives']}")
    print(f"  - Hub primitives: {counts['hub_primitives']}")
    print(f"  - Primitive families: {counts['primitive_families']}")

    print("\nPrimitives by bank:")
    for bank in SemanticBank:
        prims = get_bank_primitives(bank)
        print(f"  Bank {bank.value} ({bank.name}): {len(prims)}")
        print(f"    {prims}")

    print("\nBipolar dimensions:")
    for dim in BIPOLAR_DIMENSIONS:
        print(f"  {dim.name}: {dim.positive} <-> {dim.negative} (Bank {dim.bank.value})")

    print("\nQuantity hierarchy:")
    for name, level in sorted(QUANTITY_HIERARCHY.items(), key=lambda x: x[1].level):
        sign = "+" if level.level > 0 else ("−" if level.level < 0 else " ")
        markers = f"[{sign}]" * level.markers if level.markers > 0 else ""
        print(f"  {name:8} = {markers}[QUANTITY]  (level {level.level:+d})")

    print("\nIntensity hierarchy:")
    for name, level in sorted(INTENSITY_HIERARCHY.items(), key=lambda x: x[1].level):
        sign = "+" if level.level > 0 else ("−" if level.level < 0 else " ")
        markers = f"[{sign}]" * level.markers if level.markers > 0 else ""
        print(f"  {name:10} = {markers}[INTENSITY]  (level {level.level:+d})")

    print("\nCertainty hierarchy:")
    for name, level in sorted(CERTAINTY_HIERARCHY.items(), key=lambda x: x[1].level):
        sign = "+" if level.level > 0 else ("−" if level.level < 0 else " ")
        markers = f"[{sign}]" * level.markers if level.markers > 0 else ""
        print(f"  {name:10} = {markers}[CERTAINTY]  (level {level.level:+d})")
