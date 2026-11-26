"""A sentence's sense selection as one constraint problem, pruned to a fixpoint.

Grammar is a constraint harness (Rohan, 2026-11-25), and selection is part of the read, not a separate step (20:56).
Each content word is a variable whose domain is its senses (``word_senses``: one coherent core per genuinely distinct
meaning, Rohan 03:28; a definition with no load-bearing value is absorbed and is not a meaning). Two kinds of
constraint join them, each read from a stated source:

* frame: a verb sense is possible only if one of its WordNet member definitions has a sentence frame hosting the
  clause with some choice of its arguments' senses (``frame_selection.frame_hosts``); an argument sense is typed
  somebody when its core holds SOMEONE+, something when it holds SOMEONE 0, and is otherwise untyped. A sense with no
  WordNet frames supports every argument.
* bearer: a predicate sense whose core holds THINK, KNOW, WANT, FEEL, SAY or DO (the reviewed profiles'
  person-typed bearers, ``valency_absence.person_bearer_primes``) needs a bearer sense that is SOMEONE+ or ALIVE+
  (Goddard 2018: creatures can feel): an adjective's bearer is its noun phrase's head, a verb's is its subject.

A value with no support is removed until nothing changes (arc consistency). Elimination only: no definition is ranked,
and a domain is never emptied (when every value would go, the word is left unrestricted).
"""

from __future__ import annotations

import json
from itertools import product

from GSE.symbolic.frame_selection import CLAUSAL, NOMINAL, NP_INNER, frame_hosts, slot_type

CONTENT = {"NOUN": "noun", "VERB": "verb", "ADJ": "adj"}


def _senses(encoder, lemma: str, pos: str) -> dict[int, tuple[dict, tuple[str, ...]]]:
    """sense number -> (its core values, its member definitions)."""
    rows = encoder.conn.execute(
        "SELECT sense, assignments, members FROM word_senses WHERE lemma = ? AND pos = ?", (lemma, pos)
    ).fetchall()
    return {sense: (json.loads(core), tuple(json.loads(members))) for sense, core, members in rows}


def _type(values: dict) -> str:
    return "somebody" if values.get("SOMEONE") == 1 else "something" if values.get("SOMEONE") == 0 else "*"


def _bearer_ok(values: dict) -> bool:
    return values.get("SOMEONE") == 1 or values.get("ALIVE") == 1


def _definition_frames(entry: str, lemma: str) -> list[str] | None:
    """The definition's own WordNet frame strings, or None when it has none."""
    from urllib.parse import unquote

    from nltk.corpus import wordnet as wn

    if not entry.startswith("wordnet:"):
        return None
    try:
        synset = wn.synset(unquote(entry.rsplit(":", 1)[-1]))
    except Exception:
        return None
    lemmas = [name for name in synset.lemmas() if name.name().lower() == lemma.lower()]
    if synset.pos() != "v" or not lemmas:
        return None
    return [f.replace(lemmas[0].name(), "V") for f in lemmas[0].frame_strings()] or None


def _frames(members: tuple[str, ...], lemma: str) -> list[str] | None:
    """A sense's frames: its WordNet members' frames, or None when any member has none (it then constrains nothing)."""
    out = []
    for entry in members:
        frames = _definition_frames(entry, lemma)
        if frames is None:
            return None
        out.extend(frames)
    return out or None


def _arguments(doc, position: int) -> tuple[int | None, list, bool]:
    """(subject position, object positions or 'something' for a clausal object, 'to' + nominal position)."""
    subject = None
    for k in range(position - 1, -1, -1):
        if doc[k].pos_ in NOMINAL:
            subject = k
            break
        if doc[k].pos_ not in NP_INNER and doc[k].pos_ != "AUX":
            break
    objects, to_target, k = [], None, position + 1
    while k < len(doc):
        token = doc[k]
        if token.pos_ == "ADP" and token.lemma_.lower() == "to":
            j = k + 1
            while j + 1 < len(doc) and doc[j + 1].pos_ in NP_INNER:
                j += 1
            if j < len(doc) and doc[j].pos_ in NOMINAL:
                to_target = j
            k = j + 1
            continue
        if token.lemma_.lower() in CLAUSAL:
            objects.append("something")
            break
        if token.pos_ not in NP_INNER:
            break
        j = k
        while (
            j + 1 < len(doc) and doc[j + 1].pos_ in {"NOUN", "PROPN"} and doc[j].pos_ in {"NOUN", "PROPN", "ADJ", "DET"}
        ):
            j += 1
        if doc[j].pos_ in NOMINAL:
            objects.append(j)
        k = j + 1
    return subject, objects, to_target


def _np_head(doc, position: int) -> int | None:
    k = position + 1
    while k < len(doc) and doc[k].pos_ in NP_INNER:
        if doc[k].pos_ in {"NOUN", "PROPN"} and not (k + 1 < len(doc) and doc[k + 1].pos_ in {"NOUN", "PROPN"}):
            return k
        k += 1
    return None


def solve(encoder, doc) -> dict[int, frozenset[str]]:
    """Positions whose senses the sentence narrows, with the member definitions of the senses that survive."""
    from GSE.curation.lexicon_builder.valency_absence import person_bearer_primes

    bearer_primes = person_bearer_primes()
    lemma = {i: t.lemma_.lower() for i, t in enumerate(doc)}
    senses: dict[int, dict[int, tuple[dict, tuple[str, ...]]]] = {}
    for i, token in enumerate(doc):
        if token.pos_ in CONTENT:
            found = _senses(encoder, lemma[i], CONTENT[token.pos_])
            if found:
                senses[i] = found
    values = {i: {s: core for s, (core, _members) in found.items()} for i, found in senses.items()}
    domain = {i: set(v) for i, v in values.items()}

    def someone(word):
        senses = encoder.lexical_lookup(word, "NOUN").get("word_senses") or {}
        return (senses.get("assignments") or {}).get("SOMEONE")

    def types(position) -> set[str]:
        """The slot types an argument can still take."""
        if position == "something":
            return {"something"}
        if position in domain:
            return {_type(values[position][d]) for d in domain[position]}
        return {slot_type(doc[position], someone) or "*"}

    def requires_bearer(i, entry: int) -> bool:
        return any(values[i][entry].get(b) == 1 for b in bearer_primes)

    def bearer_types(position) -> set[bool]:
        if position in domain:
            return {_bearer_ok(values[position][d]) for d in domain[position]}
        token = doc[position]
        return {True} if token.pos_ == "PRON" and slot_type(token, someone) == "somebody" else {True, False}

    clauses = {}
    for i, token in enumerate(doc):
        if token.pos_ == "VERB" and i in domain:
            clauses[i] = _arguments(doc, i)
    bearers = {}  # predicate position -> bearer position
    for i, token in enumerate(doc):
        if token.pos_ == "ADJ" and i in domain:
            head = _np_head(doc, i)
            if head is not None:
                bearers[i] = head
        elif i in clauses and clauses[i][0] is not None:
            bearers[i] = clauses[i][0]

    def verb_supported(v, entry, fixed: dict) -> bool:
        frames = _frames(senses[v][entry][1], lemma[v])
        if frames is None:
            return True
        subject, objects, to_target = clauses[v]
        slots = [subject, *objects]
        options = [({"*"} if s is None else fixed.get(s) or types(s)) for s in slots]
        to_options = (
            [False]
            if to_target is None
            else sorted({t == "somebody" for t in (fixed.get(to_target) or types(to_target))})
        )
        for combo in product(*options):
            for to_somebody in to_options:
                pattern = (combo[0], tuple(combo[1:]), to_somebody)
                if any(frame_hosts(frame, pattern) for frame in frames):
                    return True
        return False

    def bearer_supported(p, entry_or_none, b, b_entry_or_none) -> bool:
        needs = requires_bearer(p, entry_or_none) if entry_or_none is not None else None
        ok = {_bearer_ok(values[b][b_entry_or_none])} if b_entry_or_none is not None else bearer_types(b)
        if needs is None:
            return any(not requires_bearer(p, d) for d in domain[p]) or True in ok
        return not needs or True in ok

    changed = True
    while changed:
        changed = False
        for v in clauses:  # verb definitions need a hosting frame
            keep = {d for d in domain[v] if verb_supported(v, d, {})}
            if keep and keep != domain[v]:
                domain[v], changed = keep, True
        for v, (subject, objects, to_target) in clauses.items():  # argument definitions need a hosting verb sense
            for a in [s for s in (subject, *objects, to_target) if isinstance(s, int) and s in domain]:
                keep = {
                    d for d in domain[a] if any(verb_supported(v, dv, {a: {_type(values[a][d])}}) for dv in domain[v])
                }
                if keep and keep != domain[a]:
                    domain[a], changed = keep, True
        for p, b in bearers.items():  # person-typed predicates need a someone or creature bearer
            keep = {d for d in domain[p] if bearer_supported(p, d, b, None)}
            if keep and keep != domain[p]:
                domain[p], changed = keep, True
            if b in domain:
                keep = {d for d in domain[b] if bearer_supported(p, None, b, d)}
                if keep and keep != domain[b]:
                    domain[b], changed = keep, True
    return {
        i: frozenset(entry for s in d for entry in senses[i][s][1]) for i, d in domain.items() if d != set(values[i])
    }
