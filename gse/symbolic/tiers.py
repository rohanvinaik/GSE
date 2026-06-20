"""Operator tiering for clause segmentation.

Single source of truth for which operations *link clauses* versus operate
*within a clause*. Drives encoder segmentation (:mod:`gse.api.encoder`) and
tier-aware AST construction (:func:`gse.symbolic.expression.from_trace`).

See ``docs/COMPLEX_SENTENCE_DESIGN.md`` §2. The one new concept the
complex-sentence build adds: a clause-linking operator takes whole clauses as
operands, so its presence is a clause boundary; a within-clause operator
resolves its arguments inside a single clause span.
"""

from __future__ import annotations

from enum import Enum


class OperationTier(Enum):
    """Whether an operation composes clauses or lives inside one."""

    WITHIN_CLAUSE = "within_clause"
    CLAUSE_LINKING = "clause_linking"


# Tier per operation label (the ``operation`` field on an OperatorTrace / Op).
# CONTRAST (but) stays WITHIN_CLAUSE for now to preserve current behavior — a
# documented candidate for promotion, out of the current build's scope.
OPERATION_TIER = {
    "SET_DIFF": OperationTier.WITHIN_CLAUSE,
    "BIND_EQ": OperationTier.WITHIN_CLAUSE,
    "DEGREE_QUERY": OperationTier.WITHIN_CLAUSE,
    "TYPE_QUERY": OperationTier.WITHIN_CLAUSE,
    "TYPE_ASSERT": OperationTier.WITHIN_CLAUSE,
    "CARD_LOWER": OperationTier.WITHIN_CLAUSE,
    "SCALAR_EXTREME": OperationTier.WITHIN_CLAUSE,
    "CONTRAST": OperationTier.WITHIN_CLAUSE,
    # COORDINATION is NP-level set-union (entities sharing one predicate, e.g.
    # "Spot and Rex are dogs") — handled in resolution as an entity grouping,
    # within a single clause.
    "COORDINATION": OperationTier.WITHIN_CLAUSE,
    # CLAUSE_COORD is clause-level "and" ("Macbeth murdered Duncan and Macduff
    # killed Macbeth") — the encoder marks it (a predicate on each side) and it
    # is a clause boundary, like because/so.
    "CLAUSE_COORD": OperationTier.CLAUSE_LINKING,
    "CAUSAL_SOURCE": OperationTier.CLAUSE_LINKING,
    "CONSEQUENCE": OperationTier.CLAUSE_LINKING,
    "REL_RESTRICT": OperationTier.CLAUSE_LINKING,
    "CONTROL": OperationTier.CLAUSE_LINKING,
}


def tier_of(operation: str) -> OperationTier:
    """Tier for an operation label.

    Unknown operations default to ``WITHIN_CLAUSE`` — the safe choice, since it
    never triggers clause segmentation for an operator we don't recognize.
    """
    return OPERATION_TIER.get(operation, OperationTier.WITHIN_CLAUSE)


def is_clause_linking(operation: str) -> bool:
    """True if the operation composes whole clauses (a clause boundary)."""
    return tier_of(operation) is OperationTier.CLAUSE_LINKING
