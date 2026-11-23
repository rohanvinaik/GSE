"""
Confidence-weighted voting for cross-source primitive aggregation.

The integrator's existing :func:`aggregate_primitives` uses raw vote counts:
each source contributes one vote and the winner is whichever value (+1 or
-1) gets more votes. That's fine when sources are equally trustworthy,
but it mis-weights "one high-confidence source agrees with three
low-confidence sources" cases.

This module ports the confidence-weighted scheme that
``scripts/rebuild_lexicon_from_sources.py`` lines 240-255 used:

* Sum source confidences by sign (positive vs negative).
* The side with higher summed confidence wins; the winning confidence is
  ``winner_weight / (winner_weight + loser_weight + epsilon)``.
* Boost by ``min(1.0, 0.7 + 0.1 * unique_source_count)`` to reward
  cross-source agreement.

Pure functions — no I/O, no globals. Tested standalone.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple

_EPS = 0.01
_BASE_AGREEMENT_BOOST = 0.7
_PER_SOURCE_BOOST = 0.1


@dataclass(frozen=True)
class WeightedVote:
    """Outcome of weighted voting for a single primitive."""

    primitive: str
    value: int  # -1, 0, or +1
    confidence: float  # in [0.0, 1.0]
    contributing_sources: Tuple[str, ...]  # sorted, unique


@dataclass
class WeightedAggregation:
    """All weighted-vote results for one word."""

    word: str
    primitives: Dict[str, WeightedVote] = field(default_factory=dict)
    source_count: int = 0  # distinct sources that contributed any data


def aggregate_weighted(
    word: str,
    source_votes: Mapping[str, Mapping[str, Tuple[int, float]]],
) -> WeightedAggregation:
    """Confidence-weighted majority vote across sources.

    Args:
        word: lemma the votes are for (used only for the result label).
        source_votes: ``{source_name: {primitive: (value, confidence)}}``.
            ``value`` is ``-1``, ``0``, or ``+1``. ``confidence`` is in
            ``[0.0, 1.0]``. ``value == 0`` votes are ignored (carry no
            primitive evidence).

    Returns:
        WeightedAggregation with one ``WeightedVote`` per primitive that
        received at least one nonzero vote.

    The voting rule (per primitive across sources):

        pos_weight = sum(confidence for value > 0)
        neg_weight = sum(confidence for value < 0)
        if pos_weight > neg_weight: value = +1
        elif neg_weight > pos_weight: value = -1
        else: value = 0  (tied; confidence 0.5)

        winner_weight = max(pos_weight, neg_weight)
        loser_weight  = min(pos_weight, neg_weight)
        raw_conf = winner_weight / (winner_weight + loser_weight + EPS)

        boost = min(1.0, 0.7 + 0.1 * unique_source_count)
        confidence = raw_conf * boost
    """
    per_prim_votes: Dict[str, List[Tuple[int, float, str]]] = defaultdict(list)
    contributing: set = set()

    for source_name, prim_dict in source_votes.items():
        used = False
        for prim, (value, conf) in prim_dict.items():
            if value == 0:
                continue
            per_prim_votes[prim].append((value, conf, source_name))
            used = True
        if used:
            contributing.add(source_name)

    primitives: Dict[str, WeightedVote] = {}
    for prim, votes in per_prim_votes.items():
        pos_weight = sum(conf for v, conf, _ in votes if v > 0)
        neg_weight = sum(conf for v, conf, _ in votes if v < 0)

        if pos_weight > neg_weight:
            final_value = 1
            winner, loser = pos_weight, neg_weight
        elif neg_weight > pos_weight:
            final_value = -1
            winner, loser = neg_weight, pos_weight
        else:
            primitives[prim] = WeightedVote(
                primitive=prim,
                value=0,
                confidence=0.5,
                contributing_sources=tuple(sorted({s for _, _, s in votes})),
            )
            continue

        raw_conf = winner / (winner + loser + _EPS)
        prim_sources = {s for _, _, s in votes}
        boost = min(1.0, _BASE_AGREEMENT_BOOST + _PER_SOURCE_BOOST * len(prim_sources))
        confidence = raw_conf * boost

        primitives[prim] = WeightedVote(
            primitive=prim,
            value=final_value,
            confidence=confidence,
            contributing_sources=tuple(sorted(prim_sources)),
        )

    return WeightedAggregation(
        word=word,
        primitives=primitives,
        source_count=len(contributing),
    )
