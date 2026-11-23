"""Independent typed questions batch without weakening per-cell admission."""

import copy
import json
from typing import Any

import pytest

from GSE.curation.lexicon_builder.engine import DomainRestriction, propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.model_batch import FORMAT, OllamaBatchTransport
from GSE.curation.lexicon_builder.residual import ModelTransportError, OllamaTransport, build_request, complete_bank


def _request(entry_id, bank="WANT", *, allowed=None, gloss="Fixture definition."):
    restrictions = () if allowed is None else (DomainRestriction(bank, allowed, "fixture", entry_id, "dictionary"),)
    resolution = propagate(BANKS, (), (), domain_restrictions=restrictions)
    return build_request(entry_id, bank, resolution, (), definition=Definition(entry_id, entry_id, "noun", gloss))


def _items(*requests):
    return tuple((request.payload(), request.output_schema()) for request in requests)


class FakeServer:
    def __init__(self, model):
        self.model = model
        self.digest = "a" * 64
        self.calls = []
        self.answer = None
        self.done = True
        self.done_reason = "stop"
        self.change_on_generate = False
        self.metrics = {}

    def request(self, request, malformed_code):
        self.calls.append(request)
        if request.method == "GET":
            return {"models": [{"name": self.model, "digest": self.digest}]}
        body = json.loads(request.data)
        prompt = json.loads(body["prompt"])
        output = (
            self.answer(prompt)
            if self.answer
            else {item["slot"]: {item["input"]["bank"]: 0} for item in reversed(prompt["items"])}
        )
        if self.change_on_generate:
            self.digest = "b" * 64
        return {
            "response": output if isinstance(output, str) else json.dumps(output),
            "done": self.done,
            "done_reason": self.done_reason,
            **self.metrics,
        }


@pytest.fixture
def transport(monkeypatch):
    base = OllamaTransport("fixture:batch", thinking=False, output_tokens=1024)
    server = FakeServer(base.model)
    monkeypatch.setattr(base, "_request_json", server.request)
    monkeypatch.setattr("GSE.curation.llm.ollama_client.register_model", lambda *args: None)
    batch = OllamaBatchTransport(base)
    batch.pin()
    server.calls.clear()
    return batch, server


def test_batch_shares_protocol_and_aligns_reordered_answers(transport):
    batch, server = transport
    requests = (_request("first"), _request("second", "SEE"))
    items = _items(*requests)
    original = copy.deepcopy(items)
    prepared = batch.prepare(items)
    assert server.calls == []
    assert prepared.request_ids == tuple(request.request_id for request in requests)
    assert prepared.slots == ("q0", "q1")
    assert prepared.input_bytes == len(prepared.body) == prepared.input_token_bound
    body = json.loads(prepared.body)
    prompt = json.loads(body["prompt"])
    assert prompt["format"] == FORMAT
    assert prompt["shared_protocol"]["examples"]
    assert all("examples" not in item for item in prompt["items"])
    assert [item["input"]["definition"] for item in prompt["items"]] == [p[0]["definition"] for p in items]
    assert [item["request_id"] for item in prompt["items"]] == list(prepared.request_ids)
    assert [item["slot"] for item in prompt["items"]] == list(prepared.slots)
    assert body["format"]["required"] == list(prepared.slots)
    assert body["format"]["additionalProperties"] is False
    assert body["options"] == {"num_ctx": 32768, "num_predict": 1024, "temperature": 0}
    assert batch.callable_batch(items) == ('{"WANT":0}', '{"SEE":0}')
    assert [call.method for call in server.calls] == ["GET", "POST", "GET"]
    assert items == original


def test_null_and_zero_remain_different_through_single_bank_acceptance(transport):
    batch, server = transport
    requests = (_request("first"), _request("second"))
    server.answer = lambda prompt: {
        item["slot"]: {item["input"]["bank"]: value} for item, value in zip(prompt["items"], (0, None))
    }
    answers = batch.callable_batch(_items(*requests))
    results = []
    for request, answer in zip(requests, answers):

        class Replay:
            identity = batch.identity

            def __call__(self, payload, schema, raw=answer):
                return raw

        results.append(complete_bank(request, BANKS, (), (), Replay()))
    assert results[0].code == "ASSIGNED"
    assert results[0].assertion is not None
    assert results[0].assertion.value == 0
    assert results[1].code == "ABSTAINED"
    assert results[1].assertion is None
    assert batch.identity in results[0].assertion.source


def test_single_callable_api_uses_same_pinned_batch_protocol(transport):
    batch, server = transport
    result = complete_bank(_request("single"), BANKS, (), (), batch)
    assert result.code == "ASSIGNED"
    assert result.assertion is not None
    assert result.assertion.source == "model:" + batch.identity
    assert len(json.loads(json.loads(server.calls[1].data)["prompt"])["items"]) == 1


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing", "BATCH_MISSING_OUTPUT_ID"),
        ("extra", "BATCH_EXTRA_OUTPUT_ID"),
        ("duplicate", "BATCH_DUPLICATE_OUTPUT_FIELD"),
        ("extra_bank", "BATCH_INVALID_OUTPUT"),
        ("wrong_bank", "BATCH_INVALID_OUTPUT"),
        ("boolean", "BATCH_INVALID_OUTPUT"),
        ("string", "BATCH_INVALID_OUTPUT"),
        ("float", "BATCH_INVALID_OUTPUT"),
        ("markdown", "BATCH_INVALID_OUTPUT"),
        ("array", "BATCH_INVALID_OUTPUT"),
        ("full_hash", "BATCH_EXTRA_OUTPUT_ID"),
    ],
)
def test_malformed_batch_never_releases_partial_answers(transport, case, code):
    batch, server = transport
    requests = (_request("first"), _request("second"))

    def answer(prompt):
        ids = [item["slot"] for item in prompt["items"]]
        result: dict[str, dict[str, Any]] = {rid: {"WANT": 0} for rid in ids}
        if case == "missing":
            result.pop(ids[1])
        elif case == "extra":
            result["unrequested-id"] = {"WANT": 0}
        elif case == "duplicate":
            return '{"' + ids[0] + '":{"WANT":0},"' + ids[0] + '":{"WANT":1},"' + ids[1] + '":{"WANT":0}}'
        elif case == "extra_bank":
            result[ids[1]]["SEE"] = 1
        elif case == "wrong_bank":
            result[ids[1]] = {"SEE": 1}
        elif case in {"boolean", "string", "float"}:
            result[ids[1]]["WANT"] = {"boolean": True, "string": "0", "float": 0.0}[case]
        elif case == "markdown":
            return "```json\n" + json.dumps(result) + "\n```"
        elif case == "array":
            return "[]"
        elif case == "full_hash":
            result[prompt["items"][1]["request_id"]] = result.pop(ids[1])
        return result

    server.answer = answer
    with pytest.raises(ModelTransportError, match=f"^{code}$"):
        batch.callable_batch(_items(*requests))


def test_answer_cannot_escape_remaining_domain(transport):
    batch, server = transport
    request = _request("limited", allowed=(-1, 0))
    server.answer = lambda prompt: {prompt["items"][0]["slot"]: {"WANT": 1}}
    with pytest.raises(ModelTransportError, match="BATCH_INVALID_OUTPUT"):
        batch.callable_batch(_items(request))


@pytest.mark.parametrize(
    "case,code",
    [
        ("empty", "INVALID_MODEL_INPUT"),
        ("duplicate", "BATCH_DUPLICATE_REQUEST"),
        ("same_definition", "BATCH_DEPENDENT_REQUESTS"),
        ("schema", "INVALID_MODEL_INPUT"),
        ("items", "BATCH_ITEM_LIMIT_EXCEEDED"),
        ("bytes", "BATCH_INPUT_TOO_LARGE"),
        ("tokens", "BATCH_INPUT_TOO_LARGE"),
        ("output", "BATCH_OUTPUT_BUDGET_EXCEEDED"),
    ],
)
def test_prepare_refuses_without_any_http_or_truncation(transport, case, code):
    batch, server = transport
    items = _items(_request("first"), _request("second"))
    if case == "empty":
        items = ()
    elif case == "duplicate":
        items = (items[0], items[0])
    elif case == "same_definition":
        items = _items(_request("same", "WANT"), _request("same", "SEE"))
    elif case == "schema":
        items[0][1]["additionalProperties"] = True
    elif case == "items":
        batch = OllamaBatchTransport(batch.transport, max_items=1)
    elif case == "bytes":
        batch = OllamaBatchTransport(batch.transport, max_input_bytes=1)
    elif case == "tokens":
        items = _items(_request("large", gloss="é" * 40000))
    elif case == "output":
        base = OllamaTransport("fixture:batch", thinking=False, output_tokens=128)
        batch = OllamaBatchTransport(base)
        items = _items(*(_request(f"definition:{number}") for number in range(8)))
    with pytest.raises(ModelTransportError, match=f"^{code}$"):
        batch.prepare(items)
    assert server.calls == []


def test_exact_byte_boundary_and_budget_identity_are_explicit(transport):
    batch, server = transport
    items = _items(_request("first"))
    bound = batch.prepare(items).input_bytes
    exact = OllamaBatchTransport(batch.transport, max_input_bytes=bound)
    short = OllamaBatchTransport(batch.transport, max_input_bytes=bound - 1)
    assert exact.prepare(items).input_bytes == bound
    assert exact.identity != short.identity != batch.identity
    with pytest.raises(ModelTransportError, match="BATCH_INPUT_TOO_LARGE"):
        short.prepare(items)
    assert server.calls == []


def test_pin_is_required_and_changed_model_cannot_release_answers(transport):
    batch, server = transport
    server.change_on_generate = True
    with pytest.raises(ModelTransportError, match="MODEL_IDENTITY_CHANGED"):
        batch.callable_batch(_items(_request("first")))
    unpinned = OllamaBatchTransport(OllamaTransport("unavailable:fixture", thinking=False, output_tokens=1024))
    with pytest.raises(ModelTransportError, match="MODEL_IDENTITY_NOT_PINNED"):
        unpinned.callable_batch(_items(_request("first")))


@pytest.mark.parametrize("case", ["length", "not_done", "configuration"])
def test_incomplete_generation_or_changed_configuration_refuses(transport, case):
    batch, server = transport
    if case == "length":
        server.done_reason = "length"
    elif case == "not_done":
        server.done = False
    else:
        batch.transport.output_tokens = 2048
    code = "BATCH_CONFIGURATION_CHANGED" if case == "configuration" else "INCOMPLETE_MODEL_OUTPUT"
    with pytest.raises(ModelTransportError, match=code):
        batch.callable_batch(_items(_request("first")))


def test_metrics_preserve_reported_numbers_without_context_or_invented_fields(transport):
    batch, server = transport
    assert batch.last_metrics is None
    server.metrics = {
        "prompt_eval_count": 123,
        "eval_count": 11,
        "prompt_eval_duration": 12345,
        "eval_duration": 456.5,
        "total_duration": 12999,
        "private_context": "must not be copied",
    }
    items = _items(_request("first"), _request("second"))
    prepared = batch.prepare(items)
    batch.callable_batch(items)
    assert batch.last_metrics == {
        "input_bytes": prepared.input_bytes,
        "item_count": 2,
        "prompt_eval_count": 123,
        "eval_count": 11,
        "prompt_eval_duration": 12345,
        "eval_duration": 456.5,
        "total_duration": 12999,
    }
    server.metrics = {"eval_count": True, "eval_duration": float("inf"), "total_duration": -1}
    batch.callable_batch(items)
    assert batch.last_metrics == {"input_bytes": prepared.input_bytes, "item_count": 2}
    server.done = False
    with pytest.raises(ModelTransportError, match="INCOMPLETE_MODEL_OUTPUT"):
        batch.callable_batch(items)
    assert batch.last_metrics is None
