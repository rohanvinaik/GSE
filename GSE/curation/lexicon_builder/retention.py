"""Retire a generated snapshot only after preserving its sources and unique audits."""

import gzip
import json
import os
import re
import sqlite3
import subprocess
from contextlib import closing
from hashlib import file_digest, sha256
from pathlib import Path

from GSE.lexicon_resource import resolve_lexicon_path

from .epoch import record

_DERIVED = frozenset(
    {
        "definition_states",
        "primitive_values",
        "sentence_primitive_values",
        "source_observations",
        "sqlite_sequence",
    }
)
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


def no_open_handles(path):
    """Use the existing local-file handle instrument; incomplete scans abstain."""
    result = subprocess.run(["lsof", "-nP", "-f", "-Fpn", "--", str(path)], capture_output=True, text=True)
    if result.returncode != 1 or result.stdout:
        raise ValueError("CHECKPOINT_OPEN_HANDLE_CHECK_FAILED:" + str(path))
    warning = None
    if result.stderr:
        diagnostic = re.fullmatch(
            r"lsof: WARNING: can't stat\(\) smbfs file system (?P<mount>/Volumes/\.timemachine/[^\n]+)\n"
            r'      Output information may be incomplete.\n      assuming "dev=(?P<device>[0-9a-fA-F]+)" from mount table\n',
            result.stderr,
        )
        if diagnostic is None:
            raise ValueError("CHECKPOINT_OPEN_HANDLE_CHECK_FAILED:" + str(path))
        mount = Path(diagnostic["mount"])
        device = int(diagnostic["device"], 16)
        if path.absolute().is_relative_to(mount) or path.stat().st_dev == device:
            raise ValueError("CHECKPOINT_ON_UNINSPECTED_NETWORK_FILESYSTEM")
        warning = {"code": "UNRELATED_INACCESSIBLE_SMB_MOUNT", "path": str(mount), "device": device}
    return {"code": "NO_OPEN_LOCAL_FILE_MATCHES", "stderr": result.stderr, "unrelated_mount": warning}


def _verify_retirement_witness(active, expected_sha256, learning_state):
    if learning_state is None:
        if resolve_lexicon_path().resolve() != active.resolve():
            raise ValueError("RETIREMENT_ACTIVE_WITNESS_CHANGED")
    else:
        head = learning_state.head()
        if Path(head["candidate"]).resolve() != active.resolve() or head["candidate_sha256"] != expected_sha256:
            raise ValueError("RETIREMENT_WORKING_HEAD_CHANGED")
    if _fingerprint(active) != expected_sha256:
        raise ValueError("RETIREMENT_ACTIVE_WITNESS_CHANGED")


def _verify_learning_retirement(source, learning_state):
    """A working-head witness can retire only its ledger's owned phase files."""
    owner = learning_state.path.parent.absolute()
    if source.parent.parent != owner or source.name not in {"teaching.db", "candidate.db"}:
        raise ValueError("RETIREMENT_NOT_OWNED_LEARNING_STAGE")
    if source.parent.is_symlink() or source.parent.name not in {
        f"epoch-{row['epoch']:02d}" for row in learning_state.head_history()
    }:
        raise ValueError("RETIREMENT_NOT_OWNED_LEARNING_STAGE")
    expected = {
        row["path"]: row["sha256"] for transition in learning_state.head_history() for row in transition["staging"]
    }.get(str(source))
    if expected is None or source.exists() and (_fingerprint(source) != expected or source.stat().st_nlink != 1):
        raise ValueError("RETIREMENT_LEARNING_STAGE_CHANGED_OR_ALIASED")
    if source.resolve() == resolve_lexicon_path().resolve():
        raise ValueError("RETIREMENT_PROTECTS_ACTIVE_AND_ROLLBACK")


def _stream(connection, query, parameters=()):
    digest, count = sha256(), 0
    for row in connection.execute(query, parameters):
        payload = json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def retire_learning_stages(learning, opening, opening_sha256):
    """Bound owned phase DBs after a durable head CAS, retaining all audit deltas.

    The opening source remains pinned and is never owned by this operation.
    Historical retirement receipts are self-contained: later heads need not
    preserve the former witness database just to resume an earlier unlink.
    """
    head = learning.head()
    active = Path(head["candidate"]).absolute()
    results = []
    for transition in learning.head_history():
        for stage in transition["staging"]:
            source = Path(stage["path"])
            if source.absolute() == active:
                continue
            receipt_path = source.with_suffix(".retirement.json")
            archive_path = source.with_suffix(".audit.json.gz")
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
                if (
                    source.exists()
                    or receipt.get("path") != str(source.absolute())
                    or receipt.get("sha256") != stage["sha256"]
                    or receipt.get("audit_archive") != str(archive_path)
                    or _fingerprint(archive_path) != receipt.get("archive_sha256")
                ):
                    raise ValueError("LEARNING_RETIREMENT_RECEIPT_CHANGED")
                results.append(receipt)
                continue
            # A crash after unlink leaves an intent whose original witness
            # might be an earlier head. Finish it before starting another epoch.
            results.append(
                retire_snapshot(
                    source,
                    active,
                    opening,
                    expected_sha256=head["candidate_sha256"],
                    previous_sha256=opening_sha256,
                    archive_path=archive_path,
                    receipt_path=receipt_path,
                    handle_check=no_open_handles,
                    learning_state=learning,
                )
            )
    return results


def retire_snapshot(
    source,
    active,
    previous,
    *,
    expected_sha256,
    previous_sha256,
    archive_path,
    receipt_path,
    handle_check,
    new_context_ids=(),
    learning_state=None,
):
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
    if learning_state is not None:
        _verify_learning_retirement(source, learning_state)
    _verify_retirement_witness(active, expected_sha256, learning_state)
    if previous.is_symlink() or not previous.is_file() or _fingerprint(previous) != previous_sha256:
        raise ValueError("RETIREMENT_ROLLBACK_MISSING_OR_CHANGED")
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if (
            source.exists()
            or receipt["path"] != str(source)
            or receipt["witness_sha256"] != expected_sha256
            or receipt["witness"] != str(active)
            or receipt["previous_sha256"] != previous_sha256
        ):
            raise ValueError("RETIREMENT_RECEIPT_IDENTITY_CHANGED")
        if _fingerprint(Path(receipt["audit_archive"])) != receipt["archive_sha256"]:
            raise ValueError("RETIREMENT_ARCHIVE_CHANGED")
        return receipt
    intent_path = receipt_path.with_suffix(".intent.json")
    if not source.exists():
        if not intent_path.exists():
            raise ValueError("RETIREMENT_ABSENT_WITHOUT_VERIFIED_INTENT")
        intent = json.loads(intent_path.read_text())
        if (
            intent.get("code") != "SNAPSHOT_RETIREMENT_READY"
            or intent.get("path") != str(source)
            or intent.get("witness_sha256") != expected_sha256
            or intent.get("previous_sha256") != previous_sha256
            or intent.get("audit_archive") != str(archive_path)
            or _fingerprint(archive_path) != intent.get("archive_sha256")
        ):
            raise ValueError("RETIREMENT_INTERRUPTED_INTENT_MISMATCH")
        result = {**intent, "code": "SOURCE_AND_UNIQUE_AUDITS_PRESERVED_SNAPSHOT_RETIRED"}
        record(receipt_path, result)
        return result
    if (
        not isinstance(new_context_ids, tuple)
        or len(set(new_context_ids)) != len(new_context_ids)
        or any(type(identity) is not str or not identity for identity in new_context_ids)
    ):
        raise ValueError("RETIREMENT_INVALID_NEW_CONTEXT_IDENTITIES")
    before, source_hash = _identity(source), _fingerprint(source)
    checks, tables = {}, {}
    with (
        closing(sqlite3.connect(source.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as old,
        closing(sqlite3.connect(active.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as witness,
    ):
        old.execute("PRAGMA query_only=ON")
        witness.execute("PRAGMA query_only=ON")
        missing = tuple(
            identity
            for identity in new_context_ids
            if not old.execute("SELECT 1 FROM source_observations WHERE record_id=?", (identity,)).fetchone()
        )
        for name, query in _STREAMS.items():
            target, parameters = query, ()
            if name == "native_observations" and missing:
                target = query.replace(
                    " ORDER BY record_id",
                    " WHERE record_id NOT IN (" + ",".join("?" for _ in missing) + ") ORDER BY record_id",
                )
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
            rows = old.execute(
                "SELECT " + fields + " FROM main." + table + " EXCEPT SELECT " + fields + " FROM retained." + table
            ).fetchall()
            if rows:
                tables[name] = {"columns": columns, "rows": rows}
    document = {
        "format": "GSE.checkpoint-audit-delta/1",
        "source": str(source),
        "source_sha256": source_hash,
        "witness": str(active),
        "witness_sha256": expected_sha256,
        "source_identity": before,
        "source_data_checks": checks,
        "excluded_new_context_ids_from_witness_only": list(missing),
        "tables": tables,
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
    _verify_retirement_witness(active, expected_sha256, learning_state)
    if _fingerprint(previous) != previous_sha256:
        raise ValueError("RETIREMENT_ROLLBACK_MISSING_OR_CHANGED")
    result = {
        "code": "SOURCE_AND_UNIQUE_AUDITS_PRESERVED_SNAPSHOT_RETIRED",
        "path": str(source),
        "sha256": source_hash,
        "identity": before,
        "witness": str(active),
        "witness_sha256": expected_sha256,
        "previous_sha256": previous_sha256,
        "audit_archive": str(archive_path),
        "archive_sha256": _fingerprint(archive_path),
        "unique_audit_rows": {name: len(value["rows"]) for name, value in tables.items()},
        "handle_check": handles,
    }
    record(intent_path, {**result, "code": "SNAPSHOT_RETIREMENT_READY"})
    source.unlink()
    record(receipt_path, result)
    return result
