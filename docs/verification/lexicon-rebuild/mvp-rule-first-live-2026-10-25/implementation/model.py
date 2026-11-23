"""Typed local selection with the same JSON schema sent to the decoder.

Both messages are structured records. No gloss, prose question, repair prompt,
free-form rationale or unrestricted vector generation is sent to the model.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass

DEFAULT_MODEL = "gemma4:e4b-it-q4_K_M"


def selection_status(options: dict[str, list[str]], answer: dict) -> str:
    """Validate the closed selection contract, independently of the backend.

    MUST-NOT: accepting extra keys, missing keys or values outside the domains.
    """
    if not options:
        return "EMPTY_DECISION"
    if set(answer) != set(options):
        return "FIELD_MISMATCH"
    if any(not isinstance(answer[key], str) or answer[key] not in values for key, values in options.items()):
        return "ILLEGAL_VALUE"
    return "VALID_SELECTION"


@dataclass
class OllamaSelector:
    model: str = DEFAULT_MODEL
    endpoint: str = "http://localhost:11434"
    timeout: int = 180

    def _request(self, route: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        request = urllib.request.Request(self.endpoint + route, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def identity(self) -> dict:
        matches = [m for m in self._request("/api/tags")["models"] if m["name"] == self.model]
        if len(matches) != 1:
            raise ValueError(f"configured local model is not installed: {self.model}")
        return matches[0]

    def select(self, payload: dict, options: dict[str, list[str]]) -> dict:
        if not options or any(not values or len(set(values)) != len(values) for values in options.values()):
            raise ValueError("decision fields require nonempty distinct options")
        schema = {
            "type": "object",
            "properties": {key: {"type": "string", "enum": values} for key, values in options.items()},
            "required": list(options),
            "additionalProperties": False,
        }
        identity = self.identity()
        contract = {
            "operation": "LEXICAL_DEFINITION_TYPED_SELECTION",
            "scope": "TARGET_READING_OWN_DEFINITION_ONLY",
            "association_fields": "OBSERVATIONS_NOT_COMPONENTS",
            "empty": "DEFINITION_DOES_NOT_ADDRESS_THIS_COORDINATE",
            "+1": "DEFINITIONAL_COMPONENT_PRESENT",
            "0": "EXPLICIT_ABSENCE_IN_APPLICABLE_UNPAIRED_DOMAIN_OR_NEITHER_BIPOLAR_POLE",
            "-1": "DEFINITIONAL_OPPOSITE_POLE_ONLY",
            "selection_schema": schema,
        }
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": json.dumps(contract, sort_keys=True)},
                {"role": "user", "content": json.dumps(payload, sort_keys=True, allow_nan=False)},
            ],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "5m",
            "options": {"temperature": 0, "seed": 17, "num_ctx": 8192, "num_predict": 256},
        }
        response = self._request("/api/chat", request)
        answer = json.loads(response["message"]["content"])
        if not isinstance(answer, dict) or selection_status(options, answer) != "VALID_SELECTION":
            raise ValueError("local decoder violated typed selection schema")
        request_hash = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        return {
            "request_sha256": request_hash,
            "model": identity,
            "request": request,
            "answer": answer,
            "done_reason": response.get("done_reason"),
            "eval_count": response.get("eval_count"),
        }
