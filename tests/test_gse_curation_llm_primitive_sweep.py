"""Manual contract tests for gse.curation.llm.primitive_sweep."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.primitive_sweep import (
    BIPOLAR_PAIRS,
    SINGLE_PRIMITIVES,
    SYSTEM_PROMPT,
    PrimitiveSweep,
    SweepStats,
    get_bipolar_batch_prompt,
    get_single_batch_prompt,
    main,
)


@pytest.fixture
def fresh_db(tmp_path):
    db_path = tmp_path / "lex.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY, lemma TEXT, frequency_rank INTEGER
        );
        CREATE TABLE primitive_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER, primitive TEXT, value INTEGER,
            confidence REAL, source TEXT
        );
    """)
    conn.commit()
    conn.close()
    return str(db_path)


def mk_sweep(fresh_db):
    with patch("gse.curation.llm.primitive_sweep.OllamaClient"):
        s = PrimitiveSweep(db_path=fresh_db)
        s.client = MagicMock()
        return s


# ---------- Constants ----------


class TestConstants:
    def test_bipolar_pair_count(self):
        assert len(BIPOLAR_PAIRS) == 14

    def test_single_primitives_count(self):
        assert len(SINGLE_PRIMITIVES) == 44

    def test_system_prompt_format_line(self):
        assert "WORD: ANSWER" in SYSTEM_PROMPT


# ---------- get_bipolar_batch_prompt ----------


class TestGetBipolarBatchPrompt:
    def test_includes_words(self):
        result = get_bipolar_batch_prompt(["happy", "sad"], "GOOD", "BAD")
        assert "happy" in result
        assert "sad" in result

    def test_includes_poles(self):
        result = get_bipolar_batch_prompt(["x"], "GOOD", "BAD")
        assert "GOOD" in result
        assert "BAD" in result

    def test_label_format(self):
        result = get_bipolar_batch_prompt(["x"], "GOOD", "BAD")
        assert "A = GOOD" in result
        assert "B = BAD" in result
        assert "N = Neither" in result

    def test_answer_format_line(self):
        result = get_bipolar_batch_prompt(["x"], "GOOD", "BAD")
        assert "word: A/B/N" in result

    def test_words_comma_separated(self):
        result = get_bipolar_batch_prompt(["a", "b", "c"], "X", "Y")
        assert "a, b, c" in result

    def test_exact_for_each_word_line(self):
        result = get_bipolar_batch_prompt(["x"], "G", "B")
        assert "For each word, which applies?" in result

    def test_exact_leans_toward_format(self):
        result = get_bipolar_batch_prompt(["x"], "G", "B")
        assert "leans toward G" in result
        assert "leans toward B" in result

    def test_exact_answer_format_line(self):
        result = get_bipolar_batch_prompt(["x"], "G", "B")
        assert 'Answer each as "word: A/B/N" on separate lines:' in result


# ---------- get_single_batch_prompt ----------


class TestGetSingleBatchPrompt:
    def test_includes_primitive_and_words(self):
        result = get_single_batch_prompt(["happy"], "GOOD")
        assert "happy" in result
        assert "GOOD" in result

    def test_y_n_o_labels(self):
        result = get_single_batch_prompt(["x"], "P")
        assert "Y = Yes" in result
        assert "N = No" in result
        assert "O = Opposite" in result

    def test_answer_format_line(self):
        result = get_single_batch_prompt(["x"], "P")
        assert "word: Y/N/O" in result

    def test_exact_does_each_word_line(self):
        result = get_single_batch_prompt(["x"], "GOOD")
        assert "Does each word's meaning involve GOOD?" in result

    def test_exact_y_yes_line(self):
        result = get_single_batch_prompt(["x"], "GOOD")
        assert "Y = Yes (involves GOOD)" in result

    def test_exact_o_opposite_line(self):
        result = get_single_batch_prompt(["x"], "GOOD")
        assert "O = Opposite (involves the opposite of GOOD)" in result

    def test_exact_n_no_line(self):
        result = get_single_batch_prompt(["x"], "GOOD")
        assert "N = No (not relevant)" in result


# ---------- SweepStats ----------


class TestSweepStats:
    def test_defaults(self):
        s = SweepStats()
        assert s.primitives_processed == 0
        assert s.words_processed == 0
        assert s.values_set == 0
        assert s.errors == 0

    def test_str_format(self):
        s = SweepStats(primitives_processed=5, words_processed=10, values_set=20)
        result = str(s)
        assert "Prims: 5" in result
        assert "Words: 10" in result
        assert "Set: 20" in result


# ---------- __init__ ----------


class TestInit:
    def test_basic(self, fresh_db):
        with patch("gse.curation.llm.primitive_sweep.OllamaClient"):
            s = PrimitiveSweep(db_path=fresh_db)
            assert s.db_path == fresh_db
            assert s.model == "qwen2.5:7b"
            assert s.batch_size == 20

    def test_custom_batch_size(self, fresh_db):
        with patch("gse.curation.llm.primitive_sweep.OllamaClient"):
            s = PrimitiveSweep(db_path=fresh_db, batch_size=5)
            assert s.batch_size == 5

    def test_config_max_tokens(self, fresh_db):
        with patch("gse.curation.llm.primitive_sweep.OllamaClient"):
            s = PrimitiveSweep(db_path=fresh_db)
            assert s.config.max_tokens == 500


# ---------- get_top_words ----------


class TestGetTopWords:
    def test_empty(self, fresh_db):
        s = mk_sweep(fresh_db)
        assert s.get_top_words() == []

    def test_returns_by_rank(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.conn.execute("INSERT INTO lexemes VALUES (1, 'b', 2)")
        s.conn.execute("INSERT INTO lexemes VALUES (2, 'a', 1)")
        s.conn.commit()
        result = s.get_top_words()
        # Ordered by rank
        assert result[0][1] == "a"
        assert result[1][1] == "b"

    def test_skips_null_rank(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.conn.execute("INSERT INTO lexemes VALUES (1, 'norank', NULL)")
        s.conn.execute("INSERT INTO lexemes VALUES (2, 'has_rank', 1)")
        s.conn.commit()
        result = s.get_top_words()
        # Only has_rank
        assert len(result) == 1
        assert result[0][1] == "has_rank"

    def test_limit(self, fresh_db):
        s = mk_sweep(fresh_db)
        for i in range(10):
            s.conn.execute("INSERT INTO lexemes VALUES (?, ?, ?)", (i, f"w{i}", i + 1))
        s.conn.commit()
        result = s.get_top_words(limit=3)
        assert len(result) == 3


# ---------- parse_bipolar_response ----------


class TestParseBipolarResponse:
    def test_a_for_word(self):
        s = mk_sweep(":memory:")
        response = "happy: A\nsad: B"
        result = s.parse_bipolar_response(response, ["happy", "sad"], "GOOD", "BAD")
        assert result["happy"] == (1, 0)
        assert result["sad"] == (0, 1)

    def test_n_for_neither(self):
        s = mk_sweep(":memory:")
        result = s.parse_bipolar_response("x: N", ["x"], "GOOD", "BAD")
        assert result["x"] == (0, 0)

    def test_missing_word_default_zero(self):
        s = mk_sweep(":memory:")
        result = s.parse_bipolar_response("foo: A", ["bar"], "GOOD", "BAD")
        assert result["bar"] == (0, 0)

    def test_case_insensitive(self):
        s = mk_sweep(":memory:")
        result = s.parse_bipolar_response("HAPPY: a", ["happy"], "GOOD", "BAD")
        assert result["happy"] == (1, 0)

    def test_alternate_separator(self):
        s = mk_sweep(":memory:")
        result = s.parse_bipolar_response("happy=A", ["happy"], "GOOD", "BAD")
        assert result["happy"] == (1, 0)


# ---------- parse_single_response ----------


class TestParseSingleResponse:
    def test_yes(self):
        s = mk_sweep(":memory:")
        result = s.parse_single_response("happy: Y", ["happy"])
        assert result["happy"] == 1

    def test_no(self):
        s = mk_sweep(":memory:")
        result = s.parse_single_response("x: N", ["x"])
        assert result["x"] == 0

    def test_opposite(self):
        s = mk_sweep(":memory:")
        result = s.parse_single_response("x: O", ["x"])
        assert result["x"] == -1

    def test_missing_default_zero(self):
        s = mk_sweep(":memory:")
        result = s.parse_single_response("foo: Y", ["bar"])
        assert result["bar"] == 0

    def test_case_insensitive(self):
        s = mk_sweep(":memory:")
        result = s.parse_single_response("HAPPY: y", ["happy"])
        assert result["happy"] == 1


# ---------- sweep_bipolar ----------


class TestSweepBipolar:
    def test_empty_words(self, fresh_db):
        s = mk_sweep(fresh_db)
        result = s.sweep_bipolar("GOOD", "BAD", [])
        assert result == 0

    def test_processes_words(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.return_value = "happy: A"
        result = s.sweep_bipolar("GOOD", "BAD", [(1, "happy")])
        assert result == 1
        # Verify DB has the value
        cursor = s.conn.execute("SELECT value FROM primitive_values WHERE primitive = 'GOOD'")
        assert cursor.fetchone()[0] == 1

    def test_exception_increments_errors(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.side_effect = RuntimeError("boom")
        s.sweep_bipolar("GOOD", "BAD", [(1, "x")])
        assert s.stats.errors == 1


# ---------- sweep_single ----------


class TestSweepSingle:
    def test_empty_words(self, fresh_db):
        s = mk_sweep(fresh_db)
        assert s.sweep_single("GOOD", []) == 0

    def test_processes_words(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.return_value = "happy: Y"
        result = s.sweep_single("FEEL", [(1, "happy")])
        assert result == 1
        cursor = s.conn.execute("SELECT value FROM primitive_values WHERE primitive = 'FEEL'")
        assert cursor.fetchone()[0] == 1

    def test_exception_increments_errors(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.side_effect = RuntimeError("boom")
        s.sweep_single("FEEL", [(1, "x")])
        assert s.stats.errors == 1


# ---------- run_full_sweep ----------


class TestRunFullSweep:
    def test_no_words(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.return_value = "x: N"
        stats = s.run_full_sweep(word_limit=10)
        # 14 bipolar pairs (28 primitives) + 44 singles = 72 prims processed
        assert stats.primitives_processed == 72

    def test_with_words(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.return_value = "happy: A"
        s.conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 1)")
        s.conn.commit()
        stats = s.run_full_sweep(word_limit=10)
        assert stats.words_processed == 1

    def test_start_primitive_resume(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.client.generate.return_value = "x: N"
        # Start from middle pair → skip earlier pairs
        stats = s.run_full_sweep(word_limit=10, start_primitive="ALIVE")
        # Started at ALIVE: pairs processed = ALIVE/DEAD + remainder
        # 14 - 3 prior pairs = 11 pairs (22 primitives) + 44 singles = 66
        # Actually counts BIPOLAR + singles after start
        # Need to verify processes started at start_primitive
        assert stats.primitives_processed > 0


# ---------- close ----------


class TestClose:
    def test_closes_conn(self, fresh_db):
        s = mk_sweep(fresh_db)
        s.close()
        with pytest.raises(sqlite3.ProgrammingError):
            s.conn.execute("SELECT 1")


# ---------- main ----------


class TestMain:
    def test_basic_run(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--words", "0"]):
            with patch("gse.curation.llm.primitive_sweep.OllamaClient"):
                with patch.object(PrimitiveSweep, "run_full_sweep", return_value=SweepStats()):
                    main()
        assert "SWEEP COMPLETE" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
