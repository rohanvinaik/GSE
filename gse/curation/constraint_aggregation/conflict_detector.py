"""
Conflict Detection

Detects conflicts in aggregated evidence:
1. Value disagreements: Sources disagree on +1 vs -1
2. Bipolar violations: Evidence for both poles of bipolar pair
3. Sign flips: Strong disagreement (multiple sources on each side)

Also determines whether a word needs manual review.
"""

from typing import Dict, List, Tuple

from gse.curation.constraint_aggregation.types import (
    ConflictRecord,
    SourceMapping,
)

# Bipolar primitive pairs (cannot both be non-zero)
BIPOLAR_PAIRS = [
    ("GOOD", "BAD"),
    ("BIG", "SMALL"),
    ("BEFORE", "AFTER"),
    ("ABOVE", "BELOW"),
    ("FAR", "NEAR"),
    ("INSIDE", "OUTSIDE"),
    ("TOWARD", "AWAY"),
    ("START", "END"),
    ("LONG_TIME", "SHORT_TIME"),
    ("ALIVE", "DEAD"),
    ("TRUE", "FALSE"),
]

# Build reverse lookup
BIPOLAR_PARTNER = {}
for p1, p2 in BIPOLAR_PAIRS:
    BIPOLAR_PARTNER[p1] = p2
    BIPOLAR_PARTNER[p2] = p1


def detect_conflicts(
    primitive_evidence: Dict[str, List[SourceMapping]],
) -> List[ConflictRecord]:
    """
    Detect all conflicts in the aggregated evidence.

    Conflict types:
    1. value_disagreement: Sources disagree on +1 vs -1 for same primitive
    2. bipolar_violation: Evidence for both poles of bipolar pair
    3. sign_flip: Strong disagreement (multiple sources on each side)

    Args:
        primitive_evidence: Dict of primitive -> list of SourceMapping

    Returns:
        List of ConflictRecord objects
    """
    conflicts = []

    # Check value disagreements per primitive
    for primitive, evidence_list in primitive_evidence.items():
        if not evidence_list:
            continue

        # Group by source and value
        values_by_source = {}
        for ev in evidence_list:
            values_by_source.setdefault(ev.source_name, []).append(ev.target_value)

        # Get sources with positive and negative values
        positive_sources = [s for s, vals in values_by_source.items() if any(v > 0 for v in vals)]
        negative_sources = [s for s, vals in values_by_source.items() if any(v < 0 for v in vals)]

        if positive_sources and negative_sources:
            # Determine severity
            if len(positive_sources) > 1 and len(negative_sources) > 1:
                severity = "critical"  # Multiple sources on each side
                conflict_type = "sign_flip"
            elif len(positive_sources) >= 1 and len(negative_sources) >= 1:
                severity = "major"
                conflict_type = "value_disagreement"
            else:
                severity = "minor"
                conflict_type = "value_disagreement"

            conflicts.append(
                ConflictRecord(
                    primitive=primitive,
                    conflict_type=conflict_type,
                    sources_positive=positive_sources,
                    sources_negative=negative_sources,
                    severity=severity,
                    resolution_required=True,
                    detail=f"{len(positive_sources)} source(s) say +1, {len(negative_sources)} source(s) say -1",
                )
            )

    # Check bipolar violations
    for pos_prim, neg_prim in BIPOLAR_PAIRS:
        pos_evidence = primitive_evidence.get(pos_prim, [])
        neg_evidence = primitive_evidence.get(neg_prim, [])

        # Check if both have positive values
        pos_has_positive = any(e.target_value > 0 for e in pos_evidence)
        neg_has_positive = any(e.target_value > 0 for e in neg_evidence)

        if pos_has_positive and neg_has_positive:
            pos_sources = [e.source_name for e in pos_evidence if e.target_value > 0]
            neg_sources = [e.source_name for e in neg_evidence if e.target_value > 0]

            conflicts.append(
                ConflictRecord(
                    primitive=f"{pos_prim}/{neg_prim}",
                    conflict_type="bipolar_violation",
                    sources_positive=pos_sources,
                    sources_negative=neg_sources,
                    severity="major",
                    resolution_required=True,
                    detail=f"Both {pos_prim} and {neg_prim} have positive evidence (bipolar violation)",
                )
            )

    return conflicts


def should_flag_for_review(
    conflicts: List[ConflictRecord],
    overall_confidence: float,
    min_confidence_threshold: float = 0.7,
) -> Tuple[bool, List[str]]:
    """
    Determine if word needs manual review.

    Returns: (needs_review, list of reasons)

    Flags for review if:
    - ANY critical conflict
    - ANY bipolar violation
    - Low overall confidence
    - Multiple value disagreements
    """
    reasons = []

    # ANY critical conflict -> flag
    critical_conflicts = [c for c in conflicts if c.severity == "critical"]
    if critical_conflicts:
        reasons.append(f"{len(critical_conflicts)} critical conflict(s)")

    # ANY bipolar violation -> flag
    bipolar_violations = [c for c in conflicts if c.conflict_type == "bipolar_violation"]
    if bipolar_violations:
        prims = [c.primitive for c in bipolar_violations]
        reasons.append(f"Bipolar violation(s): {', '.join(prims)}")

    # Low overall confidence -> flag
    if overall_confidence < min_confidence_threshold:
        reasons.append(f"Low confidence: {overall_confidence:.2f}")

    # Multiple value disagreements -> flag
    value_disagreements = [c for c in conflicts if c.conflict_type == "value_disagreement"]
    if len(value_disagreements) >= 3:
        reasons.append(f"{len(value_disagreements)} value disagreements")

    # ANY sign flip -> flag
    sign_flips = [c for c in conflicts if c.conflict_type == "sign_flip"]
    if sign_flips:
        prims = [c.primitive for c in sign_flips]
        reasons.append(f"Sign flip(s): {', '.join(prims)}")

    return len(reasons) > 0, reasons


def get_conflict_summary(conflicts: List[ConflictRecord]) -> Dict:
    """Get summary statistics of conflicts."""
    if not conflicts:
        return {
            "total": 0,
            "by_type": {},
            "by_severity": {},
            "primitives_affected": [],
        }

    by_type = {}
    by_severity = {}
    primitives = set()

    for c in conflicts:
        by_type[c.conflict_type] = by_type.get(c.conflict_type, 0) + 1
        by_severity[c.severity] = by_severity.get(c.severity, 0) + 1
        primitives.add(c.primitive)

    return {
        "total": len(conflicts),
        "by_type": by_type,
        "by_severity": by_severity,
        "primitives_affected": list(primitives),
    }
