"""
Primitive Rules Module

Handles primitives that can be inferred without LLM:
1. Bipolar pairs (BAD from GOOD, SMALL from BIG, etc.)
2. Grammatical/closed-class words (I, YOU, ONE, TWO, SING, PLUR)
3. Defaults for primitives with no source coverage

This reduces LLM calls while maintaining quality through principled rules.
"""

from typing import Optional, Dict, Set


# =============================================================================
# BIPOLAR PRIMITIVE PAIRS
# =============================================================================
# These primitives are semantic opposites. If we know one, we can infer the other.
# Logic: If GOOD=+1, then BAD=-1. If GOOD=-1, then BAD=+1. If GOOD=0, BAD=0.

BIPOLAR_PAIRS = {
    # (primary, opposite) - we typically have data for primary
    "BAD": "GOOD",      # BAD = -GOOD
    "SMALL": "BIG",     # SMALL = -BIG
    "DEAD": "ALIVE",    # DEAD = -ALIVE (also: DEAD = -LIVE in some contexts)
    "FALSE": "TRUE",    # FALSE = -TRUE
}

# Reverse mapping for lookup
BIPOLAR_PRIMARIES = {v: k for k, v in BIPOLAR_PAIRS.items()}


def infer_bipolar(
    primitive: str,
    known_values: Dict[str, int]
) -> Optional[int]:
    """
    Infer a bipolar primitive from its opposite.

    Args:
        primitive: The primitive to infer (e.g., "BAD")
        known_values: Dict of primitive -> value for known primitives

    Returns:
        Inferred value (+1, 0, -1) or None if cannot infer
    """
    if primitive in BIPOLAR_PAIRS:
        opposite = BIPOLAR_PAIRS[primitive]
        if opposite in known_values:
            # Negate the opposite value
            return -known_values[opposite]

    return None


def get_bipolar_opposite(primitive: str) -> Optional[str]:
    """Get the opposite of a bipolar primitive."""
    if primitive in BIPOLAR_PAIRS:
        return BIPOLAR_PAIRS[primitive]
    if primitive in BIPOLAR_PRIMARIES:
        return BIPOLAR_PRIMARIES[primitive]
    return None


# =============================================================================
# GRAMMATICAL / CLOSED-CLASS PRIMITIVES
# =============================================================================
# These primitives apply only to specific closed-class words.
# No LLM needed - just check membership in a list.

GRAMMATICAL_PRIMITIVES = {
    # First person pronouns
    "I": {
        "words": {"i", "me", "my", "mine", "myself"},
        "value": 1,
        "description": "First person reference"
    },
    # Second person pronouns
    "YOU": {
        "words": {"you", "your", "yours", "yourself", "yourselves"},
        "value": 1,
        "description": "Second person reference"
    },
    # Singular number markers
    "ONE": {
        "words": {"one", "a", "an", "single", "sole", "only", "1", "first"},
        "value": 1,
        "description": "Singular quantity"
    },
    # Dual/pair markers
    "TWO": {
        "words": {"two", "both", "pair", "couple", "2", "second", "twice", "double"},
        "value": 1,
        "description": "Dual quantity"
    },
    # Zero/none markers
    "ZERO": {
        "words": {"zero", "none", "no", "nothing", "nil", "0", "neither"},
        "value": 1,
        "description": "Zero quantity or absence"
    },
}

# POS-based grammatical rules
POS_GRAMMATICAL_RULES = {
    # Singular nouns get SING=1
    "SING": {
        "pos_patterns": ["NN", "NNP"],  # Singular noun, proper noun singular
        "value": 1,
    },
    # Plural nouns get PLUR=1
    "PLUR": {
        "pos_patterns": ["NNS", "NNPS"],  # Plural noun, proper noun plural
        "value": 1,
    },
}


def apply_grammatical_rule(
    primitive: str,
    lemma: str,
    pos: str = None
) -> Optional[int]:
    """
    Apply grammatical rules for closed-class primitives.

    Args:
        primitive: The primitive to check
        lemma: The word (lowercased)
        pos: Part of speech tag (optional)

    Returns:
        Value (usually 1) if rule applies, None otherwise
    """
    lemma_lower = lemma.lower()

    # Check word-based rules
    if primitive in GRAMMATICAL_PRIMITIVES:
        rule = GRAMMATICAL_PRIMITIVES[primitive]
        if lemma_lower in rule["words"]:
            return rule["value"]
        return 0  # Doesn't apply to this word

    # Check POS-based rules
    if primitive in POS_GRAMMATICAL_RULES and pos:
        rule = POS_GRAMMATICAL_RULES[primitive]
        if pos in rule["pos_patterns"]:
            return rule["value"]
        return 0  # POS doesn't match

    return None  # Not a grammatical primitive


def is_grammatical_primitive(primitive: str) -> bool:
    """Check if a primitive is handled by grammatical rules."""
    return primitive in GRAMMATICAL_PRIMITIVES or primitive in POS_GRAMMATICAL_RULES


# =============================================================================
# PRIMITIVES WITH NO SOURCE COVERAGE
# =============================================================================
# These primitives have no external source data and no inference rules.
# For these, we default to 0 (neutral) rather than calling the LLM with no context.

UNCOVERED_PRIMITIVES = {
    # These have no good external data source and aren't inferrable
    # LLM would be guessing without context - better to mark as unknown
    "KIND",       # Taxonomic - hard to get from word alone
    "IF",         # Conditional logic - context-dependent
    "HIER_PLUS",  # Hierarchy direction - needs sentence context
    "HIER_MINUS", # Hierarchy direction - needs sentence context
    "AGREE",      # Agreement - context-dependent
}


def get_default_for_uncovered(primitive: str) -> Optional[int]:
    """
    Get default value for primitives with no source coverage.

    Returns 0 (neutral) for uncovered primitives rather than
    calling LLM with no context to translate.
    """
    if primitive in UNCOVERED_PRIMITIVES:
        return 0
    return None


# =============================================================================
# MAIN INFERENCE FUNCTION
# =============================================================================

def infer_primitive_value(
    primitive: str,
    lemma: str,
    pos: str,
    known_values: Dict[str, int],
    source_has_data: bool = False
) -> tuple[Optional[int], str]:
    """
    Try to infer a primitive value without LLM.

    Args:
        primitive: The primitive to infer
        lemma: The word
        pos: Part of speech
        known_values: Dict of already-known primitive values
        source_has_data: Whether external sources have data for this primitive

    Returns:
        Tuple of (value, method) where:
        - value is +1/0/-1 or None if LLM needed
        - method is "bipolar", "grammatical", "default", or "llm_needed"
    """
    # 1. Try bipolar inference first (most reliable)
    value = infer_bipolar(primitive, known_values)
    if value is not None:
        return (value, "bipolar")

    # 2. Try grammatical rules
    value = apply_grammatical_rule(primitive, lemma, pos)
    if value is not None:
        return (value, "grammatical")

    # 3. If sources have data, LLM should translate it
    if source_has_data:
        return (None, "llm_needed")

    # 4. Check if this is an uncovered primitive
    value = get_default_for_uncovered(primitive)
    if value is not None:
        return (value, "default_uncovered")

    # 5. No rule applies and no source data - LLM would be guessing
    # Default to 0 (neutral) rather than unreliable LLM guess
    return (0, "default_no_context")


# =============================================================================
# STATISTICS
# =============================================================================

def get_rule_coverage_stats() -> Dict:
    """Get statistics on how many primitives are covered by rules."""
    return {
        "bipolar_pairs": len(BIPOLAR_PAIRS),
        "grammatical_word_based": len(GRAMMATICAL_PRIMITIVES),
        "grammatical_pos_based": len(POS_GRAMMATICAL_RULES),
        "uncovered_defaults": len(UNCOVERED_PRIMITIVES),
        "total_rule_based": (
            len(BIPOLAR_PAIRS) +
            len(GRAMMATICAL_PRIMITIVES) +
            len(POS_GRAMMATICAL_RULES) +
            len(UNCOVERED_PRIMITIVES)
        ),
    }


if __name__ == "__main__":
    # Test the module
    print("Primitive Rules Module Test")
    print("=" * 50)

    stats = get_rule_coverage_stats()
    print(f"\nRule coverage stats:")
    for key, val in stats.items():
        print(f"  {key}: {val}")

    # Test bipolar inference
    print("\n\nBipolar inference tests:")
    known = {"GOOD": 1, "BIG": -1, "ALIVE": 1}
    for prim in ["BAD", "SMALL", "DEAD"]:
        val = infer_bipolar(prim, known)
        print(f"  {prim} (opposite has value): {val}")

    # Test grammatical rules
    print("\n\nGrammatical rule tests:")
    test_cases = [
        ("I", "i", "PRP"),
        ("I", "happy", "JJ"),
        ("YOU", "you", "PRP"),
        ("ONE", "single", "JJ"),
        ("SING", "dog", "NN"),
        ("PLUR", "dogs", "NNS"),
    ]
    for prim, lemma, pos in test_cases:
        val = apply_grammatical_rule(prim, lemma, pos)
        print(f"  {prim} for '{lemma}' ({pos}): {val}")

    # Test full inference
    print("\n\nFull inference tests:")
    test_cases = [
        ("BAD", "evil", "JJ", {"GOOD": -1}, False),
        ("I", "i", "PRP", {}, False),
        ("KIND", "type", "NN", {}, False),
        ("MOVE", "run", "VB", {}, True),  # Has source data
    ]
    for prim, lemma, pos, known, has_data in test_cases:
        val, method = infer_primitive_value(prim, lemma, pos, known, has_data)
        print(f"  {prim} for '{lemma}': value={val}, method={method}")
