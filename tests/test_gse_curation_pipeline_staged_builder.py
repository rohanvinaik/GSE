"""Manual contract tests for gse.curation.pipeline.staged_builder."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.pipeline.staged_builder import (
    BuildStats,
    StagedBuilder,
    build_lexicon,
)


@pytest.fixture
def freq_db(tmp_path):
    """Build a small frequency database."""
    db_path = tmp_path / "freq.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE frequency (
            word TEXT PRIMARY KEY,
            combined_rank INTEGER,
            david47k_rank INTEGER,
            local_rank INTEGER,
            weight REAL
        )
    """)
    conn.executemany(
        "INSERT INTO frequency VALUES (?, ?, ?, ?, ?)",
        [
            ("the", 1, 1, 1, 1.0),
            ("happy", 500, 500, 500, 0.8),
            ("rare", 5000, 5000, 5000, 0.3),
        ],
    )
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def lex_path(tmp_path):
    return str(tmp_path / "lex.db")


def mk_builder(lex_path, freq_db):
    return StagedBuilder(
        lexicon_db_path=lex_path,
        frequency_db_path=freq_db,
        use_mock_llm=True,
    )


# ---------- BuildStats ----------

class TestBuildStats:
    def test_construction(self):
        s = BuildStats(
            phase=1, words_total=10, words_processed=8, words_validated=7,
            words_failed=1, words_review=0, duration_seconds=12.5,
        )
        assert s.phase == 1
        assert s.words_total == 10
        assert s.duration_seconds == 12.5

    def test_optional_timestamps(self):
        s = BuildStats(phase=1, words_total=0, words_processed=0,
                       words_validated=0, words_failed=0, words_review=0,
                       duration_seconds=0.0)
        assert s.started_at is None
        assert s.completed_at is None


# ---------- __init__ ----------

class TestInit:
    def test_basic(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        assert b.lexicon_db_path == lex_path
        assert b.freq_db_path == freq_db
        b.close()

    def test_uses_mock_llm(self, lex_path, freq_db):
        b = StagedBuilder(
            lexicon_db_path=lex_path,
            frequency_db_path=freq_db,
            use_mock_llm=True,
        )
        # MockQwenClient
        assert b.llm.__class__.__name__ == "MockQwenClient"
        b.close()

    def test_real_llm_when_not_mock(self, lex_path, freq_db):
        with patch("gse.curation.pipeline.staged_builder.OllamaClient") as MockClient:
            b = StagedBuilder(
                lexicon_db_path=lex_path,
                frequency_db_path=freq_db,
                use_mock_llm=False,
            )
            MockClient.assert_called_once()
            b.close()

    def test_default_freq_db_uses_helper(self, lex_path):
        with patch("gse.curation.frequency_integration.get_default_frequency_db_path",
                   return_value=lex_path):
            # Get the real func to return something usable
            with patch("gse.curation.pipeline.staged_builder.FrequencyDatabase"):
                b = StagedBuilder(
                    lexicon_db_path=lex_path,
                    use_mock_llm=True,
                )
                b.close()


# ---------- close ----------

class TestClose:
    def test_closes_all(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.close()
        # lexicon_db conn closed
        with pytest.raises(sqlite3.ProgrammingError):
            b.lexicon_db.conn.execute("SELECT 1")


# ---------- context manager ----------

class TestContextManager:
    def test_context_closes(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        with b:
            assert b.lexicon_db.conn is not None
        # After exit
        with pytest.raises(sqlite3.ProgrammingError):
            b.lexicon_db.conn.execute("SELECT 1")


# ---------- initialize_from_frequency ----------

class TestInitializeFromFrequency:
    def test_default_phases(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.initialize_from_frequency()
        # Should have added words across all 3 phases
        stats = b.lexicon_db.get_stats()
        assert stats["total_lexemes"] > 0
        b.close()

    def test_specific_phase(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.initialize_from_frequency([1])
        # Only phase 1 (ranks 1-1000) → "the" and "happy"
        count = b.lexicon_db.count_by_phase(1)
        assert count["total"] == 2
        b.close()

    def test_phase_3_includes_all_high_rank(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.initialize_from_frequency([3])
        # Phase 3 = 3001+ → "rare"
        count = b.lexicon_db.count_by_phase(3)
        assert count["total"] == 1
        b.close()


# ---------- build_phase_one ----------

class TestBuildPhaseOne:
    def test_auto_initializes(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        # No words yet → should initialize from freq
        b.processor = MagicMock()
        b.processor.process_phase.return_value = {
            "processed": 0, "validated": 0, "failed": 0, "review_flagged": 0,
        }
        stats = b.build_phase_one()
        # Phase 1 was initialized
        assert b.lexicon_db.count_by_phase(1)["total"] > 0
        assert isinstance(stats, BuildStats)
        b.close()

    def test_returns_build_stats(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.processor = MagicMock()
        b.processor.process_phase.return_value = {
            "processed": 2, "validated": 2, "failed": 0, "review_flagged": 0,
        }
        stats = b.build_phase_one()
        assert stats.phase == 1
        assert stats.words_processed == 2
        b.close()

    def test_stores_in_stats_dict(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.processor = MagicMock()
        b.processor.process_phase.return_value = {
            "processed": 1, "validated": 1, "failed": 0, "review_flagged": 0,
        }
        b.build_phase_one()
        assert 1 in b.stats
        b.close()


# ---------- build_phase_two ----------

class TestBuildPhaseTwo:
    def test_basic(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.processor = MagicMock()
        b.processor.process_phase.return_value = {
            "processed": 0, "validated": 0, "failed": 0, "review_flagged": 0,
        }
        stats = b.build_phase_two()
        assert stats.phase == 2
        b.close()


# ---------- build_phase_three ----------

class TestBuildPhaseThree:
    def test_basic(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.processor = MagicMock()
        b.processor.process_phase.return_value = {
            "processed": 0, "validated": 0, "failed": 0, "review_flagged": 0,
        }
        stats = b.build_phase_three()
        assert stats.phase == 3
        b.close()


# ---------- build_all ----------

class TestBuildAll:
    def test_runs_all_phases(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        b.processor = MagicMock()
        b.processor.process_phase.return_value = {
            "processed": 0, "validated": 0, "failed": 0, "review_flagged": 0,
        }
        result = b.build_all()
        assert 1 in result
        assert 2 in result
        assert 3 in result
        b.close()


# ---------- get_status ----------

class TestGetStatus:
    def test_empty(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        status = b.get_status()
        assert status["total"]["words"] == 0
        assert status["total"]["validation_rate"] == 0
        b.close()

    def test_with_data(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        lex_id = b.lexicon_db.add_lexeme(lemma="x", pos="n", phase=1)
        b.lexicon_db.update_lexeme(lex_id, validation_status="validated")
        status = b.get_status()
        assert status["total"]["words"] == 1
        assert status["total"]["validated"] == 1
        assert status["total"]["validation_rate"] == 100.0
        b.close()

    def test_partial_validation(self, lex_path, freq_db):
        b = mk_builder(lex_path, freq_db)
        lex_a = b.lexicon_db.add_lexeme(lemma="a", pos="n", phase=1)
        b.lexicon_db.update_lexeme(lex_a, validation_status="validated")
        b.lexicon_db.add_lexeme(lemma="b", pos="n", phase=1)  # pending
        status = b.get_status()
        assert status["total"]["validation_rate"] == 50.0
        b.close()


# ---------- build_lexicon convenience ----------

class TestBuildLexicon:
    def test_default_all_phases(self, lex_path, freq_db):
        with patch.object(StagedBuilder, "build_phase_one") as p1:
            with patch.object(StagedBuilder, "build_phase_two") as p2:
                with patch.object(StagedBuilder, "build_phase_three") as p3:
                    result = build_lexicon(
                        lexicon_db_path=lex_path,
                        frequency_db_path=freq_db,
                        use_mock=True,
                    )
                    p1.assert_called_once()
                    p2.assert_called_once()
                    p3.assert_called_once()
        assert "total" in result

    def test_phases_filter(self, lex_path, freq_db):
        with patch.object(StagedBuilder, "build_phase_one") as p1:
            with patch.object(StagedBuilder, "build_phase_two") as p2:
                with patch.object(StagedBuilder, "build_phase_three") as p3:
                    build_lexicon(
                        lexicon_db_path=lex_path,
                        frequency_db_path=freq_db,
                        phases=[1],
                        use_mock=True,
                    )
                    p1.assert_called_once()
                    p2.assert_not_called()
                    p3.assert_not_called()

    def test_returns_status(self, lex_path, freq_db):
        with patch.object(StagedBuilder, "build_phase_one"):
            with patch.object(StagedBuilder, "build_phase_two"):
                with patch.object(StagedBuilder, "build_phase_three"):
                    result = build_lexicon(
                        lexicon_db_path=lex_path,
                        frequency_db_path=freq_db,
                        use_mock=True,
                    )
        assert "phases" in result
        assert "total" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
