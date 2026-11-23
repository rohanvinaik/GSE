"""Adversarial migration history and filesystem tests on isolated fixtures."""

import json
import sqlite3
import sys

import pytest
from test_lexicon_builder_rule_migration import Transport, packet

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.reconsideration import reconsider
from GSE.curation.lexicon_builder.rule_history import digest, install_history
from GSE.curation.lexicon_builder.rule_migration import migrate_rule
from GSE.curation.lexicon_builder.validation import validate_build


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("rejected_admission", "RULE_ADMISSION_NOT_APPROVED"),
        ("lost_archive", "MISSING_HISTORICAL_MODEL_RECEIPT"),
        ("duplicate_archive", "DUPLICATE_HISTORICAL_MODEL_RECEIPT"),
    ],
)
def test_self_consistent_event_hash_does_not_authorize_broken_history(tmp_path, mutation, reason):
    source, input_path, audit_path, review = packet(tmp_path)
    output = tmp_path / "migrated.db"
    migrate_rule(source, output, input_path, audit_path, review)
    with sqlite3.connect(output) as conn:
        event_id, payload = conn.execute("SELECT event_id,payload FROM rule_migrations").fetchone()
        event = json.loads(payload)
        if mutation == "rejected_admission":
            event["admission"]["review"]["decision"] = "REJECT_DEFINITIONAL_RULE"
        elif mutation == "lost_archive":
            event["archived"] = []
        else:
            event["archived"].append(event["archived"][0])
        # Deliberately bypass the write guard to test the independent reader.
        conn.execute("DROP TRIGGER rule_migrations_no_update")
        conn.execute(
            "UPDATE rule_migrations SET event_id=?,payload=? WHERE event_id=?",
            (digest(event), json.dumps(event), event_id),
        )
    with pytest.raises(ValueError, match=reason):
        validate_build(output)


@pytest.mark.parametrize("changed", ["definition", "native_observation"])
def test_stale_audited_source_is_rejected_even_when_candidate_replay_is_valid(tmp_path, changed):
    source, input_path, audit_path, review = packet(tmp_path)
    with sqlite3.connect(source) as conn:
        if changed == "definition":
            conn.execute("UPDATE lexemes SET gloss=? WHERE sense_id='h'", ("Changed held-out definition.",))
        else:
            record_id, payload = conn.execute(
                "SELECT record_id,payload FROM source_observations WHERE entry_id='h'"
            ).fetchone()
            observation = json.loads(payload)
            observation["features"]["native_revision"] = "changed-after-audit"
            conn.execute(
                "UPDATE source_observations SET payload=? WHERE record_id=?", (json.dumps(observation), record_id)
            )
    assert validate_build(source)["code"] == "REPLAY_VALIDATED"
    before = source.read_bytes()
    output = tmp_path / "failed.db"
    with pytest.raises(ValueError, match="MIGRATION_AUDITED_SNAPSHOT_CHANGED"):
        migrate_rule(source, output, input_path, audit_path, review)
    assert source.read_bytes() == before
    assert not output.exists()
    assert not list(tmp_path.glob(".gse-migration-*"))


def test_new_unreviewed_model_context_is_archived_without_becoming_a_native_fact(tmp_path):
    source, input_path, audit_path, review = packet(tmp_path)
    # The held-out audit deliberately starts from native/anchor context. A later
    # unreviewed model answer is neither an audited premise nor a hard native
    # counterexample. It must be explicitly archived when its context changes.
    report = complete_dictionary(source, Transport(0), 1, entry_ids=("h",), banks=("BE",))
    assert report["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(source) as conn:
        receipt = read_model_receipts(conn)["h"][0]
    output = tmp_path / "migrated.db"
    result = migrate_rule(source, output, input_path, audit_path, review)
    assert result["archived_model_receipts"] == 4
    with sqlite3.connect(output) as conn:
        assert "h" not in read_model_receipts(conn)
        event = json.loads(conn.execute("SELECT payload FROM rule_migrations").fetchone()[0])
        archived = [item for group in event["archived"] for item in group["receipts"]]
        assert receipt in archived
        domains = json.loads(conn.execute("SELECT domains FROM definition_states WHERE entry_id='h'").fetchone()[0])
    assert domains["BE"] == [-1, 0, 1]
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


def test_reconsidered_question_and_distinct_retry_survive_rule_migration(tmp_path):
    source, input_path, audit_path, review = packet(tmp_path)
    with sqlite3.connect(source) as conn:
        original = read_model_receipts(conn)["b"][0]
    withdrawn = reconsider(source, original["request_id"], convention="fixture", reason="test", apply=True)
    assert withdrawn["after_domains"]["WANT"] == [-1, 0, 1]

    retry = Transport(1)
    retry.identity = "synthetic-new-wire-protocol"
    report = complete_dictionary(source, retry, 1, entry_ids=("b",), banks=("WANT",))
    assert report["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(source) as conn:
        replacement = read_model_receipts(conn)["b"][0]
    assert original["request_id"] == replacement["request_id"]
    assert digest(original) != digest(replacement)

    output = tmp_path / "retry-migrated.db"
    migrate_rule(source, output, input_path, audit_path, review)
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"
    with sqlite3.connect(output) as conn:
        assert read_model_receipts(conn)["b"][0] == replacement
        row = conn.execute("SELECT payload FROM model_reconsideration_archive").fetchone()
        assert json.loads(row[0])["archived_receipts"][0]["receipt"] == original
        assert conn.execute(
            "SELECT receipt_sha256 FROM model_rule_versions WHERE request_id=?", (replacement["request_id"],)
        ).fetchall() == [(digest(replacement),)]


def test_legacy_binding_table_upgrade_preserves_rows_and_refuses_duplicate_receipt():
    with sqlite3.connect(":memory:") as conn:
        conn.execute(
            "CREATE TABLE model_rule_versions (request_id TEXT PRIMARY KEY NOT NULL,entry_id TEXT NOT NULL,"
            "version TEXT NOT NULL,receipt_sha256 TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO model_rule_versions VALUES ('question','entry','old','receipt-a')")
        conn.execute(
            "CREATE TRIGGER model_rule_versions_no_replace BEFORE INSERT ON model_rule_versions "
            "WHEN EXISTS (SELECT 1 FROM model_rule_versions WHERE request_id=NEW.request_id) "
            "BEGIN SELECT RAISE(ABORT,'RULE_HISTORY_APPEND_ONLY'); END"
        )
        install_history(conn)
        conn.execute("INSERT INTO model_rule_versions VALUES ('question','entry','new','receipt-b')")
        assert conn.execute("SELECT version,receipt_sha256 FROM model_rule_versions ORDER BY receipt_sha256").fetchall() == [
            ("old", "receipt-a"), ("new", "receipt-b"),
        ]
        with pytest.raises(sqlite3.IntegrityError, match="RULE_HISTORY_APPEND_ONLY"):
            conn.execute("INSERT OR REPLACE INTO model_rule_versions VALUES ('question','entry','new','receipt-a')")


def test_report_symlink_created_after_preflight_cannot_overwrite_source(tmp_path, monkeypatch):
    from scripts import migrate_lexicon_rule as cli

    source, input_path, audit_path, review = packet(tmp_path)
    output, report_path, review_path = (tmp_path / name for name in ("migrated.db", "report.json", "review.json"))
    review_path.write_text(json.dumps(review))
    before = source.read_bytes()
    actual = cli.migrate_rule

    def insert_racing_symlink(*args, **kwargs):
        result = actual(*args, **kwargs)
        report_path.symlink_to(source)
        return result

    monkeypatch.setattr(cli, "migrate_rule", insert_racing_symlink)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate",
            "--candidate",
            str(source),
            "--output",
            str(output),
            "--input",
            str(input_path),
            "--audit",
            str(audit_path),
            "--review",
            str(review_path),
            "--report",
            str(report_path),
        ],
    )
    with pytest.raises(FileExistsError):
        cli.main()
    assert source.read_bytes() == before
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


def test_racing_candidate_destination_is_never_overwritten(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import rule_migration

    source, input_path, audit_path, review = packet(tmp_path)
    output = tmp_path / "migrated.db"
    before = source.read_bytes()
    actual = rule_migration.os.link
    occupied = b"This destination was installed by another writer."

    def insert_racing_destination(temporary, destination):
        output.write_bytes(occupied)
        return actual(temporary, destination)

    monkeypatch.setattr(rule_migration.os, "link", insert_racing_destination)
    with pytest.raises(FileExistsError):
        migrate_rule(source, output, input_path, audit_path, review)
    assert source.read_bytes() == before
    assert output.read_bytes() == occupied
    assert not list(tmp_path.glob(".gse-migration-*"))
