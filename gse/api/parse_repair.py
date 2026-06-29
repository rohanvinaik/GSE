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

# Tokens skipped when finding the nearest *content* flanker (determiners and
# punctuation sit between a verb and its arguments without being arguments).
# Locality alone discriminates the copula cases the arc version drew via arcs:
# "Duncan is a king" (right content = king → promote, feeds TYPE_ASSERT) vs
# "Mike is taller than Rex" (right content = taller/ADJ → no promote).
_SKIP_FLANK_POS = {"PUNCT", "DET"}


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


def _in_hyphen_compound(toks, i: int) -> bool:
    """True when ``toks[i]`` is a member of a hyphenated nominal compound
    (``cart-horse``) — a noun *modifier*, never a buried verb.

    The flanker search skips PUNCT, so it discards the hyphen — the one token that
    marks ``cart - horse colts`` a compound — and reads it as subject-verb-object,
    spuriously promoting the verb-sensed middle noun (``horse``). The hyphen is the
    compound signal; a real transitive verb is never directly joined by one. Detection
    is local and text-agnostic: a hyphen token immediately adjacent to the candidate
    whose other side is entity-like. (A spaced clause dash — ``There -- take`` — is a
    separate token shape and does not match.)
    """
    n = len(toks)
    if i - 2 >= 0 and toks[i - 1].text == "-" and _entity_like(toks[i - 2]):
        return True
    if i + 2 < n and toks[i + 1].text == "-" and _entity_like(toks[i + 2]):
        return True
    return False


def verbs_to_promote(doc) -> Set[int]:
    """Token indices of buried (mis-tagged) verbs to promote to ``pos == VERB``.

    A buried verb is a non-VERB token whose lemma has a verb sense and whose
    nearest *content* token on each side (determiners/punctuation skipped) is
    entity-like — the transitive-mistag signature (subject before, object
    after). WS1: the flanking signal is *positional* (the token stream), NOT
    spaCy dependency arcs — ``children``/``head`` are never read. Validated to
    match the arc version on the bounded register (``scripts/ws1_parity.py``);
    the coherence gate flags any tail divergence.
    """
    toks = list(doc)

    def _nearest_content(i: int, step: int):
        j = i + step
        while 0 <= j < len(toks):
            if toks[j].pos_ not in _SKIP_FLANK_POS:
                return toks[j]
            j += step
        return None

    promote: Set[int] = set()
    for i, t in enumerate(toks):
        if t.pos_ in ("VERB", "PUNCT"):
            continue
        if not _has_verb_sense(t.lemma_):
            continue
        if _in_hyphen_compound(toks, i):   # a hyphenated noun-compound member is a modifier, not a verb
            continue
        left = _nearest_content(i, -1)
        right = _nearest_content(i, +1)
        if left is not None and right is not None \
                and _entity_like(left) and _entity_like(right):
            promote.add(t.i)
    return promote


def _verbs_to_promote_arcs(doc) -> Set[int]:
    """Legacy arc-based reference — kept only for the WS1 parity harness.

    Reads spaCy ``children``/``head``/``dep_``; the production path no longer
    does. Delete once the parity gate is green and the engine swap lands.
    """
    promote: Set[int] = set()
    for t in doc:
        if t.pos_ == "VERB" or t.dep_ == "punct":
            continue
        if not _has_verb_sense(t.lemma_):
            continue
        neighbors = list(t.children)
        if t.head.i != t.i:
            neighbors.append(t.head)
        ents = [n for n in neighbors if n.dep_ != "punct" and _entity_like(n)]
        if any(n.i < t.i for n in ents) and any(n.i > t.i for n in ents):
            promote.add(t.i)
    return promote
