"""Upstream parse repair for the verb-POS mistag.

spaCy's small model mistags an unknown proper-noun subject + a noun/verb
ambiguous predicate ("Macbeth murders Duncan") so that the verb is tagged NOUN
and the subject demoted to ADJ. With no ``pos == "VERB"`` token in the clause,
``expression._try_event`` finds no predicate and the clause collapses to a bare
nominal — dropping the subject, which blocks rule-learning downstream (Genesis).

This module detects the buried verb from its *local dependency arc-neighbourhood*
and reports its token index; the encoder promotes that token's POS to VERB so the
existing position-based EVENT synthesis fires. Detection is conservative by
construction: it requires a verb-sense token flanked by entity-like tokens on
*both* sides (subject before, object after), the transitive mistag signature —
so a verbless noun phrase ("the big red ball"), whose verb-sense head has no
entity-like flankers, is never promoted.

Only POS is corrected (the clause-graph fix the seam needs); the HDC vector's
role binding is a separate, deliberate follow-up.
"""

from __future__ import annotations

from typing import Set

from nltk.corpus import wordnet as wn

_NOMINAL_POS = {"PROPN", "NOUN", "PRON"}


def _has_verb_sense(lemma: str) -> bool:
    """Dictionary fact: does this lemma have a verb reading? (Not a verb list.)"""
    return bool(wn.synsets(lemma, pos="v"))


def _has_adjective_sense(lemma: str) -> bool:
    return bool(wn.synsets(lemma, pos="a") or wn.synsets(lemma, pos="s"))


def _entity_like(tok) -> bool:
    """True for a referential nominal — including a proper noun the mistag has
    demoted to ADJ (a title-case content word that is not actually an adjective).
    """
    if tok.pos_ in _NOMINAL_POS:
        return True
    return (
        tok.is_alpha
        and tok.is_title
        and not tok.is_stop
        and not _has_adjective_sense(tok.lemma_)
    )


def verbs_to_promote(doc) -> Set[int]:
    """Token indices of buried (mis-tagged) verbs to promote to ``pos == VERB``.

    A buried verb is a non-VERB token whose lemma has a verb sense and which is
    flanked, within its dependency arc-neighbourhood (children + head), by
    entity-like tokens on both sides.
    """
    promote: Set[int] = set()
    for t in doc:
        if t.pos_ == "VERB" or t.dep_ == "punct":
            continue
        if not _has_verb_sense(t.lemma_):
            continue
        neighbors = list(t.children)
        if t.head.i != t.i:  # not the ROOT (which heads itself)
            neighbors.append(t.head)
        ents = [n for n in neighbors if n.dep_ != "punct" and _entity_like(n)]
        if any(n.i < t.i for n in ents) and any(n.i > t.i for n in ents):
            promote.add(t.i)
    return promote
