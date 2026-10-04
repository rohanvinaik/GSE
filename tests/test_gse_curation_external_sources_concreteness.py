"""Manual contract tests for gse.curation.external_sources.concreteness."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.concreteness import (
    ConcretenessEntry,
    ConcretenessParser,
)


def mk_entry(word="x", c=3.0, known=100.0, n=30):
    return ConcretenessEntry(word=word, concreteness=c, known_percent=known, n_ratings=n)


# ---------- ConcretenessEntry ----------


class TestEntry:
    def test_construction(self):
        e = ConcretenessEntry(word="dog", concreteness=4.5, known_percent=99.0, n_ratings=30)
        assert e.word == "dog"
        assert e.concreteness == 4.5
        assert e.known_percent == 99.0
        assert e.n_ratings == 30


# ---------- __init__ ----------


class TestInit:
    def test_default_path(self):
        assert ConcretenessParser().data_path.name == "concreteness.csv"

    def test_custom_path(self, tmp_path):
        p = ConcretenessParser(data_path=str(tmp_path / "x.csv"))
        assert p.data_path == tmp_path / "x.csv"

    def test_initial_empty(self):
        assert ConcretenessParser().entries == {}

    def test_initial_loaded_false(self):
        assert ConcretenessParser()._loaded is False


# ---------- download ----------


class TestDownload:
    def test_success(self, tmp_path):
        p = ConcretenessParser(data_path=str(tmp_path / "c.csv"))
        mock_resp = MagicMock()
        mock_resp.text = "header\nword,0,4.5,0,0,99\n"
        with patch("requests.get", return_value=mock_resp):
            assert p.download() is True
            assert p.data_path.exists()

    def test_failure(self, tmp_path):
        p = ConcretenessParser(data_path=str(tmp_path / "x.csv"))
        with patch("requests.get", side_effect=Exception("net")):
            assert p.download() is False

    def test_creates_parent(self, tmp_path):
        p = ConcretenessParser(data_path=str(tmp_path / "sub" / "c.csv"))
        mock_resp = MagicMock()
        mock_resp.text = ""
        with patch("requests.get", return_value=mock_resp):
            p.download()
            assert (tmp_path / "sub").exists()


# ---------- load ----------


class TestLoad:
    def _write(self, tmp_path, content):
        path = tmp_path / "c.csv"
        path.write_text(content)
        return path

    def test_basic(self, tmp_path):
        path = self._write(tmp_path, "header\ntable,0,4.85,0,0,99\nfreedom,0,1.5,0,0,98\n")
        p = ConcretenessParser(data_path=str(path))
        assert p.load() is True
        assert p.entries["table"].concreteness == 4.85
        assert p.entries["freedom"].concreteness == 1.5

    def test_known_pct_set(self, tmp_path):
        path = self._write(tmp_path, "header\ntable,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert p.entries["table"].known_percent == 99.0

    def test_n_ratings_default_30(self, tmp_path):
        path = self._write(tmp_path, "header\ntable,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert p.entries["table"].n_ratings == 30

    def test_empty_known_pct_uses_100(self, tmp_path):
        # parts[5] empty → defaults to 100.0
        path = self._write(tmp_path, "header\ntable,0,4.85,0,0,\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert p.entries["table"].known_percent == 100.0

    def test_skips_blank(self, tmp_path):
        path = self._write(tmp_path, "header\n\ntable,0,4.85,0,0,99\n\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert "table" in p.entries

    def test_skips_short_rows(self, tmp_path):
        # Less than 6 columns
        path = self._write(tmp_path, "header\nshort,row\ntable,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert len(p.entries) == 1

    def test_skips_invalid_float(self, tmp_path):
        path = self._write(tmp_path, "header\nbad,0,NOT_A_NUMBER,0,0,99\ntable,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert "table" in p.entries
        assert "bad" not in p.entries

    def test_lowercases(self, tmp_path):
        path = self._write(tmp_path, "header\nTABLE,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert "table" in p.entries

    def test_strips_quotes(self, tmp_path):
        path = self._write(tmp_path, 'header\n"table",0,4.85,0,0,99\n')
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert "table" in p.entries

    def test_missing_file_triggers_download(self, tmp_path):
        p = ConcretenessParser(data_path=str(tmp_path / "missing.csv"))
        with patch.object(p, "download", return_value=False) as mock_dl:
            assert p.load() is False
            mock_dl.assert_called_once()

    def test_exception_returns_false(self, tmp_path):
        path = self._write(tmp_path, "header\ntable,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        with patch("builtins.open", side_effect=RuntimeError("boom")):
            assert p.load() is False

    def test_sets_loaded(self, tmp_path):
        path = self._write(tmp_path, "header\ntable,0,4.85,0,0,99\n")
        p = ConcretenessParser(data_path=str(path))
        p.load()
        assert p._loaded is True


# ---------- get_concreteness ----------


class TestGetConcreteness:
    def test_returns_value(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries["dog"] = mk_entry(c=4.5)
        assert p.get_concreteness("dog") == 4.5

    def test_unknown(self):
        p = ConcretenessParser()
        p._loaded = True
        assert p.get_concreteness("nonexistent") is None

    def test_case_insensitive(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries["dog"] = mk_entry(c=4.5)
        assert p.get_concreteness("DOG") == 4.5

    def test_auto_loads(self):
        p = ConcretenessParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_concreteness("x")
            mock_load.assert_called_once()


# ---------- to_primitives ----------


class TestToPrimitives:
    def _make(self, c):
        p = ConcretenessParser()
        p._loaded = True
        p.entries["x"] = mk_entry(c=c)
        return p

    def test_unknown_empty(self):
        p = ConcretenessParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_concrete_above_4(self):
        # 4.2 >= 4.0 but < 4.5 → SOMETHING only
        assert self._make(c=4.2).to_primitives("x") == {"SOMETHING": 1}

    def test_very_concrete_above_4_5(self):
        # 4.6 >= 4.5 → SOMETHING + BODY
        assert self._make(c=4.6).to_primitives("x") == {"SOMETHING": 1, "BODY": 1}

    def test_concrete_at_4(self):
        # 4.0 >= 4.0 inclusive → triggers SOMETHING
        assert self._make(c=4.0).to_primitives("x") == {"SOMETHING": 1}

    def test_concrete_at_4_5(self):
        # 4.5 >= 4.5 inclusive → triggers BODY
        assert self._make(c=4.5).to_primitives("x") == {"SOMETHING": 1, "BODY": 1}

    def test_just_below_4(self):
        # 3.99 < 4.0 → NOT concrete branch. Also > 2.5 → not abstract
        assert self._make(c=3.99).to_primitives("x") == {}

    def test_just_below_4_5(self):
        # 4.49 >= 4.0 (SOMETHING) but < 4.5 (no BODY)
        assert self._make(c=4.49).to_primitives("x") == {"SOMETHING": 1}

    def test_abstract_at_2_5(self):
        # 2.5 <= 2.5 → THINK
        assert self._make(c=2.5).to_primitives("x") == {"THINK": 1}

    def test_very_abstract_below_1_8(self):
        # 1.5 <= 1.8 → THINK + SOMETHING: -1
        assert self._make(c=1.5).to_primitives("x") == {"THINK": 1, "SOMETHING": -1}

    def test_abstract_at_1_8(self):
        # 1.8 <= 1.8 inclusive
        assert self._make(c=1.8).to_primitives("x") == {"THINK": 1, "SOMETHING": -1}

    def test_just_above_1_8(self):
        # 1.81 > 1.8 → only THINK
        assert self._make(c=1.81).to_primitives("x") == {"THINK": 1}

    def test_mid_range_empty(self):
        # 3.0 between thresholds
        assert self._make(c=3.0).to_primitives("x") == {}

    def test_just_above_2_5(self):
        # 2.51 > 2.5 → not abstract branch
        assert self._make(c=2.51).to_primitives("x") == {}

    def test_custom_thresholds(self):
        # Loose: concrete_threshold=3.5 → 3.6 triggers SOMETHING
        result = self._make(c=3.6).to_primitives("x", concrete_threshold=3.5)
        assert result["SOMETHING"] == 1

    def test_custom_abstract_threshold(self):
        # abstract_threshold=3.0 → 2.8 triggers THINK
        result = self._make(c=2.8).to_primitives("x", abstract_threshold=3.0)
        assert result["THINK"] == 1


# ---------- get_all_words ----------


class TestGetAllWords:
    def test_returns_keys(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"a": mk_entry(), "b": mk_entry()}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_auto_loads(self):
        p = ConcretenessParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_new_words ----------


class TestGetNewWords:
    def test_filters(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"a": mk_entry(), "b": mk_entry()}
        assert set(p.get_new_words({"a"})) == {"b"}

    def test_auto_loads(self):
        p = ConcretenessParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_new_words(set())
            mock_load.assert_called_once()


# ---------- get_concrete_words ----------


class TestGetConcreteWords:
    def test_default_threshold(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {
            "high": mk_entry(c=4.7),
            "low": mk_entry(c=2.0),
        }
        assert p.get_concrete_words() == ["high"]

    def test_inclusive_at_threshold(self):
        # >= 4.5
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"x": mk_entry(c=4.5)}
        assert p.get_concrete_words() == ["x"]

    def test_strict_below(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"x": mk_entry(c=4.49)}
        assert p.get_concrete_words() == []

    def test_custom_threshold(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"x": mk_entry(c=3.0)}
        assert p.get_concrete_words(threshold=3.0) == ["x"]

    def test_auto_loads(self):
        p = ConcretenessParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_concrete_words()
            mock_load.assert_called_once()


# ---------- get_abstract_words ----------


class TestGetAbstractWords:
    def test_default_threshold(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {
            "abstract": mk_entry(c=1.5),
            "concrete": mk_entry(c=4.5),
        }
        assert p.get_abstract_words() == ["abstract"]

    def test_inclusive_at_threshold(self):
        # <= 2.0
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"x": mk_entry(c=2.0)}
        assert p.get_abstract_words() == ["x"]

    def test_strict_above(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"x": mk_entry(c=2.01)}
        assert p.get_abstract_words() == []

    def test_custom_threshold(self):
        p = ConcretenessParser()
        p._loaded = True
        p.entries = {"x": mk_entry(c=3.0)}
        assert p.get_abstract_words(threshold=3.0) == ["x"]

    def test_auto_loads(self):
        p = ConcretenessParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_abstract_words()
            mock_load.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
