"""One-cell, typed model completion after symbolic closure.

The model receives JSON data and a generation schema, never an English task.
Its answer is a proposed assertion: the symbolic engine still decides whether
the enlarged evidence set is consistent. Neither failure nor abstention is zero.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from gse.curation.lexicon_builder.engine import Assertion, Relation, Resolution
from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.resolution import resolve_dictionary


def _json_copy(value: Any) -> Any:
    """Copy JSON data without accepting non-finite numbers or foreign objects."""

    def check(item: Any) -> None:
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list or type(item) is tuple:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise ValueError("non_json_data")

    check(value)
    return json.loads(json.dumps(value, allow_nan=False))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _definition_payload(definition: Definition, entry_id: str) -> dict[str, str]:
    """Require the actual lexical identity and meaning, never an opaque ID alone."""
    if not isinstance(definition, Definition):
        raise ValueError("invalid_definition_context")
    result = {name: getattr(definition, name) for name in ("entry_id", "lemma", "pos", "definition")}
    if any(type(value) is not str or not value.strip() for value in result.values()):
        raise ValueError("invalid_definition_context")
    if result["entry_id"] != entry_id:
        raise ValueError("definition_identity_mismatch")
    return result


def _request_payload(
    entry_id: str,
    bank: str,
    allowed_values: tuple[int, ...],
    known: dict[str, int],
    observations: tuple[dict, ...],
    definition: Definition,
) -> dict:
    return {
        "format": "gse.bank-request/1",
        "entry_id": entry_id,
        "definition": _definition_payload(definition, entry_id),
        "bank": bank,
        "allowed_values": list(allowed_values),
        "known": _json_copy(known),
        "observations": _json_copy(observations),
        "fill": {bank: None},
    }


def _request_id(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BankRequest:
    entry_id: str
    bank: str
    allowed_values: tuple[int, ...]
    known: dict[str, int]
    observations: tuple[dict, ...]
    request_id: str
    definition: Definition

    def payload(self) -> dict:
        """Return independent JSON data; mutating it cannot alter the request."""
        return _request_payload(
            self.entry_id, self.bank, self.allowed_values, self.known, self.observations, self.definition
        )

    def output_schema(self) -> dict:
        """Restrict generation to the single requested bank or explicit null."""
        return {
            "type": "object",
            "properties": {
                self.bank: {"type": ["integer", "null"], "enum": [*self.allowed_values, None]},
            },
            "required": [self.bank],
            "additionalProperties": False,
        }


@dataclass(frozen=True)
class Completion:
    code: str
    assertion: Assertion | None
    resolution: Resolution | None
    details: dict


def build_request(
    entry_id: str,
    bank: str,
    resolution: Resolution,
    observations: tuple[dict, ...],
    *,
    definition: Definition,
) -> BankRequest:
    """Build a typed request only for an unresolved, nonconflicted coordinate."""
    if type(entry_id) is not str or not entry_id:
        raise ValueError("invalid_entry_id")
    _definition_payload(definition, entry_id)
    if type(bank) is not str or not bank or bank not in resolution.domains:
        raise ValueError("unknown_bank")
    if resolution.code == "CONFLICT":
        raise ValueError("conflicted_resolution")
    if resolution.code not in {"PARTIAL", "RESOLVED"}:
        raise ValueError("invalid_resolution_code")
    domain = resolution.domains[bank]
    if not domain or any(type(value) is not int or value not in (-1, 0, 1) for value in domain):
        raise ValueError("invalid_domain")
    if bank in resolution.assignments or len(domain) == 1:
        raise ValueError("already_assigned")
    for name, value in resolution.assignments.items():
        if type(name) is not str or type(value) is not int or value not in (-1, 0, 1):
            raise ValueError("invalid_known_assignment")
        if name not in resolution.domains or resolution.domains[name] != frozenset({value}):
            raise ValueError("inconsistent_known_assignment")
    if type(observations) is not tuple or any(type(item) is not dict for item in observations):
        raise ValueError("invalid_observations")
    allowed = tuple(sorted(domain))
    known = dict(sorted(resolution.assignments.items()))
    copied = tuple(_json_copy(observations))
    payload = _request_payload(entry_id, bank, allowed, known, copied, definition)
    return BankRequest(entry_id, bank, allowed, known, copied, _request_id(payload), definition)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _read_value(raw: str, request: BankRequest) -> int | None:
    if type(raw) is not str:
        raise ValueError("response_not_string")
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if type(value) is not dict or set(value) != {request.bank}:
        raise ValueError("unexpected_output_fields")
    answer = value[request.bank]
    if answer is None:
        return None
    if type(answer) is not int or answer not in request.allowed_values:
        raise ValueError("value_outside_domain")
    return answer


def complete_bank(
    request: BankRequest,
    banks: tuple[str, ...],
    assertions: tuple[Assertion, ...],
    relations: tuple[Relation, ...],
    transport: Callable[[dict, dict], str],
    context: dict[str, str] | None = None,
    *,
    evidence_banks: tuple[str, ...] = (),
) -> Completion:
    """Validate freshness, obtain one ruling, then propagate before admitting it.

    Inputs are never mutated. Invalid caller-supplied engine inputs raise the
    engine's ValueError rather than being mislabeled as a model/network failure.
    """
    current = resolve_dictionary(banks, assertions, relations, context, evidence_banks=evidence_banks)
    try:
        fresh = build_request(
            request.entry_id, request.bank, current, request.observations, definition=request.definition
        )
        same = fresh.request_id == request.request_id and _request_id(request.payload()) == request.request_id
    except ValueError as exc:
        return Completion("STALE_REQUEST", None, current, {"reason": str(exc)})
    if not same:
        return Completion("STALE_REQUEST", None, current, {"reason": "changed_request_state"})

    try:
        raw = transport(fresh.payload(), fresh.output_schema())
    except Exception as exc:
        return Completion("TRANSPORT_ERROR", None, current, {"error_type": type(exc).__name__})
    try:
        value = _read_value(raw, fresh)
    except (ValueError, TypeError, RecursionError) as exc:
        return Completion("INVALID_OUTPUT", None, current, {"reason": str(exc)})
    if value is None:
        return Completion("ABSTAINED", None, current, {"request_id": fresh.request_id})

    model = getattr(transport, "model", "typed-residual")
    if type(model) is not str or not model:
        model = "typed-residual"
    assertion = Assertion(fresh.bank, value, f"model:{model}", fresh.request_id, "model")
    resolved = resolve_dictionary(banks, assertions + (assertion,), relations, context, evidence_banks=evidence_banks)
    previous_exceptions = {
        rule_id
        for record in current.trace
        if record["kind"] == "CONDITIONAL_EXCEPTION"
        for rule_id in record["rule_ids"]
    }
    new_exceptions = tuple(
        record
        for record in resolved.trace
        if record["kind"] == "CONDITIONAL_EXCEPTION" and set(record["rule_ids"]) - previous_exceptions
    )
    changed_known = {
        bank: {"before": value, "after": resolved.assignments.get(bank)}
        for bank, value in current.assignments.items()
        if resolved.assignments.get(bank) != value
    }
    if resolved.code == "CONFLICT" or new_exceptions or changed_known:
        return Completion(
            "CONTRADICTION",
            None,
            current,
            {
                "request_id": fresh.request_id,
                "conflicts": resolved.conflicts
                or tuple(conflict for record in new_exceptions for conflict in record["conflicts"]),
                "conditional_exceptions": new_exceptions,
                "changed_known": changed_known,
            },
        )
    return Completion("ASSIGNED", assertion, resolved, {"request_id": fresh.request_id})


class OllamaTransport:
    """Explicit local model selection with typed input and constrained generation."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout: float = 60):
        if type(model) is not str or not model.strip():
            raise ValueError("model_required")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid_timeout")
        if type(base_url) is not str:
            raise ValueError("invalid_base_url")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("invalid_base_url")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    def __call__(self, payload: dict, schema: dict) -> str:
        body = {
            "model": self.model,
            "prompt": _canonical_json(_json_copy(payload)),
            "format": _json_copy(schema),
            "stream": False,
            "raw": True,
            "options": {"temperature": 0, "num_predict": 128},
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=_canonical_json(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        if type(envelope) is not dict or type(envelope.get("response")) is not str:
            raise ValueError("invalid_ollama_response")
        from gse.curation.llm.ollama_client import register_model

        register_model(self.model, self.base_url)
        return envelope["response"]
