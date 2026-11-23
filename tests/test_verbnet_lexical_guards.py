"""Own-word causation requires a native bound outcome, never a role proxy."""

import copy
from types import SimpleNamespace
from xml.etree.ElementTree import fromstring

import pytest

from GSE.curation.external_sources.verbnet import VerbNetEntry, VerbNetParser, _native_frame, _native_xml
from GSE.curation.lexicon_builder.evidence import collect_evidence


def predicate(name, event="during(E)", roles=("Theme",), *, negative=False, extra=""):
    args = "".join(f'<ARG type="ThemRole" value="{role}"/>' for role in roles)
    events = (event,) if isinstance(event, str) else event
    args += "".join(f'<ARG type="Event" value="{value}"/>' for value in events)
    return f'<PRED value="{name}"' + (' bool="!"' if negative else "") + f"><ARGS>{args}{extra}</ARGS></PRED>"


def entry_for(*predicates, syntax="", restrictions="", roles=("Agent", "Theme")):
    frame = _native_frame(
        fromstring(f"<FRAME><SYNTAX>{syntax}</SYNTAX><SEMANTICS>{''.join(predicates)}</SEMANTICS></FRAME>")
    )
    trees = [
        _native_xml(fromstring(f'<THEMROLE type="{role}">{restrictions if role == "Theme" else ""}</THEMROLE>'))
        for role in roles
    ]
    return VerbNetEntry(
        "verb",
        "fixture-1",
        list(roles),
        class_context=[{"class_id": "fixture-1", "thematic_roles": trees, "frames": [frame]}],
    )


def cause(event="E", roles=("Agent",)):
    return predicate("cause", event, roles)


def test_bound_outcome_warrants_cause_and_agent_do_without_participant_banks():
    entry = entry_for(cause(), predicate("contact", "end(E)"))
    original = copy.deepcopy(entry)
    parser = VerbNetParser()
    assert parser.to_primitives_for_entry(entry) == {"CAUSE": 1, "DO": 1}
    proof = parser.projection_diagnostics_for_entry(entry)["frames"][0]["cause"]["proofs"][0]
    assert proof["affected_roles"] == ["Theme"]
    assert proof["cause_predicate"] == 0 and proof["outcome_predicate"] == 1
    assert entry == original


def test_event_causer_warrants_happen_without_inventing_agent_do():
    entry = entry_for(cause(("E0", "E1"), ()), predicate("contact", "end(E1)"), roles=("Theme",))
    assert VerbNetParser().to_primitives_for_entry(entry) == {"CAUSE": 1, "HAPPEN": 1}


@pytest.mark.parametrize(
    "outcome,syntax,restrictions,roles,reason",
    [
        (predicate("transfer_info"), "", "", ("Agent", "Theme"), None),
        (predicate("Pred", "result(E)"), "", "", ("Agent", "Theme"), "CONSTRUCTION_RESULT_PLACEHOLDER"),
        (predicate("exist", "end(E)"), "", "", ("Agent", "Theme"), "PARTICIPANT_EXISTENCE_PRESUPPOSITION"),
        (
            predicate("contact", "end(E)"),
            '<NP value="Theme"><SYNRESTRS><SYNRESTR Value="+" type="refl"/></SYNRESTRS></NP>',
            "",
            ("Agent", "Theme"),
            "AFFECTED_PARTICIPANT_IDENTITY_UNCONFIRMED",
        ),
        (
            predicate("contact", "end(E)"),
            "",
            '<SELRESTRS><SELRESTR Value="+" type="body_part"/></SELRESTRS>',
            ("Agent", "Theme"),
            "AFFECTED_PARTICIPANT_IDENTITY_UNCONFIRMED",
        ),
        (predicate("contact", "end(E)"), "", "", ("Agent",), "AFFECTED_PARTICIPANT_IDENTITY_UNCONFIRMED"),
        (predicate("contact", "end(E)", ("Agent",)), "", "", ("Agent", "Theme"), None),
    ],
)
def test_presupposition_reflexivity_ownership_and_construction_do_not_label_cause(
    outcome, syntax, restrictions, roles, reason
):
    entry = entry_for(cause(), outcome, syntax=syntax, restrictions=restrictions, roles=roles)
    parser = VerbNetParser()
    assert parser.to_primitives_for_entry(entry) == {}
    decision = parser.projection_diagnostics_for_entry(entry)["frames"][0]["cause"]
    assert decision["code"] == "NO_CHANGE_TO_ANOTHER_PARTICIPANT"
    if reason is not None:
        assert reason in decision["blocked_evidence"]


def test_existence_transition_is_content_when_same_event_and_role_changes():
    entry = entry_for(cause(), predicate("exist", "start(E)", negative=True), predicate("exist", "end(E)"))
    assert VerbNetParser().to_primitives_for_entry(entry) == {"CAUSE": 1, "DO": 1}
    entry.class_context[0]["frames"][0]["semantics"][1]["arguments"][0]["value"] = "Agent"
    assert VerbNetParser().to_primitives_for_entry(entry) == {}


def test_marked_semantic_roles_retain_declared_bindings_and_native_markers():
    entry = entry_for(cause(roles=("?Agent",)), predicate("contact", "end(E)", ("?Theme",)))
    original = copy.deepcopy(entry)
    parser = VerbNetParser()
    assert parser.to_primitives_for_entry(entry) == {"CAUSE": 1, "DO": 1}
    assert entry == original
    proof = parser.projection_diagnostics_for_entry(entry)["frames"][0]["cause"]["proofs"][0]
    assert proof["affected_roles"] == ["Theme"]


def test_unrelated_subevent_cannot_supply_cause_outcome():
    entry = entry_for(cause("E1"), predicate("contact", "end(E0)"))
    assert VerbNetParser().to_primitives_for_entry(entry) == {}


def test_later_component_negation_does_not_erase_positive_phase_but_same_phase_conflict_abstains():
    parser = VerbNetParser()
    entry = entry_for(predicate("motion", "during(E)"), predicate("motion", "end(E)", negative=True))
    assert parser.to_primitives_for_entry(entry) == {"MOVE": 1}
    entry = entry_for(predicate("motion"), predicate("motion", negative=True))
    assert parser.to_primitives_for_entry(entry) == {}
    assert (
        parser.projection_diagnostics_for_entry(entry)["frames"][0]["components"]["MOVE"]["code"]
        == "CONTRADICTORY_NATIVE_BINDING"
    )


def test_positive_outcome_conflict_does_not_prove_cause():
    entry = entry_for(cause(), predicate("contact", "end(E)"), predicate("contact", "end(E)", negative=True))
    assert VerbNetParser().to_primitives_for_entry(entry) == {}


def test_all_applicable_frames_and_child_restrictions_are_checked():
    parser = VerbNetParser()
    entry = entry_for(cause(), predicate("contact", "end(E)"))
    entry.class_context.append({"class_id": "child-1", "frames": [copy.deepcopy(entry.class_context[0]["frames"][0])]})
    assert parser.to_primitives_for_entry(entry) == {"CAUSE": 1, "DO": 1}
    entry.class_context[1]["frames"].append({"semantics": []})
    assert parser.to_primitives_for_entry(entry) == {}
    entry.class_context[1]["frames"].pop()
    entry.class_context[1]["thematic_roles"] = [
        _native_xml(
            fromstring(
                '<THEMROLE type="Theme"><SELRESTRS><SELRESTR Value="+" type="body_part"/></SELRESTRS></THEMROLE>'
            )
        )
    ]
    assert parser.to_primitives_for_entry(entry) == {}


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        [None],
        [{"predicate_value": None}],
        [{"predicate_value": "motion", "negated": False, "polarity": "", "arguments": [None]}],
    ],
)
def test_malformed_native_semantics_never_supply_values(malformed):
    entry = entry_for()
    entry.class_context[0]["frames"][0]["semantics"] = malformed
    assert VerbNetParser().to_primitives_for_entry(entry) == {}


@pytest.mark.parametrize("event", ["unknown", "E2", "during( E)", "", "future(E)"])
def test_unrecognized_native_event_form_abstains(event):
    entry = entry_for(predicate("motion", event))
    assert VerbNetParser().to_primitives_for_entry(entry) == {}


def test_actual_collector_still_requires_exact_wordnet_key_and_preserves_source():
    entry = entry_for(cause(), predicate("contact", "end(E)"))
    entry.wordnet_sense_keys = ["verb%2:00:00"]
    synset = SimpleNamespace(
        name=lambda: "verb.v.01",
        pos=lambda: "v",
        definition=lambda: "a fixture lexical act",
        hypernym_paths=lambda: [],
        lexname=lambda: "verb.contact",
    )
    wn = SimpleNamespace(
        synsets=lambda word: [synset],
        lemma_from_key=lambda key: SimpleNamespace(name=lambda: "verb", synset=lambda: synset),
    )
    grammar = SimpleNamespace(_loaded=True, _wn=wn, to_primitives_for_definition=lambda name: {})
    parser = VerbNetParser()
    parser._loaded = True
    parser.entries = {"verb": [entry]}
    bundle = collect_evidence({"wordnet_hierarchy": grammar, "verbnet": parser}, ("verb",))
    assert {(assertion.bank, assertion.value) for assertion in bundle.assertions} == {("CAUSE", 1), ("DO", 1)}
    witnesses = [o for o in bundle.observations if o.source == "verbnet" and o.scope == "lexical"]
    assert len(witnesses) == 1 and witnesses[0].entry_id == "wordnet:verb:verb.v.01"
    assert witnesses[0].features["native"]["class_context"] == entry.class_context
    entry.wordnet_sense_keys = ["?verb%2:00:00"]
    unlinked = collect_evidence({"wordnet_hierarchy": grammar, "verbnet": parser}, ("verb",))
    assert not unlinked.assertions
    assert all(o.scope != "lexical" for o in unlinked.observations if o.source == "verbnet")
