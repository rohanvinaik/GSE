"""
Tests for K-line pattern storage and completion.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.patterns import KLine, KLineStore
from gse.primitives_v2 import Polarity, PrimitiveActivation


class TestKLineStorage:
    def test_add_creates_kline(self):
        store = KLineStore()
        pattern = {("GOOD", 1), ("FEEL", 1), ("SOMEONE", 1)}
        kl = store.add_or_reinforce(pattern)
        assert kl is not None
        assert kl.frequency == 1
        assert len(store) == 1

    def test_add_below_min_size_returns_none(self):
        store = KLineStore(min_pattern_size=2)
        kl = store.add_or_reinforce({("GOOD", 1)})
        assert kl is None
        assert len(store) == 0

    def test_reinforcement_increments_frequency(self):
        store = KLineStore()
        pattern = {("GOOD", 1), ("FEEL", 1)}
        kl1 = store.add_or_reinforce(pattern)
        kl2 = store.add_or_reinforce(pattern)
        assert kl1.id == kl2.id
        assert kl2.frequency == 2
        assert len(store) == 1

    def test_add_from_activations(self):
        store = KLineStore()
        activations = [
            PrimitiveActivation(primitive="FEEL", role="experiencer", polarity=Polarity.POSITIVE),
            PrimitiveActivation(primitive="GOOD", role="evaluation", polarity=Polarity.NEGATIVE),
            PrimitiveActivation(primitive="SOMEONE", role="object", polarity=Polarity.POSITIVE),
        ]
        kl = store.add_from_activations(activations)
        assert kl is not None
        assert ("GOOD", -1) in kl.pattern
        assert ("FEEL", 1) in kl.pattern


class TestKLineMatching:
    def test_matches_jaccard(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1), ("GOOD", 1)}))
        overlap = kl.matches({("FEEL", 1), ("GOOD", 1), ("SOMEONE", 1)})
        # Intersection: 2; Union: 3 → 2/3
        assert abs(overlap - 2 / 3) < 1e-9

    def test_no_overlap_returns_zero(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1)}))
        assert kl.matches({("HEAR", 1)}) == 0.0

    def test_empty_query_returns_zero(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1)}))
        assert kl.matches(set()) == 0.0

    def test_get_missing(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1), ("GOOD", 1), ("SOMEONE", 1)}))
        missing = kl.get_missing({("FEEL", 1)})
        assert missing == {("GOOD", 1), ("SOMEONE", 1)}


class TestKLineReinforcement:
    def test_success_increases_strength(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1)}))
        initial = kl.strength
        kl.reinforce(success=True, amount=0.1)
        assert kl.strength > initial

    def test_failure_decays_faster(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1)}), strength=5.0)
        initial = kl.strength
        kl.reinforce(success=False, amount=0.1)
        # Failure decays by 2x amount
        assert kl.strength == pytest.approx(initial - 0.2, abs=1e-6)

    def test_strength_clamped_below_ten(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1)}), strength=9.95)
        kl.reinforce(success=True, amount=0.5)
        assert kl.strength <= 10.0

    def test_strength_clamped_above_zero(self):
        kl = KLine(id="x", pattern=frozenset({("FEEL", 1)}), strength=0.05)
        kl.reinforce(success=False, amount=1.0)
        assert kl.strength > 0


class TestPatternCompletion:
    @pytest.fixture
    def populated_store(self):
        store = KLineStore()
        # "love" pattern, seen 5 times
        love = {("FEEL", 1), ("GOOD", 1), ("WANT", 1), ("SOMEONE", 1)}
        for _ in range(5):
            store.add_or_reinforce(love)
        # "hate" pattern, seen 3 times
        hate = {("FEEL", 1), ("GOOD", -1), ("WANT", -1), ("SOMEONE", 1)}
        for _ in range(3):
            store.add_or_reinforce(hate)
        # "joy" pattern, seen 2 times
        joy = {("FEEL", 1), ("GOOD", 1), ("HAPPEN", 1)}
        for _ in range(2):
            store.add_or_reinforce(joy)
        return store

    def test_find_matching_returns_candidates(self, populated_store):
        partial = {("FEEL", 1), ("GOOD", 1)}
        matches = populated_store.find_matching(partial, top_k=5)
        assert len(matches) >= 1
        # Highest-scoring should be love (more frequent + better overlap)
        top_kline, top_score = matches[0]
        assert ("GOOD", 1) in top_kline.pattern

    def test_complete_pattern_predicts_missing(self, populated_store):
        partial = {("FEEL", 1), ("GOOD", 1)}
        predictions = populated_store.complete_pattern(partial, min_confidence=0.1)
        prim_pols = {(p, pol) for p, pol, _ in predictions}
        # Should predict WANT+ and/or SOMEONE+ from love pattern
        assert any(pp in prim_pols for pp in [("WANT", 1), ("SOMEONE", 1)])

    def test_complete_pattern_distinguishes_polarity(self, populated_store):
        # Query with negative GOOD should retrieve hate, not love
        partial = {("FEEL", 1), ("GOOD", -1)}
        predictions = populated_store.complete_pattern(partial, min_confidence=0.1)
        prim_pols = {(p, pol) for p, pol, _ in predictions}
        # Should predict WANT⁻ from hate pattern
        assert ("WANT", -1) in prim_pols

    def test_no_matches_returns_empty(self):
        store = KLineStore()
        store.add_or_reinforce({("FEEL", 1), ("GOOD", 1)})
        result = store.complete_pattern({("MOVE", 1), ("FAST", 1)})
        assert result == []


class TestEviction:
    def test_eviction_at_max(self):
        store = KLineStore(min_pattern_size=2, max_patterns=3)
        store.add_or_reinforce({("A", 1), ("B", 1)})
        store.add_or_reinforce({("C", 1), ("D", 1)})
        store.add_or_reinforce({("E", 1), ("F", 1)})
        assert len(store) == 3

        # Adding a 4th should evict the weakest
        store.add_or_reinforce({("G", 1), ("H", 1)})
        assert len(store) == 3


class TestSerialization:
    def test_roundtrip(self):
        store = KLineStore()
        store.add_or_reinforce({("FEEL", 1), ("GOOD", 1)})
        store.add_or_reinforce({("MOVE", 1), ("FAST", 1)})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            store.save(tmp_path)
            loaded = KLineStore.load(tmp_path)

            assert len(loaded) == len(store)
            # Both patterns should be findable
            matches = loaded.find_matching({("FEEL", 1), ("GOOD", 1)}, min_overlap=0.9)
            assert len(matches) == 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
