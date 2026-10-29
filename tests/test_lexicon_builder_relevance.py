"""Record relevance cannot silently authorize lexical absence or assertions."""

from copy import deepcopy

import pytest

from gse.curation.lexicon_builder.evidence import Observation
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.relevance import observation_relevance, validate_bank_relevance


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
