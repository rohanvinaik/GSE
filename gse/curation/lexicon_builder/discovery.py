"""Source-backed implication diagnostics; no frequency-based rule admission.

Observation groups preserve a dictionary entry, source and evidence family.
Disagreement within such a group stays disagreement. Unknown antecedents are
outside the candidate's eligible population; unknown consequents are reported
separately and never count as confirmation. Weights describe coverage only.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from itertools import permutations
from typing import TYPE_CHECKING

from .engine import TERNARY, Relation

if TYPE_CHECKING:
    from .evidence import EvidenceBundle


@dataclass(frozen=True)
class BankObservation:
    """A typed observation with explicit derivation and projection provenance."""

    entry_id: str
    bank: str
    value: int | None
    source: str
    record_id: str
    family: str
    origin: str = "source"
    scope: str = "lexical"

    def __post_init__(self) -> None:
        for field in ("entry_id", "bank", "source", "record_id", "family", "scope"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"INVALID_{field.upper()}")
        if self.value is not None and (type(self.value) is not int or self.value not in TERNARY):
            raise ValueError("INVALID_TERNARY_VALUE")
        if self.origin not in {"source", "derived", "model"}:
            raise ValueError("INVALID_OBSERVATION_ORIGIN")


@dataclass(frozen=True)
class CandidateReport:
    """Receipts for one proposed implication; its relation is never approved."""

    relation: Relation
    antecedent: tuple[str, int]
    consequent: tuple[str, int]
    support: tuple[dict, ...]
    counterexamples: tuple[dict, ...]
    unknown: tuple[dict, ...]
    conflicting: tuple[dict, ...]
    ineligible: tuple[dict, ...]
    by_family: dict[str, dict[str, int | float]]
    admission: str = "UNAPPROVED_CANDIDATE"
    propagation_scope: str = "LOCAL_ARC_CONSISTENCY"


def _record(item: BankObservation) -> dict:
    return {
        "entry_id": item.entry_id,
        "bank": item.bank,
        "value": item.value,
        "source": item.source,
        "record_id": item.record_id,
        "family": item.family,
        "origin": item.origin,
        "scope": item.scope,
    }


def _candidate(value: object) -> tuple[str, int, str, int]:
    if not isinstance(value, tuple) or len(value) != 4:
        raise ValueError("INVALID_CANDIDATE")
    left, a, right, b = value
    if any(not isinstance(bank, str) or not bank.strip() for bank in (left, right)) or left == right:
        raise ValueError("INVALID_CANDIDATE_BANKS")
    if any(type(v) is not int or v not in TERNARY for v in (a, b)):
        raise ValueError("INVALID_CANDIDATE_VALUE")
    return left, a, right, b


def _weight_map(weights: dict[str, float] | None) -> dict[str, float]:
    if weights is None:
        return {}
    if not isinstance(weights, dict):
        raise ValueError("INVALID_WEIGHTS")
    result: dict[str, float] = {}
    for key, value in weights.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("INVALID_WEIGHT_ENTRY")
        if type(value) not in (int, float) or value < 0:
            raise ValueError("INVALID_WEIGHT")
        try:
            number = float(value)
        except OverflowError as error:
            raise ValueError("INVALID_WEIGHT") from error
        if not math.isfinite(number):
            raise ValueError("INVALID_WEIGHT")
        result[key] = number
    return result


def _count(counts: dict[str, dict[str, int | float]], family: str, status: str, weight: float) -> None:
    bucket = counts.setdefault(family, {})
    bucket[status] = bucket.get(status, 0) + 1
    weighted = f"weighted_{status}"
    total = bucket.get(weighted, 0.0) + weight
    if not math.isfinite(total):
        raise ValueError("WEIGHT_TOTAL_OVERFLOW")
    bucket[weighted] = total


def _population(keys: set[tuple[str, str, str]], weights: dict[str, float]) -> dict[str, tuple[int, float]]:
    summary: dict[str, tuple[int, float]] = {}
    for entry_id, _source, family in sorted(keys):
        count, weight = summary.get(family, (0, 0.0))
        total = weight + weights.get(entry_id, 1.0)
        if not math.isfinite(total):
            raise ValueError("WEIGHT_TOTAL_OVERFLOW")
        summary[family] = count + 1, total
    return summary


def discover_relations(
    observations: tuple[BankObservation, ...],
    weights: dict[str, float] | None = None,
    candidates: tuple[tuple[str, int, str, int], ...] | None = None,
) -> tuple[CandidateReport, ...]:
    """Diagnose candidate implications using native own-word observations.

    Optional candidate tuples are (antecedent_bank, value, consequent_bank, value).
    Otherwise candidates come from observed singleton pairs, including explicit
    zero. Missing cells never generate a candidate. Counts are source-entry-group
    counts by family, not a claim of independent votes or causal confidence.

    The returned table encodes the candidate implication, but approved=False means
    the solver cannot apply it. Structural justification and admission are separate.
    """
    if not isinstance(observations, tuple) or any(not isinstance(item, BankObservation) for item in observations):
        raise ValueError("INVALID_OBSERVATIONS")
    word_weights = _weight_map(weights)
    grouped: dict[tuple[str, str, str], dict[str, list[BankObservation]]] = {}
    excluded: list[dict] = []
    for item in sorted(
        observations,
        key=lambda o: (
            o.entry_id,
            o.source,
            o.family,
            o.bank,
            o.record_id,
            o.origin,
            o.scope,
            2 if o.value is None else o.value,
        ),
    ):
        item.__post_init__()
        if item.origin != "source" or item.scope != "lexical":
            excluded.append({**_record(item), "code": "NOT_SOURCE_LEXICAL_EVIDENCE"})
        else:
            grouped.setdefault((item.entry_id, item.source, item.family), {}).setdefault(item.bank, []).append(item)

    values = {
        key: {bank: frozenset(item.value for item in rows if item.value is not None) for bank, rows in banks.items()}
        for key, banks in grouped.items()
    }
    # Indexing by antecedent keeps diagnostic work proportional to its actual
    # population; absent antecedents are counted, never expanded into evidence.
    matching: dict[tuple[str, int], set[tuple[str, str, str]]] = {}
    observed: dict[str, set[tuple[str, str, str]]] = {}
    conflicts: dict[str, set[tuple[str, str, str]]] = {}
    generated: set[tuple[str, int, str, int]] = set()
    for key, bank_values in values.items():
        singletons: list[tuple[str, int]] = []
        for bank, domain in bank_values.items():
            if domain:
                observed.setdefault(bank, set()).add(key)
            if len(domain) == 1:
                value = next(iter(domain))
                matching.setdefault((bank, value), set()).add(key)
                singletons.append((bank, value))
            elif len(domain) > 1:
                conflicts.setdefault(bank, set()).add(key)
        if candidates is None:
            for (left, a), (right, b) in permutations(singletons, 2):
                generated.add((left, a, right, b))
    if candidates is not None:
        if not isinstance(candidates, tuple):
            raise ValueError("INVALID_CANDIDATES")
        generated = {_candidate(item) for item in candidates}

    reports: list[CandidateReport] = []
    all_keys = set(grouped)
    totals = _population(all_keys, word_weights)
    observed_totals = {bank: _population(keys, word_weights) for bank, keys in observed.items()}
    matching_totals = {literal: _population(keys, word_weights) for literal, keys in matching.items()}
    conflict_totals = {bank: _population(keys, word_weights) for bank, keys in conflicts.items()}
    excluded_records = tuple(excluded)
    for left, a, right, b in sorted(generated):
        antecedent_keys = matching.get((left, a), set())
        conflict_keys = conflicts.get(left, set())
        buckets: dict[str, list[dict]] = {name: [] for name in ("support", "counterexamples", "unknown", "conflicting")}
        counts: dict[str, dict[str, int | float]] = {}
        for family, total in totals.items():
            seen = observed_totals.get(left, {}).get(family, (0, 0.0))
            matched = matching_totals.get((left, a), {}).get(family, (0, 0.0))
            conflicted = conflict_totals.get(left, {}).get(family, (0, 0.0))
            for status, count, weight in (
                ("antecedent_unknown", total[0] - seen[0], total[1] - seen[1]),
                ("antecedent_other", seen[0] - matched[0] - conflicted[0], seen[1] - matched[1] - conflicted[1]),
            ):
                if count:
                    counts.setdefault(family, {}).update({status: count, f"weighted_{status}": max(0.0, weight)})
        for key in sorted(antecedent_keys | conflict_keys):
            entry_id, source, family = key
            left_values = values[key].get(left, frozenset())
            right_values = values[key].get(right, frozenset())
            weight = word_weights.get(entry_id, 1.0)
            if len(left_values) > 1:
                status, reason = "conflicting", "ANTECEDENT_CONFLICT"
            elif len(right_values) > 1:
                status, reason = "conflicting", "CONSEQUENT_CONFLICT"
            elif not right_values:
                status, reason = "unknown", "CONSEQUENT_UNOBSERVED"
            elif b in right_values:
                status, reason = "support", "OBSERVED_AGREEMENT"
            else:
                status, reason = "counterexamples", "OBSERVED_COUNTEREXAMPLE"
            rows = grouped[key].get(left, []) + grouped[key].get(right, [])
            receipt = {
                "entry_id": entry_id,
                "source": source,
                "family": family,
                "weight": weight,
                "code": reason,
                "antecedent_values": tuple(sorted(left_values)),
                "consequent_values": tuple(sorted(right_values)),
                "observations": tuple(_record(item) for item in rows),
            }
            buckets[status].append(receipt)
            _count(counts, family, status, weight)
            if status in {"support", "counterexamples"}:
                _count(counts, family, "eligible", weight)
        identity = hashlib.sha256(json.dumps([left, a, right, b], separators=(",", ":")).encode()).hexdigest()[:20]
        provenance = tuple(
            sorted(
                {
                    f"{row['source']}:{row['record_id']}"
                    for receipt in buckets["support"]
                    for row in receipt["observations"]
                }
            )
        )
        relation = Relation(
            rule_id=f"candidate:{identity}",
            banks=(left, right),
            allowed_rows=tuple((x, y) for x in sorted(TERNARY) for y in sorted(TERNARY) if x != a or y == b),
            provenance=provenance,
            authority="conditional",
            approved=False,
        )
        reports.append(
            CandidateReport(
                relation,
                (left, a),
                (right, b),
                tuple(buckets["support"]),
                tuple(buckets["counterexamples"]),
                tuple(buckets["unknown"]),
                tuple(buckets["conflicting"]),
                excluded_records,
                {family: dict(sorted(entries.items())) for family, entries in sorted(counts.items())},
            )
        )
    return tuple(reports)


def discover_bundle(bundle: EvidenceBundle, weights: dict[str, float] | None = None) -> tuple[CandidateReport, ...]:
    """Diagnose the bundle's already-warranted projections, using exact links.

    This does not reinterpret raw ratings, manufacture definitions, or re-ground a
    source. An assertion must have one exact source-record link to a known entry;
    ambiguous or missing links are refused. Records with nonlexical provenance and
    model/derived sources remain ineligible. The build calls this only on request.
    """
    definitions = {definition.entry_id for definition in bundle.definitions}
    links: dict[tuple[str, str], list] = {}
    for observation in bundle.observations:
        links.setdefault((observation.source, observation.record_id), []).append(observation)
    observations: list[BankObservation] = []
    for assertion in bundle.assertions:
        records = links.get((assertion.source, assertion.record_id), [])
        identities = {record.entry_id for record in records}
        if not records or None in identities or len(identities) != 1:
            raise ValueError(f"UNRESOLVED_ASSERTION_LINK:{assertion.source}:{assertion.record_id}")
        entry_id = next(iter(identities))
        if entry_id not in definitions:
            raise ValueError(f"UNKNOWN_ASSERTION_DEFINITION:{entry_id}")
        if any(record.family != assertion.family for record in records):
            raise ValueError(f"ASSERTION_FAMILY_MISMATCH:{assertion.record_id}")
        scopes = {record.scope for record in records}
        if len(scopes) != 1:
            raise ValueError(f"ASSERTION_SCOPE_MISMATCH:{assertion.record_id}")
        origin = "source"
        if assertion.source.startswith("model:") or assertion.family == "model":
            origin = "model"
        elif assertion.source.startswith(("rule:", "derived:")) or assertion.family == "derived":
            origin = "derived"
        observations.append(
            BankObservation(
                entry_id=entry_id,
                bank=assertion.bank,
                value=assertion.value,
                source=assertion.source,
                record_id=assertion.record_id,
                family=assertion.family,
                origin=origin,
                scope=next(iter(scopes)),
            )
        )
    return discover_relations(tuple(observations), weights)
