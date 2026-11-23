"""Bounded independent single-bank questions over the existing pinned transport.

Batching changes only the wire envelope. Each full original request keeps its
own identity, schema, evidence and later symbolic acceptance check. No question
is dropped to fit a budget, and no malformed batch releases partial answers.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from urllib.request import Request

from .model_protocol import model_input, protocol_contract
from .residual import ModelTransportError, OllamaTransport, _canonical_json, _json_copy, _request_id

FORMAT = "gse.lexical-component-batch/2"


def batch_contract() -> dict:
    return {
        "format": FORMAT,
        "item_scope": "DISTINCT_DEFINITION_SINGLE_REQUESTED_BANK",
        "item_relation": "INDEPENDENT_QUESTIONS_NO_CROSS_ITEM_EVIDENCE",
        "output_identity": "FIXED_SLOT_KEYS_BOUND_TO_FULL_REQUEST_SHA256",
        "output_fields": "ONE_REQUESTED_BANK_OBJECT_PER_SLOT",
        "output_completeness": "ALL_SLOTS_EXACTLY_ONCE_NO_EXTRAS",
        "null": "ABSTAINED_NOT_ZERO",
        "acceptance": "SEPARATE_FRESHNESS_AND_SYMBOLIC_CLOSURE_FOR_EACH_ORIGINAL_REQUEST",
        "budget_semantics": "REJECT_OVERSIZE_NEVER_TRUNCATE",
    }


@dataclass(frozen=True)
class PreparedBatch:
    request_ids: tuple[str, ...]
    slots: tuple[str, ...]
    banks: tuple[str, ...]
    allowed_values: tuple[tuple[int, ...], ...]
    body: bytes
    input_bytes: int
    input_token_bound: int
    output_token_bound: int


def _output_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ModelTransportError("BATCH_DUPLICATE_OUTPUT_FIELD")
        result[key] = value
    return result


class OllamaBatchTransport:
    """Reuse an explicitly configured Ollama transport, including its model pin.

    ``prepare`` performs no network calls and is suitable before journaling.
    ``callable_batch`` returns single-bank JSON strings in input order only
    after validating the complete slot-keyed output. Each slot is bound to its
    full request hash in the input. ``__call__`` supports the
    existing one-cell callable contract by sending a one-item batch.
    """

    def __init__(self, transport: OllamaTransport, *, max_items: int = 8, max_input_bytes: int | None = None):
        if not isinstance(transport, OllamaTransport):
            raise ValueError("batch_requires_ollama_transport")
        if type(max_items) is not int or max_items < 1:
            raise ValueError("invalid_batch_item_budget")
        if max_input_bytes is None:
            max_input_bytes = transport.context_tokens - transport.output_tokens - 1024
        if type(max_input_bytes) is not int or max_input_bytes < 1:
            raise ValueError("invalid_batch_byte_budget")
        self.transport = transport
        self.max_items = max_items
        self.max_input_bytes = max_input_bytes
        self.last_metrics: dict[str, int | float] | None = None
        self._configuration = self._current_configuration()
        self._protocol_digest = _request_id(
            {
                "batch": batch_contract(),
                "single_protocol_digest": transport._protocol_digest,
                "configuration": self._configuration,
            }
        )

    @property
    def model(self) -> str:
        return self.transport.model

    @property
    def identity(self) -> str:
        return f"{self.transport.identity}:batch@{self._protocol_digest}"

    def _current_configuration(self) -> dict:
        return {
            "model": self.transport.model,
            "base_url": self.transport.base_url,
            "timeout": self.transport.timeout,
            "context_tokens": self.transport.context_tokens,
            "output_tokens": self.transport.output_tokens,
            "thinking": self.transport.thinking,
            "temperature": 0,
            "single_protocol_digest": self.transport._protocol_digest,
            "max_items": self.max_items,
            "max_input_bytes": self.max_input_bytes,
            "protocol": protocol_contract(),
        }

    def _verify_configuration(self) -> None:
        if self._current_configuration() != self._configuration:
            raise ModelTransportError("BATCH_CONFIGURATION_CHANGED")

    def pin(self) -> dict[str, str]:
        self._verify_configuration()
        return {**self.transport.pin(), "batch_protocol_digest": self._protocol_digest}

    def prepare(self, items: tuple[tuple[dict, dict], ...]) -> PreparedBatch:
        """Validate all questions and budgets without mutation or model access."""
        self._verify_configuration()
        if type(items) is not tuple or not items:
            raise ModelTransportError("INVALID_MODEL_INPUT")
        if len(items) > self.max_items:
            raise ModelTransportError("BATCH_ITEM_LIMIT_EXCEEDED")
        ids, slots, banks, domains, questions, schemas = [], [], [], [], [], {}
        entries = set()
        shared = None
        for item in items:
            if type(item) is not tuple or len(item) != 2:
                raise ModelTransportError("INVALID_MODEL_INPUT")
            try:
                payload, schema = _json_copy(item)
                bank, allowed, entry_id = payload["bank"], payload["allowed_values"], payload["entry_id"]
                if (
                    type(entry_id) is not str
                    or not entry_id.strip()
                    or type(bank) is not str
                    or type(allowed) is not list
                    or len(allowed) not in (2, 3)
                    or any(type(value) is not int or value not in (-1, 0, 1) for value in allowed)
                    or allowed != [value for value in (-1, 0, 1) if value in allowed]
                    or payload.get("fill") != {bank: None}
                ):
                    raise ValueError("invalid_question")
                expected_schema = {
                    "type": "object",
                    "properties": {bank: {"type": ["integer", "null"], "enum": [*allowed, None]}},
                    "required": [bank],
                    "additionalProperties": False,
                }
                if _canonical_json(schema) != _canonical_json(expected_schema):
                    raise ValueError("invalid_single_bank_schema")
                wire = model_input(payload)
                coordinate, data = wire.pop("coordinate"), wire.pop("input")
            except (ValueError, TypeError, KeyError, RecursionError) as exc:
                raise ModelTransportError("INVALID_MODEL_INPUT") from exc
            request_id = _request_id(payload)
            if request_id in ids:
                raise ModelTransportError("BATCH_DUPLICATE_REQUEST")
            if entry_id in entries:
                raise ModelTransportError("BATCH_DEPENDENT_REQUESTS")
            if shared is not None and shared != wire:
                raise ModelTransportError("BATCH_CONFIGURATION_CHANGED")
            shared = wire
            slot = f"q{len(ids)}"
            entries.add(entry_id)
            ids.append(request_id)
            slots.append(slot)
            banks.append(bank)
            domains.append(tuple(allowed))
            schemas[slot] = schema
            questions.append({"slot": slot, "request_id": request_id, "coordinate": coordinate, "input": data})
        prompt = _canonical_json({**batch_contract(), "shared_protocol": shared, "items": questions})
        schema = {"type": "object", "properties": schemas, "required": slots, "additionalProperties": False}
        body = _canonical_json(
            {
                "model": self.transport.model,
                "prompt": prompt,
                "format": schema,
                "stream": False,
                "think": self.transport.thinking,
                "options": {
                    "temperature": 0,
                    "num_predict": self.transport.output_tokens,
                    "num_ctx": self.transport.context_tokens,
                },
            }
        ).encode("utf-8")
        # One token per UTF-8 byte is conservative for the same byte-backed
        # tokenizer assumption as the single-item transport. Include schema and
        # body overhead too; never truncate an observation or silently drop an item.
        input_bytes = len(body)
        if (
            input_bytes > self.max_input_bytes
            or input_bytes + self.transport.output_tokens + 1024 > self.transport.context_tokens
        ):
            raise ModelTransportError("BATCH_INPUT_TOO_LARGE")
        output_bound = len(_canonical_json({slot: {bank: None} for slot, bank in zip(slots, banks)}).encode("utf-8"))
        if output_bound > self.transport.output_tokens:
            raise ModelTransportError("BATCH_OUTPUT_BUDGET_EXCEEDED")
        return PreparedBatch(
            tuple(ids), tuple(slots), tuple(banks), tuple(domains), body, input_bytes, input_bytes, output_bound
        )

    def _answers(self, raw: str, prepared: PreparedBatch) -> tuple[str, ...]:
        if len(raw.encode("utf-8")) > self.transport.output_tokens:
            raise ModelTransportError("BATCH_OUTPUT_BUDGET_EXCEEDED")
        try:
            output = json.loads(raw, object_pairs_hook=_output_object)
        except ModelTransportError:
            raise
        except (ValueError, TypeError, RecursionError) as exc:
            raise ModelTransportError("BATCH_INVALID_OUTPUT") from exc
        if type(output) is not dict:
            raise ModelTransportError("BATCH_INVALID_OUTPUT")
        expected = set(prepared.slots)
        if output.keys() - expected:
            raise ModelTransportError("BATCH_EXTRA_OUTPUT_ID")
        if expected - output.keys():
            raise ModelTransportError("BATCH_MISSING_OUTPUT_ID")
        answers = []
        for slot, bank, allowed in zip(prepared.slots, prepared.banks, prepared.allowed_values):
            item = output[slot]
            if type(item) is not dict or set(item) != {bank}:
                raise ModelTransportError("BATCH_INVALID_OUTPUT")
            value = item[bank]
            if value is not None and (type(value) is not int or value not in allowed):
                raise ModelTransportError("BATCH_INVALID_OUTPUT")
            answers.append(_canonical_json(item))
        return tuple(answers)

    def callable_batch(self, items: tuple[tuple[dict, dict], ...]) -> tuple[str, ...]:
        self.last_metrics = None
        prepared = self.prepare(items)
        self.transport._verify_pin()
        request = Request(
            f"{self.transport.base_url}/api/generate",
            data=prepared.body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        envelope = self.transport._request_json(request, "INVALID_OLLAMA_RESPONSE")
        self.transport._verify_pin()
        self._verify_configuration()
        if type(envelope) is not dict or type(envelope.get("response")) is not str:
            raise ModelTransportError("INVALID_OLLAMA_RESPONSE")
        if envelope.get("done") is not True or envelope.get("done_reason") == "length":
            raise ModelTransportError("INCOMPLETE_MODEL_OUTPUT")
        answers = self._answers(envelope["response"], prepared)
        self.last_metrics = {"input_bytes": prepared.input_bytes, "item_count": len(prepared.request_ids)}
        for key in ("prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration", "total_duration"):
            value = envelope.get(key)
            if type(value) in (int, float) and value >= 0 and math.isfinite(value):
                self.last_metrics[key] = value
        from gse.curation.llm.ollama_client import register_model

        register_model(self.transport.model, self.transport.base_url)
        return answers

    def __call__(self, payload: dict, schema: dict) -> str:
        return self.callable_batch(((payload, schema),))[0]
