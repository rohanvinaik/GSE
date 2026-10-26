"""Atomic, deterministic SQLite publication of the mask-aware symbolic artifact.

Compatibility tables expose settled written cells only. The full sparse record
remains authoritative: missing compatibility rows may be unresolved or silent,
and consumers must read released_readings to distinguish them. Publication does
not certify a candidate's semantic truth or resolve competing lexical senses.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from gse.lexicon_builder.artifact import validate_sparse
from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.core import CANONICAL_COORDINATES
from gse.lexicon_builder.sources import word_key

RELEASE_SCHEMA = "GSE_SYMBOLIC_LEXICON_RELEASE_V1"
RELEASE_SOURCE = "gse_symbolic_release"
_INPUTS = ("manifest.json", "sparse.jsonl", "structures.jsonl")


def _json(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("NON_JSON_RELEASE_PAYLOAD") from exc


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def release_manifest_status(manifest: object) -> str:
    """Validate the recorded source contract without fetching original resources."""
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        return "INVALID_RELEASE_MANIFEST"
    if manifest.get("basis_id") != BASIS_ID or manifest.get("coordinate_order") != list(CANONICAL_COORDINATES):
        return "INCOMPATIBLE_RELEASE_BASIS"
    words = manifest.get("words")
    if not _strings(words) or not words or any(not word_key(w) for w in words):
        return "INVALID_RELEASE_WORKLIST"
    if len({word_key(w) for w in words}) != len(words):
        return "DUPLICATE_RELEASE_WORKLIST_ID"
    if any(not _digest(manifest.get(k)) for k in ("rulebook_sha256", "foundation_sha256")):
        return "MISSING_RELEASE_CONTRACT_PIN"
    implementation = manifest.get("implementation")
    if (
        not isinstance(implementation, dict)
        or not implementation
        or any(not isinstance(k, str) or not k or not _digest(v) for k, v in implementation.items())
    ):
        return "MISSING_RELEASE_IMPLEMENTATION_PIN"
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        return "MISSING_RELEASE_SOURCE_PINS"
    names, identities = set(), set()
    for source in sources:
        if not isinstance(source, dict) or any(
            not isinstance(source.get(k), str) or not source[k] for k in ("source", "units", "scope", "status")
        ):
            return "INVALID_RELEASE_SOURCE_PIN"
        if source["source"] in names:
            return "DUPLICATE_RELEASE_SOURCE_ID"
        names.add(source["source"])
        files = source.get("files")
        if not isinstance(files, list) or source["status"] not in {"AVAILABLE", "UNAVAILABLE"}:
            return "INVALID_RELEASE_SOURCE_PIN"
        if (source["status"] == "AVAILABLE") != bool(files):
            return "INCONSISTENT_RELEASE_SOURCE_PIN"
        for file in files:
            if (
                not isinstance(file, dict)
                or any(not isinstance(file.get(k), str) or not file[k] for k in ("path", "id"))
                or not _digest(file.get("sha256"))
            ):
                return "MISSING_RELEASE_SOURCE_HASH"
            identity = source["source"], file["id"]
            if identity in identities:
                return "DUPLICATE_RELEASE_SOURCE_FILE_ID"
            identities.add(identity)
    return "VALID_RELEASE_MANIFEST"


def _validated_manifest(manifest: object) -> dict:
    status = release_manifest_status(manifest)
    if status != "VALID_RELEASE_MANIFEST":
        raise ValueError(status)
    assert isinstance(manifest, dict)
    _json(manifest)
    return manifest


def _reading_status(record: dict) -> str:
    validate_sparse(record)
    provenance = record.get("provenance")
    if (
        not isinstance(provenance, dict)
        or any(not _strings(provenance.get(k)) for k in ("source_record_ids", "fired_rules", "model_requests"))
        or not isinstance(provenance.get("trace"), list)
    ):
        raise ValueError("MISSING_RELEASE_PROVENANCE")
    if not isinstance(record.get("number_scale"), (dict, type(None))) or not isinstance(
        record.get("constructions"), (dict, list)
    ):
        raise ValueError("INVALID_RELEASE_SCALE_OR_CONSTRUCTION")
    if word_key(record["word"]) != record["word"]:
        raise ValueError("NONCANONICAL_RELEASE_SURFACE")
    states = {cell["state"] for cell in record["cells"].values()}
    # A native event/role collision can be a source conflict without emptying
    # the global cell domains. Its audit status still forbids selection.
    if record["code"] == "SOURCE_CONFLICT":
        return "symbolic_conflict"
    if (record["code"] == "CONFLICT") != ("conflict" in states):
        raise ValueError("RELEASE_CONFLICT_STATUS_MISMATCH")
    if "conflict" in states:
        return "symbolic_conflict"
    if record["code"] in {"CANDIDATE_COMPLETE", "RESOLVED"}:
        if "unresolved" in states:
            raise ValueError("RELEASE_COMPLETENESS_STATUS_MISMATCH")
        return "symbolic_complete"
    return "symbolic_partial"


def _validated_structure(record: object) -> dict:
    if not isinstance(record, dict) or record.get("basis_id") != BASIS_ID:
        raise ValueError("INCOMPATIBLE_RELEASE_STRUCTURE_BASIS")
    if any(
        not isinstance(record.get(k), str) or not record[k]
        for k in ("word", "reading_id", "operation", "source", "location")
    ):
        raise ValueError("MALFORMED_RELEASE_STRUCTURE")
    if (
        not _strings(record.get("surfaces"))
        or record["word"] not in record["surfaces"]
        or not _strings(record.get("basis_gaps"))
    ):
        raise ValueError("MALFORMED_RELEASE_STRUCTURE")
    if not isinstance(record.get("claims"), list) or not isinstance(record.get("lexical_projection"), dict):
        raise ValueError("MISSING_RELEASE_STRUCTURE_ACCOUNT")
    if record["lexical_projection"].get("code") not in {"CONSTRUCTION_ONLY", "WARRANTED_PARTIAL_LEXICAL_PROJECTION"}:
        raise ValueError("INVALID_RELEASE_STRUCTURE_ACCOUNT")
    if word_key(record["word"]) != record["word"]:
        raise ValueError("NONCANONICAL_RELEASE_SURFACE")
    _json(record)
    return record


def _records(path: Path) -> Iterator[dict]:
    with path.open() as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeError) as exc:
                raise ValueError("INVALID_RELEASE_JSON:" + path.name) from exc
            yield record


_SCHEMA = """
PRAGMA user_version = 1;
PRAGMA application_id = 1196639564;
CREATE TABLE release_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE released_readings (
    lexeme_id INTEGER PRIMARY KEY, word TEXT NOT NULL, reading_id TEXT NOT NULL,
    validation_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL, payload TEXT NOT NULL,
    UNIQUE(word, reading_id)
);
CREATE TABLE lexemes (
    id INTEGER PRIMARY KEY REFERENCES released_readings(lexeme_id),
    lemma TEXT NOT NULL, pos TEXT NOT NULL, reading_id TEXT NOT NULL,
    source TEXT NOT NULL, validation_status TEXT NOT NULL,
    comp_primitive TEXT, comp_arity INTEGER, comp_operation TEXT
);
CREATE INDEX lexemes_lemma ON lexemes(lemma, id);
CREATE TABLE primitive_values (
    lexeme_id INTEGER NOT NULL REFERENCES lexemes(id), primitive TEXT NOT NULL,
    value INTEGER NOT NULL CHECK(value IN (-1,0,1)), PRIMARY KEY(lexeme_id, primitive)
) WITHOUT ROWID;
CREATE TABLE sentence_primitive_values (
    lexeme_id INTEGER NOT NULL REFERENCES lexemes(id), primitive TEXT NOT NULL,
    value INTEGER NOT NULL CHECK(value IN (-1,0,1)), PRIMARY KEY(lexeme_id, primitive)
) WITHOUT ROWID;
CREATE TABLE released_structures (
    word TEXT NOT NULL, reading_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
    payload TEXT NOT NULL, PRIMARY KEY(word, reading_id)
) WITHOUT ROWID;
CREATE TEMP TABLE staging_readings (
    word TEXT NOT NULL, reading_id TEXT NOT NULL, validation_status TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(word,reading_id)
) WITHOUT ROWID;
CREATE TEMP TABLE staging_structures (
    word TEXT NOT NULL, reading_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
    payload TEXT NOT NULL, PRIMARY KEY(word,reading_id)
) WITHOUT ROWID;
"""


def _populate(conn: sqlite3.Connection, build_dir: Path, manifest: dict, pins: dict[str, str]) -> dict:
    worklist = {word_key(w) for w in manifest["words"]}
    for record in _records(build_dir / "sparse.jsonl"):
        status = _reading_status(record)
        if record["word"] not in worklist:
            raise ValueError("RELEASE_SURFACE_OUTSIDE_WORKLIST")
        payload = _json(record)
        try:
            conn.execute(
                "INSERT INTO staging_readings VALUES (?,?,?,?,?)",
                (record["word"], record["reading_id"], status, _sha(payload), payload),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("DUPLICATE_RELEASE_READING_ID") from exc
    for record in _records(build_dir / "structures.jsonl"):
        record = _validated_structure(record)
        if record["word"] not in worklist:
            raise ValueError("RELEASE_SURFACE_OUTSIDE_WORKLIST")
        payload = _json(record)
        try:
            conn.execute(
                "INSERT INTO staging_structures VALUES (?,?,?,?)",
                (record["word"], record["reading_id"], _sha(payload), payload),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("DUPLICATE_RELEASE_STRUCTURE_ID") from exc
    conn.execute(
        "INSERT INTO released_readings SELECT row_number() OVER (ORDER BY word,reading_id), word,reading_id,validation_status,payload_sha256,payload FROM staging_readings ORDER BY word,reading_id"
    )
    conn.execute("INSERT INTO released_structures SELECT * FROM staging_structures ORDER BY word,reading_id")
    counts: dict[str, int] = {}
    for lexeme_id, word, reading_id, status, payload in conn.execute(
        "SELECT lexeme_id,word,reading_id,validation_status,payload FROM released_readings ORDER BY lexeme_id"
    ):
        counts[status] = counts.get(status, 0) + 1
        if status == "symbolic_conflict":
            continue
        record = json.loads(payload)
        pos = record.get("pos", "x")
        if not isinstance(pos, str) or not pos:
            raise ValueError("INVALID_RELEASE_POS")
        conn.execute(
            "INSERT INTO lexemes(id,lemma,pos,reading_id,source,validation_status) VALUES (?,?,?,?,?,?)",
            (lexeme_id, word, pos, reading_id, RELEASE_SOURCE, status),
        )
        conn.executemany(
            "INSERT INTO primitive_values VALUES (?,?,?)",
            [(lexeme_id, c, cell["value"]) for c, cell in record["cells"].items() if cell["written"] is True],
        )
    counts["structures"] = conn.execute("SELECT count(*) FROM released_structures").fetchone()[0]
    metadata = {
        "schema": RELEASE_SCHEMA,
        "basis_id": BASIS_ID,
        "coordinate_order": list(CANONICAL_COORDINATES),
        "manifest": manifest,
        "manifest_snapshot_sha256": _sha(_json(manifest)),
        "input_sha256": pins,
        "counts": counts,
    }
    conn.executemany("INSERT INTO release_metadata VALUES (?,?)", [(k, _json(v)) for k, v in sorted(metadata.items())])
    return counts


def _release_metadata(conn: sqlite3.Connection) -> dict:
    if not isinstance(conn, sqlite3.Connection):
        raise ValueError("INVALID_RELEASE_CONNECTION")
    try:
        values = {row[0]: json.loads(row[1]) for row in conn.execute("SELECT key,value FROM release_metadata")}
    except (sqlite3.Error, ValueError, TypeError) as exc:
        raise ValueError("INVALID_RELEASE_METADATA") from exc
    if (
        values.get("schema") != RELEASE_SCHEMA
        or values.get("basis_id") != BASIS_ID
        or values.get("coordinate_order") != list(CANONICAL_COORDINATES)
    ):
        raise ValueError("INCOMPATIBLE_RELEASE_BASIS")
    manifest = _validated_manifest(values.get("manifest"))
    if values.get("manifest_snapshot_sha256") != _sha(_json(manifest)):
        raise ValueError("RELEASE_MANIFEST_DIGEST_MISMATCH")
    pins = values.get("input_sha256")
    if not isinstance(pins, dict) or set(pins) != set(_INPUTS) or any(not _digest(v) for v in pins.values()):
        raise ValueError("MISSING_RELEASE_INPUT_PINS")
    return values


@dataclass
class ReleaseReader:
    """One validated connection, invalidated by local or external DB writes.

    The caller owns its lifetime alongside the connection and file identity.
    There is deliberately no global cache. Full manifest validation is reused
    only while SQLite's data_version and the connection's total_changes agree.
    """

    conn: sqlite3.Connection
    metadata: dict = field(init=False, default_factory=dict)
    validation_status: str = field(init=False, default="INITIAL_VALIDATION")
    invalidation_code: str = field(init=False, default="INITIAL_VALIDATION")
    _version: tuple[int, int] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.validate()

    def _token(self) -> tuple[int, int]:
        if not isinstance(self.conn, sqlite3.Connection):
            raise ValueError("INVALID_RELEASE_CONNECTION")
        try:
            return self.conn.execute("PRAGMA data_version").fetchone()[0], self.conn.total_changes
        except sqlite3.Error as exc:
            raise ValueError("UNAVAILABLE_RELEASE_CONNECTION") from exc

    def validate(self) -> dict:
        before = self._token()
        if before == self._version:
            self.validation_status = "REUSED_VALIDATED_RELEASE_CONNECTION"
            return self.metadata
        if self._version is not None:
            self.invalidation_code = (
                "SAME_CONNECTION_CHANGED" if before[1] != self._version[1] else "EXTERNAL_CONNECTION_CHANGED"
            )
        self._version = None
        self.metadata = {}
        self.validation_status = "INVALIDATED_RELEASE_CONNECTION"
        metadata = _release_metadata(self.conn)
        after = self._token()
        if before != after:
            raise ValueError("RELEASE_CHANGED_DURING_VALIDATION")
        self.metadata, self._version = metadata, after
        self.validation_status = "VALIDATED_RELEASE_CONNECTION"
        return metadata


def _validate_connection(conn: sqlite3.Connection, reader: ReleaseReader | None) -> dict:
    if reader is None:
        return _release_metadata(conn)
    if not isinstance(reader, ReleaseReader) or reader.conn is not conn:
        raise ValueError("RELEASE_READER_CONNECTION_MISMATCH")
    return reader.validate()


def read_released_reading(conn: sqlite3.Connection, lexeme_id: int, *, reader: ReleaseReader | None = None) -> dict:
    """Read the full sparse payload by deterministic ID, including audit-only conflicts."""
    _validate_connection(conn, reader)
    if type(lexeme_id) is not int or lexeme_id < 1:
        raise ValueError("INVALID_RELEASE_LEXEME_ID")
    row = conn.execute(
        "SELECT word,reading_id,validation_status,payload_sha256,payload FROM released_readings WHERE lexeme_id=?",
        (lexeme_id,),
    ).fetchone()
    if row is None:
        raise ValueError("RELEASE_READING_NOT_FOUND")
    try:
        record = json.loads(row[4])
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_RELEASE_READING_JSON") from exc
    if _sha(row[4]) != row[3]:
        raise ValueError("RELEASE_READING_DIGEST_MISMATCH")
    status = _reading_status(record)
    if (record["word"], record["reading_id"], status) != tuple(row[:3]):
        raise ValueError("RELEASE_READING_IDENTITY_MISMATCH")
    return record


def read_released_structures(conn: sqlite3.Connection, word: str, *, reader: ReleaseReader | None = None) -> list[dict]:
    """Read separate construction homes without fabricating a lexical vector."""
    _validate_connection(conn, reader)
    if not isinstance(word, str) or not word_key(word):
        raise ValueError("INVALID_RELEASE_SURFACE")
    records = []
    for reading_id, digest, payload in conn.execute(
        "SELECT reading_id,payload_sha256,payload FROM released_structures WHERE word=? ORDER BY reading_id",
        (word_key(word),),
    ):
        if _sha(payload) != digest:
            raise ValueError("RELEASE_STRUCTURE_DIGEST_MISMATCH")
        record = _validated_structure(json.loads(payload))
        if record["word"] != word_key(word) or record["reading_id"] != reading_id:
            raise ValueError("RELEASE_STRUCTURE_IDENTITY_MISMATCH")
        records.append(record)
    return records


def build_release(build_dir: Path | str, db_path: Path | str) -> dict:
    """Validate and atomically publish one SQLite artifact, preserving any prior release on failure."""
    build_dir, db_path = Path(build_dir), Path(db_path)
    for name in _INPUTS:
        if not (build_dir / name).is_file():
            raise ValueError("MISSING_RELEASE_INPUT:" + name)
    pins = {name: _file_sha(build_dir / name) for name in _INPUTS}
    manifest_bytes = (build_dir / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != pins["manifest.json"]:
        raise ValueError("RELEASE_INPUT_CHANGED_DURING_BUILD")
    try:
        manifest = _validated_manifest(json.loads(manifest_bytes))
    except json.JSONDecodeError as exc:
        raise ValueError("INVALID_RELEASE_MANIFEST_JSON") from exc
    db_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix=".gse-lexicon-release-", suffix=".sqlite", dir=db_path.parent)
    os.close(descriptor)
    temporary = Path(filename)
    conn = None
    try:
        conn = sqlite3.connect(temporary)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(_SCHEMA)
        counts = _populate(conn, build_dir, manifest, pins)
        if {name: _file_sha(build_dir / name) for name in _INPUTS} != pins:
            raise ValueError("RELEASE_INPUT_CHANGED_DURING_BUILD")
        conn.commit()
        _release_metadata(conn)
        if (
            conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or conn.execute("PRAGMA foreign_key_check").fetchone() is not None
        ):
            raise ValueError("RELEASE_DATABASE_INTEGRITY_FAILURE")
        conn.close()
        conn = None
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        digest = _file_sha(temporary)
        os.replace(temporary, db_path)
        return {
            "schema": RELEASE_SCHEMA,
            "basis_id": BASIS_ID,
            "code": "PUBLISHED_SYMBOLIC_RELEASE",
            "path": str(db_path.resolve()),
            "sha256": digest,
            "input_sha256": pins,
            "counts": counts,
        }
    finally:
        if conn is not None:
            conn.close()
        temporary.unlink(missing_ok=True)
