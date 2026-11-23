"""MVP consumer contract: complete vectors preserve explicit absence and silence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gse.lexicon_builder.artifact import export_vector, read_vectors, vector_status
from gse.lexicon_builder.build import build
from gse.lexicon_builder.core import CANONICAL_COORDINATES
from gse.lexicon_builder.model import selection_status
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_rulebook import admitted_rulebook
from tests.lexicon_sources import requires_lexicon_sources


class DegreeSelector:
    """Deterministic stand-in for transport tests; the live proof uses Ollama."""

    def select(self, payload, options):
        answer = {key: "ACCOUNTED" if payload["operation"] == "BANK_OMISSION_REVIEW" else "+1" for key in options}
        assert selection_status(options, answer) == "VALID_SELECTION"
        return {"request_sha256": "transport-test", "answer": answer}


def test_written_zero_is_retained_and_silence_has_no_numeric_value():
    states = dict.fromkeys(CANONICAL_COORDINATES, "empty")
    states.update(FEEL="+1", KIND="0")
    mask = [states[c] != "empty" for c in CANONICAL_COORDINATES]
    values = [None if states[c] == "empty" else int(states[c]) for c in CANONICAL_COORDINATES]
    assert vector_status(states, mask, values) == "VALID_VECTOR"
    mask[CANONICAL_COORDINATES.index("KIND")] = False
    assert vector_status(states, mask, values) == "MASK_MISMATCH"


def test_unknown_or_missing_coordinates_cannot_masquerade_as_silence():
    assert vector_status(None, None, None) == "MALFORMED_VECTOR"
    assert vector_status({}, [], []) == "COORDINATE_MISMATCH"
    states = dict.fromkeys(CANONICAL_COORDINATES, "empty")
    assert vector_status(states, [], []) == "SHAPE_MISMATCH"
    states["NUMBER"] = "+1"
    assert vector_status(states, [], []) == "COORDINATE_MISMATCH"


@requires_lexicon_sources
def test_degree_domain_never_depends_on_a_word_level_affect_rating():
    words = ["happy", "delighted", "tiny"]
    sources = NativeSources(words, Path("data/external"), Path.home() / "nltk_data/corpora")
    book = admitted_rulebook("USAS_OWN_HAPPY_SAD_STATE", "USAS_OWN_SIZE_POLE")
    records = list(build(words, sources, book, None))
    for record in records:
        reading = record["readings"][0]
        assert reading["symbolic_before"]["forced"]["INTENSITY"] == "+1"
        assert reading["model_calls"] == []
        assert reading["candidate_vector"] is None
        assert reading["number_scale"]["numeric_gain"] is None
        assert "NUMBER" not in reading["symbolic_before"]["domains"]


def test_unpaired_negative_and_numeric_silence_are_refused():
    states = dict.fromkeys(CANONICAL_COORDINATES, "empty")
    mask = [False] * 58
    values = [None] * 58
    states["FEEL"] = "-1"
    assert vector_status(states, mask, values) == "ILLEGAL_STATE"
    states["FEEL"] = "empty"
    values[0] = 0
    assert vector_status(states, mask, values) == "SILENCE_HAS_VALUE"


def test_boolean_and_wrong_signed_values_are_not_accepted_as_integer_signs():
    states = dict.fromkeys(CANONICAL_COORDINATES, "empty")
    states["GOOD"] = "-1"
    mask = [states[c] != "empty" for c in CANONICAL_COORDINATES]
    values = [None if states[c] == "empty" else int(states[c]) for c in CANONICAL_COORDINATES]
    assert vector_status(states, mask, values) == "VALID_VECTOR"
    values[CANONICAL_COORDINATES.index("GOOD")] = True
    assert vector_status(states, mask, values) == "VALUE_MISMATCH"


@requires_lexicon_sources
def test_real_source_templates_cannot_export_unproved_silences():
    words = ["superb", "immense", "delighted", "sorrowful"]
    sources = NativeSources(words, Path("data/external"), Path.home() / "nltk_data/corpora")
    book = admitted_rulebook("USAS_OWN_QUALITY_POLE", "USAS_OWN_SIZE_POLE", "USAS_OWN_HAPPY_SAD_STATE")
    records = list(build(words, sources, book, DegreeSelector(), bank_review=True))
    assert all(record["readings"] for record in records)  # otherwise the checks below pass vacuously
    for record in records:
        for reading in record["readings"]:
            assert reading["code"] == "PARTIAL"
            assert reading["candidate_vector"] is None
            if "provisional_vector" in reading:
                assert reading["provisional_vector"] is not None
            with pytest.raises(ValueError, match="complete candidate"):
                export_vector(reading)


def complete_transport_fixture():
    """Declared wire-format fixture, not an English lexical-completeness claim."""
    states = dict.fromkeys(CANONICAL_COORDINATES, "empty")
    states.update(FEEL="+1", GOOD="-1", KIND="0", SOMETHING="0", INTENSITY="+1")
    return {
        "word": "transport-fixture",
        "reading_id": "transport-fixture:declared",
        "code": "CANDIDATE_COMPLETE",
        "candidate_vector": {
            "states": states,
            "mask": [states[c] != "empty" for c in CANONICAL_COORDINATES],
            "signs": [None if states[c] == "empty" else int(states[c]) for c in CANONICAL_COORDINATES],
            "provisional_silence": [],
        },
        "number_scale": {"family": "test-only", "numeric_gain": None},
        "premise_record_ids": ["fixture:explicit-declaration"],
        "rule_id": "TRANSPORT_FIXTURE",
        "after_closure": {"fired_rules": ["TRANSPORT_FIXTURE"]},
        "model_calls": [],
    }


def test_explicit_declared_vector_round_trips_without_losing_zeros_or_masks(tmp_path):
    artifacts = [export_vector(complete_transport_fixture())]
    path = tmp_path / "vectors.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in artifacts))
    assert list(read_vectors(path)) == artifacts
    assert artifacts[0]["prime_views"]["BAD"] == 1
    assert artifacts[0]["states"]["GOOD"] == "-1"
    assert artifacts[0]["states"]["KIND"] == "0"
    assert artifacts[0]["states"]["THINK"] == "empty"
    assert artifacts[0]["number_scale"]["numeric_gain"] is None
    assert all(not r["production_eligible"] for r in artifacts)


@requires_lexicon_sources
def test_partial_native_reading_cannot_be_exported_as_a_complete_vector():
    sources = NativeSources(["exchange"], Path("data/external"), Path.home() / "nltk_data/corpora")
    reading = list(build(["exchange"], sources, admitted_rulebook("VN_POSSESSION"), None))[0]["readings"][0]
    with pytest.raises(ValueError, match="complete candidate"):
        export_vector(reading)


def test_consumer_refuses_an_alias_that_disagrees_with_the_canonical_coordinate(tmp_path):
    record = export_vector(complete_transport_fixture())
    record["prime_views"]["SMALL"] = -1
    path = tmp_path / "vectors.jsonl"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="alias views"):
        list(read_vectors(path))
