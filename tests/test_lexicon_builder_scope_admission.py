"""Exact reference catalog evidence cannot admit a stative BE model assertion."""

import copy
import json
from dataclasses import asdict

import pytest

from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import collect_evidence
from GSE.curation.lexicon_builder.model_batch import OllamaBatchTransport
from GSE.curation.lexicon_builder.residual import OllamaTransport, build_request, complete_bank
from GSE.curation.lexicon_builder.scope_admission import model_scope_admission

BANKS = ("I", "YOU", "BE", "SOMEONE", "SOMETHING", "EXIST")


def native_request(word="you", bank="BE", *, extra=()):
    parser = GSEClosedClassParser()
    parser.load()
    bundle = collect_evidence({"gse_closed_class": parser}, (word,))
    entry_id = f"gse_closed_class:pronoun:{word}"
    definition = next(item for item in bundle.definitions if item.entry_id == entry_id)
    observations = tuple(
        json.loads(json.dumps(asdict(item))) for item in bundle.observations if item.entry_id == entry_id
    )
    ids = {record["record_id"] for record in observations}
    assertions = tuple(item for item in bundle.assertions if item.record_id in ids)
    current = propagate(BANKS, assertions, ())
    request = build_request(entry_id, bank, current, observations + extra, definition=definition)
    return request, assertions, current


@pytest.mark.parametrize("word", ["you", "he", "it", "this", "someone"])
def test_actual_collector_reference_definitions_refuse_positive_be_without_zero(word):
    request, assertions, current = native_request(word)
    original = request.payload()
    result = complete_bank(request, BANKS, assertions, (), lambda payload, schema: '{"BE":1}')
    assert result.code == "SCOPE_UNJUSTIFIED"
    assert result.assertion is None
    assert result.resolution == current
    assert result.resolution is not None
    assert result.resolution.domains["BE"] == frozenset((-1, 0, 1))
    assert "BE" not in result.resolution.assignments
    assert result.details["reason"] == "ENTITY_REFERENCE_ALONE_DOES_NOT_JUSTIFY_POSITIVE_BE"
    assert request.payload() == original


@pytest.mark.parametrize("value,code", [(0, "ASSIGNED"), (-1, "ASSIGNED"), (None, "ABSTAINED")])
def test_other_outputs_follow_existing_admission_without_automatic_fill(value, code):
    request, assertions, _ = native_request()
    result = complete_bank(request, BANKS, assertions, (), lambda payload, schema: json.dumps({"BE": value}))
    assert result.code == code
    if value is None:
        assert result.assertion is None
    else:
        assert result.assertion is not None and result.assertion.value == value


def test_exist_remains_outside_be_only_guard():
    request, assertions, _ = native_request(bank="EXIST")
    result = complete_bank(request, BANKS, assertions, (), lambda payload, schema: '{"EXIST":1}')
    assert result.code == "ASSIGNED"


@pytest.mark.parametrize("scope", ["association", "world", "source_structure"])
def test_nonlexical_records_cannot_supply_own_stative_content(scope):
    request, _, _ = native_request()
    other = {
        "entry_id": request.entry_id,
        "source": "conceptnet" if scope == "world" else "fixture",
        "scope": scope,
        "features": {"primitives": {"BE": 1}},
    }
    decision = model_scope_admission(request.entry_id, "BE", 1, request.observations + (other,))
    assert decision["code"] == "SCOPE_UNJUSTIFIED"


def test_foreign_or_candidate_lexical_record_is_not_exact_stative_evidence():
    request, _, _ = native_request()
    for entry_id in (None, "unrelated-definition"):
        other = {
            "entry_id": entry_id,
            "candidate_entry_ids": [request.entry_id],
            "source": "fixture",
            "scope": "lexical",
        }
        assert (
            model_scope_admission(request.entry_id, "BE", 1, request.observations + (other,))["code"]
            == "SCOPE_UNJUSTIFIED"
        )


def test_additional_exact_lexical_source_prevents_narrow_reference_only_classification():
    request, _, _ = native_request()
    other = {
        "entry_id": request.entry_id,
        "source": "fixture",
        "scope": "lexical",
        "features": {"definition": "A stative use."},
    }
    decision = model_scope_admission(request.entry_id, "BE", 1, request.observations + (other,))
    assert decision == {"code": "NOT_APPLICABLE", "reason": "ADDITIONAL_EXACT_LEXICAL_SOURCE"}


@pytest.mark.parametrize(
    "change",
    ["nonreference", "empty", "wrong_role", "wrong_catalog", "definition", "native_origin", "boolean", "extra_field"],
)
def test_labels_or_spelling_do_not_substitute_for_complete_existing_native_record(change):
    request, _, _ = native_request()
    records = copy.deepcopy(request.observations)
    features = records[0]["features"]
    if change == "nonreference":
        features["primitives"]["BE"] = 1
    elif change == "empty":
        features["primitives"] = {}
    elif change == "wrong_role":
        features["grammar_roles"] = ["AUX"]
    elif change == "wrong_catalog":
        features["catalog"] = "auxiliary"
    elif change == "definition":
        features["definition"] = "A different stative definition."
    elif change == "native_origin":
        features["native_encodings"][0]["value"]["primitives"]["BE"] = 1
    elif change == "boolean":
        features["primitives"]["SOMEONE"] = True
    else:
        features["additional_lexical_content"] = {"BE": 1}
    assert model_scope_admission(request.entry_id, "BE", 1, records)["code"] == "NOT_APPLICABLE"


def test_no_source_does_not_become_general_pronoun_mask():
    assert model_scope_admission("gse_closed_class:pronoun:you", "BE", 1, ()) == {
        "code": "NOT_APPLICABLE",
        "reason": "NO_EXACT_LEXICAL_SOURCE",
    }


def test_refusal_also_follows_actual_batch_transport_and_preserves_known_value(monkeypatch):
    request, assertions, current = native_request()
    base = OllamaTransport("fixture", thinking=False, output_tokens=1024)
    calls = []

    def network(message, malformed_code):
        if message.method == "GET":
            return {"models": [{"name": "fixture", "digest": "a" * 64}]}
        calls.append(json.loads(message.data))
        return {"done": True, "done_reason": "stop", "response": '{"q0":{"BE":1}}'}

    monkeypatch.setattr(base, "_request_json", network)
    monkeypatch.setattr("GSE.curation.llm.ollama_client.register_model", lambda *args: None)
    batch = OllamaBatchTransport(base)
    batch.pin()
    result = complete_bank(request, BANKS, assertions, (), batch)
    assert len(calls) == 1
    assert result.code == "SCOPE_UNJUSTIFIED"
    assert result.assertion is None
    assert result.resolution == current
    assert result.resolution is not None
    assert result.resolution.assignments == {"SOMEONE": 1, "YOU": 1}


def test_zero_still_obeys_existing_symbolic_contradiction_check():
    request, assertions, _ = native_request()
    # The request was built before a new hard value, so even a zero response
    # must not be used to overwrite that new evidence.
    updated = assertions + (Assertion("BE", 1, "fixture", "stative", "dictionary"),)
    result = complete_bank(request, BANKS, updated, (), lambda payload, schema: '{"BE":0}')
    assert result.code == "STALE_REQUEST"
    assert result.assertion is None
