"""Snapshot retirement preserves unique evidence and consumes its handle decision."""

import gzip
import json
import sqlite3

import pytest

from GSE.curation.lexicon_builder import retention


@pytest.fixture
def snapshots(tmp_path, monkeypatch):
    source, active, previous = (tmp_path / name for name in ("source.db", "active.db", "previous.db"))
    for path in (source, active):
        with sqlite3.connect(path) as c:
            c.executescript("""
                CREATE TABLE source_observations(record_id TEXT PRIMARY KEY,entry_id TEXT,source TEXT,family TEXT,scope TEXT,payload TEXT);
                CREATE TABLE lexemes(id INTEGER PRIMARY KEY,lemma TEXT,pos TEXT,sense_id TEXT,gloss TEXT,source TEXT);
                CREATE TABLE definition_states(entry_id TEXT PRIMARY KEY,lexeme_id INTEGER);
                CREATE TABLE receipts(id TEXT PRIMARY KEY,payload TEXT);
            """)
    with sqlite3.connect(source) as c:
        c.execute("INSERT INTO receipts VALUES ('unique','original audit')")
    previous.write_bytes(b"rollback")
    monkeypatch.setattr(retention, "resolve_lexicon_path", lambda: active)
    return source, active, previous, {
        "expected_sha256": retention._fingerprint(active), "archive_path": tmp_path / "audit.json.gz",
        "previous_sha256": retention._fingerprint(previous),
        "receipt_path": tmp_path / "retirement.json", "handle_check": lambda path: {"code": "NO_OPEN_LOCAL_FILE_MATCHES"},
    }


def test_retirement_preserves_audits_and_replays_its_receipt(snapshots):
    source, active, previous, kwargs = snapshots
    receipt = retention.retire_snapshot(source, active, previous, **kwargs)
    assert not source.exists() and active.exists() and previous.read_bytes() == b"rollback"
    assert receipt["unique_audit_rows"] == {"receipts": 1}
    document = json.loads(gzip.decompress(kwargs["archive_path"].read_bytes()))
    assert document["tables"]["receipts"]["rows"] == [["unique", "original audit"]]
    assert retention.retire_snapshot(source, active, previous, **kwargs) == receipt


@pytest.mark.parametrize("index", [1, 2])
def test_retirement_protects_active_and_previous(snapshots, index):
    _, active, previous, kwargs = snapshots
    source = snapshots[index]
    with pytest.raises(ValueError, match="RETIREMENT_PROTECTS_ACTIVE_AND_ROLLBACK"):
        retention.retire_snapshot(source, active, previous, **kwargs)
    assert source.exists()


@pytest.mark.parametrize("decision", [None, False, {}, {"code": "BUSY"}])
def test_retirement_requires_a_named_positive_handle_decision(snapshots, decision):
    source, active, previous, kwargs = snapshots
    kwargs["handle_check"] = lambda path: decision
    with pytest.raises(ValueError, match="RETIREMENT_NO_OPEN_HANDLES_NOT_ESTABLISHED"):
        retention.retire_snapshot(source, active, previous, **kwargs)
    assert source.exists()


def test_retirement_closes_readers_before_handle_instrument(snapshots, monkeypatch):
    source, active, previous, kwargs = snapshots
    connect = sqlite3.connect
    opened = []

    def tracked(*args, **options):
        connection = connect(*args, **options)
        opened.append(connection)
        return connection

    def closed(path):
        assert len(opened) == 2
        for c in opened:
            with pytest.raises(sqlite3.ProgrammingError):
                c.execute("SELECT 1")
        return {"code": "NO_OPEN_LOCAL_FILE_MATCHES"}

    monkeypatch.setattr(retention.sqlite3, "connect", tracked)
    kwargs["handle_check"] = closed
    retention.retire_snapshot(source, active, previous, **kwargs)


def test_retirement_allows_only_named_new_context_records(snapshots):
    source, active, previous, kwargs = snapshots
    with sqlite3.connect(active) as c:
        c.execute("INSERT INTO source_observations VALUES ('new-context','d','s','f','lexical','{}')")
    kwargs["expected_sha256"] = retention._fingerprint(active)
    with pytest.raises(ValueError, match="RETIREMENT_SOURCE_STREAM_MISMATCH"):
        retention.retire_snapshot(source, active, previous, **kwargs)
    assert source.exists()
    result = retention.retire_snapshot(source, active, previous, **kwargs, new_context_ids=("new-context",))
    assert result["code"] == "SOURCE_AND_UNIQUE_AUDITS_PRESERVED_SNAPSHOT_RETIRED"


def test_retirement_refuses_changed_old_sources_even_with_new_context_allowance(snapshots):
    source, active, previous, kwargs = snapshots
    for path in (source, active):
        with sqlite3.connect(path) as c:
            c.execute("INSERT INTO source_observations VALUES ('old','d','s','f','lexical',?)", (path.name,))
    kwargs["expected_sha256"] = retention._fingerprint(active)
    with pytest.raises(ValueError, match="RETIREMENT_SOURCE_STREAM_MISMATCH"):
        retention.retire_snapshot(source, active, previous, **kwargs, new_context_ids=("new-context",))
    assert source.exists()


def test_retirement_preserves_a_snapshot_with_a_sidecar(snapshots):
    source, active, previous, kwargs = snapshots

    def sidecar(path):
        path.with_name(path.name + "-journal").touch()
        return {"code": "NO_OPEN_LOCAL_FILE_MATCHES"}

    kwargs["handle_check"] = sidecar
    with pytest.raises(ValueError, match="RETIREMENT_HAS_SIDECAR"):
        retention.retire_snapshot(source, active, previous, **kwargs)
    assert source.exists()


def test_retirement_requires_an_intact_rollback(snapshots):
    source, active, previous, kwargs = snapshots
    previous.write_bytes(b"changed")
    with pytest.raises(ValueError, match="RETIREMENT_ROLLBACK_MISSING_OR_CHANGED"):
        retention.retire_snapshot(source, active, previous, **kwargs)
    assert source.exists() and not kwargs["archive_path"].exists()


def test_retirement_recovers_after_unlink_before_final_receipt(snapshots, monkeypatch):
    source, active, previous, kwargs = snapshots
    original = retention.record

    def fail_final(path, document):
        if path == kwargs["receipt_path"]:
            raise OSError("interrupted after unlink")
        original(path, document)

    monkeypatch.setattr(retention, "record", fail_final)
    with pytest.raises(OSError, match="interrupted after unlink"):
        retention.retire_snapshot(source, active, previous, **kwargs)
    assert not source.exists() and not kwargs["receipt_path"].exists()
    monkeypatch.setattr(retention, "record", original)
    result = retention.retire_snapshot(source, active, previous, **kwargs)
    assert result["code"] == "SOURCE_AND_UNIQUE_AUDITS_PRESERVED_SNAPSHOT_RETIRED"
    assert json.loads(kwargs["receipt_path"].read_text()) == result


def test_retirement_refuses_missing_source_without_a_verified_intent(snapshots):
    source, active, previous, kwargs = snapshots
    source.unlink()
    with pytest.raises(ValueError, match="RETIREMENT_ABSENT_WITHOUT_VERIFIED_INTENT"):
        retention.retire_snapshot(source, active, previous, **kwargs)
