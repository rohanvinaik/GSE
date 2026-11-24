"""Lossless question evidence in the learner ledger, never lexical authority."""

import hashlib
import json

from GSE.namespace import current_id

from .model_receipts import (
    CONTEXT_SCHEMA,
    CONTEXT_VERSION,
    VERSION,
    _context_digest,
    _read_context,
    _store_context,
    restore_request_context,
    store_request_context,
)

FORMAT = "GSE.lexicon-learning-question/1"
SCHEMA = """CREATE TABLE IF NOT EXISTS learning_requests (
 archive_sha256 TEXT PRIMARY KEY, payload TEXT NOT NULL)"""


def initialize(conn):
    conn.execute(CONTEXT_SCHEMA)
    conn.execute(SCHEMA)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _literal_digest(value):
    """Hash the original wire fields without normalizing namespace spelling."""
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def archive_request(conn, payload, schema, transport):
    from .residual import _request_id

    if type(payload) is not dict or type(schema) is not dict or type(transport) is not str or not transport.strip():
        raise ValueError("INVALID_LEARNING_QUESTION")
    literal = _literal_digest(payload)
    packed = store_request_context(conn, payload)
    restored = restore_request_context(conn, packed, VERSION)
    fallback = None
    if _literal_digest(restored) != literal:
        # The receipt store shares equivalent pre/post-rename fields. Preserve
        # the exact original payload only for this rare literal collision.
        if _context_digest(restored) != _context_digest(payload):
            raise ValueError("LEARNING_QUESTION_CONTEXT_CHANGED")
        fallback = _store_context(conn, {"literal_sha256": literal, "request": payload})
    record = {
        "format": FORMAT,
        "request_id": _request_id(payload),
        "transport": transport,
        "schema": schema,
        "context_version": VERSION,
        "request": packed,
        "literal_sha256": literal,
        "literal_fallback": fallback,
    }
    identity, encoded = _literal_digest(record), _json(record)
    previous = conn.execute("SELECT payload FROM learning_requests WHERE archive_sha256=?", (identity,)).fetchone()
    if previous is not None and previous[0] != encoded:
        raise ValueError("LEARNING_QUESTION_HASH_COLLISION")
    conn.execute("INSERT OR IGNORE INTO learning_requests VALUES (?,?)", (identity, encoded))
    read_request(conn, identity)
    return identity


def read_request(conn, identity):
    from .residual import _request_id

    if type(identity) is not str or len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("INVALID_LEARNING_QUESTION_REFERENCE")
    row = conn.execute("SELECT payload FROM learning_requests WHERE archive_sha256=?", (identity,)).fetchone()
    if row is None:
        raise ValueError("MISSING_LEARNING_QUESTION")
    try:
        record = json.loads(row[0])
    except json.JSONDecodeError:
        raise ValueError("INVALID_LEARNING_QUESTION_ARCHIVE") from None
    if _literal_digest(record) != identity:
        raise ValueError("LEARNING_QUESTION_HASH_MISMATCH")
    required = {
        "format",
        "request_id",
        "transport",
        "schema",
        "context_version",
        "request",
        "literal_sha256",
        "literal_fallback",
    }
    if (
        type(record) is not dict
        or record.keys() != required
        or current_id(record["format"]) != FORMAT
        or current_id(record["context_version"]) not in {CONTEXT_VERSION, VERSION}
    ):
        raise ValueError("INVALID_LEARNING_QUESTION_ARCHIVE")
    restored = restore_request_context(conn, record["request"], record["context_version"])
    request = restored
    if record["literal_fallback"] is not None:
        fallback = _read_context(conn, record["literal_fallback"])
        if (
            type(fallback) is not dict
            or fallback.keys() != {"literal_sha256", "request"}
            or fallback["literal_sha256"] != record["literal_sha256"]
        ):
            raise ValueError("INVALID_LEARNING_QUESTION_LITERAL_CONTEXT")
        request = fallback["request"]
        if _context_digest(restored) != _context_digest(request):
            raise ValueError("LEARNING_QUESTION_CONTEXT_CHANGED")
    if _literal_digest(request) != record["literal_sha256"] or _request_id(request) != record["request_id"]:
        raise ValueError("LEARNING_QUESTION_ORIGINAL_FIELDS_CHANGED")
    return {**record, "request": request}
