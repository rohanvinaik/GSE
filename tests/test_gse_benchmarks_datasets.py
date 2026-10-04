"""Manual contract tests for gse.benchmarks.datasets."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.benchmarks.datasets import (
    PRIMITIVE_ANTONYM_PAIRS,
    SYNONYM_PAIRS,
    BenchmarkDataset,
    SentencePair,
    WordPair,
    _ensure_simlex999,
    _ensure_sts_benchmark,
    _ensure_wordsim353,
    extract_negation_subset,
    get_all_datasets,
    load_custom_antonyms,
    load_custom_synonyms,
    load_simlex999,
    load_sts_benchmark,
    load_wordsim353,
)

# ---------- Dataclasses ----------

class TestWordPair:
    def test_basic(self):
        p = WordPair(word1="dog", word2="cat", score=5.0)
        assert p.word1 == "dog"
        assert p.score == 5.0
        assert p.pos is None
        assert p.relation is None

    def test_with_optional(self):
        p = WordPair(word1="a", word2="b", score=1.0, pos="N", relation="synonym")
        assert p.pos == "N"
        assert p.relation == "synonym"


class TestSentencePair:
    def test_basic(self):
        p = SentencePair(sentence1="A", sentence2="B", score=4.0)
        assert p.sentence1 == "A"


# ---------- Constants ----------

class TestConstants:
    def test_antonym_pairs_nonempty(self):
        assert len(PRIMITIVE_ANTONYM_PAIRS) > 0
        # All entries are tuples
        for p in PRIMITIVE_ANTONYM_PAIRS:
            assert isinstance(p, tuple) and len(p) == 2

    def test_synonym_pairs_nonempty(self):
        assert len(SYNONYM_PAIRS) > 0

    def test_antonym_has_good_bad(self):
        assert ("good", "bad") in PRIMITIVE_ANTONYM_PAIRS


# ---------- BenchmarkDataset ----------

class TestBenchmarkDataset:
    def test_init(self):
        pairs = [WordPair("a", "b", 1.0)]
        ds = BenchmarkDataset("test", pairs, description="x", citation="y")
        assert ds.name == "test"
        assert ds.description == "x"

    def test_len(self):
        pairs = [WordPair("a", "b", 1.0), WordPair("c", "d", 2.0)]
        ds = BenchmarkDataset("t", pairs)
        assert len(ds) == 2

    def test_iter(self):
        p1 = WordPair("a", "b", 1.0)
        ds = BenchmarkDataset("t", [p1])
        assert list(ds) == [p1]

    def test_get_words(self):
        pairs = [WordPair("dog", "cat", 1.0), WordPair("big", "small", 2.0)]
        ds = BenchmarkDataset("t", pairs)
        w1, w2 = ds.get_words()
        assert w1 == ["dog", "big"]
        assert w2 == ["cat", "small"]

    def test_get_scores(self):
        pairs = [WordPair("a", "b", 1.5), WordPair("c", "d", 2.5)]
        ds = BenchmarkDataset("t", pairs)
        assert ds.get_scores() == [1.5, 2.5]


# ---------- _ensure_simlex999 ----------

class TestEnsureSimlex:
    def test_cached_file_returned(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        simlex = cache / "SimLex-999.txt"
        simlex.write_text("dummy")
        result = _ensure_simlex999(cache)
        assert result == simlex


# ---------- load_simlex999 ----------

class TestLoadSimlex999:
    def test_loads_pairs(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        simlex_path = cache / "SimLex-999.txt"
        # Create a fake SimLex tab-separated file
        with open(simlex_path, "w") as f:
            f.write("word1\tword2\tPOS\tSimLex999\n")
            f.write("happy\tjoyful\tA\t8.5\n")
            f.write("hot\tcold\tA\t1.2\n")
        ds = load_simlex999(cache_dir=cache)
        assert ds.name == "SimLex-999"
        assert len(ds) == 2
        assert ds.pairs[0].score == 8.5
        assert ds.pairs[0].pos == "A"


# ---------- _ensure_wordsim353 ----------

class TestEnsureWordsim:
    def test_local_data_path_returned(self, tmp_path):
        # Use cache dir variant — local paths likely don't exist
        cache = tmp_path / "cache"
        cache.mkdir()
        ws_path = cache / "wordsim353.csv"
        ws_path.write_text("data")
        result = _ensure_wordsim353(cache)
        # Should find the cache file
        assert result == ws_path or result.exists()

    def test_missing_creates_empty(self, tmp_path):
        cache = tmp_path / "no_local"
        result = _ensure_wordsim353(cache)
        # Empty file created at cache/wordsim353.csv
        assert result.exists()


# ---------- load_wordsim353 ----------

class TestLoadWordsim:
    def test_empty_file_returns_empty(self, tmp_path, monkeypatch):
        # Force loader to use cache path (skip local data resolution)
        cache = tmp_path / "cache"
        cache.mkdir()
        empty_path = cache / "wordsim353.csv"
        empty_path.touch()
        monkeypatch.setattr(
            "gse.benchmarks.datasets._ensure_wordsim353",
            lambda cache_dir=None: empty_path,
        )
        ds = load_wordsim353(cache_dir=cache)
        assert ds.name == "WordSim-353"
        assert len(ds) == 0

    def test_loads_tab_separated(self, tmp_path, monkeypatch):
        cache = tmp_path / "cache"
        cache.mkdir()
        ws_path = cache / "wordsim353.csv"
        with open(ws_path, "w") as f:
            f.write("word1\tword2\tscore\n")
            f.write("dog\tcat\t7.5\n")
        monkeypatch.setattr(
            "gse.benchmarks.datasets._ensure_wordsim353",
            lambda cache_dir=None: ws_path,
        )
        ds = load_wordsim353(cache_dir=cache)
        assert len(ds) == 1
        assert ds.pairs[0].word1 == "dog"

    def test_loads_comma_separated(self, tmp_path, monkeypatch):
        cache = tmp_path / "cache"
        cache.mkdir()
        ws_path = cache / "wordsim353.csv"
        with open(ws_path, "w") as f:
            f.write("word1,word2,score\n")
            f.write("dog,cat,7.5\n")
        monkeypatch.setattr(
            "gse.benchmarks.datasets._ensure_wordsim353",
            lambda cache_dir=None: ws_path,
        )
        ds = load_wordsim353(cache_dir=cache)
        assert len(ds) == 1

    def test_invalid_rows_skipped(self, tmp_path, monkeypatch):
        cache = tmp_path / "cache"
        cache.mkdir()
        ws_path = cache / "wordsim353.csv"
        with open(ws_path, "w") as f:
            f.write("word1\tword2\tscore\n")
            f.write("dog\tcat\tnotanumber\n")
            f.write("a\tb\t1.0\n")
        monkeypatch.setattr(
            "gse.benchmarks.datasets._ensure_wordsim353",
            lambda cache_dir=None: ws_path,
        )
        ds = load_wordsim353(cache_dir=cache)
        assert len(ds) == 1


# ---------- _ensure_sts_benchmark ----------

class TestEnsureStsBenchmark:
    def test_cached_dir_returned(self, tmp_path):
        cache = tmp_path / "cache"
        sts_dir = cache / "stsbenchmark"
        sts_dir.mkdir(parents=True)
        (sts_dir / "sts-test.csv").touch()
        result = _ensure_sts_benchmark(cache)
        assert result == sts_dir

    def test_download_failure_creates_dir(self, tmp_path):
        cache = tmp_path / "cache"
        with patch("gse.benchmarks.datasets._download_file",
                   side_effect=Exception("network failure")):
            result = _ensure_sts_benchmark(cache)
            # Directory created as fallback
            assert result.exists()


# ---------- load_sts_benchmark ----------

class TestLoadStsBenchmark:
    def test_missing_returns_empty(self, tmp_path):
        cache = tmp_path / "cache"
        sts_dir = cache / "stsbenchmark"
        sts_dir.mkdir(parents=True)
        # No sts-test.csv created
        ds = load_sts_benchmark("test", cache_dir=cache)
        assert ds.name == "STS-Benchmark-test"
        assert len(ds) == 0

    def test_loads_pairs(self, tmp_path):
        cache = tmp_path / "cache"
        sts_dir = cache / "stsbenchmark"
        sts_dir.mkdir(parents=True)
        sts_file = sts_dir / "sts-test.csv"
        # STS format has 7+ columns, score at index 4, sentences at 5,6
        with open(sts_file, "w") as f:
            f.write("a\tb\tc\td\t4.5\tHello world.\tHi there.\n")
            f.write("a\tb\tc\td\t2.0\tFoo.\tBar.\n")
        ds = load_sts_benchmark("test", cache_dir=cache)
        assert len(ds) == 2
        assert ds.pairs[0].score == 4.5
        assert ds.pairs[0].sentence1 == "Hello world."

    def test_skips_malformed_rows(self, tmp_path):
        cache = tmp_path / "cache"
        sts_dir = cache / "stsbenchmark"
        sts_dir.mkdir(parents=True)
        sts_file = sts_dir / "sts-test.csv"
        with open(sts_file, "w") as f:
            f.write("a\tb\tc\td\tnotanumber\thello\thi\n")
            f.write("a\tb\tc\td\t4.0\tx\ty\n")
        ds = load_sts_benchmark("test", cache_dir=cache)
        # Malformed row skipped
        assert len(ds) == 1


# ---------- load_custom_antonyms ----------

class TestLoadCustomAntonyms:
    def test_returns_dataset(self):
        ds = load_custom_antonyms()
        assert ds.name == "GSE-Antonyms"
        assert len(ds) == len(PRIMITIVE_ANTONYM_PAIRS)

    def test_score_is_negative(self):
        ds = load_custom_antonyms()
        assert all(p.score == -1.0 for p in ds.pairs)

    def test_relation_marked(self):
        ds = load_custom_antonyms()
        assert all(p.relation == "antonym" for p in ds.pairs)


# ---------- load_custom_synonyms ----------

class TestLoadCustomSynonyms:
    def test_returns_dataset(self):
        ds = load_custom_synonyms()
        assert ds.name == "GSE-Synonyms"

    def test_score_is_positive(self):
        ds = load_custom_synonyms()
        assert all(p.score == 1.0 for p in ds.pairs)

    def test_relation_marked(self):
        ds = load_custom_synonyms()
        assert all(p.relation == "synonym" for p in ds.pairs)


# ---------- extract_negation_subset ----------

class TestExtractNegationSubset:
    def test_filters_pairs_with_negation(self):
        pairs = [
            SentencePair("I don't know.", "I know.", 1.0),
            SentencePair("Hello.", "Hi.", 5.0),
            SentencePair("never agree", "always", 2.0),
        ]
        ds = BenchmarkDataset("source", pairs)
        result = extract_negation_subset(ds)
        # Pair 0 has 'n't', Pair 2 has 'never' → 2 pairs kept
        assert len(result) == 2

    def test_no_negation_empty(self):
        ds = BenchmarkDataset("source", [
            SentencePair("Hello.", "Hi.", 5.0),
        ])
        result = extract_negation_subset(ds)
        assert len(result) == 0

    def test_name_appended(self):
        ds = BenchmarkDataset("STS-test", [])
        result = extract_negation_subset(ds)
        assert result.name == "STS-test-Negation"


# ---------- get_all_datasets ----------

class TestGetAllDatasets:
    def test_returns_dict_with_custom(self, tmp_path):
        # Default cache doesn't have most datasets — only custom should be present
        ds = get_all_datasets(cache_dir=tmp_path / "empty")
        assert "antonyms" in ds
        assert "synonyms" in ds


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
