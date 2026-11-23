"""
Pronoun Encoding Definitions for GSE Sentence-Scope System

Design principle:
- All pronouns share SOMEONE=1 (or SOMETHING=1 for "it/what")
- Differentiation happens via grammatical features
- This enables cosine similarity ~1.0 at word level for I/you/he/she
- Sentence-level parsing uses gram features to distinguish

The informational zero concept:
- "I" and "you" differ only in person (1 vs 2)
- At the word level, both mean "a person" = SOMEONE
- At the sentence level, person feature determines reference
"""

from typing import Any, Dict

# ============================================================
# PRONOUN ENCODINGS
# ============================================================

# Each entry contains:
# - primitives: Semantic primitives (SOMEONE or SOMETHING)
# - gram: Grammatical features (person, number, gender, case, reflexivity)
# - animacy: ANIMATE or INANIMATE

PRONOUN_ENCODINGS: Dict[str, Dict[str, Any]] = {
    # ========================================
    # First Person
    # ========================================
    "i": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "SINGULAR", "case": "NOM"},
        "animacy": "ANIMATE",
    },
    "me": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "SINGULAR", "case": "ACC"},
        "animacy": "ANIMATE",
    },
    "my": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "SINGULAR", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "mine": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "SINGULAR", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "myself": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "SINGULAR", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    "we": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "PLURAL", "case": "NOM"},
        "animacy": "ANIMATE",
    },
    "us": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "PLURAL", "case": "ACC"},
        "animacy": "ANIMATE",
    },
    "our": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "PLURAL", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "ours": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "PLURAL", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "ourselves": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 1, "number": "PLURAL", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    # ========================================
    # Second Person
    # ========================================
    "you": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 2, "case": "NOM"},  # number ambiguous in English
        "animacy": "ANIMATE",
    },
    "your": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 2, "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "yours": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 2, "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "yourself": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 2, "number": "SINGULAR", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    "yourselves": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 2, "number": "PLURAL", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    # ========================================
    # Third Person Masculine
    # ========================================
    "he": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "MASC", "case": "NOM"},
        "animacy": "ANIMATE",
    },
    "him": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "MASC", "case": "ACC"},
        "animacy": "ANIMATE",
    },
    "his": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "MASC", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "himself": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "MASC", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    # ========================================
    # Third Person Feminine
    # ========================================
    "she": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "FEM", "case": "NOM"},
        "animacy": "ANIMATE",
    },
    "her": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "FEM", "case": "ACC"},  # Also GEN, handled separately
        "animacy": "ANIMATE",
    },
    "hers": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "FEM", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "herself": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "FEM", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    # ========================================
    # Third Person Neuter (it)
    # ========================================
    "it": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "NEUT"},
        "animacy": "INANIMATE",
    },
    "its": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "NEUT", "case": "GEN"},
        "animacy": "INANIMATE",
    },
    "itself": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR", "gender": "NEUT", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "INANIMATE",
    },
    # ========================================
    # Third Person Plural (they)
    # ========================================
    "they": {
        "primitives": {"SOMEONE": 1},  # Can also be SOMETHING for inanimate plural
        "gram": {"person": 3, "number": "PLURAL", "case": "NOM"},
        "animacy": "ANIMATE",
    },
    "them": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "PLURAL", "case": "ACC"},
        "animacy": "ANIMATE",
    },
    "their": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "PLURAL", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "theirs": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "PLURAL", "case": "GEN"},
        "animacy": "ANIMATE",
    },
    "themselves": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "PLURAL", "case": "ACC", "reflexivity": "REFLEXIVE"},
        "animacy": "ANIMATE",
    },
    # ========================================
    # Interrogative/Relative Pronouns
    # ========================================
    "who": {
        "primitives": {"SOMEONE": 1},
        "gram": {"case": "NOM"},
        "animacy": "ANIMATE",
        "is_interrogative": True,
    },
    "whom": {
        "primitives": {"SOMEONE": 1},
        "gram": {"case": "ACC"},
        "animacy": "ANIMATE",
        "is_interrogative": True,
    },
    "whose": {
        "primitives": {"SOMEONE": 1},
        "gram": {"case": "GEN"},
        "animacy": "ANIMATE",
        "is_interrogative": True,
    },
    "what": {
        "primitives": {"SOMETHING": 1},
        "gram": {"gender": "NEUT"},
        "animacy": "INANIMATE",
        "is_interrogative": True,
    },
    "which": {
        "primitives": {"SOMETHING": 1},
        "gram": {},
        "animacy": "INANIMATE",
        "is_interrogative": True,
    },
    "whoever": {
        "primitives": {"SOMEONE": 1},
        "gram": {"case": "NOM"},
        "animacy": "ANIMATE",
    },
    "whomever": {
        "primitives": {"SOMEONE": 1},
        "gram": {"case": "ACC"},
        "animacy": "ANIMATE",
    },
    "whatever": {
        "primitives": {"SOMETHING": 1},
        "gram": {},
        "animacy": "INANIMATE",
    },
    "whichever": {
        "primitives": {"SOMETHING": 1},
        "gram": {},
        "animacy": "INANIMATE",
    },
    # ========================================
    # Indefinite Pronouns
    # ========================================
    "someone": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "ANIMATE",
    },
    "somebody": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "ANIMATE",
    },
    "anyone": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "ANIMATE",
    },
    "anybody": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "ANIMATE",
    },
    "everyone": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR"},  # Syntactically singular
        "animacy": "ANIMATE",
    },
    "everybody": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "ANIMATE",
    },
    "no one": {
        "primitives": {"SOMEONE": 1},  # With ZERO context
        "gram": {"person": 3, "number": "SINGULAR", "polarity": "NEGATIVE"},
        "animacy": "ANIMATE",
    },
    "nobody": {
        "primitives": {"SOMEONE": 1},
        "gram": {"person": 3, "number": "SINGULAR", "polarity": "NEGATIVE"},
        "animacy": "ANIMATE",
    },
    "something": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "INANIMATE",
    },
    "anything": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "INANIMATE",
    },
    "everything": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR"},
        "animacy": "INANIMATE",
    },
    "nothing": {
        "primitives": {"SOMETHING": 1},
        "gram": {"person": 3, "number": "SINGULAR", "polarity": "NEGATIVE"},
        "animacy": "INANIMATE",
    },
    # ========================================
    # Demonstrative Pronouns
    # ========================================
    "this": {
        "primitives": {"SOMETHING": 1},
        "gram": {"number": "SINGULAR", "deixis": "PROXIMAL"},
        "animacy": "INANIMATE",
    },
    "that": {
        "primitives": {"SOMETHING": 1},
        "gram": {"number": "SINGULAR", "deixis": "DISTAL"},
        "animacy": "INANIMATE",
    },
    "these": {
        "primitives": {"SOMETHING": 1},
        "gram": {"number": "PLURAL", "deixis": "PROXIMAL"},
        "animacy": "INANIMATE",
    },
    "those": {
        "primitives": {"SOMETHING": 1},
        "gram": {"number": "PLURAL", "deixis": "DISTAL"},
        "animacy": "INANIMATE",
    },
    # ========================================
    # Reciprocal Pronouns
    # ========================================
    "each other": {
        "primitives": {"SOMEONE": 1},
        "gram": {"number": "PLURAL", "reflexivity": "RECIPROCAL"},
        "animacy": "ANIMATE",
    },
    "one another": {
        "primitives": {"SOMEONE": 1},
        "gram": {"number": "PLURAL", "reflexivity": "RECIPROCAL"},
        "animacy": "ANIMATE",
    },
}


def get_pronoun_encoding(word: str) -> Dict[str, Any] | None:
    """Get encoding for a pronoun, or None if not found."""
    return PRONOUN_ENCODINGS.get(word.lower())


def is_pronoun(word: str) -> bool:
    """Check if a word is a defined pronoun."""
    return word.lower() in PRONOUN_ENCODINGS


def get_all_pronouns() -> list:
    """Get list of all defined pronouns."""
    return list(PRONOUN_ENCODINGS.keys())
