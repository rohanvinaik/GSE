"""Context-aware spell-correction — the sentence-scale layer over the word-level
:mod:`gse.nlp.spellcheck`.

The word-level corrector ranks by the noisy channel (edit cost + frequency prior).
That resolves unambiguous typos but is structurally blind: it cannot tell ``weird``
from ``wired`` (same edit, frequency favours the wrong one), because the deciding
evidence is the *clause*, not the word. This module adds the two context signals the
residual confusions need — each deterministic and in-process, no sparse-wiki (which
is a named-entity grounder, not a common-word topical signal):

1. **structural well-formedness** (the GSE-native parse signal). Substitute each
   candidate into the sentence, re-encode, and count grammatical DEFECTS in the parse:
   a degraded/collapsed clause, a verb sitting in a pre-nominal modifier slot
   (``a wired ghost`` -> ``DET VERB NOUN``), a dangling preposition with no object.
   The candidate that yields the most well-formed parse is preferred. This is the
   flywheel's "rank by which one makes the clause cohere", made concrete with a
   well-formedness scorer richer than the collapse-only coherence gate.

2. **gloss-overlap topical coherence** (Lesk, 1986). The structural signal is blind
   to two same-POS candidates (``weird``/``wired`` are both adjectives in some frames);
   gloss overlap breaks that tie. Overlap a candidate's WordNet definition bag with
   the context words (and their glosses): ``weird``'s gloss (strange/supernatural)
   overlaps ``ghost``'s; ``wired``'s (electrical/connected) does not. Definitional,
   deterministic, already in GSE's dependency set.

Combined score (minimised):  noisy_channel + W_STRUCT*defects - W_GLOSS*gloss_coherence.
A grammatical defect is a strong penalty (~one edit); gloss coherence is a bounded
pull that breaks small ties without overriding the error model or structure.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import FrozenSet, List, Optional, Sequence, Tuple

from gse.nlp.native import _STOP
from gse.nlp.spellcheck import Candidate, _DEFAULT_LEXICON, propose, _Lexicon

# Weights: a structural defect costs ~one edit; gloss coherence (0..1) pulls up to ~1.
W_STRUCT = 1.0
W_GLOSS = 1.0
_TOPK = 6  # only the cheapest few candidates are worth a full re-parse
# Commit only when the best beats the runner-up by this combined-score margin;
# otherwise abstain. A minimal pair the signals cannot separate (weird/wired) lands
# inside the margin -> honest abstention rather than a confident-wrong commit.
_COMMIT_MARGIN = 0.5


# --------------------------------------------------------------------------- #
# Structural well-formedness: substitute, re-parse, count grammatical defects  #
# --------------------------------------------------------------------------- #
def _structural_defects(tokens) -> int:
    """Genuine grammatical defects in a parsed token sequence (TokenTrace list).
    Higher = less well-formed. Deliberately conservative — only SOUND defects:

    * dangling preposition — an ADP that ends the clause or is followed by a verb,
      with no nominal object (``with read``).

    NOTE: a ``DET VERB NOUN`` pattern (``a wired ghost``) is NOT a defect — ``wired``
    is a legitimate participial adjective. Penalising it (an earlier rule) was unsound:
    it punished a valid reading and produced confidently-wrong corrections. The lesson:
    a same-POS / participle minimal pair (``weird``/``wired``) is NOT a structural
    distinction; the layer must abstain on it, not invent a defect.
    """
    defects = 0
    pos = [t.pos for t in tokens]
    n = len(pos)
    for i, p in enumerate(pos):
        if p == "ADP" and (i == n - 1 or pos[i + 1] in ("VERB", "AUX")):
            defects += 1
    return defects


def _parse_defects(text: str, encoder) -> int:
    """Encode ``text`` and count structural defects (parse + coherence gate)."""
    from gse.symbolic import from_trace, resolve, evaluate_tree
    from gse.symbolic.coherence import coherence_report

    trace = encoder.encode(text)
    defects = _structural_defects(trace.tokens)
    try:
        tree = evaluate_tree(resolve(from_trace(trace)))
        defects += len(coherence_report(tree, trace))
    except Exception:
        defects += 1  # a parse that throws is itself a defect
    return defects


# --------------------------------------------------------------------------- #
# Gloss-overlap (Lesk) topical coherence                                       #
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8192)
def _gloss_bag(word: str) -> FrozenSet[str]:
    """Content tokens drawn from all of ``word``'s WordNet glosses (definitions)."""
    from nltk.corpus import wordnet as wn

    bag = set()
    for syn in wn.synsets(word):
        for tok in syn.definition().lower().replace(",", " ").replace(";", " ").split():
            tok = tok.strip(".()'\"")
            if len(tok) > 2 and tok not in _STOP:
                bag.add(tok)
    return frozenset(bag)


def _gloss_coherence(candidate: str, context_words: Sequence[str]) -> float:
    """Lesk overlap: candidate's gloss bag vs the context words and their gloss bags."""
    cb = _gloss_bag(candidate)
    if not cb:
        return 0.0
    ctx = set(w.lower() for w in context_words)
    for w in context_words:
        ctx |= _gloss_bag(w)
    if not ctx:
        return 0.0
    return len(cb & ctx) / len(cb | ctx)


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ScoredCandidate:
    word: str
    noisy: float
    defects: int
    gloss: float

    @property
    def total(self) -> float:
        return self.noisy + W_STRUCT * self.defects - W_GLOSS * self.gloss

    def __repr__(self) -> str:
        return (f"{self.word}(ns={self.noisy:.2f}, def={self.defects}, "
                f"gloss={self.gloss:.2f}, tot={self.total:.2f})")


@dataclass(frozen=True)
class ContextCorrection:
    surface: str
    committed: Optional[str]
    ranked: Tuple[ScoredCandidate, ...]
    note: str = ""

    def __repr__(self) -> str:
        head = self.committed if self.committed else "ABSTAIN"
        top = ", ".join(repr(c) for c in self.ranked[:4])
        return f"ContextCorrection({self.surface!r} -> {head} | [{top}])"


def suggest_in_context(
    surface: str,
    context_words: Sequence[str],
    encoder,
    sentence_template: Optional[str] = None,
    n: int = 5,
    lexicon: _Lexicon = _DEFAULT_LEXICON,
) -> List[ScoredCandidate]:
    """Top-``n`` context-ranked suggestions (structural + gloss + noisy-channel).
    Empty if the surface already grounds. The full ranked list a UI surfaces as
    "did you mean", best first."""
    return list(correct_in_context(
        surface, context_words, encoder, sentence_template, lexicon
    ).ranked[:n])


_PREDICATE_POS = {"VERB", "AUX"}


def _token_pos(text: str, word: str, encoder) -> Optional[str]:
    """The POS the parser assigns to ``word`` in ``text`` (local role signal)."""
    for t in encoder.encode(text).tokens:
        if t.token.lower() == word.lower():
            return t.pos
    return None


def recover_rare_tail(surface, sentence_template, encoder,
                      lexicon: _Lexicon = _DEFAULT_LEXICON) -> Optional[str]:
    """Recover a rare-tail grounding token (a typo that happens to be an obscure
    dictionary word, e.g. ``cen``) — ONLY structure-confirmed and to a common target.
    Returns the recovered common word, or None (leave the surface untouched).

    Conservative by construction: a candidate is accepted only if (a) it is in the small
    common-target set, and (b) it takes a *predicate* role (VERB/AUX) that the surface
    does NOT — i.e. the common word rescues a verb/aux slot the typo left orphaned
    (``we can tell``: ``can``=AUX vs ``cen``=NOUN). This is a LOCAL per-token signal, so
    it is not masked by other clauses in a long sentence. Same-POS pairs
    (``bok``/``book``, both NOUN) yield no role change -> left alone; jargon has no
    common-target neighbour -> never touched."""
    from gse.nlp.spellcheck import _edits1, Candidate, looks_non_lexical
    if sentence_template is None or looks_non_lexical(surface):
        return None                                         # acronyms/code/names never recovered
    cands = [Candidate(c, ec, lexicon.prior(c)) for c, ec in _edits1(surface.lower()).items()
             if lexicon.is_common_target(c)]
    if not cands:
        return None
    surf_pos = _token_pos(sentence_template.replace("___", surface), surface, encoder)
    if surf_pos in _PREDICATE_POS:
        return None                                         # surface already fills a predicate role
    cands.sort(key=lambda c: (c.score, c.word))             # closest/commonest first
    for c in cands:
        if _token_pos(sentence_template.replace("___", c.word), c.word, encoder) in _PREDICATE_POS:
            return c.word                                   # common word rescues a verb/aux slot
    return None


def correct_in_context(
    surface: str,
    context_words: Sequence[str],
    encoder,
    sentence_template: Optional[str] = None,
    lexicon: _Lexicon = _DEFAULT_LEXICON,
) -> ContextCorrection:
    """Correct ``surface`` using the full noisy-channel + structural + gloss score.

    ``context_words`` are the surrounding content lemmas (for gloss coherence).
    ``sentence_template`` (with ``___`` where the token goes) enables the structural
    re-parse; if omitted, only the noisy-channel + gloss signals are used.
    """
    if lexicon.grounds(surface):
        return ContextCorrection(surface, surface, (), "surface grounds")

    cands: List[Candidate] = propose(surface, lexicon)[:_TOPK]
    if not cands:
        return ContextCorrection(surface, None, (), "no grounded candidate")

    scored: List[ScoredCandidate] = []
    for c in cands:
        defects = 0
        if sentence_template is not None:
            defects = _parse_defects(sentence_template.replace("___", c.word), encoder)
        gloss = _gloss_coherence(c.word, context_words) if context_words else 0.0
        scored.append(ScoredCandidate(c.word, c.score, defects, gloss))

    scored.sort(key=lambda s: (s.total, s.word))
    best = scored[0]
    second = scored[1] if len(scored) > 1 else None
    decisive = second is None or (second.total - best.total) >= _COMMIT_MARGIN
    committed = best.word if decisive else None
    note = "committed" if committed else "signals do not decisively separate: abstained"
    return ContextCorrection(surface, committed, tuple(scored), note)
