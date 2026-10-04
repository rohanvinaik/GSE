"""
Mapping Registry

Central registry of:
1. Source reliability weights
2. Which primitives each source can inform
3. Mapping tables from source concepts to GSE primitives

All mappings are defined here to ensure consistency and maintainability.
"""

from typing import Dict, List, Set

from gse.curation.constraint_aggregation.types import (
    ConstraintType,
    EvidenceStrength,
    SourceMapping,
)

# Source reliability weights (0.0 to 1.0)
# Higher = more trustworthy for GSE primitive inference
SOURCE_RELIABILITY: Dict[str, float] = {
    # Linguistically-grounded sources (highest reliability)
    "verbnet": 0.85,  # Principled verb classes with thematic roles
    "framenet": 0.85,  # Well-structured frame semantics
    "propbank": 0.80,  # Argument structure annotations
    "usas": 0.80,  # Lancaster semantic tagger, well-validated
    # Taxonomic sources
    "wordnet_hierarchy": 0.75,  # Good for entity types, domains
    # Psycholinguistic norms (validated with human subjects)
    "lancaster_sensorimotor": 0.80,  # Strong for sensory/body primitives
    "nrc_vad": 0.75,  # Well-validated affect norms
    "concreteness": 0.75,  # Good for abstract vs concrete
    # Sentiment/emotion (some noise expected)
    "nrc_emotion": 0.70,  # Emotion categories, some overlap
    "sentiwordnet": 0.65,  # Noisy, averaged over senses
    # Large-scale resources (broad coverage but noisier)
    "wiktionary": 0.70,  # Definitions can be imprecise
    "conceptnet": 0.65,  # Crowdsourced, variable quality
}


# Which primitives can each source reliably inform?
SOURCE_PRIMITIVE_COVERAGE: Dict[str, Dict[str, List[str]]] = {
    "verbnet": {
        "definitive": [
            "DO",
            "SOMEONE",
            "SOMETHING",
            "MOVE",
            "SAY",
            "SEE",
            "HEAR",
            "FEEL",
            "THINK",
            "TOWARD",
            "AWAY",
            "CAUSE",
            "WITH",
        ],
        "inferential": ["WANT", "GOOD", "BODY"],
    },
    "framenet": {
        "definitive": [
            "DO",
            "SOMEONE",
            "SOMETHING",
            "MOVE",
            "SAY",
            "SEE",
            "HEAR",
            "FEEL",
            "THINK",
            "WANT",
            "KNOW",
            "CAUSE",
            "WHERE",
            "WHEN",
            "TOWARD",
            "AWAY",
            "WORDS",
            "BODY",
            "HAVE",
            "START",
            "END",
        ],
        "inferential": ["GOOD", "ALIVE", "MUST", "CAN"],
    },
    "propbank": {
        "definitive": [
            "DO",
            "SOMEONE",
            "SOMETHING",
            "MOVE",
            "SAY",
            "THINK",
            "KNOW",
            "FEEL",
            "WANT",
            "SEE",
            "HEAR",
            "HAVE",
            "ALIVE",
            "CAUSE",
        ],
        "inferential": ["GOOD", "BODY", "WHERE", "WHEN"],
    },
    "wordnet_hierarchy": {
        "definitive": [
            "SOMEONE",
            "SOMETHING",
            "ALIVE",
            "WHERE",
            "WHEN",
            "THINK",
            "FEEL",
            "SAY",
            "WORDS",
            "BODY",
            "PART",
            "HAVE",
            "DO",
            "HAPPEN",
        ],
        "inferential": ["MOVE", "SEE", "HEAR", "WANT"],
    },
    "nrc_vad": {
        "definitive": ["GOOD"],  # Valence maps directly
        "inferential": ["INTENSITY", "CAN", "MUST"],
    },
    "nrc_emotion": {
        "definitive": ["FEEL"],
        "inferential": ["GOOD", "WANT", "KNOW", "BEFORE"],
    },
    "lancaster_sensorimotor": {
        "definitive": ["BODY", "SEE", "HEAR", "TOUCH", "MOVE", "DO"],
        "inferential": ["FEEL", "INSIDE", "THINK", "SOMETHING"],
    },
    "concreteness": {
        "definitive": ["SOMETHING"],
        "inferential": ["BODY", "THINK"],
    },
    "sentiwordnet": {
        "definitive": ["GOOD"],
        "inferential": [],
    },
    "wiktionary": {
        "definitive": [],  # Definition analysis is always inferential
        "inferential": [
            "DO",
            "MOVE",
            "SAY",
            "WORDS",
            "THINK",
            "KNOW",
            "FEEL",
            "SEE",
            "HEAR",
            "TOUCH",
            "WANT",
            "HAVE",
            "BE",
            "EXIST",
            "ALIVE",
            "GOOD",
            "BIG",
            "SOMEONE",
            "SOMETHING",
            "BODY",
            "WHERE",
            "WHEN",
            "BEFORE",
            "AFTER",
            "INSIDE",
            "OUTSIDE",
            "CAUSE",
            "BECAUSE",
            "CAN",
            "MUST",
            "MAYBE",
        ],
    },
    "conceptnet": {
        "definitive": ["HAVE", "PART"],
        "inferential": [
            "SOMEONE",
            "SOMETHING",
            "WHERE",
            "WHEN",
            "DO",
            "MOVE",
            "CAUSE",
            "BEFORE",
            "START",
            "END",
            "CAN",
            "WANT",
            "ALIVE",
            "FEEL",
            "LIKE",
            "NOT",
        ],
    },
    "usas": {
        "definitive": [
            # USAS has strong coverage of semantic fields
            "MOVE",
            "WHERE",
            "WHEN",
            "FEEL",
            "SAY",
            "WORDS",
            "THINK",
            "KNOW",
            "WANT",
            "DO",
            "BODY",
            "ALIVE",
            "SOMEONE",
            "PEOPLE",
            "HAVE",
            "SOMETHING",
            "GOOD",
            "ONE",
            "QUANTITY",
        ],
        "inferential": [
            "SAME",
            "OTHER",
            "INTENSITY",
            "CAN",
            "MUST",
            "MAYBE",
            "START",
            "END",
            "LONG_TIME",
            "SHORT_TIME",
            "SOME",
            "ALL",
            "MUCH",
            "LITTLE",
            "CAUSE",
            "INSIDE",
            "BE",
        ],
    },
}


def get_primitive_constraint_type(source_name: str, primitive: str) -> ConstraintType:
    """
    Determine the constraint type for a source-primitive pair.

    Returns:
        DEFINITIVE if the source directly asserts this primitive
        INFERENTIAL if the source implies this primitive
        CORRELATIONAL otherwise
    """
    coverage = SOURCE_PRIMITIVE_COVERAGE.get(source_name, {})

    if primitive in coverage.get("definitive", []):
        return ConstraintType.DEFINITIVE
    elif primitive in coverage.get("inferential", []):
        return ConstraintType.INFERENTIAL
    else:
        return ConstraintType.CORRELATIONAL


def get_evidence_strength(constraint_type: ConstraintType) -> EvidenceStrength:
    """Map constraint type to evidence strength."""
    if constraint_type == ConstraintType.DEFINITIVE:
        return EvidenceStrength.STRONG
    elif constraint_type == ConstraintType.INFERENTIAL:
        return EvidenceStrength.MODERATE
    else:
        return EvidenceStrength.WEAK


def get_mapping_for_source(
    source_name: str,
    primitive: str,
    value: int,
    source_concept: str = None,
    raw_value: float = None,
    conditions: str = None,
) -> SourceMapping:
    """
    Create a SourceMapping object for a source-primitive pair.

    This is the main factory function for creating evidence records.
    """
    constraint_type = get_primitive_constraint_type(source_name, primitive)
    evidence_strength = get_evidence_strength(constraint_type)

    return SourceMapping(
        source_name=source_name,
        source_concept=source_concept or f"{source_name}_{primitive}",
        target_primitive=primitive,
        target_value=value,
        constraint_type=constraint_type,
        evidence_strength=evidence_strength,
        conditions=conditions,
        raw_value=raw_value,
    )


def get_all_covered_primitives(source_name: str) -> Set[str]:
    """Get all primitives that a source can inform (definitive + inferential)."""
    coverage = SOURCE_PRIMITIVE_COVERAGE.get(source_name, {})
    definitive = set(coverage.get("definitive", []))
    inferential = set(coverage.get("inferential", []))
    return definitive | inferential


def get_sources_for_primitive(primitive: str) -> List[str]:
    """Get all sources that can inform a given primitive."""
    sources = []
    for source_name, coverage in SOURCE_PRIMITIVE_COVERAGE.items():
        all_prims = set(coverage.get("definitive", [])) | set(coverage.get("inferential", []))
        if primitive in all_prims:
            sources.append(source_name)
    return sources
