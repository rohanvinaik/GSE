"""Tests for WiktionaryPrimitivesV2Loader.

Uses an in-memory fixture DB matching the v2 schema; doesn't touch the real
886MB v2 DB on disk.
"""

import sqlite3
from pathlib import Path

import pytest

from gse.curation.external_sources.wiktionary_v2 import (
    WiktionaryPrimitivesV2Loader,
)


def _fixture_db(tmp_path: Path) -> Path:
    """Build a small fixture DB mirroring the v2 schema."""
    db = tmp_path / "wiktionary_primitives_v2.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE primitive_dictionary (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            bank INTEGER,
            is_bipolar INTEGER DEFAULT 0,
            bipolar_partner_id INTEGER
        );
        CREATE TABLE source_dictionary (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            reliability REAL
        );
        CREATE TABLE word_primitives_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            pos TEXT,
            primitive_id INTEGER NOT NULL,
            value INTEGER NOT NULL,
            confidence REAL,
            source_id INTEGER,
            FOREIGN KEY (primitive_id) REFERENCES primitive_dictionary(id)
        );
        INSERT INTO primitive_dictionary (id, name, bank) VALUES
            (1, 'GOOD',   2),
            (2, 'BAD',    2),
            (3, 'FEEL',   3),
            (4, 'NEAR',   6),
            (5, 'FAR',    6);
        INSERT INTO word_primitives_v2 (word, pos, primitive_id, value, confidence) VALUES
            ('good', 'adj', 1, 1,  0.92),
            ('good', 'adj', 3, 1,  0.55),
            ('bad',  'adj', 2, 1,  0.88),
            ('bad',  'adj', 3, 1,  0.60),
            ('near', 'adv', 4, 1,  0.80),
            ('near', 'adv', 5, -1, 0.20),
            ('emptyword', 'n', 1, 0, 0.0);
        """
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def loader(tmp_path):
    db = _fixture_db(tmp_path)
    inst = WiktionaryPrimitivesV2Loader(db_path=db)
    assert inst.load() is True
    yield inst
    inst.close()


class TestLoad:
    def test_missing_db_returns_false(self, tmp_path):
        inst = WiktionaryPrimitivesV2Loader(db_path=tmp_path / "missing.db")
        assert inst.load() is False
        assert inst._loaded is False

    def test_load_succeeds_with_valid_schema(self, loader):
        assert loader._loaded is True

    def test_load_rejects_db_missing_required_tables(self, tmp_path):
        db = tmp_path / "wrong_schema.db"
        c = sqlite3.connect(str(db))
        c.execute("CREATE TABLE entries (word TEXT)")
        c.commit()
        c.close()
        inst = WiktionaryPrimitivesV2Loader(db_path=db)
        assert inst.load() is False


class TestToPrimitives:
    def test_returns_active_primitives_only(self, loader):
        prims = loader.to_primitives("good")
        assert prims == {"GOOD": 1, "FEEL": 1}

    def test_negative_value_preserved(self, loader):
        prims = loader.to_primitives("near")
        assert prims["NEAR"] == 1
        assert prims["FAR"] == -1

    def test_zero_value_rows_excluded(self, loader):
        assert loader.to_primitives("emptyword") == {}

    def test_unknown_word_returns_empty(self, loader):
        assert loader.to_primitives("nonexistent") == {}

    def test_case_insensitive_lookup(self, loader):
        assert loader.to_primitives("GOOD") == loader.to_primitives("good")


class TestToPrimitivesWithConfidence:
    def test_returns_value_and_confidence_tuples(self, loader):
        out = loader.to_primitives_with_confidence("good")
        assert out["GOOD"] == (1, 0.92)
        assert out["FEEL"] == (1, 0.55)

    def test_confidence_preserved_for_negative_pole(self, loader):
        out = loader.to_primitives_with_confidence("near")
        assert out["FAR"] == (-1, 0.20)


class TestGetAllWords:
    def test_returns_distinct_words(self, loader):
        words = loader.get_all_words()
        assert set(words) == {"good", "bad", "near", "emptyword"}

    def test_has_word_lookup(self, loader):
        assert loader.has_word("good")
        assert not loader.has_word("nonexistent")


class TestClose:
    def test_close_releases_connection(self, loader):
        loader.close()
        assert loader.conn is None
        assert loader._loaded is False
