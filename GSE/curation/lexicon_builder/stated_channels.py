"""Stated facts for WordNet definitions, from sources linked to the exact sense (ledger confirmation input).

A value counts as stated only when a source asserts it about the definition's own sense, through that
source's declared per-unit table, never through voting, a default, or a value some rule derived from
WordNet's hierarchy (SIGNIFICANCE_WEIGHTING.md §14). A word-level source reaches a WordNet definition
only through an exact link: WordNet lists exactly one sense for the lemma in that part of speech, and the
source lists exactly one reading for it (one FrameNet lexical unit, one Wiktionary sense). USAS is excluded: its
tags are semantic fields, so its table turns a word's topic into a meaning (abhorrent -> BODY, airfare -> HAVE).
Each fact keeps its channel.

Channels:
- ``assertion``: the release's own source assertions (not ``wordnet_hierarchy``, whose values rules derive);
- ``framenet``: the single lexical unit's frame, through ``FRAME_TO_PRIMITIVE`` (frame elements name
  participants, not the word, and are not read);
- ``wordnet_gloss`` and ``wiktionary_gloss``: the definition's own text, read by GSE's reviewed frame reader
  (``native_noun_frames``) and concluded through the release's reviewed frame-guarded rules.
"""

from __future__ import annotations

import json
from collections import defaultdict

from .definition_frames import NATIVE_FRAME_PREFIX, native_noun_frames

WN_TO_UPOS = {"n": "NOUN", "v": "VERB", "a": "ADJ", "s": "ADJ", "r": "ADV"}
WN_TO_FRAMENET = {"n": "n", "v": "v", "a": "a", "s": "a", "r": "adv"}
WN_TO_LEXEME = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}


def implication(relation: dict):
    """(premise or None, conclusion) of a one-bank or two-bank implication table, else None."""
    banks, rows = relation["banks"], [tuple(r) for r in relation["allowed_rows"]]
    if len(banks) == 1:
        values = {r[0] for r in rows}
        return (None, (banks[0], next(iter(values)))) if len(values) == 1 else None
    if len(banks) != 2:
        return None
    for a in (-1, 0, 1):
        ys = {y for x, y in rows if x == a}
        others = {(x, y) for x, y in rows if x != a}
        if len(ys) == 1 and len(others) == 6:  # every other antecedent value is unconstrained
            return ((banks[0], a), (banks[1], next(iter(ys))))
    return None


def frame_rules(relations: list[dict]) -> list[tuple[str, dict, tuple]]:
    """Reviewed rules guarded by one native gloss frame, with their mechanically read implication."""
    out = []
    for relation in relations:
        frames = [k for k, _ in relation["guards"] if k.startswith(NATIVE_FRAME_PREFIX)]
        read = implication(relation)
        if len(frames) == 1 and read is not None and relation.get("approved", True):
            out.append((frames[0], relation, read))
    return out


def guards_hold(relation: dict, pos: str, synset: str, ancestors: frozenset, entry: str, frames: set) -> bool:
    """Evaluate a reviewed rule's guards on a WordNet definition; an unknown guard kind does not hold."""
    for key, value in relation["guards"]:
        if key == "pos":
            ok = value == WN_TO_LEXEME.get(pos)
        elif key == "wordnet_native_lemma":
            ok = True
        elif key.startswith(NATIVE_FRAME_PREFIX):
            ok = key in frames
        elif key.startswith("wordnet_ancestor:"):
            ok = key.split(":", 1)[1] in ancestors
        elif key.startswith("wordnet_outside_ancestor:"):
            ok = key.split(":", 1)[1] not in ancestors
        elif key.startswith("wordnet_other_than_synset:"):
            ok = key.split(":", 1)[1] != synset
        elif key.startswith("except_entry:"):
            ok = key.split(":", 1)[1] != entry
        else:
            ok = False
        if not ok:
            return False
    return True


def gloss_facts(gloss, pos, synset, ancestors, entry, rules, domains) -> list[tuple[str, int]]:
    """Facts a definition's own text states, read through the reviewed frame rules whose premise holds."""
    if pos != "n" or not isinstance(gloss, str):
        return []
    frames = {NATIVE_FRAME_PREFIX + f for f in native_noun_frames(gloss)}
    facts = []
    for frame, relation, (premise, conclusion) in rules:
        if frame not in frames or not guards_hold(relation, pos, synset, ancestors, entry, frames):
            continue
        if premise is not None and domains.get(premise[0]) != [premise[1]]:
            continue
        facts.append(conclusion)
    return facts


def collect(conn, entries, framenet_entries, frame_table, in_scope, wn) -> dict:
    """entry -> [(bank, value, channel)] over every exact channel (see module docstring)."""
    stated = defaultdict(list)
    for entry, payload in conn.execute(
        "SELECT entry_id, payload FROM builder_assertions WHERE entry_id LIKE 'wordnet:%'"
    ):
        record = json.loads(payload)
        if record["source"] != "wordnet_hierarchy":
            stated[entry].append((record["bank"], record["value"], "assertion"))
    relations = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
    rules = frame_rules(relations)
    wiktionary = defaultdict(list)
    for lemma, pos, gloss, entry in conn.execute(
        "SELECT l.lemma, l.pos, l.gloss, d.entry_id FROM definition_states d JOIN lexemes l ON d.lexeme_id=l.id"
        " WHERE d.entry_id LIKE 'wiktionary:%'"
    ):
        wiktionary[(lemma.lower(), pos)].append((entry, gloss))
    wikt_assertions = defaultdict(list)
    for entry, payload in conn.execute(
        "SELECT entry_id, payload FROM builder_assertions WHERE entry_id LIKE 'wiktionary:%'"
    ):
        record = json.loads(payload)
        wikt_assertions[entry].append((record["bank"], record["value"]))
    rows = conn.execute(
        "SELECT d.entry_id, l.gloss, d.domains FROM definition_states d JOIN lexemes l ON d.lexeme_id=l.id"
        " WHERE d.entry_id LIKE 'wordnet:%'"
    )
    for entry, gloss, raw in rows:
        if entry not in entries:
            continue
        synset, ancestors, lemma = entries[entry]
        pos = synset.split(".")[-2]
        domains = json.loads(raw)
        for bank, value in gloss_facts(gloss, pos, synset, ancestors, entry, rules, domains):
            stated[entry].append((bank, value, "wordnet_gloss"))
        if len(wn.synsets(lemma, pos="a" if pos == "s" else pos)) != 1:
            continue  # the word-level channels below need an exact sense link
        units = [u for u in framenet_entries.get(lemma.lower(), []) if u.pos == WN_TO_FRAMENET[pos]]
        if len(units) == 1:
            for bank, value in frame_table.get(units[0].frame_name, {}).items():
                if in_scope("framenet", bank):
                    stated[entry].append((bank, value, "framenet"))
        senses = wiktionary.get((lemma.lower(), WN_TO_LEXEME[pos]), [])
        if len(senses) == 1:
            w_entry, w_gloss = senses[0]
            for bank, value in wikt_assertions.get(w_entry, []):
                stated[entry].append((bank, value, "wiktionary"))
            for bank, value in gloss_facts(w_gloss, pos, synset, ancestors, entry, rules, domains):
                stated[entry].append((bank, value, "wiktionary_gloss"))
    return stated
