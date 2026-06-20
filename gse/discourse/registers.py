"""The register taxonomy — the canonical label space for text-category resolution.

Single source of truth for *what the dispatcher resolves a text into*. Two-level
hierarchy: a top-line ``register_class`` (the structural axis — does the text
represent literal speech, or is it non-speech structured text?) over fine
``genre`` labels. The corpus is labeled against this, and the Society-of-Mind
router learns to resolve into it; voice-mode scripts attach per genre (and inherit
down the class).

Extensible by design: adding a register = adding a label here + a provider in
``scripts/build_l2_corpus.py``. The diachronic axis (archaic / translationese) and
the long-tail messy registers (social, OCR-noise, L2-English) slot in as new genres
under the appropriate class.
"""
from __future__ import annotations

from typing import Dict, List

# register_class → genres. The structural top-line split.
REGISTER_TAXONOMY: Dict[str, List[str]] = {
    # SPEECH-derived: prose/verse that represents or transcribes human speech.
    "speech": [
        # Brown corpus (genre-balanced, curated):
        "adventure", "belles_lettres", "editorial", "fiction", "government",
        "hobbies", "humor", "learned", "lore", "mystery", "news", "religion",
        "reviews", "romance", "science_fiction",
        # added registers:
        "chat",             # IM / forum posts (fragmentary, conversational)
        "newswire",         # wire-service news
        "archaic_english",  # older English (e.g. the 1611 KJV)
        "shakespeare",      # Early Modern verse drama
    ],
    # NON-SPEECH: words that communicate but do not represent literal speech.
    "non_speech": [
        "poetry",     # verse — no sentence-boundary structure
        "reference",  # dictionary / encyclopedia entries (definitional)
        "list",       # grocery / packing / catalog / agenda (fragmentary)
    ],
}

# Reverse index: genre → register_class.
GENRE_TO_CLASS: Dict[str, str] = {
    g: cls for cls, genres in REGISTER_TAXONOMY.items() for g in genres
}

ALL_GENRES: List[str] = sorted(GENRE_TO_CLASS)


def register_class_of(genre: str) -> str:
    """The top-line class for a fine genre (raises on an unknown genre — labels
    must be declared here so the corpus and the router stay in sync)."""
    try:
        return GENRE_TO_CLASS[genre]
    except KeyError as exc:
        raise KeyError(
            f"unknown genre {genre!r}; declare it in REGISTER_TAXONOMY") from exc
