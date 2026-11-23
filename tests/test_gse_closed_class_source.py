"""Curated grammar enters the same evidence spine without homograph guessing."""

import copy
import importlib
import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from gse.curation.external_sources.gse_closed_class import (
    FOUNDATION_COHORT,
    GSEClosedClassParser,
    grammatical_entry_ids,
    grammatical_requirement,
)
from gse.curation.external_sources.integrator import ExternalSourcesIntegrator
from gse.curation.external_sources.source_scope import SOURCE_PRIMITIVE_SCOPE
from gse.curation.lexicon_builder.evidence import (
    _SOURCE_CLASSES,
    collect_evidence,
    load_local_sources,
    validate_assertion_competence,
)
from gse.curation.lexicon_builder.model_evidence import evidence_view
from gse.curation.lexicon_builder.pipeline import load_evidence
from gse.lexicon.function_words import DETERMINER_ENCODINGS
from gse.lexicon.pronouns import PRONOUN_ENCODINGS


@pytest.mark.parametrize(
    "word,role,category,primitives",
    [
        ("he", "PRON", "pronoun", {"SOMEONE": 1}),
        ("this", "PRON", "pronoun", {"SOMETHING": 1}),
        ("might", "AUX", "modal", {"MAYBE": 1}),
        ("can", "AUX", "modal", {"CAN": 1}),
        ("must", "AUX", "modal", {"MUST": 1}),
        ("could", "AUX", "modal", {"CAN": 1}),
        ("should", "AUX", "modal", {"MUST": 1}),
        ("would", "AUX", "modal", {"MAYBE": 1}),
        ("perhaps", "ADV", "modal", {"MAYBE": 1}),
        ("maybe", "ADV", "modal", {"MAYBE": 1}),
        ("cannot", "AUX", "modal", {"CAN": 1, "NOT": 1}),
        ("are", "AUX", "auxiliary", {"BE": 1}),
        ("did", "AUX", "auxiliary", {"DO": 1}),
        ("has", "AUX", "auxiliary", {"HAVE": 1}),
        ("not", "PART", "negation", {"NOT": 1}),
        ("like", "ADP", "preposition", {"LIKE": 1}),
        ("will", "AUX", "modal", {}),
        ("shall", "AUX", "modal", {}),
    ],
)
def test_native_grammar_definition_identity_and_authored_projection(word, role, category, primitives):
    parser = GSEClosedClassParser()
    ids = grammatical_entry_ids(word, role)
    assert ids == (f"gse_closed_class:{category}:{word}",)
    entry = next(entry for entry in parser.get_entries(word) if entry.entry_id == ids[0])
    assert parser.to_primitives_for_entry(entry) == primitives
    assert entry.provenance and entry.native_encodings
    assert entry.cohort == FOUNDATION_COHORT
    assert grammatical_entry_ids(word, "NOUN") == ()


def test_distinct_grammar_roles_are_not_merged_or_first_selected():
    parser = GSEClosedClassParser()
    entries = parser.get_entries("that")
    assert {entry.catalog for entry in entries} == {"pronoun", "determiner", "conjunction"}
    assert grammatical_entry_ids("that", "PRON") == ("gse_closed_class:pronoun:that",)
    assert grammatical_entry_ids("that", "DET") == ("gse_closed_class:determiner:that",)
    assert grammatical_entry_ids("that", "SCONJ") == ("gse_closed_class:conjunction:that",)
    assert parser.to_primitives("that") == {}
    assert grammatical_entry_ids("'d", "AUX") == ()
    assert grammatical_entry_ids("has", "VERB") == ()


def test_source_tables_are_unchanged_and_possession_remains_grammar():
    originals = copy.deepcopy((PRONOUN_ENCODINGS, DETERMINER_ENCODINGS))
    parser = GSEClosedClassParser()
    entries = parser.get_entries("my")
    pronoun = next(entry for entry in entries if entry.catalog == "pronoun")
    assert pronoun.primitives == {"SOMEONE": 1} and "HAVE" not in pronoun.primitives
    assert pronoun.grammatical_features["gram"]["case"] == "GEN"
    pronoun.grammatical_features["gram"]["case"] = "changed copy"
    assert (PRONOUN_ENCODINGS, DETERMINER_ENCODINGS) == originals


def test_modal_requirement_comes_from_positive_declared_component_not_category():
    assert grammatical_requirement("gse_closed_class:modal:might") == "MODAL_PROJECTION_REQUIRED"
    assert grammatical_requirement("gse_closed_class:modal:maybe") == "MODAL_PROJECTION_REQUIRED"
    assert grammatical_requirement("gse_closed_class:modal:will") == "LEXICAL_ABSTENTION_ALLOWED"
    assert grammatical_requirement("gse_closed_class:modal:shall") == "LEXICAL_ABSTENTION_ALLOWED"
    assert grammatical_requirement("invented") == "UNKNOWN_GRAMMATICAL_DEFINITION"


def test_local_source_mandatory_cohort_even_when_content_list_is_empty():
    parsers, diagnostics = load_local_sources(("gse_closed_class",))
    assert diagnostics[0]["code"] == "LOADED"
    parser = parsers["gse_closed_class"]
    bundle = collect_evidence(parsers, ())
    assert len(bundle.definitions) == sum(len(records) for records in parser.entries.values())
    assert {d.lemma for d in bundle.definitions} == set(parser.get_all_words())
    assert all(o.scope == "lexical" and o.candidate_entry_ids == (o.entry_id,) for o in bundle.observations)
    assert all(a.value in (-1, 1) for a in bundle.assertions)
    assert not bundle.unresolved
    for assertion in bundle.assertions:
        validate_assertion_competence(assertion)
    empty = collect_evidence({}, ())
    assert empty.definitions == ()  # No implicit source injection into caller bundles.


def test_native_ids_stay_separate_from_wordnet_homographs():
    class Synset:
        def name(self):
            return "helium.n.01"

        def definition(self):
            return "a chemical element"

        def pos(self):
            return "n"

        def hypernym_paths(self):
            return []

        def lexname(self):
            return "noun.substance"

    wn = SimpleNamespace(synsets=lambda word: [Synset()] if word == "he" else [])
    wordnet = SimpleNamespace(_loaded=True, _wn=wn, to_primitives_for_definition=lambda name: {"SOMETHING": 1})
    grammar = GSEClosedClassParser()
    grammar.load()
    bundle = collect_evidence({"gse_closed_class": grammar, "wordnet_hierarchy": wordnet}, ("he",))
    assert {d.entry_id for d in bundle.definitions if d.lemma == "he"} == {
        "wordnet:he:helium.n.01",
        "gse_closed_class:pronoun:he",
    }
    links = {o.record_id: o.entry_id for o in bundle.observations}
    values = {(links[a.record_id], a.bank, a.value) for a in bundle.assertions}
    assert ("gse_closed_class:pronoun:he", "SOMEONE", 1) in values
    assert ("wordnet:he:helium.n.01", "SOMEONE", 1) not in values
    assert ("gse_closed_class:pronoun:he", "SOMETHING", 1) not in values


def test_complete_native_evidence_replays_without_changed_ids_or_values(tmp_path):
    parsers, _ = load_local_sources(("gse_closed_class",))
    bundle = collect_evidence(parsers, ("he",))
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"format": "gse.lexicon-evidence/1", **asdict(bundle)}))
    assert load_evidence(path) == bundle
    observations = [asdict(o) for o in bundle.observations]
    view = evidence_view(observations, "WANT")
    assert view["format"] == "gse.model-evidence/5"
    for raw, summary in zip(observations, view["records"], strict=True):
        assert summary["features"] == raw["features"]
        assert summary["omitted_fields"] == []
    altered = copy.deepcopy(observations[0])
    altered["features"]["future_field"] = 1
    assert evidence_view([altered], "WANT")["records"][0]["omitted_fields"] == [
        {"field": "/features/future_field", "code": "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA"}
    ]


@pytest.mark.parametrize(
    "change,code",
    [
        ({"primitives": {"SOMEONE": 0}}, "INVALID_CLOSED_CLASS_LEXICAL_COMPONENT"),
        ({"primitives": {"GOOD": 1}}, "INVALID_CLOSED_CLASS_LEXICAL_COMPONENT"),
        ({"primitives": {"SOMEONE": True}}, "INVALID_CLOSED_CLASS_LEXICAL_COMPONENT"),
        ({"entry_id": "wordnet:he:helium.n.01"}, "INVALID_CLOSED_CLASS_IDENTITY"),
        ({"provenance": ()}, "INVALID_CLOSED_CLASS_PROVENANCE"),
        ({"native_encodings": ()}, "INVALID_CLOSED_CLASS_NATIVE_ENCODING"),
        ({"grammatical_features": {"bad": float("nan")}}, "INVALID_CLOSED_CLASS_NATIVE_ENCODING"),
        ({"grammar_roles": ("NOUN",)}, "INVALID_CLOSED_CLASS_GRAMMAR_ROLE"),
    ],
)
def test_malformed_source_record_refuses_instead_of_projecting(change, code):
    entry = GSEClosedClassParser().get_entries("he")[0]
    with pytest.raises(ValueError, match=code):
        replace(entry, **change)


def test_actual_integrator_registers_source_without_external_network(monkeypatch):
    for source, class_name in _SOURCE_CLASSES.items():
        if source == "gse_closed_class":
            continue
        module = importlib.import_module(f"gse.curation.external_sources.{source}")
        monkeypatch.setattr(getattr(module, class_name), "load", lambda self: False)
    integrator = ExternalSourcesIntegrator()
    stats = integrator.load_all_sources()
    assert stats == {"gse_closed_class": len(integrator.parsers["gse_closed_class"].entries)}
    assert integrator.parsers["gse_closed_class"].to_primitives("might") == {"MAYBE": 1}
    assert set(SOURCE_PRIMITIVE_SCOPE["gse_closed_class"]) >= {"SOMEONE", "MAYBE", "CAN", "MUST"}


def test_foundation_definitions_do_not_expand_requested_other_source_vocabulary():
    requested = []
    wordnet = SimpleNamespace(_loaded=True, _wn=SimpleNamespace(synsets=lambda word: requested.append(word) or []))
    grammar = GSEClosedClassParser()
    grammar.load()
    bundle = collect_evidence({"gse_closed_class": grammar, "wordnet_hierarchy": wordnet}, ("requestedword",))
    assert requested == ["requestedword"]
    assert "he" in {definition.lemma for definition in bundle.definitions}
    assert all(definition.entry_id.startswith("gse_closed_class:") for definition in bundle.definitions)


@pytest.mark.parametrize("changes", [{"grammatical_features": {1: "bad key"}}, {"grammar_roles": ([],)}])
def test_native_shape_errors_have_named_codes(changes):
    entry = GSEClosedClassParser().get_entries("he")[0]
    with pytest.raises(ValueError, match="INVALID_CLOSED_CLASS"):
        replace(entry, **changes)
