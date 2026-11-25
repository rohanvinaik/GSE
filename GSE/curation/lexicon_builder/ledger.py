"""The promotion gate for type-guarded lexical rules (SIGNIFICANCE_WEIGHTING.md §§14, 16.6-16.7).

A candidate rule says every definition under WordNet type T has bank b = v. Its fate is computed, never
voted or thresholded, from three measured facts, as Regenesis ``promotion_ledger.admissible_promotions``
computes them for narrative rules:

- confirmation: a STATED fact (a source assertion, never a value some rule derived) under T asserts b = v;
- contradiction: a stated fact under T asserts b with another value, or a native restriction excludes v;
- reach (kappa): the cells under T where b is still open, which the rule would settle.

A confirmed and contradicted rule oscillates. It is narrowed, not banned: the separating guards are the
types every confirming definition shares and no contradicting definition holds (``impute_guard_candidates``).
When no type separates them, the oscillation is the finding and is logged with the exact definitions.
A rule with no stated fact under T is unconfirmed: what it asserts is outside what the sources teach.
"""

from __future__ import annotations

ADMISSIBLE = "ADMISSIBLE"
SPECIALIZED = "OSCILLATING_SPECIALIZED"
FINDING = "OSCILLATING_NO_SEPARATING_TYPE"
UNCONFIRMED = "UNCONFIRMED"
NO_REACH = "NO_REACH"
EXCEEDS_REVIEWED = "EXCEEDS_REVIEWED_RULE"


def impute_guard_candidates(confirming: list[frozenset], contradicting: list[frozenset]) -> tuple[str, ...]:
    """Types held by every confirming definition and by no contradicting one (both sets nonempty)."""
    if not confirming or not contradicting:
        return ()
    shared = frozenset.intersection(*confirming)
    held = frozenset().union(*contradicting)
    return tuple(sorted(shared - held))


def verdict(n_confirming: int, n_contradicting: int, kappa: int, guards: tuple, exceeds_reviewed: bool) -> str:
    """The computed gate: confirmed, uncontradicted (or narrowed), reach above zero, inside reviewed scope."""
    if exceeds_reviewed:
        return EXCEEDS_REVIEWED
    if n_confirming == 0:
        return UNCONFIRMED
    if n_contradicting:
        return SPECIALIZED if guards else FINDING
    return ADMISSIBLE if kappa > 0 else NO_REACH
