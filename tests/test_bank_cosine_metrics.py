"""Tests for the bank-projected cosine metrics."""

from unittest.mock import MagicMock

from gse.benchmarks.metrics import bank_cosine_signature, min_bank_cosine
from gse.primitives_v2 import SemanticBank


def _vec(per_bank_cosines, global_cos):
    """Build a paired (v1, v2) mock where with_bank_only returns predictable cosines.

    per_bank_cosines maps SemanticBank value -> cosine to report (or None to
    simulate an empty-bank projection).
    """
    v1 = MagicMock()
    v2 = MagicMock()
    v1.cosine = MagicMock(return_value=global_cos)
    v2.cosine = MagicMock(return_value=global_cos)

    def proj_factory(self, bank_idx, _dims):
        cos = per_bank_cosines.get(bank_idx)
        out = MagicMock()
        if cos is None:
            out.nnz = 0
        else:
            out.nnz = 10
            out.cosine = MagicMock(return_value=cos)
        return out

    v1.with_bank_only = lambda b, d: proj_factory(v1, b, d)
    v2.with_bank_only = lambda b, d: proj_factory(v2, b, d)
    return v1, v2


class TestBankCosineSignature:
    def test_picks_most_negative_bank(self):
        # EVALUATORS opposes; others mostly positive
        per = {
            SemanticBank.EVALUATORS.value: -1.0,
            SemanticBank.MENTAL.value: +0.8,
            SemanticBank.ACTION.value: +0.7,
        }
        v1, v2 = _vec(per, global_cos=0.4)
        sig = bank_cosine_signature(v1, v2)
        assert sig.min_bank_name == "EVALUATORS"
        assert sig.min_bank_cosine == -1.0
        assert sig.global_cosine == 0.4

    def test_skips_empty_banks(self):
        # Only one bank has support on both sides
        per = {SemanticBank.SPATIAL.value: -0.5}
        v1, v2 = _vec(per, global_cos=-0.5)
        sig = bank_cosine_signature(v1, v2)
        assert sig.min_bank_name == "SPATIAL"
        assert sig.per_bank["MENTAL"] is None
        assert sig.per_bank["SPATIAL"] == -0.5

    def test_falls_back_to_global_when_no_bank_populated(self):
        v1, v2 = _vec({}, global_cos=0.3)
        sig = bank_cosine_signature(v1, v2)
        assert sig.min_bank_name is None
        assert sig.min_bank_cosine == 0.3

    def test_all_banks_positive_picks_smallest_positive(self):
        per = {
            SemanticBank.EVALUATORS.value: +0.9,
            SemanticBank.MENTAL.value: +0.2,
            SemanticBank.ACTION.value: +0.5,
        }
        v1, v2 = _vec(per, global_cos=0.6)
        sig = bank_cosine_signature(v1, v2)
        # "min" means most-negative; with all positive, least-positive wins
        assert sig.min_bank_name == "MENTAL"
        assert sig.min_bank_cosine == 0.2


class TestMinBankCosine:
    def test_returns_min_bank_value(self):
        per = {
            SemanticBank.EVALUATORS.value: -1.0,
            SemanticBank.MENTAL.value: +0.4,
        }
        v1, v2 = _vec(per, global_cos=-0.3)
        assert min_bank_cosine(v1, v2) == -1.0

    def test_returns_global_when_no_banks_populated(self):
        v1, v2 = _vec({}, global_cos=0.7)
        assert min_bank_cosine(v1, v2) == 0.7
