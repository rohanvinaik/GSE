"""Manual contract tests for gse.curation.external_sources.usas."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.usas import (
    USAS_MODIFIERS,
    USAS_TO_GSE,
    USASEntry,
    USASParser,
    download_usas,
)


def mk_entry(lemma="x", pos="V", tags=None):
    return USASEntry(lemma=lemma, pos=pos, semantic_tags=tags or [])


# ---------- USASEntry ----------

class TestUSASEntry:
    def test_construction(self):
        e = mk_entry(tags=["M1"])
        assert e.lemma == "x"
        assert e.semantic_tags == ["M1"]


# ---------- USAS_TO_GSE ----------

class TestUSASToGSE:
    def test_m1_move(self):
        assert USAS_TO_GSE["M1"] == {"MOVE": 1}

    def test_b1_body(self):
        assert USAS_TO_GSE["B1"] == {"BODY": 1}

    def test_e1_feel(self):
        assert USAS_TO_GSE["E1"] == {"FEEL": 1}

    def test_a3_empty(self):
        assert USAS_TO_GSE["A3"] == {}


# ---------- USAS_MODIFIERS ----------

class TestModifiers:
    def test_positive(self):
        assert USAS_MODIFIERS["+"] == {"GOOD": 1}

    def test_negative(self):
        assert USAS_MODIFIERS["-"] == {"GOOD": -1}

    def test_double_positive(self):
        assert USAS_MODIFIERS["++"] == {"GOOD": 1, "INTENSITY": 1}

    def test_double_negative(self):
        assert USAS_MODIFIERS["--"] == {"GOOD": -1, "INTENSITY": 1}


# ---------- __init__ ----------

class TestInit:
    def test_default_path(self):
        p = USASParser()
        assert p.lexicon_path.name == "semantic_lexicon_en.tsv"

    def test_custom_path(self, tmp_path):
        p = USASParser(lexicon_path=tmp_path / "x.tsv")
        assert p.lexicon_path == tmp_path / "x.tsv"

    def test_initial_empty(self):
        p = USASParser()
        assert p.entries == {}
        assert p._mwe_entries == {}

    def test_config_name(self):
        assert USASParser().config.name == "usas"


# ---------- download ----------

class TestDownload:
    def test_success(self, tmp_path):
        # Monkey-patch DATA_DIR to tmp_path
        with patch("gse.curation.external_sources.usas.DATA_DIR", tmp_path):
            p = USASParser(lexicon_path=tmp_path / "x.tsv")
            mock_resp = MagicMock()
            mock_resp.content = b"happy\tA\tE4+"
            with patch("requests.get", return_value=mock_resp):
                assert p.download() is True

    def test_failure(self, tmp_path):
        with patch("gse.curation.external_sources.usas.DATA_DIR", tmp_path):
            p = USASParser(lexicon_path=tmp_path / "x.tsv")
            with patch("requests.get", side_effect=Exception("net")):
                assert p.download() is False


# ---------- load ----------

class TestLoad:
    def test_missing_file_triggers_download(self, tmp_path):
        p = USASParser(lexicon_path=tmp_path / "missing.tsv")
        with patch.object(p, "download", return_value=False) as mock_dl:
            assert p.load() is False
            mock_dl.assert_called_once()

    def test_basic_load_three_columns(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("run\tV\tM1\n")
        p = USASParser(lexicon_path=path)
        assert p.load() is True
        assert "run" in p.entries
        assert p.entries["run"][0].semantic_tags == ["M1"]
        assert p.entries["run"][0].pos == "V"

    def test_basic_load_two_columns(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("run\tM1\n")
        p = USASParser(lexicon_path=path)
        p.load()
        assert p.entries["run"][0].pos is None
        assert p.entries["run"][0].semantic_tags == ["M1"]

    def test_skips_blank(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("\n\nrun\tV\tM1\n\n")
        p = USASParser(lexicon_path=path)
        p.load()
        assert "run" in p.entries

    def test_skips_comments(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("# header\nrun\tV\tM1\n")
        p = USASParser(lexicon_path=path)
        p.load()
        assert len(p.entries) == 1

    def test_skips_single_column(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("only_one_field\nrun\tV\tM1\n")
        p = USASParser(lexicon_path=path)
        p.load()
        assert "only_one_field" not in p.entries

    def test_multiple_tags(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("happy\tA\tE4+ A5.1+\n")
        p = USASParser(lexicon_path=path)
        p.load()
        assert p.entries["happy"][0].semantic_tags == ["E4+", "A5.1+"]

    def test_lowercases_lemma(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("RUN\tV\tM1\n")
        p = USASParser(lexicon_path=path)
        p.load()
        assert "run" in p.entries

    def test_exception_returns_false(self, tmp_path):
        path = tmp_path / "u.tsv"
        path.write_text("ok\tV\tM1\n")
        p = USASParser(lexicon_path=path)
        with patch("builtins.open", side_effect=RuntimeError("boom")):
            assert p.load() is False


# ---------- _parse_tag ----------

class TestParseTag:
    def test_simple_category(self):
        p = USASParser()
        result = p._parse_tag("M1")
        assert result == {"MOVE": 1}

    def test_subcategory_falls_back(self):
        # "E4.2" not in dict, falls back to "E4" then "E" — E not in dict either
        # E1-6 are, but plain "E" is not
        p = USASParser()
        result = p._parse_tag("E4.2")
        # E4 in dict → FEEL
        assert result == {"FEEL": 1}

    def test_modifier_positive(self):
        p = USASParser()
        result = p._parse_tag("E4+")
        assert result["FEEL"] == 1
        assert result["GOOD"] == 1

    def test_modifier_negative(self):
        p = USASParser()
        result = p._parse_tag("E4-")
        assert result["GOOD"] == -1

    def test_double_plus_intensity(self):
        p = USASParser()
        result = p._parse_tag("E4++")
        assert result["GOOD"] == 1
        assert result["INTENSITY"] == 1

    def test_double_minus_intensity(self):
        p = USASParser()
        result = p._parse_tag("E4--")
        assert result["GOOD"] == -1
        assert result["INTENSITY"] == 1

    def test_unknown_tag(self):
        p = USASParser()
        # Tag "ZZ99" — letter Z is in dict but only Z0-Z9 and Z99 are. ZZ → main="ZZ" → first letter "Z"
        # Z dict entry: "Z" not a top-level key. Z0 has empty, others have content.
        # ZZ99 strip digits → "ZZ" → first letter "Z" — Z not a key.
        # So falls through and returns empty
        result = p._parse_tag("ZZ99")
        # All test_cats checked: ZZ, Z. None match (only Z0-Z9, Z99). Returns {}
        assert result == {}

    def test_compound_tag_slash(self):
        p = USASParser()
        result = p._parse_tag("M1/N3")
        # M1 → MOVE, N3 → QUANTITY
        assert result["MOVE"] == 1
        assert result["QUANTITY"] == 1

    def test_gender_marker_stripped(self):
        # "S2mfc" → S2 mfc stripped → S2
        p = USASParser()
        result = p._parse_tag("S2mfc")
        # S2 in dict
        assert "SOMEONE" in result

    def test_modifier_balance(self):
        # +- mixed: plus_count==minus_count → no GOOD/INTENSITY change
        p = USASParser()
        result = p._parse_tag("E4+-")
        # plus_count=1, minus_count=1 → no eval marker added; E4 contributes FEEL
        assert "GOOD" not in result
        assert result["FEEL"] == 1


# ---------- to_primitives ----------

class TestToPrimitives:
    def _make(self, tags_per_entry):
        p = USASParser()
        p._loaded = True
        p.entries["x"] = [mk_entry(lemma="x", tags=tags) for tags in tags_per_entry]
        return p

    def test_unknown_empty(self):
        p = USASParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_single_tag(self):
        p = self._make([["M1"]])
        assert p.to_primitives("x") == {"MOVE": 1}

    def test_majority_voting_resolves_conflict(self):
        # Two entries with E4+ (GOOD=1), one with E4- (GOOD=-1)
        # Majority +1 wins
        p = USASParser()
        p._loaded = True
        p.entries["x"] = [
            mk_entry(tags=["E4+"]),
            mk_entry(tags=["E4+"]),
            mk_entry(tags=["E4-"]),
        ]
        result = p.to_primitives("x")
        assert result["GOOD"] == 1

    def test_case_insensitive(self):
        p = USASParser()
        p._loaded = True
        p.entries["x"] = [mk_entry(tags=["M1"])]
        result = p.to_primitives("X")
        assert result["MOVE"] == 1

    def test_multiple_tags_aggregate(self):
        # M1 (MOVE) + B1 (BODY)
        p = self._make([["M1", "B1"]])
        result = p.to_primitives("x")
        assert result["MOVE"] == 1
        assert result["BODY"] == 1


# ---------- get_semantic_tags ----------

class TestGetSemanticTags:
    def test_returns_tags(self):
        p = USASParser()
        p._loaded = True
        p.entries["x"] = [mk_entry(tags=["M1", "B1"])]
        result = set(p.get_semantic_tags("x"))
        assert result == {"M1", "B1"}

    def test_dedup(self):
        p = USASParser()
        p._loaded = True
        p.entries["x"] = [mk_entry(tags=["M1"]), mk_entry(tags=["M1"])]
        # set dedup
        assert p.get_semantic_tags("x") == ["M1"]

    def test_unknown_empty(self):
        p = USASParser()
        p._loaded = True
        assert p.get_semantic_tags("xyz") == []

    def test_lowercases(self):
        p = USASParser()
        p._loaded = True
        p.entries["x"] = [mk_entry(tags=["M1"])]
        assert "M1" in p.get_semantic_tags("X")


# ---------- get_category_name ----------

class TestGetCategoryName:
    def test_M_movement(self):
        assert USASParser().get_category_name("M1") == "Movement/Location"

    def test_B_body(self):
        assert USASParser().get_category_name("B1") == "Body"

    def test_E_emotion(self):
        assert USASParser().get_category_name("E1") == "Emotion"

    def test_unknown_returns_unknown(self):
        # Lowercase letter not in category map
        assert USASParser().get_category_name("zzz") == "Unknown"

    def test_empty_tag(self):
        assert USASParser().get_category_name("") == "Unknown"

    def test_all_categories(self):
        # Pin every category name (covers 21 VALUE mutants for the dict)
        p = USASParser()
        expected = {
            "A": "General/Abstract", "B": "Body", "C": "Arts/Crafts",
            "E": "Emotion", "F": "Food/Farming", "G": "Government",
            "H": "Housing/Architecture", "I": "Money/Commerce",
            "K": "Entertainment/Sports", "L": "Life/Living",
            "M": "Movement/Location", "N": "Numbers/Measurement",
            "O": "Substances/Objects", "P": "Education",
            "Q": "Communication", "S": "Social", "T": "Time",
            "W": "World/Environment", "X": "Psychological",
            "Y": "Science/Technology", "Z": "Names/Grammar",
        }
        for letter, expected_name in expected.items():
            assert p.get_category_name(letter + "1") == expected_name
            assert p.get_category_name(letter) == expected_name


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_returns_keys(self):
        p = USASParser()
        p._loaded = True
        p.entries = {"a": [], "b": []}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_load_fail_returns_empty(self, tmp_path):
        p = USASParser(lexicon_path=tmp_path / "missing.tsv")
        with patch.object(p, "download", return_value=False):
            assert p.get_all_words() == []


# ---------- download_usas ----------

class TestDownloadUsas:
    def test_success_prints(self, capsys):
        with patch.object(USASParser, "download", return_value=True):
            with patch.object(USASParser, "load", return_value=True):
                download_usas()
        out = capsys.readouterr().out
        assert "successfully" in out

    def test_failure_prints(self, capsys):
        with patch.object(USASParser, "download", return_value=False):
            download_usas()
        out = capsys.readouterr().out
        assert "Failed" in out

    def test_load_failure_after_download(self, capsys):
        # download succeeds, load fails
        with patch.object(USASParser, "download", return_value=True):
            with patch.object(USASParser, "load", return_value=False):
                download_usas()
        # Should still print "successfully" but not "Loaded ... unique words"
        out = capsys.readouterr().out
        assert "successfully" in out
        assert "Loaded" not in out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
