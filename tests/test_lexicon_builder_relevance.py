"""Record relevance cannot silently authorize lexical absence or assertions."""

import sqlite3
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from gse.curation.external_sources.sentiwordnet import SentiWordEntry, SentiWordNetParser
from gse.curation.lexicon_builder.engine import Assertion
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation, collect_evidence
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.relevance import observation_relevance, validate_bank_relevance
from gse.curation.lexicon_builder.storage import runtime_lookup


def test_unclassified_ratings_and_source_scope_do_not_limit_relevance():
    observation = Observation(None, "sentiwordnet", "record", "wordnet", {"pos_score": 0}, "association", ("id",))
    assert observation_relevance(observation) == frozenset(BANKS)
    assert "DO" in observation_relevance(observation)


def test_classification_is_independent_of_exact_or_candidate_link():
    annotation = {"code": "CLASSIFIED", "banks": ["WANT", "GOOD"], "provenance": ["review:record:1"]}
    for entry_id, candidates in (("id", ()), (None, ("id", "other"))):
        observation = Observation(
            entry_id, "source", "record", "family", {"bank_relevance": annotation}, "lexical", candidates
        )
        assert observation_relevance(observation) == frozenset({"WANT", "GOOD"})


def test_explicit_empty_requires_review_and_does_not_change_native_payload():
    features = {
        "raw": {"missing": None, "zero": 0},
        "bank_relevance": {"code": "CLASSIFIED", "banks": [], "provenance": ["review:no-own-word-banks"]},
    }
    original = deepcopy(features)
    observation = Observation(None, "source", "record", "family", features, "argument_structure")
    assert observation_relevance(observation) == frozenset()
    assert features == original
    assert observation.features is features


@pytest.mark.parametrize(
    "annotation,code",
    [
        (None, "FIELDS"),
        ([], "FIELDS"),
        ({}, "FIELDS"),
        ({"code": "CLASSIFIED", "banks": []}, "FIELDS"),
        ({"code": "CLASSIFIED", "banks": [], "provenance": ["review"], "value": 0}, "FIELDS"),
        ({"code": "UNCLASSIFIED", "banks": [], "provenance": ["review"]}, "CODE"),
        ({"code": True, "banks": [], "provenance": ["review"]}, "CODE"),
        ({"code": "CLASSIFIED", "banks": None, "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": "GOOD", "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": ["BAD"], "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": ["good"], "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": ["THIS"], "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": ["GOOD", "GOOD"], "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": [True], "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": [{}], "provenance": ["review"]}, "BANKS"),
        ({"code": "CLASSIFIED", "banks": [], "provenance": []}, "PROVENANCE"),
        ({"code": "CLASSIFIED", "banks": [], "provenance": "review"}, "PROVENANCE"),
        ({"code": "CLASSIFIED", "banks": [], "provenance": [""]}, "PROVENANCE"),
        ({"code": "CLASSIFIED", "banks": [], "provenance": [" "]}, "PROVENANCE"),
        ({"code": "CLASSIFIED", "banks": [], "provenance": [1]}, "PROVENANCE"),
    ],
)
def test_malformed_annotation_fails_closed(annotation, code):
    with pytest.raises(ValueError, match=f"INVALID_BANK_RELEVANCE_{code}"):
        validate_bank_relevance(annotation)


def test_every_canonical_bank_is_permitted_without_creating_values():
    assert validate_bank_relevance(
        {"code": "CLASSIFIED", "banks": list(BANKS), "provenance": ["review:all"]}
    ) == frozenset(BANKS)


@pytest.mark.parametrize("scores", [(0.0, 0.0, 1.0), (0.9, 0.1, 0.0), (0.0, 0.8, 0.2)])
def test_native_sentiment_relevance_does_not_assign_a_lexical_sign(scores):
    parser = SentiWordNetParser()
    parser._loaded = True
    parser.entries = {"good": [SentiWordEntry("good", "adj", *scores, "good.a.01")]}
    bundle = collect_evidence({"sentiwordnet": parser})
    assert bundle.assertions == ()
    assert len(bundle.observations) == 1
    observation = bundle.observations[0]
    assert observation_relevance(observation) == frozenset({"GOOD"})
    assert observation.entry_id is None
    assert observation.features["pos_score"] == scores[0]
    assert observation.features["neg_score"] == scores[1]


@pytest.mark.parametrize("extra", [{"size": 0}, {"definition": "large and pleasant"}])
def test_unknown_native_fields_cannot_be_silently_classified_as_sentiment_only(extra):
    parser = SentiWordNetParser()
    parser._loaded = True
    record = vars(SentiWordEntry("good", "adj", 0.9, 0.1, 0.0, "good.a.01")) | extra
    parser.entries = {"good": [record]}
    bundle = collect_evidence({"sentiwordnet": parser})
    assert observation_relevance(bundle.observations[0]) == frozenset(BANKS)
    for key, value in extra.items():
        assert bundle.observations[0].features[key] == value


@pytest.mark.parametrize("scores", [(True, 0, 0), (-0.1, 0.1, 1.0), (0.5, 0.5, 0.5), (None, 0, 1)])
def test_malformed_native_scores_do_not_authorize_narrowing(scores):
    parser = SentiWordNetParser()
    entry = SentiWordEntry("good", "adj", *scores, "good.a.01")
    assert parser.bank_relevance_for_entry(entry) is None


def test_existing_explicit_size_relevance_is_never_overwritten_by_adapter_hook():
    annotation = {"code": "CLASSIFIED", "banks": ["BIG"], "provenance": ["review:size-record"]}
    parser = SimpleNamespace(
        _loaded=True,
        entries={"large": {"bank_relevance": annotation}},
        bank_relevance_for_entry=lambda record: {
            "code": "CLASSIFIED",
            "banks": ["GOOD"],
            "provenance": ["incorrect-override"],
        },
    )
    bundle = collect_evidence({"source": parser})
    assert bundle.observations[0].features["bank_relevance"] == annotation


def test_exact_sentiment_link_does_not_narrow_unrestricted_wordnet_definition():
    synset = SimpleNamespace(
        name=lambda: "pleasant.a.01",
        definition=lambda: "A pleasant quality, with unrestricted definitional context.",
        pos=lambda: "a",
        lexname=lambda: "adj.all",
        hypernym_paths=lambda: [],
    )
    wordnet = SimpleNamespace(
        _loaded=True,
        _wn=SimpleNamespace(synsets=lambda word: [synset]),
        entries={},
        to_primitives_for_definition=lambda synset_name: {},
    )
    sentiment = SentiWordNetParser()
    sentiment._loaded = True
    sentiment.entries = {"pleasant": [SentiWordEntry("pleasant", "adj", 0.9, 0.1, 0.0, "pleasant.a.01")]}
    bundle = collect_evidence({"wordnet_hierarchy": wordnet, "sentiwordnet": sentiment}, ("pleasant",))
    definition = bundle.definitions[0]
    observations = {observation.source: observation for observation in bundle.observations}
    assert observations["sentiwordnet"].entry_id == definition.entry_id
    assert observation_relevance(observations["sentiwordnet"]) == frozenset({"GOOD"})
    assert observation_relevance(observations["wordnet_hierarchy"]) == frozenset(BANKS)
    assert bundle.assertions == ()


def test_relevance_annotation_does_not_change_native_record_identity():
    parser = SentiWordNetParser()
    parser._loaded = True
    parser.entries = {"good": [SentiWordEntry("good", "adj", 0.9, 0.1, 0.0, "good.a.01")]}
    classified = collect_evidence({"sentiwordnet": parser})
    unclassified_parser = SimpleNamespace(_loaded=True, entries=parser.entries)
    unclassified = collect_evidence({"sentiwordnet": unclassified_parser})
    assert classified.observations[0].record_id == unclassified.observations[0].record_id


@pytest.mark.parametrize("size_record", ["none", "candidate", "unclassified", "asserted"])
def test_native_relevance_bridge_preserves_size_evidence_gate_in_real_build(tmp_path, size_record):
    parser = SentiWordNetParser()
    parser._loaded = True
    parser.entries = {"pleasant": [SentiWordEntry("pleasant", "adj", 0.9, 0.1, 0.0, "pleasant.a.01")]}
    native = collect_evidence({"sentiwordnet": parser})
    # An independently authored definition is a possible, unresolved sense link.
    definition = Definition("pleasant:authored", "pleasant", "adjective", "A pleasant quality.")
    sentiment = replace(native.observations[0], candidate_entry_ids=(definition.entry_id,))
    author = Observation(
        definition.entry_id,
        "authored",
        "author:good",
        "authored",
        {"bank_relevance": {"code": "CLASSIFIED", "banks": ["GOOD"], "provenance": ["author:good"]}},
        "lexical",
    )
    observations = (author, sentiment)
    assertions = (Assertion("GOOD", 1, "authored", "author:good", "authored"),)
    if size_record != "none":
        features = (
            {}
            if size_record == "unclassified"
            else {"bank_relevance": {"code": "CLASSIFIED", "banks": ["BIG"], "provenance": ["review:size"]}}
        )
        size = Observation(
            definition.entry_id if size_record == "asserted" else None,
            "authored_size",
            "size:record",
            "size",
            features,
            "lexical",
            (definition.entry_id,),
        )
        observations += (size,)
        if size_record == "asserted":
            assertions += (Assertion("BIG", 1, "authored_size", "size:record", "size"),)
    path = tmp_path / "lexicon.db"
    build_dictionary(EvidenceBundle((definition,), observations, assertions, ()), path)
    with closing(sqlite3.connect(path)) as connection:
        result = runtime_lookup(connection, "pleasant")
    assert result["code"] == "IDENTIFIED"
    record = result["selected"]
    assert record["assignments"]["GOOD"] == 1
    if size_record == "none":
        assert record["assignments"]["BIG"] == 0
    elif size_record == "asserted":
        assert record["assignments"]["BIG"] == 1
    else:
        assert "BIG" not in record["assignments"]
        assert record["domains"]["BIG"] == [-1, 0, 1]
