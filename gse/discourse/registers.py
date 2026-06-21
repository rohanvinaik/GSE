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

from collections import defaultdict
from typing import Dict, List, Optional, Sequence

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
        # contemporary HF sources (augment — modern text vs the 1961 Brown):
        "modern_news",      # ag_news — contemporary journalism (diachronic vs `news`)
        "reviews_modern",   # imdb — contemporary informal opinion/reviews
        "twitter",          # tweet_eval — social media (the messiest modern register)
    ],
    # NON-SPEECH: words that communicate but do not represent literal speech.
    "non_speech": [
        "poetry",     # verse — no sentence-boundary structure
        "reference",  # dictionary / encyclopedia entries (definitional)
        "list",       # grocery / packing / catalog / agenda (fragmentary)
    ],
}

# --- the middle level: super-registers -----------------------------------------
# Derived from hierarchical (ward) clustering of per-genre profile centroids on the
# corpus (NOT hand-grouped) — the granularity the signal + data actually support.
# A super-register is the unit a voice-mode toolkit attaches to (the Genesis-style
# Compass: deduction baseline + censor + explanation, inherited down to the genre).
SUPER_REGISTER_OF: Dict[str, str] = {
    # NARRATIVE — fiction sub-genres (the dominant confusion cluster).
    "adventure": "narrative", "fiction": "narrative", "mystery": "narrative",
    "romance": "narrative", "science_fiction": "narrative",
    # REPORTORIAL — factual/official prose.
    "editorial": "reportorial", "government": "reportorial", "learned": "reportorial",
    "news": "reportorial", "newswire": "reportorial",
    "modern_news": "reportorial",   # diachronic augment of `news` (same node on purpose)
    # NEW super-registers from the contemporary feed (new SoM specialists):
    "reviews_modern": "review",     # contemporary opinion — its own specialist
    "twitter": "social",            # social media — its own specialist (messiest)
    # ESSAYISTIC — discursive/elevated prose.
    "belles_lettres": "essayistic", "hobbies": "essayistic", "humor": "essayistic",
    "lore": "essayistic", "religion": "essayistic", "reviews": "essayistic",
    # LEXICALLY_DIVERGENT — high-OOV registers (slang vs archaic); they cluster
    # together because both need lexical-repair voice-modes (different dictionaries).
    "chat": "lexically_divergent", "shakespeare": "lexically_divergent",
    # distinct singletons:
    "archaic_english": "archaic",
    "poetry": "poetry", "reference": "reference", "list": "list",
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


def super_register_of(genre: str) -> str:
    """The middle-level super-register for a fine genre (the toolkit-inheritance
    unit). Raises on an undeclared genre."""
    try:
        return SUPER_REGISTER_OF[genre]
    except KeyError as exc:
        raise KeyError(
            f"unknown genre {genre!r}; declare it in SUPER_REGISTER_OF") from exc


# --- the resolution tree: the recognizer descends it, deepest-confident-node ----
# The nested SoM router (gse.discourse.nested_router) is a specialist per INTERNAL
# node, each classifying among that node's children. The tree is just the taxonomy
# read top-down: ROOT → register_class → super_register → genre (leaves).
ROOT = "*"

# Super-registers, as a set, to classify a node by its level without a lookup table.
_SUPER_REGISTERS = frozenset(SUPER_REGISTER_OF.values())


def taxonomy_tree(genres: Optional[Sequence[str]] = None) -> Dict[str, List[str]]:
    """Parent → sorted children for every INTERNAL node of the resolution tree.

    Restricted to ``genres`` when given (so the cascade is built over exactly what
    the corpus contains — a super-register with one present genre needs no router);
    defaults to the full declared taxonomy. Leaves (genres) are not keys.
    """
    gs = sorted(set(genres)) if genres is not None else list(ALL_GENRES)
    tree: Dict[str, set] = defaultdict(set)
    for g in gs:
        cls = register_class_of(g)
        sup = super_register_of(g)
        tree[ROOT].add(cls)
        tree[cls].add(sup)
        # Singleton super-registers (poetry/reference/list) have a single genre child
        # WITH THE SAME NAME. Adding it makes a self-referential node
        # (tree["poetry"] == ["poetry"]) — recursive nonsense that loops the descent.
        # The super-register IS the leaf there; only add a genre child that refines it.
        if g != sup:
            tree[sup].add(g)
    return {node: sorted(children) for node, children in tree.items()}


def child_on_path(node: str, genre: str) -> Optional[str]:
    """The child of ``node`` on the root→``genre`` path, or ``None`` if ``genre``
    does not pass through ``node``. This is the per-node training label: at ROOT a
    genre's label is its register_class, at a register_class node its super_register,
    at a super_register node the genre itself."""
    if node == ROOT:
        return register_class_of(genre)
    if node in REGISTER_TAXONOMY:                      # node is a register_class
        return super_register_of(genre) if register_class_of(genre) == node else None
    if node in _SUPER_REGISTERS:                       # node is a super_register
        return genre if super_register_of(genre) == node else None
    return None
