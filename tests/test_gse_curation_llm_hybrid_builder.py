"""Manual contract tests for gse.curation.llm.hybrid_builder."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.hybrid_builder import (
    BuilderStats,
    HybridLexiconBuilder,
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


def mk_builder(fresh_db):
    """Make a builder with both clients mocked."""
    with patch("gse.curation.llm.hybrid_builder.OllamaClient") as MockClient:
        b = HybridLexiconBuilder(db_path=fresh_db)
        # Get the two distinct mock instances
        # OllamaClient was called twice (fast + validator)
        b.fast_client = MagicMock()
        b.validator_client = MagicMock()
    return b


# ---------- BuilderStats ----------

class TestBuilderStats:
    def test_defaults(self):
        s = BuilderStats()
        assert s.words_processed == 0
        assert s.errors == 0

    def test_str_format(self):
        s = BuilderStats(words_processed=5, primitives_fast_filled=10,
                         primitives_validated=3, primitives_corrected=1)
        result = str(s)
        assert "Processed: 5" in result
        assert "Fast-filled: 10" in result
        assert "Validated: 3" in result
        assert "Corrected: 1" in result


# ---------- __init__ ----------

class TestInit:
    def test_default_models(self, fresh_db):
        with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
            b = HybridLexiconBuilder(db_path=fresh_db)
            assert b.fast_model == "qwen2.5:7b"
            assert b.validator_model == "qwen3:32b"

    def test_validation_threshold_default(self, fresh_db):
        with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
            b = HybridLexiconBuilder(db_path=fresh_db)
            assert b.validation_threshold == 0.6

    def test_fast_config(self, fresh_db):
        with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
            b = HybridLexiconBuilder(db_path=fresh_db)
            assert b.fast_config.temperature == 0.1
            assert b.fast_config.max_tokens == 20

    def test_validator_config(self, fresh_db):
        with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
            b = HybridLexiconBuilder(db_path=fresh_db)
            assert b.validator_config.temperature == 0.3
            assert b.validator_config.max_tokens == 200

    def test_stats_initialized(self, fresh_db):
        with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
            b = HybridLexiconBuilder(db_path=fresh_db)
            assert isinstance(b.stats, BuilderStats)


# ---------- fast_match_bipolar ----------

class TestFastMatchBipolar:
    def test_response_a(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "A"
        result = b.fast_match_bipolar("happy", "GOOD", "BAD")
        assert result == (1, 0, 0.8)

    def test_response_b(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "B"
        result = b.fast_match_bipolar("sad", "GOOD", "BAD")
        assert result == (0, 1, 0.8)

    def test_response_neither(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NEITHER"
        result = b.fast_match_bipolar("x", "GOOD", "BAD")
        assert result == (0, 0, 0.9)

    def test_response_c(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "C"
        result = b.fast_match_bipolar("x", "GOOD", "BAD")
        assert result == (0, 0, 0.9)

    def test_ambiguous_pole_a(self, fresh_db):
        # Contains pole_a upper but doesn't start with A
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "the GOOD answer"
        result = b.fast_match_bipolar("x", "GOOD", "BAD")
        assert result == (1, 0, 0.5)

    def test_ambiguous_pole_b(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "the BAD answer"
        result = b.fast_match_bipolar("x", "GOOD", "BAD")
        assert result == (0, 1, 0.5)

    def test_very_uncertain(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "unknown"
        result = b.fast_match_bipolar("x", "GOOD", "BAD")
        assert result == (0, 0, 0.4)

    def test_exception_returns_zero(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.side_effect = RuntimeError("boom")
        result = b.fast_match_bipolar("x", "GOOD", "BAD")
        assert result == (0, 0, 0.0)


# ---------- fast_match_single ----------

class TestFastMatchSingle:
    def test_yes(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "YES"
        assert b.fast_match_single("x", "GOOD") == (1, 0.8)

    def test_y(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "Y"
        assert b.fast_match_single("x", "GOOD") == (1, 0.8)

    def test_opposite(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "OPPOSITE"
        assert b.fast_match_single("x", "GOOD") == (-1, 0.75)

    def test_no(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NO"
        assert b.fast_match_single("x", "GOOD") == (0, 0.85)

    def test_n(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "N"
        assert b.fast_match_single("x", "GOOD") == (0, 0.85)

    def test_ambiguous_yes(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "maybe YES somewhere"
        # Doesn't start with YES/Y but contains YES
        assert b.fast_match_single("x", "GOOD") == (1, 0.5)

    def test_unknown(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "MAYBE"
        assert b.fast_match_single("x", "GOOD") == (0, 0.3)

    def test_exception_zero(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.side_effect = RuntimeError("boom")
        assert b.fast_match_single("x", "GOOD") == (0, 0.0)


# ---------- fast_decompose ----------

class TestFastDecompose:
    def test_bipolar_pairs_processed(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "A"
        # Include GOOD (a bipolar pair member) in missing
        result = b.fast_decompose("happy", {"GOOD"})
        assert "GOOD" in result

    def test_single_primitives_processed(self, fresh_db):
        # NOT is a single primitive
        from gse.curation.llm.primitive_matcher import SINGLE_PRIMITIVES
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "YES"
        # Take first single primitive
        first_single = next(iter(SINGLE_PRIMITIVES))
        result = b.fast_decompose("x", {first_single})
        assert first_single in result

    def test_empty_missing(self, fresh_db):
        b = mk_builder(fresh_db)
        result = b.fast_decompose("x", set())
        assert result == {}


# ---------- get_missing_primitives ----------

class TestGetMissingPrimitives:
    def test_all_missing(self, fresh_db):
        from gse.curation.schema import ALL_PRIMITIVES
        b = mk_builder(fresh_db)
        assert b.get_missing_primitives(1) == set(ALL_PRIMITIVES)

    def test_excludes_filled(self, fresh_db):
        b = mk_builder(fresh_db)
        b.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'GOOD', 1, 0.9, 'verbnet')"
        )
        b.conn.commit()
        missing = b.get_missing_primitives(1)
        assert "GOOD" not in missing


# ---------- validate_decomposition ----------

class TestValidateDecomposition:
    def test_no_low_confidence_skips_validation(self, fresh_db):
        b = mk_builder(fresh_db)
        # All high confidence → skip
        primitives = {"GOOD": (1, 0.9)}
        result = b.validate_decomposition("x", primitives)
        assert result == {"GOOD": 1}
        # validator not called
        b.validator_client.generate.assert_not_called()

    def test_zero_value_not_validated(self, fresh_db):
        b = mk_builder(fresh_db)
        # value=0 → not eligible for validation
        primitives = {"GOOD": (0, 0.3)}
        result = b.validate_decomposition("x", primitives)
        assert result == {"GOOD": 0}

    def test_correct_judgment_keeps_value(self, fresh_db):
        b = mk_builder(fresh_db)
        b.validator_client.generate.return_value = '{"GOOD": "CORRECT"}'
        primitives = {"GOOD": (1, 0.3)}
        result = b.validate_decomposition("x", primitives)
        assert result["GOOD"] == 1

    def test_wrong_judgment_corrects(self, fresh_db):
        b = mk_builder(fresh_db)
        b.validator_client.generate.return_value = '{"GOOD": "WRONG:-1"}'
        primitives = {"GOOD": (1, 0.3)}
        result = b.validate_decomposition("x", primitives)
        assert result["GOOD"] == -1

    def test_wrong_invalid_format_ignored(self, fresh_db):
        b = mk_builder(fresh_db)
        b.validator_client.generate.return_value = '{"GOOD": "WRONG:invalid"}'
        primitives = {"GOOD": (1, 0.3)}
        result = b.validate_decomposition("x", primitives)
        # Value unchanged
        assert result["GOOD"] == 1

    def test_exception_returns_original(self, fresh_db):
        b = mk_builder(fresh_db)
        b.validator_client.generate.side_effect = RuntimeError("boom")
        primitives = {"GOOD": (1, 0.3)}
        result = b.validate_decomposition("x", primitives)
        assert result == {"GOOD": 1}

    def test_no_json_in_response(self, fresh_db):
        b = mk_builder(fresh_db)
        b.validator_client.generate.return_value = "no json here"
        primitives = {"GOOD": (1, 0.3)}
        result = b.validate_decomposition("x", primitives)
        # Falls through to fallback returning originals
        assert result == {"GOOD": 1}


# ---------- process_word ----------

class TestProcessWord:
    def test_all_filled_returns_empty(self, fresh_db):
        from gse.curation.schema import ALL_PRIMITIVES
        b = mk_builder(fresh_db)
        # Fill all primitives
        for p in ALL_PRIMITIVES:
            b.conn.execute(
                "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
                "VALUES (1, ?, 0, 0.5, 's')",
                (p,),
            )
        b.conn.commit()
        result = b.process_word(1, "happy")
        assert result == {}

    def test_fast_only_no_validation(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NO"
        result = b.process_word(1, "happy", validate=False)
        # validator not called
        b.validator_client.generate.assert_not_called()
        assert isinstance(result, dict)

    def test_stores_results_in_db(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NO"
        b.process_word(1, "happy", validate=False)
        cursor = b.conn.execute("SELECT COUNT(*) FROM primitive_values")
        count = cursor.fetchone()[0]
        assert count > 0

    def test_increments_words_processed(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NO"
        b.process_word(1, "happy", validate=False)
        assert b.stats.words_processed == 1


# ---------- process_batch ----------

class TestProcessBatch:
    def test_no_words(self, fresh_db):
        b = mk_builder(fresh_db)
        stats = b.process_batch()
        assert stats.words_processed == 0

    def test_processes_words(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NO"
        b.conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 1)")
        b.conn.commit()
        stats = b.process_batch(min_missing=10, validate=False)
        assert stats.words_processed == 1

    def test_min_missing_filter(self, fresh_db):
        b = mk_builder(fresh_db)
        b.conn.execute("INSERT INTO lexemes VALUES (1, 'x', 1)")
        # Fill almost all primitives (only 5 missing)
        from gse.curation.schema import ALL_PRIMITIVES
        for p in list(ALL_PRIMITIVES)[:67]:
            b.conn.execute(
                "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
                "VALUES (1, ?, 0, 0.5, 's')",
                (p,),
            )
        b.conn.commit()
        # 5 missing < min_missing=10 → not processed
        stats = b.process_batch(min_missing=10, validate=False)
        assert stats.words_processed == 0

    def test_limit(self, fresh_db):
        b = mk_builder(fresh_db)
        b.fast_client.generate.return_value = "NO"
        for i in range(5):
            b.conn.execute("INSERT INTO lexemes VALUES (?, ?, ?)", (i, f"w{i}", i))
        b.conn.commit()
        stats = b.process_batch(limit=2, min_missing=10, validate=False)
        assert stats.words_processed == 2

    def test_exception_in_word_increments_errors(self, fresh_db):
        b = mk_builder(fresh_db)
        b.conn.execute("INSERT INTO lexemes VALUES (1, 'x', 1)")
        b.conn.commit()
        with patch.object(b, "process_word", side_effect=RuntimeError("boom")):
            stats = b.process_batch(min_missing=10, validate=False)
            assert stats.errors == 1


# ---------- close ----------

class TestClose:
    def test_closes_conn(self, fresh_db):
        b = mk_builder(fresh_db)
        b.close()
        with pytest.raises(sqlite3.ProgrammingError):
            b.conn.execute("SELECT 1")


# ---------- main ----------

class TestMain:
    def test_default_batch_run(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--limit", "0"]):
            with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
                with patch.object(HybridLexiconBuilder, "process_batch",
                                  return_value=BuilderStats()):
                    main()
        assert "HYBRID BUILD COMPLETE" in capsys.readouterr().out

    def test_word_arg_not_found(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--word", "missing"]):
            with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
                main()
        assert "Word not found" in capsys.readouterr().out

    def test_word_arg_found(self, fresh_db, capsys):
        # Pre-insert a word
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 1)")
        conn.commit()
        conn.close()
        with patch("sys.argv", ["prog", "--db", fresh_db, "--word", "happy"]):
            with patch("gse.curation.llm.hybrid_builder.OllamaClient"):
                with patch.object(HybridLexiconBuilder, "process_word",
                                  return_value={"GOOD": 1}):
                    main()
        assert "happy" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
