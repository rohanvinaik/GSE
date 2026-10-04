"""
Modifier Hierarchy System for GSE Sentence-Scope Encoding

Four core scales, each with 11 positions (-5 to +5):

1. INTENSITY Scale
   -5: not at all     0: [neutral]     +5: absolutely
   -3: slightly       +2: very
   -1: somewhat       +4: extremely

2. QUANTITY Scale
   -5: none           0: [neutral]     +5: all
   -3: few            +2: many
   -1: some           +4: most

3. CERTAINTY Scale
   -5: impossible     0: [neutral]     +5: certainly
   -3: unlikely       +2: probably
   -1: maybe          +4: definitely

4. FREQUENCY Scale
   -5: never          0: [neutral]     +5: always
   -3: rarely         +2: often
   -1: sometimes      +4: usually

Stack Operation Encoding:
- Base primitive: INTENSITY, QUANTITY, CERTAINTY, or FREQUENCY
- Direction: -1 or +1
- Level: 1-5

Example: "very" = INTENSITY with direction=+1, level=2
"""

from typing import Any, Dict

# ============================================================
# INTENSITY SCALE WORDS
# ============================================================

INTENSITY_WORDS: Dict[str, Dict[str, Any]] = {
    # Maximum negative
    "not at all": {"direction": -1, "level": 5},
    # High negative
    "barely": {"direction": -1, "level": 4},
    "hardly": {"direction": -1, "level": 4},
    "scarcely": {"direction": -1, "level": 4},
    # Medium negative
    "slightly": {"direction": -1, "level": 3},
    "a little": {"direction": -1, "level": 3},
    "a bit": {"direction": -1, "level": 3},
    "mildly": {"direction": -1, "level": 3},
    # Low negative
    "somewhat": {"direction": -1, "level": 2},
    "rather": {"direction": -1, "level": 2},
    "fairly": {"direction": -1, "level": 2},
    "kind of": {"direction": -1, "level": 2},
    "sort of": {"direction": -1, "level": 2},
    # Slight negative
    "moderately": {"direction": -1, "level": 1},
    # Low positive
    "quite": {"direction": 1, "level": 1},
    "pretty": {"direction": 1, "level": 1},
    # Medium positive
    "very": {"direction": 1, "level": 2},
    "really": {"direction": 1, "level": 2},
    "truly": {"direction": 1, "level": 2},
    # High positive
    "highly": {"direction": 1, "level": 3},
    "greatly": {"direction": 1, "level": 3},
    "deeply": {"direction": 1, "level": 3},
    "immensely": {"direction": 1, "level": 3},
    # Very high positive
    "extremely": {"direction": 1, "level": 4},
    "incredibly": {"direction": 1, "level": 4},
    "extraordinarily": {"direction": 1, "level": 4},
    "tremendously": {"direction": 1, "level": 4},
    # Maximum positive
    "absolutely": {"direction": 1, "level": 5},
    "utterly": {"direction": 1, "level": 5},
    "completely": {"direction": 1, "level": 5},
    "totally": {"direction": 1, "level": 5},
    "perfectly": {"direction": 1, "level": 5},
    "entirely": {"direction": 1, "level": 5},
}


# ============================================================
# QUANTITY SCALE WORDS
# ============================================================

QUANTITY_WORDS: Dict[str, Dict[str, Any]] = {
    # Maximum negative (none)
    "none": {"direction": -1, "level": 5},
    "zero": {"direction": -1, "level": 5},
    "no": {"direction": -1, "level": 5},
    # High negative
    "almost none": {"direction": -1, "level": 4},
    "barely any": {"direction": -1, "level": 4},
    "hardly any": {"direction": -1, "level": 4},
    # Medium negative
    "few": {"direction": -1, "level": 3},
    "little": {"direction": -1, "level": 3},
    # Low negative
    "some": {"direction": -1, "level": 2},
    "a few": {"direction": -1, "level": 2},
    "a little": {"direction": -1, "level": 2},
    # Slight negative
    "several": {"direction": -1, "level": 1},
    # Low positive
    "many": {"direction": 1, "level": 2},
    "much": {"direction": 1, "level": 2},
    "lots": {"direction": 1, "level": 2},
    "plenty": {"direction": 1, "level": 2},
    # Medium positive
    "a lot": {"direction": 1, "level": 3},
    "lots of": {"direction": 1, "level": 3},
    "numerous": {"direction": 1, "level": 3},
    # High positive
    "most": {"direction": 1, "level": 4},
    "majority": {"direction": 1, "level": 4},
    "nearly all": {"direction": 1, "level": 4},
    "almost all": {"direction": 1, "level": 4},
    # Maximum positive (all)
    "all": {"direction": 1, "level": 5},
    "every": {"direction": 1, "level": 5},
    "each": {"direction": 1, "level": 5},
    "entire": {"direction": 1, "level": 5},
    "complete": {"direction": 1, "level": 5},
    "whole": {"direction": 1, "level": 5},
}


# ============================================================
# CERTAINTY SCALE WORDS
# ============================================================

CERTAINTY_WORDS: Dict[str, Dict[str, Any]] = {
    # Maximum negative (impossible)
    "impossible": {"direction": -1, "level": 5},
    "inconceivable": {"direction": -1, "level": 5},
    # High negative
    "very unlikely": {"direction": -1, "level": 4},
    "doubtful": {"direction": -1, "level": 4},
    "improbable": {"direction": -1, "level": 4},
    # Medium negative
    "unlikely": {"direction": -1, "level": 3},
    # Low negative
    "possibly": {"direction": -1, "level": 2},
    "conceivably": {"direction": -1, "level": 2},
    # Slight negative
    "perhaps": {"direction": -1, "level": 1},
    "maybe": {"direction": -1, "level": 1},
    "might": {"direction": -1, "level": 1},
    # Low positive
    "likely": {"direction": 1, "level": 1},
    # Medium positive
    "probably": {"direction": 1, "level": 2},
    # High positive
    "very likely": {"direction": 1, "level": 3},
    "almost certainly": {"direction": 1, "level": 3},
    # Very high positive
    "certainly": {"direction": 1, "level": 4},
    "surely": {"direction": 1, "level": 4},
    "definitely": {"direction": 1, "level": 4},
    "undoubtedly": {"direction": 1, "level": 4},
    # Maximum positive
    "necessarily": {"direction": 1, "level": 5},
    "absolutely": {"direction": 1, "level": 5},
    "inevitably": {"direction": 1, "level": 5},
}


# ============================================================
# FREQUENCY SCALE WORDS
# ============================================================

FREQUENCY_WORDS: Dict[str, Dict[str, Any]] = {
    # Maximum negative (never)
    "never": {"direction": -1, "level": 5},
    "not once": {"direction": -1, "level": 5},
    # High negative
    "almost never": {"direction": -1, "level": 4},
    "rarely": {"direction": -1, "level": 4},
    "seldom": {"direction": -1, "level": 4},
    "hardly ever": {"direction": -1, "level": 4},
    # Medium negative
    "infrequently": {"direction": -1, "level": 3},
    "occasionally": {"direction": -1, "level": 3},
    # Low negative
    "sometimes": {"direction": -1, "level": 2},
    "now and then": {"direction": -1, "level": 2},
    "from time to time": {"direction": -1, "level": 2},
    # Low positive
    "often": {"direction": 1, "level": 2},
    "frequently": {"direction": 1, "level": 2},
    # Medium positive
    "regularly": {"direction": 1, "level": 3},
    "typically": {"direction": 1, "level": 3},
    # High positive
    "usually": {"direction": 1, "level": 4},
    "generally": {"direction": 1, "level": 4},
    "mostly": {"direction": 1, "level": 4},
    "nearly always": {"direction": 1, "level": 4},
    # Maximum positive (always)
    "always": {"direction": 1, "level": 5},
    "constantly": {"direction": 1, "level": 5},
    "invariably": {"direction": 1, "level": 5},
    "forever": {"direction": 1, "level": 5},
}


# ============================================================
# COMBINED SCALE LOOKUP
# ============================================================

ALL_MODIFIER_SCALES = {
    "INTENSITY": INTENSITY_WORDS,
    "QUANTITY": QUANTITY_WORDS,
    "CERTAINTY": CERTAINTY_WORDS,
    "FREQUENCY": FREQUENCY_WORDS,
}


def get_modifier_encoding(word: str) -> tuple | None:
    """
    Get scale and position for a modifier word.

    Returns (scale, direction, level) or None if not found.
    """
    word_lower = word.lower()

    for scale, words in ALL_MODIFIER_SCALES.items():
        if word_lower in words:
            encoding = words[word_lower]
            return (scale, encoding["direction"], encoding["level"])

    return None


def get_all_modifiers() -> Dict[str, str]:
    """Get all modifier words with their scales."""
    result = {}
    for scale, words in ALL_MODIFIER_SCALES.items():
        for word in words:
            result[word] = scale
    return result
