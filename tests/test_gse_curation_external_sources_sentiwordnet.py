"""Manual contract tests for gse.curation.external_sources.sentiwordnet."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.sentiwordnet import (
    SentiWordEntry,
    SentiWordNetParser,
    download_sentiwordnet,
)


def make_entry(word="dog", pos="noun", pos_score=0.5, neg_score=0.0, obj_score=0.5, synset_id="dog.n.01"):
    return SentiWordEntry(
        word=word, pos=pos,
        pos_score=pos_score, neg_score=neg_score, obj_score=obj_score,
        synset_id=synset_id,
    )


# ---------- SentiWordEntry ----------

class TestSentiWordEntry:
    def test_construction(self):
        e = make_entry()
        assert e.word == "dog"
        assert e.pos == "noun"
        assert e.pos_score == 0.5
        assert e.neg_score == 0.0
        assert e.obj_score == 0.5
        assert e.synset_id == "dog.n.01"


# ---------- __init__ ----------

class TestInit:
    def test_initial_state(self):
        p = SentiWordNetParser()
        assert p.entries == {}
        assert p._loaded is False


# ---------- _convert_pos ----------

class TestConvertPos:
    def test_noun(self):
        assert SentiWordNetParser()._convert_pos("n") == "noun"

    def test_verb(self):
        assert SentiWordNetParser()._convert_pos("v") == "verb"

    def test_adj_a(self):
        assert SentiWordNetParser()._convert_pos("a") == "adj"

    def test_adv(self):
        assert SentiWordNetParser()._convert_pos("r") == "adv"

    def test_satellite_adj(self):
        # 's' maps to 'adj'
        assert SentiWordNetParser()._convert_pos("s") == "adj"

    def test_unknown(self):
        assert SentiWordNetParser()._convert_pos("Z") == "unknown"

    def test_empty(self):
        assert SentiWordNetParser()._convert_pos("") == "unknown"


# ---------- load ----------

class TestLoad:
    @pytest.fixture(autouse=True)
    def _stub_corpus(self, monkeypatch):
        # The parser imports the corpus at call time. Replace NLTK's LazyCorpusLoader itself, so the
        # attribute patches below never trigger a real corpus load (which needs installed NLTK data).
        monkeypatch.setattr("nltk.corpus.sentiwordnet", MagicMock())

    def test_failure_returns_false(self):
        # Was skipped as a broken mock (it set sys.modules['nltk']=None, then imported nltk); with the
        # corpus stubbed, the exception path is reachable directly.
        p = SentiWordNetParser()
        with patch("nltk.corpus.sentiwordnet.all_senti_synsets", side_effect=RuntimeError("boom")):
            assert p.load() is False

    def test_successful_load_sets_loaded(self):
        p = SentiWordNetParser()
        # Mock the NLTK pipeline
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "good"
        mock_synset = MagicMock()
        mock_synset.lemmas.return_value = [mock_lemma]
        mock_synset.pos.return_value = "a"
        mock_synset.name.return_value = "good.a.01"
        mock_senti_synset = MagicMock()
        mock_senti_synset.synset = mock_synset
        mock_senti_synset.pos_score.return_value = 0.8
        mock_senti_synset.neg_score.return_value = 0.0
        mock_senti_synset.obj_score.return_value = 0.2

        with patch("nltk.corpus.sentiwordnet.senti_synsets"):
            with patch("nltk.corpus.sentiwordnet.all_senti_synsets",
                       return_value=iter([mock_senti_synset])):
                assert p.load() is True
                assert p._loaded is True
                assert "good" in p.entries

    def test_load_replaces_underscore(self):
        p = SentiWordNetParser()
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "happy_camper"
        mock_synset = MagicMock()
        mock_synset.lemmas.return_value = [mock_lemma]
        mock_synset.pos.return_value = "a"
        mock_synset.name.return_value = "happy.a.01"
        mock_senti = MagicMock()
        mock_senti.synset = mock_synset
        mock_senti.pos_score.return_value = 0.5
        mock_senti.neg_score.return_value = 0.0
        mock_senti.obj_score.return_value = 0.5

        with patch("nltk.corpus.sentiwordnet.senti_synsets"):
            with patch("nltk.corpus.sentiwordnet.all_senti_synsets",
                       return_value=iter([mock_senti])):
                p.load()
                assert "happy camper" in p.entries


# ---------- get_sentiment ----------

class TestGetSentiment:
    def _make_loaded(self):
        p = SentiWordNetParser()
        p._loaded = True
        p.entries["dog"] = [
            make_entry(pos="noun", pos_score=0.4, neg_score=0.1, obj_score=0.5),
            make_entry(pos="noun", pos_score=0.6, neg_score=0.0, obj_score=0.4),
        ]
        return p

    def test_unknown_word(self):
        p = self._make_loaded()
        assert p.get_sentiment("nonexistent") is None

    def test_returns_averages(self):
        p = self._make_loaded()
        result = p.get_sentiment("dog")
        assert result == {
            "pos": pytest.approx(0.5),
            "neg": pytest.approx(0.05),
            "obj": pytest.approx(0.45),
        }

    def test_case_insensitive_lookup(self):
        p = self._make_loaded()
        assert p.get_sentiment("DOG") is not None

    def test_pos_filter(self):
        p = SentiWordNetParser()
        p._loaded = True
        p.entries["dog"] = [
            make_entry(pos="noun", pos_score=0.4),
            make_entry(pos="verb", pos_score=0.8),
        ]
        result = p.get_sentiment("dog", pos="verb")
        assert result["pos"] == 0.8

    def test_pos_filter_empty_returns_none(self):
        p = self._make_loaded()
        # No verb entries
        assert p.get_sentiment("dog", pos="verb") is None

    def test_auto_loads(self):
        p = SentiWordNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_sentiment("dog")
            mock_load.assert_called_once()


# ---------- to_primitives ----------

class TestToPrimitives:
    def _make_with(self, pos_score, neg_score):
        p = SentiWordNetParser()
        p._loaded = True
        p.entries["x"] = [make_entry(pos_score=pos_score, neg_score=neg_score, obj_score=1 - pos_score - neg_score)]
        return p

    def test_unknown_word_returns_empty(self):
        p = SentiWordNetParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_positive_sentiment_above_threshold(self):
        p = self._make_with(0.8, 0.0)
        assert p.to_primitives("x") == {"GOOD": 1}

    def test_negative_sentiment_above_threshold(self):
        p = self._make_with(0.0, 0.8)
        assert p.to_primitives("x") == {"GOOD": -1}

    def test_both_below_threshold(self):
        # Below threshold of 0.25 → empty
        p = self._make_with(0.1, 0.1)
        assert p.to_primitives("x") == {}

    def test_pos_greater_than_neg(self):
        # Both above threshold, pos > neg → +1
        p = self._make_with(0.6, 0.3)
        assert p.to_primitives("x") == {"GOOD": 1}

    def test_neg_greater_than_pos(self):
        p = self._make_with(0.3, 0.6)
        assert p.to_primitives("x") == {"GOOD": -1}

    def test_equal_pos_and_neg_empty(self):
        # Tied → neither branch triggers (strict > comparison)
        p = self._make_with(0.5, 0.5)
        assert p.to_primitives("x") == {}

    def test_custom_threshold(self):
        # 0.3 below default 0.25? No, 0.3 > 0.25 → triggers. Raise threshold to 0.5
        p = self._make_with(0.3, 0.0)
        assert p.to_primitives("x", threshold=0.5) == {}

    def test_at_threshold_boundary(self):
        # Strict > 0.25 → 0.25 itself does NOT trigger
        p = self._make_with(0.25, 0.0)
        assert p.to_primitives("x") == {}

    def test_equal_above_threshold_both_branches_skipped(self):
        # Distinct from test_equal_pos_and_neg_empty: explicit assertion both branches skipped
        # pos==neg==0.4 (both > 0.25 threshold) → neither > the other → empty
        p = self._make_with(0.4, 0.4)
        result = p.to_primitives("x")
        # If either > were mutated to >=, this would return GOOD=1 or GOOD=-1
        assert "GOOD" not in result
        assert result == {}

    def test_neg_above_threshold_neg_eq_pos_no_neg_one(self):
        # Specifically pin: neg > pos must be strict (not >=)
        # Both 0.3 > 0.25, but neg == pos (=0.3) — neither branch should fire
        p = self._make_with(0.3, 0.3)
        assert p.to_primitives("x") == {}

    def test_pos_above_threshold_pos_eq_neg_no_plus_one(self):
        # Mirror: pos > neg must be strict
        p = self._make_with(0.6, 0.6)
        assert p.to_primitives("x") == {}


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_empty_unloaded(self):
        p = SentiWordNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            words = p.get_all_words()
            mock_load.assert_called_once()
            assert words == []

    def test_loaded_returns_keys(self):
        p = SentiWordNetParser()
        p._loaded = True
        p.entries = {"a": [], "b": []}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_returns_list_type(self):
        p = SentiWordNetParser()
        p._loaded = True
        assert isinstance(p.get_all_words(), list)


# ---------- get_new_words ----------

class TestGetNewWords:
    def test_filters_existing(self):
        p = SentiWordNetParser()
        p._loaded = True
        p.entries = {"dog": [], "cat": [], "fish": []}
        new = p.get_new_words({"dog"})
        assert set(new) == {"cat", "fish"}

    def test_all_existing_returns_empty(self):
        p = SentiWordNetParser()
        p._loaded = True
        p.entries = {"a": []}
        assert p.get_new_words({"a"}) == []

    def test_auto_loads(self):
        p = SentiWordNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_new_words(set())
            mock_load.assert_called_once()


# ---------- download_sentiwordnet ----------

class TestDownloadSentiWordNet:
    def test_calls_nltk_download_three_times(self, capsys):
        with patch("nltk.download") as mock_dl:
            download_sentiwordnet()
            # 3 downloads: sentiwordnet, wordnet, omw-1.4
            assert mock_dl.call_count == 3
            mock_dl.assert_any_call("sentiwordnet")
            mock_dl.assert_any_call("wordnet")
            mock_dl.assert_any_call("omw-1.4")

    def test_prints_success(self, capsys):
        with patch("nltk.download"):
            download_sentiwordnet()
            assert "successfully" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
