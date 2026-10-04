"""Manual contract tests for gse.curation.external_sources.propbank."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.propbank import (
    ARG_TO_PRIMITIVE,
    ROLESET_CLASS_TO_PRIMITIVE,
    PropBankEntry,
    PropBankParser,
    download_propbank,
)


def mk_entry(lemma="run", rsid="run.01", name="operate", roles=None):
    return PropBankEntry(lemma=lemma, roleset_id=rsid, name=name, roles=roles or {})


# ---------- PropBankEntry ----------


class TestPropBankEntry:
    def test_construction(self):
        e = mk_entry(roles={"ARG0": "agent"})
        assert e.lemma == "run"
        assert e.roleset_id == "run.01"
        assert e.name == "operate"
        assert e.roles == {"ARG0": "agent"}


# ---------- ARG_TO_PRIMITIVE ----------


class TestArgToPrimitive:
    def test_arg0_agent(self):
        assert ARG_TO_PRIMITIVE["ARG0"] == {"SOMEONE": 1, "DO": 1}

    def test_arg1_patient(self):
        assert ARG_TO_PRIMITIVE["ARG1"] == {"SOMETHING": 1}

    def test_argm_tmp_when(self):
        assert ARG_TO_PRIMITIVE["ARGM-TMP"] == {"WHEN": 1}

    def test_argm_neg_not(self):
        assert ARG_TO_PRIMITIVE["ARGM-NEG"] == {"NOT": 1}

    def test_argm_cau_because_cause(self):
        assert ARG_TO_PRIMITIVE["ARGM-CAU"] == {"BECAUSE": 1, "CAUSE": 1}

    def test_arg2_empty(self):
        assert ARG_TO_PRIMITIVE["ARG2"] == {}

    def test_argm_gol_toward(self):
        assert ARG_TO_PRIMITIVE["ARGM-GOL"] == {"TOWARD": 1}


# ---------- ROLESET_CLASS_TO_PRIMITIVE ----------


class TestRolesetClassMappings:
    def test_run_motion(self):
        assert ROLESET_CLASS_TO_PRIMITIVE["run"] == {"MOVE": 1, "BODY": 1}

    def test_kill_negative_alive(self):
        assert ROLESET_CLASS_TO_PRIMITIVE["kill"] == {"ALIVE": -1, "CAUSE": 1}

    def test_give_negative_have(self):
        assert ROLESET_CLASS_TO_PRIMITIVE["give"] == {"HAVE": -1}

    def test_fall_below(self):
        assert ROLESET_CLASS_TO_PRIMITIVE["fall"]["BELOW"] == 1

    def test_rise_above(self):
        assert ROLESET_CLASS_TO_PRIMITIVE["rise"]["ABOVE"] == 1


# ---------- __init__ ----------


class TestInit:
    def test_initial_state(self):
        p = PropBankParser()
        assert p.entries == {}
        assert p._loaded is False

    def test_config_name(self):
        p = PropBankParser()
        assert p.config.name == "propbank"


# ---------- load ----------


class TestLoad:
    def test_failure_returns_false(self):
        p = PropBankParser()
        with patch("nltk.corpus.propbank.rolesets", side_effect=Exception("boom")):
            assert p.load() is False

    def test_successful_load(self):
        # Mock a roleset
        mock_roleset = MagicMock()
        mock_roleset.attrib = {"id": "run.01", "name": "operate"}
        mock_role = MagicMock()
        mock_role.attrib = {"n": "0", "descr": "operator"}
        mock_roleset.findall.return_value = [mock_role]

        with patch("nltk.corpus.propbank.rolesets", return_value=[mock_roleset]):
            p = PropBankParser()
            assert p.load() is True
            assert p._loaded is True
            assert "run" in p.entries
            assert p.entries["run"][0].roleset_id == "run.01"
            assert p.entries["run"][0].name == "operate"
            assert p.entries["run"][0].roles["ARG0"] == "operator"

    def test_load_uses_lemma_prefix(self):
        mock_roleset = MagicMock()
        mock_roleset.attrib = {"id": "Take.01", "name": ""}
        mock_roleset.findall.return_value = []
        with patch("nltk.corpus.propbank.rolesets", return_value=[mock_roleset]):
            p = PropBankParser()
            p.load()
            assert "take" in p.entries


# ---------- to_primitives ----------


class TestToPrimitives:
    def test_unknown_returns_empty(self):
        p = PropBankParser()
        p._loaded = True
        # Clear the lru_cache between tests
        p.to_primitives.cache_clear()
        assert p.to_primitives("nonexistent_word_xyz") == {}

    def test_class_match_run(self):
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["run"] = [mk_entry(lemma="run", roles={})]
        result = p.to_primitives("run")
        assert result["MOVE"] == 1
        assert result["BODY"] == 1

    def test_arg_role_based(self):
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["xyz_verb"] = [mk_entry(lemma="xyz_verb", roles={"ARG0": "agent", "ARG1": "patient"})]
        result = p.to_primitives("xyz_verb")
        assert result["SOMEONE"] == 1
        assert result["DO"] == 1
        assert result["SOMETHING"] == 1

    def test_temporal_arg_when(self):
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["xyz"] = [mk_entry(roles={"ARGM-TMP": "yesterday"})]
        result = p.to_primitives("xyz")
        assert result["WHEN"] == 1

    def test_unknown_arg_ignored(self):
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["xyz"] = [mk_entry(roles={"ARG99": "something"})]
        # Unknown ARG → falls through to default DO
        assert p.to_primitives("xyz") == {"DO": 1}

    def test_empty_arg_mapping_skipped(self):
        # ARG2 has empty dict in ARG_TO_PRIMITIVE
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["xyz"] = [mk_entry(roles={"ARG2": "beneficiary"})]
        # ARG2 dict empty → no primitive added → fall through to DO default
        assert p.to_primitives("xyz") == {"DO": 1}

    def test_class_takes_priority(self):
        # 'give' in ROLESET_CLASS_TO_PRIMITIVE has HAVE: -1
        # If ARG0 added DO=1, that should NOT override class's DO if present
        # But 'give' class doesn't set DO — so ARG0's DO=1 should be added
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["give"] = [mk_entry(lemma="give", roles={"ARG0": "giver"})]
        result = p.to_primitives("give")
        assert result["HAVE"] == -1
        # ARG0 adds DO=1 since not yet in dict
        assert result["DO"] == 1

    def test_class_value_not_overwritten_by_arg(self):
        # If class set DO=-1 and ARG0 also wants DO=1, class wins
        # 'destroy' class has DO=1, END=1 — match
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        # Use 'forget' which has KNOW=-1; ARG0 adds SOMEONE, DO=1 (not yet present)
        p.entries["forget"] = [mk_entry(lemma="forget", roles={"ARG0": "x"})]
        result = p.to_primitives("forget")
        assert result["KNOW"] == -1  # Class

    def test_default_do_fallback(self):
        # No class match, no roles
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["xyz"] = [mk_entry(lemma="xyz", roles={})]
        assert p.to_primitives("xyz") == {"DO": 1}

    def test_case_insensitive(self):
        p = PropBankParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["run"] = [mk_entry(lemma="run", roles={})]
        result = p.to_primitives("RUN")
        assert "MOVE" in result

    def test_auto_loads(self):
        p = PropBankParser()
        p.to_primitives.cache_clear()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.to_primitives("x")
            mock_load.assert_called_once()


# ---------- get_all_words ----------


class TestGetAllWords:
    def test_returns_keys(self):
        p = PropBankParser()
        p._loaded = True
        p.entries = {"run": [mk_entry()], "walk": [mk_entry()]}
        assert set(p.get_all_words()) == {"run", "walk"}

    def test_auto_loads(self):
        p = PropBankParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_rolesets ----------


class TestGetRolesets:
    def test_returns_entries(self):
        p = PropBankParser()
        p._loaded = True
        p.entries["run"] = [mk_entry(), mk_entry(rsid="run.02")]
        assert len(p.get_rolesets("run")) == 2

    def test_unknown_empty(self):
        p = PropBankParser()
        p._loaded = True
        assert p.get_rolesets("nonexistent") == []

    def test_case_insensitive(self):
        p = PropBankParser()
        p._loaded = True
        p.entries["run"] = [mk_entry()]
        assert len(p.get_rolesets("RUN")) == 1

    def test_auto_loads(self):
        p = PropBankParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_rolesets("x")
            mock_load.assert_called_once()


# ---------- get_roleset_info ----------


class TestGetRolesetInfo:
    def test_finds_matching(self):
        p = PropBankParser()
        p._loaded = True
        p.entries["run"] = [mk_entry(rsid="run.01"), mk_entry(rsid="run.02")]
        result = p.get_roleset_info("run.02")
        assert result is not None
        assert result.roleset_id == "run.02"

    def test_unknown_lemma_none(self):
        p = PropBankParser()
        p._loaded = True
        assert p.get_roleset_info("xyz.01") is None

    def test_no_matching_roleset_id(self):
        p = PropBankParser()
        p._loaded = True
        p.entries["run"] = [mk_entry(rsid="run.01")]
        # lemma exists but roleset id doesn't
        assert p.get_roleset_info("run.99") is None

    def test_auto_loads(self):
        p = PropBankParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_roleset_info("x.01")
            mock_load.assert_called_once()

    def test_case_insensitive_lemma(self):
        # roleset_id "Run.01" → lemma "run"
        p = PropBankParser()
        p._loaded = True
        p.entries["run"] = [mk_entry(rsid="Run.01")]
        result = p.get_roleset_info("Run.01")
        assert result is not None


# ---------- download_propbank ----------


class TestDownloadPropbank:
    def test_calls_nltk_download(self, capsys):
        with patch("nltk.download") as mock_dl:
            download_propbank()
            mock_dl.assert_called_once_with("propbank")

    def test_prints_success(self, capsys):
        with patch("nltk.download"):
            download_propbank()
            assert "successfully" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
