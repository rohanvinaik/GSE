"""
Function Word Encoding Definitions for GSE Sentence-Scope System

Extends existing OPERATOR classifications with:
1. Definiteness for determiners
2. Clause relations for conjunctions/complementizers
3. Spatial/temporal features for prepositions
"""

from typing import Any, Dict

# ============================================================
# DETERMINER ENCODINGS
# Adds definiteness feature to determiners
# ============================================================

DETERMINER_ENCODINGS: Dict[str, Dict[str, Any]] = {
    # Definite
    "the": {"definiteness": "DEFINITE"},
    # Indefinite
    "a": {"definiteness": "INDEFINITE", "number": "SINGULAR"},
    "an": {"definiteness": "INDEFINITE", "number": "SINGULAR"},
    "some": {"definiteness": "INDEFINITE"},
    "any": {"definiteness": "INDEFINITE"},
    # Demonstrative (proximal)
    "this": {"definiteness": "DEMONSTRATIVE", "deixis": "PROXIMAL", "number": "SINGULAR"},
    "these": {"definiteness": "DEMONSTRATIVE", "deixis": "PROXIMAL", "number": "PLURAL"},
    # Demonstrative (distal)
    "that": {"definiteness": "DEMONSTRATIVE", "deixis": "DISTAL", "number": "SINGULAR"},
    "those": {"definiteness": "DEMONSTRATIVE", "deixis": "DISTAL", "number": "PLURAL"},
    # Universal
    "every": {"definiteness": "UNIVERSAL", "number": "SINGULAR"},
    "each": {"definiteness": "UNIVERSAL", "number": "SINGULAR"},
    "all": {"definiteness": "UNIVERSAL", "number": "PLURAL"},
    "both": {"definiteness": "UNIVERSAL", "number": "DUAL"},
    # Negative
    "no": {"definiteness": "NEGATIVE", "polarity": "NEGATIVE"},
    "neither": {"definiteness": "NEGATIVE", "polarity": "NEGATIVE", "number": "DUAL"},
    # Possessive
    "my": {"definiteness": "POSSESSIVE", "person": 1, "number": "SINGULAR"},
    "your": {"definiteness": "POSSESSIVE", "person": 2},
    "his": {"definiteness": "POSSESSIVE", "person": 3, "gender": "MASC"},
    "her": {"definiteness": "POSSESSIVE", "person": 3, "gender": "FEM"},
    "its": {"definiteness": "POSSESSIVE", "person": 3, "gender": "NEUT"},
    "our": {"definiteness": "POSSESSIVE", "person": 1, "number": "PLURAL"},
    "their": {"definiteness": "POSSESSIVE", "person": 3, "number": "PLURAL"},
    # Interrogative
    "which": {"definiteness": "INTERROGATIVE"},
    "what": {"definiteness": "INTERROGATIVE"},
    "whose": {"definiteness": "INTERROGATIVE"},
}


# ============================================================
# CONJUNCTION/COMPLEMENTIZER ENCODINGS
# Adds clause relation features
# ============================================================

CONJUNCTION_ENCODINGS: Dict[str, Dict[str, Any]] = {
    # Coordinating
    "and": {"clause_relation": "ADDITIVE", "coord_type": "ADDITIVE"},
    "or": {"clause_relation": "ALTERNATIVE", "coord_type": "DISJUNCTIVE"},
    "but": {"clause_relation": "CONTRAST", "coord_type": "ADVERSATIVE"},
    "nor": {"clause_relation": "NEGATIVE_ADDITIVE", "coord_type": "ADDITIVE", "polarity": "NEGATIVE"},
    "yet": {"clause_relation": "CONCESSIVE", "coord_type": "ADVERSATIVE"},
    "so": {"clause_relation": "RESULT", "coord_type": "CAUSAL"},
    "for": {"clause_relation": "REASON", "coord_type": "CAUSAL"},
    # Subordinating - Temporal
    "when": {"clause_relation": "TEMPORAL", "temporal_type": "SIMULTANEOUS"},
    "while": {"clause_relation": "TEMPORAL", "temporal_type": "DURATION"},
    "before": {"clause_relation": "TEMPORAL", "temporal_type": "ANTERIOR"},
    "after": {"clause_relation": "TEMPORAL", "temporal_type": "POSTERIOR"},
    "until": {"clause_relation": "TEMPORAL", "temporal_type": "TERMINUS"},
    "since": {"clause_relation": "TEMPORAL", "temporal_type": "STARTING_POINT"},
    "as": {"clause_relation": "TEMPORAL", "temporal_type": "SIMULTANEOUS"},
    # Subordinating - Causal
    "because": {"clause_relation": "CAUSAL", "causal_type": "REASON"},
    "since": {"clause_relation": "CAUSAL", "causal_type": "REASON"},  # Also temporal
    "although": {"clause_relation": "CONCESSIVE"},
    "though": {"clause_relation": "CONCESSIVE"},
    "even though": {"clause_relation": "CONCESSIVE"},
    # Subordinating - Conditional
    "if": {"clause_relation": "CONDITIONAL", "conditional_type": "HYPOTHETICAL"},
    "unless": {"clause_relation": "CONDITIONAL", "conditional_type": "NEGATIVE"},
    "whether": {"clause_relation": "CONDITIONAL", "conditional_type": "ALTERNATIVE"},
    # Subordinating - Purpose
    "so that": {"clause_relation": "PURPOSE"},
    "in order that": {"clause_relation": "PURPOSE"},
    # Complementizers
    "that": {"clause_relation": "COMPLEMENT", "complement_type": "DECLARATIVE"},
}


# ============================================================
# PREPOSITION ENCODINGS
# Adds spatial/temporal features
# ============================================================

PREPOSITION_ENCODINGS: Dict[str, Dict[str, Any]] = {
    # Spatial - Location
    "in": {"spatial_type": "CONTAINMENT", "temporal_type": "DURATION"},
    "on": {"spatial_type": "SURFACE", "temporal_type": "POINT"},
    "at": {"spatial_type": "POINT", "temporal_type": "POINT"},
    "under": {"spatial_type": "BELOW"},
    "over": {"spatial_type": "ABOVE"},
    "above": {"spatial_type": "ABOVE"},
    "below": {"spatial_type": "BELOW"},
    "between": {"spatial_type": "INTERMEDIATE"},
    "among": {"spatial_type": "DISTRIBUTED"},
    "inside": {"spatial_type": "INTERIOR"},
    "outside": {"spatial_type": "EXTERIOR"},
    "beside": {"spatial_type": "PROXIMATE"},
    "near": {"spatial_type": "PROXIMATE"},
    "behind": {"spatial_type": "POSTERIOR"},
    "before": {"spatial_type": "ANTERIOR", "temporal_type": "ANTERIOR"},
    "after": {"spatial_type": "POSTERIOR", "temporal_type": "POSTERIOR"},
    # Spatial - Direction
    "to": {"spatial_type": "GOAL"},
    "from": {"spatial_type": "SOURCE"},
    "into": {"spatial_type": "GOAL_INTERIOR"},
    "onto": {"spatial_type": "GOAL_SURFACE"},
    "through": {"spatial_type": "PATH"},
    "across": {"spatial_type": "PATH_TRANSVERSE"},
    "along": {"spatial_type": "PATH_PARALLEL"},
    "toward": {"spatial_type": "DIRECTION"},
    "towards": {"spatial_type": "DIRECTION"},
    "away from": {"spatial_type": "DIRECTION_OPPOSITE"},
    # Temporal
    "during": {"temporal_type": "DURATION"},
    "until": {"temporal_type": "TERMINUS"},
    "since": {"temporal_type": "STARTING_POINT"},
    "by": {"temporal_type": "DEADLINE"},
    # Other relations
    "with": {"relation_type": "ACCOMPANIMENT"},
    "without": {"relation_type": "ACCOMPANIMENT", "polarity": "NEGATIVE"},
    "for": {"relation_type": "BENEFACTIVE"},
    "of": {"relation_type": "POSSESSIVE"},
    "about": {"relation_type": "TOPIC"},
    "by": {"relation_type": "AGENT"},  # Also temporal
    "against": {"relation_type": "OPPOSITION"},
    "like": {"relation_type": "MANNER"},
    "as": {"relation_type": "ROLE"},
}


def get_determiner_encoding(word: str) -> Dict[str, Any] | None:
    """Get encoding for a determiner, or None if not found."""
    return DETERMINER_ENCODINGS.get(word.lower())


def get_conjunction_encoding(word: str) -> Dict[str, Any] | None:
    """Get encoding for a conjunction, or None if not found."""
    return CONJUNCTION_ENCODINGS.get(word.lower())


def get_preposition_encoding(word: str) -> Dict[str, Any] | None:
    """Get encoding for a preposition, or None if not found."""
    return PREPOSITION_ENCODINGS.get(word.lower())
