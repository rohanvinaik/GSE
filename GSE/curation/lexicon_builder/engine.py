"""Finite-domain lexical constraints, with explicit absence and proof receipts.

Only admitted relation tables are propagated. A table's rows describe permitted
joint assignments; this module does not invent linguistic implications or turn
corpus frequency into a rule. All operations leave the supplied records intact.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from math import prod

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
class DomainRestriction:
    """Native evidence excludes values without claiming a unique remaining sign."""

    bank: str
    allowed_values: tuple[int, ...]
    source: str
    record_id: str
    family: str
    scope: str = "lexical"

    def __post_init__(self) -> None:
        for field in ("bank", "source", "record_id", "family", "scope"):
            _name(getattr(self, field), field)
        if not isinstance(self.allowed_values, tuple) or not 1 <= len(self.allowed_values) < len(TERNARY):
            raise ValueError("INVALID_RESTRICTION_DOMAIN")
        for value in self.allowed_values:
            _value(value)
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("DUPLICATE_RESTRICTION_VALUE")
        if self.scope != "lexical":
            raise ValueError("NONLEXICAL_RESTRICTION")


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
    means that some coordinates remain ambiguous. The INFERENCE_SCOPE receipt
    distinguishes checked joint support from components exceeding the search cap.
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


def _resolution(
    domains: dict[str, frozenset[int]], conflicts: list[dict], trace: list[dict], *, complete_search: bool = False
) -> Resolution:
    assignments = {bank: next(iter(values)) for bank, values in domains.items() if len(values) == 1}
    code = "CONFLICT" if conflicts else "RESOLVED" if len(assignments) == len(domains) else "PARTIAL"
    receipts = (
        *trace,
        {
            "kind": "INFERENCE_SCOPE",
            "method": "GENERALIZED_ARC_CONSISTENCY_AND_BOUNDED_JOINT_SUPPORT",
            "complete_search": complete_search,
            "satisfiability": "UNSATISFIABLE" if conflicts else "SATISFIABLE" if complete_search else "NOT_ESTABLISHED",
            "partial_means": "AMBIGUOUS_JOINT_SUPPORTED_DOMAINS"
            if complete_search
            else "LOCAL_FIXED_POINT_SEARCH_LIMIT",
        },
    )
    return Resolution(code, dict(domains), assignments, tuple(conflicts), receipts)


def _relation_components(relations: list[Relation]) -> tuple[tuple[Relation, ...], ...]:
    """Partition active tables so unrelated banks never multiply search cost."""
    parents: dict[str, str] = {}

    def root(bank: str) -> str:
        parents.setdefault(bank, bank)
        while parents[bank] != bank:
            parents[bank] = parents[parents[bank]]
            bank = parents[bank]
        return bank

    for relation in relations:
        for bank in relation.banks:
            left, right = root(relation.banks[0]), root(bank)
            if left != right:
                parents[max(left, right)] = min(left, right)
    groups: dict[str, list[Relation]] = {}
    for relation in relations:
        groups.setdefault(root(relation.banks[0]), []).append(relation)
    return tuple(tuple(sorted(group, key=lambda rule: rule.rule_id)) for _, group in sorted(groups.items()))


def _joint_tables(
    banks: tuple[str, ...], rules: tuple[Relation, ...]
) -> tuple[tuple[tuple[int, ...], tuple[tuple[int, ...], ...]], ...]:
    """Canonical positional tables, independent of rule identities and row order."""
    positions = {bank: index for index, bank in enumerate(banks)}
    tables = set()
    for rule in rules:
        columns = tuple(sorted(range(len(rule.banks)), key=lambda index: positions[rule.banks[index]]))
        indices = tuple(positions[rule.banks[column]] for column in columns)
        rows = tuple(sorted({tuple(row[column] for column in columns) for row in rule.allowed_rows}))
        tables.add((indices, rows))
    return tuple(sorted(tables))


@lru_cache(maxsize=4096)
def _joint_witnesses(
    ordered_domains: tuple[tuple[int, ...], ...],
    tables: tuple[tuple[tuple[int, ...], tuple[tuple[int, ...], ...]], ...],
) -> tuple[int, tuple[frozenset[int], ...]]:
    """Reuse only exhaustive results; the caller must enforce its budget first.

    No source identity, approval, guard, receipt, or mutable object enters this
    cache. All those decisions remain in propagation. Exceptions during search
    cannot populate the cache with an incomplete support set.
    """
    memberships = tuple((indices, frozenset(rows)) for indices, rows in tables)
    supported: list[set[int]] = [set() for _ in ordered_domains]
    witnesses = 0
    for values in product(*ordered_domains):
        if all(tuple(values[index] for index in indices) in rows for indices, rows in memberships):
            witnesses += 1
            for support, value in zip(supported, values, strict=True):
                support.add(value)
    return witnesses, tuple(frozenset(values) for values in supported)


def _joint_support(domains, active, conflicts, trace, max_joint_assignments) -> bool:
    """Keep only projections of complete witnesses in each affordable component.

    A skipped component retains all GAC survivors, including explicit zero. No
    partial enumeration is used to infer absence of support. Independent small
    components are still checked when another component exceeds the bound.
    """
    complete = True
    for rules in _relation_components(active):
        banks = tuple(sorted({bank for rule in rules for bank in rule.banks}))
        ordered_domains = tuple(tuple(sorted(domains[bank])) for bank in banks)
        combinations = prod(len(values) for values in ordered_domains)
        before = {bank: tuple(sorted(domains[bank])) for bank in banks}
        receipt = {
            "banks": banks,
            "rule_ids": tuple(rule.rule_id for rule in rules),
            "provenance": tuple((rule.rule_id, rule.provenance) for rule in rules),
            "domains_before": before,
            "joint_assignments": combinations,
            "max_joint_assignments": max_joint_assignments,
        }
        if combinations > max_joint_assignments:
            complete = False
            trace.append({"kind": "SOLVER_LIMIT", "code": "JOINT_SEARCH_LIMIT", **receipt})
            continue
        witnesses, supported = _joint_witnesses(ordered_domains, _joint_tables(banks, rules))
        trace.append({"kind": "JOINT_CHECK", "witnesses": witnesses, **receipt})
        if not witnesses:
            conflicts.append({"code": "JOINT_CONFLICT", **receipt})
            for bank in banks:
                domains[bank] = frozenset()
            return False
        for bank, new in zip(banks, supported, strict=True):
            old = domains[bank]
            if new != old:
                domains[bank] = new
                trace.append(
                    {
                        "kind": "JOINT_SUPPORT",
                        "bank": bank,
                        "removed": tuple(sorted(old - new)),
                        "remaining": tuple(sorted(new)),
                        "witnesses": witnesses,
                        **receipt,
                    }
                )
    return complete


def _validated_inputs(
    banks: tuple[str, ...],
    assertions: tuple[Assertion, ...],
    relations: tuple[Relation, ...],
    context: dict[str, str] | None,
    domain_restrictions: tuple[DomainRestriction, ...] = (),
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
    if not isinstance(domain_restrictions, tuple) or any(
        not isinstance(item, DomainRestriction) for item in domain_restrictions
    ):
        raise ValueError("INVALID_DOMAIN_RESTRICTIONS")
    for restriction in domain_restrictions:
        restriction.__post_init__()
        if restriction.bank not in known:
            raise ValueError(f"UNKNOWN_RESTRICTION_BANK:{restriction.bank}")
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
    *,
    domain_restrictions: tuple[DomainRestriction, ...] = (),
    max_joint_assignments: int = 100_000,
) -> Resolution:
    """Intersect evidence, enforce arc consistency, then bounded joint support.

    Each surviving value must have a supporting row in every active relation that
    mentions its bank. Higher-order tables therefore support conjunctive and
    inverse narrowing. Candidate rules and unmatched guards never constrain cells;
    no contrapositive rule is synthesized from prose or a defeasible association.
    """
    if type(max_joint_assignments) is not int or max_joint_assignments < 1:
        raise ValueError("INVALID_JOINT_SEARCH_LIMIT")
    context_values = _validated_inputs(banks, assertions, relations, context, domain_restrictions)
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

    restricted: dict[str, list[dict]] = {}
    for item in sorted(
        domain_restrictions,
        key=lambda r: (r.bank, tuple(sorted(r.allowed_values)), r.source, r.record_id, r.family, r.scope),
    ):
        record = {
            "bank": item.bank,
            "allowed_values": tuple(sorted(item.allowed_values)),
            "source": item.source,
            "record_id": item.record_id,
            "family": item.family,
            "scope": item.scope,
        }
        restricted.setdefault(item.bank, []).append(record)
        old = domains[item.bank]
        new = old & frozenset(item.allowed_values)
        if new != old:
            domains[item.bank] = new
            trace.append(
                {
                    "kind": "DOMAIN_RESTRICTION",
                    **record,
                    "removed": tuple(sorted(old - new)),
                    "remaining": tuple(sorted(new)),
                }
            )
    for bank, records in sorted(restricted.items()):
        if not domains[bank]:
            conflicts.append(
                {
                    "code": "DOMAIN_RESTRICTION_CONFLICT",
                    "bank": bank,
                    "restrictions": tuple(records),
                    "assertions": tuple(_assertion_record(item) for item in evidence[bank]),
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
    complete = _joint_support(domains, active, conflicts, trace, max_joint_assignments)
    return _resolution(domains, conflicts, trace, complete_search=complete)
