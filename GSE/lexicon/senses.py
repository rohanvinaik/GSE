"""Read a word's senses: the founder-corrected lexicon's runtime side (lexicon FC-6).

A word's definitions collapse into a few senses per part of speech
(``GSE.curation.lexicon_builder.word_senses``). At read time the sentence's part of speech
selects that part of speech's senses. The reading is what every surviving sense shares; where
they differ, the bank carries its possible signs; where any sense leaves it unconstrained, it
stays unknown. A word is never refused for having several definitions. When context has already
identified one exact definition, the reading is that definition's sense.

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


def _consequence(senses: list[dict]) -> tuple[dict[str, int], dict[str, list[int]]]:
    """What every surviving sense fixes, and the possible signs where they differ."""
    banks = set().union(*(set(s["assignments"]) | set(s["open"]) for s in senses))
    shared: dict[str, int] = {}
    open_: dict[str, list[int]] = {}
    for bank in sorted(banks):
        possible = []
        for sense in senses:
            if bank in sense["assignments"]:
                possible.append({sense["assignments"][bank]})
            elif bank in sense["open"]:
                possible.append(set(sense["open"][bank]))
            else:
                break  # one sense leaves it unconstrained: unknown
        else:
            union = set().union(*possible)
            if len(union) == 1:
                shared[bank] = next(iter(union))
            else:
                open_[bank] = sorted(union)
    return shared, open_


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
        chosen_pos, sense = chosen[0]
        selected, selected_pos, basis = [sense], chosen_pos, "IDENTIFIED_DEFINITION"
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
        selected = by_pos[selected_pos]
    shared, open_ = _consequence(selected)
    return {
        "policy": POLICY,
        "pos": selected_pos,
        "basis": basis,
        "senses": [{"sense": s["sense"], "definitions": len(s["members"]) + len(s["absorbed"])} for s in selected],
        "assignments": shared,
        "open": open_,
    }
