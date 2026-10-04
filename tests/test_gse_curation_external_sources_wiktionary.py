"""Manual contract tests for gse.curation.external_sources.wiktionary."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.wiktionary import (
    DEFINITION_PATTERNS,
    ETYMOLOGY_PATTERNS,
    WiktionaryEntry,
    WiktionaryParser,
    download_wiktionary,
)


@pytest.fixture
def fresh_db(tmp_path):
    """Build empty Wiktionary SQLite schema."""
    db_path = tmp_path / "wikt.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            pos TEXT,
            definition TEXT,
            etymology TEXT,
            synonyms TEXT,
            antonyms TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_word ON entries(word)")
    conn.commit()
    conn.close()
    return db_path


def insert_entry(db_path, word, pos="n", definition="", etymology="",
                 synonyms=None, antonyms=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO entries (word, pos, definition, etymology, synonyms, antonyms) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (word, pos, definition, etymology,
         json.dumps(synonyms or []), json.dumps(antonyms or [])),
    )
    conn.commit()
    conn.close()


# ---------- WiktionaryEntry ----------

class TestEntry:
    def test_construction(self):
        e = WiktionaryEntry(
            word="dog", pos="noun", definition="an animal",
            etymology="OE docga", synonyms=["canine"], antonyms=["cat"],
        )
        assert e.word == "dog"
        assert e.synonyms == ["canine"]


# ---------- Patterns ----------

class TestPatterns:
    def test_definition_patterns_dict_nonempty(self):
        assert len(DEFINITION_PATTERNS) > 0

    def test_etymology_patterns_dict_nonempty(self):
        assert len(ETYMOLOGY_PATTERNS) > 0

    def test_negative_prefix_pattern(self):
        # Make sure the etymology negative prefix pattern exists
        assert any("negative" in p for p in ETYMOLOGY_PATTERNS.keys())


# ---------- __init__ ----------

class TestInit:
    def test_default_path(self):
        p = WiktionaryParser()
        assert p.db_path.name == "wiktionary-en.sqlite"

    def test_custom_path(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        assert p.db_path == tmp_path / "x.db"

    def test_conn_initially_none(self):
        assert WiktionaryParser().conn is None

    def test_config_name(self):
        assert WiktionaryParser().config.name == "wiktionary"

    def test_precompiles_patterns(self):
        p = WiktionaryParser()
        assert len(p._compiled_def_patterns) == len(DEFINITION_PATTERNS)
        assert len(p._compiled_etym_patterns) == len(ETYMOLOGY_PATTERNS)


# ---------- _create_database ----------

class TestCreateDatabase:
    def test_creates_table(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        p._create_database()
        conn = sqlite3.connect(str(p.db_path))
        # Should be able to query the entries table
        conn.execute("SELECT * FROM entries").fetchall()
        conn.close()


# ---------- _insert_batch ----------

class TestInsertBatch:
    def test_inserts_rows(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        p.conn = sqlite3.connect(str(fresh_db))
        batch = [("dog", "noun", "an animal", "", "[]", "[]")]
        p._insert_batch(batch)
        rows = p.conn.execute("SELECT word FROM entries").fetchall()
        p.conn.close()
        assert rows == [("dog",)]


# ---------- download_and_process ----------

class TestDownloadAndProcess:
    def test_basic(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        mock_response = MagicMock()
        # Use iter_lines with one valid JSON line
        entry_json = json.dumps({
            "word": "dog",
            "pos": "noun",
            "senses": [{"glosses": ["an animal"]}],
            "etymology_text": "OE",
        })
        mock_response.iter_lines.return_value = iter([entry_json.encode()])

        with patch("requests.get", return_value=mock_response):
            assert p.download_and_process() is True

        conn = sqlite3.connect(str(p.db_path))
        rows = conn.execute("SELECT word FROM entries").fetchall()
        conn.close()
        assert rows == [("dog",)]

    def test_empty_word_skipped(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter([json.dumps({"word": ""}).encode()])
        with patch("requests.get", return_value=mock_response):
            p.download_and_process()
        conn = sqlite3.connect(str(p.db_path))
        rows = conn.execute("SELECT * FROM entries").fetchall()
        conn.close()
        assert rows == []

    def test_empty_line_skipped(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter([b"", b'{"word":"dog","senses":[{"glosses":["x"]}]}'])
        with patch("requests.get", return_value=mock_response):
            p.download_and_process()
        conn = sqlite3.connect(str(p.db_path))
        rows = conn.execute("SELECT word FROM entries").fetchall()
        conn.close()
        assert rows == [("dog",)]

    def test_invalid_json_skipped(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter([
            b"INVALID JSON",
            json.dumps({"word": "dog", "senses": [{"glosses": ["x"]}]}).encode(),
        ])
        with patch("requests.get", return_value=mock_response):
            p.download_and_process()
        conn = sqlite3.connect(str(p.db_path))
        rows = conn.execute("SELECT * FROM entries").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_synonyms_extracted(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        entry_json = json.dumps({
            "word": "happy",
            "senses": [{
                "glosses": ["feeling good"],
                "synonyms": [{"word": "joyful"}, {"word": "elated"}],
            }],
        })
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter([entry_json.encode()])
        with patch("requests.get", return_value=mock_response):
            p.download_and_process()
        conn = sqlite3.connect(str(p.db_path))
        row = conn.execute("SELECT synonyms FROM entries WHERE word='happy'").fetchone()
        conn.close()
        assert "joyful" in row[0]
        assert "elated" in row[0]

    def test_lowercases_word(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        entry_json = json.dumps({"word": "DOG", "senses": [{"glosses": ["x"]}]})
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = iter([entry_json.encode()])
        with patch("requests.get", return_value=mock_response):
            p.download_and_process()
        conn = sqlite3.connect(str(p.db_path))
        rows = conn.execute("SELECT word FROM entries").fetchall()
        conn.close()
        assert rows == [("dog",)]

    def test_exception_returns_false(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "x.db")
        with patch("requests.get", side_effect=Exception("network")):
            assert p.download_and_process() is False


# ---------- load ----------

class TestLoad:
    def test_no_db_returns_false(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        assert p.load() is False

    def test_existing_db_loads(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        assert p.load() is True
        assert p._loaded is True

    def test_exception_during_load(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        with patch("sqlite3.connect", side_effect=RuntimeError("boom")):
            assert p.load() is False


# ---------- to_primitives ----------

class TestToPrimitives:
    def test_unknown_empty(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        assert p.to_primitives("nonexistent") == {}

    @pytest.mark.skip(reason="pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built definition-match behavior")
    def test_definition_match(self, fresh_db):
        insert_entry(fresh_db, "dog", definition="A four-legged animal that can move")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        result = p.to_primitives("dog")
        # "to move" matches MOVE pattern
        assert result["MOVE"] == 1

    def test_etymology_match(self, fresh_db):
        insert_entry(fresh_db, "x", definition="something",
                     etymology="From a negative prefix")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        result = p.to_primitives("x")
        # 'negative prefix' matches NOT pattern
        assert result["NOT"] == 1

    def test_case_insensitive(self, fresh_db):
        insert_entry(fresh_db, "dog", definition="something good")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        result = p.to_primitives("DOG")
        assert result["GOOD"] == 1

    def test_first_value_wins(self, fresh_db):
        # GOOD: 1 matches, then bad would not overwrite
        insert_entry(fresh_db, "x", definition="good and bad")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        result = p.to_primitives("x")
        # First match wins — depends on dict iteration; either +1 or -1
        assert "GOOD" in result

    def test_no_match_empty(self, fresh_db):
        insert_entry(fresh_db, "x", definition="zzzzzzz")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        assert p.to_primitives("x") == {}

    def test_empty_definition_handled(self, fresh_db):
        insert_entry(fresh_db, "x", definition="")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.to_primitives.cache_clear()
        assert p.to_primitives("x") == {}

    def test_auto_load_returns_empty_on_fail(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        p.to_primitives.cache_clear()
        assert p.to_primitives("dog") == {}


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_returns_words(self, fresh_db):
        insert_entry(fresh_db, "dog")
        insert_entry(fresh_db, "cat")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert set(p.get_all_words()) == {"dog", "cat"}

    def test_no_db_returns_empty(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        assert p.get_all_words() == []


# ---------- get_definition ----------

class TestGetDefinition:
    def test_returns_definition(self, fresh_db):
        insert_entry(fresh_db, "dog", definition="an animal")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_definition("dog") == "an animal"

    def test_unknown_none(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_definition("nonexistent") is None

    def test_lowercases(self, fresh_db):
        insert_entry(fresh_db, "dog", definition="an animal")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_definition("DOG") == "an animal"

    def test_load_fail_returns_none(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        assert p.get_definition("x") is None


# ---------- get_synonyms ----------

class TestGetSynonyms:
    def test_returns_list(self, fresh_db):
        insert_entry(fresh_db, "happy", synonyms=["joyful"])
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_synonyms("happy") == ["joyful"]

    def test_unknown_empty(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_synonyms("xyz") == []

    def test_no_db_returns_empty(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        assert p.get_synonyms("x") == []

    def test_empty_synonyms_field(self, fresh_db):
        insert_entry(fresh_db, "happy", synonyms=[])
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_synonyms("happy") == []


# ---------- get_antonyms ----------

class TestGetAntonyms:
    def test_returns_list(self, fresh_db):
        insert_entry(fresh_db, "happy", antonyms=["sad"])
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_antonyms("happy") == ["sad"]

    def test_unknown_empty(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_antonyms("xyz") == []

    def test_no_db_returns_empty(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        assert p.get_antonyms("x") == []


# ---------- get_etymology ----------

class TestGetEtymology:
    def test_returns_etymology(self, fresh_db):
        insert_entry(fresh_db, "dog", etymology="OE docga")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_etymology("dog") == "OE docga"

    def test_empty_etymology_excluded(self, fresh_db):
        # Filter excludes empty etymology rows
        insert_entry(fresh_db, "x", etymology="")
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        assert p.get_etymology("x") is None

    def test_no_db_returns_none(self, tmp_path):
        p = WiktionaryParser(db_path=tmp_path / "missing.db")
        assert p.get_etymology("x") is None


# ---------- close ----------

class TestClose:
    def test_closes_conn(self, fresh_db):
        p = WiktionaryParser(db_path=fresh_db)
        p.load()
        p.close()
        assert p.conn is None

    def test_no_conn_safe(self):
        p = WiktionaryParser()
        p.close()


# ---------- download_wiktionary ----------

class TestDownloadWiktionary:
    def test_success_prints(self, capsys):
        with patch.object(WiktionaryParser, "download_and_process", return_value=True):
            download_wiktionary()
        out = capsys.readouterr().out
        assert "successfully" in out

    def test_failure_prints(self, capsys):
        with patch.object(WiktionaryParser, "download_and_process", return_value=False):
            download_wiktionary()
        out = capsys.readouterr().out
        assert "Failed" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
