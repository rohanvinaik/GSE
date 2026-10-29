"""Local exceptions for approved conditional relations over an inviolate base.

Native/anchor assertions and foundational relations are hard constraints. An
exception withdraws conditional inferences for this definition only; it neither
deletes the rule nor invents a lexical guard. Significance ranking and corpus
guard specialization are separate operations, not firing gates here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, replace

from .engine import TERNARY, Assertion, Relation, Resolution, _validated_inputs, propagate


def _conditional_components(
    foundational: tuple[Relation, ...], conditional: tuple[Relation, ...]
) -> tuple[tuple[Relation, ...], ...]:
    """Connect conditional rules through shared banks and foundational edges."""
    parents: dict[str, str] = {}

    def root(bank: str) -> str:
        parents.setdefault(bank, bank)
        while parents[bank] != bank:
            parents[bank] = parents[parents[bank]]
            bank = parents[bank]
        return bank

    for rule in foundational + conditional:
        for bank in rule.banks:
            left, right = root(rule.banks[0]), root(bank)
            if left != right:
                parents[max(left, right)] = min(left, right)
    groups: dict[str, list[Relation]] = defaultdict(list)
    for rule in conditional:
        groups[root(rule.banks[0])].append(rule)
    components = [tuple(sorted(group, key=lambda rule: rule.rule_id)) for group in groups.values()]
    return tuple(sorted(components, key=lambda component: component[0].rule_id))


def _exception(
    rules: tuple[Relation, ...], reason: str, witness: Resolution, hard: Resolution, context: dict[str, str]
) -> dict:
    banks = sorted({bank for rule in rules for bank in rule.banks})
    return {
        "kind": "CONDITIONAL_EXCEPTION",
        "reason": reason,
        "disposition": "EXCEPTED_FOR_THIS_DEFINITION",
        "rule_ids": tuple(rule.rule_id for rule in rules),
        "rules": tuple(
            {"rule_id": rule.rule_id, "provenance": rule.provenance, "guards": rule.guards} for rule in rules
        ),
        "context": dict(sorted(context.items())),
        "hard_domains": {bank: tuple(sorted(hard.domains[bank])) for bank in banks},
        "conflicts": witness.conflicts,
        "specialization": "NOT_INFERRED",
    }


def _resolve_ordinary(
    banks: tuple[str, ...],
    assertions: tuple[Assertion, ...],
    relations: tuple[Relation, ...],
    context: dict[str, str] | None = None,
) -> Resolution:
    """Apply conditional rules unless they contradict hard evidence or each other.

    An approved rule with no guards has universal scope. Explicit guards retain
    the engine's exact-match semantics. Individually contradicted conditional
    rules are locally excepted. A jointly conflicting connected component loses
    all its conditional rules, preserving order independence and avoiding an
    arbitrary winner. Foundational edges participate in connectivity; otherwise
    a hard relation could conceal a conflict between ostensibly separate rules.

    This conservative component withdrawal can also remove a harmless rule that
    shares the component. Receipts name every withdrawn rule and the demonstrated
    contradiction. Constraint consistency remains generalized arc consistency,
    not a claim of global satisfiability or completed significance induction.
    """
    # Validate all inputs through the existing engine and preserve its normal
    # single-pass path when no contradiction requires an exception decision.
    combined = propagate(banks, assertions, relations, context)
    if combined.code != "CONFLICT":
        return combined
    context_values = context or {}
    active = tuple(
        rule
        for rule in relations
        if rule.approved and all(context_values.get(key) == value for key, value in rule.guards)
    )
    foundational = tuple(rule for rule in active if rule.authority == "foundational")
    conditional = tuple(
        sorted((rule for rule in active if rule.authority == "conditional"), key=lambda rule: rule.rule_id)
    )
    inactive = tuple(rule for rule in relations if rule not in active)
    hard = propagate(banks, assertions, foundational, context)
    if hard.code == "CONFLICT":
        return hard
    exceptions, eligible = [], []
    for rule in conditional:
        witness = propagate(banks, assertions, foundational + (rule,), context)
        if witness.code == "CONFLICT":
            exceptions.append(_exception((rule,), "HARD_CONTRADICTION", witness, hard, context_values))
        else:
            eligible.append(rule)
    retained = []
    for component in _conditional_components(foundational, tuple(eligible)):
        witness = propagate(banks, assertions, foundational + component, context)
        if witness.code == "CONFLICT":
            exceptions.append(_exception(component, "CONDITIONAL_COMPONENT_CONFLICT", witness, hard, context_values))
        else:
            retained.extend(component)
    resolved = propagate(banks, assertions, foundational + tuple(retained) + inactive, context)
    receipts = tuple(sorted(exceptions, key=lambda item: item["rule_ids"]))
    return Resolution(
        resolved.code, resolved.domains, resolved.assignments, resolved.conflicts, resolved.trace + receipts
    )


def _evidence_guard_receipt(rule, assertions, baseline, supplied, context):
    """Explain eligibility using only evidence predating every default."""
    witnesses = []
    for bank in sorted(rule.absent_evidence):
        claims = tuple(
            sorted(
                (asdict(assertion) for assertion in assertions if assertion.bank == bank),
                key=lambda record: (record["source"], record["record_id"], record["family"], record["value"]),
            )
        )
        narrowed = baseline.domains[bank] != TERNARY
        if bank in supplied or claims or narrowed:
            witnesses.append(
                {
                    "bank": bank,
                    "supplied_evidence": bank in supplied,
                    "assertions": claims,
                    "baseline_domain": tuple(sorted(baseline.domains[bank])),
                    "baseline_narrowed": narrowed,
                    "baseline_rule_ids": tuple(
                        sorted(
                            {
                                record["rule_id"]
                                for record in baseline.trace
                                if record["kind"] == "RELATION" and record["bank"] == bank
                            }
                        )
                    ),
                }
            )
    reason = (
        "BASELINE_CONFLICT"
        if baseline.code == "CONFLICT"
        else "UNAPPROVED"
        if not rule.approved
        else "GUARD_MISMATCH"
        if any(context.get(key) != value for key, value in rule.guards)
        else "RELEVANT_EVIDENCE"
        if witnesses
        else "NO_RELEVANT_EVIDENCE"
    )
    return {
        "kind": "EVIDENCE_GUARD",
        "rule_id": rule.rule_id,
        "status": "ELIGIBLE" if reason == "NO_RELEVANT_EVIDENCE" else "BLOCKED",
        "reason": reason,
        "relation": asdict(rule),
        "context": dict(sorted(context.items())),
        "witnesses": tuple(witnesses),
        "relevance_basis": "ORDINARY_CLOSURE_BEFORE_ALL_DEFAULTS",
    }


def resolve_dictionary(
    banks: tuple[str, ...],
    assertions: tuple[Assertion, ...],
    relations: tuple[Relation, ...],
    context: dict[str, str] | None = None,
    *,
    evidence_banks: tuple[str, ...] = (),
) -> Resolution:
    """Resolve ordinary evidence before admitting evidence-conditioned defaults.

    A supplied evidence bank can be relevant without having a known sign. Every
    explicit assertion, including zero, and every ordinarily narrowed domain is
    also relevant. All defaults inspect this same baseline; a default's results
    cannot make another default eligible or ineligible. Blocked defaults never
    enter propagation and therefore never require contradiction-based fallback.
    """
    context_values = _validated_inputs(banks, assertions, relations, context)
    if not isinstance(evidence_banks, tuple) or any(
        not isinstance(bank, str) or not bank.strip() for bank in evidence_banks
    ):
        raise ValueError("INVALID_EVIDENCE_BANKS")
    if len(set(evidence_banks)) != len(evidence_banks):
        raise ValueError("DUPLICATE_EVIDENCE_BANK")
    if not set(evidence_banks) <= set(banks):
        raise ValueError("UNKNOWN_EVIDENCE_BANK")
    ordinary = tuple(rule for rule in relations if not rule.absent_evidence)
    defaults = tuple(sorted((rule for rule in relations if rule.absent_evidence), key=lambda rule: rule.rule_id))
    baseline = _resolve_ordinary(banks, assertions, ordinary, context_values)
    if not defaults:
        return baseline
    supplied = set(evidence_banks)
    receipts = tuple(_evidence_guard_receipt(rule, assertions, baseline, supplied, context_values) for rule in defaults)
    eligible = tuple(
        replace(rule, absent_evidence=())
        for rule, receipt in zip(defaults, receipts, strict=True)
        if receipt["status"] == "ELIGIBLE"
    )
    resolved = _resolve_ordinary(banks, assertions, ordinary + eligible, context_values) if eligible else baseline
    return Resolution(
        resolved.code, resolved.domains, resolved.assignments, resolved.conflicts, resolved.trace + receipts
    )
