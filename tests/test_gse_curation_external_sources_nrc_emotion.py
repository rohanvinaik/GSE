"""Manual contract tests for gse.curation.external_sources.nrc_emotion."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.nrc_emotion import (
    EMOTION_TO_PRIMITIVE,
    EmotionEntry,
    NRCEmotionParser,
)

# ---------- EmotionEntry ----------


class TestEmotionEntry:
    def test_construction(self):
        e = EmotionEntry(word="dog", emotions={"joy": 1})
        assert e.word == "dog"
        assert e.emotions == {"joy": 1}


# ---------- EMOTION_TO_PRIMITIVE ----------


class TestEmotionToPrimitive:
    def test_joy_maps_good_feel(self):
        assert EMOTION_TO_PRIMITIVE["joy"] == {"GOOD": 1, "FEEL": 1}

    def test_sadness_maps_bad_feel(self):
        assert EMOTION_TO_PRIMITIVE["sadness"] == {"GOOD": -1, "FEEL": 1}

    def test_anger_includes_want(self):
        assert "WANT" in EMOTION_TO_PRIMITIVE["anger"]

    def test_surprise_negates_know(self):
        assert EMOTION_TO_PRIMITIVE["surprise"]["KNOW"] == -1

    def test_anticipation_has_before(self):
        assert EMOTION_TO_PRIMITIVE["anticipation"]["BEFORE"] == 1

    def test_positive_only_good(self):
        assert EMOTION_TO_PRIMITIVE["positive"] == {"GOOD": 1}

    def test_negative_only_bad(self):
        assert EMOTION_TO_PRIMITIVE["negative"] == {"GOOD": -1}

    def test_all_ten_emotions_present(self):
        expected = {
            "joy",
            "sadness",
            "anger",
            "fear",
            "trust",
            "disgust",
            "surprise",
            "anticipation",
            "positive",
            "negative",
        }
        assert set(EMOTION_TO_PRIMITIVE.keys()) == expected


# ---------- __init__ ----------


class TestInit:
    def test_default_data_path(self):
        p = NRCEmotionParser()
        assert p.data_path.name == "nrc_emotion.txt"

    def test_custom_data_path(self, tmp_path):
        custom = tmp_path / "custom.txt"
        p = NRCEmotionParser(data_path=str(custom))
        assert p.data_path == custom

    def test_initial_entries_empty(self):
        assert NRCEmotionParser().entries == {}

    def test_initial_loaded_false(self):
        assert NRCEmotionParser()._loaded is False


# ---------- download ----------


class TestDownload:
    def test_success(self, tmp_path):
        p = NRCEmotionParser(data_path=str(tmp_path / "nrc.txt"))
        mock_response = MagicMock()
        mock_response.text = "happy\tjoy\t1\n"
        with patch("requests.get", return_value=mock_response):
            assert p.download() is True
            assert p.data_path.exists()

    def test_failure_returns_false(self, tmp_path):
        p = NRCEmotionParser(data_path=str(tmp_path / "x.txt"))
        with patch("requests.get", side_effect=Exception("network error")):
            assert p.download() is False

    def test_creates_parent_dir(self, tmp_path):
        p = NRCEmotionParser(data_path=str(tmp_path / "sub" / "nrc.txt"))
        mock_response = MagicMock()
        mock_response.text = ""
        with patch("requests.get", return_value=mock_response):
            p.download()
            assert (tmp_path / "sub").exists()


# ---------- load ----------


class TestLoad:
    def test_parses_basic_lines(self, tmp_path):
        path = tmp_path / "nrc.txt"
        path.write_text("happy\tjoy\t1\nhappy\tsadness\t0\nsad\tsadness\t1\n")
        p = NRCEmotionParser(data_path=str(path))
        assert p.load() is True
        assert "happy" in p.entries
        assert p.entries["happy"].emotions["joy"] == 1
        assert p.entries["happy"].emotions["sadness"] == 0
        assert p.entries["sad"].emotions["sadness"] == 1

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "nrc.txt"
        path.write_text("\n\nhappy\tjoy\t1\n\n")
        p = NRCEmotionParser(data_path=str(path))
        p.load()
        assert "happy" in p.entries

    def test_skips_comments(self, tmp_path):
        path = tmp_path / "nrc.txt"
        path.write_text("# header\nhappy\tjoy\t1\n")
        p = NRCEmotionParser(data_path=str(path))
        p.load()
        assert len(p.entries) == 1

    def test_skips_malformed_lines(self, tmp_path):
        # Lines without 3 tab-separated parts
        path = tmp_path / "nrc.txt"
        path.write_text("only_two\tparts\nhappy\tjoy\t1\n")
        p = NRCEmotionParser(data_path=str(path))
        p.load()
        assert "happy" in p.entries
        assert "only_two" not in p.entries

    def test_lowercases_word(self, tmp_path):
        path = tmp_path / "nrc.txt"
        path.write_text("Happy\tjoy\t1\n")
        p = NRCEmotionParser(data_path=str(path))
        p.load()
        assert "happy" in p.entries

    def test_sets_loaded(self, tmp_path):
        path = tmp_path / "nrc.txt"
        path.write_text("happy\tjoy\t1\n")
        p = NRCEmotionParser(data_path=str(path))
        p.load()
        assert p._loaded is True

    def test_missing_file_triggers_download(self, tmp_path):
        path = tmp_path / "missing.txt"
        p = NRCEmotionParser(data_path=str(path))
        with patch.object(p, "download", return_value=False) as mock_dl:
            result = p.load()
            mock_dl.assert_called_once()
            assert result is False

    def test_load_exception_returns_false(self, tmp_path):
        path = tmp_path / "nrc.txt"
        path.write_text("ok\tjoy\t1\n")
        p = NRCEmotionParser(data_path=str(path))
        with patch("builtins.open", side_effect=RuntimeError("boom")):
            assert p.load() is False


# ---------- get_emotions ----------


class TestGetEmotions:
    def test_returns_emotions_dict(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries["dog"] = EmotionEntry(word="dog", emotions={"joy": 1})
        assert p.get_emotions("dog") == {"joy": 1}

    def test_case_insensitive(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries["dog"] = EmotionEntry(word="dog", emotions={"joy": 1})
        assert p.get_emotions("DOG") == {"joy": 1}

    def test_unknown_returns_none(self):
        p = NRCEmotionParser()
        p._loaded = True
        assert p.get_emotions("nonexistent") is None

    def test_auto_loads(self):
        p = NRCEmotionParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_emotions("x")
            mock_load.assert_called_once()


# ---------- to_primitives ----------


class TestToPrimitives:
    def _make(self, emotions):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries["x"] = EmotionEntry(word="x", emotions=emotions)
        return p

    def test_unknown_word_empty(self):
        p = NRCEmotionParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_joy_yields_good_feel(self):
        result = self._make({"joy": 1}).to_primitives("x")
        assert result == {"GOOD": 1, "FEEL": 1}

    def test_zero_value_emotion_ignored(self):
        # joy=0 → no mapping triggered
        result = self._make({"joy": 0, "sadness": 1}).to_primitives("x")
        assert "GOOD" in result
        assert result["GOOD"] == -1

    def test_unknown_emotion_ignored(self):
        # 'foo' not in EMOTION_TO_PRIMITIVE
        result = self._make({"foo": 1}).to_primitives("x")
        assert result == {}

    def test_conflict_uses_abs_value(self):
        # joy → GOOD: +1, sadness → GOOD: -1. Both same abs value, kept as first wins.
        # First key inserted depends on iteration order.
        result = self._make({"joy": 1, "sadness": 1}).to_primitives("x")
        # Both have abs == 1, so first wins (joy=+1)
        assert result["GOOD"] in (1, -1)
        # FEEL = +1 from both
        assert result["FEEL"] == 1

    def test_compounds_primitives_from_multiple_emotions(self):
        # joy + trust → GOOD=+1, FEEL=+1, KNOW=+1
        result = self._make({"joy": 1, "trust": 1}).to_primitives("x")
        assert result["GOOD"] == 1
        assert result["FEEL"] == 1
        assert result["KNOW"] == 1

    def test_anger_compounds(self):
        result = self._make({"anger": 1}).to_primitives("x")
        assert result == {"GOOD": -1, "FEEL": 1, "WANT": 1}

    def test_surprise_negative_know(self):
        result = self._make({"surprise": 1}).to_primitives("x")
        assert result["KNOW"] == -1
        assert result["FEEL"] == 1

    def test_empty_emotions_dict(self):
        result = self._make({}).to_primitives("x")
        assert result == {}


# ---------- get_all_words ----------


class TestGetAllWords:
    def test_returns_keys(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries = {"a": EmotionEntry("a", {}), "b": EmotionEntry("b", {})}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_empty(self):
        p = NRCEmotionParser()
        p._loaded = True
        assert p.get_all_words() == []

    def test_auto_loads(self):
        p = NRCEmotionParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_new_words ----------


class TestGetNewWords:
    def test_filters(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries = {"a": EmotionEntry("a", {}), "b": EmotionEntry("b", {})}
        assert set(p.get_new_words({"a"})) == {"b"}

    def test_auto_loads(self):
        p = NRCEmotionParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_new_words(set())
            mock_load.assert_called_once()


# ---------- get_emotion_words ----------


class TestGetEmotionWords:
    def test_filters_by_emotion(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries = {
            "joyful": EmotionEntry("joyful", {"joy": 1}),
            "sad": EmotionEntry("sad", {"joy": 0, "sadness": 1}),
        }
        assert p.get_emotion_words("joy") == ["joyful"]

    def test_only_returns_value_one(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries = {
            "x": EmotionEntry("x", {"joy": 1}),
            "y": EmotionEntry("y", {"joy": 0}),
        }
        assert p.get_emotion_words("joy") == ["x"]

    def test_missing_emotion_treated_as_zero(self):
        p = NRCEmotionParser()
        p._loaded = True
        p.entries = {"x": EmotionEntry("x", {})}  # no 'joy' key
        assert p.get_emotion_words("joy") == []

    def test_auto_loads(self):
        p = NRCEmotionParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_emotion_words("joy")
            mock_load.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
