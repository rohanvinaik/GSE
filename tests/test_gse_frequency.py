"""Manual contract tests for gse.frequency."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.frequency import (
    FrequencyDatabase,
    FrequencyInfo,
    WeightProfile,
)


@pytest.fixture
def db_path():
    """Create a temporary frequency database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        # Build a minimal database
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fd1:
            fd1.write("the\na\nan\nis\ndog\ncat\nrun\nfeel\ngood\nbad\n")
            d47k = fd1.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fd2:
            fd2.write("the: 1000\na: 800\ndog: 50\ncat: 40\nspecial: 5\n")
            local = fd2.name
        db = FrequencyDatabase(db_path=path)
        db.build_from_sources(d47k, local)
        Path(d47k).unlink(missing_ok=True)
        Path(local).unlink(missing_ok=True)
        yield path
    finally:
        Path(path).unlink(missing_ok=True)


class TestFrequencyInfo:
    def test_construct(self):
        info = FrequencyInfo(word="dog", rank=10, david47k_rank=5, local_rank=15, weight=0.5)
        assert info.word == "dog"
        assert info.rank == 10
        assert info.weight == 0.5


class TestFrequencyDatabaseInit:
    def test_default_db_path(self):
        db = FrequencyDatabase()
        assert "frequency.db" in db.db_path

    def test_custom_db_path(self):
        db = FrequencyDatabase(db_path="/tmp/custom.db")
        assert db.db_path == "/tmp/custom.db"

    def test_empty_cache_initially(self):
        db = FrequencyDatabase()
        assert db._cache == {}


class TestRankToWeight:
    def test_rank_one_min_weight(self):
        db = FrequencyDatabase()
        w = db._rank_to_weight(1, 100)
        # rank=1 → log(1)/log(100) = 0 → MIN_WEIGHT
        assert w == pytest.approx(db.MIN_WEIGHT)

    def test_max_rank_max_weight(self):
        db = FrequencyDatabase()
        w = db._rank_to_weight(100, 100)
        # rank=max → log(100)/log(100) = 1 → MAX_WEIGHT
        assert w == pytest.approx(db.MAX_WEIGHT)

    def test_rank_zero_clamped_to_one(self):
        db = FrequencyDatabase()
        # rank=0 should be clamped to 1
        w0 = db._rank_to_weight(0, 100)
        w1 = db._rank_to_weight(1, 100)
        assert w0 == pytest.approx(w1)

    def test_negative_rank_clamped(self):
        db = FrequencyDatabase()
        w_neg = db._rank_to_weight(-5, 100)
        w_one = db._rank_to_weight(1, 100)
        assert w_neg == pytest.approx(w_one)

    def test_rank_over_max_clamped(self):
        db = FrequencyDatabase()
        w_over = db._rank_to_weight(1000, 100)
        w_max = db._rank_to_weight(100, 100)
        assert w_over == pytest.approx(w_max)

    def test_monotonic(self):
        db = FrequencyDatabase()
        max_rank = 100
        weights = [db._rank_to_weight(r, max_rank) for r in [1, 10, 50, 99, 100]]
        for i in range(len(weights) - 1):
            assert weights[i] <= weights[i+1], f"Not monotonic: {weights}"


class TestLookup:
    def test_known_word(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        info = db.lookup("dog")
        assert info.word == "dog"
        assert info.rank > 0

    def test_unknown_word_returns_default(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        info = db.lookup("zxqvnonsense")
        assert info.word == "zxqvnonsense"
        assert info.rank == db.DEFAULT_MAX_RANK
        assert info.weight == db.MAX_WEIGHT

    def test_case_insensitive(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        i1 = db.lookup("DOG")
        i2 = db.lookup("dog")
        assert i1.rank == i2.rank
        assert i1.weight == i2.weight

    def test_cached_after_first_lookup(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        db.lookup("dog")
        assert "dog" in db._cache

    def test_missing_db_returns_default(self):
        db = FrequencyDatabase(db_path="/nonexistent/path.db")
        info = db.lookup("dog")
        assert info.rank == db.DEFAULT_MAX_RANK
        assert info.weight == db.MAX_WEIGHT


class TestGetWeightAndRank:
    def test_get_weight_known(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        w = db.get_weight("dog")
        assert isinstance(w, float)

    def test_get_weight_unknown(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        assert db.get_weight("zxqv") == db.MAX_WEIGHT

    def test_get_rank_known(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        r = db.get_rank("dog")
        assert isinstance(r, int)
        assert r > 0

    def test_get_rank_unknown(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        assert db.get_rank("zxqv") == db.DEFAULT_MAX_RANK


class TestBatchLookup:
    def test_returns_dict(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        result = db.batch_lookup(["dog", "cat", "zxqv"])
        assert isinstance(result, dict)
        assert "dog" in result
        assert "cat" in result
        assert "zxqv" in result

    def test_uncached_then_cached(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        r1 = db.batch_lookup(["dog"])
        r2 = db.batch_lookup(["dog"])
        # Second call should hit cache
        assert r1["dog"].rank == r2["dog"].rank

    def test_unknown_words_default(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        result = db.batch_lookup(["zxqv1", "zxqv2"])
        for word, info in result.items():
            assert info.rank == db.DEFAULT_MAX_RANK
            assert info.weight == db.MAX_WEIGHT

    def test_db_error_returns_defaults(self):
        db = FrequencyDatabase(db_path="/nonexistent/path.db")
        result = db.batch_lookup(["a", "b"])
        for word, info in result.items():
            assert info.rank == db.DEFAULT_MAX_RANK


class TestStats:
    def test_returns_dict(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        s = db.stats()
        assert isinstance(s, dict)

    def test_includes_counts(self, db_path):
        db = FrequencyDatabase(db_path=db_path)
        s = db.stats()
        assert "total_words" in s
        assert s["total_words"] > 0

    def test_missing_db_returns_error(self):
        db = FrequencyDatabase(db_path="/nonexistent/path.db")
        s = db.stats()
        assert "error" in s


class TestBuildFromSources:
    def test_returns_count(self, tmp_path):
        d47k = tmp_path / "d47k.txt"
        d47k.write_text("the\na\ndog\n")
        local = tmp_path / "local.txt"
        local.write_text("the: 100\ndog: 5\n")
        db_path = tmp_path / "freq.db"
        db = FrequencyDatabase(db_path=str(db_path))
        count = db.build_from_sources(str(d47k), str(local))
        assert count == 3  # the, a, dog (union)


class TestWeightProfileApply:
    def test_balanced_returns_input(self):
        assert WeightProfile.apply(WeightProfile.BALANCED, 1.5) == 1.5

    def test_content_focused_amplifies(self):
        result = WeightProfile.apply(WeightProfile.CONTENT_FOCUSED, 2.0)
        # 2.0 ** 1.5 = 2.828...
        assert result == pytest.approx(2.0 ** 1.5)

    def test_structure_focused_compresses(self):
        result = WeightProfile.apply(WeightProfile.STRUCTURE_FOCUSED, 4.0)
        # sqrt(4.0) = 2.0
        assert result == pytest.approx(2.0)

    def test_structure_dominant_inverts(self):
        result = WeightProfile.apply(WeightProfile.STRUCTURE_DOMINANT, 2.0)
        # 1.0 / 2.0 = 0.5
        assert result == pytest.approx(0.5)

    def test_structure_dominant_zero_clamped(self):
        result = WeightProfile.apply(WeightProfile.STRUCTURE_DOMINANT, 0.0)
        # max(0.1, 0.0) = 0.1, so 1/0.1 = 10
        assert result == pytest.approx(10.0)

    def test_idf_style_returns_input(self):
        assert WeightProfile.apply(WeightProfile.IDF_STYLE, 1.7) == 1.7

    def test_unknown_profile_returns_input(self):
        assert WeightProfile.apply("unknown_profile", 1.5) == 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
