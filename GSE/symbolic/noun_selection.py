"""Sentence-side noun sense selection: the bearer of a person-typed predicate keeps its someone or creature senses.

Selection is part of the read (Rohan, 2026-11-25 20:56: "Sentence-side selection. You arbitrarily split it into a
different step, when it isn't"). The predicates are those whose bearer the October-reviewed prime profiles type
``person`` (``valency_absence.person_bearer_primes``: THINK, KNOW, WANT, FEEL, SAY, DO); Goddard (2018) lets a
creature bear them ("something living ... something like this can feel something"). So when a sentence makes a noun
the bearer of such a predicate, the noun keeps the definitions that are SOMEONE+ or ALIVE+. When none qualifies,
nothing is restricted.

The bearer is read linearly (GSE's front end builds no arcs): an adjective predicates of the noun its noun phrase ends
in ("the happy dog"); a verb's bearer is the nominal before it, as ``frame_selection.clause_pattern`` reads a subject.
"""

from __future__ import annotations

import json

NOMINAL = {"NOUN", "PROPN", "PRON"}
NP_INNER = {"DET", "ADJ", "NUM", "ADV"}
CLAUSE_BREAK = {"PUNCT", "CCONJ", "SCONJ", "ADP"}


def _bears_person_predicate(encoder, token, pos: str) -> bool:
    from GSE.curation.lexicon_builder.valency_absence import person_bearer_primes

    values = encoder.lexical_lookup(token.lemma_.lower(), pos).get("primitives") or {}
    return any(values.get(bank) == 1 for bank in person_bearer_primes())


def _is_bearer(encoder, doc, position: int) -> bool:
    k = position - 1
    while k >= 0 and doc[k].pos_ in NP_INNER:
        if doc[k].pos_ == "ADJ" and _bears_person_predicate(encoder, doc[k], "ADJ"):
            return True
        k -= 1
    for k in range(position + 1, len(doc)):
        token = doc[k]
        if token.pos_ in NOMINAL or token.pos_ in CLAUSE_BREAK:
            return False
        if token.pos_ == "VERB":
            return _bears_person_predicate(encoder, token, "VERB")
    return False


def bearer_senses(encoder, doc, position: int, lemma: str) -> set[str] | None:
    """The noun's someone/creature definitions when its sentence makes it a person-typed bearer; else None."""
    if not _is_bearer(encoder, doc, position):
        return None
    rows = encoder.conn.execute(
        "SELECT d.entry_id, d.domains FROM definition_states d JOIN lexemes l ON d.lexeme_id = l.id"
        " WHERE l.lemma = ? AND l.pos = 'noun'",
        (lemma,),
    ).fetchall()
    kept = {
        entry
        for entry, raw in rows
        for domains in [json.loads(raw)]
        if domains.get("SOMEONE") == [1] or domains.get("ALIVE") == [1]
    }
    return kept or None
