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
    "n't": ["not"], "'re": ["are"], "'ve": ["have"], "'ll": ["will"], "'m": ["am"],
    "'d": ["would", "had"],   # ambiguous: modal vs perfect
    "'s": ["is", "has"],      # ambiguous: copula vs perfect  (possessive: see note)
}


def candidates(fragment: str) -> List[str]:
    """The candidate expansions for a contraction fragment (error-model step)."""
    return list(CONTRACTION_EXPANSIONS.get(fragment.lower(), []))


def _is_participle(tok: Any) -> bool:
    """A past-participle / perfect form — GSE's own lemmatizer marks it: a verb whose
    surface differs from its lemma (``gone``≠``go``, ``walked``≠``walk``). A base form
    (``go``==``go``) or a nominal is not."""
    return (getattr(tok, "pos_", "") in ("VERB", "AUX")
            and tok.text.lower() != tok.lemma_)


def resolve_contraction(fragment: str, following: Optional[Any]) -> Optional[str]:
    """Expand a contraction fragment, disambiguating the ambiguous ones (`'d`/`'s`)
    by the FOLLOWING token. ``following=None`` (or no signal) → the default expansion.

    Returns the resolved word, or ``None`` if ``fragment`` is not a contraction.
    """
    cands = candidates(fragment)
    if not cands:
        return None
    if len(cands) == 1 or following is None:
        return cands[0]
    # ambiguous 'd/'s: a following past-participle → the perfect reading (had/has);
    # otherwise the default (would/is). (Possessive 's — "Mike's dog" — is the
    # THREE-way case; use resolve_apostrophe_s, which adds the clause-verb signal.)
    return cands[1] if _is_participle(following) else cands[0]


# Result sentinel for the possessive reading of ``'s`` (not a word expansion).
POSSESSIVE = "POSSESSIVE"


def resolve_apostrophe_s(following: Optional[Any], verb_or_copula_after: bool) -> str:
    """The integrated three-way ``'s`` resolver — the spell-check voice-mode completing
    the ``possessive: see note`` deferral. ``'s`` is one of:

    * ``has`` — the perfect, when the FOLLOWING token is a past participle
      (``the fire's gone`` = the fire HAS gone). Checked FIRST so the participle is
      not mistaken for a separate clause verb.
    * ``POSSESSIVE`` — when ANOTHER verb/copula appears later, so ``'s`` is not the
      clause's own predicate: the ``'s``-headed NP is an argument
      (``White's suggestion flattered``) or a possessive subject of that verb
      (``Brenner's voice was oily`` — the copula is ``was``, not ``'s``).
    * ``is`` — the copula ONLY when nothing else could be the predicate
      (``fire's too big`` = the fire IS too big), which flows into the copula
      TYPE_ASSERT synthesis. Conservative by design: re-tag ``'s`` to a copula only
      when confident; otherwise leave it for the (working) possessive path.

    The caller supplies the context signals (the following token; whether any
    verb/copula follows) — the candidate→context→resolve shape, one branch added.
    """
    if following is not None and _is_participle(following):
        return "has"
    if verb_or_copula_after:
        return POSSESSIVE
    return "is"
