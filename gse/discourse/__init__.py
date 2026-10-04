"""Discourse-scale (L2) GSE — beyond the single sentence.

The deterministic *signal layer* the L2 Society-of-Mind router navigates. GSE
encodes each sentence into a typed clause graph + HDC vector + coherence /
grounding flags (the sentence scale, ``gse.api`` / ``gse.symbolic``); this package
aggregates those per-sentence signals over a whole text into a single feature
profile — the "k-line pattern" a genre/archetype recognizer matches on.

It is **deterministic** (no learning here): the SoM is the small learned router
*over* these features, trained on a hand-curated corpus (see ``docs`` / the SoM
design). Infrastructure-first: the quality of these signals sets the router's
ceiling, so this is where the investment goes.
"""

from gse.discourse.profile import (
    PROFILE_FIELDS,
    TextProfile,
    split_sentences,
    text_profile,
)
from gse.discourse.registers import (
    ALL_GENRES,
    GENRE_TO_CLASS,
    REGISTER_TAXONOMY,
    SUPER_REGISTER_OF,
    register_class_of,
    super_register_of,
)

__all__ = [
    "PROFILE_FIELDS",
    "TextProfile",
    "split_sentences",
    "text_profile",
    "REGISTER_TAXONOMY",
    "GENRE_TO_CLASS",
    "SUPER_REGISTER_OF",
    "ALL_GENRES",
    "register_class_of",
    "super_register_of",
]
