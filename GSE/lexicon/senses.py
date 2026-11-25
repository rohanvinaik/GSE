"""Read a word's senses: the founder-corrected lexicon's runtime side (lexicon FC-6).

A word's definitions collapse into a few senses per part of speech
(``GSE.curation.lexicon_builder.word_senses``). At read time the sentence's part of speech
selects that part of speech's senses, and the reading is the main sense: the coherent core of the
word's whole set of definitions, its "real and obvious meaning" (Rohan). A sense that breaks that
coherence is "an out-of-variance exception that breaks coherence and should be handled thus"
(Rohan, 2026-11-24): it is carried under ``exceptions``, with the banks where it differs from the
core and the possible signs there, and never erases the core. When context has identified one
exact definition, the reading is that definition's sense. A word is never refused for having
several definitions.

Reading only what every sense shares erased the obvious meaning: one minority sense of "give"
(THINK+, "give thought to") cancelled its DO+. Nothing in a sentence that fixes only the part of
speech has selected a minority sense.

Only a lexicon that carries a ``word_senses`` table is read this way; otherwise ``read_senses``
returns None and the caller keeps its definition-identity behavior.
"""

from __future__ import annotations

import json
import sqlite3

POLICY = "word-senses/1"
# The front end's tags for content words; proper nouns are handled by the name system.
UD_TO_POS = {"NOUN": "noun", "VERB": "verb", "AUX": "verb", "ADJ": "adj", "ADV": "adv"}
_ORDER = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}


def has_senses(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='word_senses'").fetchone() is not None


def _differences(core: dict, alternatives: list[dict]) -> dict[str, list[int]]:
    """Banks where another sense fixes a different value than the core: their possible signs."""
    differing: dict[str, set[int]] = {}
    for sense in alternatives:
        for bank, value in sense["assignments"].items():
            if core["assignments"].get(bank) != value:
                base = {core["assignments"][bank]} if bank in core["assignments"] else set(core["open"].get(bank, ()))
                differing.setdefault(bank, set(base)).add(value)
    return {bank: sorted(values) for bank, values in sorted(differing.items())}


def read_senses(
    conn: sqlite3.Connection, lemma: str, pos: str | None = None, entry_id: str | None = None
) -> dict | None:
    """The word's reading from its senses, or None when the lexicon has no senses for it."""
    if not has_senses(conn):
        return None
    rows = conn.execute(
        "SELECT pos, sense, assignments, open, members, absorbed FROM word_senses WHERE lemma = ? ORDER BY pos, sense",
        (lemma,),
    ).fetchall()
    if not rows:
        return None
    by_pos: dict[str, list[dict]] = {}
    for row_pos, sense, assignments, open_, members, absorbed in rows:
        by_pos.setdefault(row_pos, []).append(
            {
                "sense": sense,
                "assignments": json.loads(assignments),
                "open": json.loads(open_),
                "members": json.loads(members),
                "absorbed": json.loads(absorbed),
            }
        )
    if entry_id is not None:
        chosen = [
            (p, s)
            for p, senses in by_pos.items()
            for s in senses
            if entry_id in s["members"] or entry_id in s["absorbed"]
        ]
        if not chosen:
            return None
        selected_pos, sense = chosen[0]
        core, basis = sense, "IDENTIFIED_DEFINITION"
    else:
        wanted = UD_TO_POS.get(pos or "", pos)
        if wanted in by_pos:
            selected_pos, basis = wanted, "PART_OF_SPEECH"
        else:
            selected_pos = sorted(
                by_pos,
                key=lambda p: (-sum(len(s["members"]) + len(s["absorbed"]) for s in by_pos[p]), _ORDER.get(p, 9), p),
            )[0]
            basis = "DOMINANT_PART_OF_SPEECH"
        core = by_pos[selected_pos][0]  # the main sense
    alternatives = [s for s in by_pos[selected_pos] if s is not core]
    return {
        "policy": POLICY,
        "pos": selected_pos,
        "basis": basis,
        "sense": core["sense"],
        "assignments": dict(core["assignments"]),
        "open": dict(core["open"]),
        "exceptions": [{"sense": s["sense"], "assignments": s["assignments"]} for s in alternatives],
        "differs": _differences(core, alternatives),
    }
