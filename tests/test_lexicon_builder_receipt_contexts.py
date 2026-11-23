"""Lossless receipt context sharing, rollback, integrity, and old-format reads."""

import copy
import json
from dataclasses import asdict

import pytest

from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.model_receipts import (
    CONTEXT_VERSION,
    LEGACY_REQUEST_STORAGE,
    LEGACY_VERSION,
    VERSION,
    _context_digest,
    _store_context,
    append_model_receipt,
    migrate_model_receipts,
    read_model_receipts,
    reset_model_receipts,
)
from GSE.curation.lexicon_builder.storage import _json, open_build


def _receipt(bank, ordinal=0):
    request_id = f"fixture:{bank}:{ordinal}"
    return {
        "entry_id": "definition:1",
        "assertion": asdict(Assertion(bank, 1, "model:fixture", request_id, "model")),
        "request_id": request_id,
        "code": "ASSIGNED",
        "schema": {"type": "object", "properties": {bank: {"enum": [-1, 0, 1, None]}}},
        "request": {
            "format": "gse.bank-request/2",
            "bank": bank,
            "observations": [{"source": "native", "features": {"full_context": "unaltered source " * 4096}}],
            "definition": {"entry_id": "definition:1", "definition": "Native meaning."},
            "scaffold": {
                "context": {"pos": "noun"},
                "relations": [{"id": "relation", "rows": [[-1, 0], [1, 1]]}],
                "domains": {bank: [-1, 0, 1]},
                "proof_trace": [],
            },
            "future_field": {"preserve": [False, None, "", 0, -1, 1]},
        },
    }


@pytest.fixture
def connection(tmp_path):
    conn = open_build(tmp_path / "receipts.db")
    with conn:
        reset_model_receipts(conn)
    yield conn
    conn.close()


def test_56_bank_receipts_store_observations_once_and_reconstruct_exactly(connection):
    originals = [_receipt(bank) for bank in BANKS]
    unchanged = copy.deepcopy(originals)
    with connection:
        for record in originals:
            append_model_receipt(connection, record)
    assert originals == unchanged
    reconstructed = read_model_receipts(connection)["definition:1"]
    assert list(reconstructed) == originals
    rows = connection.execute("SELECT payload FROM model_receipt_contexts").fetchall()
    assert sum(_json(originals[0]["request"]["observations"]) == row[0] for row in rows) == 1
    persisted = sum(len(row[0]) for row in rows) + sum(
        len(row[0]) for row in connection.execute("SELECT payload FROM accepted_model_receipts")
    )
    assert persisted < sum(len(_json(record)) for record in originals) / 10
    # Returned requests must be independent, despite sharing storage.
    reconstructed[0]["request"]["observations"][0]["features"]["full_context"] = "changed by caller"
    assert reconstructed[1] == originals[1]
    assert read_model_receipts(connection)["definition:1"][0] == originals[0]


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing", "MISSING_MODEL_RECEIPT_CONTEXT"),
        ("tamper", "MODEL_RECEIPT_CONTEXT_HASH_MISMATCH"),
        ("table", "MISSING_MODEL_RECEIPT_CONTEXT_TABLE"),
        ("duplicate", "DUPLICATE_MODEL_RECEIPT_CONTEXT"),
    ],
)
def test_reconstruction_loads_and_checks_full_context(connection, case, code):
    with connection:
        append_model_receipt(connection, _receipt("WANT"))
    stored = json.loads(connection.execute("SELECT payload FROM accepted_model_receipts").fetchone()[0])
    digest = stored["request"]["contexts"]["observations"]
    with connection:
        if case == "missing":
            connection.execute("DELETE FROM model_receipt_contexts WHERE context_sha256=?", (digest,))
        elif case == "tamper":
            connection.execute("UPDATE model_receipt_contexts SET payload='[]' WHERE context_sha256=?", (digest,))
        elif case == "table":
            connection.execute("DROP TABLE model_receipt_contexts")
        else:
            connection.execute("ALTER TABLE model_receipt_contexts RENAME TO old_contexts")
            connection.execute("CREATE TABLE model_receipt_contexts AS SELECT * FROM old_contexts")
            connection.execute("INSERT INTO model_receipt_contexts SELECT * FROM old_contexts")
    with pytest.raises(ValueError, match=f"^{code}$"):
        read_model_receipts(connection)


def test_failed_append_rolls_back_shared_context_and_receipt_together(connection):
    with pytest.raises(RuntimeError, match="rollback"), connection:
        append_model_receipt(connection, _receipt("WANT"))
        raise RuntimeError("rollback")
    assert connection.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM model_receipt_contexts").fetchone()[0] == 0


def test_indexed_v1_receipts_read_and_migrate_without_request_changes(connection):
    record = _receipt("WANT")
    record["request"]["format"] = "gse.bank-request/1"
    record["request"].pop("scaffold")
    with connection:
        connection.execute("DROP TABLE model_receipt_contexts")
        connection.execute(
            "UPDATE builder_metadata SET value=? WHERE key='model_receipts_format'", (_json(LEGACY_VERSION),)
        )
        connection.execute(
            "INSERT INTO accepted_model_receipts VALUES (?,?,?,?)",
            (record["entry_id"], 0, record["request_id"], _json(record)),
        )
    assert read_model_receipts(connection)["definition:1"] == (record,)
    with connection:
        migrate_model_receipts(connection)
    assert read_model_receipts(connection)["definition:1"] == (record,)
    assert (
        json.loads(
            connection.execute("SELECT value FROM builder_metadata WHERE key='model_receipts_format'").fetchone()[0]
        )
        == VERSION
    )
    with connection:
        migrate_model_receipts(connection)
    assert connection.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0] == 1


def test_indexed_v1_migration_rollback_preserves_old_authority(connection, monkeypatch):
    from GSE.curation.lexicon_builder import model_receipts

    record = _receipt("WANT")
    with connection:
        connection.execute("DROP TABLE model_receipt_contexts")
        connection.execute(
            "UPDATE builder_metadata SET value=? WHERE key='model_receipts_format'", (_json(LEGACY_VERSION),)
        )
        connection.execute(
            "INSERT INTO accepted_model_receipts VALUES (?,?,?,?)",
            (record["entry_id"], 0, record["request_id"], _json(record)),
        )
    original = model_receipts._stored_receipt

    def fail_after_context(*args):
        original(*args)
        raise OSError("migration interrupted")

    monkeypatch.setattr(model_receipts, "_stored_receipt", fail_after_context)
    with pytest.raises(OSError, match="interrupted"), connection:
        migrate_model_receipts(connection)
    assert read_model_receipts(connection)["definition:1"] == (record,)
    assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='model_receipt_contexts'").fetchone() is None


def test_persisted_reference_cannot_override_inline_field(connection):
    with connection:
        append_model_receipt(connection, _receipt("WANT"))
        row = json.loads(connection.execute("SELECT payload FROM accepted_model_receipts").fetchone()[0])
        row["request"]["inline"]["observations"] = []
        connection.execute("UPDATE accepted_model_receipts SET payload=?", (_json(row),))
    with pytest.raises(ValueError, match="MODEL_RECEIPT_CONTEXT_FIELD_COLLISION"):
        read_model_receipts(connection)


def _proof_record(index):
    return {"kind": "FIXTURE_PROOF", "ordinal": index, "evidence": "Unchanged proof provenance. " * 128}


def test_evolving_56_bank_traces_intern_each_record_and_preserve_order(connection):
    originals = []
    proof = []
    with connection:
        for index, bank in enumerate(BANKS):
            proof.append(_proof_record(index))
            record = _receipt(bank)
            # Repeated records are intentional: retain both multiplicity and order.
            record["request"]["scaffold"]["proof_trace"] = [*proof, proof[0]]
            originals.append(record)
            append_model_receipt(connection, record)
    restored = read_model_receipts(connection)["definition:1"]
    assert list(restored) == originals
    assert [_context_digest(record["request"]) for record in restored] == [
        _context_digest(record["request"]) for record in originals
    ]
    payloads = [row[0] for row in connection.execute("SELECT payload FROM model_receipt_contexts")]
    assert all(payloads.count(_json(record)) == 1 for record in proof)
    assert all(_json(record["request"]["scaffold"]["proof_trace"]) not in payloads for record in originals)


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing", "MISSING_MODEL_RECEIPT_CONTEXT"),
        ("tampered_record", "MODEL_RECEIPT_CONTEXT_HASH_MISMATCH"),
        ("reordered", "MODEL_RECEIPT_PROOF_TRACE_HASH_MISMATCH"),
        ("omitted_duplicate", "MODEL_RECEIPT_PROOF_TRACE_HASH_MISMATCH"),
        ("bad_trace_hash", "MODEL_RECEIPT_PROOF_TRACE_HASH_MISMATCH"),
    ],
)
def test_proof_records_and_order_are_verified(connection, case, code):
    record = _receipt("WANT")
    record["request"]["scaffold"]["proof_trace"] = [_proof_record(0), _proof_record(1), _proof_record(0)]
    with connection:
        append_model_receipt(connection, record)
    stored = json.loads(connection.execute("SELECT payload FROM accepted_model_receipts").fetchone()[0])
    reference = stored["request"]["scaffold"]["proof_trace"]
    digest = reference["record_sha256s"][0]
    with connection:
        if case == "missing":
            connection.execute("DELETE FROM model_receipt_contexts WHERE context_sha256=?", (digest,))
        elif case == "tampered_record":
            connection.execute("UPDATE model_receipt_contexts SET payload='{}' WHERE context_sha256=?", (digest,))
        else:
            if case == "reordered":
                references = reference["record_sha256s"]
                references[0], references[1] = references[1], references[0]
            elif case == "omitted_duplicate":
                reference["record_sha256s"].pop()
            else:
                reference["trace_sha256"] = "0" * 64
            connection.execute("UPDATE accepted_model_receipts SET payload=?", (_json(stored),))
    with pytest.raises(ValueError, match=f"^{code}$"):
        read_model_receipts(connection)


def _write_v2_receipt(conn, record):
    request = dict(record["request"])
    contexts = {key: _store_context(conn, request.pop(key)) for key in ("observations", "definition")}
    scaffold = {key: _store_context(conn, value) for key, value in request.pop("scaffold").items()}
    packed = {
        **record,
        "request": {"format": LEGACY_REQUEST_STORAGE, "inline": request, "contexts": contexts, "scaffold": scaffold},
    }
    conn.execute("UPDATE builder_metadata SET value=? WHERE key='model_receipts_format'", (_json(CONTEXT_VERSION),))
    conn.execute(
        "INSERT INTO accepted_model_receipts VALUES (?,?,?,?)",
        (record["entry_id"], 0, record["request_id"], _json(packed)),
    )
    return scaffold["proof_trace"]


def test_v2_trace_blob_reads_and_migrates_without_retaining_duplicate_payload(connection):
    record = _receipt("WANT")
    record["request"]["scaffold"]["proof_trace"] = [_proof_record(0), _proof_record(1), _proof_record(0)]
    with connection:
        old_trace = _write_v2_receipt(connection, record)
    assert read_model_receipts(connection)[record["entry_id"]] == (record,)
    with connection:
        migrate_model_receipts(connection)
    assert read_model_receipts(connection)[record["entry_id"]] == (record,)
    assert (
        connection.execute("SELECT 1 FROM model_receipt_contexts WHERE context_sha256=?", (old_trace,)).fetchone()
        is None
    )
    for proof in record["request"]["scaffold"]["proof_trace"]:
        assert connection.execute(
            "SELECT payload FROM model_receipt_contexts WHERE context_sha256=?", (_context_digest(proof),)
        ).fetchone()[0] == _json(proof)


def test_v2_proof_migration_failure_rolls_back_all_new_records(connection, monkeypatch):
    from GSE.curation.lexicon_builder import model_receipts

    record = _receipt("WANT")
    record["request"]["scaffold"]["proof_trace"] = [_proof_record(0)]
    with connection:
        _write_v2_receipt(connection, record)
    before = connection.execute("SELECT * FROM model_receipt_contexts ORDER BY context_sha256").fetchall()
    original = model_receipts._prune_unreferenced_contexts

    def fail_after_prune(conn):
        original(conn)
        raise OSError("proof migration interrupted")

    monkeypatch.setattr(model_receipts, "_prune_unreferenced_contexts", fail_after_prune)
    with pytest.raises(OSError, match="interrupted"), connection:
        migrate_model_receipts(connection)
    assert read_model_receipts(connection)[record["entry_id"]] == (record,)
    assert connection.execute("SELECT * FROM model_receipt_contexts ORDER BY context_sha256").fetchall() == before


def test_full_56_bank_completion_replays_with_interned_proof_records(tmp_path):
    from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle
    from GSE.curation.lexicon_builder.pipeline import build_dictionary
    from GSE.curation.lexicon_builder.validation import validate_build

    path = tmp_path / "full-fixture.db"
    definition = Definition("fixture:storage", "storage-fixture", "synthetic", "Storage fixture, not linguistic gold.")
    report = build_dictionary(
        EvidenceBundle((definition,), (), (), ()),
        path,
        transport=lambda payload, schema: json.dumps({payload["bank"]: 0}),
        max_model_calls=len(BANKS),
    )
    assert report["model_calls"] == len(BANKS)
    assert report["outcomes"] == {"RESOLVED": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
