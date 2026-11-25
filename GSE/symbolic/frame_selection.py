"""Sentence-side sense selection by WordNet's own per-sense sentence frames (Rohan, 2026-11-25).

Grammar is a constraint harness: a verb sense survives only if one of its source frames can host the clause's
argument pattern ("Somebody ----s somebody something" hosts "She gave the boy a lock"; "Something ----s something"
does not). Elimination only: a definition without frame information (not a WordNet verb sense) is never removed, a
pattern the parser cannot type keeps every sense, and no survivor is ranked above another. The surviving senses'
agreement is the reading (``GSE.lexicon.senses.read_senses(..., allowed=...)``).
"""

from __future__ import annotations

from urllib.parse import unquote

PERSONAL = frozenset({"i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them", "who", "whom"})


def slot_type(token, someone) -> str | None:
    """'somebody', 'something', or None when the source says nothing decisive about the argument."""
    if token.pos_ == "PRON":
        return "somebody" if token.lemma_.lower() in PERSONAL else "something"
    if token.pos_ in {"NOUN", "PROPN"}:
        value = someone(token.lemma_.lower())
        return "somebody" if value == 1 else "something" if value == 0 else None
    return None


NOMINAL = frozenset({"NOUN", "PROPN", "PRON"})
NP_INNER = frozenset({"DET", "ADJ", "NUM", "PRON", "NOUN", "PROPN", "ADV"})


def clause_pattern(doc, position, someone) -> tuple | None:
    """(subject, objects in order, 'to' + somebody) for the verb at ``position``, read from GSE's linear grammar
    (the native front end builds no arcs): the subject is the nearest nominal before the verb, the objects are the
    noun-phrase heads after it up to the clause boundary. An argument whose type the lexicon does not settle is "*":
    it matches either slot, so frames are still eliminated by arity and by the typed slots."""
    subject = None
    for k in range(position - 1, -1, -1):
        token = doc[k]
        if token.pos_ in NOMINAL:
            subject = slot_type(token, someone) or "*"
            break
        if token.pos_ not in NP_INNER and token.pos_ != "AUX":
            break
    objects, to_somebody, k = [], False, position + 1
    while k < len(doc):
        token = doc[k]
        if token.pos_ == "ADP" and token.lemma_.lower() == "to":
            j = k + 1
            while j < len(doc) and doc[j].pos_ in NP_INNER and doc[j].pos_ not in NOMINAL:
                j += 1
            if j < len(doc) and doc[j].pos_ in NOMINAL and slot_type(doc[j], someone) == "somebody":
                to_somebody = True
            k = j + 1
            continue
        if token.pos_ not in NP_INNER:
            break
        j = k
        while (
            j + 1 < len(doc) and doc[j + 1].pos_ in {"NOUN", "PROPN"} and doc[j].pos_ in {"NOUN", "PROPN", "ADJ", "DET"}
        ):
            j += 1
        head = doc[j]
        if head.pos_ in NOMINAL:
            objects.append(slot_type(head, someone) or "*")
        k = j + 1
    return subject, tuple(objects), to_somebody


def frame_hosts(frame: str, pattern: tuple) -> bool:
    """Whether one WordNet frame string ("Somebody ----s somebody something") hosts the clause pattern."""
    subject, objects, to_somebody = pattern
    words = frame.lower().split()
    if "v" not in words:
        return False
    head = words.index("v")
    before, after = words[:head], words[head + 1 :]
    if subject not in (None, "*") and before and before[0] not in {subject, subject + "s"}:
        return False
    slots = [w for w in after if w in {"somebody", "something"}]
    wants_to = "to" in after
    if to_somebody and not wants_to:
        return False
    framed = tuple(slots[:-1]) if wants_to and slots and slots[-1] == "somebody" else tuple(slots)
    return len(framed) == len(objects) and all(o in ("*", f) for f, o in zip(framed, objects, strict=True))


def surviving(lemma: str, candidate_ids, pattern: tuple | None) -> set:
    """Candidate definitions the clause allows: WordNet verb senses with a hosting frame, plus every candidate
    WordNet gives no frames for. With an untyped pattern every candidate survives."""
    from nltk.corpus import wordnet as wn

    ids = set(candidate_ids)
    if pattern is None:
        return ids
    kept = set()
    for entry_id in ids:
        if not entry_id.startswith("wordnet:"):
            kept.add(entry_id)
            continue
        synset = wn.synset(unquote(entry_id.rsplit(":", 1)[-1]))
        if synset is None:
            kept.add(entry_id)
            continue
        lemmas = [name for name in synset.lemmas() if name.name().lower() == lemma.lower()]
        if synset.pos() != "v" or not lemmas:
            kept.add(entry_id)
            continue
        frames = [f.replace(lemmas[0].name(), "V") for f in lemmas[0].frame_strings()]
        if any(frame_hosts(frame, pattern) for frame in frames):
            kept.add(entry_id)
    return kept or ids
