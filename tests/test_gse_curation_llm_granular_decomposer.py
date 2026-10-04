"""Manual contract tests for gse.curation.llm.granular_decomposer."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.granular_decomposer import (
    GRANULAR_SYSTEM_PROMPT,
    PRIMITIVE_GROUPS,
    GranularDecomposer,
    GranularResult,
    get_granular_prompt,
)


@pytest.fixture
def fresh_db(tmp_path):
    db_path = tmp_path / "lex.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, frequency_rank INTEGER
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


# ---------- PRIMITIVE_GROUPS ----------


class TestPrimitiveGroups:
    def test_has_8_banks(self):
        assert len(PRIMITIVE_GROUPS) == 8

    def test_substantives_count_10(self):
        assert len(PRIMITIVE_GROUPS["substantives"]) == 10

    def test_quantity_count_3(self):
        assert len(PRIMITIVE_GROUPS["quantity"]) == 3

    def test_evaluators_count_4(self):
        assert len(PRIMITIVE_GROUPS["evaluators"]) == 4

    def test_logical_count_14(self):
        assert len(PRIMITIVE_GROUPS["logical"]) == 14

    def test_good_in_evaluators(self):
        assert "GOOD" in PRIMITIVE_GROUPS["evaluators"]

    def test_someone_in_substantives(self):
        assert "SOMEONE" in PRIMITIVE_GROUPS["substantives"]


# ---------- GRANULAR_SYSTEM_PROMPT ----------


class TestSystemPrompt:
    def test_mentions_bipolar(self):
        assert "BIPOLAR" in GRANULAR_SYSTEM_PROMPT

    def test_mentions_json(self):
        assert "JSON" in GRANULAR_SYSTEM_PROMPT


# ---------- get_granular_prompt ----------


class TestGetGranularPrompt:
    def test_includes_word(self):
        result = get_granular_prompt("happy", ["GOOD", "FEEL"])
        assert "happy" in result

    def test_includes_primitives_list(self):
        result = get_granular_prompt("happy", ["GOOD", "FEEL"])
        assert "GOOD" in result
        assert "FEEL" in result

    def test_pos_appended(self):
        result = get_granular_prompt("happy", ["GOOD"], pos="adj")
        assert "(adj)" in result

    def test_no_pos_no_parens(self):
        result = get_granular_prompt("happy", ["GOOD"])
        assert "(adj)" not in result

    def test_word_quoted(self):
        result = get_granular_prompt("happy", ["GOOD"])
        assert '"happy"' in result

    def test_comma_separator(self):
        result = get_granular_prompt("happy", ["GOOD", "BIG"])
        assert "GOOD, BIG" in result

    def test_exact_evaluate_only_line(self):
        result = get_granular_prompt("x", ["GOOD"])
        assert "Evaluate ONLY these primitives:" in result

    def test_exact_example_format_line(self):
        result = get_granular_prompt("x", ["GOOD"])
        assert "Example format:" in result

    def test_exact_think_carefully(self):
        result = get_granular_prompt("x", ["GOOD"])
        assert "Think carefully" in result

    def test_exact_example_json_inline(self):
        # Pin the example format JSON string
        result = get_granular_prompt("x", ["GOOD"])
        assert '{"PRIMITIVE1": 1, "PRIMITIVE2": 0, "PRIMITIVE3": -1}' in result


# ---------- GranularResult ----------


class TestGranularResult:
    def test_construction(self):
        r = GranularResult(word="x", primitives={"GOOD": 1}, source="llm:m", bank="evaluators")
        assert r.word == "x"
        assert r.source == "llm:m"
        assert r.raw_response is None


# ---------- __init__ ----------


class TestInit:
    def test_basic(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            assert d.db_path == fresh_db
            assert d.model == "qwen3:32b"
            assert d.temperature == 0.2

    def test_custom_model_temp(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db, model="llama", temperature=0.5)
            assert d.model == "llama"
            assert d.temperature == 0.5


# ---------- get_filled_primitives ----------


class TestGetFilled:
    def test_empty(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            assert d.get_filled_primitives(1) == {}

    def test_returns_value_and_source(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            d.conn.execute(
                "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
                "VALUES (1, 'GOOD', 1, 0.9, 'verbnet')"
            )
            d.conn.commit()
            result = d.get_filled_primitives(1)
            assert result == {"GOOD": (1, "verbnet")}


# ---------- get_missing_primitives ----------


class TestGetMissing:
    def test_all_missing_when_empty(self, fresh_db):
        from gse.curation.schema import ALL_PRIMITIVES

        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            assert set(d.get_missing_primitives(1)) == set(ALL_PRIMITIVES)

    def test_excludes_filled(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            d.conn.execute(
                "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
                "VALUES (1, 'GOOD', 1, 0.9, 'verbnet')"
            )
            d.conn.commit()
            assert "GOOD" not in d.get_missing_primitives(1)


# ---------- decompose_primitives ----------


class TestDecomposePrimitives:
    def test_empty_list(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            assert d.decompose_primitives("x", []) == {}

    def test_basic_response(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": 1, "BAD": 0}'
            d = GranularDecomposer(db_path=fresh_db)
            result = d.decompose_primitives("happy", ["GOOD", "BAD"])
            assert result == {"GOOD": 1, "BAD": 0}

    def test_positive_value_normalized(self, fresh_db):
        # Value 5 normalized to 1
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": 5}'
            d = GranularDecomposer(db_path=fresh_db)
            assert d.decompose_primitives("x", ["GOOD"])["GOOD"] == 1

    def test_negative_value_normalized(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": -3}'
            d = GranularDecomposer(db_path=fresh_db)
            assert d.decompose_primitives("x", ["GOOD"])["GOOD"] == -1

    def test_zero_value(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": 0}'
            d = GranularDecomposer(db_path=fresh_db)
            assert d.decompose_primitives("x", ["GOOD"])["GOOD"] == 0

    def test_non_numeric_value_becomes_0(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": "yes"}'
            d = GranularDecomposer(db_path=fresh_db)
            assert d.decompose_primitives("x", ["GOOD"])["GOOD"] == 0

    def test_missing_primitive_filled_with_0(self, fresh_db):
        # If LLM returns response without one of the requested primitives → 0
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": 1}'
            d = GranularDecomposer(db_path=fresh_db)
            result = d.decompose_primitives("x", ["GOOD", "BAD"])
            assert result == {"GOOD": 1, "BAD": 0}

    def test_no_json_returns_all_zeros(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "no json here"
            d = GranularDecomposer(db_path=fresh_db)
            result = d.decompose_primitives("x", ["GOOD", "BAD"])
            assert result == {"GOOD": 0, "BAD": 0}

    def test_exception_returns_all_zeros(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.side_effect = RuntimeError("boom")
            d = GranularDecomposer(db_path=fresh_db)
            result = d.decompose_primitives("x", ["GOOD", "BAD"])
            assert result == {"GOOD": 0, "BAD": 0}


# ---------- process_word ----------


class TestProcessWord:
    def test_skips_filled_when_skip_filled_true(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": 1}'
            d = GranularDecomposer(db_path=fresh_db)
            # All evaluators pre-filled
            for p in ["GOOD", "BAD", "BIG", "SMALL"]:
                d.conn.execute(
                    "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
                    "VALUES (1, ?, 1, 0.9, 'verbnet')",
                    (p,),
                )
            d.conn.commit()
            results = d.process_word(1, "happy", skip_filled=True)
            # evaluators bank skipped (all filled)
            assert "evaluators" not in results

    def test_no_skip_processes_all_banks(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "{}"
            d = GranularDecomposer(db_path=fresh_db)
            results = d.process_word(1, "happy", skip_filled=False)
            # All 8 banks queried
            assert len(results) == 8

    def test_stores_results_in_db(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = '{"GOOD": 1}'
            d = GranularDecomposer(db_path=fresh_db, model="m")
            d.process_word(1, "happy", skip_filled=False)
            # DB should have entries with source "llm:m"
            cursor = d.conn.execute("SELECT COUNT(*) FROM primitive_values WHERE source = 'llm:m'")
            count = cursor.fetchone()[0]
            assert count > 0


# ---------- process_batch ----------


class TestProcessBatch:
    def test_no_words(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            stats = d.process_batch()
            assert stats["processed"] == 0

    def test_processes_words(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "{}"
            d = GranularDecomposer(db_path=fresh_db)
            d.conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 'adj', 1)")
            d.conn.commit()
            stats = d.process_batch()
            assert stats["processed"] == 1

    def test_limit(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "{}"
            d = GranularDecomposer(db_path=fresh_db)
            for i in range(5):
                d.conn.execute("INSERT INTO lexemes VALUES (?, ?, ?, ?)", (i, f"w{i}", "n", i))
            d.conn.commit()
            stats = d.process_batch(limit=3)
            assert stats["processed"] == 3

    def test_only_missing_false_returns_all(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "{}"
            d = GranularDecomposer(db_path=fresh_db)
            d.conn.execute("INSERT INTO lexemes VALUES (1, 'w1', 'n', 1)")
            d.conn.commit()
            stats = d.process_batch(only_missing=False)
            assert stats["processed"] == 1


# ---------- close ----------


class TestClose:
    def test_closes_conn(self, fresh_db):
        with patch("gse.curation.llm.granular_decomposer.OllamaClient"):
            d = GranularDecomposer(db_path=fresh_db)
            d.close()
            with pytest.raises(sqlite3.ProgrammingError):
                d.conn.execute("SELECT 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
