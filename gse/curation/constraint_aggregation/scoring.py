"""
Confidence Scoring

Calculates confidence scores for constraints based on:
1. Number of agreeing sources
2. Source reliability weights
3. Evidence strength (definitive vs inferential)
4. Presence of conflicts

Formula:
confidence = (weighted_support - weighted_conflict) / total_weight
           + source_count_bonus (up to +0.2 for 3+ sources)
"""

from typing import Dict, List

from gse.curation.constraint_aggregation.mapping_registry import SOURCE_RELIABILITY
from gse.curation.constraint_aggregation.types import (
    PrimitiveConstraint,
    SourceMapping,
)


def calculate_constraint_confidence(
    supporting_evidence: List[SourceMapping],
    conflicting_evidence: List[SourceMapping],
    source_reliability: Dict[str, float] = None,
) -> float:
    """
    Calculate confidence score for a primitive constraint.

    Args:
        supporting_evidence: Evidence records that support the proposed value
        conflicting_evidence: Evidence records that oppose the proposed value
        source_reliability: Override reliability weights (uses defaults if None)

    Returns:
        Confidence score in range [0.0, 1.0]
    """
    if source_reliability is None:
        source_reliability = SOURCE_RELIABILITY

    if not supporting_evidence and not conflicting_evidence:
        return 0.0

    weighted_support = 0.0
    weighted_conflict = 0.0

    # Calculate weighted support
    for evidence in supporting_evidence:
        source_rel = source_reliability.get(evidence.source_name, 0.5)
        strength = evidence.evidence_strength.value
        weighted_support += source_rel * strength

    # Calculate weighted conflict
    for evidence in conflicting_evidence:
        source_rel = source_reliability.get(evidence.source_name, 0.5)
        strength = evidence.evidence_strength.value
        weighted_conflict += source_rel * strength

    total_weight = weighted_support + weighted_conflict
    if total_weight == 0:
        return 0.0

    # Calculate raw confidence score in [-1, 1]
    raw_score = (weighted_support - weighted_conflict) / total_weight

    # Normalize to [0, 1]
    confidence = (raw_score + 1) / 2

    # Apply source count bonus (more sources = more confidence)
    unique_supporting = len(set(e.source_name for e in supporting_evidence))
    source_bonus = min(0.1 * (unique_supporting - 1), 0.2)  # Up to +0.2 for 3+ sources

    # Only apply bonus if there are no conflicts
    if not conflicting_evidence:
        confidence = min(confidence + source_bonus, 1.0)

    # Penalize for conflicts
    if conflicting_evidence:
        # Reduce confidence based on conflict ratio
        conflict_ratio = len(conflicting_evidence) / (len(supporting_evidence) + len(conflicting_evidence))
        confidence *= (1 - conflict_ratio * 0.5)  # Up to 50% reduction

    return round(confidence, 3)


def calculate_overall_word_confidence(
    constraints: Dict[str, PrimitiveConstraint],
    sources_with_data: List[str],
    total_sources: int = 11,
) -> float:
    """
    Calculate overall confidence for a word's constraint profile.

    Considers:
    - Average confidence across all constraints
    - Source coverage (how many sources had data)
    - Presence of conflicts

    Args:
        constraints: Dict of primitive -> PrimitiveConstraint
        sources_with_data: List of sources that had data for this word
        total_sources: Total number of available sources (default 11)

    Returns:
        Overall confidence in range [0.0, 1.0]
    """
    if not constraints:
        return 0.0

    # Calculate source coverage factor (0.5 to 1.0)
    source_coverage = len(sources_with_data) / total_sources
    coverage_factor = 0.5 + 0.5 * source_coverage

    # Calculate average constraint confidence
    confidences = [c.confidence for c in constraints.values() if c.confidence > 0]
    if not confidences:
        return 0.0

    avg_confidence = sum(confidences) / len(confidences)

    # Count constraints with conflicts
    conflict_count = sum(1 for c in constraints.values() if c.has_conflict)
    conflict_penalty = 1.0 - (conflict_count / len(constraints)) * 0.3  # Up to 30% reduction

    overall = avg_confidence * coverage_factor * conflict_penalty

    return round(min(max(overall, 0.0), 1.0), 3)


def confidence_to_status(
    confidence: float,
    has_conflict: bool,
    min_auto_apply: float = 0.8,
    min_sufficient: float = 0.3,
) -> str:
    """
    Convert confidence score to status string.

    Args:
        confidence: Confidence score [0, 1]
        has_conflict: Whether there's a conflict
        min_auto_apply: Minimum confidence for auto-apply (default 0.8)
        min_sufficient: Minimum confidence to consider "sufficient" (default 0.3)

    Returns:
        Status string: "auto_apply", "flag_review", or "insufficient"
    """
    # ANY conflict requires review
    if has_conflict:
        return "flag_review"

    # High confidence with no conflict -> auto-apply
    if confidence >= min_auto_apply:
        return "auto_apply"

    # Low confidence -> insufficient evidence
    if confidence < min_sufficient:
        return "insufficient"

    # Medium confidence without conflict -> still flag for review
    # (we're being strict about accuracy)
    return "flag_review"
