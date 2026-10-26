"""Bank-scoped omission accounting and bounded repair, never blanket silence.

Model accounts remain provisional. A named omission needs an explicit legal
repair domain from the reading's rule; otherwise the reading stays partial.
"""

from __future__ import annotations

from gse.lexicon_builder.basis import BANKS, PRIME_TO_BANK
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Law, Observation, Resolution, resolve
from gse.lexicon_builder.model import OllamaSelector, selection_status

BANK_FIELDS = tuple(f"BANK_{i}" for i in range(len(BANKS)))
ACCOUNT_OPTIONS = ["ACCOUNTED", "MISSING", "UNRESOLVED"]


def bank_coverage_status(accounts: dict) -> str:
    """All banks must have an explicit account; uncertainty never closes a mask."""
    if set(accounts) != set(BANK_FIELDS):
        return "INCOMPLETE_BANK_REVIEW"
    if any(v not in ACCOUNT_OPTIONS for v in accounts.values()):
        return "INVALID_BANK_REVIEW"
    if "MISSING" in accounts.values():
        return "MISSING_COMPONENT"
    if "UNRESOLVED" in accounts.values():
        return "UNRESOLVED_BANK_REVIEW"
    return "BANKS_ACCOUNTED"


def _select(selector: OllamaSelector, payload: dict, options: dict) -> dict:
    call = selector.select(payload, options)
    if selection_status(options, call["answer"]) != "VALID_SELECTION":
        raise ValueError("invalid bank review selection")
    return call


def review_banks(
    reading_id: str,
    observations: tuple[Observation, ...],
    laws: list[Law],
    state: Resolution,
    payload: dict,
    selector: OllamaSelector | None,
    repair_domains: dict[str, list[str]],
    max_repairs: int = 5,
) -> dict:
    """Review every bank; repair only scoped, surviving options, then propagate.

    A repair invalidates earlier coverage accounts: changed content may create
    obligations in another bank. Re-review the resulting vector, not the old one.
    """
    calls, decisions, rounds = [], [], []
    result = {
        "state": state,
        "laws": laws,
        "calls": calls,
        "decisions": decisions,
        "rounds": rounds,
        "code": "NOT_CHECKED",
        "missing": [],
    }
    if selector is None or state.code in {"CONFLICT", "PARTIAL_SOLVER_LIMIT"}:
        return result
    for repair_round in range(max_repairs + 1):
        fields = {}
        for bank_id, field in enumerate(BANK_FIELDS):
            fields[field] = {
                "coordinate_domains": {
                    c: [v.value for v in state.domains[c]] for c in CANONICAL_COORDINATES if PRIME_TO_BANK[c] == bank_id
                },
            }
        accounts = {}
        # Eight small three-option fields, batched to the existing five-field
        # limit. No global 56-option question licenses the other banks.
        for offset in range(0, len(BANK_FIELDS), 5):
            batch = BANK_FIELDS[offset : offset + 5]
            request = {
                **payload,
                "operation": "BANK_OMISSION_REVIEW",
                "fixed_coordinates": {c: v.value for c, v in state.forced().items()},
                "bank_accounts": {f: fields[f] for f in batch},
                "account_contract": {
                    "ACCOUNTED": "NO_MISSING_OWN_DEFINITION_COMPONENT_IN_THIS_BANK",
                    "MISSING": "OWN_DEFINITION_COMPONENT_MISSING_IN_THIS_BANK",
                    "UNRESOLVED": "CANNOT_ACCOUNT_FOR_THIS_BANK",
                    "scope": "PROVISIONAL_CANDIDATE_ONLY",
                },
            }
            call = _select(selector, request, {f: list(ACCOUNT_OPTIONS) for f in batch})
            calls.append(call)
            accounts.update(call["answer"])
        round_record = {
            "round": repair_round,
            "accounts": accounts,
            "status": bank_coverage_status(accounts),
            "missing": [],
        }
        rounds.append(round_record)
        result["code"] = round_record["status"]
        if result["code"] == "BANKS_ACCOUNTED":
            return result
        missing_banks = [f for f, account in accounts.items() if account == "MISSING"]
        if not missing_banks:
            return result
        # Locate an omission inside its bank; this diagnoses a missing
        # projection rather than granting unrestricted vector-writing power.
        options = {}
        for field in missing_banks:
            bank_id = BANK_FIELDS.index(field)
            candidates = [c for c in CANONICAL_COORDINATES if PRIME_TO_BANK[c] == bank_id and len(state.domains[c]) > 1]
            options[field] = candidates + ["UNRESOLVED"]
        missing = {}
        for offset in range(0, len(missing_banks), 5):
            batch = missing_banks[offset : offset + 5]
            call = _select(
                selector,
                {**payload, "operation": "LOCATE_BANK_OMISSION", "bank_accounts": {f: fields[f] for f in batch}},
                {f: options[f] for f in batch},
            )
            calls.append(call)
            missing.update(call["answer"])
        result["missing"] = list(missing.values())
        round_record["missing"] = missing
        # Process one choice and recalculate everything. A cross-bank law may
        # settle other omissions; stale model choices must not be applied.
        coordinate = next((c for c in missing.values() if c in repair_domains), None)
        if coordinate is None:
            result["code"] = "MISSING_PROJECTION_CONTRACT"
            return result
        if repair_round == max_repairs:
            result["code"] = "REPAIR_LIMIT"
            return result
        allowed = sorted(set(repair_domains[coordinate]) & {v.value for v in state.domains[coordinate]})
        # MISSING is not authority to pick an arbitrary sign, write zero, or
        # declare silence. The scoped domain must contain a positive component.
        allowed = [v for v in allowed if v in {"+1", "-1"}]
        if not allowed:
            result["code"] = "NO_LEGAL_REPAIR"
            return result
        call = _select(
            selector,
            {
                **payload,
                "operation": "FILL_SCOPED_OMISSION",
                "fixed_coordinates": {c: v.value for c, v in state.forced().items()},
                "residual_domains": {coordinate: allowed},
            },
            {coordinate: allowed + ["UNRESOLVED"]},
        )
        calls.append(call)
        selected = call["answer"][coordinate]
        if selected == "UNRESOLVED":
            result["code"] = "UNRESOLVED_REPAIR"
            return result
        laws.append(
            Law(
                "MODEL_OMISSION:" + call["request_sha256"],
                (coordinate,),
                ((Cell(selected),),),
                (),
                "Scoped omission repair; provisional model selection",
            )
        )
        previous = state
        state = resolve(reading_id, observations, laws=tuple(laws))
        decisions.append(
            {
                "selected": call["answer"],
                "reason": "BANK_OMISSION_REPAIR",
                "before": previous.to_json(),
                "after": state.to_json(),
            }
        )
        result["state"] = state
        if state.code in {"CONFLICT", "PARTIAL_SOLVER_LIMIT"}:
            result["code"] = state.code
            return result
    return result
