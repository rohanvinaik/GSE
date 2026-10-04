"""
Per-source primitive scope restriction.

Empirical finding from the May 2026 antonym-cosine investigation: the
encoder produces correct geometry per bank UNLESS sources vote on
primitives outside their semantic domain. NRC VAD voting on LOGICAL
primitives (INTENSITY, MUST), Lancaster voting on TEMPORAL primitives,
etc., cause cross-bank pollution: a word picks up shared activations on
banks where it has no meaningful evidence, and the bipolar opposition
that should live in one bank gets washed out by spurious agreement in
others.

This module enforces a **per-source primitive scope**: each external
source is allowed to vote only on primitives within its semantic domain.
Votes on primitives outside that domain are dropped before aggregation.

The scope map is empirically derived from a diagnostic on 50 sample
words (see ``docs/CONSTRUCTION_PLAN.md`` §4 and the May 2026 session
notes). Sources not listed are unrestricted (used as broad-coverage
contributors — currently only Wiktionary v2 fits that role).
"""

from typing import Dict, FrozenSet, Mapping, Optional, Set, Tuple

from gse.primitives_v2 import PRIMITIVE_REGISTRY, SENTENCE_SCALE


def _build_word_scale_excluded() -> FrozenSet[str]:
    """Primitives that don't belong in the word-scale lexicon (architectural).

    Per ``sentence_architecture.md``: tense, modifiers, comparison operators,
    and intensity/hierarchy anchors are sentence-scale concerns. The word-
    scale lexicon stores informational zeros for these dimensions but never
    activates them. This filter prevents word-scale aggregation from voting
    for them.

    Read from the system — both SENTENCE_SCALE.primitive_registry and
    PRIMITIVE_REGISTRY's hierarchy flags. Do not hand-author.
    """
    excluded = set(SENTENCE_SCALE.primitive_registry.keys())
    for name, info in PRIMITIVE_REGISTRY.items():
        if info.is_hierarchy_marker or info.is_hierarchy_base:
            excluded.add(name)
    return frozenset(excluded)


# 24 sentence-scale (SYN_*, COMP_*) + 5 hierarchy ops (HIER_PLUS/MINUS,
# INTENSITY, CERTAINTY, QUANTITY) = 29 primitives no word-scale source
# may vote for. Computed at import time from the system's tables of truth.
WORD_SCALE_EXCLUDED_PRIMITIVES: FrozenSet[str] = _build_word_scale_excluded()


# Primitives each source is allowed to vote on. The "broadly correct"
# domain — not a tight authority claim. The intent is to drop votes that
# are demonstrably outside the source's competence (e.g., NRC VAD voting
# on logical-modal primitives like MUST/CAN).
#
# Sources NOT listed here are unrestricted (vote on any primitive). The
# degenerate broad-coverage source (wiktionary_v2) that this note once referenced
# was retired 2026-06-20.
SOURCE_PRIMITIVE_SCOPE: Mapping[str, Set[str]] = {
    # NRC Emotion Lexicon: 8 emotions + 2 sentiments. Affective signal only.
    "nrc_emotion": {"GOOD", "BAD", "FEEL", "WANT", "KNOW"},
    # NRC VAD: valence/arousal/dominance. Currently valence-only after the
    # May 2026 parser fix; the scope still allows MENTAL primitives so a
    # future arousal/dominance remap can land without scope changes.
    "nrc_vad": {"GOOD", "BAD", "FEEL", "WANT"},
    # SentiWordNet: positive/negative sentiment per WordNet synset.
    "sentiwordnet": {"GOOD", "BAD"},
    # Concreteness ratings: tagging concrete things as SOMETHING is the
    # one defensible mapping. Other mappings (THINK for abstract words)
    # are noise.
    "concreteness": {"SOMETHING"},
    # Lancaster Sensorimotor: 11 modality-specific perception/action scores.
    # Maps cleanly to sensory/motor primitives in MENTAL, SPATIAL, ACTION.
    "lancaster_sensorimotor": {
        "SEE",
        "HEAR",
        "FEEL",
        "TOUCH",
        "BODY",
        "MOVE",
        "INSIDE",
        "DO",
    },
    # VerbNet: verb classes with thematic roles. Action and causation.
    "verbnet": {
        "DO",
        "HAPPEN",
        "MOVE",
        "BE",
        "CAUSE",
        "SAY",
        "WORDS",
        "SOMEONE",
        "SOMETHING",
    },
    # WordNet hierarchy: IS-A taxonomy. Its competence is *category* — the
    # SUBSTANTIVES bank — which the dictionary genus chains cannot reach
    # (Wiktionary defines `animal` as "a member of the kingdom Animalia", never
    # "alive"). Scoped to category only so it contributes IS-A grounding and
    # not the DO/CAUSE/THINK noise its union-over-senses also carries.
    "wordnet_hierarchy": {
        "SOMETHING",
        "SOMEONE",
        "ALIVE",
        "BODY",
        "PEOPLE",
        "PART",
        "KIND",
    },
    # FrameNet: frame semantics — event structure, participant roles, and the
    # cognition/perception/communication/emotion frames that are its core
    # competence. Affect POLARITY is excluded: frame-level GOOD is polarity-blind
    # (the Judgment frame fires identically for `praise` and `criticize`) — the
    # affect sources (NRC / SentiWordNet) own that signal.
    # SOMEONE/SOMETHING are excluded: the parser derives them from Agent/Theme
    # FRAME-ELEMENT slots, i.e. the verb's argument FRAME, not the word's own
    # meaning (they fire on virtually every verb — with PropBank agreeing, the
    # ≥2 gate would flood the lexicon; measured 2026-07-01). Argument frames
    # belong in the verb-template layer, not primitive_values.
    "framenet": {
        "DO",
        "HAPPEN",
        "MOVE",
        "CAUSE",
        "BE",
        "EXIST",
        "HAVE",
        "START",
        "END",
        "SAY",
        "WORDS",
        "THINK",
        "KNOW",
        "SEE",
        "HEAR",
        "FEEL",
        "TOUCH",
        "WANT",
        "BODY",
        "ALIVE",
        "WHERE",
        "WHEN",
        "BEFORE",
        "AFTER",
        "TOWARD",
        "AWAY",
        "BECAUSE",
        "WITH",
        "MUST",
        "CAN",
        "MOMENT",
        "LONG_TIME",
    },
    # PropBank: verb rolesets — the same predicate-argument competence family as
    # VerbNet (which completes the designed verb-source trio), plus the
    # aspect/possession/cognition verbs its curated class map encodes. Affect
    # polarity excluded for the same reason as FrameNet.
    # SOMEONE/SOMETHING (ARG0/ARG1 slots) and WHEN/WHERE/TOWARD/BECAUSE
    # (ARGM-* adjunct slots) are excluded — argument-frame structure, not the
    # verb's own decomposition (same rationale as FrameNet above).
    "propbank": {
        "DO",
        "HAPPEN",
        "MOVE",
        "BE",
        "EXIST",
        "CAUSE",
        "SAY",
        "WORDS",
        "HAVE",
        "START",
        "END",
        "KNOW",
        "THINK",
        "SEE",
        "HEAR",
        "FEEL",
        "TOUCH",
        "WANT",
        "ALIVE",
        "BODY",
    },
    # ConceptNet: crowd-sourced commonsense relations. Competence is the
    # STRUCTURAL relations — taxonomy/mereology/location/capability/purpose.
    # Excluded: affect (HasProperty good/bad is crowd noise), and NOT — an
    # Antonym edge is a relation BETWEEN words, not a NOT-component of either
    # word's own decomposition.
    "conceptnet": {
        "KIND",
        "PART",
        "HAVE",
        "WHERE",
        "NEAR",
        "CAUSE",
        "CAN",
        "WANT",
        "DO",
        "BEFORE",
        "START",
        "END",
        "SOMETHING",
    },
    # USAS: UCREL semantic-field taxonomy — coarse categorical/topical typing,
    # the topical complement to wordnet_hierarchy's IS-A. Excluded: quantifier
    # fields (the quantifier layer owns those), pronoun/deixis fields (tier-0
    # owns the primes), modality (the modal track is a separate gap), and
    # affect modifiers (owned by the affect sources).
    "usas": {
        "BODY",
        "ALIVE",
        "MOVE",
        "WHERE",
        "WHEN",
        "SOMEONE",
        "PEOPLE",
        "SOMETHING",
        "SAY",
        "WORDS",
        "THINK",
        "KNOW",
        "FEEL",
        "WANT",
        "DO",
        "BE",
        "HAVE",
        "START",
        "LONG_TIME",
        "SHORT_TIME",
    },
}


def filter_votes_by_scope(
    source_name: str,
    votes: Dict[str, Tuple[int, float]],
    scope: Optional[Mapping[str, Set[str]]] = None,
) -> Dict[str, Tuple[int, float]]:
    """Drop a source's votes for primitives outside its semantic scope.

    Two filters apply in order:

    1. **Word-scale boundary** (always): drop votes for the 29 primitives in
       :data:`WORD_SCALE_EXCLUDED_PRIMITIVES`. These belong to sentence-
       scale or are hierarchy operators; no word-scale source — including
       broadly-unrestricted ones like Wiktionary v2 — may vote for them.
    2. **Per-source scope** (if the source is listed): keep only votes for
       primitives in the source's semantic domain.

    Args:
        source_name: name of the source (matches the integrator's parser key).
        votes: ``{primitive_name: (value, confidence)}`` from
            ``parser.to_primitives_with_confidence``.
        scope: optional override of :data:`SOURCE_PRIMITIVE_SCOPE`. The
            default uses the empirically-derived map.

    Returns:
        Filtered votes dict.
    """
    # Word-scale boundary first — applies to every source unconditionally.
    votes = {prim: val for prim, val in votes.items() if prim not in WORD_SCALE_EXCLUDED_PRIMITIVES}

    scope_map = scope if scope is not None else SOURCE_PRIMITIVE_SCOPE
    allowed = scope_map.get(source_name)
    if allowed is None:
        # Unrestricted source — typically Wiktionary v2 or future
        # definition-based broad-coverage sources.
        return votes
    return {prim: val for prim, val in votes.items() if prim in allowed}


def in_scope(source_name: str, primitive: str) -> bool:
    """True if ``source_name`` may vote for ``primitive`` under the scope map."""
    allowed = SOURCE_PRIMITIVE_SCOPE.get(source_name)
    if allowed is None:
        return True
    return primitive in allowed
