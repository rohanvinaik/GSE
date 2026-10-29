"""Store explicit values and unresolved domains without a closed-world default.

The ordinary lexemes/primitive_values tables remain the runtime projection.
Construction evidence, definition IDs, domains, and hierarchy have their own
versioned records. A conflicted entry has no published primitive projection.
"""

import json
import sqlite3
from dataclasses import asdict, fields
from pathlib import Path

from gse.curation.schema import SCHEMA

VERSION = "gse.lexicon-builder/1"
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS builder_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS definition_states (
 entry_id TEXT PRIMARY KEY, lexeme_id INTEGER UNIQUE NOT NULL,
 code TEXT NOT NULL, domains TEXT NOT NULL, conflicts TEXT NOT NULL,
 trace TEXT NOT NULL, hierarchy TEXT NOT NULL,
 FOREIGN KEY(lexeme_id) REFERENCES lexemes(id));
CREATE TABLE IF NOT EXISTS source_observations (
 record_id TEXT PRIMARY KEY, entry_id TEXT, source TEXT NOT NULL,
 family TEXT NOT NULL, scope TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS builder_assertions (
 entry_id TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(entry_id,ordinal));
CREATE TABLE IF NOT EXISTS unresolved_sources (
 ordinal INTEGER PRIMARY KEY, code TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_unresolved_sources_code ON unresolved_sources(code);
CREATE INDEX IF NOT EXISTS idx_source_observations_entry ON source_observations(entry_id);
CREATE TABLE IF NOT EXISTS candidate_relations (
 rule_id TEXT PRIMARY KEY, summary TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candidate_evidence (
 rule_id TEXT NOT NULL, category TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(rule_id,category,ordinal));
CREATE TABLE IF NOT EXISTS sentence_primitive_values (
 lexeme_id INTEGER NOT NULL, primitive TEXT NOT NULL, value INTEGER NOT NULL,
 UNIQUE(lexeme_id,primitive));
"""


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def open_build(path: str | Path) -> sqlite3.Connection:
    """Refuse legacy databases; never relabel old default zeros as evidence."""
    conn = sqlite3.connect(path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "lexemes" in tables and "builder_metadata" not in tables:
            raise ValueError("LEGACY_DATABASE_REQUIRES_NEW_BUILD_PATH")
        if "builder_metadata" in tables:
            row = conn.execute("SELECT value FROM builder_metadata WHERE key='format'").fetchone()
            if row is None or json.loads(row[0]) != VERSION:
                raise ValueError("UNSUPPORTED_BUILD_FORMAT")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA + EXTRA_SCHEMA)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(lexemes)")}
        for name, declaration in (
            ("comp_primitive", "TEXT"),
            ("comp_arity", "INTEGER DEFAULT 0"),
            ("comp_operation", "TEXT"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE lexemes ADD COLUMN {name} {declaration}")
        conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES ('format',?)", (_json(VERSION),))
        conn.commit()
        return conn
    except BaseException:
        conn.close()
        raise


def store_entry(conn, definition, resolution, assertions=(), hierarchy=None) -> None:
    """Replace one explicitly identified definition's complete build receipt."""
    hierarchy = hierarchy or {}
    if resolution.code == "CONFLICT":
        hierarchy = {}
    if any(bank not in resolution.assignments or resolution.assignments[bank] == 0 for bank in hierarchy):
        raise ValueError("HIERARCHY_REQUIRES_NONZERO_BASE")
    status = {"CONFLICT": "rejected", "PARTIAL": "partial", "RESOLVED": "validated"}[resolution.code]
    conn.execute(
        """INSERT INTO lexemes(lemma,pos,sense_id,gloss,source,validation_status)
                    VALUES (?,?,?,?,?,?) ON CONFLICT(lemma,pos,sense_id)
                    DO UPDATE SET gloss=excluded.gloss,validation_status=excluded.validation_status""",
        (definition.lemma, definition.pos, definition.entry_id, definition.definition, VERSION, status),
    )
    lexeme_id = conn.execute(
        "SELECT id FROM lexemes WHERE lemma=? AND pos=? AND sense_id=?",
        (definition.lemma, definition.pos, definition.entry_id),
    ).fetchone()[0]
    conn.execute("DELETE FROM primitive_values WHERE lexeme_id=?", (lexeme_id,))
    if resolution.code != "CONFLICT":
        conn.executemany(
            "INSERT INTO primitive_values(lexeme_id,primitive,value,source) VALUES (?,?,?,?)",
            [(lexeme_id, bank, value, VERSION) for bank, value in sorted(resolution.assignments.items())],
        )
    conn.execute(
        "INSERT OR REPLACE INTO definition_states VALUES (?,?,?,?,?,?,?)",
        (
            definition.entry_id,
            lexeme_id,
            resolution.code,
            _json({b: sorted(v) for b, v in resolution.domains.items()}),
            _json(resolution.conflicts),
            _json(resolution.trace),
            _json(hierarchy),
        ),
    )
    conn.execute("DELETE FROM builder_assertions WHERE entry_id=?", (definition.entry_id,))
    conn.executemany(
        "INSERT INTO builder_assertions VALUES (?,?,?)",
        [(definition.entry_id, i, _json(asdict(a))) for i, a in enumerate(assertions)],
    )


def store_observations(conn, observations) -> None:
    """Keep native records even when their dictionary linkage is unresolved."""
    for observation in observations:
        payload = _json(asdict(observation))
        previous = conn.execute(
            "SELECT payload FROM source_observations WHERE record_id=?", (observation.record_id,)
        ).fetchone()
        if previous is not None and previous[0] != payload:
            raise ValueError("SOURCE_RECORD_ID_COLLISION")
        conn.execute(
            "INSERT OR IGNORE INTO source_observations VALUES (?,?,?,?,?,?)",
            (
                observation.record_id,
                observation.entry_id,
                observation.source,
                observation.family,
                observation.scope,
                payload,
            ),
        )


def store_unresolved(conn, records) -> dict:
    """Store corpus diagnostics as rows, never one corpus-sized JSON value."""
    from collections import Counter

    counts = Counter()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("code"), str):
            raise ValueError("INVALID_SOURCE_DIAGNOSTIC")
        counts[record["code"]] += 1
        conn.execute("INSERT INTO unresolved_sources VALUES (?,?,?)", (index, record["code"], _json(record)))
    return {"table": "unresolved_sources", "records": sum(counts.values()), "outcomes": dict(counts)}


def store_candidates(conn, candidates) -> dict:
    """Keep each candidate's individual evidence separate from its summary."""
    count = 0
    categories = ("support", "counterexamples", "unknown", "conflicting", "ineligible")
    for candidate in candidates:
        record = {
            field.name: getattr(candidate, field.name) for field in fields(candidate) if field.name not in categories
        }
        record["relation"] = asdict(candidate.relation)
        rule_id = candidate.relation.rule_id
        record["evidence_counts"] = {key: len(getattr(candidate, key)) for key in categories}
        conn.execute("INSERT INTO candidate_relations VALUES (?,?)", (rule_id, _json(record)))
        for key in categories:
            conn.executemany(
                "INSERT INTO candidate_evidence VALUES (?,?,?,?)",
                ((rule_id, key, index, _json(receipt)) for index, receipt in enumerate(getattr(candidate, key))),
            )
        count += 1
    return {"table": "candidate_relations", "evidence_table": "candidate_evidence", "records": count}


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
