"""
Tier 0 dispatch — definitional decompositions for primitive English labels.

The 68 primitives in :data:`gse.primitives_v2.PRIMITIVE_REGISTRY` whose names
are ordinary English lemmas (good, bad, big, small, someone, think, …) have
*definitional* word-scale decompositions: each maps to itself, with value
``+1``, and nothing else. They are NSM primes. Their decomposition is not
something to be discovered from external sources — it is what every other
word's decomposition is defined against.

The 5 primitives flagged ``is_hierarchy_marker`` or ``is_hierarchy_base``
(``HIER_PLUS``, ``HIER_MINUS``, ``INTENSITY``, ``CERTAINTY``, ``QUANTITY``)
are operators/anchors, not English lemmas; they are excluded from Tier 0.

Sentence-scale primitives (``SYN_*``, ``COMP_*``) live in
:data:`gse.primitives_v2.SENTENCE_SCALE` and are out of scope for the
word-scale lexicon entirely; they don't appear here.

This module is consulted before any aggregation. If a word matches a Tier 0
canonical lemma, its decomposition is the identity ``{LABEL: +1}`` and
aggregation is skipped.
"""

from typing import Dict, FrozenSet, Optional

from gse.primitives_v2 import PRIMITIVE_REGISTRY


def _build_tier_0_set() -> FrozenSet[str]:
    """Read from PRIMITIVE_REGISTRY — do not hand-author."""
    return frozenset(
        name
        for name, info in PRIMITIVE_REGISTRY.items()
        if not info.is_hierarchy_marker and not info.is_hierarchy_base
    )


TIER_0_PRIMITIVES: FrozenSet[str] = _build_tier_0_set()


def _normalize_lemma(lemma: str) -> str:
    """Map a spaCy-style lemma to the PRIMITIVE_REGISTRY key form.

    Multi-word phrases like 'long time' / 'short time' map to the
    underscore-joined registry keys ``LONG_TIME`` / ``SHORT_TIME``.
    Pronouns 'i' / 'you' map to uppercase ``I`` / ``YOU``.
    """
    return lemma.upper().strip().replace(" ", "_").replace("-", "_")


def canonical_decomposition(lemma: str) -> Optional[Dict[str, int]]:
    """If ``lemma`` is an English label for a Tier 0 primitive, return ``{LABEL: +1}``.

    Otherwise return ``None`` so the caller falls back to aggregation.
    """
    key = _normalize_lemma(lemma)
    if key in TIER_0_PRIMITIVES:
        return {key: 1}
    return None


def is_tier_0(lemma: str) -> bool:
    """True if ``lemma`` has a definitional decomposition."""
    return _normalize_lemma(lemma) in TIER_0_PRIMITIVES
