"""Authored ordinary-family boundaries, separate from their content warrants.

A required-component record checks a derivation; it never supplies that
component. Only independently authored silence and optional domains compile
to constraints. The enclosing source rule carries admission and versioning.
"""

from __future__ import annotations

from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Law, Resolution, legal_domain


def family_contract_status(contract: object) -> str:
    """Refuse incomplete or malformed authored boundaries with named codes."""
    if not isinstance(contract, dict):
        return "MALFORMED_FAMILY_CONTRACT"
    if contract.get("schema") != "GSE_AUTHORED_FAMILY_V1":
        return "UNKNOWN_FAMILY_SCHEMA"
    if any(not isinstance(contract.get(k), str) or not contract[k] for k in ("id", "source_rule_id", "scope")):
        return "MISSING_FAMILY_IDENTITY"
    guard = contract.get("guard")
    if (
        not isinstance(guard, list)
        or not guard
        or any(not isinstance(g, list) or len(g) != 2 or any(not isinstance(v, str) or not v for v in g) for g in guard)
    ):
        return "MALFORMED_FAMILY_GUARD"
    cells = contract.get("cells")
    if not isinstance(cells, dict) or set(cells) != set(CANONICAL_COORDINATES):
        return "INCOMPLETE_FAMILY_ACCOUNT"
    for coordinate, decision in cells.items():
        if not isinstance(decision, dict):
            return "MALFORMED_FAMILY_DECISION"
        if not isinstance(decision.get("kind"), str) or decision["kind"] not in {"REQUIRED", "OPTIONAL", "SILENT"}:
            return "UNKNOWN_FAMILY_DECISION"
        domain = decision.get("domain")
        if (
            not isinstance(domain, list)
            or not domain
            or any(not isinstance(v, str) or v not in legal_domain(coordinate) for v in domain)
            or len(domain) != len(set(domain))
        ):
            return "ILLEGAL_FAMILY_DOMAIN"
        if (decision["kind"] == "OPTIONAL" and len(domain) < 2) or (
            decision["kind"] != "OPTIONAL" and len(domain) != 1
        ):
            return "FAMILY_DECISION_SHAPE"
        if decision["kind"] == "SILENT" and domain != ["empty"]:
            return "FAMILY_SILENCE_MISMATCH"
        refs = decision.get("source_refs")
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or not r for r in refs):
            return "MISSING_FAMILY_WARRANT"
        if not isinstance(decision.get("reason"), str) or not decision["reason"]:
            return "MISSING_FAMILY_WARRANT"
    return "VALID_FAMILY_CONTRACT"


def family_contract(rule: dict) -> dict | None:
    contract = rule.get("definition_boundary")
    if contract is None:
        return None
    status = family_contract_status(contract)
    if status != "VALID_FAMILY_CONTRACT":
        raise ValueError(status)
    if contract["source_rule_id"] != rule["rule_id"]:
        raise ValueError("FAMILY_SOURCE_RULE_MISMATCH")
    return contract


def family_laws(rule: dict) -> list[Law]:
    """Compile only explicit boundary decisions, never expected content."""
    contract = family_contract(rule)
    if contract is None:
        return []
    return [
        Law(
            "FAMILY:" + contract["id"] + ":" + coordinate,
            (coordinate,),
            tuple((Cell(v),) for v in decision["domain"]),
            tuple(tuple(g) for g in contract["guard"]),
            decision["reason"],
            "CONDITIONAL",
        )
        for coordinate, decision in contract["cells"].items()
        if decision["kind"] != "REQUIRED"
    ]


def optional_components(rule: dict) -> list[str]:
    contract = family_contract(rule)
    return [] if contract is None else [c for c, d in contract["cells"].items() if d["kind"] == "OPTIONAL"]


def account_family(rule: dict, state: Resolution) -> dict:
    """Check all obligations without repairing an omission with its expectation."""
    contract = family_contract(rule)
    if contract is None:
        return {"code": "NO_FAMILY_ACCOUNT"}
    unresolved, contradictions = [], []
    for coordinate, decision in contract["cells"].items():
        actual = {v.value for v in state.domains[coordinate]}
        allowed = set(decision["domain"])
        if not actual or not actual & allowed:
            contradictions.append(coordinate)
        elif len(actual) != 1 or not actual <= allowed:
            unresolved.append(coordinate)
    return {
        "code": "FAMILY_CONTRADICTED" if contradictions else "FAMILY_UNRESOLVED" if unresolved else "FAMILY_ACCOUNTED",
        "family_id": contract["id"],
        "authority": "AUTHORED_GSE_BOUNDARY; NOT_INDEPENDENT_SEMANTIC_COMPLETENESS",
        "unresolved": unresolved,
        "contradictions": contradictions,
    }
