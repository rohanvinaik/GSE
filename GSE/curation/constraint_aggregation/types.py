"""
Type Definitions for Constraint Aggregation

Core data structures for tracking evidence, constraints, and conflicts
across multiple NLP data sources.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ConstraintType(Enum):
    """How strongly the source constrains the primitive."""

    DEFINITIVE = "definitive"  # Source directly asserts this (e.g., VerbNet role)
    INFERENTIAL = "inferential"  # Source implies this (e.g., high concreteness -> SOMETHING)
    CORRELATIONAL = "correlational"  # Statistical tendency (e.g., NRC emotion)


class EvidenceStrength(Enum):
    """Strength of evidence from a single source."""

    STRONG = 1.0  # Clear mapping, source designed for this
    MODERATE = 0.7  # Reasonable inference
    WEAK = 0.4  # Correlational/suggestive


@dataclass(frozen=True)
class SourceMapping:
    """
    A single mapping from source concept to GSE primitive.

    Represents one piece of evidence from one source for one primitive.
    """

    source_name: str  # e.g., "verbnet", "nrc_vad"
    source_concept: str  # e.g., "Agent", "high_valence"
    target_primitive: str  # e.g., "SOMEONE", "GOOD"
    target_value: int  # +1 or -1
    constraint_type: ConstraintType
    evidence_strength: EvidenceStrength
    conditions: Optional[str] = None  # e.g., "score > 0.65"
    raw_value: Optional[float] = None  # Original value from source

    def __hash__(self):
        return hash((self.source_name, self.source_concept, self.target_primitive, self.target_value))


@dataclass
class PrimitiveConstraint:
    """
    Aggregated constraint for a single primitive from all sources.

    This is the result of combining evidence from multiple sources
    for a single primitive for a single word.
    """

    primitive: str
    value: int  # Final resolved value (+1, -1)
    confidence: float  # 0.0 to 1.0
    supporting_sources: List[str]  # Sources that agree
    conflicting_sources: List[str]  # Sources that disagree
    evidence_records: List[SourceMapping]
    status: str  # "auto_apply", "flag_review", "insufficient"

    @property
    def has_conflict(self) -> bool:
        return len(self.conflicting_sources) > 0

    @property
    def is_unanimous(self) -> bool:
        return len(self.conflicting_sources) == 0 and len(self.supporting_sources) > 0


@dataclass
class ConflictRecord:
    """Record of a detected conflict between sources."""

    primitive: str
    conflict_type: str  # "value_disagreement", "bipolar_violation", "sign_flip"
    sources_positive: List[str]  # Sources saying +1
    sources_negative: List[str]  # Sources saying -1
    severity: str  # "minor", "major", "critical"
    resolution_required: bool
    detail: Optional[str] = None  # Human-readable explanation


@dataclass
class WordConstraintProfile:
    """
    Complete constraint profile for a word from all sources.

    This is the main output of the constraint aggregation engine.
    Contains all constraints, conflicts, and metadata for a single word.
    """

    word: str
    pos: Optional[str]
    sources_checked: List[str]  # All sources we tried to query
    sources_with_data: List[str]  # Sources that had data for this word
    constraints: Dict[str, PrimitiveConstraint]  # primitive -> constraint
    conflicts: List[ConflictRecord]  # All detected conflicts
    overall_confidence: float  # Combined confidence score
    review_required: bool  # Whether manual review is needed
    review_reasons: List[str]  # Why review is required
    raw_source_data: Dict[str, Any] = None  # Raw data from each source for LLM context

    def get_auto_apply_constraints(self) -> Dict[str, int]:
        """Get only constraints that can be auto-applied."""
        return {prim: c.value for prim, c in self.constraints.items() if c.status == "auto_apply"}

    def get_review_candidates(self) -> List[Dict]:
        """Get constraints that need manual review with reasons."""
        candidates = []
        for prim, c in self.constraints.items():
            if c.status == "flag_review":
                candidates.append(
                    {
                        "primitive": prim,
                        "proposed_value": c.value,
                        "confidence": c.confidence,
                        "supporting": c.supporting_sources,
                        "conflicting": c.conflicting_sources,
                        "reason": "Source disagreement" if c.conflicting_sources else "Low confidence",
                    }
                )
        return candidates

    def summary(self) -> Dict:
        """Get summary statistics."""
        auto_apply = sum(1 for c in self.constraints.values() if c.status == "auto_apply")
        flag_review = sum(1 for c in self.constraints.values() if c.status == "flag_review")
        insufficient = sum(1 for c in self.constraints.values() if c.status == "insufficient")

        return {
            "word": self.word,
            "sources_with_data": len(self.sources_with_data),
            "total_constraints": len(self.constraints),
            "auto_apply": auto_apply,
            "flag_review": flag_review,
            "insufficient": insufficient,
            "conflicts": len(self.conflicts),
            "overall_confidence": self.overall_confidence,
            "review_required": self.review_required,
        }
