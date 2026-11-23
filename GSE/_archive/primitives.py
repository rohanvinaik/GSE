# =============================================================================
# SCALE DEFINITIONS
# =============================================================================
# Each scale in the constraint cascade has its own primitive set.
# Scales form a hierarchy: Text → Paragraph → Sentence → Word → HDC

from enum import Enum, IntEnum


class Scale(Enum):
    """Processing scales in the constraint cascade."""
    TEXT = "text"           # Document-level: genre, register, domain
    PARAGRAPH = "paragraph" # Discourse-level: relations, flow
    SENTENCE = "sentence"   # Grammatical: structure, roles (NOT semantic)
    WORD = "word"           # Semantic: NSM primitives


# =============================================================================
# TEXT-SCALE PRIMITIVES (12)
# =============================================================================
# Meta-constraints that set the "mind frame" for downstream processing.
# NO learning network - detected via surface feature pattern matching.

TEXT_PRIMITIVES = [
    # Genre markers
    "NARRATIVE",        # Story-telling, temporal flow
    "EXPOSITORY",       # Explaining, informing
    "ARGUMENTATIVE",    # Persuading, reasoning
    "DESCRIPTIVE",      # Depicting, characterizing

    # Register markers
    "FORMAL",           # Academic, professional
    "INFORMAL",         # Casual, conversational
    "TECHNICAL",        # Domain-specific vocabulary
    "CONVERSATIONAL",   # Interactive, dialogic

    # Domain signals
    "ACADEMIC",         # Scholarly context
    "COMMERCIAL",       # Business, marketing
    "PERSONAL",         # Private, intimate
    "INSTITUTIONAL",    # Organizational, official
]


# =============================================================================
# PARAGRAPH-SCALE PRIMITIVES (15)
# =============================================================================
# Discourse relations - how paragraphs connect and flow.
# MAYBE minimal learning network (8-12 nodes) for open-ended patterns.

PARAGRAPH_PRIMITIVES = [
    # Rhetorical structure (RST-inspired)
    "TOPIC_INTRO",      # Introducing a new topic
    "CONTINUATION",     # Extending the current topic
    "ELABORATION",      # Adding detail to prior point
    "CONTRAST",         # Opposing prior point
    "CAUSE",            # Causal antecedent
    "EFFECT",           # Causal consequent
    "EXAMPLE",          # Illustrative instance
    "SUMMARY",          # Condensing prior content

    # Flow markers
    "SHIFT",            # Topic change
    "RETURN",           # Returning to prior topic
    "PARALLEL",         # Similar structure to prior
    "SEQUENCE",         # Temporal/logical ordering

    # Intentional markers
    "CLAIM",            # Main assertion
    "EVIDENCE",         # Supporting information
    "CONCESSION",       # Acknowledging counter-point
]


# =============================================================================
# SENTENCE-SCALE PRIMITIVES (20)
# =============================================================================
# GRAMMATICAL primitives - NOT semantic. These are about sentence structure.
# NO learning network - spaCy handles parsing; we just extract these.

SENTENCE_PRIMITIVES = [
    # Core grammatical functions
    "SUBJECT",          # Nominal subject
    "PREDICATE",        # Verbal core
    "OBJECT",           # Direct object
    "COMPLEMENT",       # Subject/object complement

    # Modifiers
    "ADJUNCT",          # Optional modifier
    "ATTRIBUTE",        # Adjectival modifier
    "ADVERBIAL",        # Adverbial modifier

    # Clause types
    "MAIN_CLAUSE",      # Independent clause
    "SUBORDINATE",      # Dependent clause
    "RELATIVE",         # Relative clause
    "CONDITIONAL",      # If-clause

    # Mood/modality
    "DECLARATIVE",      # Statement
    "INTERROGATIVE",    # Question
    "IMPERATIVE",       # Command
    "CERTAIN",          # High certainty modal
    "POSSIBLE",         # Epistemic possibility
    "NECESSARY",        # Deontic necessity

    # Polarity
    "AFFIRMATIVE",      # Positive polarity
    "NEGATIVE_POL",     # Negative polarity (renamed to avoid conflict)
    "PASSIVE_VOICE",    # Passive construction
]


# =============================================================================
# WORD-SCALE PRIMITIVES (62 - original NSM-based)
# =============================================================================
# Semantic primitives for word decomposition.
# MINIMAL learning network (24 nodes) learns primitive connection rules.

PRIMITIVES = [
    # Substantives (Bank 0)
    "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY",
    "KIND", "PART", "THIS", "SAME", "OTHER",
    # Determiners/Quantifiers (Bank 1)
    "ONE", "TWO", "SOME", "ALL", "MUCH", "LITTLE",
    # Evaluators (Bank 2)
    "GOOD", "BAD", "BIG", "SMALL",
    # Mental (Bank 3)
    "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR",
    # Action/State (Bank 4)
    "SAY", "WORDS", "TRUE", "DO", "HAPPEN", "MOVE",
    "BE", "HAVE", "EXIST", "LIVE", "DIE",
    # Temporal (Bank 5)
    "WHEN", "NOW", "BEFORE", "AFTER", "LONG_TIME", "SHORT_TIME", "MOMENT",
    # Spatial (Bank 6)
    "WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR", "INSIDE", "SIDE", "TOUCH",
    # Logical/Modifiers (Bank 7)
    "NOT", "MAYBE", "CAN", "BECAUSE", "IF", "VERY", "MORE", "LIKE"
]

# Alias for clarity
WORD_PRIMITIVES = PRIMITIVES


# =============================================================================
# SEMANTIC BANKS
# =============================================================================
# Group primitives into semantic banks for the Hadamard-OTP architecture.
# Each bank is relatively orthogonal to others.

SEMANTIC_BANKS = {
    0: ["I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART", "THIS", "SAME", "OTHER"],
    1: ["ONE", "TWO", "SOME", "ALL", "MUCH", "LITTLE"],
    2: ["GOOD", "BAD", "BIG", "SMALL"],
    3: ["THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR"],
    4: ["SAY", "WORDS", "TRUE", "DO", "HAPPEN", "MOVE", "BE", "HAVE", "EXIST", "LIVE", "DIE"],
    5: ["WHEN", "NOW", "BEFORE", "AFTER", "LONG_TIME", "SHORT_TIME", "MOMENT"],
    6: ["WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR", "INSIDE", "SIDE", "TOUCH"],
    7: ["NOT", "MAYBE", "CAN", "BECAUSE", "IF", "VERY", "MORE", "LIKE"],
}

# Reverse lookup: primitive → bank
PRIMITIVE_TO_BANK = {}
for bank_id, prims in SEMANTIC_BANKS.items():
    for p in prims:
        PRIMITIVE_TO_BANK[p] = bank_id


# =============================================================================
# HUB PRIMITIVES (24 nodes for Word-scale learning network)
# =============================================================================
# These are "bank representatives" - key primitives that drive activation
# patterns within their semantic bank. The learning network uses these
# as nodes to learn connection rules, NOT all 62 primitives.

HUB_PRIMITIVES = [
    # Bank 0 - Substantives (3 hubs)
    "SOMEONE",      # Animate entity hub
    "SOMETHING",    # Inanimate entity hub
    "PART",         # Relational hub

    # Bank 1 - Quantifiers (3 hubs)
    "SOME",         # Existential quantifier hub
    "ALL",          # Universal quantifier hub
    "MUCH",         # Degree quantifier hub

    # Bank 2 - Evaluators (2 hubs)
    "GOOD",         # Positive evaluation hub (includes BAD via polarity)
    "BIG",          # Size/magnitude hub (includes SMALL via polarity)

    # Bank 3 - Mental (4 hubs)
    "THINK",        # Cognitive hub
    "KNOW",         # Epistemic hub
    "FEEL",         # Affective hub
    "WANT",         # Conative hub

    # Bank 4 - Action/State (4 hubs)
    "DO",           # Agentive action hub
    "HAPPEN",       # Event hub
    "BE",           # State/existence hub
    "MOVE",         # Motion hub

    # Bank 5 - Temporal (2 hubs)
    "NOW",          # Temporal reference hub
    "BEFORE",       # Temporal relation hub (includes AFTER via polarity)

    # Bank 6 - Spatial (3 hubs)
    "WHERE",        # Location reference hub
    "ABOVE",        # Vertical relation hub (includes BELOW via polarity)
    "INSIDE",       # Containment hub

    # Bank 7 - Logical (3 hubs)
    "NOT",          # Negation hub
    "CAN",          # Modal hub
    "BECAUSE",      # Causal relation hub
]

# Verify we have 24 hubs
assert len(HUB_PRIMITIVES) == 24, f"Expected 24 hub primitives, got {len(HUB_PRIMITIVES)}"


# =============================================================================
# ORCHESTRATOR PRIMITIVES (36 nodes for routing network)
# =============================================================================
# The orchestrator learns task-specific routing and combination rules.
# These nodes represent cross-scale coordination patterns.

ORCHESTRATOR_NODES = [
    # Scale routing signals (4)
    "ROUTE_TEXT",           # Activate text-scale processing
    "ROUTE_PARAGRAPH",      # Activate paragraph-scale processing
    "ROUTE_SENTENCE",       # Activate sentence-scale processing
    "ROUTE_WORD",           # Activate word-scale processing

    # Task type signals (8)
    "TASK_CLASSIFY",        # Classification task
    "TASK_EXTRACT",         # Information extraction
    "TASK_COMPARE",         # Comparison/similarity
    "TASK_GENERATE",        # Generation/completion
    "TASK_SUMMARIZE",       # Summarization
    "TASK_ANALYZE",         # Deep analysis
    "TASK_VALIDATE",        # Validation/verification
    "TASK_TRANSFORM",       # Transformation

    # Confidence signals (4)
    "CONF_HIGH",            # High confidence path
    "CONF_MEDIUM",          # Medium confidence
    "CONF_LOW",             # Low confidence
    "CONF_AMBIGUOUS",       # Genuine ambiguity detected

    # Combination rules (8)
    "COMBINE_BUNDLE",       # Use bundling
    "COMBINE_BIND",         # Use binding
    "COMBINE_PERMUTE",      # Use permutation
    "COMBINE_WEIGHT",       # Apply frequency weighting
    "COMBINE_OVERRIDE",     # Override with context
    "COMBINE_AVERAGE",      # Weighted average
    "COMBINE_MAX",          # Take maximum signal
    "COMBINE_VOTE",         # Majority voting

    # Error handling (4)
    "ERROR_RETRY",          # Retry with different strategy
    "ERROR_FALLBACK",       # Use fallback encoding
    "ERROR_ESCALATE",       # Escalate to external system
    "ERROR_ACCEPT",         # Accept uncertainty

    # Context signals (8)
    "CTX_PRIOR",            # Use prior context
    "CTX_POSTERIOR",        # Update with new info
    "CTX_RESET",            # Reset context
    "CTX_CACHE_HIT",        # Merkle cache hit
    "CTX_CACHE_MISS",       # Merkle cache miss
    "CTX_FREQUENCY",        # Use frequency weighting
    "CTX_SALIENCE",         # Use salience weighting
    "CTX_RECENCY",          # Use recency weighting
]

# Verify we have 36 orchestrator nodes
assert len(ORCHESTRATOR_NODES) == 36, f"Expected 36 orchestrator nodes, got {len(ORCHESTRATOR_NODES)}"


# =============================================================================
# PRIMITIVES BY SCALE
# =============================================================================
# Mapping from scale to its primitive set

PRIMITIVES_BY_SCALE = {
    Scale.TEXT: TEXT_PRIMITIVES,
    Scale.PARAGRAPH: PARAGRAPH_PRIMITIVES,
    Scale.SENTENCE: SENTENCE_PRIMITIVES,
    Scale.WORD: WORD_PRIMITIVES,
}

ROLES = [
    # Core thematic roles
    "agent", "patient", "experiencer", "theme",
    "recipient", "beneficiary", "instrument", "source", "goal", "location",
    # Descriptive roles
    "attribute", "manner", "time", "cause", "result",
    "action", "state", "evaluation", "intention", "content",
    # Intensity and aspect roles
    "intensity",      # How much/strong (VERY, MORE, LITTLE)
    "duration",       # How long (LONG_TIME, SHORT_TIME, MOMENT)
    "aspect",         # Completion, iteration (ongoing, completed, repeated)
    "frequency",      # How often
    "degree",         # Scalar degree (MORE, LESS)
    # Additional roles for FrameNet/WordNet integration
    "quantity",       # Amount/number (ONE, TWO, SOME, ALL, MUCH)
    "relation",       # Relational marker (BECAUSE, IF, etc.)
    "property",       # Generic property
    "possessor",      # Owner/possessor
    "path",           # Path of motion
]

from typing import List, Tuple, NamedTuple, Optional

class Polarity(IntEnum):
    """Ternary polarity for semantic encoding."""
    POSITIVE = 1    # Primitive applies with positive valence
    NEGATIVE = -1   # Primitive applies with opposite valence
    # Zero (orthogonal) = primitive ABSENT from decomposition


class PrimitiveActivation(NamedTuple):
    """A single primitive activation with role and polarity."""
    primitive: str
    role: str
    polarity: Polarity = Polarity.POSITIVE


# Canonical forms: always use positive primitive with polarity marker
# This ensures antonyms SHARE vectors (with opposite signs)
ANTONYM_CANONICAL = {
    # Negative form → (Canonical positive form, polarity)
    "BAD": ("GOOD", Polarity.NEGATIVE),
    "SMALL": ("BIG", Polarity.NEGATIVE),
    "LITTLE": ("MUCH", Polarity.NEGATIVE),
    "SHORT_TIME": ("LONG_TIME", Polarity.NEGATIVE),
    "NEAR": ("FAR", Polarity.NEGATIVE),
    "BELOW": ("ABOVE", Polarity.NEGATIVE),
    "AFTER": ("BEFORE", Polarity.NEGATIVE),
    "DIE": ("LIVE", Polarity.NEGATIVE),
}


class SemanticBank(IntEnum):
    """Semantic bank identifiers for Hadamard-OTP architecture."""
    SUBSTANTIVES = 0
    DETERMINERS = 1
    EVALUATORS = 2
    MENTAL = 3
    ACTION = 4
    TEMPORAL = 5
    SPATIAL = 6
    LOGICAL = 7


# =============================================================================
# POLARITY SCOPE - Which banks get "infected" by negative polarity
# =============================================================================
# When a primitive with negative polarity appears, it propagates that polarity
# to co-occurring primitives in semantically coupled banks.
#
# Example: "sad" = {BAD→(GOOD,-1), FEEL, SOMEONE}
# After propagation: {(GOOD,-1), (FEEL,-1), (SOMEONE,+1)}
# This increases opposition between "happy" and "sad" from 33% to 67%

POLARITY_SCOPE = {
    # When GOOD appears with negative polarity (i.e., BAD was canonicalized):
    # - Infect MENTAL bank: emotions inherit the negative valence
    # - Infect EVALUATORS bank: other evaluative terms also flip
    "GOOD": [SemanticBank.MENTAL, SemanticBank.EVALUATORS],

    # When BIG appears with negative polarity (i.e., SMALL was canonicalized):
    # - Infect DETERMINERS bank: quantity-related terms flip
    "BIG": [SemanticBank.DETERMINERS],

    # When LIVE appears with negative polarity (i.e., DIE was canonicalized):
    # - Infect ACTION bank: action-related terms flip
    "LIVE": [SemanticBank.ACTION],

    # When ABOVE appears with negative polarity (i.e., BELOW was canonicalized):
    # - Infect SPATIAL bank: other spatial terms inherit orientation
    "ABOVE": [SemanticBank.SPATIAL],

    # When BEFORE appears with negative polarity (i.e., AFTER was canonicalized):
    # - Infect TEMPORAL bank: temporal terms inherit direction
    "BEFORE": [SemanticBank.TEMPORAL],

    # When FAR appears with negative polarity (i.e., NEAR was canonicalized):
    # - Infect SPATIAL bank: spatial proximity terms flip
    "FAR": [SemanticBank.SPATIAL],
}


def canonicalize_decomposition(decomp: List[Tuple]) -> List[PrimitiveActivation]:
    """
    Convert decomposition to canonical polarity form.

    Ensures antonyms share the same primitive with opposite polarity:
    - "happy" → [(GOOD, evaluation, +1), (FEEL, experiencer, +1), ...]
    - "sad"   → [(GOOD, evaluation, -1), (FEEL, experiencer, +1), ...]

    Now cosine(happy, sad) ≈ -0.7 (opposites) instead of ≈ 0 (unrelated)
    """
    result = []
    for item in decomp:
        if len(item) == 2:
            prim, role = item
            polarity = Polarity.POSITIVE
        elif len(item) == 3:
            prim, role, pol = item
            polarity = Polarity(pol) if isinstance(pol, int) else pol
        else:
            continue  # Skip malformed entries

        # Canonicalize: convert BAD → GOOD with negative polarity
        if prim in ANTONYM_CANONICAL:
            canonical_prim, canonical_pol = ANTONYM_CANONICAL[prim]
            # Multiply polarities: neg * neg = pos, pos * neg = neg
            final_pol = Polarity(int(polarity) * int(canonical_pol))
            result.append(PrimitiveActivation(canonical_prim, role, final_pol))
        else:
            result.append(PrimitiveActivation(prim, role, polarity))

    return result


def propagate_polarity(activations: List[PrimitiveActivation]) -> List[PrimitiveActivation]:
    """
    Propagate negative polarity to semantically coupled primitives.

    When a primitive with negative polarity is detected, it "infects"
    co-occurring primitives from related semantic banks.

    Before: "sad" = {(GOOD, -1), (FEEL, +1), (SOMEONE, +1)}
    After:  "sad" = {(GOOD, -1), (FEEL, -1), (SOMEONE, +1)}

    Result: "happy" vs "sad" now has 2/3 opposition instead of 1/3,
    producing negative cosine similarity (clear antonyms).

    Args:
        activations: List of primitive activations from canonicalize_decomposition

    Returns:
        List of primitive activations with propagated polarity
    """
    if not activations:
        return activations

    # Find primitives with negative polarity that have scope rules
    infected_banks = set()
    for activation in activations:
        if activation.polarity == Polarity.NEGATIVE:
            if activation.primitive in POLARITY_SCOPE:
                infected_banks.update(POLARITY_SCOPE[activation.primitive])

    # If no infection, return unchanged
    if not infected_banks:
        return activations

    # Flip primitives in infected banks
    result = []
    for activation in activations:
        prim_bank = PRIMITIVE_TO_BANK.get(activation.primitive)

        if prim_bank is not None:
            bank_enum = SemanticBank(prim_bank)

            # If this primitive's bank is infected and it's currently positive, flip it
            if bank_enum in infected_banks and activation.polarity == Polarity.POSITIVE:
                result.append(PrimitiveActivation(
                    activation.primitive,
                    activation.role,
                    Polarity.NEGATIVE
                ))
            else:
                result.append(activation)
        else:
            # Unknown primitive, keep as-is
            result.append(activation)

    return result


def full_canonicalize(decomp: List[Tuple]) -> List[PrimitiveActivation]:
    """
    Full canonicalization with polarity propagation.

    This is the main entry point for processing decompositions:
    1. Canonicalize antonym primitives (BAD → GOOD with negative polarity)
    2. Propagate negative polarity to semantically coupled banks

    Result: Antonym pairs produce vectors with high opposition,
    leading to negative cosine similarity.
    """
    # Step 1: Basic canonicalization
    canonical = canonicalize_decomposition(decomp)

    # Step 2: Propagate polarity to coupled banks
    propagated = propagate_polarity(canonical)

    return propagated

# =============================================================================
# INTENSITY MODIFIERS
# =============================================================================
# Used to scale the strength of semantic components

INTENSITY_LEVELS = {
    "extreme_high": 1.5,    # "extremely", "utterly"
    "high": 1.25,           # "very", "really"
    "moderate": 1.0,        # default/unmarked
    "low": 0.75,            # "somewhat", "slightly"
    "minimal": 0.5,         # "barely", "hardly"
}

# Words that signal intensity modifications
INTENSITY_MARKERS = {
    "extremely": "extreme_high",
    "utterly": "extreme_high",
    "completely": "extreme_high",
    "very": "high",
    "really": "high",
    "quite": "high",
    "fairly": "moderate",
    "rather": "moderate",
    "somewhat": "low",
    "slightly": "low",
    "a bit": "low",
    "barely": "minimal",
    "hardly": "minimal",
    "scarcely": "minimal",
}

# =============================================================================
# ASPECT MARKERS
# =============================================================================
# Grammatical aspect affects meaning composition

ASPECT_TYPES = {
    "perfective": "completed",      # "ate", "ran"
    "imperfective": "ongoing",      # "eating", "running"
    "inchoative": "beginning",      # "started to"
    "cessative": "ending",          # "stopped"
    "iterative": "repeated",        # "kept doing"
    "habitual": "regular",          # "used to"
}

# =============================================================================
# MORPHOLOGICAL AFFIXES
# =============================================================================
# Productive prefixes and suffixes with semantic effects

PREFIXES = {
    "un-": [("NOT", "state")],              # unhappy = NOT happy
    "dis-": [("NOT", "state")],             # disagree = NOT agree
    "in-": [("NOT", "state")],              # incomplete = NOT complete
    "im-": [("NOT", "state")],              # impossible = NOT possible
    "il-": [("NOT", "state")],              # illegal = NOT legal
    "ir-": [("NOT", "state")],              # irregular = NOT regular
    "non-": [("NOT", "attribute")],         # non-toxic = NOT toxic
    "anti-": [("NOT", "evaluation"), ("BAD", "evaluation")],  # anti-war
    "re-": [("AGAIN", "aspect")],           # redo = do AGAIN (need AGAIN primitive?)
    "pre-": [("BEFORE", "time")],           # prehistoric = BEFORE history
    "post-": [("AFTER", "time")],           # postwar = AFTER war
    "over-": [("MORE", "degree"), ("MUCH", "intensity")],  # overeat = eat MUCH
    "under-": [("LITTLE", "degree")],       # underestimate = estimate LITTLE
    "mis-": [("BAD", "manner"), ("NOT", "manner")],  # misunderstand
    "out-": [("MORE", "degree")],           # outrun = run MORE than
    "super-": [("VERY", "intensity"), ("BIG", "degree")],  # superhuman
    "ultra-": [("VERY", "intensity")],      # ultrafine
    "semi-": [("PART", "degree")],          # semicircle = PART of circle
    "multi-": [("MUCH", "quantity")],       # multicolor = MUCH color
    "co-": [("SAME", "manner")],            # coexist = exist SAME time
}

SUFFIXES = {
    "-ness": "nominalization",      # happy → happiness (state noun)
    "-ity": "nominalization",       # able → ability
    "-ment": "nominalization",      # develop → development
    "-tion": "nominalization",      # act → action
    "-er": "agent",                 # teach → teacher (SOMEONE who teaches)
    "-or": "agent",                 # act → actor
    "-ist": "agent",                # art → artist
    "-ee": "patient",               # employ → employee (SOMEONE employed)
    "-able": "possibility",         # read → readable (CAN be read)
    "-ible": "possibility",
    "-ful": "having",               # hope → hopeful (HAVE hope)
    "-less": "lacking",             # hope → hopeless (NOT HAVE hope)
    "-ly": "manner",                # quick → quickly (adverb)
    "-ize": "causative",            # modern → modernize (MAKE modern)
    "-ify": "causative",            # simple → simplify
    "-en": "causative",             # bright → brighten
}
