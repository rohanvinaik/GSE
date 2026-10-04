"""Manual contract tests for gse.curation.llm.primitive_matcher."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.primitive_matcher import (
    BIPOLAR_PAIRS,
    MATCHER_SYSTEM,
    SINGLE_PRIMITIVES,
    CommonSensePostProcessor,
    MatchResult,
    PrimitiveMatcher,
    get_bipolar_prompt,
    get_single_prompt,
    run_batch,
)

# Imported under another name: a bare `test_matcher` is collected by pytest as a module-level test and
# runs the production smoke check unmocked, 36 generate() calls against whatever Ollama is serving.
from gse.curation.llm.primitive_matcher import test_matcher as smoke_check_matcher


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


def mk_matcher(fresh_db=None):
    with patch("gse.curation.llm.primitive_matcher.OllamaClient"):
        m = PrimitiveMatcher(db_path=fresh_db)
        m.client = MagicMock()
        return m


# ---------- BIPOLAR_PAIRS, SINGLE_PRIMITIVES ----------


class TestConstants:
    def test_bipolar_pair_count(self):
        assert len(BIPOLAR_PAIRS) == 14

    def test_good_bad_in_bipolar(self):
        assert ("GOOD", "BAD") in BIPOLAR_PAIRS

    def test_single_primitives_non_empty(self):
        assert len(SINGLE_PRIMITIVES) > 0

    def test_someone_in_single(self):
        assert "SOMEONE" in SINGLE_PRIMITIVES

    def test_matcher_system_short(self):
        # Brief system prompt
        assert len(MATCHER_SYSTEM) < 200


# ---------- get_bipolar_prompt ----------


class TestGetBipolarPrompt:
    def test_includes_word_and_poles(self):
        result = get_bipolar_prompt("happy", "GOOD", "BAD")
        assert "happy" in result
        assert "GOOD" in result
        assert "BAD" in result

    def test_letter_options(self):
        result = get_bipolar_prompt("x", "GOOD", "BAD")
        assert "A)" in result
        assert "B)" in result
        assert "C)" in result

    def test_word_quoted(self):
        result = get_bipolar_prompt("happy", "GOOD", "BAD")
        assert '"happy"' in result

    def test_neither_option(self):
        result = get_bipolar_prompt("x", "GOOD", "BAD")
        assert "Neither" in result

    def test_exact_which_applies_line(self):
        result = get_bipolar_prompt("x", "GOOD", "BAD")
        assert "Which applies? Answer with just the letter:" in result

    def test_exact_answer_prompt(self):
        result = get_bipolar_prompt("x", "GOOD", "BAD")
        # Ends with "Answer:" line
        assert "Answer:" in result

    def test_exact_pole_description_format(self):
        # "A) GOOD - the word leans toward GOOD"
        result = get_bipolar_prompt("x", "GOOD", "BAD")
        assert "A) GOOD - the word leans toward GOOD" in result
        assert "B) BAD - the word leans toward BAD" in result


# ---------- get_single_prompt ----------


class TestGetSinglePrompt:
    def test_includes_word_and_primitive(self):
        result = get_single_prompt("happy", "GOOD")
        assert "happy" in result
        assert "GOOD" in result

    def test_includes_answer_options(self):
        result = get_single_prompt("x", "Y")
        assert "YES" in result
        assert "NO" in result
        assert "OPPOSITE" in result

    def test_exact_does_word_involve_line(self):
        result = get_single_prompt("happy", "GOOD")
        assert "Does this word's meaning involve GOOD?" in result

    def test_exact_answer_format(self):
        result = get_single_prompt("x", "Y")
        assert "Answer with just: YES, NO, or OPPOSITE" in result

    def test_word_quoted_primitive_unquoted(self):
        result = get_single_prompt("happy", "GOOD")
        assert 'Word: "happy"' in result
        assert "Primitive: GOOD" in result


# ---------- MatchResult ----------


class TestMatchResult:
    def test_construction(self):
        r = MatchResult(word="x", primitive="GOOD", value=1, raw_response="YES")
        assert r.value == 1


# ---------- __init__ ----------


class TestInit:
    def test_defaults(self):
        with patch("gse.curation.llm.primitive_matcher.OllamaClient"):
            m = PrimitiveMatcher()
            assert m.model == "qwen2.5:7b"
            assert m.temperature == 0.1
            assert m.timeout == 30
            assert m.db_path is None
            assert m.conn is None

    def test_with_db(self, fresh_db):
        with patch("gse.curation.llm.primitive_matcher.OllamaClient"):
            m = PrimitiveMatcher(db_path=fresh_db)
            assert m.db_path == fresh_db
            assert m.conn is not None


# ---------- match_bipolar ----------


class TestMatchBipolar:
    def test_a_response(self):
        m = mk_matcher()
        m.client.generate.return_value = "A"
        assert m.match_bipolar("happy", "GOOD", "BAD") == (1, 0)

    def test_b_response(self):
        m = mk_matcher()
        m.client.generate.return_value = "B"
        assert m.match_bipolar("sad", "GOOD", "BAD") == (0, 1)

    def test_neither(self):
        m = mk_matcher()
        m.client.generate.return_value = "C"
        assert m.match_bipolar("x", "GOOD", "BAD") == (0, 0)

    def test_pole_name_match(self):
        m = mk_matcher()
        m.client.generate.return_value = "the answer is GOOD"
        assert m.match_bipolar("x", "GOOD", "BAD") == (1, 0)

    def test_exception_zero(self):
        m = mk_matcher()
        m.client.generate.side_effect = RuntimeError("boom")
        assert m.match_bipolar("x", "GOOD", "BAD") == (0, 0)


# ---------- match_single ----------


class TestMatchSingle:
    def test_yes(self):
        m = mk_matcher()
        m.client.generate.return_value = "YES"
        assert m.match_single("happy", "GOOD") == 1

    def test_opposite(self):
        m = mk_matcher()
        m.client.generate.return_value = "OPPOSITE"
        assert m.match_single("x", "Y") == -1

    def test_opp(self):
        m = mk_matcher()
        m.client.generate.return_value = "OPP"
        assert m.match_single("x", "Y") == -1

    def test_no(self):
        m = mk_matcher()
        m.client.generate.return_value = "NO"
        assert m.match_single("x", "Y") == 0

    def test_exception_zero(self):
        m = mk_matcher()
        m.client.generate.side_effect = RuntimeError("boom")
        assert m.match_single("x", "Y") == 0


# ---------- decompose_word ----------


class TestDecomposeWord:
    def test_decomposes_all_primitives(self):
        m = mk_matcher()
        m.client.generate.return_value = "NO"
        result = m.decompose_word("x")
        # All 14 bipolar pairs (28 primitives) + SINGLE_PRIMITIVES
        expected_count = len(BIPOLAR_PAIRS) * 2 + len(SINGLE_PRIMITIVES)
        assert len(result) == expected_count

    def test_all_keys_present(self):
        m = mk_matcher()
        m.client.generate.return_value = "NO"
        result = m.decompose_word("x")
        for pole_a, pole_b in BIPOLAR_PAIRS:
            assert pole_a in result
            assert pole_b in result
        for prim in SINGLE_PRIMITIVES:
            assert prim in result


# ---------- decompose_word_fast ----------


class TestDecomposeWordFast:
    def test_skip_zeros_default(self):
        m = mk_matcher()
        m.client.generate.return_value = "NO"
        result = m.decompose_word_fast("x")
        # All zero → empty result
        assert result == {}

    def test_skip_zeros_keeps_non_zero(self):
        m = mk_matcher()
        m.client.generate.return_value = "YES"
        result = m.decompose_word_fast("x")
        # Yes triggers val=1 for singles
        assert any(v == 1 for v in result.values())

    def test_no_skip_zeros(self):
        m = mk_matcher()
        m.client.generate.return_value = "NO"
        result = m.decompose_word_fast("x", skip_zeros=False)
        # Should fill all primitives even if zero
        assert len(result) > 0


# ---------- get_missing_primitives ----------


class TestGetMissingPrimitives:
    def test_no_db_returns_all(self):
        m = mk_matcher()
        # No db connection
        m.conn = None
        result = m.get_missing_primitives(1)
        # All primitives returned as missing
        assert len(result) > 0

    def test_excludes_filled(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'GOOD', 1, 0.9, 'verbnet')"
        )
        m.conn.commit()
        missing = m.get_missing_primitives(1)
        assert "GOOD" not in missing


# ---------- process_word_to_db ----------


class TestProcessWordToDB:
    def test_raises_without_conn(self):
        m = mk_matcher()
        m.conn = None
        with pytest.raises(ValueError, match="Database connection"):
            m.process_word_to_db(1, "happy")

    def test_processes_and_stores(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.client.generate.return_value = "NO"
        result = m.process_word_to_db(1, "happy")
        # Should have entries in DB
        cursor = m.conn.execute("SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'llm:%'")
        assert cursor.fetchone()[0] > 0
        assert len(result) > 0

    def test_no_skip_filled_processes_all(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.client.generate.return_value = "NO"
        # Pre-fill GOOD
        m.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'GOOD', 1, 0.9, 'verbnet')"
        )
        m.conn.commit()
        result = m.process_word_to_db(1, "happy", skip_filled=False)
        # GOOD is in result (not skipped)
        assert "GOOD" in result


# ---------- process_batch ----------


class TestProcessBatch:
    def test_raises_without_conn(self):
        m = mk_matcher()
        m.conn = None
        with pytest.raises(ValueError, match="Database connection"):
            m.process_batch()

    def test_no_words(self, fresh_db):
        m = mk_matcher(fresh_db)
        stats = m.process_batch()
        assert stats["processed"] == 0

    def test_processes_words(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.client.generate.return_value = "NO"
        m.conn.execute("INSERT INTO lexemes VALUES (1, 'x', 'n', 1)")
        m.conn.commit()
        stats = m.process_batch(min_missing=10)
        assert stats["processed"] == 1

    def test_limit(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.client.generate.return_value = "NO"
        for i in range(5):
            m.conn.execute("INSERT INTO lexemes VALUES (?, ?, 'n', ?)", (i, f"w{i}", i))
        m.conn.commit()
        stats = m.process_batch(limit=2, min_missing=10)
        assert stats["processed"] == 2

    def test_exception_in_word_errors(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.conn.execute("INSERT INTO lexemes VALUES (1, 'x', 'n', 1)")
        m.conn.commit()
        with patch.object(m, "process_word_to_db", side_effect=RuntimeError("boom")):
            stats = m.process_batch(min_missing=10)
            assert stats["errors"] == 1


# ---------- close ----------


class TestClose:
    def test_with_conn(self, fresh_db):
        m = mk_matcher(fresh_db)
        m.close()
        with pytest.raises(sqlite3.ProgrammingError):
            m.conn.execute("SELECT 1")

    def test_without_conn_safe(self):
        m = mk_matcher()
        m.conn = None
        # Should not raise
        m.close()


# ---------- CommonSensePostProcessor ----------


class TestCommonSensePostProcessor:
    def test_init(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        assert p.conn is not None

    def test_no_violations(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        assert p.fix_bipolar_violations() == 0

    def test_fix_bipolar_higher_conf_a(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        # GOOD with high conf, BAD with low conf → BAD zeroed
        p.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'GOOD', 1, 0.9, 's')"
        )
        p.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'BAD', 1, 0.3, 's')"
        )
        p.conn.commit()
        fixed = p.fix_bipolar_violations()
        assert fixed == 1
        # BAD zeroed
        cursor = p.conn.execute("SELECT value FROM primitive_values WHERE primitive = 'BAD'")
        assert cursor.fetchone()[0] == 0

    def test_fix_bipolar_higher_conf_b(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        # GOOD low, BAD high → GOOD zeroed
        p.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'GOOD', 1, 0.3, 's')"
        )
        p.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'BAD', 1, 0.9, 's')"
        )
        p.conn.commit()
        p.fix_bipolar_violations()
        cursor = p.conn.execute("SELECT value FROM primitive_values WHERE primitive = 'GOOD'")
        assert cursor.fetchone()[0] == 0

    def test_apply_pos_rules_verbs(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        # Verb with HAPPEN set (unlikely... wait HAPPEN is in 'likely' for verbs)
        # Actually verbs have ["DO", "HAPPEN"] as likely; no unlikely
        # Use adj with DO unlikely
        p.conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 'adj', 1)")
        p.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'DO', 1, 0.5, 's')"
        )
        p.conn.commit()
        updated = p.apply_pos_rules()
        # 0.5 < 0.8 + adj unlikely DO → zero out
        assert updated == 1

    def test_pos_rules_high_conf_not_changed(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        p.conn.execute("INSERT INTO lexemes VALUES (1, 'happy', 'adj', 1)")
        p.conn.execute(
            "INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source) "
            "VALUES (1, 'DO', 1, 0.95, 's')"
        )
        p.conn.commit()
        updated = p.apply_pos_rules()
        # 0.95 >= 0.8 → not changed
        assert updated == 0

    def test_run_all_returns_stats(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        stats = p.run_all()
        assert "bipolar_fixed" in stats
        assert "pos_rules_applied" in stats

    def test_close(self, fresh_db):
        p = CommonSensePostProcessor(fresh_db)
        p.close()
        with pytest.raises(sqlite3.ProgrammingError):
            p.conn.execute("SELECT 1")


# ---------- test_matcher / run_batch entrypoints ----------


class TestEntrypoints:
    def test_test_matcher_runs(self, capsys):
        with patch("gse.curation.llm.primitive_matcher.OllamaClient") as MockClient:
            MockClient.return_value.generate.return_value = "NO"
            smoke_check_matcher()
        # Should print at least the test words
        out = capsys.readouterr().out
        assert "love" in out

    def test_run_batch_basic(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--limit", "0"]):
            with patch("gse.curation.llm.primitive_matcher.OllamaClient"):
                with patch.object(
                    PrimitiveMatcher,
                    "process_batch",
                    return_value={"processed": 0, "primitives_filled": 0, "errors": 0},
                ):
                    run_batch()
        assert "Batch Complete" in capsys.readouterr().out

    def test_run_batch_post_process(self, fresh_db, capsys):
        with patch("sys.argv", ["prog", "--db", fresh_db, "--post-process", "--limit", "0"]):
            with patch("gse.curation.llm.primitive_matcher.OllamaClient"):
                with patch.object(
                    PrimitiveMatcher,
                    "process_batch",
                    return_value={"processed": 0, "primitives_filled": 0, "errors": 0},
                ):
                    run_batch()
        assert "Post-Processing" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
