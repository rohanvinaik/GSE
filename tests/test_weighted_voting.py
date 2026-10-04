"""Tests for confidence-weighted voting aggregation."""

import pytest

from gse.curation.external_sources.weighted_voting import aggregate_weighted


class TestSingleSource:
    def test_single_positive_vote(self):
        result = aggregate_weighted("good", {"src_a": {"GOOD": (1, 0.8)}})
        vote = result.primitives["GOOD"]
        assert vote.value == 1
        # winner_weight=0.8, loser_weight=0 → raw ~= 0.8/(0.8+0.01) ≈ 0.988
        # boost = 0.7 + 0.1*1 = 0.8
        assert vote.confidence == pytest.approx(0.988 * 0.8, rel=1e-2)
        assert vote.contributing_sources == ("src_a",)
        assert result.source_count == 1

    def test_zero_value_votes_ignored(self):
        result = aggregate_weighted("x", {"src_a": {"GOOD": (0, 0.9)}})
        assert result.primitives == {}
        assert result.source_count == 0  # source contributed nothing usable


class TestAgreement:
    def test_multiple_sources_agreeing_boost_confidence(self):
        votes = {
            "src_a": {"GOOD": (1, 0.5)},
            "src_b": {"GOOD": (1, 0.5)},
            "src_c": {"GOOD": (1, 0.5)},
        }
        result = aggregate_weighted("good", votes)
        vote = result.primitives["GOOD"]
        # raw_conf = 1.5 / (1.5 + 0 + 0.01) ≈ 0.993
        # boost = 0.7 + 0.1*3 = 1.0
        assert vote.confidence == pytest.approx(0.993, rel=1e-2)
        assert set(vote.contributing_sources) == {"src_a", "src_b", "src_c"}

    def test_boost_caps_at_one(self):
        # 5 sources all agree
        votes = {f"s{i}": {"GOOD": (1, 0.5)} for i in range(5)}
        result = aggregate_weighted("good", votes)
        # boost = min(1.0, 0.7 + 0.1*5) = min(1.0, 1.2) = 1.0
        assert result.primitives["GOOD"].confidence <= 1.0


class TestDisagreement:
    def test_higher_confidence_wins(self):
        votes = {
            "high_conf": {"GOOD": (1, 0.9)},
            "low_conf": {"GOOD": (-1, 0.2)},
        }
        result = aggregate_weighted("x", votes)
        # pos=0.9, neg=0.2 → positive wins; raw = 0.9/(0.9+0.2+0.01) ≈ 0.811
        # boost = 0.7 + 0.1*2 = 0.9
        vote = result.primitives["GOOD"]
        assert vote.value == 1
        assert vote.confidence == pytest.approx(0.811 * 0.9, rel=1e-2)

    def test_majority_count_loses_to_concentrated_confidence(self):
        # 3 weak negatives vs 1 strong positive — strong wins because
        # confidence-weighted, not vote-count
        votes = {
            "strong": {"GOOD": (1, 0.95)},
            "weak_a": {"GOOD": (-1, 0.2)},
            "weak_b": {"GOOD": (-1, 0.2)},
            "weak_c": {"GOOD": (-1, 0.2)},
        }
        result = aggregate_weighted("x", votes)
        assert result.primitives["GOOD"].value == 1

    def test_tied_weight_marks_value_zero_confidence_half(self):
        votes = {
            "src_a": {"GOOD": (1, 0.5)},
            "src_b": {"GOOD": (-1, 0.5)},
        }
        result = aggregate_weighted("x", votes)
        vote = result.primitives["GOOD"]
        assert vote.value == 0
        assert vote.confidence == 0.5
        assert set(vote.contributing_sources) == {"src_a", "src_b"}


class TestIsolation:
    def test_different_primitives_aggregated_independently(self):
        votes = {
            "src_a": {"GOOD": (1, 0.9), "FEEL": (1, 0.5)},
            "src_b": {"GOOD": (1, 0.5), "FEEL": (-1, 0.5)},
        }
        result = aggregate_weighted("happy", votes)
        # GOOD: both +1 → still +1
        assert result.primitives["GOOD"].value == 1
        # FEEL: 0.5 vs 0.5 → tie
        assert result.primitives["FEEL"].value == 0
        assert result.source_count == 2

    def test_empty_source_votes_returns_empty_aggregation(self):
        result = aggregate_weighted("x", {})
        assert result.primitives == {}
        assert result.source_count == 0
