"""Word-scale morphological operations — the comparative/superlative slice.

The first instance of *morphology-as-operation* (``docs/MORPHOLOGY_RESEARCH_BRIEF.md``).
An inflected surface collapses to ``base × grammatical-feature`` via the same
propose→coherence-resolve shape as :mod:`gse.nlp.contractions`:

1. **marker** — an inflectional process on the surface triggers the operation
   (here ``-er``/``-est``, or a suppletive degree form).
2. **propose base candidate(s)** — the *inverse formation model*: the four regular
   English orthographic processes (bare / silent-``e`` / gemination / ``y→i``) run
   BACKWARD. A small, closed generator — not a per-word table, not a lookup DB.
3. **resolve by coherence** — keep the candidate that GROUNDS as a gradable
   adjective (WordNet, the token-layer lexical oracle). The oracle, not a rule
   order, decides — which also resolves the ``-er`` collision for free: comparative
   ``bigger`` (base ``big`` grounds) vs agentive ``teacher`` (``teach`` is a verb,
   not gradable → declines) vs non-morphemic ``water`` (no base grounds → declines).

The orthographic facts of English are encoded ONCE here, as the *definition* of the
operation, gated by the grounding oracle — categorically different from an ad-hoc
suffix-strip or a runtime DB. The base is the word-lens identity (the lemma); the
degree is the sentence-lens half of the decomposition.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from nltk.corpus import wordnet as wn

# The degree feature carried alongside the base (the sentence-lens half of the
# decomposition). Recorded by the operation; a future slice rides it on the `morph`
# channel once a consumer exists (MORPH_TO_TAM ignores unknown features).
COMPARATIVE = "Degree=Cmp"
SUPERLATIVE = "Degree=Sup"

# Suppletive degree forms — a FINITE closed list (a fact of the language, like the
# irregular-verb table; legitimately enumerable, NOT the rejected lookup DB).
# Restricted to the unambiguous adjective suppletives; the overloaded quantifier
# degrees (more/most/less/least) are deferred — they are periphrastic markers and
# determiners, a separate concern.
_SUPPLETIVE_DEGREE = {
    "better": "good", "best": "good",
    "worse": "bad", "worst": "bad",
    "further": "far", "furthest": "far",
    "farther": "far", "farthest": "far",
}
# (elder/eldest excluded — too often nominal: "the elder", "village elder".)


def _is_gradable_adjective(word: str) -> bool:
    """The grounding oracle at the token layer: a known adjective (WordNet ``a``/``s``
    synsets). Adjectives are the gradable category, so a verb base (``teach``) or a
    non-word (``wat``/``togeth``) fails — which is exactly what declines the ``-er``
    collision and the false strips."""
    return bool(wn.synsets(word, pos="a") or wn.synsets(word, pos="s"))


def _candidate_bases(stem: str) -> List[str]:
    """Inverse comparative/superlative formation — the four regular orthographic
    processes run BACKWARD, proposing base candidates. The grounding oracle selects,
    so over-proposing is harmless; the set is closed (the four processes), not open.

    bare ``tall(er)→tall`` · silent-``e`` ``larg(er)→large`` · gemination
    ``bigg(er)→big`` · ``y→i`` ``earli(er)→early``.
    """
    cands = [stem, stem + "e"]
    if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
        cands.append(stem[:-1])             # gemination: bigg → big
    if stem.endswith("i"):
        cands.append(stem[:-1] + "y")       # y→i: earli → early, happi → happy
    return cands


def resolve_degree(surface: str) -> Optional[Tuple[str, str]]:
    """The comparative/superlative operation: ``surface → (base, degree-feature)``,
    or ``None`` when ``surface`` is not a degree form.

    Suppletive forms resolve via the finite list; otherwise strip ``-est``/``-er``
    and select the PROPOSED base that grounds as a gradable adjective. A word that
    merely ends in ``-er``/``-est`` without a grounding base (``together``, ``water``,
    ``teacher``) returns ``None`` — it is not a degree form.
    """
    low = surface.lower()
    if low in _SUPPLETIVE_DEGREE:
        feat = SUPERLATIVE if low.endswith("st") else COMPARATIVE
        return _SUPPLETIVE_DEGREE[low], feat
    for suffix, feat in (("est", SUPERLATIVE), ("er", COMPARATIVE)):
        if low.endswith(suffix) and len(low) > len(suffix) + 1:
            stem = low[: -len(suffix)]
            for cand in _candidate_bases(stem):
                if _is_gradable_adjective(cand):
                    return cand, feat
            return None  # ends in the suffix but no base grounds → not a degree form
    return None
