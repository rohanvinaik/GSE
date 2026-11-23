"""One-cell, typed model completion after symbolic closure.

The model receives JSON data and a generation schema, never an English task.
Its answer is a proposed assertion: the symbolic engine still decides whether
the enlarged evidence set is consistent. Neither failure nor abstention is zero.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from GSE.curation.lexicon_builder.engine import Assertion, DomainRestriction, Relation, Resolution
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.resolution import resolve_dictionary

REQUEST_FORMAT = "gse.bank-request/2"
LEGACY_REQUEST_FORMAT = "gse.bank-request/1"


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
    scaffold: dict | None = None,
    request_format: str = REQUEST_FORMAT,
) -> dict:
    payload = {
        "format": request_format,
        "entry_id": entry_id,
        "definition": _definition_payload(definition, entry_id),
        "bank": bank,
        "allowed_values": list(allowed_values),
        "known": _json_copy(known),
        "observations": _json_copy(observations),
        "fill": {bank: None},
    }
    if request_format == REQUEST_FORMAT:
        payload["scaffold"] = _json_copy(scaffold)
    return payload


def _scaffold(
    resolution: Resolution, relations: tuple[Relation, ...], context: dict[str, str] | None, bank: str
) -> dict:
    """Snapshot the actual closure, retaining rule dispositions and proof data.

    All domains and proofs are context, not requested output. Approved tables
    are preserved even when skipped or locally excepted; only ACTIVE tables
    constrain this definition. Candidate tables never become model authority.
    """
    if type(relations) is not tuple or any(not isinstance(rule, Relation) for rule in relations):
        raise ValueError("invalid_request_relations")
    context = {} if context is None else context
    if type(context) is not dict or any(type(k) is not str or type(v) is not str for k, v in context.items()):
        raise ValueError("invalid_request_context")
    by_id = {}
    for rule in relations:
        rule.__post_init__()
        if rule.rule_id in by_id or not set(rule.banks + rule.absent_evidence) <= resolution.domains.keys():
            raise ValueError("invalid_request_relations")
        by_id[rule.rule_id] = rule
    active, excepted, skipped, referenced = set(), set(), {}, set()
    for receipt in resolution.trace:
        ids = set(receipt.get("rule_ids", ()))
        if "rule_id" in receipt:
            ids.add(receipt["rule_id"])
        referenced.update(ids)
        if receipt["kind"] in {"JOINT_CHECK", "SOLVER_LIMIT"}:
            active.update(ids)
        elif receipt["kind"] == "CONDITIONAL_EXCEPTION":
            excepted.update(ids)
        elif receipt["kind"] == "RELATION_SKIPPED":
            skipped[receipt["rule_id"]] = receipt["reason"]
        elif receipt["kind"] == "EVIDENCE_GUARD" and receipt["status"] == "BLOCKED":
            skipped[receipt["rule_id"]] = receipt["reason"]
    if not referenced <= by_id.keys():
        raise ValueError("missing_request_relation_context")
    connected = {bank}
    approved = tuple(rule for rule in relations if rule.approved)
    while True:
        expanded = connected | {
            name
            for rule in approved
            if connected.intersection(rule.banks + rule.absent_evidence)
            for name in rule.banks + rule.absent_evidence
        }
        if expanded == connected:
            break
        connected = expanded
    records = []
    for rule in sorted(approved, key=lambda item: item.rule_id):
        if rule.rule_id in excepted:
            disposition, reason = "EXCEPTED_FOR_THIS_DEFINITION", "CONDITIONAL_EXCEPTION"
        elif rule.rule_id in skipped:
            disposition, reason = "BLOCKED", skipped[rule.rule_id]
        elif rule.rule_id in active:
            disposition, reason = "ACTIVE", "SYMBOLIC_CLOSURE"
        else:
            raise ValueError("missing_request_rule_proof")
        guard_matches = all(context.get(key) == value for key, value in rule.guards)
        if (disposition == "ACTIVE" and not guard_matches) or (reason == "GUARD_MISMATCH" and guard_matches):
            raise ValueError("inconsistent_request_guard_context")
        records.append(
            {
                **asdict(rule),
                "disposition": disposition,
                "reason": reason,
                "requested_component": bool(connected.intersection(rule.banks)),
            }
        )
    return _json_copy(
        {
            "format": "gse.symbolic-scaffold/1",
            "context": dict(sorted(context.items())),
            "domains": {name: sorted(values) for name, values in sorted(resolution.domains.items())},
            "approved_relations": records,
            "proof_trace": resolution.trace,
            "relation_semantics": "ONLY_ACTIVE_TABLES_CONSTRAIN_THIS_DEFINITION",
            "proof_semantics": "SYMBOLIC_JUSTIFICATION_NOT_ADDITIONAL_MODEL_OUTPUT",
        }
    )


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
    scaffold: dict | None = None
    request_format: str = REQUEST_FORMAT

    def payload(self) -> dict:
        """Return independent JSON data; mutating it cannot alter the request."""
        return _request_payload(
            self.entry_id,
            self.bank,
            self.allowed_values,
            self.known,
            self.observations,
            self.definition,
            self.scaffold,
            self.request_format,
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
    relations: tuple[Relation, ...] = (),
    context: dict[str, str] | None = None,
    request_format: str = REQUEST_FORMAT,
) -> BankRequest:
    """Build a typed request only for an unresolved, nonconflicted coordinate."""
    if type(entry_id) is not str or not entry_id:
        raise ValueError("invalid_entry_id")
    _definition_payload(definition, entry_id)
    if request_format not in {REQUEST_FORMAT, LEGACY_REQUEST_FORMAT}:
        raise ValueError("unsupported_request_format")
    if type(bank) is not str or not bank or bank not in resolution.domains:
        raise ValueError("unknown_bank")
    if resolution.code == "CONFLICT":
        raise ValueError("conflicted_resolution")
    if resolution.code not in {"PARTIAL", "RESOLVED"}:
        raise ValueError("invalid_resolution_code")
    domain = resolution.domains[bank]
    for name, values in resolution.domains.items():
        if (
            type(name) is not str
            or not name
            or type(values) is not frozenset
            or not values
            or any(type(value) is not int or value not in (-1, 0, 1) for value in values)
        ):
            raise ValueError("invalid_domain")
    if bank in resolution.assignments or len(domain) == 1:
        raise ValueError("already_assigned")
    for name, value in resolution.assignments.items():
        if type(name) is not str or type(value) is not int or value not in (-1, 0, 1):
            raise ValueError("invalid_known_assignment")
        if name not in resolution.domains or resolution.domains[name] != frozenset({value}):
            raise ValueError("inconsistent_known_assignment")
    if set(resolution.assignments) != {name for name, values in resolution.domains.items() if len(values) == 1}:
        raise ValueError("incomplete_known_assignments")
    if type(observations) is not tuple or any(type(item) is not dict for item in observations):
        raise ValueError("invalid_observations")
    allowed = tuple(sorted(domain))
    known = dict(sorted(resolution.assignments.items()))
    copied = tuple(_json_copy(observations))
    scaffold = _scaffold(resolution, relations, context, bank) if request_format == REQUEST_FORMAT else None
    payload = _request_payload(entry_id, bank, allowed, known, copied, definition, scaffold, request_format)
    return BankRequest(
        entry_id, bank, allowed, known, copied, _request_id(payload), definition, scaffold, request_format
    )


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
    domain_restrictions: tuple[DomainRestriction, ...] = (),
) -> Completion:
    """Validate freshness, obtain one ruling, then propagate before admitting it.

    Inputs are never mutated. Invalid caller-supplied engine inputs raise the
    engine's ValueError rather than being mislabeled as a model/network failure.
    """
    current = resolve_dictionary(
        banks, assertions, relations, context, evidence_banks=evidence_banks, domain_restrictions=domain_restrictions
    )
    try:
        fresh = build_request(
            request.entry_id,
            request.bank,
            current,
            request.observations,
            definition=request.definition,
            relations=relations,
            context=context,
            request_format=request.request_format,
        )
        same = fresh.request_id == request.request_id and _request_id(request.payload()) == request.request_id
    except ValueError as exc:
        return Completion("STALE_REQUEST", None, current, {"reason": str(exc)})
    if not same:
        return Completion("STALE_REQUEST", None, current, {"reason": "changed_request_state"})

    try:
        raw = transport(fresh.payload(), fresh.output_schema())
    except Exception as exc:
        details = {"error_type": type(exc).__name__}
        if isinstance(exc, ModelTransportError):
            details["reason"] = exc.code
        return Completion("TRANSPORT_ERROR", None, current, details)
    try:
        value = _read_value(raw, fresh)
    except (ValueError, TypeError, RecursionError) as exc:
        return Completion("INVALID_OUTPUT", None, current, {"reason": str(exc)})
    if value is None:
        return Completion("ABSTAINED", None, current, {"request_id": fresh.request_id})

    from .scope_admission import model_scope_admission

    scope = model_scope_admission(fresh.entry_id, fresh.bank, value, fresh.observations)
    if scope["code"] == "SCOPE_UNJUSTIFIED":
        return Completion("SCOPE_UNJUSTIFIED", None, current, {"request_id": fresh.request_id, **scope})

    model = getattr(transport, "identity", getattr(transport, "model", "typed-residual"))
    if type(model) is not str or not model:
        model = "typed-residual"
    assertion = Assertion(fresh.bank, value, f"model:{model}", fresh.request_id, "model")
    resolved = resolve_dictionary(
        banks,
        assertions + (assertion,),
        relations,
        context,
        evidence_banks=evidence_banks,
        domain_restrictions=domain_restrictions,
    )
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


class ModelTransportError(ValueError):
    """A named transport refusal without request contents or endpoint secrets."""

    def __init__(self, code: str):
        if code not in {
            "MODEL_CONTEXT_EXCEEDED",
            "MODEL_IDENTITY_NOT_PINNED",
            "MODEL_IDENTITY_CHANGED",
            "MODEL_IDENTITY_NOT_FOUND_OR_AMBIGUOUS",
            "INVALID_MODEL_DIGEST",
            "INVALID_MODEL_IDENTITY_RESPONSE",
            "INVALID_OLLAMA_RESPONSE",
            "INCOMPLETE_MODEL_OUTPUT",
            "MODEL_TIMEOUT",
            "MODEL_HTTP_ERROR",
            "MODEL_CONNECTION_ERROR",
            "INVALID_MODEL_INPUT",
            "BATCH_INPUT_TOO_LARGE",
            "BATCH_ITEM_LIMIT_EXCEEDED",
            "BATCH_OUTPUT_BUDGET_EXCEEDED",
            "BATCH_DUPLICATE_REQUEST",
            "BATCH_DEPENDENT_REQUESTS",
            "BATCH_CONFIGURATION_CHANGED",
            "BATCH_DUPLICATE_OUTPUT_FIELD",
            "BATCH_MISSING_OUTPUT_ID",
            "BATCH_EXTRA_OUTPUT_ID",
            "BATCH_INVALID_OUTPUT",
        }:
            raise ValueError("invalid_transport_error_code")
        self.code = code
        super().__init__(code)


class OllamaTransport:
    """Explicit local model selection with typed input and constrained generation."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 120,
        *,
        context_tokens: int = 32768,
        thinking: bool = True,
        output_tokens: int | None = None,
    ):
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
        if type(context_tokens) is not int or context_tokens < 2048:
            raise ValueError("invalid_context_tokens")
        self.context_tokens = context_tokens
        if type(thinking) is not bool:
            raise ValueError("invalid_thinking_mode")
        self.thinking = thinking
        self.output_tokens = (1024 if thinking else 128) if output_tokens is None else output_tokens
        if (
            type(self.output_tokens) is not int
            or not 1 <= self.output_tokens <= 32768
            or self.output_tokens + 1024 >= context_tokens
        ):
            raise ValueError("invalid_output_tokens")
        from .model_protocol import protocol_contract

        digest = _request_id(
            {
                "protocol": protocol_contract(),
                "thinking": thinking,
                "context_tokens": context_tokens,
                "output_tokens": self.output_tokens,
                "temperature": 0,
            }
        )
        self._protocol_digest = digest
        self.model_digest: str | None = None
        self.identity = f"{model}@{digest}"

    def _request_json(self, request: Request, malformed_code: str) -> Any:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelTransportError("MODEL_HTTP_ERROR") from exc
        except TimeoutError as exc:
            raise ModelTransportError("MODEL_TIMEOUT") from exc
        except URLError as exc:
            code = "MODEL_TIMEOUT" if isinstance(exc.reason, TimeoutError) else "MODEL_CONNECTION_ERROR"
            raise ModelTransportError(code) from exc
        except (ValueError, UnicodeError) as exc:
            raise ModelTransportError(malformed_code) from exc

    def _installed_digest(self) -> str:
        request = Request(f"{self.base_url}/api/tags", method="GET")
        envelope = self._request_json(request, "INVALID_MODEL_IDENTITY_RESPONSE")
        if type(envelope) is not dict or type(envelope.get("models")) is not list:
            raise ModelTransportError("INVALID_MODEL_IDENTITY_RESPONSE")
        matches = [item for item in envelope["models"] if isinstance(item, dict) and item.get("name") == self.model]
        if len(matches) != 1:
            raise ModelTransportError("MODEL_IDENTITY_NOT_FOUND_OR_AMBIGUOUS")
        digest = matches[0].get("digest")
        if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ModelTransportError("INVALID_MODEL_DIGEST")
        return digest

    def pin(self) -> dict[str, str]:
        """Resolve the installed artifact explicitly; never repin a changed tag."""
        digest = self._installed_digest()
        if self.model_digest is not None and digest != self.model_digest:
            raise ModelTransportError("MODEL_IDENTITY_CHANGED")
        self.model_digest = digest
        self.identity = f"{self.model}#{digest}@{self._protocol_digest}"
        return {"model": self.model, "digest": digest}

    def _verify_pin(self) -> None:
        if self.model_digest is None:
            raise ModelTransportError("MODEL_IDENTITY_NOT_PINNED")
        if self._installed_digest() != self.model_digest:
            raise ModelTransportError("MODEL_IDENTITY_CHANGED")

    def __call__(self, payload: dict, schema: dict) -> str:
        from .model_protocol import model_input

        try:
            prompt = _canonical_json(model_input(_json_copy(payload)))
        except ValueError as exc:
            raise ModelTransportError("INVALID_MODEL_INPUT") from exc
        # UTF-8 byte count is a conservative bound for byte-backed tokenizers.
        # Reserve template/output space; refusal is preferable to silent loss
        # of a contradictory observation near the start of a long request.
        if len(prompt.encode("utf-8")) > self.context_tokens - self.output_tokens - 1024:
            raise ModelTransportError("MODEL_CONTEXT_EXCEEDED")
        self._verify_pin()
        body = {
            "model": self.model,
            "prompt": prompt,
            "format": _json_copy(schema),
            "stream": False,
            "think": self.thinking,
            "options": {"temperature": 0, "num_predict": self.output_tokens, "num_ctx": self.context_tokens},
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=_canonical_json(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        envelope = self._request_json(request, "INVALID_OLLAMA_RESPONSE")
        self._verify_pin()
        if type(envelope) is not dict or type(envelope.get("response")) is not str:
            raise ModelTransportError("INVALID_OLLAMA_RESPONSE")
        if envelope.get("done_reason") == "length":
            raise ModelTransportError("INCOMPLETE_MODEL_OUTPUT")
        from GSE.curation.llm.ollama_client import register_model

        register_model(self.model, self.base_url)
        return envelope["response"]
