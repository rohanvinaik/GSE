"""Manual contract tests for gse.curation.llm.gap_filler."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.gap_filler import (
    BIPOLAR_INFERENCE,
    NEED_LLM,
    SYSTEM_PROMPT,
    GapFiller,
    get_single_prompt,
    main,
)


@pytest.fixture
def fresh_db(tmp_path):
    """Build empty lexicon DB."""
    db_path = tmp_path / "lex.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY, lemma TEXT, frequency_rank INTEGER
        );
        CREATE TABLE primitive_values (
            lexeme_id INTEGER, primitive TEXT, value INTEGER,
            confidence REAL, source TEXT,
            PRIMARY KEY (lexeme_id, primitive, source)
        );
    """)
    conn.commit()
    conn.close()
    return str(db_path)


# ---------- NEED_LLM ----------


class TestNeedLLM:
    def test_contains_bad(self):
        assert "BAD" in NEED_LLM

    def test_contains_after(self):
        assert "AFTER" in NEED_LLM

    def test_does_not_contain_good(self):
        # GOOD is covered by external sources
        assert "GOOD" not in NEED_LLM

    def test_is_set_type(self):
        assert isinstance(NEED_LLM, set)


# ---------- BIPOLAR_INFERENCE ----------


class TestBipolarInference:
    def test_good_bad_inferable(self):
        assert BIPOLAR_INFERENCE[("GOOD", "BAD")] == "GOOD"

    def test_big_small_inferable(self):
        assert BIPOLAR_INFERENCE[("BIG", "SMALL")] == "BIG"

    def test_same_other_both_llm(self):
        assert BIPOLAR_INFERENCE[("SAME", "OTHER")] is None

    def test_true_false_both_llm(self):
        assert BIPOLAR_INFERENCE[("TRUE", "FALSE")] is None


# ---------- SYSTEM_PROMPT ----------


class TestSystemPrompt:
    def test_mentions_options(self):
        assert "YES" in SYSTEM_PROMPT
        assert "NO" in SYSTEM_PROMPT
        assert "OPPOSITE" in SYSTEM_PROMPT


# ---------- get_single_prompt ----------


class TestGetSinglePrompt:
    def test_includes_word(self):
        result = get_single_prompt("happy", "GOOD")
        assert "happy" in result

    def test_includes_primitive(self):
        result = get_single_prompt("happy", "GOOD")
        assert "GOOD" in result

    def test_includes_answer_options(self):
        result = get_single_prompt("x", "Y")
        assert "YES" in result
        assert "NO" in result
        assert "OPPOSITE" in result

    def test_exact_prompt_format(self):
        # Pin exact prompt format
        result = get_single_prompt("happy", "GOOD")
        assert 'Word: "happy"' in result
        assert "Primitive: GOOD" in result
        assert "involve GOOD" in result
        assert "Answer: YES, NO, or OPPOSITE" in result

    def test_word_quoted_in_prompt(self):
        # Word is quoted with double quotes
        result = get_single_prompt("xyz", "P")
        assert '"xyz"' in result

    def test_primitive_unquoted(self):
        # Primitive appears without quotes
        result = get_single_prompt("x", "GOOD")
        assert "Primitive: GOOD" in result
        # Not '"GOOD"' after "Primitive: "
        assert 'Primitive: "GOOD"' not in result


# ---------- __init__ ----------


class TestInit:
    def test_basic(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            assert g.db_path == fresh_db
            assert g.model == "qwen2.5:7b"

    def test_custom_model(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db, model="llama2")
            assert g.model == "llama2"

    def test_config_low_temperature(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            assert g.config.temperature == 0.1
            assert g.config.max_tokens == 20


# ---------- get_external_primitives ----------


class TestGetExternalPrimitives:
    def test_empty(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            assert g.get_external_primitives(1) == {}

    def test_returns_non_llm(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            g.conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 'verbnet')")
            g.conn.commit()
            assert g.get_external_primitives(1) == {"GOOD": 1}

    def test_excludes_llm_sources(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            g.conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 'verbnet')")
            g.conn.execute("INSERT INTO primitive_values VALUES (1, 'BAD', 1, 0.7, 'llm:qwen')")
            g.conn.commit()
            result = g.get_external_primitives(1)
            assert "GOOD" in result
            assert "BAD" not in result


# ---------- infer_bipolar_counterpart ----------


class TestInferBipolarCounterpart:
    def test_empty(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            assert g.infer_bipolar_counterpart({}) == {}

    def test_good_to_bad_zero(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            # GOOD known, BAD inferred as 0
            assert g.infer_bipolar_counterpart({"GOOD": 1}) == {"BAD": 0}

    def test_negative_good_still_zero_bad(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            # GOOD=-1 → still BAD=0 (never positive)
            assert g.infer_bipolar_counterpart({"GOOD": -1}) == {"BAD": 0}

    def test_no_inference_when_unknown_pole_present(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            # Both poles in external → no inference
            assert g.infer_bipolar_counterpart({"GOOD": 1, "BAD": 1}) == {}

    def test_skips_none_inferable_pairs(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            # TRUE/FALSE is None in BIPOLAR_INFERENCE
            assert g.infer_bipolar_counterpart({"TRUE": 1}) == {}

    def test_alive_to_dead(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            assert g.infer_bipolar_counterpart({"ALIVE": 1}) == {"DEAD": 0}


# ---------- get_primitives_to_query ----------


class TestGetPrimitivesToQuery:
    def test_default_returns_need_llm(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            result = g.get_primitives_to_query(1)
            # Should match NEED_LLM
            assert result == NEED_LLM

    def test_removes_inferred(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            # Insert GOOD external → BAD inferred → removed from to_query
            g.conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 'verbnet')")
            g.conn.commit()
            result = g.get_primitives_to_query(1)
            assert "BAD" not in result

    def test_removes_already_done(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            g.conn.execute("INSERT INTO primitive_values VALUES (1, 'BAD', 1, 0.7, 'llm:qwen')")
            g.conn.commit()
            result = g.get_primitives_to_query(1)
            assert "BAD" not in result


# ---------- query_primitive ----------


class TestQueryPrimitive:
    def test_yes_returns_1(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "YES"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("happy", "GOOD") == 1

    def test_y_returns_1(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "Y"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("happy", "GOOD") == 1

    def test_opposite_returns_minus_1(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "OPPOSITE"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("sad", "GOOD") == -1

    def test_opp_returns_minus_1(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "OPP"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("x", "Y") == -1

    def test_no_returns_0(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("x", "Y") == 0

    def test_unknown_returns_0(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "MAYBE"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("x", "Y") == 0

    def test_exception_returns_0(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.side_effect = RuntimeError("network")
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("x", "Y") == 0

    def test_lowercase_yes(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "yes"
            g = GapFiller(db_path=fresh_db)
            assert g.query_primitive("x", "Y") == 1


# ---------- process_word ----------


class TestProcessWord:
    def test_stores_inferred(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            g = GapFiller(db_path=fresh_db)
            # Insert GOOD=1 external → BAD inferred=0
            g.conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 'verbnet')")
            g.conn.commit()
            result = g.process_word(1, "happy")
            # BAD should be inferred as 0
            assert result.get("BAD") == 0
            # DB should have entry with source 'inferred:bipolar'
            cursor = g.conn.execute("SELECT source FROM primitive_values WHERE primitive='BAD'")
            sources = [r[0] for r in cursor.fetchall()]
            assert "inferred:bipolar" in sources

    def test_stores_llm_results(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "YES"
            g = GapFiller(db_path=fresh_db)
            g.process_word(1, "happy")
            # All NEED_LLM primitives should be queried and stored
            cursor = g.conn.execute("SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'llm:%'")
            count = cursor.fetchone()[0]
            assert count == len(NEED_LLM)


# ---------- process_batch ----------


class TestProcessBatch:
    def test_empty(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            g = GapFiller(db_path=fresh_db)
            stats = g.process_batch()
            assert stats["processed"] == 0

    def test_processes_words(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            g = GapFiller(db_path=fresh_db)
            g.conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 1)")
            g.conn.commit()
            stats = g.process_batch()
            assert stats["processed"] == 1

    def test_limit(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            g = GapFiller(db_path=fresh_db)
            for i in range(5):
                g.conn.execute("INSERT INTO lexemes VALUES (?, ?, ?)", (i, f"w{i}", i + 1))
            g.conn.commit()
            stats = g.process_batch(limit=2)
            assert stats["processed"] == 2

    def test_start_rank(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            g = GapFiller(db_path=fresh_db)
            for i in range(5):
                g.conn.execute("INSERT INTO lexemes VALUES (?, ?, ?)", (i, f"w{i}", i + 1))
            g.conn.commit()
            stats = g.process_batch(start_rank=3)
            # Starts at rank 3 → 3 words (ranks 3, 4, 5)
            assert stats["processed"] == 3


# ---------- close ----------


class TestClose:
    def test_closes_conn(self, fresh_db):
        with patch("gse.curation.llm.gap_filler.OllamaClient"):
            g = GapFiller(db_path=fresh_db)
            g.close()
            # After close, executing should fail
            with pytest.raises(sqlite3.ProgrammingError):
                g.conn.execute("SELECT 1")


# ---------- main ----------


class TestMain:
    def test_default_runs_batch(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--limit", "0"]):
            with patch("gse.curation.llm.gap_filler.OllamaClient"):
                with patch.object(
                    GapFiller, "process_batch", return_value={"processed": 0, "inferred": 0, "llm_queries": 0}
                ):
                    main()
        assert "GAP FILLING COMPLETE" in capsys.readouterr().out

    def test_word_arg_with_known_word(self, fresh_db, capsys):
        # Pre-populate lexeme
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 1)")
        conn.commit()
        conn.close()

        with patch("sys.argv", ["prog", "--db", fresh_db, "--word", "happy"]):
            with patch("gse.curation.llm.gap_filler.OllamaClient") as MockClient:
                MockClient.return_value.generate.return_value = "NO"
                main()
        out = capsys.readouterr().out
        assert "happy" in out

    def test_word_arg_not_found(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--word", "nonexistent"]):
            with patch("gse.curation.llm.gap_filler.OllamaClient"):
                main()
        out = capsys.readouterr().out
        assert "Word not found" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
