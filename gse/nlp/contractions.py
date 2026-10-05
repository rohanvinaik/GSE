"""Contraction resolution — the first test of the spell-check / error-correction pipeline.

A contraction's post-apostrophe fragment is a FRONT-TRUNCATED word (`'d`=would/had,
`'ve`=have, `n't`=not, …). Most expand deterministically; a few are genuinely
ambiguous (`'d` = would|had, `'s` = is|has) and resolve by CONTEXT — the same
candidate → context → best-fit shape as the general spell-check (and the GenomeVault
nucleotide-misread model):

1. **error model → candidates** — the front-truncation maps a fragment to a small,
   *known* candidate set (the contraction expansions).
2. **context → rank** — the implicit grammatical role of the FOLLOWING word picks
   among candidates, read from its **inflection** (GSE already lemmatizes it): a past
   participle (surface ≠ lemma — `gone`≠`go`, `left`≠`leave`) signals the perfect
   (`'d`→had, `'s`→has); a base form or a nominal signals the modal/copula
   (`'d`→would, `'s`→is).
3. **resolve.**

Contractions are the clean validation case: the candidate set is tiny and the ground
truth is known. The *general* spell-check keeps this shape but swaps step-1's error
model (edit-distance / keyboard / phonetic) and step-2's ranker (Jaccard of lexicon
vectors); contractions exercise the pipeline end-to-end first.
"""

from __future__ import annotations

from typing import Any, List, Optional

# Front-truncation error model: fragment → candidate expansions (default first).
CONTRACTION_EXPANSIONS = {
    "n't": ["not"],
    "'re": ["are"],
    "'ve": ["have"],
    "'ll": ["will"],
    "'m": ["am"],
    "'d": ["would", "had"],  # ambiguous: modal vs perfect
    "'s": ["is", "has"],  # ambiguous: copula vs perfect  (possessive: see note)
}


def candidates(fragment: str) -> List[str]:
    """The candidate expansions for a contraction fragment (error-model step)."""
    return list(CONTRACTION_EXPANSIONS.get(fragment.lower(), []))


def contraction_reading(fragment: str, next_pos: str, next_text: str, next_lemma: str) -> str:
    """The word a contraction fragment stands for, read from the token after it; ``""`` if it is not a fragment.

    The two ambiguous fragments resolve by that token's inflection: before a past participle (a VERB or AUX whose
    surface differs from its lemma, ``gone``≠``go``) ``'d`` is ``had`` and ``'s`` is ``has``; otherwise the default,
    ``would`` and ``is``. Every other fragment has one reading. The next token is given as strings (its POS, its
    surface, its lemma; empty when there is none), so the decision is total over plain values.
    """
    cands = candidates(fragment)
    if not cands:
        return ""
    return cands[1] if len(cands) > 1 and is_past_participle(next_pos, next_text, next_lemma) else cands[0]


def is_past_participle(pos: str, text: str, lemma: str) -> bool:
    """A past participle, as both contraction readers judge one: a VERB or AUX whose surface differs from its lemma
    (``gone``≠``go``, ``been``≠``be``) and is not a V-ing form ("dividing" is the present participle, read with is,
    never had or has)."""
    low = text.lower()
    return pos in ("VERB", "AUX") and low != lemma and not low.endswith("ing")


def resolve_contraction(fragment: str, following: Optional[Any]) -> Optional[str]:
    """Expand a contraction fragment, disambiguating the ambiguous ones (`'d`/`'s`)
    by the FOLLOWING token. ``following=None`` (or no signal) → the default expansion.

    Returns the resolved word, or ``None`` if ``fragment`` is not a contraction. The decision is
    :func:`contraction_reading`; this reads the following token's POS, surface and lemma for it.
    (Possessive 's — "Mike's dog" — is the THREE-way case; use resolve_apostrophe_s, which adds the
    clause-verb signal.)
    """
    if following is None:
        reading = contraction_reading(fragment, "", "", "")
    else:
        reading = contraction_reading(fragment, getattr(following, "pos_", ""), following.text, following.lemma_)
    return reading or None


# Result sentinel for the possessive reading of ``'s`` (not a word expansion).
POSSESSIVE = "POSSESSIVE"
# The possessive before a plural noun the third-singular rule tagged VERB ("Duncan's guards"): the caller re-tags it.
POSSESSIVE_PLURAL = "POSSESSIVE_PLURAL"

# Hosts that never take a possessive 's: "it's", "that's", "there's", "who's" are always it is / it has (the possessive
# forms are its, whose, his, her). The indefinites are left out, since they do take one ("everyone's favourite").
_NEVER_POSSESSIVE_HOSTS = frozenset(
    {"it", "he", "she", "that", "this", "there", "here", "who", "what", "where", "when", "why", "how"}
)


def apostrophe_s_reading(
    host: str, host_is_name: bool, next_pos: str, next_text: str, next_lemma: str, verb_in_clause: bool
) -> str:
    """What an ``'s`` is, from the word it is attached to (``host``), the token after it, and whether another verb or
    copula already predicates its clause. Returns ``"is"``, ``"has"``, ``POSSESSIVE``, ``POSSESSIVE_PLURAL`` or ``"us"``.

    * After a host that never takes a possessive (``_NEVER_POSSESSIVE_HOSTS``: it, that, there, who, …) ``'s`` is the
      verb: ``has`` before a past participle ("it's gone"), else ``is`` ("it's raining", "that's why it works").
    * After ``let`` it is ``us`` ("let's go").
    * After a name, a following plural that the third-singular rule tagged VERB makes it possessive ("Duncan's guards
      became drunk"), where the plural would otherwise pass for a participle: ``POSSESSIVE_PLURAL``, which also tells
      the caller that the next word is that plural noun and must be re-tagged as one.
    * Otherwise ``has`` before a past participle ("the fire's gone"), the possessive when another verb or copula
      predicates the clause ("White's suggestion flattered"), and ``is`` when nothing else could ("the fire's too big").

    A past participle is a VERB or AUX whose surface differs from its lemma (``gone``≠``go``), never a V-ing form:
    "it's dividing" is the progressive, not the perfect. The next token is given as strings (empty when there is none).
    """
    host = host.lower()
    if host == "let":
        return "us"
    nxt = next_text.lower()
    participle = is_past_participle(next_pos, next_text, next_lemma)
    if host in _NEVER_POSSESSIVE_HOSTS:
        return "has" if participle else "is"
    if host_is_name and next_pos == "VERB" and nxt.endswith("s") and not nxt.endswith("ss"):
        return POSSESSIVE_PLURAL
    if participle:
        return "has"
    return POSSESSIVE if verb_in_clause else "is"


def resolve_apostrophe_s(
    following: Optional[Any], verb_or_copula_in_clause: bool, host: str = "", host_is_name: bool = False
) -> str:
    """The integrated three-way ``'s`` resolver: ``has`` (the perfect), ``POSSESSIVE``, or ``is`` (the copula), plus
    ``us`` after ``let``. The decision is :func:`apostrophe_s_reading`; this reads the following token's POS, surface
    and lemma for it. The caller supplies the context: the following token, whether another verb or copula predicates
    the clause, the host word the ``'s`` is attached to, and whether that host is a name.
    """
    if following is None:
        return apostrophe_s_reading(host, host_is_name, "", "", "", verb_or_copula_in_clause)
    return apostrophe_s_reading(
        host, host_is_name, getattr(following, "pos_", ""), following.text, following.lemma_, verb_or_copula_in_clause
    )
