"""Tests for gse.benchmarks.run CLI plumbing.

These tests stub the GSEEncoder so they don't hit the heavy real encoder;
the goal is to verify the runner wires the datasets, encoder, and metrics
correctly, not to re-test the metrics themselves.
"""

from unittest.mock import MagicMock, patch

import pytest

from gse.benchmarks.datasets import BenchmarkDataset, SentencePair, WordPair
from gse.benchmarks.run import PairResult, _encode_pairs, run_task


def _fake_encoder(cos_value, bank_cos=None):
    """Encoder whose every encode() returns a vector with the given cosine.

    When ``bank_cos`` is provided, every with_bank_only-projected vector also
    reports that cosine and a nonzero ``nnz`` so bank_cosine_signature
    proceeds rather than skipping. Otherwise, projected vectors report
    ``nnz == 0`` so bank metrics are skipped (matches the correlation task
    path that doesn't request bank signatures).
    """
    encoder = MagicMock()

    def fake_encode(_text):
        result = MagicMock()
        result.vector.cosine = MagicMock(return_value=cos_value)
        if bank_cos is None:
            projected = MagicMock()
            projected.nnz = 0
            result.vector.with_bank_only = MagicMock(return_value=projected)
        else:
            projected = MagicMock()
            projected.nnz = 10
            projected.cosine = MagicMock(return_value=bank_cos)
            result.vector.with_bank_only = MagicMock(return_value=projected)
        return result

    encoder.encode = MagicMock(side_effect=fake_encode)
    return encoder


class TestEncodePairs:
    def test_word_pair_dataset_records_gold_and_predicted(self):
        ds = BenchmarkDataset(
            "toy",
            [WordPair("dog", "puppy", 0.9), WordPair("hot", "cold", 0.0)],
        )
        encoder = _fake_encoder(0.5)
        results = _encode_pairs(ds, encoder)
        assert results == [
            PairResult("dog", "puppy", 0.9, 0.5),
            PairResult("hot", "cold", 0.0, 0.5),
        ]

    def test_sentence_pair_dataset_uses_sentence_attrs(self):
        ds = BenchmarkDataset("toy-sts", [SentencePair("the cat sat", "a cat is sitting", 4.5)])
        encoder = _fake_encoder(0.7)
        results = _encode_pairs(ds, encoder)
        assert results[0].text1 == "the cat sat"
        assert results[0].text2 == "a cat is sitting"
        assert results[0].gold == 4.5
        assert results[0].predicted == 0.7

    def test_limit_truncates_pairs(self):
        ds = BenchmarkDataset(
            "toy",
            [WordPair(f"w{i}", f"v{i}", float(i)) for i in range(10)],
        )
        encoder = _fake_encoder(0.0)
        assert len(_encode_pairs(ds, encoder, limit=3)) == 3


class TestRunTask:
    def test_unknown_task_raises(self):
        with pytest.raises(ValueError, match="Unknown task"):
            run_task("does-not-exist")

    def test_antonyms_task_uses_negative_rate(self, capsys):
        # Antonyms task now requests per-bank signatures; provide a bank cosine
        # so the bank-projected section also reports.
        ds = BenchmarkDataset("toy-ant", [WordPair("good", "bad", 0.0)])
        encoder = _fake_encoder(-0.8, bank_cos=-0.9)
        with patch("gse.benchmarks.run.TASKS", {"antonyms": (lambda: ds, "antonym")}):
            results = run_task("antonyms", encoder=encoder)
        assert results[0].predicted == -0.8
        assert results[0].min_bank_cosine == -0.9
        out = capsys.readouterr().out
        assert "Negative rate:  1.000" in out  # global cos < 0
        assert "Mean cos:       -0.8000" in out
        # Bank-projected section also present
        assert "Bank-projected" in out
        assert "Mean min-bank:  -0.9000" in out

    def test_antonyms_global_zero_but_bank_negative(self, capsys):
        # The realistic case the metric was added for: global cos positive
        # (shared context) but a single bank opposes strongly.
        ds = BenchmarkDataset("toy-ant", [WordPair("good", "bad", 0.0)])
        encoder = _fake_encoder(+0.6, bank_cos=-1.0)
        with patch("gse.benchmarks.run.TASKS", {"antonyms": (lambda: ds, "antonym")}):
            results = run_task("antonyms", encoder=encoder)
        assert results[0].predicted == +0.6
        assert results[0].min_bank_cosine == -1.0
        out = capsys.readouterr().out
        # Global says "no antonymy detected" but bank-projected catches it
        assert "Negative rate:  0.000" in out
        assert "Mean min-bank:  -1.0000" in out

    def test_synonyms_task_reports_positive_rate(self, capsys):
        ds = BenchmarkDataset(
            "toy-syn",
            [WordPair("happy", "joyful", 1.0), WordPair("big", "large", 1.0)],
        )
        encoder = _fake_encoder(0.5, bank_cos=0.5)
        with patch("gse.benchmarks.run.TASKS", {"synonyms": (lambda: ds, "synonym")}):
            run_task("synonyms", encoder=encoder)
        out = capsys.readouterr().out
        assert "Positive rate:  1.000" in out

    def test_bipolar_pairs_task_dispatched_through_run_task(self, capsys):
        # Mock encoder that returns vectors with bank-projected cos = -1
        # for any pair. Verifies run_task dispatches to run_bipolar_pairs
        # and the per-pair output format.
        encoder = MagicMock()

        def fake_encode(_text):
            r = MagicMock()
            r.vector.cosine = MagicMock(return_value=-1.0)
            projected = MagicMock()
            projected.nnz = 5
            projected.cosine = MagicMock(return_value=-1.0)
            r.vector.with_bank_only = MagicMock(return_value=projected)
            return r

        encoder.encode = MagicMock(side_effect=fake_encode)
        results = run_task("bipolar_pairs", encoder=encoder)
        out = capsys.readouterr().out
        # 14 BIPOLAR_DIMENSIONS expected
        assert len(results) == 14
        assert "Bipolar antagonism" in out
        # When every pair hits cos = -1.0, all 14 pass
        assert "14/14 pairs pass" in out

    def test_bipolar_pairs_records_target_bank(self, capsys):
        encoder = MagicMock()

        def fake_encode(_text):
            r = MagicMock()
            r.vector.cosine = MagicMock(return_value=0.5)
            projected = MagicMock()
            projected.nnz = 5
            projected.cosine = MagicMock(return_value=-0.95)
            r.vector.with_bank_only = MagicMock(return_value=projected)
            return r

        encoder.encode = MagicMock(side_effect=fake_encode)
        results = run_task("bipolar_pairs", encoder=encoder)
        # Each pair has the target bank recorded
        bank_names = {r.min_bank_name for r in results}
        # 8 SemanticBank values, but bipolar dimensions only span 6 banks
        # (no QUANTITY or MENTAL bipolars)
        assert bank_names == {
            "SUBSTANTIVES",
            "EVALUATORS",
            "ACTION",
            "TEMPORAL",
            "SPATIAL",
            "LOGICAL",
        }

    def test_correlation_task_prints_spearman(self, capsys):
        # Two pairs with monotonic gold-vs-predicted: predicted should track gold perfectly.
        ds = BenchmarkDataset(
            "toy-corr",
            [WordPair("a", "b", 0.1), WordPair("c", "d", 0.9), WordPair("e", "f", 0.5)],
        )
        encoder = MagicMock()
        cos_values = iter([0.1, 0.9, 0.5, 0.1, 0.9, 0.5])  # paired encodes

        def encode(_t):
            r = MagicMock()
            r.vector.cosine = MagicMock(return_value=next(cos_values))
            return r

        encoder.encode = MagicMock(side_effect=encode)
        with patch("gse.benchmarks.run.TASKS", {"toy": (lambda: ds, "correlation")}):
            run_task("toy", encoder=encoder, n_bootstrap=10)
        out = capsys.readouterr().out
        assert "Spearman rho:" in out
        assert "95% CI:" in out
