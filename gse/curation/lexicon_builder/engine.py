"""Finite-domain lexical constraints, with explicit absence and proof receipts.

Only admitted relation tables are propagated. A table's rows describe permitted
joint assignments; this module does not invent linguistic implications or turn
corpus frequency into a rule. All operations leave the supplied records intact.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

TERNARY = frozenset((-1, 0, 1))


def _name(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"INVALID_{field.upper()}")


def _value(value: object) -> None:
    if type(value) is not int or value not in TERNARY:
        raise ValueError("INVALID_TERNARY_VALUE")


@dataclass(frozen=True)
class Assertion:
    """One source's own-word assertion; zero is an actual assertion."""

    bank: str
    value: int
    source: str
    record_id: str
    family: str
    scope: str = "lexical"

    def __post_init__(self) -> None:
        for field in ("bank", "source", "record_id", "family", "scope"):
            _name(getattr(self, field), field)
        _value(self.value)
        if self.scope != "lexical":
            raise ValueError("NONLEXICAL_ASSERTION")


@dataclass(frozen=True)
class Relation:
    """A scoped, version-identifiable table of allowed joint bank values."""

    rule_id: str
    banks: tuple[str, ...]
    allowed_rows: tuple[tuple[int, ...], ...]
    provenance: tuple[str, ...]
    authority: str = "conditional"
    approved: bool = False
    guards: tuple[tuple[str, str], ...] = ()
    absent_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _name(self.rule_id, "rule_id")
        _name(self.authority, "authority")
        if not isinstance(self.banks, tuple) or not self.banks:
            raise ValueError("INVALID_RELATION_BANKS")
        for bank in self.banks:
            _name(bank, "bank")
        if len(set(self.banks)) != len(self.banks):
            raise ValueError("DUPLICATE_RELATION_BANK")
        if not isinstance(self.allowed_rows, tuple):
            raise ValueError("INVALID_RELATION_ROWS")
        for row in self.allowed_rows:
            if not isinstance(row, tuple) or len(row) != len(self.banks):
                raise ValueError("INVALID_RELATION_ROW_ARITY")
            for value in row:
                _value(value)
        if not isinstance(self.provenance, tuple):
            raise ValueError("INVALID_PROVENANCE")
        for source in self.provenance:
            _name(source, "provenance")
        if type(self.approved) is not bool:
            raise ValueError("INVALID_APPROVAL")
        if self.approved and self.authority not in {"foundational", "conditional"}:
            raise ValueError("UNAPPROVED_AUTHORITY")
        if self.approved and not self.provenance:
            raise ValueError("MISSING_RULE_PROVENANCE")
        if not isinstance(self.guards, tuple):
            raise ValueError("INVALID_GUARDS")
        keys: set[str] = set()
        for guard in self.guards:
            if not isinstance(guard, tuple) or len(guard) != 2:
                raise ValueError("INVALID_GUARD")
            key, value = guard
            _name(key, "guard_key")
            if not isinstance(value, str):
                raise ValueError("INVALID_GUARD_VALUE")
            if key in keys:
                raise ValueError("DUPLICATE_GUARD_KEY")
            keys.add(key)
        if not isinstance(self.absent_evidence, tuple):
            raise ValueError("INVALID_ABSENT_EVIDENCE")
        for bank in self.absent_evidence:
            _name(bank, "absent_evidence_bank")
        if len(set(self.absent_evidence)) != len(self.absent_evidence):
            raise ValueError("DUPLICATE_ABSENT_EVIDENCE_BANK")


@dataclass(frozen=True)
class Resolution:
    """Current domains and warranted singletons, never a majority winner.

    CONFLICT forbids committing even the remaining singleton assignments. PARTIAL
    means that arc consistency has reached a fixed point, not that the complete
    constraint problem has been proved satisfiable.
    """

    code: str
    domains: dict[str, frozenset[int]]
    assignments: dict[str, int]
    conflicts: tuple[dict, ...]
    trace: tuple[dict, ...]


def _assertion_record(assertion: Assertion) -> dict:
    return {
        "bank": assertion.bank,
        "value": assertion.value,
        "source": assertion.source,
        "record_id": assertion.record_id,
        "family": assertion.family,
        "scope": assertion.scope,
    }


def _resolution(domains: dict[str, frozenset[int]], conflicts: list[dict], trace: list[dict]) -> Resolution:
    assignments = {bank: next(iter(values)) for bank, values in domains.items() if len(values) == 1}
    code = "CONFLICT" if conflicts else "RESOLVED" if len(assignments) == len(domains) else "PARTIAL"
    receipts = (
        *trace,
        {
            "kind": "INFERENCE_SCOPE",
            "method": "GENERALIZED_ARC_CONSISTENCY",
            "complete_search": False,
            "partial_means": "LOCAL_FIXED_POINT_NOT_GLOBAL_SATISFIABILITY",
        },
    )
    return Resolution(code, dict(domains), assignments, tuple(conflicts), receipts)


def _validated_inputs(
    banks: tuple[str, ...],
    assertions: tuple[Assertion, ...],
    relations: tuple[Relation, ...],
    context: dict[str, str] | None,
) -> dict[str, str]:
    if not isinstance(banks, tuple):
        raise ValueError("INVALID_BANKS")
    for bank in banks:
        _name(bank, "bank")
    if len(set(banks)) != len(banks):
        raise ValueError("DUPLICATE_BANK")
    if not isinstance(assertions, tuple) or not all(isinstance(item, Assertion) for item in assertions):
        raise ValueError("INVALID_ASSERTIONS")
    if not isinstance(relations, tuple) or not all(isinstance(item, Relation) for item in relations):
        raise ValueError("INVALID_RELATIONS")
    known = set(banks)
    for assertion in assertions:
        assertion.__post_init__()
        if assertion.bank not in known:
            raise ValueError(f"UNKNOWN_BANK:{assertion.bank}")
    rule_ids: set[str] = set()
    for relation in relations:
        relation.__post_init__()
        if not set(relation.banks) <= known:
            raise ValueError(f"UNKNOWN_RELATION_BANK:{relation.rule_id}")
        if not set(relation.absent_evidence) <= known:
            raise ValueError(f"UNKNOWN_ABSENT_EVIDENCE_BANK:{relation.rule_id}")
        if relation.rule_id in rule_ids:
            raise ValueError(f"DUPLICATE_RULE_ID:{relation.rule_id}")
        rule_ids.add(relation.rule_id)
    if context is None:
        return {}
    if not isinstance(context, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in context.items()
    ):
        raise ValueError("INVALID_CONTEXT")
    return dict(context)


def propagate(
    banks: tuple[str, ...],
    assertions: tuple[Assertion, ...],
    relations: tuple[Relation, ...],
    context: dict[str, str] | None = None,
) -> Resolution:
    """Intersect source assertions and enforce generalized arc consistency.

    Each surviving value must have a supporting row in every active relation that
    mentions its bank. Higher-order tables therefore support conjunctive and
    inverse narrowing. Candidate rules and unmatched guards never constrain cells;
    no contrapositive rule is synthesized from prose or a defeasible association.
    """
    context_values = _validated_inputs(banks, assertions, relations, context)
    domains = {bank: TERNARY for bank in sorted(banks)}
    trace: list[dict] = []
    conflicts: list[dict] = []
    evidence: dict[str, list[Assertion]] = {bank: [] for bank in domains}
    ordered_assertions = sorted(
        assertions,
        key=lambda item: (item.bank, item.value, item.source, item.record_id, item.family, item.scope),
    )
    for assertion in ordered_assertions:
        evidence[assertion.bank].append(assertion)
        old = domains[assertion.bank]
        new = old & {assertion.value}
        if new != old:
            domains[assertion.bank] = frozenset(new)
            trace.append(
                {
                    "kind": "ASSERTION",
                    **_assertion_record(assertion),
                    "removed": tuple(sorted(old - new)),
                    "remaining": tuple(sorted(new)),
                }
            )
    for bank, records in evidence.items():
        if not domains[bank]:
            conflicts.append(
                {
                    "code": "ASSERTION_CONFLICT",
                    "bank": bank,
                    "assertions": tuple(_assertion_record(item) for item in records),
                }
            )
    if conflicts:
        return _resolution(domains, conflicts, trace)

    active: list[Relation] = []
    for relation in sorted(relations, key=lambda item: item.rule_id):
        reason = (
            "UNAPPROVED"
            if not relation.approved
            else "GUARD_MISMATCH"
            if any(context_values.get(key) != value for key, value in relation.guards)
            else "EVIDENCE_GUARD_NOT_EVALUATED"
            if relation.absent_evidence
            else None
        )
        if reason:
            trace.append({"kind": "RELATION_SKIPPED", "rule_id": relation.rule_id, "reason": reason})
        else:
            active.append(relation)

    watchers: dict[str, set[int]] = {bank: set() for bank in domains}
    for index, relation in enumerate(active):
        for bank in relation.banks:
            watchers[bank].add(index)
    pending = list(range(len(active)))
    queued = set(pending)
    while pending:
        relation_index = heapq.heappop(pending)
        queued.remove(relation_index)
        relation = active[relation_index]
        rows = tuple(
            sorted(
                {
                    row
                    for row in relation.allowed_rows
                    if all(value in domains[bank] for bank, value in zip(relation.banks, row))
                }
            )
        )
        before = {bank: tuple(sorted(domains[bank])) for bank in relation.banks}
        if not rows:
            conflicts.append(
                {
                    "code": "RELATION_CONFLICT",
                    "rule_id": relation.rule_id,
                    "banks": relation.banks,
                    "domains_before": before,
                    "provenance": relation.provenance,
                }
            )
        for index, bank in enumerate(relation.banks):
            old = domains[bank]
            new = frozenset(row[index] for row in rows)
            if new != old:
                domains[bank] = new
                trace.append(
                    {
                        "kind": "RELATION",
                        "rule_id": relation.rule_id,
                        "bank": bank,
                        "removed": tuple(sorted(old - new)),
                        "remaining": tuple(sorted(new)),
                        "domains_before": before,
                        "support_rows": rows,
                        "provenance": relation.provenance,
                    }
                )
                for dependent in sorted(watchers[bank] - queued - {relation_index}):
                    heapq.heappush(pending, dependent)
                    queued.add(dependent)
        if conflicts:
            return _resolution(domains, conflicts, trace)
    return _resolution(domains, conflicts, trace)
