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
SUBJECT = frozenset({"nsubj"})
OBJECTS = frozenset({"dobj", "obj", "iobj", "dative"})


def slot_type(token, someone) -> str | None:
    """'somebody', 'something', or None when the source says nothing decisive about the argument."""
    if token.pos_ == "PRON":
        return "somebody" if token.lemma_.lower() in PERSONAL else "something"
    if token.pos_ in {"NOUN", "PROPN"}:
        value = someone(token.lemma_.lower())
        return "somebody" if value == 1 else "something" if value == 0 else None
    return None


def clause_pattern(doc, position, someone) -> tuple | None:
    """(subject, objects in order, has 'to' + somebody) for the verb at ``position``; None if any slot is untyped."""
    verb = doc[position]
    subject, objects, to_somebody = None, [], False
    for child in verb.children:
        if child.dep_ in SUBJECT:
            subject = slot_type(child, someone)
            if subject is None:
                return None
        elif child.dep_ in OBJECTS:
            kind = slot_type(child, someone)
            if kind is None:
                return None
            objects.append((child.i, kind))
        elif child.dep_ == "prep" and child.lemma_.lower() == "to":
            for grand in child.children:
                if slot_type(grand, someone) == "somebody":
                    to_somebody = True
    return subject, tuple(kind for _position, kind in sorted(objects)), to_somebody


def frame_hosts(frame: str, pattern: tuple) -> bool:
    """Whether one WordNet frame string ("Somebody ----s somebody something") hosts the clause pattern."""
    subject, objects, to_somebody = pattern
    words = frame.lower().split()
    if "v" not in words:
        return False
    head = words.index("v")
    before, after = words[:head], words[head + 1 :]
    if subject is not None and before and before[0] not in {subject, subject + "s"}:
        return False
    slots = [w for w in after if w in {"somebody", "something"}]
    wants_to = "to" in after
    if to_somebody and not wants_to:
        return False
    framed = tuple(slots[:-1]) if wants_to and slots and slots[-1] == "somebody" else tuple(slots)
    return framed == objects


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
