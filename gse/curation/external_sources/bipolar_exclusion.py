"""
Bipolar mutual-exclusion enforcement for lexicon decompositions.

The 14 bipolar dimensions in NSM (GOOD/BAD, BIG/SMALL, NEAR/FAR, etc.) are
defined to be mutually exclusive: a word activates at most one pole of
each pair, never both. The previous LLM-populated lexicon violated this
in ~all words — both BIG=-1 and SMALL=+1 on the same lemma, both NEAR=+1
and AWAY=+1 on "near", etc. — which neutralized the bipolar opposition
at encode time.

This module enforces the constraint as a post-voting cleanup step. For
each bipolar pair, if both poles arrive active, the higher-confidence
pole is kept and the other is suppressed (set to 0). The suppression is
recorded so the provenance trail captures which sources voted for the
losing pole.

Pure functions — no I/O. Operates on plain dicts so it composes with
either the integrator's raw output or the weighted-voting output.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

from gse.curation.schema import BIPOLAR_PAIRS


@dataclass(frozen=True)
class Suppression:
    """A record of one bipolar conflict resolved by mutual exclusion."""
    kept: str
    kept_confidence: float
    dropped: str
    dropped_confidence: float
    bipolar_pair: Tuple[str, str]  # canonical (positive, negative)


@dataclass
class ExclusionResult:
    """Post-exclusion decomposition + audit trail."""
    primitives: Dict[str, int]
    confidences: Dict[str, float]
    suppressions: List[Suppression] = field(default_factory=list)


def enforce_bipolar_exclusion(
    primitives: Mapping[str, int],
    confidences: Optional[Mapping[str, float]] = None,
) -> ExclusionResult:
    """Drop the weaker pole when both bipolar pair members are active.

    A primitive is "active" if its value is nonzero (``+1`` or ``-1``).
    For each canonical pair in :data:`gse.curation.schema.BIPOLAR_PAIRS`,
    if both members are active, the one with higher confidence is kept
    and the other is removed (along with its confidence). When
    confidences tie, the positive pole is kept by convention.

    Args:
        primitives: mapping of primitive name to ``-1 / 0 / +1``.
        confidences: optional per-primitive confidence in ``[0.0, 1.0]``.
            Missing entries default to ``1.0`` so that the function works
            on hand-authored decompositions without confidence scores.

    Returns:
        ExclusionResult with the cleaned primitives, cleaned confidences,
        and a list of Suppression records (one per resolved conflict).
        Non-bipolar primitives pass through untouched.
    """
    out_primitives: Dict[str, int] = {k: v for k, v in primitives.items() if v != 0}
    out_confidences: Dict[str, float] = dict(confidences) if confidences else {}
    suppressions: List[Suppression] = []

    for pos, neg in BIPOLAR_PAIRS:
        if pos not in out_primitives or neg not in out_primitives:
            continue

        conf_pos = out_confidences.get(pos, 1.0)
        conf_neg = out_confidences.get(neg, 1.0)

        if conf_pos >= conf_neg:
            kept, dropped = pos, neg
            kept_conf, dropped_conf = conf_pos, conf_neg
        else:
            kept, dropped = neg, pos
            kept_conf, dropped_conf = conf_neg, conf_pos

        suppressions.append(Suppression(
            kept=kept,
            kept_confidence=kept_conf,
            dropped=dropped,
            dropped_confidence=dropped_conf,
            bipolar_pair=(pos, neg),
        ))

        del out_primitives[dropped]
        out_confidences.pop(dropped, None)

    return ExclusionResult(
        primitives=out_primitives,
        confidences=out_confidences,
        suppressions=suppressions,
    )


def count_violations(primitives: Mapping[str, int]) -> int:
    """How many bipolar pairs have BOTH members active in this decomposition?

    Useful for auditing an existing lexicon without modifying it. Returns
    the count of pairs with both members nonzero (range ``0..14``).
    """
    return sum(
        1
        for pos, neg in BIPOLAR_PAIRS
        if primitives.get(pos, 0) != 0 and primitives.get(neg, 0) != 0
    )
