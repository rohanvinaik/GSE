"""
Numeral Encoding Definitions for GSE Sentence-Scope System

Design principle (Two Orthogonal Systems):

System 1: SING/ZERO (Existence)
- Encodes presence/absence of a singular entity
- SING=1 -> exists as one
- ZERO=1 -> non-existence (with negative modifier on SING)

System 2: PLUR/ZERO (Multiplicity)
- Encodes presence/absence of multiples
- PLUR=1 -> more than one
- ZERO=1 -> no multiples (with negative modifier on PLUR)

Mutual Transparency Rule:
- If SING=1 and PLUR=0 -> exactly one
- If SING=1 and PLUR=1 -> at least one, with multiplicity
- If ZERO=1 -> neither SING nor PLUR can be 1

Numbers are encoded as iterative modifiers on SING primitive:
- 1 = SING
- 2 = SING + PLUR + HIER_PLUS=1
- 3 = SING + PLUR + HIER_PLUS=2
- etc.

This is intentionally inefficient for large numbers (NLP-focused, not math-focused).
"""

from typing import Any, Dict

# ============================================================
# NUMERAL ENCODINGS
# ============================================================

# Each entry contains:
# - primitives: SING, PLUR, ZERO combinations
# - hierarchy: Optional scale position (direction, level)
# - quantity_type: cardinal, ordinal, fraction, multiplier

NUMERAL_ENCODINGS: Dict[str, Dict[str, Any]] = {
    # ========================================
    # Zero / None (absence)
    # ========================================
    "0": {
        "primitives": {"ZERO": 1, "NUMBER": 1},
        "hierarchy": None,
        "quantity_type": "cardinal",
    },
    "zero": {
        "primitives": {"ZERO": 1, "NUMBER": 1},
        "hierarchy": None,
        "quantity_type": "cardinal",
    },
    "none": {
        "primitives": {"ZERO": 1},
        "hierarchy": None,
        "quantity_type": "quantifier",
    },
    "no": {  # As in "no apples"
        "primitives": {"ZERO": 1},
        "hierarchy": None,
        "quantity_type": "quantifier",
    },
    # ========================================
    # One (singular existence)
    # ========================================
    "1": {
        "primitives": {"SING": 1, "ONE": 1, "NUMBER": 1},
        "hierarchy": None,
        "quantity_type": "cardinal",
    },
    "one": {
        "primitives": {"SING": 1, "ONE": 1, "NUMBER": 1},
        "hierarchy": None,
        "quantity_type": "cardinal",
    },
    "a": {  # Indefinite article = one
        "primitives": {"SING": 1},
        "hierarchy": None,
        "quantity_type": "article",
    },
    "an": {
        "primitives": {"SING": 1},
        "hierarchy": None,
        "quantity_type": "article",
    },
    "single": {
        "primitives": {"SING": 1, "ONE": 1, "NUMBER": 1},
        "hierarchy": None,
        "quantity_type": "adjective",
    },
    # ========================================
    # Small Cardinals (2-5)
    # Encoded as SING + PLUR + iterative hierarchy
    # ========================================
    "2": {
        "primitives": {"SING": 1, "PLUR": 1, "TWO": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "cardinal",
    },
    "two": {
        "primitives": {"SING": 1, "PLUR": 1, "TWO": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "cardinal",
    },
    "3": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "cardinal",
    },
    "three": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "cardinal",
    },
    "4": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "cardinal",
    },
    "four": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "cardinal",
    },
    "5": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "cardinal",
    },
    "five": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "cardinal",
    },
    # ========================================
    # Medium Cardinals (6-10)
    # ========================================
    "6": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "six": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "7": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "seven": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "8": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "eight": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "9": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "nine": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "cardinal",
    },
    "10": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "cardinal",
    },
    "ten": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "cardinal",
    },
    # ========================================
    # Larger Cardinals (11-20)
    # ========================================
    "eleven": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "cardinal",
    },
    "twelve": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "cardinal",
    },
    "thirteen": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "cardinal",
    },
    "twenty": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "cardinal",
    },
    # ========================================
    # Large Cardinals (100+)
    # ========================================
    "hundred": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "cardinal",
    },
    "thousand": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "cardinal",
    },
    "million": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "cardinal",
    },
    "billion": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "cardinal",
    },
    # ========================================
    # Quantifiers (unspecified amounts)
    # ========================================
    "few": {
        "primitives": {"PLUR": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": -1, "level": 2},
        "quantity_type": "quantifier",
    },
    "several": {
        "primitives": {"PLUR": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "quantifier",
    },
    "some": {
        "primitives": {"PLUR": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "quantifier",
    },
    "many": {
        "primitives": {"PLUR": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "quantifier",
    },
    "much": {
        "primitives": {"SING": 1},  # Uncountable
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 3},
        "quantity_type": "quantifier",
    },
    "most": {
        "primitives": {"PLUR": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 4},
        "quantity_type": "quantifier",
    },
    "all": {
        "primitives": {"PLUR": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "quantifier",
    },
    "every": {
        "primitives": {"SING": 1, "PLUR": 1},  # Distributive
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "quantifier",
    },
    "each": {
        "primitives": {"SING": 1},  # Singular distributive
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "quantifier",
    },
    "both": {
        "primitives": {"SING": 1, "PLUR": 1, "TWO": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "quantifier",
    },
    # ========================================
    # Ordinals
    # ========================================
    "first": {
        "primitives": {"SING": 1, "ONE": 1, "NUMBER": 1},
        "hierarchy": None,
        "quantity_type": "ordinal",
    },
    "second": {
        "primitives": {"SING": 1, "PLUR": 1, "TWO": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "ordinal",
    },
    # "third" (ordinal) — SHADOWED, kept verbatim for the record. It was written twice (ordinal here,
    # fraction below) and a dict literal keeps only the LAST value, so the fraction has always been the
    # one in effect. This schema holds one encoding per word and the two senses conflict on every key,
    # so which sense "third" carries (or a per-sense schema) is an open decision for the closed-class
    # build (#9). The ordinal encoding as authored:
    #   "third": {"primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
    #             "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
    #             "quantity_type": "ordinal"},
    "last": {
        "primitives": {"SING": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 5},
        "quantity_type": "ordinal",
    },
    # ========================================
    # Fractions
    # ========================================
    "half": {
        "primitives": {"SING": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": -1, "level": 2},
        "quantity_type": "fraction",
    },
    "quarter": {
        "primitives": {"SING": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": -1, "level": 3},
        "quantity_type": "fraction",
    },
    "third": {  # As fraction (distinct from ordinal)
        "primitives": {"SING": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": -1, "level": 2},
        "quantity_type": "fraction",
    },
    # ========================================
    # Multipliers
    # ========================================
    "double": {
        "primitives": {"SING": 1, "PLUR": 1, "TWO": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 1},
        "quantity_type": "multiplier",
    },
    "triple": {
        "primitives": {"SING": 1, "PLUR": 1, "NUMBER": 1},
        "hierarchy": {"scale": "QUANTITY", "direction": 1, "level": 2},
        "quantity_type": "multiplier",
    },
}


def get_numeral_encoding(word: str) -> Dict[str, Any] | None:
    """Get encoding for a numeral, or None if not found."""
    return NUMERAL_ENCODINGS.get(word.lower())


def is_numeral(word: str) -> bool:
    """Check if a word is a defined numeral."""
    return word.lower() in NUMERAL_ENCODINGS


def get_all_numerals() -> list:
    """Get list of all defined numerals."""
    return list(NUMERAL_ENCODINGS.keys())


def validate_mutual_transparency(primitives: Dict[str, int]) -> bool:
    """
    Validate the SING/PLUR/ZERO mutual transparency rule.

    Returns True if encoding is valid, False otherwise.
    """
    sing = primitives.get("SING", 0)
    plur = primitives.get("PLUR", 0)
    zero = primitives.get("ZERO", 0)

    # If ZERO=1, neither SING nor PLUR can be 1
    if zero == 1 and (sing == 1 or plur == 1):
        return False

    return True
