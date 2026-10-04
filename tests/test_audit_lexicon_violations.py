"""Tests for the legacy lexicon violation audit script."""

import importlib.util
import sqlite3
from pathlib import Path

import pytest


# Load the script as a module (it's in scripts/, not gse/)
def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_lexicon_violations",
        Path(__file__).parent.parent / "scripts" / "audit_lexicon_violations.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def audit_mod():
    return _load_audit_module()


@pytest.fixture
def fixture_db(tmp_path):
    """Build a tiny lexicon with known violations."""
    db = tmp_path / "lexicon.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT);
        CREATE TABLE primitive_values (
            lexeme_id INTEGER,
            primitive TEXT,
            value INTEGER
        );
        INSERT INTO lexemes (id, lemma) VALUES (1, 'noisy_word');
        -- 3 bipolar violations on lex 1: GOOD/BAD, BIG/SMALL, ALIVE/DEAD
        INSERT INTO primitive_values VALUES
            (1, 'GOOD', 1), (1, 'BAD', 1),
            (1, 'BIG', 1),  (1, 'SMALL', 1),
            (1, 'ALIVE', 1), (1, 'DEAD', 1),
            (1, 'FEEL', 1);

        INSERT INTO lexemes (id, lemma) VALUES (2, 'clean_word');
        -- clean — only one pole of each pair
        INSERT INTO primitive_values VALUES
            (2, 'GOOD', 1),
            (2, 'BIG', 1);

        INSERT INTO lexemes (id, lemma) VALUES (3, 'empty_word');
        -- no primitive_values rows
        """
    )
    conn.commit()
    conn.close()
    return db


class TestAudit:
    def test_counts_lexemes_with_violations(self, audit_mod, fixture_db):
        report = audit_mod.audit(fixture_db)
        assert report["total_lexemes"] == 3
        assert report["lexemes_with_violations"] == 1
        assert report["violation_rate"] == pytest.approx(1.0 / 3)

    def test_total_violations_summed(self, audit_mod, fixture_db):
        report = audit_mod.audit(fixture_db)
        # noisy_word: 3 violations (GOOD/BAD, BIG/SMALL, ALIVE/DEAD)
        assert report["total_violations"] == 3

    def test_per_pair_counts(self, audit_mod, fixture_db):
        report = audit_mod.audit(fixture_db)
        pair_counts = report["per_bipolar_pair_violation_count"]
        assert pair_counts.get("GOOD/BAD") == 1
        assert pair_counts.get("BIG/SMALL") == 1
        assert pair_counts.get("ALIVE/DEAD") == 1
        # No NEAR/FAR violation
        assert pair_counts.get("NEAR/FAR", 0) == 0

    def test_worst_offenders_ranked_by_count(self, audit_mod, fixture_db):
        report = audit_mod.audit(fixture_db)
        worst = report["worst_offenders"]
        assert worst[0]["lemma"] == "noisy_word"
        assert worst[0]["violations"] == 3

    def test_empty_db_handled(self, audit_mod, tmp_path):
        db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db))
        conn.executescript(
            "CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT);"
            "CREATE TABLE primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);"
        )
        conn.commit()
        conn.close()
        report = audit_mod.audit(db)
        assert report["total_lexemes"] == 0

    def test_missing_db_raises(self, audit_mod, tmp_path):
        with pytest.raises(FileNotFoundError):
            audit_mod.audit(tmp_path / "missing.db")
