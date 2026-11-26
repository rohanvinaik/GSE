"""Read a word's senses: the founder-corrected lexicon's runtime side (lexicon FC-6).

A word's definitions collapse, by coherence over the whole set, into its genuinely distinct senses, one coherent
core per homonym and none ranked above another (``GSE.curation.lexicon_builder.word_senses``). Grammar and context
choose among senses; the lexicon does not (Rohan, 2026-11-25). The reading for a part of speech is every sense of
that part of speech: banks they all agree on are its values, and where they disagree it carries the set of possible
signs. When context has identified one exact definition, the reading is that definition's sense. A word is never
refused for having several definitions.

Only a lexicon that carries a ``word_senses`` table is read this way; otherwise ``read_senses``
returns None and the caller keeps its definition-identity behavior.
"""

from __future__ import annotations

import json
import sqlite3

POLICY = "word-senses/2"
# The front end's tags for content words; proper nouns are handled by the name system.
UD_TO_POS = {"NOUN": "noun", "VERB": "verb", "AUX": "verb", "ADJ": "adj", "ADV": "adv"}
_ORDER = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}


def has_senses(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='word_senses'").fetchone() is not None


def _possible(sense: dict, bank: str) -> set[int]:
    """The signs a sense allows on a bank: its value, its open domain, or every sign when it says nothing."""
    if bank in sense["assignments"]:
        return {sense["assignments"][bank]}
    return set(sense["open"].get(bank, (-1, 0, 1)))


def _agreement(senses: list[dict]) -> tuple[dict[str, int], dict[str, list[int]]]:
    """Values every sense shares, and the possible signs where they do not (banks no sense speaks to stay out)."""
    banks = {bank for sense in senses for bank in (*sense["assignments"], *sense["open"])}
    agreed, possible = {}, {}
    for bank in sorted(banks):
        signs = set().union(*(_possible(sense, bank) for sense in senses))
        if len(signs) == 1:
            agreed[bank] = next(iter(signs))
        elif signs != {-1, 0, 1} or any(bank in s["assignments"] for s in senses):
            possible[bank] = sorted(signs)
    return agreed, possible


def reading(senses: list[dict]) -> tuple[dict[str, int], dict[str, list[int]], list[dict]]:
    """Agreed values, possible signs, and out-of-variance exceptions for one part of speech's senses.

    Rohan (2026-11-25): "If a single input completely destroys the coherence model, then that's an
    out-of-variance exception that breaks coherence and should be handled thus." A sense of a single
    definition is an exception when it breaks a value every multi-definition sense agrees on: it rules that value
    out. A sense that only leaves the bank open does not break it (the animal dog.n.01, silent on SOMEONE, is not an
    exception to the people senses of "dog"). Exceptions are recorded and kept out of the reading. When every sense
    is a single definition, none is an exception.
    """
    base = [s for s in senses if len(s.get("members", ())) >= 2]
    if not base:
        return (*_agreement(senses), [])
    base_agreed, _ = _agreement(base)
    exceptions = [
        s
        for s in senses
        if len(s.get("members", ())) < 2 and any(value not in _possible(s, bank) for bank, value in base_agreed.items())
    ]
    kept = [s for s in senses if s not in exceptions]
    return (*_agreement(kept), exceptions)


def read_senses(
    conn: sqlite3.Connection,
    lemma: str,
    pos: str | None = None,
    entry_id: str | None = None,
    allowed: frozenset | None = None,
) -> dict | None:
    """``allowed``: the definitions the sentence's grammar leaves possible; senses with none of them drop out."""
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
    if entry_id is not None:
        return {
            "policy": POLICY,
            "pos": selected_pos,
            "basis": basis,
            "sense": core["sense"],
            "assignments": dict(core["assignments"]),
            "open": dict(core["open"]),
            "senses": [{"sense": core["sense"], "assignments": core["assignments"]}],
        }
    senses = by_pos[selected_pos]
    if allowed is not None:
        # A sense is judged on the definitions the sentence left it (exceptions included, below).
        kept = [
            {**s, "members": [m for m in s["members"] if m in allowed]} for s in senses if set(s["members"]) & allowed
        ]
        senses = kept or senses
        basis = basis + "+FRAME_SELECTED" if kept else basis
    agreed, possible, exceptions = reading(senses)
    return {
        "policy": POLICY,
        "pos": selected_pos,
        "basis": basis,
        "sense": None,
        "assignments": agreed,
        "open": possible,
        "senses": [{"sense": s["sense"], "assignments": s["assignments"]} for s in senses if s not in exceptions],
        "exceptions": [{"sense": s["sense"], "assignments": s["assignments"]} for s in exceptions],
    }
