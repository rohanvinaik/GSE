"""
Constraint Aggregation Engine

Aggregates semantic constraints from multiple NLP databases to determine
GSE primitive values with high confidence.

Strategy:
1. Collect evidence from each source (11 total)
2. Detect conflicts between sources
3. Score confidence based on agreement and source reliability
4. Apply strict constraint logic:
   - Unanimous agreement + high confidence -> auto-apply
   - ANY disagreement -> flag for review
   - Missing data -> no constraint (let LLM decide)
"""

from gse.curation.constraint_aggregation.conflict_detector import (
    detect_conflicts,
    should_flag_for_review,
)
from gse.curation.constraint_aggregation.engine import ConstraintAggregationEngine
from gse.curation.constraint_aggregation.mapping_registry import (
    SOURCE_PRIMITIVE_COVERAGE,
    SOURCE_RELIABILITY,
    get_mapping_for_source,
)
from gse.curation.constraint_aggregation.scoring import (
    calculate_constraint_confidence,
    calculate_overall_word_confidence,
)
from gse.curation.constraint_aggregation.types import (
    ConflictRecord,
    ConstraintType,
    EvidenceStrength,
    PrimitiveConstraint,
    SourceMapping,
    WordConstraintProfile,
)

__all__ = [
    # Types
    "ConstraintType",
    "EvidenceStrength",
    "SourceMapping",
    "PrimitiveConstraint",
    "WordConstraintProfile",
    "ConflictRecord",
    # Registry
    "SOURCE_RELIABILITY",
    "SOURCE_PRIMITIVE_COVERAGE",
    "get_mapping_for_source",
    # Scoring
    "calculate_constraint_confidence",
    "calculate_overall_word_confidence",
    # Conflict detection
    "detect_conflicts",
    "should_flag_for_review",
    # Main engine
    "ConstraintAggregationEngine",
]
