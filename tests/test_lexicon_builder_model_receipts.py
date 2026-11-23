"""Normalized model authority remains exact, lazy, and backward compatible."""

import json
import sqlite3

import pytest

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from gse.curation.lexicon_builder.model_receipts import ModelReceipts, migrate_model_receipts, read_model_receipts
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.validation import validate_build


@pytest.fixture
def modeled(tmp_path):
    path = tmp_path / "model.db"
    bundle = EvidenceBundle(
        (Definition("d", "d", "verb", "fixture"),), (Observation("d", "native", "r", "native", {}, "lexical"),), (), ()
    )
    build_dictionary(
        bundle, path, transport=lambda payload, schema: json.dumps({payload["bank"]: 0}), max_model_calls=1
    )
    return path


def make_legacy(path):
    with sqlite3.connect(path) as conn:
        authority = read_model_receipts(conn)
        records = [record for entry in authority for record in authority[entry]]
        conn.execute("DROP TABLE accepted_model_receipts")
        conn.execute("DROP TABLE model_receipt_contexts")
        conn.execute("DELETE FROM builder_metadata WHERE key='model_receipts_format'")
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='model_completions'", (json.dumps(records),))
    return records


def test_new_build_uses_indexed_rows_and_lazy_entry_loading(modeled):
    with sqlite3.connect(modeled) as conn:
        assert (
            json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='model_completions'").fetchone()[0])
            == []
        )
        models = read_model_receipts(conn)
        assert isinstance(models, ModelReceipts)
        assert set(models) == {"d"}
        trace = []
        conn.set_trace_callback(trace.append)
        assert "d" in models
        assert len(models) == 1
        assert not trace  # Corpus membership tests must not reload request bodies.
        assert models["d"][0]["entry_id"] == "d"
        assert sum("FROM accepted_model_receipts" in statement for statement in trace) == 1
        assert all(
            "FROM accepted_model_receipts" in statement or "FROM model_receipt_contexts" in statement
            for statement in trace
        )  # Only the requested definition and its fully verified context are loaded.
    assert validate_build(modeled)["code"] == "REPLAY_VALIDATED"


def test_legacy_replay_then_one_time_completion_migration(modeled):
    old = make_legacy(modeled)
    assert validate_build(modeled)["code"] == "REPLAY_VALIDATED"
    report = complete_dictionary(
        modeled, lambda payload, schema: json.dumps({payload["bank"]: 1}), 1, entry_ids=("d",), banks=("GOOD",)
    )
    assert report["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(modeled) as conn:
        records = read_model_receipts(conn)["d"]
        assert records[0] == old[0]
        assert len(records) == 2
        assert (
            json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='model_completions'").fetchone()[0])
            == []
        )
        before = conn.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0]
        with conn:
            migrate_model_receipts(conn)
        assert conn.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0] == before
    assert validate_build(modeled)["code"] == "REPLAY_VALIDATED"


def test_migration_failure_rolls_back_schema_rows_and_legacy_authority(modeled, monkeypatch):
    from gse.curation.lexicon_builder import model_receipts

    old = make_legacy(modeled)
    original = model_receipts.append_model_receipt

    def fail_after_insert(*args):
        original(*args)
        raise OSError("fixture migration failure")

    monkeypatch.setattr(model_receipts, "append_model_receipt", fail_after_insert)
    with sqlite3.connect(modeled) as conn:
        with pytest.raises(OSError, match="migration failure"), conn:
            migrate_model_receipts(conn)
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='accepted_model_receipts'").fetchone() is None
        assert (
            json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='model_completions'").fetchone()[0])
            == old
        )
    assert validate_build(modeled)["code"] == "REPLAY_VALIDATED"


def test_nonempty_legacy_authority_cannot_be_shadowed_by_normalized_table(modeled):
    with sqlite3.connect(modeled) as conn:
        raw = json.loads(conn.execute("SELECT payload FROM accepted_model_receipts").fetchone()[0])
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='model_completions'", (json.dumps([raw]),))
    with pytest.raises(ValueError, match="COMPETING_MODEL_RECEIPT_AUTHORITIES"):
        validate_build(modeled)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("ordinal", "INVALID_MODEL_RECEIPT_ORDINAL"),
        ("entry", "COLUMN_PAYLOAD_MISMATCH"),
        ("request_id", "COLUMN_PAYLOAD_MISMATCH"),
        ("format", "UNSUPPORTED_MODEL_RECEIPTS_FORMAT"),
        ("missing_table", "MISSING_MODEL_RECEIPTS_TABLE"),
        ("duplicate", "INVALID_MODEL_RECEIPT_ORDINAL"),
    ],
)
def test_normalized_receipt_integrity_rejects_corruption(modeled, change, reason):
    with sqlite3.connect(modeled) as conn:
        if change == "ordinal":
            conn.execute("UPDATE accepted_model_receipts SET ordinal=2")
        elif change == "entry":
            conn.execute("UPDATE accepted_model_receipts SET entry_id='wrong'")
        elif change == "request_id":
            conn.execute("UPDATE accepted_model_receipts SET request_id='wrong'")
        elif change == "format":
            conn.execute("UPDATE builder_metadata SET value='\"unknown\"' WHERE key='model_receipts_format'")
        elif change == "missing_table":
            conn.execute("DROP TABLE accepted_model_receipts")
        else:
            conn.execute("ALTER TABLE accepted_model_receipts RENAME TO original_receipts")
            conn.execute("CREATE TABLE accepted_model_receipts AS SELECT * FROM original_receipts")
            conn.execute("INSERT INTO accepted_model_receipts SELECT * FROM original_receipts")
    with pytest.raises(ValueError, match=reason):
        validate_build(modeled)


def test_missing_receipt_does_not_authorize_retained_model_assertion(modeled):
    with sqlite3.connect(modeled) as conn:
        conn.execute("DELETE FROM accepted_model_receipts")
    report = validate_build(modeled)
    assert report["code"] == "REPLAY_MISMATCH"
    assert any(item.get("reason") == "ASSERTION_PROVENANCE_MISMATCH" for item in report["mismatches"])


def test_receipt_payload_schema_tampering_is_checked_by_replay(modeled):
    with sqlite3.connect(modeled) as conn:
        receipt = json.loads(conn.execute("SELECT payload FROM accepted_model_receipts").fetchone()[0])
        receipt["schema"]["additionalProperties"] = True
        conn.execute("UPDATE accepted_model_receipts SET payload=?", (json.dumps(receipt),))
    assert validate_build(modeled)["code"] == "REPLAY_MISMATCH"
