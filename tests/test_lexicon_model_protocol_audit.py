"""The calibration adapter exercises real closure without claiming native gold."""

import json

import pytest

from gse.curation.lexicon_builder.foundation import BANKS
from scripts import audit_lexicon_model_protocol as audit


def payload(bank="WANT", pos="noun"):
    return {
        "entry_id": "d",
        "bank": bank,
        "definition": {"entry_id": "d", "lemma": "table", "pos": pos, "definition": "a piece of furniture"},
        "known": {},
        "observations": [],
        "allowed_values": [0],
    }


def native(entry="d", scope="lexical"):
    return {
        "entry_id": entry,
        "candidate_entry_ids": ["d"],
        "source": "authored_dictionary",
        "record_id": "r",
        "family": "dictionary",
        "scope": scope,
        "features": {"definition": "a piece of furniture"},
    }


def test_production_uses_full_basis_and_real_projection_not_fixture_domain():
    request, symbolic = audit.prepare_case(payload(), production_scaffold=True)
    assert symbolic is None
    assert set(request.scaffold["domains"]) == set(BANKS)
    assert request.known["GOOD"] == 0
    assert request.allowed_values == (-1, 0, 1)
    assert request.scaffold["context"] == {"pos": "noun"}
    assert len(request.scaffold["approved_relations"]) == 23


def test_small_fixture_default_retains_separate_no_rule_experiment():
    request, symbolic = audit.prepare_case(payload())
    assert symbolic is None
    assert request.known == {}
    assert request.scaffold["domains"] == {"WANT": [-1, 0, 1]}
    assert request.scaffold["approved_relations"] == []


def test_projection_can_resolve_target_before_any_model_call():
    request, symbolic = audit.prepare_case(payload("GOOD"), production_scaffold=True)
    assert request is None
    assert symbolic["code"] == "SYMBOLICALLY_RESOLVED"
    assert symbolic["value"] == 0


def test_source_relevance_blocks_default_even_when_candidate_identity_unresolved():
    data = payload("GOOD", "adjective")
    data["known"] = {"BIG": 1}
    data["observations"] = [native(None, "association")]
    request, symbolic = audit.prepare_case(data, production_scaffold=True)
    assert symbolic is None
    assert request.allowed_values == (-1, 0, 1)
    guard = next(
        record
        for record in request.scaffold["proof_trace"]
        if record["kind"] == "EVIDENCE_GUARD" and record["rule_id"] == "founder:absence:big-good"
    )
    assert guard["reason"] == "RELEVANT_EVIDENCE"
    assert guard["witnesses"][0]["supplied_evidence"] is True


def test_restrictions_require_exact_native_link_and_preserve_remaining_domain():
    data = payload()
    data["observations"] = [native()]
    data["domain_restrictions"] = [
        {
            "bank": "WANT",
            "allowed_values": [0, 1],
            "source": "authored_dictionary",
            "record_id": "r",
            "family": "dictionary",
            "scope": "lexical",
        }
    ]
    request, symbolic = audit.prepare_case(data, production_scaffold=True)
    assert symbolic is None
    assert request.allowed_values == (0, 1)
    data["observations"] = [native(None)]
    with pytest.raises(ValueError, match="CALIBRATION_RESTRICTION_PROVENANCE_MISMATCH"):
        audit.prepare_case(data, production_scaffold=True)


def test_foreign_exact_definition_cannot_be_smuggled_through_candidate_list():
    data = payload()
    data["observations"] = [native("other:sense")]
    with pytest.raises(ValueError, match="CALIBRATION_SOURCE_DEFINITION_MISMATCH"):
        audit.prepare_case(data, production_scaffold=True)


def test_cli_separates_symbolic_decision_from_label_agreement_and_counts_real_calls(tmp_path, monkeypatch):
    cases = tmp_path / "cases.json"
    report = tmp_path / "report.json"
    cases.write_text(
        json.dumps(
            {
                "label_authority": "AUTHORED_NOT_GOLD",
                "cases": [
                    {"input": payload("GOOD"), "expected": 1},
                    {"input": payload(), "expected": None},
                    {"input": payload(), "expected": None},
                ],
            }
        )
    )
    calls = []

    class Fake:
        identity = "pinned:test"
        output_tokens, context_tokens, thinking, timeout = 128, 32768, False, 300

        def __init__(self, *args, **kwargs):
            pass

        def pin(self):
            return {"model": "test", "digest": "a" * 64}

        def __call__(self, data, schema):
            calls.append((data, schema))
            return '{"WANT":null}'

    monkeypatch.setattr(audit, "OllamaTransport", Fake)
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit",
            "--cases",
            str(cases),
            "--report",
            str(report),
            "--model",
            "test",
            "--production-scaffold",
            "--max-model-calls",
            "1",
        ],
    )
    audit.main()
    result = json.loads(report.read_text())
    assert result["model_calls"] == len(calls) == 1
    assert result["label_authority"] == "AUTHORED_NOT_GOLD"
    assert [case["code"] for case in result["cases"]] == [
        "SYMBOLICALLY_RESOLVED",
        "IDENTIFIED",
        "MODEL_BUDGET_EXHAUSTED",
    ]
    assert [case["expected_agreement"] for case in result["cases"]] == ["MISMATCH", "MATCH", "NO_VALUE"]
    assert result["cases"][1]["value"] is None


def batch_cases(entries=("a", "b", "c")):
    cases = []
    for entry in entries:
        data = payload()
        data["entry_id"] = data["definition"]["entry_id"] = entry
        cases.append({"input": data, "expected": None})
    return cases


def pinned_batch(monkeypatch, *, max_items=4, max_input_bytes=None):
    from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport
    from gse.curation.lexicon_builder.residual import OllamaTransport

    base = OllamaTransport("test", thinking=False, output_tokens=1024)
    requests = []

    def network(request, malformed_code):
        if request.full_url.endswith("/api/tags"):
            return {"models": [{"name": "test", "digest": "a" * 64}]}
        body = json.loads(request.data)
        prompt = json.loads(body["prompt"])
        slots = [item["slot"] for item in prompt["items"]]
        assert slots == [f"q{index}" for index in range(len(slots))]
        assert set(body["format"]["properties"]) == set(slots)
        requests.append(body)
        return {
            "done": True,
            "response": json.dumps(
                {slot: {body["format"]["properties"][slot]["required"][0]: None} for slot in reversed(slots)}
            ),
            "eval_count": 17,
        }

    monkeypatch.setattr(base, "_request_json", network)
    monkeypatch.setattr("gse.curation.llm.ollama_client.register_model", lambda *args: None)
    base.pin()
    return base, OllamaBatchTransport(base, max_items=max_items, max_input_bytes=max_input_bytes), requests


def test_batch_cli_uses_real_wrapper_preserves_labels_outside_input_and_counts_questions(tmp_path, monkeypatch):
    base, _, network = pinned_batch(monkeypatch)
    cases, report = tmp_path / "cases.json", tmp_path / "report.json"
    cases.write_text(json.dumps({"label_authority": "AUTHORED_NOT_GOLD", "cases": batch_cases()}))
    monkeypatch.setattr(audit, "OllamaTransport", lambda *args, **kwargs: base)
    monkeypatch.setattr(
        "sys.argv",
        ["audit", "--cases", str(cases), "--report", str(report), "--model", "test", "--batch-size", "4"],
    )
    audit.main()
    result = json.loads(report.read_text())
    assert result["cell_questions"] == result["model_calls"] == 3
    assert result["transport_invocations"] == len(network) == 1
    assert result["budget_unit"] == "CELL_QUESTIONS"
    assert result["label_authority"] == "AUTHORED_NOT_GOLD"
    assert result["per_class"] == {"UNRESOLVED": {"IDENTIFIED": 3}}
    assert all(record["value"] is None for record in result["cases"])
    assert all(record["elapsed_scope"] == "SHARED_BATCH_INVOCATION" for record in result["cases"])
    assert ":batch@" in result["transport_identity"]
    prompt = json.loads(network[0]["prompt"])
    assert all("expected" not in item and "expected" not in item["input"] for item in prompt["items"])
    assert {item["input"]["entry_id"] for item in prompt["items"]} == {"a", "b", "c"}
    assert prompt["format"] == "gse.lexical-component-batch/2"
    assert [item["slot"] for item in prompt["items"]] == ["q0", "q1", "q2"]
    assert all(len(item["request_id"]) == 64 for item in prompt["items"])
    assert all(record["transport_metrics"]["eval_count"] == 17 for record in result["cases"])
    assert all(record["transport_metrics"]["item_count"] == 3 for record in result["cases"])


def test_batch_shrinks_group_without_changing_single_request_evidence(monkeypatch):
    from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport

    cases = batch_cases()
    base, transport, network = pinned_batch(monkeypatch)
    prepared = [audit.prepare_case(case["input"])[0] for case in cases]
    items = tuple((request.payload(), request.output_schema()) for request in prepared)
    maximum = transport.prepare(items[:1]).input_bytes
    limited = OllamaBatchTransport(base, max_items=4, max_input_bytes=maximum)
    rows = list(audit.calibration_results(cases, limited, budget=3, batch_size=4))
    assert rows[-1][2:] == (3, 3)
    assert [row[1]["input"] for row in rows] == [request.payload() for request in prepared]
    assert all(len(json.loads(body["prompt"])["items"]) == 1 for body in network)


def test_batch_repeated_definition_splits_and_budget_counts_cells(monkeypatch):
    _, transport, network = pinned_batch(monkeypatch)
    cases = batch_cases(("same", "same", "other", "last"))
    rows = list(audit.calibration_results(cases, transport, budget=3, batch_size=4))
    assert rows[-1][2:] == (3, 2)
    assert len(network) == 2
    assert [row[1]["code"] for row in rows] == ["IDENTIFIED"] * 3 + ["MODEL_BUDGET_EXHAUSTED"]
    assert [len(json.loads(body["prompt"])["items"]) for body in network] == [1, 2]


def test_batch_oversized_singleton_refuses_without_transport_or_label_change(monkeypatch):
    _, transport, network = pinned_batch(monkeypatch, max_input_bytes=1)
    rows = list(audit.calibration_results(batch_cases(), transport, budget=3, batch_size=4))
    assert rows[-1][2:] == (0, 0)
    assert network == []
    assert all(row[1]["reason"] == "BATCH_INPUT_TOO_LARGE" for row in rows)
    assert all("value" not in row[1] for row in rows)


def test_batch_symbolic_target_does_not_consume_budget(monkeypatch):
    _, transport, network = pinned_batch(monkeypatch)
    cases = [{"input": payload("GOOD"), "expected": 1}, *batch_cases(("a", "b"))]
    rows = list(audit.calibration_results(cases, transport, budget=2, batch_size=4, production_scaffold=True))
    assert rows[0][1]["code"] == "SYMBOLICALLY_RESOLVED"
    assert rows[0][1]["expected_agreement"] == "MISMATCH"
    assert rows[-1][2:] == (2, 1)
    assert len(network) == 1


def test_batch_foreign_cardinality_is_error_for_every_requested_cell():
    class Malformed:
        def prepare(self, items):
            pass

        def callable_batch(self, items):
            return ('{"WANT":0}',)

    rows = list(audit.calibration_results(batch_cases(), Malformed(), budget=3, batch_size=4))
    assert all(row[1]["reason"] == "INVALID_BATCH_RESULT_CARDINALITY" for row in rows)
    assert all("value" not in row[1] for row in rows)
    assert rows[-1][2:] == (3, 1)
