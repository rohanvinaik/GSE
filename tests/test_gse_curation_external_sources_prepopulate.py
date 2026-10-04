"""Manual contract tests for gse.curation.external_sources.prepopulate."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.prepopulate import (
    PrimitiveEvidence,
    aggregate_external_evidence,
    get_missing_primitives,
    get_prefill_summary,
    prepopulate_from_external,
)

# ---------- PrimitiveEvidence ----------


class TestPrimitiveEvidence:
    def test_construction(self):
        e = PrimitiveEvidence(primitive="GOOD", value=1, sources=["a"], confidence=0.9)
        assert e.primitive == "GOOD"
        assert e.value == 1
        assert e.sources == ["a"]
        assert e.confidence == 0.9


# ---------- aggregate_external_evidence ----------


def _make_comparator(parser_map):
    """parser_map: dict[name, dict[primitive, value]]"""
    comparator = MagicMock()
    parsers = {}
    for name, prims in parser_map.items():
        parser = MagicMock()
        parser.to_primitives.return_value = prims
        parsers[name] = parser
    comparator.parsers = parsers
    return comparator


class TestAggregateExternalEvidence:
    def test_empty_no_evidence(self):
        c = _make_comparator({})
        assert aggregate_external_evidence("x", c) == {}

    def test_zero_value_skipped(self):
        c = _make_comparator({"s1": {"GOOD": 0}})
        assert aggregate_external_evidence("x", c) == {}

    def test_single_source(self):
        c = _make_comparator({"s1": {"GOOD": 1}})
        result = aggregate_external_evidence("x", c)
        assert "GOOD" in result
        assert result["GOOD"].value == 1
        assert result["GOOD"].sources == ["s1"]

    def test_multiple_agree_higher_confidence(self):
        c = _make_comparator(
            {
                "s1": {"GOOD": 1},
                "s2": {"GOOD": 1},
                "s3": {"GOOD": 1},
            }
        )
        result = aggregate_external_evidence("x", c)
        # 0.5 + 0.15*3 = 0.95 → capped at 0.95
        assert result["GOOD"].confidence == 0.95
        assert len(result["GOOD"].sources) == 3

    def test_two_agree_confidence(self):
        c = _make_comparator(
            {
                "s1": {"GOOD": 1},
                "s2": {"GOOD": 1},
            }
        )
        result = aggregate_external_evidence("x", c)
        # 0.5 + 0.15*2 = 0.8
        assert result["GOOD"].confidence == pytest.approx(0.8)

    def test_one_agree_confidence(self):
        c = _make_comparator({"s1": {"GOOD": 1}})
        result = aggregate_external_evidence("x", c)
        # 0.5 + 0.15*1 = 0.65
        assert result["GOOD"].confidence == pytest.approx(0.65)

    def test_cap_at_0_95(self):
        # 5 agreeing sources → 0.5 + 0.15*5 = 1.25 → cap to 0.95
        c = _make_comparator({f"s{i}": {"GOOD": 1} for i in range(5)})
        result = aggregate_external_evidence("x", c)
        assert result["GOOD"].confidence == 0.95

    def test_disagreement_reduces_confidence(self):
        c = _make_comparator(
            {
                "s1": {"GOOD": 1},
                "s2": {"GOOD": 1},
                "s3": {"GOOD": -1},
            }
        )
        result = aggregate_external_evidence("x", c)
        # n_agree=2, n_disagree=1 → 2/3 * 0.8 = 0.533...
        assert result["GOOD"].value == 1  # majority
        assert result["GOOD"].confidence == pytest.approx(2 / 3 * 0.8)

    def test_majority_wins(self):
        c = _make_comparator(
            {
                "s1": {"GOOD": -1},
                "s2": {"GOOD": -1},
                "s3": {"GOOD": 1},
            }
        )
        result = aggregate_external_evidence("x", c)
        assert result["GOOD"].value == -1
        assert "s1" in result["GOOD"].sources
        assert "s2" in result["GOOD"].sources

    def test_multiple_primitives(self):
        c = _make_comparator({"s1": {"GOOD": 1, "BIG": -1}})
        result = aggregate_external_evidence("x", c)
        assert result["GOOD"].value == 1
        assert result["BIG"].value == -1


# ---------- prepopulate_from_external ----------


@pytest.fixture
def fresh_db(tmp_path):
    """Create empty lexicon DB with required schema."""
    db_path = tmp_path / "lex.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT);
        CREATE TABLE primitive_values (
            lexeme_id INTEGER, primitive TEXT, value INTEGER,
            confidence REAL, source TEXT,
            PRIMARY KEY (lexeme_id, primitive)
        );
    """)
    conn.commit()
    conn.close()
    return str(db_path)


class TestPrepopulateFromExternal:
    def test_no_lexemes_no_filled(self, fresh_db):
        with patch("gse.curation.external_sources.prepopulate.ExternalSourcesComparator") as MockComp:
            MockComp.return_value.load_all_sources.return_value = {}
            MockComp.return_value.parsers = {}
            stats = prepopulate_from_external(fresh_db)
            assert stats["words_processed"] == 0
            assert stats["primitives_filled"] == 0

    def test_fills_primitives(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes (id, lemma) VALUES (1, 'happy')")
        conn.commit()
        conn.close()

        mock_parser = MagicMock()
        mock_parser.to_primitives.return_value = {"GOOD": 1}
        with patch("gse.curation.external_sources.prepopulate.ExternalSourcesComparator") as MockComp:
            MockComp.return_value.load_all_sources.return_value = {"s1": 1}
            MockComp.return_value.parsers = {"s1": mock_parser}
            stats = prepopulate_from_external(fresh_db)

        assert stats["words_processed"] == 1
        assert stats["words_with_evidence"] == 1
        assert stats["primitives_filled"] >= 1

        # Verify DB has the entry
        conn = sqlite3.connect(fresh_db)
        rows = conn.execute("SELECT * FROM primitive_values").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_below_min_confidence_skipped(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes (id, lemma) VALUES (1, 'x')")
        conn.commit()
        conn.close()

        mock_parser = MagicMock()
        mock_parser.to_primitives.return_value = {"GOOD": 1}
        with patch("gse.curation.external_sources.prepopulate.ExternalSourcesComparator") as MockComp:
            MockComp.return_value.load_all_sources.return_value = {}
            MockComp.return_value.parsers = {"s1": mock_parser}
            # min_confidence=0.99 → 0.65 single-source confidence not enough
            stats = prepopulate_from_external(fresh_db, min_confidence=0.99)

        assert stats["primitives_filled"] == 0

    def test_reset_existing(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO primitive_values VALUES (99, 'OLD', 1, 0.5, 'old')")
        conn.commit()
        conn.close()

        with patch("gse.curation.external_sources.prepopulate.ExternalSourcesComparator") as MockComp:
            MockComp.return_value.load_all_sources.return_value = {}
            MockComp.return_value.parsers = {}
            prepopulate_from_external(fresh_db, reset_existing=True)

        conn = sqlite3.connect(fresh_db)
        rows = conn.execute("SELECT * FROM primitive_values").fetchall()
        conn.close()
        assert rows == []

    def test_no_reset_keeps_existing(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO primitive_values VALUES (99, 'OLD', 1, 0.5, 'old')")
        conn.commit()
        conn.close()

        with patch("gse.curation.external_sources.prepopulate.ExternalSourcesComparator") as MockComp:
            MockComp.return_value.load_all_sources.return_value = {}
            MockComp.return_value.parsers = {}
            prepopulate_from_external(fresh_db, reset_existing=False)

        conn = sqlite3.connect(fresh_db)
        rows = conn.execute("SELECT * FROM primitive_values").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_by_source_count(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes (id, lemma) VALUES (1, 'x')")
        conn.commit()
        conn.close()

        p1 = MagicMock()
        p1.to_primitives.return_value = {"GOOD": 1}
        p2 = MagicMock()
        p2.to_primitives.return_value = {"GOOD": 1}
        with patch("gse.curation.external_sources.prepopulate.ExternalSourcesComparator") as MockComp:
            MockComp.return_value.load_all_sources.return_value = {}
            MockComp.return_value.parsers = {"s1": p1, "s2": p2}
            stats = prepopulate_from_external(fresh_db, min_confidence=0.0)

        assert stats["by_source"]["s1"] >= 1
        assert stats["by_source"]["s2"] >= 1


# ---------- get_missing_primitives ----------


class TestGetMissingPrimitives:
    def test_all_missing_when_no_data(self, fresh_db):
        from gse.curation.schema import ALL_PRIMITIVES

        result = get_missing_primitives(fresh_db, lexeme_id=42)
        assert set(result) == set(ALL_PRIMITIVES)

    def test_excludes_filled(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 's')")
        conn.commit()
        conn.close()

        result = get_missing_primitives(fresh_db, lexeme_id=1)
        assert "GOOD" not in result

    def test_only_for_matching_lexeme(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 's')")
        conn.commit()
        conn.close()

        # lexeme 2 has no data
        result = get_missing_primitives(fresh_db, lexeme_id=2)
        assert "GOOD" in result


# ---------- get_prefill_summary ----------


class TestGetPrefillSummary:
    def test_empty_db(self, fresh_db):
        summary = get_prefill_summary(fresh_db)
        assert summary["total_lexemes"] == 0
        assert summary["lexemes_with_data"] == 0
        assert summary["primitives_filled"] == 0
        assert summary["avg_per_word"] == 0  # 0 / max(0, 1) = 0
        assert summary["coverage"] == 0
        assert summary["top_primitives"] == {}
        assert summary["by_source"] == {}

    def test_with_data(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes VALUES (1, 'a')")
        conn.execute("INSERT INTO lexemes VALUES (2, 'b')")
        conn.execute("INSERT INTO primitive_values VALUES (1, 'GOOD', 1, 0.9, 's1')")
        conn.execute("INSERT INTO primitive_values VALUES (1, 'BIG', -1, 0.8, 's2')")
        conn.commit()
        conn.close()

        summary = get_prefill_summary(fresh_db)
        assert summary["total_lexemes"] == 2
        assert summary["lexemes_with_data"] == 1
        assert summary["primitives_filled"] == 2  # both have value != 0
        assert summary["coverage"] == pytest.approx(0.5)
        assert summary["avg_per_word"] == pytest.approx(2.0)

    def test_excludes_zero_value_from_filled(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute("INSERT INTO lexemes VALUES (1, 'a')")
        conn.execute("INSERT INTO primitive_values VALUES (1, 'X', 0, 0.5, 's')")
        conn.commit()
        conn.close()

        summary = get_prefill_summary(fresh_db)
        assert summary["primitives_filled"] == 0

    def test_top_primitives_limit(self, fresh_db):
        # Create 15 distinct primitives to verify limit=10
        conn = sqlite3.connect(fresh_db)
        for i in range(15):
            conn.execute("INSERT INTO lexemes VALUES (?, ?)", (i, f"w{i}"))
            conn.execute(
                "INSERT INTO primitive_values VALUES (?, ?, 1, 0.9, 's')",
                (i, f"PRIM{i}"),
            )
        conn.commit()
        conn.close()

        summary = get_prefill_summary(fresh_db)
        assert len(summary["top_primitives"]) == 10

    def test_by_source_limit(self, fresh_db):
        # Create 15 source entries to confirm LIMIT 10
        conn = sqlite3.connect(fresh_db)
        for i in range(15):
            conn.execute("INSERT INTO lexemes VALUES (?, ?)", (i, f"w{i}"))
            conn.execute(
                "INSERT INTO primitive_values VALUES (?, 'P', 1, 0.9, ?)",
                (i, f"src{i}"),
            )
        conn.commit()
        conn.close()

        summary = get_prefill_summary(fresh_db)
        assert len(summary["by_source"]) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
