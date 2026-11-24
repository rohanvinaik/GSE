"""Read the versioned definition database: its format, its definitions, and one by identity.

The runtime reads lexical definitions through this module; the lexicon builder
writes them (``GSE.curation.lexicon_builder.storage``) and re-exports these names.
Selection is by identity: an ambiguous or conflicted spelling is reported, never
resolved by insertion order or by nearest vector.
"""

import json
import sqlite3

VERSION = "GSE.lexicon-builder/1"


def read_entries(conn, lemma: str | None = None, entry_id: str | None = None) -> list[dict]:
    """Return all matching definitions, never pick one by insertion order."""
    conn.row_factory = sqlite3.Row
    query = "SELECT l.*, d.entry_id,d.code,d.domains,d.conflicts,d.trace,d.hierarchy FROM lexemes l JOIN definition_states d ON l.id=d.lexeme_id"
    conditions, values = [], []
    if lemma is not None:
        conditions.append("l.lemma=?")
        values.append(lemma)
    if entry_id is not None:
        conditions.append("d.entry_id=?")
        values.append(entry_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    result = []
    for row in conn.execute(query + " ORDER BY d.entry_id", values).fetchall():
        record = dict(row)
        for key in ("domains", "conflicts", "trace", "hierarchy"):
            record[key] = json.loads(record[key])
        record["assignments"] = dict(
            conn.execute(
                "SELECT primitive,value FROM primitive_values WHERE lexeme_id=? ORDER BY primitive", (record["id"],)
            ).fetchall()
        )
        result.append(record)
    return result


def runtime_lookup(conn, lemma: str, entry_id: str | None = None) -> dict:
    """A definition selector is identity, never a nearest-vector decision."""
    entries = read_entries(conn, lemma, entry_id)
    if not entries:
        return {"code": "NOT_FOUND", "candidates": [], "selected": None}
    if len(entries) != 1:
        return {"code": "AMBIGUOUS", "candidates": [e["entry_id"] for e in entries], "selected": None}
    entry = entries[0]
    if entry["code"] == "CONFLICT":
        return {"code": "CONFLICT", "candidates": [entry["entry_id"]], "selected": None}
    return {"code": "IDENTIFIED", "candidates": [entry["entry_id"]], "selected": entry}
