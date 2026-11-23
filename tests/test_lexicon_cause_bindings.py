"""CAUSE needs an affected participant, not a role label or result placeholder."""

from pathlib import Path

from gse.lexicon_builder.build import build
from gse.lexicon_builder.native_constraints import caused_change_status, frame_constraints
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_sources import requires_lexicon_sources


def predicate(name, event, role):
    return {
        "predicate": {"value": name},
        "arguments": [
            {"type": "Event", "value": event},
            {"type": "ThemRole", "value": role},
        ],
    }


def frame():
    return {
        "predicates": [predicate("cause", "E", "Agent"), predicate("motion", "during(E)", "Patient")],
        "role_restrictions": [{"role": "Agent", "restrictions": []}, {"role": "Patient", "restrictions": []}],
        "syntax": [],
    }


def test_declared_other_participant_with_lexical_outcome_qualifies():
    result = caused_change_status(frame(), 0, set())
    assert result == {"code": "BOUND_CAUSED_CHANGE", "predicate_index": 1, "affected_roles": ["Patient"]}


def test_body_part_without_owner_identity_must_not_prove_distinctness():
    value = frame()
    value["role_restrictions"][1]["restrictions"] = [
        {
            "tag": "SELRESTRS",
            "attributes": {},
            "children": [
                {"tag": "SELRESTR", "attributes": {"type": "body_part", "Value": "+"}, "children": []},
            ],
        }
    ]
    result = caused_change_status(value, 0, set())
    assert result["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT"
    assert result["blocked_evidence"] == ["AFFECTED_PARTICIPANT_IDENTITY_UNCONFIRMED"]


def test_reflexive_target_does_not_qualify_even_with_a_distinct_role_name():
    value = frame()
    value["syntax"] = [
        {
            "tag": "NP",
            "attributes": {"value": "Patient"},
            "children": [
                {
                    "tag": "SYNRESTR",
                    "attributes": {"type": "refl", "Value": "+"},
                    "children": [],
                }
            ],
        }
    ]
    assert caused_change_status(value, 0, set())["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT"


def test_result_placeholder_or_undeclared_role_must_not_supply_lexical_cause():
    value = frame()
    value["predicates"][1] = predicate("Pred", "result(E)", "Oblique1")
    result = caused_change_status(value, 0, set())
    assert result["blocked_evidence"] == ["CONSTRUCTION_RESULT_PLACEHOLDER"]
    value["predicates"][1] = predicate("motion", "during(E)", "Oblique1")
    assert caused_change_status(value, 0, set())["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT"


def test_refused_source_join_and_unrelated_event_must_not_support_cause():
    assert caused_change_status(frame(), 0, {1})["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT"
    value = frame()
    value["predicates"][0] = predicate("cause", "E0", "Agent")
    value["predicates"][1] = predicate("motion", "during(E1)", "Patient")
    assert caused_change_status(value, 0, set())["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT"


def test_unsupported_cause_or_outcome_polarity_must_not_supply_caused_change():
    value = frame()
    value["predicates"][1] = predicate("contact", "end(E)", "Patient")
    value["predicates"][1]["predicate"]["bool"] = "?"
    assert caused_change_status(value, 0, set()) == {
        "code": "NO_CHANGE_TO_ANOTHER_PARTICIPANT",
        "blocked_evidence": ["UNSUPPORTED_NATIVE_POLARITY"],
    }
    value = frame()
    value["predicates"][0]["predicate"]["bool"] = "?"
    assert caused_change_status(value, 0, set()) == {
        "code": "NO_CHANGE_TO_ANOTHER_PARTICIPANT",
        "blocked_evidence": ["UNSUPPORTED_NATIVE_POLARITY"],
    }


def test_frame_projection_refuses_unsupported_outcome_without_losing_terminal_negation():
    value = frame()
    value["predicates"][1] = predicate("contact", "end(E)", "Patient")
    value["predicates"][1]["predicate"]["bool"] = "?"
    result = frame_constraints(value, load_rulebook())
    assert not any("CAUSE" in law.coordinates or "DO" in law.coordinates for law in result["laws"])
    assert any(u["code"] == "UNSUPPORTED_NATIVE_POLARITY" for u in result["unmapped"])
    assert any(
        u["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT" and u["blocked_evidence"] == ["UNSUPPORTED_NATIVE_POLARITY"]
        for u in result["unmapped"]
    )
    for polarity in (None, "!"):
        value["predicates"][1]["predicate"]["bool"] = polarity
        assert caused_change_status(value, 0, set())["code"] == "BOUND_CAUSED_CHANGE"
        result = frame_constraints(value, load_rulebook())
        writes = {
            law.coordinates: tuple(tuple(cell.value for cell in row) for row in law.allowed) for law in result["laws"]
        }
        assert writes[("CAUSE",)] == (("+1",),)
        assert writes[("DO",)] == (("+1",),)


@requires_lexicon_sources
def test_actual_builder_keeps_kill_causative_and_withholds_wink_and_speech_causes():
    words = ["kill", "wink", "walk", "say", "tell"]
    sources = NativeSources(words, Path("data/external"), Path.home() / "nltk_data/corpora")
    records = {r["word"]: r for r in build(words, sources, load_rulebook(), None, tail_tasks=[])}
    assert any(r["after_selection"]["forced"].get("CAUSE") == "+1" for r in records["kill"]["readings"])
    for word in ("wink", "say", "tell"):
        assert all(r["after_selection"]["forced"].get("CAUSE") != "+1" for r in records[word]["readings"])
    reflexive = next(r for r in records["walk"]["readings"] if r["reading_id"] == "walk:VERB:run-51.3.2:frame-8")
    assert "CAUSE" not in reflexive["after_selection"]["forced"]
    assert any(u.get("blocked_evidence") == ["CONSTRUCTION_RESULT_PLACEHOLDER"] for u in reflexive["unmapped"])
