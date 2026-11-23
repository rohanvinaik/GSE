"""Preserve unique working-snapshot audits against retained release 019.

This command prepares archives only. It never deletes a database.
"""

import argparse
import gzip
import json
import sqlite3
from hashlib import file_digest, sha256
from pathlib import Path

from gse.curation.lexicon_builder.epoch import read, record

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/coherence-020"
TARGETS = {
    "epoch-01-teaching": WORK / "zipf/epoch-01/teaching.db",
    "epoch-01-candidate": WORK / "zipf/epoch-01/candidate.db",
    "epoch-02-teaching": WORK / "zipf/epoch-02/teaching.db",
}
DERIVED_OR_VERIFIED = {
    "definition_states", "primitive_values", "sentence_primitive_values",
    "source_observations", "sqlite_sequence",
}
STREAMS = {
    "native_observations": "SELECT record_id,entry_id,source,family,scope,payload FROM source_observations ORDER BY record_id",
    "definitions": "SELECT d.entry_id,l.lemma,l.pos,l.sense_id,l.gloss,l.source "
    "FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id ORDER BY d.entry_id",
}


def fingerprint(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def identity(path):
    stat = path.stat()
    return {"device": stat.st_dev, "inode": stat.st_ino, "logical_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def stream_fingerprint(connection, query):
    digest, count = sha256(), 0
    for row in connection.execute(query):
        value = json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def prepare(label):
    source = TARGETS[label]
    lineage = read(NOTES / "020-retirement-preparation.json")
    witness = Path(lineage["witness"])
    if source.is_symlink() or not source.is_file() or fingerprint(witness) != lineage["witness_sha256"]:
        raise ValueError("CHECKPOINT_ARCHIVE_SOURCE_OR_WITNESS_INVALID")
    before, digest = identity(source), fingerprint(source)
    expected = lineage["prepared"][0]["source_data_checks"]
    checks, tables = {}, {}
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA cache_size=-32768")
        for name, query in STREAMS.items():
            observed = stream_fingerprint(connection, query)
            if observed != expected[name]["witness"]:
                raise ValueError("CHECKPOINT_ARCHIVE_SOURCE_STREAM_DIFFERS:" + name)
            checks[name] = {"code": "EXACT_STREAM_HASH_EQUAL", **observed}
            print("CHECKPOINT_SOURCE_VERIFIED", label, name, observed["rows"], flush=True)
        connection.execute("ATTACH DATABASE ? AS retained", (f"file:{witness}?mode=ro",))
        names = [row[0] for row in connection.execute("SELECT name FROM main.sqlite_master WHERE type='table' ORDER BY name")]
        for name in names:
            if name in DERIVED_OR_VERIFIED:
                continue
            table = '"' + name.replace('"', '""') + '"'
            columns = [row[1] for row in connection.execute("PRAGMA main.table_info(" + table + ")")]
            if columns != [row[1] for row in connection.execute("PRAGMA retained.table_info(" + table + ")")]:
                raise ValueError("CHECKPOINT_ARCHIVE_SCHEMA_DIFFERS:" + name)
            fields = ",".join('"' + column.replace('"', '""') + '"' for column in columns)
            rows = connection.execute(
                "SELECT " + fields + " FROM main." + table + " EXCEPT SELECT " + fields + " FROM retained." + table
            ).fetchall()
            if rows:
                tables[name] = {"columns": columns, "rows": rows}
    document = {
        "format": "gse.checkpoint-audit-delta/1", "source": str(source), "source_sha256": digest,
        "witness": str(witness), "witness_sha256": lineage["witness_sha256"],
        "scope": "All source and definition identity streams match retained 019; archive every unique row outside reproducible bank projections.",
        "source_data_checks": checks, "derived_or_verified_tables": sorted(DERIVED_OR_VERIFIED), "tables": tables,
    }
    archive = witness.parent / "ssl-explicit-genera/retired-audit" / ("020-" + label + "-audit-delta.json.gz")
    archive.write_bytes(gzip.compress(json.dumps(document, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    if json.loads(gzip.decompress(archive.read_bytes())) != json.loads(json.dumps(document)) or identity(source) != before:
        raise ValueError("CHECKPOINT_ARCHIVE_ROUNDTRIP_OR_SOURCE_CHANGED")
    result = {
        "format": "gse.retirement-preparation/1", "code": "WORK_AUDITS_PRESERVED_NO_CHECKPOINT_REMOVED",
        "path": str(source), "sha256": digest, **before, "witness": str(witness),
        "witness_sha256": lineage["witness_sha256"], "audit_delta": str(archive),
        "audit_delta_sha256": sha256(archive.read_bytes()).hexdigest(),
        "retired_only_row_counts": {table: len(data["rows"]) for table, data in tables.items()},
        "source_data_checks": checks,
    }
    record(NOTES / ("020-" + label + "-retirement-preparation.json"), result)
    print("WORK_AUDIT_ARCHIVE_READY", label, result["retired_only_row_counts"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", choices=tuple(TARGETS))
    prepare(parser.parse_args().label)
