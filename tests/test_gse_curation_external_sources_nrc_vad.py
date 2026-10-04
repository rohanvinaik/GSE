"""Manual contract tests for gse.curation.external_sources.nrc_vad."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.nrc_vad import NRCVADParser, VADEntry


def mk_entry(word="x", v=0.5, a=0.5, d=0.5):
    return VADEntry(word=word, valence=v, arousal=a, dominance=d)


# ---------- VADEntry ----------


class TestVADEntry:
    def test_construction(self):
        e = VADEntry(word="dog", valence=0.6, arousal=0.4, dominance=0.7)
        assert e.word == "dog"
        assert e.valence == 0.6
        assert e.arousal == 0.4
        assert e.dominance == 0.7


# ---------- __init__ ----------


class TestInit:
    def test_default_path(self):
        p = NRCVADParser()
        assert p.data_path.name == "nrc_vad.txt"

    def test_custom_path(self, tmp_path):
        custom = tmp_path / "x.txt"
        p = NRCVADParser(data_path=str(custom))
        assert p.data_path == custom

    def test_initial_empty(self):
        assert NRCVADParser().entries == {}

    def test_initial_loaded_false(self):
        assert NRCVADParser()._loaded is False


# ---------- download ----------


class TestDownload:
    def test_success(self, tmp_path):
        p = NRCVADParser(data_path=str(tmp_path / "vad.txt"))
        mock_resp = MagicMock()
        mock_resp.text = "header\nhappy\t0.9\t0.5\t0.5\n"
        with patch("requests.get", return_value=mock_resp):
            assert p.download() is True
            assert p.data_path.exists()

    def test_failure(self, tmp_path):
        p = NRCVADParser(data_path=str(tmp_path / "x.txt"))
        with patch("requests.get", side_effect=Exception("no net")):
            assert p.download() is False

    def test_creates_parent(self, tmp_path):
        p = NRCVADParser(data_path=str(tmp_path / "sub" / "vad.txt"))
        mock_resp = MagicMock()
        mock_resp.text = ""
        with patch("requests.get", return_value=mock_resp):
            p.download()
            assert (tmp_path / "sub").exists()


# ---------- load ----------


class TestLoad:
    def test_basic(self, tmp_path):
        path = tmp_path / "vad.txt"
        path.write_text("Word\tValence\tArousal\tDominance\nhappy\t0.9\t0.7\t0.6\nsad\t0.1\t0.3\t0.3\n")
        p = NRCVADParser(data_path=str(path))
        assert p.load() is True
        assert "happy" in p.entries
        assert p.entries["happy"].valence == 0.9
        assert p.entries["happy"].arousal == 0.7
        assert p.entries["happy"].dominance == 0.6

    def test_skips_blank(self, tmp_path):
        path = tmp_path / "vad.txt"
        path.write_text("header\n\nhappy\t0.9\t0.7\t0.6\n\n")
        p = NRCVADParser(data_path=str(path))
        p.load()
        assert "happy" in p.entries

    def test_skips_malformed(self, tmp_path):
        path = tmp_path / "vad.txt"
        path.write_text("header\nonly\ttwo\nhappy\t0.9\t0.7\t0.6\n")
        p = NRCVADParser(data_path=str(path))
        p.load()
        assert len(p.entries) == 1
        assert "happy" in p.entries

    def test_lowercases(self, tmp_path):
        path = tmp_path / "vad.txt"
        path.write_text("header\nHAPPY\t0.9\t0.7\t0.6\n")
        p = NRCVADParser(data_path=str(path))
        p.load()
        assert "happy" in p.entries

    def test_skips_header_line(self, tmp_path):
        path = tmp_path / "vad.txt"
        # First line is treated as header and consumed
        path.write_text("header\there\tnot\twords\nhappy\t0.9\t0.7\t0.6\n")
        p = NRCVADParser(data_path=str(path))
        p.load()
        assert "header" not in p.entries
        assert "happy" in p.entries

    def test_missing_file_triggers_download(self, tmp_path):
        path = tmp_path / "missing.txt"
        p = NRCVADParser(data_path=str(path))
        with patch.object(p, "download", return_value=False) as mock_dl:
            assert p.load() is False
            mock_dl.assert_called_once()

    def test_exception_returns_false(self, tmp_path):
        path = tmp_path / "vad.txt"
        path.write_text("header\nhappy\t0.9\t0.7\t0.6\n")
        p = NRCVADParser(data_path=str(path))
        with patch("builtins.open", side_effect=RuntimeError("boom")):
            assert p.load() is False

    def test_sets_loaded(self, tmp_path):
        path = tmp_path / "vad.txt"
        path.write_text("header\nhappy\t0.9\t0.7\t0.6\n")
        p = NRCVADParser(data_path=str(path))
        p.load()
        assert p._loaded is True


# ---------- get_vad ----------


class TestGetVAD:
    def test_returns_entry(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries["dog"] = mk_entry(word="dog", v=0.7)
        assert p.get_vad("dog").valence == 0.7

    def test_unknown_returns_none(self):
        p = NRCVADParser()
        p._loaded = True
        assert p.get_vad("nonexistent") is None

    def test_case_insensitive(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries["dog"] = mk_entry(word="dog")
        assert p.get_vad("DOG") is not None

    def test_auto_loads(self):
        p = NRCVADParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_vad("x")
            mock_load.assert_called_once()


# ---------- to_primitives ----------


class TestToPrimitives:
    def _make(self, v=0.5, a=0.5, d=0.5):
        p = NRCVADParser()
        p._loaded = True
        p.entries["x"] = mk_entry(word="x", v=v, a=a, d=d)
        return p

    def test_unknown_empty(self):
        p = NRCVADParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_all_neutral_empty(self):
        # All at 0.5 → no primitives triggered
        assert self._make(v=0.5, a=0.5, d=0.5).to_primitives("x") == {}

    def test_high_valence_good_plus(self):
        # 0.7 > 0.5 + 0.15 = 0.65 → GOOD: +1
        assert self._make(v=0.7).to_primitives("x")["GOOD"] == 1

    def test_low_valence_good_minus(self):
        # 0.3 < 0.5 - 0.15 = 0.35 → GOOD: -1
        assert self._make(v=0.3).to_primitives("x")["GOOD"] == -1

    # Arousal/dominance mappings to LOGICAL-bank primitives (INTENSITY, CAN,
    # MUST) were removed in the May 2026 antonym investigation — those were
    # category errors causing cross-bank pollution. NRC VAD now contributes
    # valence only (GOOD/BAD). The arousal_threshold/dominance_threshold
    # params remain for backwards compat but have no effect.

    def test_arousal_no_longer_votes_intensity(self):
        assert "INTENSITY" not in self._make(a=0.7).to_primitives("x")
        assert "INTENSITY" not in self._make(a=0.3).to_primitives("x")

    def test_dominance_no_longer_votes_can_must(self):
        assert "CAN" not in self._make(d=0.8).to_primitives("x")
        assert "MUST" not in self._make(d=0.2).to_primitives("x")

    def test_valence_at_threshold_no_primitive(self):
        # 0.65 strict > → 0.65 itself does NOT trigger
        assert self._make(v=0.65).to_primitives("x") == {}

    def test_valence_low_at_threshold_no_primitive(self):
        # 0.35 strict < → 0.35 itself does NOT trigger
        assert self._make(v=0.35).to_primitives("x") == {}

    def test_combined_high(self):
        # High V/A/D → only GOOD from valence; A and D no longer contribute
        result = self._make(v=0.9, a=0.8, d=0.9).to_primitives("x")
        assert result == {"GOOD": 1}

    def test_combined_low(self):
        # Low V/A/D → only BAD valence; A and D no longer contribute
        result = self._make(v=0.1, a=0.2, d=0.1).to_primitives("x")
        assert result == {"GOOD": -1}

    def test_custom_valence_threshold(self):
        # Raise threshold to 0.3 → 0.7 valence: 0.7 > 0.5+0.3=0.8 is False
        result = self._make(v=0.7).to_primitives("x", valence_threshold=0.3)
        assert "GOOD" not in result

    def test_arousal_threshold_param_accepted_but_inert(self):
        # The parameter exists for backwards compat; passing it doesn't error.
        result = self._make(a=0.7).to_primitives("x", arousal_threshold=0.3)
        assert "INTENSITY" not in result

    def test_dominance_threshold_param_accepted_but_inert(self):
        result = self._make(d=0.75).to_primitives("x", dominance_threshold=0.1)
        assert "CAN" not in result
        assert "MUST" not in result


# ---------- get_all_words ----------


class TestGetAllWords:
    def test_returns_keys(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"a": mk_entry(), "b": mk_entry()}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_auto_loads(self):
        p = NRCVADParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_new_words ----------


class TestGetNewWords:
    def test_filters(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"a": mk_entry(), "b": mk_entry()}
        assert set(p.get_new_words({"a"})) == {"b"}

    def test_auto_loads(self):
        p = NRCVADParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_new_words(set())
            mock_load.assert_called_once()


# ---------- get_high_valence_words ----------


class TestGetHighValenceWords:
    def test_default_threshold(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"happy": mk_entry(v=0.9), "neutral": mk_entry(v=0.5)}
        assert p.get_high_valence_words() == ["happy"]

    def test_inclusive_at_threshold(self):
        # >= 0.8 means 0.8 is included
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"x": mk_entry(v=0.8)}
        assert p.get_high_valence_words() == ["x"]

    def test_strict_below_threshold(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"x": mk_entry(v=0.79)}
        assert p.get_high_valence_words() == []

    def test_custom_threshold(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"x": mk_entry(v=0.5)}
        assert p.get_high_valence_words(threshold=0.4) == ["x"]

    def test_auto_loads(self):
        p = NRCVADParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_high_valence_words()
            mock_load.assert_called_once()


# ---------- get_low_valence_words ----------


class TestGetLowValenceWords:
    def test_default_threshold(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"sad": mk_entry(v=0.1), "neutral": mk_entry(v=0.5)}
        assert p.get_low_valence_words() == ["sad"]

    def test_inclusive_at_threshold(self):
        # <= 0.2 → 0.2 included
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"x": mk_entry(v=0.2)}
        assert p.get_low_valence_words() == ["x"]

    def test_strict_above_threshold(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"x": mk_entry(v=0.21)}
        assert p.get_low_valence_words() == []

    def test_custom_threshold(self):
        p = NRCVADParser()
        p._loaded = True
        p.entries = {"x": mk_entry(v=0.5)}
        assert p.get_low_valence_words(threshold=0.6) == ["x"]

    def test_auto_loads(self):
        p = NRCVADParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_low_valence_words()
            mock_load.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
