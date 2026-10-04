"""Manual contract tests for gse.curation.external_sources.run_comparison."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.run_comparison import (
    calculate_stats,
    generate_report,
    main,
    run_comparison,
)


def mk_disagreement(primitive="GOOD", llm_value=1, external_value=-1, external_source="verbnet", severity="major"):
    d = MagicMock()
    d.primitive = primitive
    d.llm_value = llm_value
    d.external_value = external_value
    d.external_source = external_source
    d.severity = severity
    return d


def mk_comparison_result(external_primitives=None, disagreements=None, needs_review=False, agreement_rate=1.0):
    r = MagicMock()
    r.external_primitives = external_primitives or {}
    r.disagreements = disagreements or []
    r.needs_review = needs_review
    r.agreement_rate = agreement_rate
    return r


# ---------- calculate_stats ----------


class TestCalculateStats:
    def test_empty(self):
        stats = calculate_stats({})
        assert stats["total_words"] == 0
        assert stats["words_with_external"] == 0
        assert stats["total_disagreements"] == 0
        assert stats["major_disagreements"] == 0
        assert stats["avg_agreement_rate"] == 0.0
        assert stats["by_severity"] == {}

    def test_counts_total_words(self):
        results = {
            "a": mk_comparison_result(),
            "b": mk_comparison_result(),
        }
        stats = calculate_stats(results)
        assert stats["total_words"] == 2

    def test_words_with_external_only_when_non_empty(self):
        results = {
            "with": mk_comparison_result(external_primitives={"verbnet": {"GOOD": 1}}, agreement_rate=0.8),
            "without": mk_comparison_result(external_primitives={}, agreement_rate=0.0),
        }
        stats = calculate_stats(results)
        assert stats["words_with_external"] == 1

    def test_words_needing_review(self):
        results = {
            "a": mk_comparison_result(needs_review=True),
            "b": mk_comparison_result(needs_review=False),
            "c": mk_comparison_result(needs_review=True),
        }
        stats = calculate_stats(results)
        assert stats["words_needing_review"] == 2

    def test_disagreement_count(self):
        results = {
            "a": mk_comparison_result(disagreements=[mk_disagreement(), mk_disagreement()]),
        }
        stats = calculate_stats(results)
        assert stats["total_disagreements"] == 2

    def test_by_severity_counts(self):
        results = {
            "a": mk_comparison_result(
                disagreements=[
                    mk_disagreement(severity="major"),
                    mk_disagreement(severity="minor"),
                    mk_disagreement(severity="major"),
                ]
            )
        }
        stats = calculate_stats(results)
        assert stats["by_severity"]["major"] == 2
        assert stats["by_severity"]["minor"] == 1

    def test_major_disagreements_counts_major_and_sign_flip(self):
        results = {
            "a": mk_comparison_result(
                disagreements=[
                    mk_disagreement(severity="major"),
                    mk_disagreement(severity="sign_flip"),
                    mk_disagreement(severity="minor"),
                ]
            )
        }
        stats = calculate_stats(results)
        assert stats["major_disagreements"] == 2

    def test_minor_disagreement_not_counted_as_major(self):
        results = {"a": mk_comparison_result(disagreements=[mk_disagreement(severity="minor")])}
        stats = calculate_stats(results)
        assert stats["major_disagreements"] == 0

    def test_by_source_counts(self):
        results = {
            "a": mk_comparison_result(
                disagreements=[
                    mk_disagreement(external_source="verbnet"),
                    mk_disagreement(external_source="verbnet"),
                    mk_disagreement(external_source="framenet"),
                ]
            )
        }
        stats = calculate_stats(results)
        assert stats["by_source"]["verbnet"] == 2
        assert stats["by_source"]["framenet"] == 1

    def test_by_primitive_counts(self):
        results = {
            "a": mk_comparison_result(
                disagreements=[
                    mk_disagreement(primitive="GOOD"),
                    mk_disagreement(primitive="GOOD"),
                ]
            )
        }
        stats = calculate_stats(results)
        assert stats["by_primitive"]["GOOD"] == 2

    def test_avg_agreement_rate(self):
        results = {
            "a": mk_comparison_result(external_primitives={"s": {}}, agreement_rate=0.8),
            "b": mk_comparison_result(external_primitives={"s": {}}, agreement_rate=0.6),
        }
        stats = calculate_stats(results)
        assert stats["avg_agreement_rate"] == pytest.approx(0.7)

    def test_avg_rate_only_uses_external(self):
        # words without external_primitives don't contribute
        results = {
            "with": mk_comparison_result(external_primitives={"s": {}}, agreement_rate=0.8),
            "without": mk_comparison_result(external_primitives={}, agreement_rate=0.2),
        }
        stats = calculate_stats(results)
        # Only "with" contributes
        assert stats["avg_agreement_rate"] == pytest.approx(0.8)

    def test_returns_regular_dicts_not_defaultdict(self):
        from collections import defaultdict

        results = {"a": mk_comparison_result(disagreements=[mk_disagreement()])}
        stats = calculate_stats(results)
        assert not isinstance(stats["by_severity"], defaultdict)
        assert not isinstance(stats["by_source"], defaultdict)
        assert not isinstance(stats["by_primitive"], defaultdict)


# ---------- run_comparison ----------


class TestRunComparison:
    def _setup_mocks(self, entries=None, source_stats=None, comparison_result=None):
        """Set up patched dependencies."""
        mock_db = MagicMock()
        mock_db.get_validated_entries.return_value = entries or []

        mock_comparator = MagicMock()
        mock_comparator.load_all_sources.return_value = source_stats or {}
        mock_comparator.compare.return_value = comparison_result or mk_comparison_result()

        return mock_db, mock_comparator

    def test_no_entries(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                stats = run_comparison(db_path=db_path)

        assert stats["total_words"] == 0

    def test_phase_filter_passed(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                run_comparison(db_path=db_path, phase=3)

        mock_db.get_validated_entries.assert_called_with(phase=3)

    def test_no_phase_default_call(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                run_comparison(db_path=db_path, phase=None)

        # No phase kwarg
        mock_db.get_validated_entries.assert_called_with()

    def test_limit_truncates(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        entries = []
        for i in range(10):
            e = MagicMock()
            e.id = i
            e.lemma = f"w{i}"
            e.decomposition = {}
            entries.append(e)
        mock_db, mock_comparator = self._setup_mocks(entries=entries)

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                stats = run_comparison(db_path=db_path, limit=3)

        # Only 3 processed
        assert stats["total_words"] == 3

    def test_download_sources_called(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                with patch("gse.curation.external_sources.integrator.download_all_sources") as mock_dl:
                    run_comparison(db_path=db_path, download_sources=True)
                    mock_dl.assert_called_once()

    def test_download_not_called_by_default(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                with patch("gse.curation.external_sources.integrator.download_all_sources") as mock_dl:
                    run_comparison(db_path=db_path, download_sources=False)
                    mock_dl.assert_not_called()

    def test_disagreements_stored(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        entry = MagicMock()
        entry.id = 1
        entry.lemma = "x"
        entry.decomposition = {}
        cmp_result = mk_comparison_result(disagreements=[mk_disagreement()])
        mock_db, mock_comparator = self._setup_mocks(entries=[entry], comparison_result=cmp_result)

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                run_comparison(db_path=db_path)

        mock_db.store_disagreements_batch.assert_called_once()

    def test_no_disagreement_no_batch_store(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                run_comparison(db_path=db_path)

        mock_db.store_disagreements_batch.assert_not_called()

    def test_coverage_stored(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        entry = MagicMock()
        entry.id = 1
        entry.lemma = "x"
        entry.decomposition = {"GOOD": 1}
        cmp_result = mk_comparison_result(
            external_primitives={"verbnet": {"GOOD": 1, "BIG": -1}},
        )
        mock_db, mock_comparator = self._setup_mocks(entries=[entry], comparison_result=cmp_result)

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                run_comparison(db_path=db_path)

        # store_source_coverage called once with (1, "verbnet", 2, 1)
        # matched=2 (GOOD, BIG); agreed=1 (only GOOD matches)
        mock_db.store_source_coverage.assert_called_once_with(1, "verbnet", 2, 1)

    def test_db_closed(self, tmp_path):
        db_path = str(tmp_path / "lex.db")
        mock_db, mock_comparator = self._setup_mocks()

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            with patch(
                "gse.curation.external_sources.run_comparison.ExternalSourcesComparator", return_value=mock_comparator
            ):
                run_comparison(db_path=db_path)

        mock_db.close.assert_called_once()


# ---------- generate_report ----------


class TestGenerateReport:
    def test_basic_report(self, tmp_path):
        mock_db = MagicMock()
        mock_db.get_disagreement_stats.return_value = {
            "total": 5,
            "unresolved": 3,
            "by_severity": {"major": 2, "minor": 3},
            "by_source": {"verbnet": 4, "framenet": 1},
        }
        mock_db.get_disagreements.return_value = []

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            report = generate_report(str(tmp_path / "lex.db"))

        assert "Total disagreements: 5" in report
        assert "Unresolved: 3" in report
        assert "major: 2" in report
        assert "verbnet: 4" in report

    def test_writes_output(self, tmp_path):
        mock_db = MagicMock()
        mock_db.get_disagreement_stats.return_value = {
            "total": 0,
            "unresolved": 0,
            "by_severity": {},
            "by_source": {},
        }
        mock_db.get_disagreements.return_value = []
        output_path = tmp_path / "out.md"

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            generate_report(str(tmp_path / "lex.db"), output_path=str(output_path))

        assert output_path.exists()

    def test_includes_sign_flip_section(self, tmp_path):
        d = {"primitive": "GOOD", "llm_value": 1, "external_source": "verbnet", "external_value": -1, "lexeme_id": 1}
        mock_db = MagicMock()
        mock_db.get_disagreement_stats.return_value = {
            "total": 1,
            "unresolved": 1,
            "by_severity": {},
            "by_source": {},
        }
        # Return sign_flip on first call, empty on second (minor)
        mock_db.get_disagreements.side_effect = [[d], []]
        mock_entry = MagicMock()
        mock_entry.lemma = "happy"
        mock_db.get_lexeme_by_id.return_value = mock_entry

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            report = generate_report(str(tmp_path / "lex.db"))

        assert "Sign-Flip" in report
        assert "happy" in report
        assert "LLM=1" in report

    def test_unknown_word_fallback(self, tmp_path):
        d = {"primitive": "GOOD", "llm_value": 1, "external_source": "verbnet", "external_value": -1, "lexeme_id": 999}
        mock_db = MagicMock()
        mock_db.get_disagreement_stats.return_value = {
            "total": 1,
            "unresolved": 1,
            "by_severity": {},
            "by_source": {},
        }
        mock_db.get_disagreements.side_effect = [[d], []]
        mock_db.get_lexeme_by_id.return_value = None

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            report = generate_report(str(tmp_path / "lex.db"))

        assert "unknown" in report

    def test_top_20_sign_flips(self, tmp_path):
        ds = [
            {"primitive": "P", "llm_value": 1, "external_source": "s", "external_value": -1, "lexeme_id": i}
            for i in range(25)
        ]
        mock_db = MagicMock()
        mock_db.get_disagreement_stats.return_value = {
            "total": 25,
            "unresolved": 25,
            "by_severity": {},
            "by_source": {},
        }
        mock_db.get_disagreements.side_effect = [ds, []]
        mock_entry = MagicMock()
        mock_entry.lemma = "x"
        mock_db.get_lexeme_by_id.return_value = mock_entry

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            report = generate_report(str(tmp_path / "lex.db"))

        # Only first 20 included
        word_lines = [line for line in report.split("\n") if "**x**" in line]
        assert len(word_lines) == 20

    def test_db_closed(self, tmp_path):
        mock_db = MagicMock()
        mock_db.get_disagreement_stats.return_value = {
            "total": 0,
            "unresolved": 0,
            "by_severity": {},
            "by_source": {},
        }
        mock_db.get_disagreements.return_value = []

        with patch("gse.curation.external_sources.run_comparison.LexiconDatabase", return_value=mock_db):
            generate_report(str(tmp_path / "lex.db"))

        mock_db.close.assert_called_once()


# ---------- main ----------


class TestMain:
    def test_report_only_calls_generate(self, capsys):
        with patch("sys.argv", ["prog", "--report-only", "--db", "x"]):
            with patch(
                "gse.curation.external_sources.run_comparison.generate_report", return_value="REPORT"
            ) as mock_gen:
                main()
                mock_gen.assert_called_once_with("x", None)
        assert "REPORT" in capsys.readouterr().out

    def test_default_runs_comparison(self, capsys):
        stats = {
            "by_severity": {"major": 1},
            "by_source": {"verbnet": 2},
            "by_primitive": {"GOOD": 1},
        }
        with patch("sys.argv", ["prog", "--db", "x"]):
            with patch("gse.curation.external_sources.run_comparison.run_comparison", return_value=stats) as mock_run:
                main()
                mock_run.assert_called_once()

    def test_phase_flag(self):
        with patch("sys.argv", ["prog", "--phase", "2", "--db", "x"]):
            with patch(
                "gse.curation.external_sources.run_comparison.run_comparison",
                return_value={"by_severity": {}, "by_source": {}, "by_primitive": {}},
            ) as mock_run:
                main()
                call_kwargs = mock_run.call_args.kwargs
                assert call_kwargs["phase"] == 2

    def test_limit_flag(self):
        with patch("sys.argv", ["prog", "--limit", "5", "--db", "x"]):
            with patch(
                "gse.curation.external_sources.run_comparison.run_comparison",
                return_value={"by_severity": {}, "by_source": {}, "by_primitive": {}},
            ) as mock_run:
                main()
                assert mock_run.call_args.kwargs["limit"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
