"""Manual contract tests for gse.curation.external_sources.verbnet."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.verbnet import (
    CLASS_TO_PRIMITIVE,
    ROLE_TO_PRIMITIVE,
    VerbNetEntry,
    VerbNetParser,
    download_verbnet,
)


def mk_entry(word="run", verb_class="run-51.3.2", roles=None):
    return VerbNetEntry(word=word, verb_class=verb_class, thematic_roles=roles or [])


# ---------- VerbNetEntry ----------

class TestVerbNetEntry:
    def test_construction(self):
        e = mk_entry(roles=["Agent", "Patient"])
        assert e.word == "run"
        assert e.verb_class == "run-51.3.2"
        assert e.thematic_roles == ["Agent", "Patient"]


# ---------- ROLE_TO_PRIMITIVE ----------

class TestRoleToPrimitive:
    def test_agent(self):
        assert ROLE_TO_PRIMITIVE["Agent"] == {"SOMEONE": 1, "DO": 1}

    def test_patient(self):
        assert ROLE_TO_PRIMITIVE["Patient"] == {"SOMETHING": 1}

    def test_experiencer(self):
        assert ROLE_TO_PRIMITIVE["Experiencer"] == {"SOMEONE": 1, "FEEL": 1}

    def test_goal(self):
        assert ROLE_TO_PRIMITIVE["Goal"] == {"TOWARD": 1}

    def test_source(self):
        assert ROLE_TO_PRIMITIVE["Source"] == {"AWAY": 1}

    def test_beneficiary_good(self):
        assert ROLE_TO_PRIMITIVE["Beneficiary"]["GOOD"] == 1

    def test_count(self):
        assert len(ROLE_TO_PRIMITIVE) == 13


# ---------- CLASS_TO_PRIMITIVE ----------

class TestClassToPrimitive:
    def test_run_motion(self):
        assert CLASS_TO_PRIMITIVE["run"] == {"MOVE": 1, "DO": 1, "BODY": 1}

    def test_give_negative_have(self):
        assert CLASS_TO_PRIMITIVE["give"] == {"HAVE": -1}

    def test_die_negative_alive(self):
        assert CLASS_TO_PRIMITIVE["die"]["ALIVE"] == -1

    def test_forget_negative_know(self):
        assert CLASS_TO_PRIMITIVE["forget"]["KNOW"] == -1

    def test_whisper_low_intensity(self):
        assert CLASS_TO_PRIMITIVE["whisper"]["INTENSITY"] == -1

    def test_shout_high_intensity(self):
        assert CLASS_TO_PRIMITIVE["shout"]["INTENSITY"] == 1


# ---------- __init__ ----------

class TestInit:
    def test_initial_state(self):
        p = VerbNetParser()
        assert p.entries == {}
        assert p._loaded is False


# ---------- load ----------

class TestLoad:
    def test_failure_returns_false(self):
        p = VerbNetParser()
        with patch("nltk.corpus.verbnet.classids", side_effect=Exception("boom")):
            assert p.load() is False

    def test_successful_load(self):
        # Mock VerbNet calls
        mock_vnclass = MagicMock()
        mock_role = MagicMock()
        mock_role.attrib = {"type": "Agent"}
        mock_vnclass.findall.return_value = [mock_role]

        with patch("nltk.corpus.verbnet.classids", return_value=["run-51.3.2"]):
            with patch("nltk.corpus.verbnet.lemmas", return_value=["run", "Run"]):
                with patch("nltk.corpus.verbnet.vnclass", return_value=mock_vnclass):
                    p = VerbNetParser()
                    assert p.load() is True
                    assert p._loaded is True
                    assert "run" in p.entries
                    # lemma "Run" lowercased
                    assert p.entries["run"][0].word == "run"
                    assert "Agent" in p.entries["run"][0].thematic_roles

    def test_handles_class_processing_exception(self):
        # If processing a class raises, should continue not abort
        with patch("nltk.corpus.verbnet.classids", return_value=["good-class", "bad-class"]):
            def lemmas_side(classid):
                if classid == "bad-class":
                    raise RuntimeError("nope")
                return ["walk"]

            mock_vnclass = MagicMock()
            mock_vnclass.findall.return_value = []
            with patch("nltk.corpus.verbnet.lemmas", side_effect=lemmas_side):
                with patch("nltk.corpus.verbnet.vnclass", return_value=mock_vnclass):
                    p = VerbNetParser()
                    assert p.load() is True
                    assert "walk" in p.entries

    def test_handles_role_parsing_failure(self):
        # If role extraction fails, entry still created with empty roles
        with patch("nltk.corpus.verbnet.classids", return_value=["c1"]):
            with patch("nltk.corpus.verbnet.lemmas", return_value=["x"]):
                with patch("nltk.corpus.verbnet.vnclass", side_effect=Exception("no class")):
                    p = VerbNetParser()
                    p.load()
                    assert p.entries["x"][0].thematic_roles == []


# ---------- get_verb_info ----------

class TestGetVerbInfo:
    def test_returns_entries(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries["run"] = [mk_entry()]
        assert len(p.get_verb_info("run")) == 1

    def test_unknown(self):
        p = VerbNetParser()
        p._loaded = True
        assert p.get_verb_info("nonexistent") is None

    def test_case_insensitive(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries["run"] = [mk_entry()]
        assert p.get_verb_info("RUN") is not None

    def test_auto_loads(self):
        p = VerbNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_verb_info("x")
            mock_load.assert_called_once()


# ---------- to_primitives ----------

class TestToPrimitives:
    def test_unknown_word_empty(self):
        p = VerbNetParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_class_match_run(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries["run"] = [mk_entry(word="run", verb_class="run-51.3.2", roles=[])]
        result = p.to_primitives("run")
        assert result["MOVE"] == 1
        assert result["DO"] == 1
        assert result["BODY"] == 1

    def test_class_match_via_verb_class_substring(self):
        # Word doesn't match a CLASS_TO_PRIMITIVE key directly,
        # but verb_class contains a key as substring (e.g., 'run' in 'run-51.3.2')
        p = VerbNetParser()
        p._loaded = True
        p.entries["sprint"] = [mk_entry(word="sprint", verb_class="run-51.3.2", roles=[])]
        result = p.to_primitives("sprint")
        # Should still pick up run's mappings via substring match
        assert result["MOVE"] == 1

    def test_role_based_agent(self):
        p = VerbNetParser()
        p._loaded = True
        # Use a verb not in CLASS_TO_PRIMITIVE, with Agent role
        p.entries["xyz_verb"] = [mk_entry(word="xyz_verb", verb_class="unknown-99", roles=["Agent"])]
        result = p.to_primitives("xyz_verb")
        assert result["SOMEONE"] == 1
        assert result["DO"] == 1

    def test_role_multiple(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries["xyz"] = [mk_entry(word="xyz", verb_class="unknown-99", roles=["Agent", "Patient"])]
        result = p.to_primitives("xyz")
        assert "SOMEONE" in result
        assert "SOMETHING" in result

    def test_unknown_role_ignored(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries["xyz"] = [mk_entry(word="xyz", verb_class="unknown-99", roles=["NotARole"])]
        # No class match + unknown role → default DO=1 (fallback)
        result = p.to_primitives("xyz")
        assert result == {"DO": 1}

    def test_default_do_fallback(self):
        p = VerbNetParser()
        p._loaded = True
        # No class match, no roles
        p.entries["xyz"] = [mk_entry(word="xyz", verb_class="unknown-99", roles=[])]
        assert p.to_primitives("xyz") == {"DO": 1}

    def test_class_takes_priority_over_role(self):
        # If class sets DO=1, role-based DO doesn't override
        p = VerbNetParser()
        p._loaded = True
        # 'love' is in CLASS_TO_PRIMITIVE with GOOD=1; Beneficiary role also has GOOD=1
        p.entries["love"] = [mk_entry(word="love", verb_class="love-99", roles=["Beneficiary"])]
        result = p.to_primitives("love")
        assert result["GOOD"] == 1  # Class wins

    def test_class_negative_value_preserved(self):
        # 'give' has HAVE: -1
        p = VerbNetParser()
        p._loaded = True
        p.entries["give"] = [mk_entry(word="give", verb_class="give-13.1", roles=[])]
        result = p.to_primitives("give")
        assert result["HAVE"] == -1

    def test_multiple_entries_roles_unioned(self):
        # Two entries with different roles → all roles considered
        p = VerbNetParser()
        p._loaded = True
        p.entries["xyz"] = [
            mk_entry(word="xyz", verb_class="unknown-99", roles=["Agent"]),
            mk_entry(word="xyz", verb_class="unknown-99", roles=["Patient"]),
        ]
        result = p.to_primitives("xyz")
        assert "SOMEONE" in result
        assert "SOMETHING" in result


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_returns_keys(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries = {"run": [mk_entry()], "walk": [mk_entry()]}
        assert set(p.get_all_words()) == {"run", "walk"}

    def test_auto_loads(self):
        p = VerbNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_new_words ----------

class TestGetNewWords:
    def test_filters(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries = {"run": [mk_entry()], "walk": [mk_entry()]}
        assert set(p.get_new_words({"run"})) == {"walk"}

    def test_auto_loads(self):
        p = VerbNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_new_words(set())
            mock_load.assert_called_once()


# ---------- download_verbnet ----------

class TestDownloadVerbNet:
    def test_calls_nltk_download(self, capsys):
        with patch("nltk.download") as mock_dl:
            download_verbnet()
            assert mock_dl.call_count == 2
            mock_dl.assert_any_call("verbnet")
            mock_dl.assert_any_call("verbnet3")

    def test_prints_success(self, capsys):
        with patch("nltk.download"):
            download_verbnet()
            assert "successfully" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
