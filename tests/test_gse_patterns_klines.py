"""Manual contract tests for gse.patterns.klines."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.patterns.klines import KLine, KLineStore


def make_activation(prim, polarity=1):
    a = MagicMock()
    a.primitive = prim
    a.polarity = polarity
    return a


# ---------- KLine ----------


class TestKLineInit:
    def test_defaults(self):
        k = KLine(id="x", pattern=frozenset([("GOOD", 1)]))
        assert k.frequency == 1
        assert k.strength == 1.0
        assert k.created_at > 0
        assert k.last_used > 0


class TestMatches:
    def test_perfect_match(self):
        k = KLine(id="x", pattern=frozenset([("A", 1), ("B", 1)]))
        score = k.matches({("A", 1), ("B", 1)})
        assert score == 1.0

    def test_partial_overlap(self):
        k = KLine(id="x", pattern=frozenset([("A", 1), ("B", 1)]))
        # query = {(A,1), (C,1)} → intersection=1, union=3
        score = k.matches({("A", 1), ("C", 1)})
        assert score == pytest.approx(1 / 3)

    def test_no_overlap(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]))
        score = k.matches({("B", 1)})
        assert score == 0.0

    def test_empty_pattern_zero(self):
        k = KLine(id="x", pattern=frozenset())
        score = k.matches({("A", 1)})
        assert score == 0.0

    def test_empty_query_zero(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]))
        score = k.matches(set())
        assert score == 0.0


class TestGetMissing:
    def test_returns_diff(self):
        k = KLine(id="x", pattern=frozenset([("A", 1), ("B", 1), ("C", 1)]))
        result = k.get_missing({("A", 1)})
        assert result == {("B", 1), ("C", 1)}

    def test_all_present_returns_empty(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]))
        assert k.get_missing({("A", 1), ("B", 1)}) == set()


class TestReinforce:
    def test_success_increases_strength(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]), strength=1.0)
        k.reinforce(success=True, amount=0.5)
        assert k.strength == 1.5

    def test_failure_decreases_strength_faster(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]), strength=2.0)
        k.reinforce(success=False, amount=0.1)
        # decay = 2 * 0.1 = 0.2
        assert k.strength == pytest.approx(1.8)

    def test_strength_capped_at_10(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]), strength=9.9)
        k.reinforce(success=True, amount=1.0)
        assert k.strength == 10.0

    def test_strength_floor_001(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]), strength=0.1)
        k.reinforce(success=False, amount=1.0)
        # 0.1 - 2*1.0 = -1.9 → clamped to 0.01
        assert k.strength == 0.01

    def test_last_used_updated(self):
        k = KLine(id="x", pattern=frozenset([("A", 1)]), last_used=0)
        k.reinforce(success=True)
        assert k.last_used > 0


# ---------- KLineStore.__init__ ----------


class TestStoreInit:
    def test_defaults(self):
        s = KLineStore()
        assert s.min_pattern_size == 2
        assert s.max_patterns == 10_000
        assert len(s) == 0

    def test_custom_params(self):
        s = KLineStore(min_pattern_size=3, max_patterns=100)
        assert s.min_pattern_size == 3
        assert s.max_patterns == 100


# ---------- add_or_reinforce ----------


class TestAddOrReinforce:
    def test_pattern_below_min_returns_none(self):
        s = KLineStore(min_pattern_size=3)
        assert s.add_or_reinforce({("A", 1)}) is None

    def test_new_pattern_added(self):
        s = KLineStore()
        k = s.add_or_reinforce({("A", 1), ("B", 1)})
        assert k is not None
        assert len(s) == 1

    def test_duplicate_reinforces(self):
        s = KLineStore()
        k1 = s.add_or_reinforce({("A", 1), ("B", 1)})
        k2 = s.add_or_reinforce({("A", 1), ("B", 1)})
        # Same K-line returned
        assert k1 is k2
        assert k1.frequency == 2

    def test_indexes_by_primitive(self):
        s = KLineStore()
        k = s.add_or_reinforce({("A", 1), ("B", 1)})
        assert k.id in s._primitive_index["A"]
        assert k.id in s._primitive_index["B"]

    def test_eviction_triggers_at_max(self):
        s = KLineStore(max_patterns=2)
        s.add_or_reinforce({("A", 1), ("B", 1)})
        s.add_or_reinforce({("C", 1), ("D", 1)})
        s.add_or_reinforce({("E", 1), ("F", 1)})
        # Eviction triggered → len should be 2
        assert len(s) == 2


# ---------- add_from_activations ----------


class TestAddFromActivations:
    def test_builds_pattern_from_activations(self):
        s = KLineStore()
        acts = [make_activation("A", 1), make_activation("B", -1)]
        k = s.add_from_activations(acts)
        assert k is not None
        assert ("A", 1) in k.pattern
        assert ("B", -1) in k.pattern


# ---------- _evict_weakest ----------


class TestEvictWeakest:
    def test_no_op_on_empty(self):
        s = KLineStore()
        s._evict_weakest()  # should not crash
        assert len(s) == 0

    def test_removes_lowest_strength(self):
        s = KLineStore()
        # Add 3 patterns with different strengths
        s.add_or_reinforce({("A", 1), ("B", 1)})
        s.add_or_reinforce({("C", 1), ("D", 1)})
        # First K-line: lower its strength
        first_id = next(iter(s._klines))
        s._klines[first_id].strength = 0.01
        s._evict_weakest()
        assert first_id not in s._klines


# ---------- find_matching ----------


class TestFindMatching:
    def test_empty_query_returns_empty(self):
        s = KLineStore()
        s.add_or_reinforce({("A", 1), ("B", 1)})
        assert s.find_matching(set()) == []

    def test_finds_overlapping(self):
        s = KLineStore()
        k = s.add_or_reinforce({("A", 1), ("B", 1)})
        results = s.find_matching({("A", 1), ("B", 1)}, min_overlap=0.5)
        # Perfect match overlap=1.0
        assert any(r[0].id == k.id for r in results)

    def test_min_overlap_filters(self):
        s = KLineStore()
        s.add_or_reinforce({("A", 1), ("B", 1), ("C", 1)})
        # query {(A,1)} → overlap = 1/3 = 0.33; threshold 0.5 filters it
        results = s.find_matching({("A", 1)}, min_overlap=0.5)
        assert results == []

    def test_top_k_limits(self):
        s = KLineStore()
        for i in range(5):
            s.add_or_reinforce({("A", 1), (f"B{i}", 1)})
        results = s.find_matching({("A", 1), ("B0", 1)}, top_k=2, min_overlap=0.3)
        assert len(results) <= 2


# ---------- complete_pattern ----------


class TestCompletePattern:
    def test_no_matches_empty(self):
        s = KLineStore()
        assert s.complete_pattern({("XYZZY", 1)}) == []

    def test_predicts_missing(self):
        s = KLineStore()
        s.add_or_reinforce({("A", 1), ("B", 1), ("C", 1)})
        s.add_or_reinforce({("A", 1), ("B", 1), ("D", 1)})
        # query {(A,1)} matches both K-lines (overlap=1/3)
        # missing from query: B, C from kl1; B, D from kl2
        # B should rank high (in both)
        result = s.complete_pattern({("A", 1)}, min_confidence=0.0)
        # At least one prediction
        assert len(result) > 0


# ---------- save / load ----------


class TestSaveLoad:
    def test_roundtrip(self, tmp_path):
        s1 = KLineStore()
        s1.add_or_reinforce({("A", 1), ("B", -1)})
        s1.add_or_reinforce({("C", 1), ("D", 1)})

        path = str(tmp_path / "k.json")
        s1.save(path)

        s2 = KLineStore.load(path)
        assert len(s2) == 2
        # Indices reconstructed
        for kline in s2._klines.values():
            for prim, _ in kline.pattern:
                assert kline.id in s2._primitive_index[prim]


# ---------- __len__ ----------


class TestLen:
    def test_empty(self):
        assert len(KLineStore()) == 0

    def test_with_klines(self):
        s = KLineStore()
        s.add_or_reinforce({("A", 1), ("B", 1)})
        assert len(s) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
