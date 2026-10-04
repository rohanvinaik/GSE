"""Tests for gse.curation.external_sources.populate."""

import pytest

from gse.curation.external_sources.integrator import ExternalWordData
from gse.curation.external_sources.populate import (
    PopulationStats,
    populate_from_entries,
)
from gse.curation.lexicon_db import LexiconDatabase


@pytest.fixture
def db(tmp_path):
    """Fresh in-memory-ish lexicon DB per test."""
    db_path = tmp_path / "lexicon.db"
    database = LexiconDatabase(str(db_path))
    yield database
    database.close()


def _entry(word, primitives, confidences=None, sources=("nrc_emotion", "sentiwordnet")):
    return ExternalWordData(
        word=word,
        sources=list(sources),
        primitives=primitives,
        confidence_scores=confidences or {p: 1.0 for p in primitives},
    )


class TestEmptyDB:
    def test_no_entries_no_writes(self, db):
        stats = populate_from_entries(db, [])
        assert stats == PopulationStats()

    def test_entry_without_primitives_is_filtered(self, db):
        stats = populate_from_entries(db, [_entry("foo", {})])
        assert stats.words_filtered_no_primitives == 1
        assert stats.lexemes_added == 0

    def test_single_entry_inserts_lexeme(self, db):
        entries = [_entry("happy", {"GOOD": 1, "FEEL": 1})]
        stats = populate_from_entries(db, entries)
        assert stats.lexemes_added == 1
        lexeme = db.get_lexeme("happy", "n")
        assert lexeme is not None
        assert lexeme.source == "external_sources_voting"


class TestDecompositionStorage:
    def test_primitives_set_count_matches_active(self, db):
        entries = [_entry("happy", {"GOOD": 1, "FEEL": 1, "BAD": -1})]
        stats = populate_from_entries(db, entries)
        assert stats.primitives_set == 3
        lexeme = db.get_lexeme("happy", "n")
        active = db.get_active_primitives(lexeme.id)
        assert active == {"GOOD": 1, "FEEL": 1, "BAD": -1}

    def test_confidences_persisted_per_primitive(self, db):
        entries = [
            _entry(
                "happy",
                {"GOOD": 1, "FEEL": 1},
                confidences={"GOOD": 0.9, "FEEL": 0.6},
            )
        ]
        populate_from_entries(db, entries)
        lex = db.get_lexeme("happy", "n")
        confs = db.get_primitive_confidences(lex.id)
        assert confs["GOOD"] == pytest.approx(0.9)
        assert confs["FEEL"] == pytest.approx(0.6)

    def test_lexeme_confidence_is_mean_of_primitive_confidences(self, db):
        entries = [
            _entry(
                "happy",
                {"GOOD": 1, "FEEL": 1},
                confidences={"GOOD": 0.8, "FEEL": 0.4},
            )
        ]
        populate_from_entries(db, entries)
        lex = db.get_lexeme("happy", "n")
        assert lex.confidence == pytest.approx(0.6)


class TestProvenance:
    def test_provenance_row_per_lexeme(self, db):
        entries = [
            _entry("happy", {"GOOD": 1}),
            _entry("sad", {"BAD": 1}),
        ]
        stats = populate_from_entries(db, entries)
        assert stats.provenance_rows == 2

    def test_provenance_source_detail_lists_sources(self, db):
        entries = [
            _entry(
                "happy",
                {"GOOD": 1},
                sources=("nrc_emotion", "sentiwordnet", "nrc_vad"),
            )
        ]
        populate_from_entries(db, entries)
        lex = db.get_lexeme("happy", "n")
        cursor = db.conn.execute(
            "SELECT source_type, source_detail FROM decomposition_provenance WHERE lexeme_id = ?",
            (lex.id,),
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["source_type"] == "external"
        # Sources stored sorted, comma-joined
        assert rows[0]["source_detail"] == "nrc_emotion,nrc_vad,sentiwordnet"


class TestIdempotency:
    def test_re_running_does_not_duplicate(self, db):
        entries = [_entry("happy", {"GOOD": 1, "FEEL": 1})]
        first = populate_from_entries(db, entries)
        second = populate_from_entries(db, entries)
        assert first.lexemes_added == 1
        assert second.lexemes_added == 0
        assert second.lexemes_skipped_existing == 1
        # Only one provenance row, not two
        cursor = db.conn.execute("SELECT COUNT(*) FROM decomposition_provenance")
        assert cursor.fetchone()[0] == 1

    def test_skip_when_existing_lexeme_already_present(self, db):
        db.add_lexeme(lemma="happy", pos="n", source="manual")
        entries = [_entry("happy", {"GOOD": 1})]
        stats = populate_from_entries(db, entries)
        assert stats.lexemes_added == 0
        assert stats.lexemes_skipped_existing == 1
