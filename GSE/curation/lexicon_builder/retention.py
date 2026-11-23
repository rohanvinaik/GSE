"""Retire a generated snapshot only after preserving its sources and unique audits."""

import gzip
import json
import os
import sqlite3
from contextlib import closing
from hashlib import file_digest, sha256
from pathlib import Path

from GSE.lexicon_resource import resolve_lexicon_path

from .epoch import record

_DERIVED = frozenset({
    "definition_states", "primitive_values", "sentence_primitive_values", "source_observations", "sqlite_sequence",
})
_STREAMS = {
    "native_observations": "SELECT record_id,entry_id,source,family,scope,payload FROM source_observations ORDER BY record_id",
    "definitions": "SELECT d.entry_id,l.lemma,l.pos,l.sense_id,l.gloss,l.source "
    "FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id ORDER BY d.entry_id",
}


def _fingerprint(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _identity(path):
    stat = path.stat()
    return {"device": stat.st_dev, "inode": stat.st_ino, "logical_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _stream(connection, query, parameters=()):
    digest, count = sha256(), 0
    for row in connection.execute(query, parameters):
        payload = json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def retire_snapshot(source, active, previous, *, expected_sha256, previous_sha256, archive_path, receipt_path,
                    handle_check, new_context_ids=()):
    """Preserve complete native streams and every unique non-derived row.

    ``new_context_ids`` names separately audited context additions in the active
    successor. A record absent from the retired snapshot may be omitted from the
    witness comparison only when explicitly named here. No old source may vanish.
    The caller supplies the established local-file handle instrument; its named
    positive result is required before unlinking. Active and rollback are protected.
    """
    source, active, previous = (Path(path).absolute() for path in (source, active, previous))
    archive_path, receipt_path = Path(archive_path), Path(receipt_path)
    if source.is_symlink() or source.resolve() in {active.resolve(), previous.resolve()}:
        raise ValueError("RETIREMENT_PROTECTS_ACTIVE_AND_ROLLBACK")
    if resolve_lexicon_path().resolve() != active.resolve() or _fingerprint(active) != expected_sha256:
        raise ValueError("RETIREMENT_ACTIVE_WITNESS_CHANGED")
    if previous.is_symlink() or not previous.is_file() or _fingerprint(previous) != previous_sha256:
        raise ValueError("RETIREMENT_ROLLBACK_MISSING_OR_CHANGED")
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if (source.exists() or receipt["path"] != str(source) or receipt["witness_sha256"] != expected_sha256
                or receipt["witness"] != str(active) or receipt["previous_sha256"] != previous_sha256):
            raise ValueError("RETIREMENT_RECEIPT_IDENTITY_CHANGED")
        if _fingerprint(Path(receipt["audit_archive"])) != receipt["archive_sha256"]:
            raise ValueError("RETIREMENT_ARCHIVE_CHANGED")
        return receipt
    intent_path = receipt_path.with_suffix(".intent.json")
    if not source.exists():
        if not intent_path.exists():
            raise ValueError("RETIREMENT_ABSENT_WITHOUT_VERIFIED_INTENT")
        intent = json.loads(intent_path.read_text())
        if (intent.get("code") != "SNAPSHOT_RETIREMENT_READY" or intent.get("path") != str(source)
                or intent.get("witness_sha256") != expected_sha256
                or intent.get("previous_sha256") != previous_sha256
                or intent.get("audit_archive") != str(archive_path)
                or _fingerprint(archive_path) != intent.get("archive_sha256")):
            raise ValueError("RETIREMENT_INTERRUPTED_INTENT_MISMATCH")
        result = {**intent, "code": "SOURCE_AND_UNIQUE_AUDITS_PRESERVED_SNAPSHOT_RETIRED"}
        record(receipt_path, result)
        return result
    if (not isinstance(new_context_ids, tuple) or len(set(new_context_ids)) != len(new_context_ids)
            or any(type(identity) is not str or not identity for identity in new_context_ids)):
        raise ValueError("RETIREMENT_INVALID_NEW_CONTEXT_IDENTITIES")
    before, source_hash = _identity(source), _fingerprint(source)
    checks, tables = {}, {}
    with closing(sqlite3.connect(source.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as old, closing(
        sqlite3.connect(active.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    ) as witness:
        old.execute("PRAGMA query_only=ON")
        witness.execute("PRAGMA query_only=ON")
        missing = tuple(identity for identity in new_context_ids
                        if not old.execute("SELECT 1 FROM source_observations WHERE record_id=?", (identity,)).fetchone())
        for name, query in _STREAMS.items():
            target, parameters = query, ()
            if name == "native_observations" and missing:
                target = query.replace(" ORDER BY record_id", " WHERE record_id NOT IN ("
                                       + ",".join("?" for _ in missing) + ") ORDER BY record_id")
                parameters = missing
            observed = _stream(old, query)
            if observed != _stream(witness, target, parameters):
                raise ValueError("RETIREMENT_SOURCE_STREAM_MISMATCH:" + name)
            checks[name] = observed
        old.execute("ATTACH DATABASE ? AS retained", (active.resolve().as_uri() + "?mode=ro",))
        for (name,) in old.execute("SELECT name FROM main.sqlite_master WHERE type='table' ORDER BY name").fetchall():
            if name in _DERIVED:
                continue
            table = '"' + name.replace('"', '""') + '"'
            columns = [row[1] for row in old.execute("PRAGMA main.table_info(" + table + ")")]
            if columns != [row[1] for row in old.execute("PRAGMA retained.table_info(" + table + ")")]:
                raise ValueError("RETIREMENT_SCHEMA_MISMATCH:" + name)
            fields = ",".join('"' + column.replace('"', '""') + '"' for column in columns)
            rows = old.execute("SELECT " + fields + " FROM main." + table
                               + " EXCEPT SELECT " + fields + " FROM retained." + table).fetchall()
            if rows:
                tables[name] = {"columns": columns, "rows": rows}
    document = {
        "format": "GSE.checkpoint-audit-delta/1", "source": str(source), "source_sha256": source_hash,
        "witness": str(active), "witness_sha256": expected_sha256, "source_identity": before,
        "source_data_checks": checks,
        "excluded_new_context_ids_from_witness_only": list(missing), "tables": tables,
        "derived_or_verified_tables": sorted(_DERIVED),
    }
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False).encode()
    if archive_path.exists():
        if gzip.decompress(archive_path.read_bytes()) != encoded:
            raise ValueError("RETIREMENT_EXISTING_ARCHIVE_DIFFERS")
    else:
        with archive_path.open("xb") as stream:
            stream.write(gzip.compress(encoded, mtime=0))
            stream.flush()
            os.fsync(stream.fileno())
    if json.loads(gzip.decompress(archive_path.read_bytes())) != json.loads(encoded):
        raise ValueError("RETIREMENT_ARCHIVE_ROUNDTRIP_FAILED")
    handles = handle_check(source)
    if not isinstance(handles, dict) or handles.get("code") != "NO_OPEN_LOCAL_FILE_MATCHES":
        raise ValueError("RETIREMENT_NO_OPEN_HANDLES_NOT_ESTABLISHED")
    if _identity(source) != before or _fingerprint(source) != source_hash:
        raise ValueError("RETIREMENT_SOURCE_CHANGED")
    if any(Path(str(source) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("RETIREMENT_HAS_SIDECAR")
    if resolve_lexicon_path().resolve() != active.resolve() or _fingerprint(active) != expected_sha256:
        raise ValueError("RETIREMENT_ACTIVE_WITNESS_CHANGED")
    if _fingerprint(previous) != previous_sha256:
        raise ValueError("RETIREMENT_ROLLBACK_MISSING_OR_CHANGED")
    result = {
        "code": "SOURCE_AND_UNIQUE_AUDITS_PRESERVED_SNAPSHOT_RETIRED", "path": str(source),
        "sha256": source_hash, "identity": before, "witness": str(active), "witness_sha256": expected_sha256,
        "previous_sha256": previous_sha256,
        "audit_archive": str(archive_path), "archive_sha256": _fingerprint(archive_path),
        "unique_audit_rows": {name: len(value["rows"]) for name, value in tables.items()}, "handle_check": handles,
    }
    record(intent_path, {**result, "code": "SNAPSHOT_RETIREMENT_READY"})
    source.unlink()
    record(receipt_path, result)
    return result
