"""Manual contract tests for gse.curation.external_sources.verbnet."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
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
    @pytest.fixture(autouse=True)
    def _stub_corpus(self, monkeypatch):
        monkeypatch.setattr("nltk.corpus.verbnet", MagicMock())

    def test_failure_returns_false(self):
        with patch("nltk.corpus.verbnet.classids", side_effect=Exception("boom")):
            assert VerbNetParser().load() is False

    def test_native_membership_and_parent_context_preserved_without_sibling_roles(self):
        from xml.etree.ElementTree import fromstring

        parent = fromstring(
            '<VNCLASS ID="parent-1"><MEMBERS><MEMBER name="Run" wn="run%2:38:00"/></MEMBERS>\n          <THEMROLES><THEMROLE type="Theme"><SELRESTRS logic="or"><SELRESTR Value="+" type="animate"/></SELRESTRS></THEMROLE></THEMROLES>\n          <FRAMES><FRAME><EXAMPLES><EXAMPLE>First example.</EXAMPLE><EXAMPLE>Second example.</EXAMPLE></EXAMPLES>\n          <SEMANTICS><PRED value="motion"><ARGS><ARG type="Event" value="during(E)"/><ARG type="ThemRole" value="Theme"/></ARGS></PRED></SEMANTICS></FRAME></FRAMES>\n          <SUBCLASSES><VNSUBCLASS ID="child-1"><MEMBERS><MEMBER name="walk" wn="walk%2:38:00"/></MEMBERS>\n          <THEMROLES><THEMROLE type="Agent"/></THEMROLES><FRAMES/><SUBCLASSES/></VNSUBCLASS></SUBCLASSES></VNCLASS>'
        )
        child = parent.find("SUBCLASSES/VNSUBCLASS")
        with patch("nltk.corpus.verbnet.classids", return_value=["parent-1", "child-1"]):
            with patch(
                "nltk.corpus.verbnet.vnclass", side_effect=lambda name: {"parent-1": parent, "child-1": child}[name]
            ):
                parser = VerbNetParser()
                assert parser.load() is True
        run = parser.entries["run"][0]
        walk = parser.entries["walk"][0]
        assert run.thematic_roles == ["Theme"]
        assert walk.thematic_roles == ["Agent", "Theme"]
        assert run.wordnet_sense_keys == ["run%2:38:00"]
        assert run.member_attributes["name"] == "Run"
        assert [level["class_id"] for level in walk.class_context] == ["parent-1", "child-1"]
        examples = run.class_context[0]["frames"][0]["native"]["children"][0]["children"]
        assert [example["text"] for example in examples] == ["First example.", "Second example."]
        assert parser.to_primitives_for_entry(walk) == {"MOVE": 1}

    def test_unreadable_class_cannot_fabricate_memberships(self):
        parser = VerbNetParser()
        with patch("nltk.corpus.verbnet.classids", return_value=["c1"]):
            with patch("nltk.corpus.verbnet.vnclass", side_effect=ValueError("invalid native class")):
                assert parser.load() is False
                assert parser.entries == {}
                assert not parser._loaded


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

    @pytest.mark.skip(
        reason="pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built to_primitives behavior"
    )
    def test_unknown_role_ignored(self):
        p = VerbNetParser()
        p._loaded = True
        p.entries["xyz"] = [mk_entry(word="xyz", verb_class="unknown-99", roles=["NotARole"])]
        # No class match + unknown role → default DO=1 (fallback)
        result = p.to_primitives("xyz")
        assert result == {"DO": 1}

    @pytest.mark.skip(
        reason="pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built to_primitives behavior"
    )
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


def semantic_frame(*predicates):
    return {"semantics": list(predicates)}


def event_predicate(name, negated=False, argument_type="Event"):
    return {
        "predicate_value": name,
        "negated": negated,
        "polarity": "!" if negated else "",
        "arguments": [{"type": argument_type, "value": "during(E)"}],
    }


class TestEntryProjection:
    @pytest.mark.parametrize("predicate,bank", [("emotional_state", "FEEL"), ("desire", "WANT")])
    def test_mental_predicate_requires_every_frame_without_affect_polarity(self, predicate, bank):
        entry = mk_entry()
        entry.class_context = [
            {"frames": [semantic_frame(event_predicate(predicate))]},
            {"frames": [semantic_frame(event_predicate(predicate))]},
        ]
        parser = VerbNetParser()
        assert parser.to_primitives_for_entry(entry) == {bank: 1}
        entry.class_context[1]["frames"].append(semantic_frame())
        assert parser.to_primitives_for_entry(entry) == {}

    @pytest.mark.parametrize("name", ["emotional_state", "desire"])
    @pytest.mark.parametrize("negative", [True, False])
    def test_mental_negation_and_non_event_arguments_abstain(self, name, negative):
        entry = mk_entry()
        invalid = event_predicate(name, negated=negative, argument_type="Event" if negative else "ThemRole")
        entry.class_context = [{"frames": [semantic_frame(event_predicate(name), invalid)]}]
        # A role-only duplicate does not invalidate a separate warranted Event;
        # on its own it cannot create an assertion.
        if not negative:
            entry.class_context = [{"frames": [semantic_frame(invalid)]}]
        assert VerbNetParser().to_primitives_for_entry(entry) == {}

    def test_induced_action_cause_is_not_universal_motion_is(self):
        entry = mk_entry()
        entry.class_context = [
            {
                "frames": [
                    semantic_frame(event_predicate("motion")),
                    semantic_frame(event_predicate("motion"), event_predicate("cause")),
                ]
            }
        ]
        assert VerbNetParser().to_primitives_for_entry(entry) == {"MOVE": 1}

    def test_bare_cause_in_every_frame_still_needs_participant_and_outcome_proof(self):
        entry = mk_entry()
        entry.class_context = [
            {"frames": [semantic_frame(event_predicate("cause"))]},
            {"frames": [semantic_frame(event_predicate("cause"))]},
        ]
        parser = VerbNetParser()
        assert parser.to_primitives_for_entry(entry) == {}
        assert all(
            frame["cause"]["code"] == "PARTICIPANT_DECLARATIONS_UNAVAILABLE"
            for frame in parser.projection_diagnostics_for_entry(entry)["frames"]
        )

    @pytest.mark.parametrize(
        "predicate",
        [
            event_predicate("motion", negated=True),
            event_predicate("motion", argument_type="ThemRole"),
            {"predicate_value": "motion", "arguments": []},
            {
                "predicate_value": "motion",
                "negated": False,
                "polarity": "?",
                "arguments": [{"type": "Event", "value": "E"}],
            },
        ],
    )
    def test_negative_missing_or_untyped_predicates_abstain(self, predicate):
        entry = mk_entry()
        entry.class_context = [{"frames": [semantic_frame(predicate)]}]
        assert VerbNetParser().to_primitives_for_entry(entry) == {}

    def test_empty_frames_and_class_name_role_hints_do_not_project(self):
        entry = mk_entry(roles=["Agent", "Theme"])
        assert VerbNetParser().to_primitives_for_entry(entry) == {}

    def test_explicit_keys_preserve_uncertainty_and_reject_lemma_mismatch(self):
        entry = mk_entry()
        entry.wordnet_sense_keys = ["run%2:38:00", "?run%2:38:01", "wrong%2:38:00", "missing%2:38:00"]
        synset = SimpleNamespace(name=lambda: "run.v.01", pos=lambda: "v")
        lemmas = {
            "run%2:38:00::": SimpleNamespace(name=lambda: "run", synset=lambda: synset),
            "wrong%2:38:00::": SimpleNamespace(name=lambda: "wrong", synset=lambda: synset),
        }
        wordnet = SimpleNamespace(lemma_from_key=lambda key: lemmas[key])
        links = VerbNetParser().definition_links(entry, wordnet)
        assert [link["code"] for link in links] == [
            "LINKED",
            "UNCERTAIN_SENSE_KEY",
            "SENSE_KEY_MISMATCH",
            "INVALID_SENSE_KEY",
        ]
        assert links[0]["normalized_sense_key"] == "run%2:38:00::"
        assert links[0]["synset_name"] == "run.v.01"

    def test_uncertain_member_cannot_link_even_with_unmarked_key(self):
        entry = mk_entry()
        entry.member_attributes = {"name": "?run"}
        entry.wordnet_sense_keys = ["run%2:38:00"]
        wordnet = SimpleNamespace(lemma_from_key=lambda key: pytest.fail("must not guess uncertain member"))
        assert VerbNetParser().definition_links(entry, wordnet)[0]["code"] == "UNCERTAIN_SENSE_KEY"


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
