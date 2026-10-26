"""Intent and negative specifications for typed lexical constraint projection."""

from pathlib import Path

from gse.lexicon_builder.build import build
from gse.lexicon_builder.native_constraints import frame_constraints, native_readings, predicate_domain
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_rulebook import admitted_rulebook
from tests.lexicon_sources import requires_lexicon_sources


def test_unpaired_negation_is_explicit_absence_and_never_an_opposite_sign():
    assert predicate_domain("FEEL", True) == ("0",)
    assert predicate_domain("MOVE", True) == ("0",)
    assert predicate_domain("HAVE", True) == ("0",)
    assert predicate_domain("FEEL", False) == ("+1",)


def test_negating_a_bipolar_pole_does_not_invent_its_antonym():
    assert predicate_domain("ALIVE", True) == ("-1", "0")
    assert predicate_domain("GOOD", True) == ("-1", "0")
    assert predicate_domain("BAD", True) == ("0", "+1")
    assert predicate_domain("GOOD", True, True) == ("-1", "0")


def test_a_warranted_alive_to_not_alive_transition_identifies_the_dead_pole():
    assert predicate_domain("ALIVE", True, True) == ("-1",)
    assert predicate_domain("ALIVE", False, True) == ("+1",)
    assert predicate_domain("DEAD", False) == ("-1",)


def test_start_and_end_states_are_not_cancelled_into_zero():
    frame = {
        "predicates": [
            {
                "predicate": {"value": "alive"},
                "arguments": [{"type": "Event", "value": "start(E)"}, {"type": "ThemRole", "value": "Patient"}],
            },
            {
                "predicate": {"value": "alive", "bool": "!"},
                "arguments": [{"type": "Event", "value": "end(E)"}, {"type": "ThemRole", "value": "Patient"}],
            },
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["bindings"][0]["allowed"] == ["-1"]
    assert len(result["bindings"][0]["all_phase_evidence"]) == 2
    assert result["laws"][0].allowed[0][0].value == "-1"


def test_the_prior_state_must_have_the_same_event_and_participant_binding():
    frame = {
        "predicates": [
            {
                "predicate": {"value": "alive"},
                "arguments": [{"type": "Event", "value": "start(E)"}, {"type": "ThemRole", "value": "Agent"}],
            },
            {
                "predicate": {"value": "alive", "bool": "!"},
                "arguments": [{"type": "Event", "value": "end(E)"}, {"type": "ThemRole", "value": "Patient"}],
            },
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["bindings"][0]["allowed"] == ["-1", "0"]
    assert result["bindings"][0]["prior_positive"] is False


def test_implicit_role_notation_does_not_invent_a_different_participant():
    frame = {
        "predicates": [
            {
                "predicate": {"value": "contact", "bool": "!"},
                "arguments": [{"type": "Event", "value": "during(E)"}, {"type": "ThemRole", "value": "Patient"}],
            },
            {
                "predicate": {"value": "contact"},
                "arguments": [{"type": "Event", "value": "end(E)"}, {"type": "ThemRole", "value": "?Patient"}],
            },
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["collisions"] == []
    assert result["bindings"][0]["allowed"] == ["+1"]
    assert result["bindings"][0]["roles"] == ["Patient"]
    assert result["bindings"][0]["all_phase_evidence"][1]["native"]["arguments"][1]["value"] == "?Patient"


def test_unknown_predicates_and_participant_types_do_not_project_content():
    frame = {
        "predicates": [
            {
                "predicate": {"value": "unknown"},
                "arguments": [{"type": "Event", "value": "E"}, {"type": "ThemRole", "value": "Experiencer"}],
            },
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["laws"] == ()
    assert result["unmapped"][0]["code"] == "UNMAPPED_NATIVE_PREDICATE"


def test_unrecognized_event_forms_do_not_default_to_a_whole_event():
    frame = {
        "predicates": [
            {"predicate": {"value": "motion"}, "arguments": [{"type": "Event", "value": "after(E)"}]},
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["laws"] == ()
    assert result["unmapped"][0]["code"] == "UNSUPPORTED_EVENT_FORM"


def test_a_transfer_retains_possession_content_and_both_participant_states():
    frame = {
        "predicates": [
            {
                "predicate": {"value": "has_possession"},
                "arguments": [{"type": "Event", "value": "end(E)"}, {"type": "ThemRole", "value": "Recipient"}],
            },
            {
                "predicate": {"value": "has_possession", "bool": "!"},
                "arguments": [{"type": "Event", "value": "end(E)"}, {"type": "ThemRole", "value": "Agent"}],
            },
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["collisions"] == []
    assert result["laws"][0].allowed[0][0].value == "+1"
    assert {tuple(b["allowed"]) for b in result["bindings"]} == {("+1",), ("0",)}


def test_contact_content_is_not_erased_by_a_later_release_state():
    frame = {
        "predicates": [
            {
                "predicate": {"value": "contact"},
                "arguments": [
                    {"type": "Event", "value": "end(E0)"},
                    {"type": "ThemRole", "value": "Agent"},
                    {"type": "ThemRole", "value": "Theme"},
                ],
            },
            {
                "predicate": {"value": "contact", "bool": "!"},
                "arguments": [
                    {"type": "Event", "value": "during(E1)"},
                    {"type": "ThemRole", "value": "Agent"},
                    {"type": "ThemRole", "value": "Theme"},
                ],
            },
        ]
    }
    result = frame_constraints(frame, load_rulebook())
    assert result["collisions"] == []
    assert result["laws"][0].allowed[0][0].value == "+1"
    assert len(result["bindings"]) == 2


def test_inherited_frames_keep_their_origin_and_all_membership_provenance():
    frame = {
        "class": "parent",
        "frame_index": 0,
        "predicates": [{"predicate": {"value": "motion"}, "arguments": [{"type": "Event", "value": "E"}]}],
    }
    native = {
        "verbnet": {
            "records": [
                {"record_id": "membership-1", "values": {"class": "child-1", "frames": [frame]}},
                {"record_id": "membership-2", "values": {"class": "child-2", "frames": [frame]}},
            ]
        }
    }
    readings = native_readings("example", native, load_rulebook())
    assert len(readings) == 1
    assert readings[0]["premise_record_ids"] == ["membership-1", "membership-2"]
    assert readings[0]["symbolic_before"]["forced"]["MOVE"] == "+1"
    assert readings[0]["symbolic_before"]["forced"]["SOMEONE"] == "0"
    assert "OWN_PHYSICAL_CHANGE_OF_PLACE" in readings[0]["symbolic_before"]["fired_rules"]


@requires_lexicon_sources
def test_native_constraints_are_consumed_by_the_word_builder():
    sources = NativeSources(["kill"], Path("data/external"), Path.home() / "nltk_data/corpora")
    word = list(build(["kill"], sources, admitted_rulebook("VN_VITALITY"), None))[0]
    assert word["code"] == "CONSTRUCTED_READINGS"
    assert any(r["symbolic_before"]["forced"].get("ALIVE") == "-1" for r in word["readings"])
    assert all(r["symbolic_before"]["forced"].get("ALIVE") != "0" for r in word["readings"])
    assert all(r["candidate_vector"] is None for r in word["readings"])
