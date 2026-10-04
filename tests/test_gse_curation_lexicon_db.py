"""Manual contract tests for gse.curation.lexicon_db."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.lexicon_db import (
    LexemeEntry,
    LexiconDatabase,
    ValidationResult,
)
from gse.curation.schema import ALL_PRIMITIVES


@pytest.fixture
def db(tmp_path):
    """Build a fresh lexicon database."""
    db_path = tmp_path / "lex.db"
    return LexiconDatabase(str(db_path))


# ---------- LexemeEntry ----------


class TestLexemeEntry:
    def test_construction(self):
        e = LexemeEntry(
            id=1,
            lemma="happy",
            pos="adj",
            sense_id="01",
            gloss="feeling good",
            source="llm",
            confidence=0.9,
            frequency_rank=10,
            frequency_weight=0.8,
            phase=1,
            validation_status="validated",
        )
        assert e.lemma == "happy"
        assert e.decomposition == {}
        assert e.primitive_confidences == {}


# ---------- ValidationResult ----------


class TestValidationResult:
    def test_defaults(self):
        r = ValidationResult(passed=True, validation_type="x")
        assert r.passed is True
        assert r.violations == []
        assert r.details is None


# ---------- __init__ ----------


class TestInit:
    def test_creates_db(self, tmp_path):
        path = tmp_path / "lex.db"
        db = LexiconDatabase(str(path))
        assert path.exists()
        db.close()

    def test_default_path(self, tmp_path, monkeypatch):
        # Change to tmp_path so default "lexicon.db" is created there
        monkeypatch.chdir(tmp_path)
        db = LexiconDatabase()
        assert db.db_path.name == "lexicon.db"
        db.close()


# ---------- add_lexeme ----------


class TestAddLexeme:
    def test_basic(self, db):
        lex_id = db.add_lexeme(lemma="happy", pos="adj")
        assert lex_id > 0

    def test_returns_lastrowid(self, db):
        id1 = db.add_lexeme(lemma="a", pos="n")
        id2 = db.add_lexeme(lemma="b", pos="n")
        assert id2 == id1 + 1

    def test_defaults(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        cursor = db.conn.execute("SELECT * FROM lexemes WHERE id = ?", (lex_id,))
        row = cursor.fetchone()
        assert row["sense_id"] == "01"
        assert row["source"] == "llm"
        assert row["confidence"] == 1.0
        assert row["phase"] == 0


# ---------- get_lexeme ----------


class TestGetLexeme:
    def test_returns_entry(self, db):
        lex_id = db.add_lexeme(lemma="happy", pos="adj")
        result = db.get_lexeme("happy")
        assert result is not None
        assert result.id == lex_id
        assert result.lemma == "happy"

    def test_with_pos_filter(self, db):
        db.add_lexeme(lemma="bear", pos="n")
        db.add_lexeme(lemma="bear", pos="v")
        result = db.get_lexeme("bear", pos="v")
        assert result.pos == "v"

    def test_not_found(self, db):
        assert db.get_lexeme("nonexistent") is None

    def test_fills_decomposition(self, db):
        lex_id = db.add_lexeme(lemma="happy", pos="adj")
        db.set_decomposition(lex_id, {"GOOD": 1})
        result = db.get_lexeme("happy")
        assert result.decomposition["GOOD"] == 1


# ---------- get_lexeme_by_id ----------


class TestGetLexemeByID:
    def test_found(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        result = db.get_lexeme_by_id(lex_id)
        assert result.id == lex_id

    def test_not_found(self, db):
        assert db.get_lexeme_by_id(999) is None


# ---------- update_lexeme ----------


class TestUpdateLexeme:
    def test_update_status(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.update_lexeme(lex_id, validation_status="validated")
        result = db.get_lexeme_by_id(lex_id)
        assert result.validation_status == "validated"

    def test_update_confidence(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.update_lexeme(lex_id, confidence=0.5)
        result = db.get_lexeme_by_id(lex_id)
        assert result.confidence == 0.5

    def test_update_source(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.update_lexeme(lex_id, source="manual")
        result = db.get_lexeme_by_id(lex_id)
        assert result.source == "manual"

    def test_update_gloss(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.update_lexeme(lex_id, gloss="new definition")
        result = db.get_lexeme_by_id(lex_id)
        assert result.gloss == "new definition"

    def test_no_op_when_all_none(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        # All None → should not run UPDATE
        db.update_lexeme(lex_id)
        # No error


# ---------- update_frequency ----------


class TestUpdateFrequency:
    def test_basic(self, db):
        db.add_lexeme(lemma="x", pos="n")
        db.update_frequency("x", 100, 0.5)
        result = db.get_lexeme("x")
        assert result.frequency_rank == 100
        assert result.frequency_weight == 0.5


# ---------- set_decomposition / get_decomposition ----------


class TestDecomposition:
    def test_set_and_get(self, db):
        lex_id = db.add_lexeme(lemma="happy", pos="adj")
        db.set_decomposition(lex_id, {"GOOD": 1, "FEEL": 1})
        result = db.get_decomposition(lex_id)
        assert result["GOOD"] == 1
        assert result["FEEL"] == 1

    def test_fills_missing_with_zero(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.set_decomposition(lex_id, {"GOOD": 1})
        result = db.get_decomposition(lex_id)
        # All 72 primitives present
        assert len(result) == len(ALL_PRIMITIVES)
        # Non-mentioned are 0
        assert result["BAD"] == 0

    def test_replace_existing(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.set_decomposition(lex_id, {"GOOD": 1})
        db.set_decomposition(lex_id, {"BAD": 1})  # Replace
        result = db.get_decomposition(lex_id)
        # GOOD now 0 (deleted), BAD = 1
        assert result["GOOD"] == 0
        assert result["BAD"] == 1

    def test_confidences_propagated(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.set_decomposition(lex_id, {"GOOD": 1}, confidences={"GOOD": 0.7})
        result = db.get_primitive_confidences(lex_id)
        assert result["GOOD"] == 0.7

    def test_default_confidence_1(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.set_decomposition(lex_id, {"GOOD": 1})
        result = db.get_primitive_confidences(lex_id)
        assert result["GOOD"] == 1.0


# ---------- get_active_primitives ----------


class TestGetActivePrimitives:
    def test_returns_non_zero(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.set_decomposition(lex_id, {"GOOD": 1, "BAD": 0, "BIG": -1})
        result = db.get_active_primitives(lex_id)
        assert result == {"GOOD": 1, "BIG": -1}

    def test_empty_when_all_zero(self, db):
        lex_id = db.add_lexeme(lemma="x", pos="n")
        db.set_decomposition(lex_id, {})
        result = db.get_active_primitives(lex_id)
        assert result == {}


# ---------- get_words_by_rank_range ----------


class TestGetWordsByRankRange:
    def test_with_end(self, db):
        db.add_lexeme(lemma="a", pos="n", frequency_rank=1)
        db.add_lexeme(lemma="b", pos="n", frequency_rank=5)
        db.add_lexeme(lemma="c", pos="n", frequency_rank=10)
        result = db.get_words_by_rank_range(1, 5)
        assert len(result) == 2

    def test_no_end(self, db):
        db.add_lexeme(lemma="a", pos="n", frequency_rank=1)
        db.add_lexeme(lemma="b", pos="n", frequency_rank=100)
        result = db.get_words_by_rank_range(50)
        assert len(result) == 1
        assert result[0]["lemma"] == "b"


# ---------- get_unprocessed_words ----------


class TestGetUnprocessedWords:
    def test_filters_by_phase_and_status(self, db):
        db.add_lexeme(lemma="a", pos="n", phase=1, frequency_rank=1)
        lex_b = db.add_lexeme(lemma="b", pos="n", phase=1, frequency_rank=2)
        db.update_lexeme(lex_b, validation_status="validated")

        result = db.get_unprocessed_words(phase=1)
        # Only "a" is pending
        assert len(result) == 1
        assert result[0]["lemma"] == "a"

    def test_start_rank_filter(self, db):
        db.add_lexeme(lemma="a", pos="n", phase=1, frequency_rank=1)
        db.add_lexeme(lemma="b", pos="n", phase=1, frequency_rank=5)
        result = db.get_unprocessed_words(phase=1, start_rank=3)
        assert len(result) == 1
        assert result[0]["lemma"] == "b"

    def test_limit(self, db):
        for i in range(5):
            db.add_lexeme(lemma=f"w{i}", pos="n", phase=1, frequency_rank=i + 1)
        result = db.get_unprocessed_words(phase=1, limit=2)
        assert len(result) == 2


# ---------- get_validated_entries ----------


class TestGetValidatedEntries:
    def test_empty(self, db):
        assert db.get_validated_entries() == []

    def test_filters_by_status(self, db):
        lex = db.add_lexeme(lemma="x", pos="n", frequency_rank=1)
        db.update_lexeme(lex, validation_status="validated")
        result = db.get_validated_entries()
        assert len(result) == 1

    def test_phase_filter(self, db):
        a = db.add_lexeme(lemma="a", pos="n", phase=1, frequency_rank=1)
        db.update_lexeme(a, validation_status="validated")
        b = db.add_lexeme(lemma="b", pos="n", phase=2, frequency_rank=2)
        db.update_lexeme(b, validation_status="validated")

        result = db.get_validated_entries(phase=1)
        assert len(result) == 1
        assert result[0].lemma == "a"

    def test_includes_decomposition(self, db):
        lex = db.add_lexeme(lemma="x", pos="n", frequency_rank=1)
        db.update_lexeme(lex, validation_status="validated")
        db.set_decomposition(lex, {"GOOD": 1})
        result = db.get_validated_entries()
        assert result[0].decomposition["GOOD"] == 1


# ---------- count_by_phase ----------


class TestCountByPhase:
    def test_empty(self, db):
        result = db.count_by_phase(1)
        assert result["total"] == 0
        assert result["validated"] == 0
        assert result["pending"] == 0
        assert result["rejected"] == 0

    def test_counts_by_status(self, db):
        a = db.add_lexeme(lemma="a", pos="n", phase=1)
        db.update_lexeme(a, validation_status="validated")
        db.add_lexeme(lemma="b", pos="n", phase=1)  # pending
        c = db.add_lexeme(lemma="c", pos="n", phase=1)
        db.update_lexeme(c, validation_status="rejected")

        result = db.count_by_phase(1)
        assert result["total"] == 3
        assert result["validated"] == 1
        assert result["pending"] == 1
        assert result["rejected"] == 1


# ---------- store_validation_result / get_validation_results ----------


class TestValidationResults:
    def test_store_and_get(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_validation_result(lex, "bipolar", True, "all good")
        results = db.get_validation_results(lex)
        assert len(results) == 1
        assert results[0]["validation_type"] == "bipolar"
        assert results[0]["passed"] == 1

    def test_no_results(self, db):
        assert db.get_validation_results(999) == []


# ---------- flag_for_review ----------


class TestFlagForReview:
    def test_updates_status(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.flag_for_review(lex)
        result = db.get_lexeme_by_id(lex)
        assert result.validation_status == "review"


# ---------- add_provenance ----------


class TestAddProvenance:
    def test_basic(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.add_provenance(
            lex, source_type="llm", source_detail="qwen", primitive="GOOD", confidence_before=0.5, confidence_after=0.9
        )
        cursor = db.conn.execute("SELECT * FROM decomposition_provenance WHERE lexeme_id = ?", (lex,))
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["source_type"] == "llm"


# ---------- checkpoint / get_last_checkpoint ----------


class TestCheckpoint:
    def test_save_and_retrieve(self, db):
        db.checkpoint(phase=1, last_rank=100, words_processed=50, words_validated=45)
        result = db.get_last_checkpoint(1)
        assert result is not None
        assert result["last_processed_rank"] == 100
        assert result["words_processed"] == 50

    def test_no_checkpoint(self, db):
        assert db.get_last_checkpoint(99) is None

    def test_replace_existing(self, db):
        db.checkpoint(phase=1, last_rank=100, words_processed=50, words_validated=45)
        db.checkpoint(phase=1, last_rank=200, words_processed=100, words_validated=90)
        result = db.get_last_checkpoint(1)
        # Replaced
        assert result["last_processed_rank"] == 200


# ---------- get_stats ----------


class TestGetStats:
    def test_empty(self, db):
        stats = db.get_stats()
        assert stats["total_lexemes"] == 0
        assert stats["by_phase"] == {}

    def test_with_data(self, db):
        db.add_lexeme(lemma="a", pos="n", phase=1)
        db.add_lexeme(lemma="b", pos="n", phase=2)
        stats = db.get_stats()
        assert stats["total_lexemes"] == 2
        assert stats["by_phase"][1] == 1
        assert stats["by_phase"][2] == 1

    def test_by_status(self, db):
        a = db.add_lexeme(lemma="a", pos="n")
        db.update_lexeme(a, validation_status="validated")
        db.add_lexeme(lemma="b", pos="n")  # pending
        stats = db.get_stats()
        assert stats["by_status"]["validated"] == 1
        assert stats["by_status"]["pending"] == 1

    def test_by_source(self, db):
        db.add_lexeme(lemma="a", pos="n", source="llm")
        db.add_lexeme(lemma="b", pos="n", source="manual")
        stats = db.get_stats()
        assert stats["by_source"]["llm"] == 1
        assert stats["by_source"]["manual"] == 1


# ---------- disagreement operations ----------


class TestDisagreements:
    def test_store_and_get(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_disagreement(lex, "GOOD", 1, -1, "verbnet", "major")
        result = db.get_disagreements(lexeme_id=lex)
        assert len(result) == 1
        assert result[0]["primitive"] == "GOOD"

    def test_batch_store(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        disagreements = [
            (lex, "GOOD", 1, -1, "verbnet", "major"),
            (lex, "BIG", -1, 1, "framenet", "sign_flip"),
        ]
        db.store_disagreements_batch(disagreements)
        result = db.get_disagreements(lexeme_id=lex)
        assert len(result) == 2

    def test_filter_by_severity(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_disagreement(lex, "GOOD", 1, -1, "v", "major")
        db.store_disagreement(lex, "BIG", 1, -1, "v", "minor")
        result = db.get_disagreements(severity="major")
        assert len(result) == 1

    def test_filter_unresolved_only(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_disagreement(lex, "GOOD", 1, -1, "v", "major")
        # Get the disagreement id
        result_all = db.get_disagreements()
        d_id = result_all[0]["id"]
        db.resolve_disagreement(d_id, "verified", 1)
        # Now resolved
        unresolved = db.get_disagreements(unresolved_only=True)
        assert len(unresolved) == 0

    def test_resolve_disagreement(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_disagreement(lex, "GOOD", 1, -1, "v", "major")
        d_id = db.get_disagreements()[0]["id"]
        db.resolve_disagreement(d_id, "verified", 1)
        result = db.get_disagreements()
        assert result[0]["resolved"] == 1


# ---------- store_source_coverage ----------


class TestStoreSourceCoverage:
    def test_basic(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_source_coverage(lex, "verbnet", primitives_matched=10, primitives_agreed=8)
        cursor = db.conn.execute("SELECT * FROM external_source_coverage WHERE lexeme_id = ?", (lex,))
        row = cursor.fetchone()
        assert row["primitives_matched"] == 10
        assert row["primitives_agreed"] == 8
        assert row["agreement_rate"] == 0.8

    def test_zero_matched_no_divzero(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        # max(0, 1) = 1 prevents div by zero
        db.store_source_coverage(lex, "v", primitives_matched=0, primitives_agreed=0)
        cursor = db.conn.execute("SELECT agreement_rate FROM external_source_coverage WHERE lexeme_id = ?", (lex,))
        assert cursor.fetchone()["agreement_rate"] == 0


# ---------- get_disagreement_stats ----------


class TestGetDisagreementStats:
    def test_empty(self, db):
        stats = db.get_disagreement_stats()
        assert stats["total"] == 0
        assert stats["by_severity"] == {}
        assert stats["unresolved"] == 0

    def test_counts(self, db):
        lex = db.add_lexeme(lemma="x", pos="n")
        db.store_disagreement(lex, "GOOD", 1, -1, "v", "major")
        db.store_disagreement(lex, "BIG", 1, -1, "v", "minor")
        stats = db.get_disagreement_stats()
        assert stats["total"] == 2
        assert stats["by_severity"]["major"] == 1
        assert stats["unresolved"] == 2


# ---------- context manager ----------


class TestContextManager:
    def test_closes(self, tmp_path):
        path = tmp_path / "lex.db"
        with LexiconDatabase(str(path)) as d:
            assert d.conn is not None
        # After exit, conn closed
        with pytest.raises(sqlite3.ProgrammingError):
            d.conn.execute("SELECT 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
