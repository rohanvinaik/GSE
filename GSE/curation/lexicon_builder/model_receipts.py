"""Indexed accepted rulings with lazy replay and strict legacy compatibility."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import fields

from .engine import Assertion
from .storage import _json

VERSION = "gse.model-receipts/3"
LEGACY_VERSION = "gse.model-receipts/1"
CONTEXT_VERSION = "gse.model-receipts/2"
REQUEST_STORAGE = "gse.model-receipt-request-storage/2"
LEGACY_REQUEST_STORAGE = "gse.model-receipt-request-storage/1"
PROOF_STORAGE = "gse.model-proof-trace/1"
TABLE = "accepted_model_receipts"
SCHEMA = """CREATE TABLE IF NOT EXISTS accepted_model_receipts (
 entry_id TEXT NOT NULL, ordinal INTEGER NOT NULL, request_id TEXT NOT NULL UNIQUE,
 payload TEXT NOT NULL, PRIMARY KEY(entry_id,ordinal))"""
CONTEXT_TABLE = "model_receipt_contexts"
CONTEXT_SCHEMA = """CREATE TABLE IF NOT EXISTS model_receipt_contexts (
 context_sha256 TEXT PRIMARY KEY NOT NULL, payload TEXT NOT NULL)"""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_RECEIPT_JSON_FIELD")
        result[key] = value
    return result


def _decode(payload):
    record = json.loads(payload, object_pairs_hook=_object)
    _json(record)  # Refuse non-finite values, including overflowing JSON floats.
    return record


def _metadata(conn, key, default=None):
    row = conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchone()
    return _decode(row[0]) if row else default


def _set_metadata(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _json(value)))


def validate_receipt(record):
    required = {"entry_id", "assertion", "request_id", "code", "request", "schema"}
    if (
        not isinstance(record, dict)
        or set(record) != required
        or not isinstance(record["entry_id"], str)
        or not record["entry_id"].strip()
    ):
        raise ValueError("INVALID_MODEL_AUTHORITY")
    raw = record["assertion"]
    if not isinstance(raw, dict) or set(raw) != {field.name for field in fields(Assertion)}:
        raise ValueError("INVALID_MODEL_ASSERTION")
    assertion = Assertion(**raw)
    if (
        record["code"] != "ASSIGNED"
        or record["request_id"] != assertion.record_id
        or assertion.family != "model"
        or not assertion.source.startswith("model:")
        or not assertion.source.removeprefix("model:").strip()
        or not isinstance(record["request"], dict)
        or not isinstance(record["schema"], dict)
    ):
        raise ValueError("INVALID_MODEL_AUTHORITY")
    return record


def _context_digest(payload):
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _read_context(conn, digest):
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("INVALID_MODEL_RECEIPT_CONTEXT_REFERENCE")
    rows = conn.execute(
        "SELECT payload FROM model_receipt_contexts WHERE context_sha256=? LIMIT 2", (digest,)
    ).fetchall()
    if not rows:
        raise ValueError("MISSING_MODEL_RECEIPT_CONTEXT")
    if len(rows) != 1:
        raise ValueError("DUPLICATE_MODEL_RECEIPT_CONTEXT")
    value = _decode(rows[0][0])
    if _context_digest(value) != digest:
        raise ValueError("MODEL_RECEIPT_CONTEXT_HASH_MISMATCH")
    return value


def _store_context(conn, value):
    digest = _context_digest(value)
    conn.execute("INSERT OR IGNORE INTO model_receipt_contexts VALUES (?,?)", (digest, _json(value)))
    # An existing key is not sufficient: load and verify the immutable payload.
    if _json(_read_context(conn, digest)) != _json(value):
        raise ValueError("MODEL_RECEIPT_CONTEXT_HASH_COLLISION")
    return digest


def _stored_scaffold_field(conn, key, value):
    if key == "proof_trace" and isinstance(value, list):
        return {
            "format": PROOF_STORAGE,
            "trace_sha256": _context_digest(value),
            "record_sha256s": [_store_context(conn, record) for record in value],
        }
    return _store_context(conn, value)


def _restored_scaffold_field(conn, key, reference, version):
    if version == VERSION and key == "proof_trace" and isinstance(reference, dict):
        if (
            set(reference) != {"format", "trace_sha256", "record_sha256s"}
            or reference["format"] != PROOF_STORAGE
            or not isinstance(reference["record_sha256s"], list)
        ):
            raise ValueError("INVALID_MODEL_RECEIPT_PROOF_TRACE")
        # Preserve duplicates and original order, and validate the entire loaded
        # trace. A set of individually valid records is not the same proof.
        trace = [_read_context(conn, digest) for digest in reference["record_sha256s"]]
        if _context_digest(trace) != reference["trace_sha256"]:
            raise ValueError("MODEL_RECEIPT_PROOF_TRACE_HASH_MISMATCH")
        return trace
    return _read_context(conn, reference)


def _stored_receipt(conn, record):
    """Split large repeated fields, preserving every original request field."""
    request = dict(record["request"])
    contexts = {key: _store_context(conn, request.pop(key)) for key in ("observations", "definition") if key in request}
    scaffold = None
    if isinstance(request.get("scaffold"), dict):
        # Relation tables/context stay stable even as domains and proof traces change.
        scaffold = {key: _stored_scaffold_field(conn, key, value) for key, value in request.pop("scaffold").items()}
    return {
        **record,
        "request": {"format": REQUEST_STORAGE, "inline": request, "contexts": contexts, "scaffold": scaffold},
    }


def _restored_receipt(conn, record, version):
    if version == LEGACY_VERSION:
        return validate_receipt(record)
    if not isinstance(record, dict):
        raise ValueError("INVALID_MODEL_AUTHORITY")
    envelope = record.get("request")
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"format", "inline", "contexts", "scaffold"}
        or envelope["format"] != (LEGACY_REQUEST_STORAGE if version == CONTEXT_VERSION else REQUEST_STORAGE)
        or not isinstance(envelope["inline"], dict)
        or not isinstance(envelope["contexts"], dict)
        or set(envelope["contexts"]) - {"observations", "definition"}
        or envelope["scaffold"] is not None
        and not isinstance(envelope["scaffold"], dict)
    ):
        raise ValueError("INVALID_MODEL_RECEIPT_STORED_REQUEST")
    request = dict(envelope["inline"])
    if request.keys() & envelope["contexts"].keys() or envelope["scaffold"] is not None and "scaffold" in request:
        raise ValueError("MODEL_RECEIPT_CONTEXT_FIELD_COLLISION")
    request.update({key: _read_context(conn, digest) for key, digest in envelope["contexts"].items()})
    if envelope["scaffold"] is not None:
        request["scaffold"] = {
            key: _restored_scaffold_field(conn, key, reference, version)
            for key, reference in envelope["scaffold"].items()
        }
    return validate_receipt({**record, "request": request})


class ModelReceipts(Mapping):
    """Keep only entry identities in memory; load bodies for one definition."""

    def __init__(self, conn, entries, version=VERSION):
        self.conn = conn
        self.entries = frozenset(entries)
        self.version = version

    def __iter__(self):
        return iter(sorted(self.entries))

    def __len__(self):
        return len(self.entries)

    def __contains__(self, entry):
        return entry in self.entries

    def __getitem__(self, entry):
        if entry not in self.entries:
            raise KeyError(entry)
        return tuple(
            _restored_receipt(self.conn, _decode(row[0]), self.version)
            for row in self.conn.execute(
                "SELECT payload FROM accepted_model_receipts WHERE entry_id=? ORDER BY ordinal", (entry,)
            )
        )


def read_model_receipts(conn):
    """Validate the complete authority index while streaming receipt bodies.

    A nonempty legacy list cannot be hidden by a newer table. Replay therefore
    cannot silently choose one of two competing authorities for a model value.
    """
    legacy = _metadata(conn, "model_completions", [])
    version = _metadata(conn, "model_receipts_format")
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone()
    if not isinstance(legacy, list):
        raise ValueError("INVALID_ASSERTION_AUTHORITIES")
    if version is None and not exists:
        grouped = defaultdict(list)
        requests = set()
        for raw in legacy:
            record = validate_receipt(raw)
            if record["request_id"] in requests:
                raise ValueError("DUPLICATE_MODEL_RECEIPT")
            requests.add(record["request_id"])
            grouped[record["entry_id"]].append(record)
        return grouped
    if version not in (LEGACY_VERSION, CONTEXT_VERSION, VERSION):
        raise ValueError("UNSUPPORTED_MODEL_RECEIPTS_FORMAT")
    if not exists:
        raise ValueError("MISSING_MODEL_RECEIPTS_TABLE")
    if legacy:
        raise ValueError("COMPETING_MODEL_RECEIPT_AUTHORITIES")
    if version in (CONTEXT_VERSION, VERSION):
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (CONTEXT_TABLE,)).fetchone():
            raise ValueError("MISSING_MODEL_RECEIPT_CONTEXT_TABLE")
        context_columns = {row[1] for row in conn.execute("PRAGMA table_info(model_receipt_contexts)")}
        if not {"context_sha256", "payload"} <= context_columns:
            raise ValueError("INVALID_MODEL_RECEIPT_CONTEXT_SCHEMA")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(accepted_model_receipts)")}
    if not {"entry_id", "ordinal", "request_id", "payload"} <= columns:
        raise ValueError("INVALID_MODEL_RECEIPTS_SCHEMA")
    entries, requests = set(), set()
    previous, next_ordinal = None, 0
    for entry, ordinal, request_id, payload in conn.execute(
        "SELECT entry_id,ordinal,request_id,payload FROM accepted_model_receipts ORDER BY entry_id,ordinal"
    ):
        record = _restored_receipt(conn, _decode(payload), version)
        if entry != previous:
            next_ordinal = 0
            previous = entry
        if type(ordinal) is not int or ordinal != next_ordinal:
            raise ValueError("INVALID_MODEL_RECEIPT_ORDINAL")
        if entry != record["entry_id"] or request_id != record["request_id"]:
            raise ValueError("MODEL_RECEIPT_COLUMN_PAYLOAD_MISMATCH")
        if request_id in requests:
            raise ValueError("DUPLICATE_MODEL_RECEIPT")
        next_ordinal += 1
        entries.add(entry)
        requests.add(request_id)
    return ModelReceipts(conn, entries, version)


def append_model_receipt(conn, record):
    """Append one accepted ruling inside the caller's assignment transaction."""
    validate_receipt(record)
    if _metadata(conn, "model_receipts_format") != VERSION:
        raise ValueError("MODEL_RECEIPTS_MIGRATION_REQUIRED")
    ordinal = conn.execute(
        "SELECT COALESCE(MAX(ordinal)+1,0) FROM accepted_model_receipts WHERE entry_id=?", (record["entry_id"],)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO accepted_model_receipts VALUES (?,?,?,?)",
        (record["entry_id"], ordinal, record["request_id"], _json(_stored_receipt(conn, record))),
    )


def _prune_unreferenced_contexts(conn):
    """Discard only blobs no longer referenced after complete receipt migration."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS live_model_receipt_contexts (context_sha256 TEXT PRIMARY KEY)")
    conn.execute("DELETE FROM live_model_receipt_contexts")
    for (payload,) in conn.execute("SELECT payload FROM accepted_model_receipts"):
        envelope = _decode(payload)["request"]
        references = list(envelope["contexts"].values())
        for key, value in (envelope["scaffold"] or {}).items():
            if key == "proof_trace" and isinstance(value, dict):
                references.extend(value["record_sha256s"])
            else:
                references.append(value)
        conn.executemany("INSERT OR IGNORE INTO live_model_receipt_contexts VALUES (?)", ((ref,) for ref in references))
    conn.execute(
        "DELETE FROM model_receipt_contexts WHERE NOT EXISTS "
        "(SELECT 1 FROM live_model_receipt_contexts live WHERE live.context_sha256=model_receipt_contexts.context_sha256)"
    )
    conn.execute("DROP TABLE live_model_receipt_contexts")


def migrate_model_receipts(conn):
    """Migrate validated legacy authority once, inside the caller's transaction."""
    if not conn.in_transaction:
        conn.execute("BEGIN")
    records = read_model_receipts(conn)
    if isinstance(records, ModelReceipts) and records.version == VERSION:
        return
    conn.execute(SCHEMA)
    conn.execute(CONTEXT_SCHEMA)
    _set_metadata(conn, "model_receipts_format", VERSION)
    for entry in sorted(records):
        for record in records[entry]:
            if isinstance(records, ModelReceipts):
                conn.execute(
                    "UPDATE accepted_model_receipts SET payload=? WHERE request_id=?",
                    (_json(_stored_receipt(conn, record)), record["request_id"]),
                )
            else:
                append_model_receipt(conn, record)
    _set_metadata(conn, "model_completions", [])
    _prune_unreferenced_contexts(conn)


def reset_model_receipts(conn):
    """A rebuilt snapshot owns new authority; old receipts must not survive."""
    if not conn.in_transaction:
        conn.execute("BEGIN")
    version = _metadata(conn, "model_receipts_format")
    if version not in (None, LEGACY_VERSION, CONTEXT_VERSION, VERSION):
        raise ValueError("UNSUPPORTED_MODEL_RECEIPTS_FORMAT")
    conn.execute(SCHEMA)
    conn.execute(CONTEXT_SCHEMA)
    conn.execute("DELETE FROM accepted_model_receipts")
    conn.execute("DELETE FROM model_receipt_contexts")
    _set_metadata(conn, "model_receipts_format", VERSION)
    _set_metadata(conn, "model_completions", [])
