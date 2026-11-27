"""The runtime artifact: the rebuilt lexicon in the form GSE reads (design E11, rebuild task 10.1).

The runtime reads a definition database through `GSE.lexicon.definitions`, `GSE.lexicon.senses`,
`GSE.lexical_evidence`, `GSE.symbolic.lexical_grounding` and `GSE.api.encoder`. `GSE.lexicon_resource` accepts it
when `builder_metadata.format` is `GSE.lexicon.definitions.VERSION`. This module writes exactly those tables:

- `lexemes`: one row per reading. `sense_id` is the reading id, `gloss` is the cohort's text and `source` is the
  format. The `comp_*` columns are read by the encoder.
The published values are the interpolated layer's decided cells, which include every known one (the lead's ruling A,
2026-11-27: the lexicon is filled by rule-warranted propagation, and interpolated content is legitimate when it is
labelled and never passed off as known). Each cell keeps its standing, known or interpolated, and its warrant, and
the known layer stays recoverable (`values` and `masks` take `layer="known"`).

- `definition_states`: per reading, its `code`, its `domains` and more fields, all of the published layer.
  - `code` is `RESOLVED` when every bank is decided, `CONFLICT` when one is empty, and `PARTIAL` otherwise.
  - `domains` maps each bank to its signs. The runtime knows only the signs -1, 0 and +1: a decided cell has one
    sign, a cell proved silent has none (F118: "0 is explicit absence; empty is silence"), and a residual has the
    signs it still allows.
  - `masks` keeps every cell's four-state mask, so the artifact is lossless. It is a hex digit per bank in
    `builder_metadata.banks` order, and it is the only place a residual's SILENT survives. `known_masks` is the
    known layer in the same form.
  - `trace` gives each narrowed cell's standing, warrant class and rule.
  - `hierarchy` gives a degree level on a bank (`{"INTENSITY": 2}`), allowed only on a bank decided nonzero.
- `primitive_values`: every decided sign, zero included (none for a conflicted reading), with its `standing`. SILENT
  is not a sign, so it has no row.
- `cell_warrants`: every narrowed cell's warrant in each layer (class and rule), so both layers' provenance is kept.
- `source_observations`: the native records the runtime re-validates (`native_records`).
- `word_senses`: E10's sense records (`senses.py`). The table always exists, because `clause_selection` and
  `declarative` read it without a guard. `sense` numbers a word's senses by their least member (no main sense).
  `members` are the definitions with evidence of their own; `absorbed` are those that joined the core without any.
  `assignments` and `open` come from the published (interpolated) encoding, and `provenance.standing` names each
  decided bank's standing. A bank whose mask still allows SILENT is left out of
  `open`: the runtime has no silence, and its signs alone would read as a constraint the definition may not state.
  `provenance` keeps both layers' four-state encodings, the kind (sense or exception), the load-bearing banks and
  the splits. `blocked` keeps the conflicts.
- `sense_residuals`: definitions that could join more than one sense, with the senses each could join. None is
  placed by choice.
- `sentence_primitive_values`, `builder_metadata`.

An artifact is written once, to a new file. The active pointer (`data/lexicon_active.json`) is never touched: the
switch is task 12.1.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from GSE.lexicon.definitions import VERSION

from .cells import BANKS, NEG, POS, SILENT, START, ZERO

FORMAT = VERSION
_SIGN = ((NEG, -1), (ZERO, 0), (POS, 1))
_STATE_NAMES = ((POS, "+1"), (NEG, "-1"), (ZERO, "0"), (SILENT, "SILENT"))
_CODE_STATUS = {"RESOLVED": "validated", "PARTIAL": "partial", "CONFLICT": "rejected"}

TABLES = """
CREATE TABLE builder_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE lexemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    sense_id TEXT DEFAULT '01',
    gloss TEXT,
    source TEXT DEFAULT 'llm',
    confidence REAL DEFAULT 1.0,
    frequency_rank INTEGER,
    frequency_weight REAL,
    phase INTEGER DEFAULT 0,
    validation_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comp_primitive TEXT,
    comp_arity INTEGER DEFAULT 0,
    comp_operation TEXT,
    UNIQUE(lemma, pos, sense_id)
);
CREATE INDEX idx_lexemes_lemma ON lexemes(lemma);
CREATE TABLE primitive_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    primitive TEXT NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'inferred',
    standing TEXT NOT NULL DEFAULT 'known',
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
    UNIQUE(lexeme_id, primitive)
);
CREATE TABLE definition_states (
    entry_id TEXT PRIMARY KEY, lexeme_id INTEGER UNIQUE NOT NULL,
    code TEXT NOT NULL, domains TEXT NOT NULL, conflicts TEXT NOT NULL,
    trace TEXT NOT NULL, hierarchy TEXT NOT NULL, masks TEXT NOT NULL, known_masks TEXT NOT NULL,
    FOREIGN KEY(lexeme_id) REFERENCES lexemes(id));
CREATE TABLE cell_warrants (
    entry_id TEXT NOT NULL, bank TEXT NOT NULL, layer TEXT NOT NULL, class TEXT NOT NULL, rule TEXT,
    PRIMARY KEY(entry_id, bank, layer));
CREATE TABLE sentence_primitive_values (
    lexeme_id INTEGER NOT NULL, primitive TEXT NOT NULL, value INTEGER NOT NULL,
    UNIQUE(lexeme_id, primitive));
CREATE TABLE source_observations (
    record_id TEXT PRIMARY KEY, entry_id TEXT, source TEXT NOT NULL,
    family TEXT NOT NULL, scope TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX idx_source_observations_entry ON source_observations(entry_id);
CREATE TABLE sense_residuals (
    lemma TEXT NOT NULL, pos TEXT NOT NULL, entry_id TEXT NOT NULL, payload TEXT NOT NULL,
    PRIMARY KEY (lemma, pos, entry_id));
CREATE TABLE word_senses (
    lemma TEXT NOT NULL, pos TEXT NOT NULL, sense INTEGER NOT NULL, code TEXT NOT NULL, core TEXT NOT NULL,
    members TEXT NOT NULL, absorbed TEXT NOT NULL, assignments TEXT NOT NULL, open TEXT NOT NULL,
    provenance TEXT NOT NULL, blocked TEXT NOT NULL,
    PRIMARY KEY (lemma, pos, sense));
"""


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True, eq=False)
class Entry:
    """One reading as stored: its identity, its published masks over `cells.BANKS` (the interpolated layer), its
    known-layer masks (None when they are the same), and each layer's warrant per narrowed cell
    ({(layer, bank): (class, rule)}, layer "known" or "interpolated")."""

    entry_id: str
    lemma: str
    pos: str
    gloss: str
    masks: np.ndarray
    warrants: dict = field(default_factory=dict)
    hierarchy: dict = field(default_factory=dict)
    known_masks: np.ndarray | None = None

    @property
    def known(self) -> np.ndarray:
        return self.masks if self.known_masks is None else self.known_masks

    def standing(self, col: int) -> str:
        return "known" if int(self.known[col]) == int(self.masks[col]) else "interpolated"


def signs(mask: int) -> list[int]:
    """The runtime's signs a cell still allows; SILENT is not a sign."""
    return [sign for state, sign in _SIGN if mask & state]


def state_names(mask: int) -> list[str]:
    return [name for state, name in _STATE_NAMES if mask & state]


def domains(masks: np.ndarray) -> dict[str, list[int]]:
    return {bank: signs(int(m)) for bank, m in zip(BANKS, masks)}


def assignments(masks: np.ndarray) -> dict[str, int]:
    """Every decided sign: a cell holding exactly one of +1, -1 or 0."""
    return {bank: signs(int(m))[0] for bank, m in zip(BANKS, masks) if int(m) in (POS, NEG, ZERO)}


def code(masks: np.ndarray) -> str:
    counts = np.array([bin(int(m)).count("1") for m in masks])
    return "CONFLICT" if (counts == 0).any() else "RESOLVED" if (counts == 1).all() else "PARTIAL"


def hex_masks(masks: np.ndarray) -> str:
    return "".join(f"{int(m):x}" for m in masks)


def create(path: Path) -> sqlite3.Connection:
    """A new, empty artifact. An existing file is never overwritten."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"ARTIFACT_EXISTS {path}")
    conn = sqlite3.connect(path)
    conn.executescript(TABLES)
    metadata = {
        "format": FORMAT,
        "banks": list(BANKS),
        "states": [name for _, name in _STATE_NAMES],
        "masks_encoding": "one hex digit per bank in `banks` order; bits +1=1, -1=2, 0=4, SILENT=8",
    }
    conn.executemany("INSERT INTO builder_metadata VALUES (?,?)", [(k, _json(v)) for k, v in metadata.items()])
    return conn


def write_entries(conn: sqlite3.Connection, entries: Iterable[Entry]) -> int:
    """Lexemes, definition states and primitive values. Lexeme ids follow the order written, after any already in the
    artifact."""
    lexemes, states, values, warrants = [], [], [], []
    first = conn.execute("SELECT COALESCE(MAX(id), 0) FROM lexemes").fetchone()[0] + 1
    for i, e in enumerate(entries, start=first):
        c = code(e.masks)
        lexemes.append((i, e.lemma, e.pos, e.entry_id, e.gloss, FORMAT, _CODE_STATUS[c]))
        conflicts = [bank for bank, m in zip(BANKS, e.masks) if int(m) == 0]
        trace = []
        for col, bank in enumerate(BANKS):
            standing = e.standing(col)
            found = e.warrants.get((standing, bank)) or e.warrants.get(("known", bank))
            if found is not None:
                trace.append({"bank": bank, "standing": standing, "class": found[0], "rule": found[1]})
        warrants += [(e.entry_id, bank, layer, cls, rule) for (layer, bank), (cls, rule) in sorted(e.warrants.items())]
        decided = assignments(e.masks)
        if any(decided.get(bank, 0) == 0 for bank in e.hierarchy):
            raise ValueError(f"HIERARCHY_REQUIRES_NONZERO_BASE {e.entry_id}")
        hierarchy = _json(e.hierarchy)
        states.append(
            (
                e.entry_id,
                i,
                c,
                _json(domains(e.masks)),
                _json(conflicts),
                _json(trace),
                hierarchy,
                hex_masks(e.masks),
                hex_masks(e.known),
            )
        )
        if c != "CONFLICT":
            index = {bank: col for col, bank in enumerate(BANKS)}
            values += [(i, bank, v, FORMAT, e.standing(index[bank])) for bank, v in sorted(decided.items())]
    conn.executemany(
        "INSERT INTO lexemes(id,lemma,pos,sense_id,gloss,source,validation_status) VALUES (?,?,?,?,?,?,?)", lexemes
    )
    conn.executemany("INSERT INTO definition_states VALUES (?,?,?,?,?,?,?,?,?)", states)
    conn.executemany(
        "INSERT INTO primitive_values(lexeme_id,primitive,value,source,standing) VALUES (?,?,?,?,?)", values
    )
    conn.executemany("INSERT INTO cell_warrants VALUES (?,?,?,?,?)", warrants)
    return len(lexemes)


def values(conn: sqlite3.Connection, entry_id: str, layer: str = "all") -> dict[str, int]:
    """A definition's decided signs: every published value (`layer="all"`, the default), or the known layer's alone
    (`layer="known"`), never a default passed off as known."""
    if layer not in ("all", "known"):
        raise ValueError(f"UNKNOWN_LAYER {layer}")
    query = (
        "SELECT p.primitive, p.value FROM primitive_values p JOIN definition_states d ON d.lexeme_id=p.lexeme_id "
        "WHERE d.entry_id=?" + (" AND p.standing='known'" if layer == "known" else "")
    )
    return dict(conn.execute(query + " ORDER BY p.primitive", (entry_id,)).fetchall())


def masks(conn: sqlite3.Connection, entry_id: str, layer: str = "all") -> np.ndarray:
    """A definition's four-state masks in the published layer (`"all"`) or the known layer (`"known"`)."""
    column = {"all": "masks", "known": "known_masks"}[layer]
    raw = conn.execute(f"SELECT {column} FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()[0]
    return np.array([int(c, 16) for c in raw], dtype=np.uint8)


def write_observations(conn: sqlite3.Connection, records: Iterable[dict]) -> int:
    out = [(r["record_id"], r["entry_id"], r["source"], r["family"], r["scope"], _json(r)) for r in records]
    conn.executemany("INSERT INTO source_observations VALUES (?,?,?,?,?,?)", out)
    return len(out)


def sense_rows(npz_path: Path, records_path: Path) -> tuple[list[dict], list[tuple[str, str, str, str]]]:
    """`word_senses` rows and residual definitions from `senses.persist`'s arrays and records."""
    data = np.load(npz_path, allow_pickle=True)
    if list(data["banks"]) != list(BANKS):
        raise ValueError("SENSE_BANKS_DIFFER")
    index = {str(sid): i for i, sid in enumerate(data["sense_ids"])}
    known, interpolated = data["known"], data["interpolated"]
    records, residuals = {}, []
    with Path(records_path).open(encoding="utf-8") as lines:
        for line in lines:
            r = json.loads(line)
            if r["type"] == "sense":
                records[r["sense"]] = r
            else:
                residuals += [(r["lemma"], r["pos"], res["reading"], _json(res)) for res in r["residuals"]]
    by_word: dict[tuple[str, str], list[str]] = {}
    for sid, r in records.items():
        by_word.setdefault((r["lemma"], r["pos"]), []).append(sid)
    rows = []
    for (lemma, pos), sids in by_word.items():
        for number, sid in enumerate(sorted(sids, key=lambda x: int(x.rsplit(":", 1)[1]))):
            r, published, known_masks = records[sid], interpolated[index[sid]], known[index[sid]]
            evidenced = set(r["evidenced"])
            decided = assignments(published)
            open_ = {
                bank: signs(int(m))
                for bank, m, start in zip(BANKS, published, START)
                if int(m) != int(start) and bank not in decided and int(m) and not int(m) & SILENT
            }
            standing = {
                bank: "known" if int(known_masks[col]) == int(published[col]) else "interpolated"
                for col, bank in enumerate(BANKS)
                if bank in decided
            }
            rows.append(
                {
                    "lemma": lemma,
                    "pos": pos,
                    "sense": number,
                    "code": code(published),
                    "core": decided,
                    "members": [m for m in r["members"] if m in evidenced],
                    "absorbed": [m for m in r["members"] if m not in evidenced],
                    "assignments": decided,
                    "open": open_,
                    "provenance": {
                        "sense_id": sid,
                        "kind": r["kind"],
                        "load_bearing": r["load_bearing"],
                        "standing": standing,
                        "known": r["known"],
                        "interpolated": r["interpolated"],
                        "splits": r["splits"],
                        "against_core": r["against_core"],
                    },
                    "blocked": r["conflicts"],
                }
            )
    return rows, residuals


def write_residuals(conn: sqlite3.Connection, residuals: Iterable[tuple[str, str, str, str]]) -> int:
    out = list(residuals)
    conn.executemany("INSERT INTO sense_residuals VALUES (?,?,?,?)", out)
    return len(out)


def write_senses(conn: sqlite3.Connection, senses: Iterable[dict]) -> int:
    """`word_senses` rows. Each sense is a dict with the table's columns; JSON columns are serialised here."""
    columns = (
        "lemma",
        "pos",
        "sense",
        "code",
        "core",
        "members",
        "absorbed",
        "assignments",
        "open",
        "provenance",
        "blocked",
    )
    text = {"lemma", "pos", "sense", "code"}
    out = [tuple(s[c] if c in text else _json(s[c]) for c in columns) for s in senses]
    conn.executemany(f"INSERT INTO word_senses VALUES ({','.join('?' * len(columns))})", out)
    return len(out)


# --- Fixtures for runtime tests -------------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureEntry:
    """A hand-written definition for a runtime test: `values` are decided signs (+1, -1, 0) or "SILENT"; every
    other bank keeps its starting mask."""

    entry_id: str
    lemma: str
    pos: str
    gloss: str
    values: dict = field(default_factory=dict)
    hierarchy: dict = field(default_factory=dict)


def fixture_masks(values: dict) -> np.ndarray:
    from .cells import BANK_INDEX, bit

    masks = START.copy()
    for bank, value in values.items():
        masks[BANK_INDEX[bank]] = bit(value)
    return masks


def closed_class_fixtures(parser=None) -> tuple[list[FixtureEntry], list[dict]]:
    """The closed-class catalog as stated definitions, as the build states them for the `gse_closed_class` family
    (the lead's ruling B, 2026-11-27). Each entry has the catalog's declared primitives as decided values, a negative
    pole written as its bank at -1 (BELOW is ABOVE -1), and its native record."""
    from .cells import NEGATIVE_POLES
    from .native_records import closed_class_record

    if parser is None:
        from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

        parser = GSEClosedClassParser()
        parser.load()
    entries, records = [], []
    for found in parser.entries.values():
        for e in found:
            values = {
                NEGATIVE_POLES.get(bank, bank): -value if bank in NEGATIVE_POLES else value
                for bank, value in e.primitives.items()
            }
            entries.append(FixtureEntry(e.entry_id, e.lemma, e.pos, e.definition, values))
            records.append(closed_class_record(e))
    return entries, records


def _fixture_entries(entries, closed: bool) -> list[Entry]:
    entries = list(entries)
    masks = np.stack([fixture_masks(e.values) for e in entries]) if entries else np.zeros((0, len(BANKS)), np.uint8)
    if closed and entries:
        from . import guards, laws
        from .cells import State
        from .closure import close
        from .inventory import Reading

        readings = tuple(Reading(e.entry_id, e.lemma, e.pos, e.gloss) for e in entries)
        state = State(tuple(r.reading_id for r in readings), masks)
        relations = laws.compile_laws()
        close(state, relations, guards.scopes(readings, {r.scope for r in relations}))
        masks = state.masks
    return [Entry(e.entry_id, e.lemma, e.pos, e.gloss, m, hierarchy=e.hierarchy) for e, m in zip(entries, masks)]


def add_fixtures(conn: sqlite3.Connection, entries: Iterable[FixtureEntry], closed: bool = False) -> int:
    """Add hand-written definitions to an open artifact (a test that grows its lexicon mid-test)."""
    return write_entries(conn, _fixture_entries(entries, closed))


def fixture(
    path: Path, entries: Iterable[FixtureEntry], observations: Iterable[dict] = (), senses=(), closed: bool = False
) -> Path:
    """A small artifact for a runtime test, written through the same tables as the real one. With `closed`, each
    definition is first closed under the authored laws (`laws.compile_laws`), as the build would close it."""
    conn = create(path)
    try:
        write_entries(conn, _fixture_entries(entries, closed))
        write_observations(conn, observations)
        write_senses(conn, senses)
        conn.commit()
    finally:
        conn.close()
    return Path(path)


# --- The real artifact ----------------------------------------------------------------------------------------


def from_round(state_path: Path, readings) -> tuple[list[Entry], dict]:
    """Entries from the round runner's persisted state (`scripts/rebuild_lexicon.persist`): the interpolated layer
    published, the known layer kept, and each layer's warrant per narrowed cell."""
    data = np.load(state_path, allow_pickle=True)
    ids = [str(x) for x in data["readings"]]
    if list(data["banks"]) != list(BANKS):
        raise ValueError("ROUND_BANKS_DIFFER")
    by_id = {r.reading_id: r for r in readings}
    if set(ids) != set(by_id):
        raise ValueError("ROUND_READINGS_DIFFER_FROM_COHORT")
    known, interpolated = data["known_masks"], data["interpolated_masks"]
    rule_ids, classes = [str(x) for x in data["rule_ids"]], [str(x) for x in data["classes"]]

    k_cls, k_rule = data["known_class"], data["known_rule"]
    i_cls, i_rule = data["interpolated_class"], data["interpolated_rule"]
    entries = []
    for row, rid in enumerate(ids):
        r = by_id[rid]
        warrants = {
            ("known", BANKS[c]): (classes[int(k_cls[row, c])], rule_ids[int(k_rule[row, c])])
            for c in np.flatnonzero(k_rule[row] >= 0)
        }
        for c in np.flatnonzero(interpolated[row] != known[row]):
            rule = rule_ids[int(i_rule[row, c])] if i_rule[row, c] >= 0 else None
            warrants[("interpolated", BANKS[c])] = (classes[int(i_cls[row, c])] if rule else "interpolated", rule)
        entries.append(Entry(rid, r.lemma, r.pos, r.gloss, interpolated[row], warrants, known_masks=known[row]))
    return entries, {"rules": len(rule_ids), "classes": classes}


def write_artifact(path: Path, entries, observations=(), senses=(), residuals=(), metadata=None) -> dict:
    """Write the whole artifact in one transaction and return its census."""
    conn = create(path)
    try:
        receipt = {
            "lexemes": write_entries(conn, entries),
            "source_observations": write_observations(conn, observations),
            "word_senses": write_senses(conn, senses),
            "sense_residuals": write_residuals(conn, residuals),
        }
        for key, value in (metadata or {}).items():
            conn.execute("INSERT INTO builder_metadata VALUES (?,?)", (key, _json(value)))
        receipt["codes"] = dict(conn.execute("SELECT code, COUNT(*) FROM definition_states GROUP BY code").fetchall())
        receipt["primitive_values"] = dict(
            conn.execute("SELECT standing, COUNT(*) FROM primitive_values GROUP BY standing").fetchall()
        )
        receipt["cell_warrants"] = dict(
            conn.execute("SELECT layer, COUNT(*) FROM cell_warrants GROUP BY layer").fetchall()
        )
        conn.commit()
    finally:
        conn.close()
    return receipt


# --- Acceptance through the real consumer ---------------------------------------------------------------------

WITNESSES = {
    "florbles": "The florbles are bigger than the blobbles.",
    "lock_noun": "She turned the key in the lock.",
    "lock_verb": "They lock the door at night.",
    "he_pronoun": "He went home after work.",
    "he_chemical": "He is a noble gas with the atomic number two.",
    "prose": "The old farmer walked to the market because he wanted to sell his apples before the rain began.",
}


def acceptance(path: Path) -> dict:
    """Each witness through `GSEEncoder` on this artifact (never the active pointer): what every token reads."""
    from GSE.api.encoder import GSEEncoder

    out = {}
    with GSEEncoder(str(path)) as encoder:
        for name, text in WITNESSES.items():
            tokens = []
            for t in encoder.encode(text).tokens:
                evidence = t.lexical_evidence or {}
                selected = evidence.get("selected_record") or {}
                tokens.append(
                    {
                        "token": t.token,
                        "lemma": t.lemma,
                        "pos": t.pos,
                        "lexicon_status": t.lexicon_status,
                        "selection": evidence.get("selection_status"),
                        "selected": selected.get("entry_id"),
                        "candidates": len(evidence.get("candidate_entry_ids") or ()),
                        "primitives": dict(t.word_primitives or {}),
                    }
                )
            out[name] = {"text": text, "tokens": tokens}
    return out


def main(argv=None) -> dict:
    import argparse
    import time

    from . import inventory, native_records

    parser = argparse.ArgumentParser(description="Write the rebuilt lexicon artifact in the runtime's form.")
    parser.add_argument("--state", type=Path, default=Path("data/lexicon_builder/rebuild/round-final.npz"))
    parser.add_argument("--cohort", type=Path, default=Path("data/lexicon_builder/rebuild/cohort.jsonl"))
    parser.add_argument("--senses", type=Path, default=Path("data/lexicon_builder/rebuild/senses.npz"))
    parser.add_argument("--sense-records", type=Path, default=Path("data/lexicon_builder/rebuild/senses.jsonl"))
    parser.add_argument("--out", type=Path, required=True, help="a new file under data/lexicon_builder/rebuild/")
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    readings = inventory.load(args.cohort)
    entries, round_info = from_round(args.state, readings)
    records = native_records.records(readings)
    accepted = native_records.validate(readings, records)
    senses, residuals = sense_rows(args.senses, args.sense_records)
    written = write_artifact(
        args.out,
        entries,
        records,
        senses,
        residuals,
        metadata={"cohort_sha256": inventory.digest(readings), "round_state": str(args.state), "round": round_info},
    )
    receipt = {
        "format": "GSE.rebuild-artifact/1",
        "artifact": str(args.out),
        "bytes": args.out.stat().st_size,
        "written": written,
        "native_records_accepted_by_the_runtime": accepted,
        "seconds_to_write": round(time.perf_counter() - started, 1),
        "acceptance": acceptance(args.out),
        "active_pointer_touched": False,
    }
    if args.receipt:
        args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "acceptance"}, indent=1))
    return receipt


if __name__ == "__main__":
    main()
