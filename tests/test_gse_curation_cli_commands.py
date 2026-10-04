"""Manual contract tests for gse.curation.cli.commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.cli.commands import (
    _print_status,
    cmd_build,
    cmd_export,
    cmd_init,
    cmd_lookup,
    cmd_status,
    cmd_validate,
    main,
)


def mk_args(**kwargs):
    """Create a Namespace-like object from kwargs."""
    a = MagicMock()
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


# ---------- _print_status ----------


class TestPrintStatus:
    def test_empty(self, capsys):
        status = {
            "phases": {},
            "total": {"words": 0, "validated": 0, "validation_rate": 0},
        }
        _print_status(status)
        out = capsys.readouterr().out
        assert "GSE LEXICON BUILD STATUS" in out

    def test_with_phase_data(self, capsys):
        status = {
            "phases": {
                1: {"total": 100, "validated": 80, "pending": 20, "rejected": 0},
            },
            "total": {"words": 100, "validated": 80, "validation_rate": 80.0},
        }
        _print_status(status)
        out = capsys.readouterr().out
        assert "Phase 1" in out
        assert "100" in out
        assert "80" in out

    def test_rate_calculated_per_phase(self, capsys):
        status = {
            "phases": {
                1: {"total": 100, "validated": 50, "pending": 50, "rejected": 0},
            },
            "total": {"words": 100, "validated": 50, "validation_rate": 50.0},
        }
        _print_status(status)
        out = capsys.readouterr().out
        assert "50.0%" in out

    def test_no_rate_for_zero_total(self, capsys):
        status = {
            "phases": {
                1: {"total": 0, "validated": 0, "pending": 0, "rejected": 0},
            },
            "total": {"words": 0, "validated": 0, "validation_rate": 0},
        }
        _print_status(status)
        # Should not error on div-by-zero


# ---------- cmd_build ----------


class TestCmdBuild:
    def test_default_phases(self):
        args = mk_args(phases=None, lexicon_db="x", frequency_db=None, no_resume=False, mock=True)
        with patch("gse.curation.pipeline.staged_builder.StagedBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value.__enter__.return_value
            mock_builder.get_status.return_value = {
                "phases": {},
                "total": {"words": 0, "validated": 0, "validation_rate": 0},
            }
            cmd_build(args)
            # All three phase methods called
            mock_builder.build_phase_one.assert_called_once()
            mock_builder.build_phase_two.assert_called_once()
            mock_builder.build_phase_three.assert_called_once()

    def test_specific_phase(self):
        args = mk_args(phases=[1], lexicon_db="x", frequency_db=None, no_resume=False, mock=True)
        with patch("gse.curation.pipeline.staged_builder.StagedBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value.__enter__.return_value
            mock_builder.get_status.return_value = {
                "phases": {},
                "total": {"words": 0, "validated": 0, "validation_rate": 0},
            }
            cmd_build(args)
            mock_builder.build_phase_one.assert_called_once()
            mock_builder.build_phase_two.assert_not_called()

    def test_resume_flag_inverted(self):
        # no_resume=True → resume=False
        args = mk_args(phases=[1], lexicon_db="x", frequency_db=None, no_resume=True, mock=True)
        with patch("gse.curation.pipeline.staged_builder.StagedBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value.__enter__.return_value
            mock_builder.get_status.return_value = {
                "phases": {},
                "total": {"words": 0, "validated": 0, "validation_rate": 0},
            }
            cmd_build(args)
            mock_builder.build_phase_one.assert_called_with(resume=False)


# ---------- cmd_init ----------


class TestCmdInit:
    def test_default_phases(self):
        args = mk_args(phases=None, lexicon_db="x", frequency_db=None)
        with patch("gse.curation.pipeline.staged_builder.StagedBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value.__enter__.return_value
            cmd_init(args)
            mock_builder.initialize_from_frequency.assert_called_once_with([1, 2, 3])

    def test_specific_phases(self):
        args = mk_args(phases=[2], lexicon_db="x", frequency_db=None)
        with patch("gse.curation.pipeline.staged_builder.StagedBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value.__enter__.return_value
            cmd_init(args)
            mock_builder.initialize_from_frequency.assert_called_once_with([2])


# ---------- cmd_status ----------


class TestCmdStatus:
    def test_calls_get_status(self):
        args = mk_args(lexicon_db="x")
        with patch("gse.curation.pipeline.staged_builder.StagedBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value.__enter__.return_value
            mock_builder.get_status.return_value = {
                "phases": {},
                "total": {"words": 0, "validated": 0, "validation_rate": 0},
            }
            cmd_status(args)
            mock_builder.get_status.assert_called_once()


# ---------- cmd_validate ----------


class TestCmdValidate:
    def test_no_entries(self):
        args = mk_args(lexicon_db="x")
        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_validated_entries.return_value = []
            with patch("gse.curation.validation.bipolar_validator.BipolarValidator"):
                with patch("gse.curation.validation.coverage_checker.CoverageChecker"):
                    with patch("gse.curation.validation.hierarchy_validator.HierarchyValidator"):
                        with pytest.raises(ZeroDivisionError):
                            cmd_validate(args)
                        # Division by zero with no entries

    def test_with_entries(self, capsys):
        entry = MagicMock()
        entry.decomposition = {"GOOD": 1}
        args = mk_args(lexicon_db="x")

        bipolar_result = MagicMock()
        bipolar_result.passed = True
        coverage_result = MagicMock()
        coverage_result.passed = True
        hierarchy_result = MagicMock()
        hierarchy_result.passed = True

        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_validated_entries.return_value = [entry]
            with patch("gse.curation.validation.bipolar_validator.BipolarValidator") as MockBP:
                MockBP.return_value.validate.return_value = bipolar_result
                with patch("gse.curation.validation.coverage_checker.CoverageChecker") as MockCV:
                    MockCV.return_value.validate.return_value = coverage_result
                    with patch("gse.curation.validation.hierarchy_validator.HierarchyValidator") as MockH:
                        MockH.return_value.validate.return_value = hierarchy_result
                        cmd_validate(args)
        out = capsys.readouterr().out
        assert "VALIDATION RESULTS" in out
        assert "All pass:        1" in out

    def test_partial_pass(self, capsys):
        entry = MagicMock()
        entry.decomposition = {}
        args = mk_args(lexicon_db="x")

        bipolar_result = MagicMock()
        bipolar_result.passed = True
        coverage_result = MagicMock()
        coverage_result.passed = False
        hierarchy_result = MagicMock()
        hierarchy_result.passed = True

        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_validated_entries.return_value = [entry]
            with patch("gse.curation.validation.bipolar_validator.BipolarValidator") as MockBP:
                MockBP.return_value.validate.return_value = bipolar_result
                with patch("gse.curation.validation.coverage_checker.CoverageChecker") as MockCV:
                    MockCV.return_value.validate.return_value = coverage_result
                    with patch("gse.curation.validation.hierarchy_validator.HierarchyValidator") as MockH:
                        MockH.return_value.validate.return_value = hierarchy_result
                        cmd_validate(args)
        out = capsys.readouterr().out
        # All pass=0 (because coverage failed)
        assert "All pass:        0" in out


# ---------- cmd_export ----------


class TestCmdExport:
    def test_basic(self, tmp_path):
        entry = MagicMock()
        entry.lemma = "happy"
        entry.pos = "adj"
        entry.gloss = "feeling good"
        entry.source = "llm"
        entry.confidence = 0.9
        entry.frequency_rank = 500
        entry.decomposition = {"GOOD": 1}

        output = tmp_path / "out.json"
        args = mk_args(lexicon_db="x", output=str(output))

        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_validated_entries.return_value = [entry]
            cmd_export(args)

        data = json.loads(output.read_text())
        assert "happy" in data
        assert data["happy"]["pos"] == "adj"
        assert data["happy"]["decomposition"]["GOOD"] == 1

    def test_default_output_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        args = mk_args(lexicon_db="x", output=None)
        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_validated_entries.return_value = []
            cmd_export(args)
        # Default file created
        assert (tmp_path / "lexicon_export.json").exists()


# ---------- cmd_lookup ----------


class TestCmdLookup:
    def test_not_found(self, capsys):
        args = mk_args(lexicon_db="x", word="missing")
        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_lexeme.return_value = None
            cmd_lookup(args)
        assert "not found" in capsys.readouterr().out

    def test_found_prints_details(self, capsys):
        entry = MagicMock()
        entry.lemma = "happy"
        entry.pos = "adj"
        entry.gloss = "feeling good"
        entry.source = "llm"
        entry.confidence = 0.9
        entry.frequency_rank = 500
        entry.validation_status = "validated"
        entry.decomposition = {"GOOD": 1}

        args = mk_args(lexicon_db="x", word="happy")
        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_lexeme.return_value = entry
            cmd_lookup(args)
        out = capsys.readouterr().out
        assert "happy" in out
        assert "DECOMPOSITION" in out

    def test_groups_by_bank(self, capsys):
        entry = MagicMock()
        entry.lemma = "x"
        entry.pos = "n"
        entry.gloss = None
        entry.source = "llm"
        entry.confidence = 0.9
        entry.frequency_rank = 1
        entry.validation_status = "validated"
        # GOOD in bank 2 (evaluators)
        entry.decomposition = {"GOOD": 1, "BAD": 0}

        args = mk_args(lexicon_db="x", word="x")
        with patch("gse.curation.lexicon_db.LexiconDatabase") as MockDB:
            MockDB.return_value.get_lexeme.return_value = entry
            cmd_lookup(args)
        out = capsys.readouterr().out
        assert "Bank 2" in out
        assert "EVALUATORS" in out


# ---------- main ----------


class TestMain:
    def test_no_command_prints_help(self, capsys):
        with patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit):
                main()
        # argparse prints help

    def test_status_command(self, capsys):
        with patch("sys.argv", ["prog", "status"]):
            with patch("gse.curation.cli.commands.cmd_status") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_build_command(self):
        with patch("sys.argv", ["prog", "build", "--mock"]):
            with patch("gse.curation.cli.commands.cmd_build") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_init_command(self):
        with patch("sys.argv", ["prog", "init"]):
            with patch("gse.curation.cli.commands.cmd_init") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_validate_command(self):
        with patch("sys.argv", ["prog", "validate"]):
            with patch("gse.curation.cli.commands.cmd_validate") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_export_command(self):
        with patch("sys.argv", ["prog", "export"]):
            with patch("gse.curation.cli.commands.cmd_export") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_lookup_command(self):
        with patch("sys.argv", ["prog", "lookup", "happy"]):
            with patch("gse.curation.cli.commands.cmd_lookup") as mock_cmd:
                main()
                mock_cmd.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
