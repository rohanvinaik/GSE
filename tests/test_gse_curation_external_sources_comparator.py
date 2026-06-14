"""Manual contract tests for gse.curation.external_sources.comparator."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.comparator import (
    ComparisonResult,
    DisagreementRecord,
    ExternalSourcesComparator,
    integrate_comparison_into_pipeline,
)


def mk_disagreement(prim="GOOD", llm=1, ext=-1, src="verbnet", sev="sign_flip"):
    return DisagreementRecord(
        primitive=prim, llm_value=llm, external_value=ext,
        external_source=src, severity=sev,
    )


# ---------- DisagreementRecord ----------

class TestDisagreementRecord:
    def test_construction(self):
        d = mk_disagreement()
        assert d.primitive == "GOOD"
        assert d.llm_value == 1
        assert d.external_value == -1
        assert d.external_source == "verbnet"
        assert d.severity == "sign_flip"

    def test_repr_format(self):
        d = mk_disagreement()
        s = repr(d)
        assert "GOOD" in s
        assert "LLM=1" in s
        assert "verbnet=-1" in s
        assert "sign_flip" in s


# ---------- ComparisonResult ----------

class TestComparisonResult:
    def test_defaults(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={})
        assert r.disagreements == []
        assert r.agreements == []
        assert r.confidence_adjustment == 0.0
        assert r.needs_review is False

    def test_agreement_rate_empty(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={})
        assert r.agreement_rate == 0.0

    def test_agreement_rate_all_agree(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={},
                             agreements=["A", "B"])
        assert r.agreement_rate == 1.0

    def test_agreement_rate_mixed(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={},
                             agreements=["A"], disagreements=[mk_disagreement()])
        assert r.agreement_rate == 0.5

    def test_major_disagreements_filter(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={},
                             disagreements=[
                                 mk_disagreement(sev="major"),
                                 mk_disagreement(sev="minor"),
                                 mk_disagreement(sev="sign_flip"),
                             ])
        major = r.major_disagreements
        assert len(major) == 2
        assert {d.severity for d in major} == {"major", "sign_flip"}

    def test_no_minor_in_major(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={},
                             disagreements=[mk_disagreement(sev="minor")])
        assert r.major_disagreements == []


# ---------- ExternalSourcesComparator.__init__ ----------

class TestInit:
    def test_initial_state(self):
        c = ExternalSourcesComparator()
        assert c.parsers == {}
        assert c._loaded is False


# ---------- load_all_sources ----------

class TestLoadAllSources:
    def test_no_sources_available(self):
        # Patch every parser import to raise — comparator catches and continues
        c = ExternalSourcesComparator()
        with patch("gse.curation.external_sources.sentiwordnet.SentiWordNetParser",
                   side_effect=ImportError("nope")):
            with patch("gse.curation.external_sources.nrc_emotion.NRCEmotionParser",
                       side_effect=ImportError("nope")):
                with patch("gse.curation.external_sources.nrc_vad.NRCVADParser",
                           side_effect=ImportError("nope")):
                    with patch("gse.curation.external_sources.verbnet.VerbNetParser",
                               side_effect=ImportError("nope")):
                        with patch("gse.curation.external_sources.concreteness.ConcretenessParser",
                                   side_effect=ImportError("nope")):
                            with patch("gse.curation.external_sources.lancaster_sensorimotor.LancasterSensorimotorParser",
                                       side_effect=ImportError("nope")):
                                stats = c.load_all_sources()
        assert stats == {}
        assert c._loaded is True

    def test_loads_sentiwordnet(self):
        c = ExternalSourcesComparator()
        mock_parser = MagicMock()
        mock_parser.load.return_value = True
        mock_parser.entries = {"happy": []}
        with patch("gse.curation.external_sources.sentiwordnet.SentiWordNetParser",
                   return_value=mock_parser):
            with patch("gse.curation.external_sources.nrc_emotion.NRCEmotionParser",
                       side_effect=ImportError("nope")):
                with patch("gse.curation.external_sources.nrc_vad.NRCVADParser",
                           side_effect=ImportError("nope")):
                    with patch("gse.curation.external_sources.verbnet.VerbNetParser",
                               side_effect=ImportError("nope")):
                        with patch("gse.curation.external_sources.concreteness.ConcretenessParser",
                                   side_effect=ImportError("nope")):
                            with patch("gse.curation.external_sources.lancaster_sensorimotor.LancasterSensorimotorParser",
                                       side_effect=ImportError("nope")):
                                stats = c.load_all_sources()
        assert stats["sentiwordnet"] == 1
        assert "sentiwordnet" in c.parsers

    def test_load_returning_false_excluded(self):
        c = ExternalSourcesComparator()
        mock_parser = MagicMock()
        mock_parser.load.return_value = False  # Load failed
        with patch("gse.curation.external_sources.sentiwordnet.SentiWordNetParser",
                   return_value=mock_parser):
            with patch("gse.curation.external_sources.nrc_emotion.NRCEmotionParser",
                       side_effect=ImportError):
                with patch("gse.curation.external_sources.nrc_vad.NRCVADParser",
                           side_effect=ImportError):
                    with patch("gse.curation.external_sources.verbnet.VerbNetParser",
                               side_effect=ImportError):
                        with patch("gse.curation.external_sources.concreteness.ConcretenessParser",
                                   side_effect=ImportError):
                            with patch("gse.curation.external_sources.lancaster_sensorimotor.LancasterSensorimotorParser",
                                       side_effect=ImportError):
                                stats = c.load_all_sources()
        assert "sentiwordnet" not in stats
        assert "sentiwordnet" not in c.parsers


# ---------- get_external_primitives ----------

class TestGetExternalPrimitives:
    def test_no_parsers_empty(self):
        c = ExternalSourcesComparator()
        c._loaded = True
        assert c.get_external_primitives("x") == {}

    def test_collects_from_parsers(self):
        c = ExternalSourcesComparator()
        c._loaded = True
        p = MagicMock()
        p.to_primitives.return_value = {"GOOD": 1}
        c.parsers["s1"] = p
        result = c.get_external_primitives("happy")
        assert result == {"s1": {"GOOD": 1}}

    def test_lowercases_input(self):
        c = ExternalSourcesComparator()
        c._loaded = True
        p = MagicMock()
        p.to_primitives.return_value = {"GOOD": 1}
        c.parsers["s1"] = p
        c.get_external_primitives("HAPPY")
        p.to_primitives.assert_called_once_with("happy")

    def test_empty_primitives_omitted(self):
        c = ExternalSourcesComparator()
        c._loaded = True
        p = MagicMock()
        p.to_primitives.return_value = {}  # Empty
        c.parsers["s1"] = p
        assert c.get_external_primitives("x") == {}

    def test_auto_loads(self):
        c = ExternalSourcesComparator()
        with patch.object(c, "load_all_sources") as mock_load:
            mock_load.side_effect = lambda: setattr(c, "_loaded", True)
            c.get_external_primitives("x")
            mock_load.assert_called_once()


# ---------- compare ----------

class TestCompare:
    def _make_comparator(self, external_data):
        """external_data: dict[source_name, dict[primitive, value]]"""
        c = ExternalSourcesComparator()
        c._loaded = True
        for source, prims in external_data.items():
            p = MagicMock()
            p.to_primitives.return_value = prims
            c.parsers[source] = p
        return c

    def test_no_external_data(self):
        c = self._make_comparator({})
        result = c.compare("x", {"GOOD": 1})
        assert result.external_primitives == {}
        assert result.disagreements == []
        assert result.agreements == []
        assert result.confidence_adjustment == 0.0

    def test_complete_agreement(self):
        c = self._make_comparator({"s1": {"GOOD": 1}})
        result = c.compare("x", {"GOOD": 1})
        assert result.agreements == ["GOOD"]
        assert result.disagreements == []
        # All agree → adjustment = (1.0 * 2 - 1) - 0 = +1.0
        assert result.confidence_adjustment == pytest.approx(1.0)

    def test_minor_disagreement_zero_vs_nonzero(self):
        # LLM says 0, external says 1
        c = self._make_comparator({"s1": {"GOOD": 1}})
        result = c.compare("x", {"GOOD": 0})
        assert len(result.disagreements) == 1
        assert result.disagreements[0].severity == "minor"

    def test_minor_external_zero(self):
        # LLM 1, external 0 — wait, external would not include 0 typically
        # but if it did, llm_val=1, ext_val=0 → minor
        c = ExternalSourcesComparator()
        c._loaded = True
        p = MagicMock()
        p.to_primitives.return_value = {"GOOD": 0}
        c.parsers["s1"] = p
        result = c.compare("x", {"GOOD": 1})
        assert result.disagreements[0].severity == "minor"

    def test_sign_flip_positive_to_negative(self):
        c = self._make_comparator({"s1": {"GOOD": -1}})
        result = c.compare("x", {"GOOD": 1})
        assert result.disagreements[0].severity == "sign_flip"

    def test_sign_flip_negative_to_positive(self):
        c = self._make_comparator({"s1": {"GOOD": 1}})
        result = c.compare("x", {"GOOD": -1})
        assert result.disagreements[0].severity == "sign_flip"

    def test_dedup_agreements(self):
        # Two sources both agree on GOOD=1 → only one in agreements list
        c = self._make_comparator({
            "s1": {"GOOD": 1},
            "s2": {"GOOD": 1},
        })
        result = c.compare("x", {"GOOD": 1})
        assert result.agreements == ["GOOD"]  # not duplicated

    def test_needs_review_high_disagreement(self):
        # 1 agreement, 1 sign_flip → 50% disagree > 30% threshold
        c = self._make_comparator({"s1": {"GOOD": -1, "BIG": 1}})
        result = c.compare("x", {"GOOD": 1, "BIG": 1})
        assert result.needs_review is True

    def test_needs_review_due_to_major(self):
        # Even 1 major disagreement triggers review
        c = self._make_comparator({"s1": {"GOOD": -1}})
        result = c.compare("x", {"GOOD": 1})
        assert result.needs_review is True

    def test_no_review_when_all_agree(self):
        c = self._make_comparator({"s1": {"GOOD": 1}})
        result = c.compare("x", {"GOOD": 1})
        assert result.needs_review is False

    def test_custom_review_threshold(self):
        # Two prims, 1 agree, 1 minor disagree → 50% disagree
        # With threshold=0.7, should NOT flag from rate alone — but minor isn't major either
        c = self._make_comparator({"s1": {"GOOD": 1, "BIG": 1}})
        result = c.compare("x", {"GOOD": 1, "BIG": 0}, review_threshold=0.7)
        # 50% disagree, threshold 0.7 → not from rate, and minor isn't major → no review
        assert result.needs_review is False

    def test_confidence_adjustment_range(self):
        # All disagree (sign flips) → adjustment = (0 * 2 - 1) - 0.5 = -1.5
        c = self._make_comparator({"s1": {"GOOD": -1}})
        result = c.compare("x", {"GOOD": 1})
        # major_count=1, total=1 → -1 - 0.5 = -1.5
        assert result.confidence_adjustment == pytest.approx(-1.5)

    def test_word_field(self):
        c = self._make_comparator({})
        result = c.compare("hello", {})
        assert result.word == "hello"

    def test_llm_primitives_propagated(self):
        c = self._make_comparator({})
        result = c.compare("x", {"GOOD": 1, "BIG": -1})
        assert result.llm_primitives == {"GOOD": 1, "BIG": -1}


# ---------- compare_batch ----------

class TestCompareBatch:
    def test_empty(self):
        c = ExternalSourcesComparator()
        c._loaded = True
        assert c.compare_batch({}) == {}

    def test_multiple_words(self):
        c = ExternalSourcesComparator()
        c._loaded = True
        results = c.compare_batch({"a": {"GOOD": 1}, "b": {"BIG": -1}})
        assert "a" in results
        assert "b" in results
        assert isinstance(results["a"], ComparisonResult)


# ---------- get_high_confidence_disagreements ----------

class TestGetHighConfidenceDisagreements:
    def test_empty(self):
        c = ExternalSourcesComparator()
        assert c.get_high_confidence_disagreements({}) == []

    def test_multiple_sources_agree_on_disagreement(self):
        # 2 sources both say GOOD=-1, LLM says GOOD=1 → high-conf disagreement
        result = ComparisonResult(
            word="x", llm_primitives={"GOOD": 1}, external_primitives={},
            disagreements=[
                mk_disagreement(prim="GOOD", llm=1, ext=-1, src="s1"),
                mk_disagreement(prim="GOOD", llm=1, ext=-1, src="s2"),
            ],
        )
        c = ExternalSourcesComparator()
        hc = c.get_high_confidence_disagreements({"x": result})
        assert len(hc) == 1
        assert hc[0][0] == "x"

    def test_sources_disagree_with_each_other_excluded(self):
        # Sources have different ext_values → not high-conf
        result = ComparisonResult(
            word="x", llm_primitives={"GOOD": 1}, external_primitives={},
            disagreements=[
                mk_disagreement(prim="GOOD", ext=-1, src="s1"),
                mk_disagreement(prim="GOOD", ext=0, src="s2"),  # different value
            ],
        )
        c = ExternalSourcesComparator()
        assert c.get_high_confidence_disagreements({"x": result}) == []

    def test_min_sources_filter(self):
        result = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={},
            disagreements=[mk_disagreement(src="s1")],  # only 1 source
        )
        c = ExternalSourcesComparator()
        # min_sources=2 default
        assert c.get_high_confidence_disagreements({"x": result}) == []

    def test_custom_min_sources(self):
        result = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={},
            disagreements=[mk_disagreement(src="s1")],
        )
        c = ExternalSourcesComparator()
        # min_sources=1 allows it
        hc = c.get_high_confidence_disagreements({"x": result}, min_sources=1)
        assert len(hc) == 1


# ---------- generate_report ----------

class TestGenerateReport:
    def test_empty(self):
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        assert "Total words analyzed: 0" in report

    def test_summary_counts(self):
        r1 = ComparisonResult(word="a", llm_primitives={},
                              external_primitives={"s1": {}},
                              needs_review=True)
        r2 = ComparisonResult(word="b", llm_primitives={},
                              external_primitives={})
        c = ExternalSourcesComparator()
        report = c.generate_report({"a": r1, "b": r2})
        assert "Total words analyzed: 2" in report
        assert "Words with external data: 1" in report
        assert "Words needing review: 1" in report

    def test_includes_high_conf_section(self):
        result = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={},
            disagreements=[
                mk_disagreement(prim="GOOD", ext=-1, src="s1"),
                mk_disagreement(prim="GOOD", ext=-1, src="s2"),
            ],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": result})
        assert "High-Confidence Disagreements" in report
        assert "**x**" in report

    def test_top_20_high_conf_limit(self):
        results = {}
        for i in range(30):
            r = ComparisonResult(
                word=f"w{i}", llm_primitives={}, external_primitives={},
                disagreements=[
                    mk_disagreement(prim="P", ext=-1, src="s1"),
                    mk_disagreement(prim="P", ext=-1, src="s2"),
                ],
            )
            results[f"w{i}"] = r
        c = ExternalSourcesComparator()
        report = c.generate_report(results)
        # Should be 20 entries in high-conf section
        high_conf_lines = [l for l in report.split("\n")
                           if l.startswith("- **w")]
        assert len(high_conf_lines) == 20

    def test_words_needing_review_section(self):
        r = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={"s1": {}},
            needs_review=True,
            disagreements=[mk_disagreement(sev="major")],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": r})
        assert "Words Needing Review" in report
        assert "**x**" in report

    def test_no_review_section_when_zero(self):
        r = ComparisonResult(word="x", llm_primitives={}, external_primitives={})
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": r})
        assert "Words Needing Review" not in report

    def test_exact_report_header(self):
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        # Pin exact header literal
        assert report.startswith("# External Sources Comparison Report\n")

    def test_exact_summary_header(self):
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        assert "## Summary" in report

    def test_exact_total_line(self):
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        # Pin exact prefix string
        assert "- Total words analyzed: 0" in report

    def test_exact_with_external_line(self):
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        assert "- Words with external data: 0" in report

    def test_exact_needs_review_line(self):
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        assert "- Words needing review: 0" in report

    def test_exact_high_conf_header(self):
        result = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={},
            disagreements=[
                mk_disagreement(prim="GOOD", ext=-1, src="s1"),
                mk_disagreement(prim="GOOD", ext=-1, src="s2"),
            ],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": result})
        assert "## High-Confidence Disagreements (1)" in report

    def test_exact_high_conf_description_line(self):
        result = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={},
            disagreements=[
                mk_disagreement(prim="P", ext=-1, src="s1"),
                mk_disagreement(prim="P", ext=-1, src="s2"),
            ],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": result})
        assert "Multiple external sources agree, LLM differs:" in report

    def test_exact_review_section_header(self):
        r = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={"s1": {}},
            needs_review=True,
            disagreements=[mk_disagreement(sev="major")],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": r})
        assert "## Words Needing Review (1)" in report

    def test_exact_review_word_format(self):
        # Pin exact format "- **word**: N major disagreements"
        r = ComparisonResult(
            word="happy", llm_primitives={}, external_primitives={"s1": {}},
            needs_review=True,
            disagreements=[
                mk_disagreement(sev="major"),
                mk_disagreement(sev="major"),
            ],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"happy": r})
        assert "- **happy**: 2 major disagreements" in report

    def test_exact_review_indent(self):
        # Sub-disagreement indent is 2 spaces
        r = ComparisonResult(
            word="happy", llm_primitives={}, external_primitives={"s1": {}},
            needs_review=True,
            disagreements=[mk_disagreement(prim="GOOD", sev="major", llm=1, ext=-1)],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"happy": r})
        # Indented sub-line
        lines = report.split("\n")
        indented = [l for l in lines if l.startswith("  - ")]
        assert len(indented) >= 1

    def test_blank_line_after_summary(self):
        # Pin the empty-string lines.append("") after summary
        c = ExternalSourcesComparator()
        report = c.generate_report({})
        lines = report.split("\n")
        # After "- Words needing review: 0" should come ""
        i = lines.index("- Words needing review: 0")
        assert lines[i + 1] == ""

    def test_blank_lines_around_high_conf(self):
        # After "Multiple external sources..." should be blank line, then items
        result = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={},
            disagreements=[
                mk_disagreement(prim="P", ext=-1, src="s1"),
                mk_disagreement(prim="P", ext=-1, src="s2"),
            ],
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": result})
        lines = report.split("\n")
        i = lines.index("Multiple external sources agree, LLM differs:")
        # Next line should be blank
        assert lines[i + 1] == ""
        # After the high-conf entries there's another blank line
        # find the line with "**x**"
        for j, line in enumerate(lines):
            if "**x**" in line:
                # The next line after the last high-conf entry should be blank
                assert lines[j + 1] == ""
                break

    def test_review_section_limit_3_major_per_word(self):
        # Only first 3 major disagreements shown per word
        disagrees = [mk_disagreement(prim=f"P{i}", sev="major") for i in range(5)]
        r = ComparisonResult(
            word="x", llm_primitives={}, external_primitives={"s1": {}},
            needs_review=True,
            disagreements=disagrees,
        )
        c = ExternalSourcesComparator()
        report = c.generate_report({"x": r})
        sub_lines = [l for l in report.split("\n") if l.startswith("  - ")]
        assert len(sub_lines) == 3


# ---------- integrate_comparison_into_pipeline ----------

class TestIntegrateComparison:
    def test_runs_without_error(self, capsys):
        mock_llm = MagicMock()
        mock_llm.decompose_word.return_value = {"GOOD": 1}
        with patch("gse.curation.llm.ollama_client.OllamaClient", return_value=mock_llm):
            with patch.object(ExternalSourcesComparator, "load_all_sources"):
                with patch.object(ExternalSourcesComparator, "compare") as mock_compare:
                    mock_result = ComparisonResult(
                        word="happy", llm_primitives={}, external_primitives={},
                        agreements=["GOOD"],
                        confidence_adjustment=0.5,
                    )
                    mock_compare.return_value = mock_result
                    integrate_comparison_into_pipeline()
        out = capsys.readouterr().out
        assert "happy" in out
        assert "100.0%" in out  # full agreement rate

    def test_prints_disagreements(self, capsys):
        mock_llm = MagicMock()
        mock_llm.decompose_word.return_value = {}
        with patch("gse.curation.llm.ollama_client.OllamaClient", return_value=mock_llm):
            with patch.object(ExternalSourcesComparator, "load_all_sources"):
                with patch.object(ExternalSourcesComparator, "compare") as mock_compare:
                    mock_result = ComparisonResult(
                        word="happy", llm_primitives={}, external_primitives={},
                        disagreements=[mk_disagreement()],
                    )
                    mock_compare.return_value = mock_result
                    integrate_comparison_into_pipeline()
        out = capsys.readouterr().out
        assert "Disagreements" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
