"""Reviewed model-ruling proposals, ephemeral staging, and direct held-out audits.

This separate diagnostic ledger never changes native-source discovery, approves
production rules, or writes a lexicon. Review is explicitly supplied and pinned;
model agreement is not independent gold or a proof of a causal law. Audit
antecedents must replay from the supplied native/anchor baseline and a complete
explicitly reviewed dependency prefix. Missing dependencies are named refusals.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from itertools import permutations
from pathlib import Path

from .definition_frames import NATIVE_FRAME_PREFIX
from .engine import Assertion, DomainRestriction, Relation
from .evidence import Definition, Observation, validate_assertion_competence
from .foundation import BANKS, lexical_context, valid_lexical_guard
from .interchange import read_json
from .model_protocol import model_input
from .model_receipts import validate_receipt
from .relevance import observation_relevance
from .residual import _canonical_json, _request_id, build_request, complete_bank
from .resolution import resolve_dictionary

INPUT_FORMAT = "gse.reviewed-pattern-input/2"
REPORT_FORMAT = "gse.reviewed-pattern-report/2"
LEGACY_INPUT_FORMAT = "gse.reviewed-pattern-input/1"
LEGACY_REPORT_FORMAT = "gse.reviewed-pattern-report/1"


@dataclass(frozen=True)
class ReviewedRuling:
    entry_id: str
    bank: str
    value: int
    request_id: str
    source: str
    review_id: str
    reviewer: str
    receipt_sha256: str
    receipt: dict
    source_refs: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class DefinitionInput:
    definition: Definition
    assertions: tuple[Assertion, ...]
    observations: tuple[dict, ...]
    restrictions: tuple[DomainRestriction, ...]
    context: dict[str, str]
    evidence_banks: tuple[str, ...]
    rule_history: dict | None = None


@dataclass(frozen=True)
class Pattern:
    relation: Relation
    antecedent: tuple[str, int] | None
    consequent: tuple[str, int]
    discovery_entry_ids: tuple[str, ...]
    audit_entry_ids: tuple[str, ...]
    records: tuple[dict, ...]
    warrant: dict | None = None
    premises: tuple[tuple[str, int], ...] = ()


def _fields(record, required, optional=()):
    if type(record) is not dict or not set(required) <= record.keys() or record.keys() - set(required) - set(optional):
        raise ValueError("INVALID_PATTERN_INPUT_FIELDS")


def _ids(values: list[str]):
    if type(values) is not list or any(type(value) is not str or not value.strip() for value in values):
        raise ValueError("INVALID_PATTERN_ENTRY_IDS")
    if len(set(values)) != len(values):
        raise ValueError("DUPLICATE_PATTERN_ENTRY_ID")
    return tuple(sorted(values))


def reviewed_rulings(records: list[dict]) -> tuple[ReviewedRuling, ...]:
    """Validate explicitly accepted reviews without upgrading model provenance."""
    if type(records) is not list:
        raise ValueError("INVALID_REVIEWED_RULINGS")
    result, seen = [], set()
    for record in records:
        _fields(record, ("receipt", "review"))
        receipt = validate_receipt(record["receipt"])
        review = record["review"]
        _fields(review, ("review_id", "reviewer", "receipt_sha256", "code"), ("source_refs", "rationale"))
        source_refs = _ids(review.get("source_refs", []))
        rationale = review.get("rationale", "")
        if type(rationale) is not str or bool(source_refs) != bool(rationale.strip()):
            raise ValueError("INVALID_RULING_REVIEW_EVIDENCE")
        if review["code"] != "ACCEPTED" or any(
            type(review[key]) is not str or not review[key].strip() for key in ("review_id", "reviewer")
        ):
            raise ValueError("RULING_REQUIRES_EXPLICIT_REVIEW")
        digest = _request_id(receipt)
        if review["receipt_sha256"] != digest:
            raise ValueError("STALE_RULING_REVIEW")
        payload, assertion = receipt["request"], Assertion(**receipt["assertion"])
        model_input(payload)  # The real wire contract validates definition, scaffold, and typed domains.
        bank = payload["bank"]
        schema = {
            "type": "object",
            "properties": {bank: {"type": ["integer", "null"], "enum": [*payload["allowed_values"], None]}},
            "required": [bank],
            "additionalProperties": False,
        }
        if (
            receipt["entry_id"] != payload["entry_id"]
            or receipt["request_id"] != _request_id(payload)
            or assertion.bank != bank
            or assertion.value not in payload["allowed_values"]
            or bank in payload["known"]
            or _canonical_json(receipt["schema"]) != _canonical_json(schema)
        ):
            raise ValueError("REVIEWED_RULING_REQUEST_MISMATCH")
        if receipt["request_id"] in seen:
            raise ValueError("DUPLICATE_REVIEWED_REQUEST")
        seen.add(receipt["request_id"])
        result.append(
            ReviewedRuling(
                receipt["entry_id"],
                bank,
                assertion.value,
                receipt["request_id"],
                assertion.source,
                review["review_id"],
                review["reviewer"],
                digest,
                receipt,
                source_refs,
                rationale,
            )
        )
    return tuple(sorted(result, key=lambda row: (row.entry_id, row.bank, row.request_id)))


def _ruling_reference(row):
    return {key: value for key, value in asdict(row).items() if key != "receipt"}


def _baseline_witness(baseline, bank, relations):
    return {
        "kind": "BASELINE_CLOSURE",
        "bank": bank,
        "value": baseline.assignments[bank],
        "baseline_sha256": _request_id({"relations": [asdict(rule) for rule in relations]}),
        "proof_trace": baseline.trace,
    }


def propose_patterns(
    rulings, *, discovery_entry_ids, audit_entry_ids, candidates=None, baselines=None, relations=()
) -> tuple[Pattern, ...]:
    """Observe pair implications; never use counts to approve a lexical rule."""
    discovery, audit = _ids(discovery_entry_ids), _ids(audit_entry_ids)
    if set(discovery) & set(audit):
        raise ValueError("DISCOVERY_AUDIT_ID_OVERLAP")
    grouped = {entry: defaultdict(list) for entry in discovery}
    for row in rulings:
        if row.entry_id in grouped:
            grouped[row.entry_id][row.bank].append(row)
    generated = set()
    if candidates is None:
        for entry, banks in grouped.items():
            singletons = [
                (bank, next(iter(values)))
                for bank, rows in banks.items()
                if len(values := {row.value for row in rows}) == 1
            ]
            generated.update((*left, *right) for left, right in permutations(singletons, 2))
            baseline = baselines.get(entry) if baselines is not None else None
            if baseline is not None and baseline.code != "CONFLICT":
                # Native-only discovery has its own evidence path. Here a new
                # teaching result can propose consequences of an existing proof.
                generated.update(
                    (left, value, *right)
                    for left, value in baseline.assignments.items()
                    if left not in banks
                    for right in singletons
                    if left != right[0]
                )
    else:
        if type(candidates) is not list:
            raise ValueError("INVALID_PATTERN_CANDIDATES")
        for candidate in candidates:
            if (
                type(candidate) is not list
                or len(candidate) != 4
                or any(type(candidate[i]) is not str or candidate[i] not in BANKS for i in (0, 2))
                or candidate[0] == candidate[2]
                or any(type(candidate[i]) is not int or candidate[i] not in (-1, 0, 1) for i in (1, 3))
            ):
                raise ValueError("INVALID_PATTERN_CANDIDATE")
            generated.add(tuple(candidate))
    patterns = []
    for left, a, right, b in sorted(generated):
        records = []
        for entry, banks in grouped.items():
            left_values = {row.value for row in banks[left]}
            right_values = {row.value for row in banks[right]}
            witness, baseline_code = None, None
            baseline = baselines.get(entry) if baselines is not None else None
            if not left_values and baseline is not None:
                if baseline.code == "CONFLICT":
                    baseline_code = "BASELINE_CONFLICT"
                elif left in baseline.assignments:
                    left_values = {baseline.assignments[left]}
                    witness = _baseline_witness(baseline, left, relations)
            code = (
                baseline_code
                if baseline_code is not None
                else "ANTECEDENT_CONFLICT"
                if len(left_values) > 1
                else "ANTECEDENT_UNKNOWN"
                if not left_values
                else "PREMISE_NOT_MET"
                if left_values != {a}
                else "CONSEQUENT_CONFLICT"
                if len(right_values) > 1
                else "CONSEQUENT_UNKNOWN"
                if not right_values
                else "OBSERVED_AGREEMENT"
                if right_values == {b}
                else "OBSERVED_COUNTEREXAMPLE"
            )
            records.append(
                {
                    "entry_id": entry,
                    "code": code,
                    "rulings": [_ruling_reference(row) for row in banks[left] + banks[right]],
                    **({"premise_witness": witness} if witness is not None else {}),
                }
            )
        provenance = tuple(
            sorted(
                {
                    f"review:{row.review_id}:{row.receipt_sha256}"
                    for row in rulings
                    if row.entry_id in discovery and row.bank in (left, right)
                }
            )
        )
        rule = Relation(
            "reviewed-pattern:" + _request_id({"antecedent": [left, a], "consequent": [right, b]}),
            (left, right),
            tuple((x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if x != a or y == b),
            provenance,
            authority="conditional",
            approved=False,
        )
        patterns.append(Pattern(rule, (left, a), (right, b), discovery, audit, tuple(records)))
    return tuple(patterns)


def _relation(record):
    _fields(
        record,
        ("rule_id", "banks", "allowed_rows", "provenance"),
        ("authority", "approved", "guards", "absent_evidence"),
    )
    result = dict(record)
    for name in ("banks", "allowed_rows", "provenance", "guards", "absent_evidence"):
        if name not in result:
            continue
        if type(result[name]) is not list:
            raise ValueError("INVALID_PATTERN_RELATION")
        if name in {"allowed_rows", "guards"} and any(type(value) is not list for value in result[name]):
            raise ValueError("INVALID_PATTERN_RELATION_ROW")
        result[name] = (
            tuple(tuple(value) for value in result[name]) if name in {"allowed_rows", "guards"} else tuple(result[name])
        )
    return Relation(**result)


def _discovery_consequent(entry, bank, relations, rulings, native_premises):
    """Reuse a proven baseline conclusion without inventing a model ruling.

    Discovery may learn from previously admitted laws. Independent audits use
    their separate baseline and still require an open target and a direct call.
    """
    values = {row.value for row in rulings if row.entry_id == entry.definition.entry_id and row.bank == bank}
    if values or not native_premises:
        return values, None, None
    baseline = resolve_dictionary(
        BANKS,
        entry.assertions,
        relations,
        entry.context,
        evidence_banks=entry.evidence_banks,
        domain_restrictions=entry.restrictions,
    )
    if baseline.code == "CONFLICT":
        return set(), None, "BASELINE_CONFLICT"
    if bank not in baseline.assignments:
        return set(), None, None
    return {baseline.assignments[bank]}, _baseline_witness(baseline, bank, relations), None


def guarded_patterns(
    records, *, discovery_entry_ids, audit_entry_ids, entries, rulings, relations=(), native_premises=False
):
    """Explicit scoped proposals with supplied warrants; never infer approval."""
    from .grounded_rules import MAX_PREMISES, implication_rows

    discovery, audit = _ids(discovery_entry_ids), _ids(audit_entry_ids)
    if set(discovery) & set(audit):
        raise ValueError("DISCOVERY_AUDIT_ID_OVERLAP")
    if type(records) is not list:
        raise ValueError("INVALID_GUARDED_PATTERN_CANDIDATES")
    patterns, seen = [], set()
    for record in records:
        _fields(record, ("consequent", "guards", "absent_evidence", "warrant"), ("antecedent", "premises"))
        if ("antecedent" in record) == ("premises" in record):
            raise ValueError("PATTERN_REQUIRES_ONE_PREMISE_FORM")
        left, right = record.get("antecedent"), record["consequent"]
        premises = record.get("premises", [] if left is None else [left])
        conjunctive = "premises" in record
        if conjunctive and (
            not native_premises or type(premises) is not list or not 2 <= len(premises) <= MAX_PREMISES
        ):
            raise ValueError("INVALID_CONJUNCTIVE_PATTERN_PREMISES")
        for pair in [*premises, right]:
            if (
                type(pair) is not list
                or len(pair) != 2
                or type(pair[0]) is not str
                or pair[0] not in BANKS
                or type(pair[1]) is not int
                or pair[1] not in (-1, 0, 1)
            ):
                raise ValueError("INVALID_GUARDED_PATTERN_COORDINATE")
        banks = [pair[0] for pair in [*premises, right]]
        if len(set(banks)) != len(banks):
            raise ValueError("INVALID_GUARDED_PATTERN_COORDINATE")
        warrant = record["warrant"]
        _fields(
            warrant,
            ("warrant_id", "kind", "source_refs", "statement", "review_id", "reviewer"),
            ("required_exception_ids", "required_reservation_ids"),
        )
        if (
            warrant["kind"] not in {"DEFINITIONAL_DERIVATION", "APPROVED_GSE_CONVENTION"}
            or any(
                type(warrant[key]) is not str or not warrant[key].strip()
                for key in ("warrant_id", "statement", "review_id", "reviewer")
            )
            or not _ids(warrant["source_refs"])
        ):
            raise ValueError("EXPLICIT_CAUSAL_WARRANT_REQUIRED")
        for key in ("required_exception_ids", "required_reservation_ids"):
            if key in warrant:
                exclusions = _ids(warrant[key])
                if not exclusions or set(exclusions) & (set(discovery) | set(audit)):
                    raise ValueError("INVALID_REQUIRED_REVISION_EXCEPTIONS")
        if not premises and not record["guards"]:
            raise ValueError("UNARY_PATTERN_REQUIRES_TYPED_GUARD")
        allowed = [list(row) for row in implication_rows(premises, right)]
        relation = _relation(
            {
                "rule_id": "reviewed-guarded-pattern:" + _request_id(record),
                "banks": banks,
                "allowed_rows": allowed,
                "provenance": [f"warrant:{warrant['warrant_id']}:{_request_id(warrant)}", *warrant["source_refs"]],
                "authority": "conditional",
                "approved": False,
                "guards": record["guards"],
                "absent_evidence": record["absent_evidence"],
            }
        )
        from .foundation import EXCEPTION_GUARD_PREFIX

        if any(
            key.startswith(EXCEPTION_GUARD_PREFIX) or not valid_lexical_guard(key, value)
            for key, value in relation.guards
        ):
            raise ValueError("UNSUPPORTED_PATTERN_CONTEXT")
        if any(bank not in BANKS for bank in relation.absent_evidence):
            raise ValueError("UNKNOWN_PATTERN_EVIDENCE_BANK")
        if relation.rule_id in seen:
            raise ValueError("DUPLICATE_GUARDED_PATTERN")
        seen.add(relation.rule_id)
        pattern = Pattern(
            relation,
            tuple(left) if left else None,
            tuple(right),
            discovery,
            audit,
            (),
            dict(warrant),
            tuple(tuple(pair) for pair in premises) if conjunctive else (),
        )
        observed = []
        for entry_id in discovery:
            entry = entries[entry_id]
            applicable = _applicability(relation, entry)
            values, consequent_witness, consequent_code = _discovery_consequent(
                entry, right[0], relations, rulings, native_premises
            )
            if conjunctive:
                baseline, _, code = _antecedent_state(pattern, entry, relations, rulings)
                witnesses = [
                    _baseline_witness(baseline, bank, relations)
                    for bank, value in pattern.premises
                    if baseline.assignments.get(bank) == value
                ]
                observed.append(
                    {
                        "entry_id": entry_id,
                        "code": (
                            code
                            if code != "READY"
                            else consequent_code
                            if consequent_code is not None
                            else "CONSEQUENT_CONFLICT"
                            if len(values) > 1
                            else "CONSEQUENT_UNKNOWN"
                            if not values
                            else "OBSERVED_AGREEMENT"
                            if values == {right[1]}
                            else "OBSERVED_COUNTEREXAMPLE"
                        ),
                        "rulings": [
                            _ruling_reference(row)
                            for row in rulings
                            if row.entry_id == entry_id and row.bank == right[0]
                        ],
                        "premise_witnesses": witnesses,
                        **({"consequent_witness": consequent_witness} if consequent_witness is not None else {}),
                    }
                )
                continue
            premises = {
                row.value for row in rulings if left is not None and row.entry_id == entry_id and row.bank == left[0]
            }
            witness, baseline_code = None, None
            if native_premises and applicable == "READY" and left is not None and not premises:
                baseline = _baseline(pattern, entry, relations)
                if baseline.code == "CONFLICT":
                    baseline_code = "BASELINE_CONFLICT"
                elif left[0] in baseline.assignments:
                    premises = {baseline.assignments[left[0]]}
                    witness = _baseline_witness(baseline, left[0], relations)
            code = (
                applicable
                if applicable != "READY"
                else baseline_code
                if baseline_code is not None
                else "ANTECEDENT_CONFLICT"
                if len(premises) > 1
                else "ANTECEDENT_UNKNOWN"
                if left is not None and not premises
                else "PREMISE_NOT_MET"
                if left is not None and premises != {left[1]}
                else consequent_code
                if consequent_code is not None
                else "CONSEQUENT_CONFLICT"
                if len(values) > 1
                else "CONSEQUENT_UNKNOWN"
                if not values
                else "OBSERVED_AGREEMENT"
                if values == {right[1]}
                else "OBSERVED_COUNTEREXAMPLE"
            )
            observed.append(
                {
                    "entry_id": entry_id,
                    "code": code,
                    "rulings": [
                        _ruling_reference(row)
                        for row in rulings
                        if row.entry_id == entry_id and row.bank in relation.banks
                    ],
                    **({"premise_witness": witness} if witness is not None else {}),
                    **({"consequent_witness": consequent_witness} if consequent_witness is not None else {}),
                }
            )
        patterns.append(replace(pattern, records=tuple(observed)))
    return tuple(patterns)


def _applicability(relation, entry):
    context = lexical_context(entry.definition, entry.observations, (relation,))
    if any(context.get(key) != value for key, value in relation.guards):
        return "GUARD_NOT_MET"
    if set(relation.absent_evidence) & set(entry.evidence_banks):
        return "RELEVANT_EVIDENCE_PRESENT"
    return "READY"


def _definition_input(raw, relations=()):
    _fields(raw, ("definition", "assertions", "anchors", "observations", "domain_restrictions", "context"))
    _fields(raw["definition"], ("entry_id", "lemma", "pos", "definition"), ("source_ids",))
    definition_data = dict(raw["definition"])
    source_ids = definition_data.get("source_ids", [])
    _ids(source_ids)
    definition_data["source_ids"] = tuple(source_ids)
    definition = Definition(**definition_data)
    for key in ("assertions", "anchors", "observations", "domain_restrictions"):
        if type(raw[key]) is not list:
            raise ValueError("INVALID_PATTERN_INPUT_SEQUENCE")
    observations, links, relevance = [], {}, set()
    for record in raw["observations"]:
        _fields(record, ("entry_id", "source", "record_id", "family", "features", "scope"), ("candidate_entry_ids",))
        native = dict(record)
        candidates = native.get("candidate_entry_ids", [])
        _ids(candidates)
        native["candidate_entry_ids"] = tuple(candidates)
        observation = Observation(**native)
        if observation.source.startswith(("model:", "rule:", "derived:")) or observation.family in {"model", "derived"}:
            raise ValueError("UNSUPPORTED_PRIOR_MODEL_OR_DERIVED_BASELINE")
        targets = (observation.entry_id,) if observation.entry_id is not None else observation.candidate_entry_ids
        if definition.entry_id not in targets:
            raise ValueError("PATTERN_SOURCE_DEFINITION_MISMATCH")
        key = (observation.source, observation.record_id)
        if key in links:
            raise ValueError("DUPLICATE_PATTERN_SOURCE_RECORD")
        links[key] = observation
        relevance.update(observation_relevance(observation))
        observations.append(asdict(observation))
    # Baseline context is derived only from its own rules and exact source
    # records. A proposed guard cannot retroactively alter a saved request.
    context = lexical_context(definition, observations, relations)
    if raw["context"] != context:
        raise ValueError("UNSUPPORTED_PATTERN_CONTEXT")
    assertions, restrictions = [], []
    for kind in ("assertions", "anchors", "domain_restrictions"):
        for record in raw[kind]:
            coordinate = "allowed_values" if kind == "domain_restrictions" else "value"
            _fields(record, ("bank", coordinate, "source", "record_id", "family"), ("scope",))
            item = dict(record)
            if kind == "domain_restrictions":
                if type(item["allowed_values"]) is not list:
                    raise ValueError("INVALID_PATTERN_RESTRICTION_VALUES")
                item["allowed_values"] = tuple(item["allowed_values"])
                value = DomainRestriction(**item)
            else:
                value = Assertion(**item)
            if value.source.startswith(("model:", "rule:", "derived:")) or value.family in {"model", "derived"}:
                raise ValueError("UNSUPPORTED_PRIOR_MODEL_OR_DERIVED_BASELINE")
            validate_assertion_competence(value)
            if kind != "anchors":
                link = links.get((value.source, value.record_id))
                if (
                    link is None
                    or link.entry_id != definition.entry_id
                    or link.scope != "lexical"
                    or link.family != value.family
                ):
                    raise ValueError("PATTERN_ASSERTION_PROVENANCE_MISMATCH")
            (restrictions if kind == "domain_restrictions" else assertions).append(value)
    return DefinitionInput(
        definition,
        tuple(assertions),
        tuple(observations),
        tuple(restrictions),
        context,
        tuple(sorted(relevance)),
    )


def _same_table(left, right):
    if set(left.banks) != set(right.banks):
        return False
    order = tuple(right.banks.index(bank) for bank in left.banks)
    return set(left.allowed_rows) == {tuple(row[i] for i in order) for row in right.allowed_rows}


def _input_rule_history(raw, relations, rulings, entries):
    """Verify exported rule versions without opening a database or trusting labels.

    Only selected, explicitly reviewed receipt bindings are carried. The same
    unaffected-scope law as database replay determines
    whether an old request can still supply active evidence.
    """
    from .rule_history import digest, receipt_binding_key, receipt_relations, relation_records

    if raw is None:
        return None
    _fields(raw, ("format", "current_version", "versions", "bindings"))
    if (
        raw["format"] not in {"gse.reviewed-pattern-history/1", "gse.reviewed-pattern-history/2"}
        or type(raw["versions"]) is not list
        or type(raw["bindings"]) is not list
    ):
        raise ValueError("INVALID_PATTERN_RULE_HISTORY")
    current_version = digest(relation_records(relations))
    if raw["current_version"] != current_version:
        raise ValueError("CURRENT_RULE_VERSION_MISMATCH")
    versions = {}
    for version in raw["versions"]:
        _fields(version, ("version", "relations"))
        key = version["version"]
        if type(key) is not str or type(version["relations"]) is not list:
            raise ValueError("INVALID_PATTERN_RULE_VERSION")
        if key in versions:
            raise ValueError("DUPLICATE_PATTERN_RULE_VERSION")
        parsed = tuple(_relation(rule) for rule in version["relations"])
        if digest(version["relations"]) != key or digest(relation_records(parsed)) != key:
            raise ValueError("RULE_VERSION_HASH_MISMATCH")
        versions[key] = parsed
    if current_version not in versions or versions[current_version] != relations:
        raise ValueError("CURRENT_RULE_VERSION_MISMATCH")
    by_id = {row.request_id: row for row in rulings}
    bindings = {}
    seen_requests = set()
    for binding in raw["bindings"]:
        _fields(binding, ("request_id", "entry_id", "version", "receipt_sha256"))
        if any(type(value) is not str or not value for value in binding.values()):
            raise ValueError("INVALID_PATTERN_RULE_BINDING")
        request_id = binding["request_id"]
        if request_id in seen_requests:
            raise ValueError("DUPLICATE_PATTERN_RULE_BINDING")
        if request_id not in by_id or binding["version"] not in versions:
            raise ValueError("UNKNOWN_PATTERN_RULE_BINDING")
        key = (request_id, binding["receipt_sha256"])
        ruling = by_id[request_id]
        if key != receipt_binding_key(ruling.receipt) or binding["entry_id"] != ruling.entry_id:
            raise ValueError("MODEL_RULE_BINDING_MISMATCH")
        seen_requests.add(request_id)
        bindings[key] = (binding["entry_id"], binding["version"])
    if set(versions) != {current_version, *(binding[1] for binding in bindings.values())}:
        raise ValueError("UNUSED_PATTERN_RULE_VERSION")
    history = {
        "versions": versions,
        "bindings": bindings,
        "allow_revisions": raw["format"] == "gse.reviewed-pattern-history/2",
    }
    for request_id, _ in bindings:
        ruling = by_id[request_id]
        entry = entries[ruling.entry_id]
        receipt_relations(
            ruling.receipt, relations, None, history, definition=entry.definition, observations=entry.observations
        )
    return history


def _baseline(pattern, entry, relations):
    # Equal sign tables can govern disjoint lexical populations. Only an
    # applicable equivalent table leaks the proposed answer into this audit;
    # an exact rule-ID collision remains invalid regardless of applicability.
    if any(
        rule.rule_id == pattern.relation.rule_id
        or _same_table(pattern.relation, rule)
        and _applicability(rule, entry) == "READY"
        for rule in relations
    ):
        raise ValueError("TESTED_RULE_PRESENT_IN_BASELINE")
    return resolve_dictionary(
        BANKS,
        entry.assertions,
        relations,
        entry.context,
        evidence_banks=entry.evidence_banks,
        domain_restrictions=entry.restrictions,
    )


def _antecedent_state(pattern, entry, relations, rulings):
    baseline = _baseline(pattern, entry, relations)
    if baseline.code == "CONFLICT":
        return baseline, entry.assertions, "BASELINE_CONFLICT"
    applicable = _applicability(pattern.relation, entry)
    if applicable != "READY":
        return baseline, entry.assertions, applicable
    if pattern.premises:
        if any(
            bank in baseline.assignments and baseline.assignments[bank] != value for bank, value in pattern.premises
        ):
            return baseline, entry.assertions, "PREMISE_NOT_MET"
        if any(bank not in baseline.assignments for bank, _ in pattern.premises):
            return baseline, entry.assertions, "ANTECEDENT_UNKNOWN"
        return baseline, entry.assertions, "READY"
    if pattern.antecedent is None:
        return baseline, entry.assertions, "READY"
    left, expected = pattern.antecedent
    if left in baseline.assignments:
        return baseline, entry.assertions, "READY" if baseline.assignments[left] == expected else "PREMISE_NOT_MET"
    relevant = [row for row in rulings if row.entry_id == entry.definition.entry_id and row.bank == left]
    if not relevant:
        return baseline, entry.assertions, "ANTECEDENT_UNKNOWN"
    if len({row.value for row in relevant}) != 1:
        return baseline, entry.assertions, "ANTECEDENT_CONFLICT"
    if relevant[0].value != expected:
        return baseline, entry.assertions, "PREMISE_NOT_MET"
    replayed = []
    for row in relevant:
        state, assertions, code = _replay_prefix(pattern, entry, relations, rulings, row, baseline)
        if code != "READY":
            return baseline, entry.assertions, code
        replayed.append((state, assertions))
    return *replayed[0], "READY"


def _replay_prefix(pattern, entry, relations, rulings, row, baseline):
    """Reconstruct the exact ordered model prefix from explicitly reviewed receipts.

    No dependency is dropped and no stored model cell is treated as native.
    Each intermediate request is regenerated, so a missing/transposed ancestor,
    stale relation set or changed native context cannot silently pass.
    """
    by_id = {item.request_id: item for item in rulings if item.entry_id == entry.definition.entry_id}
    dependencies = [
        record
        for record in row.receipt["request"]["scaffold"]["proof_trace"]
        if record.get("kind") == "ASSERTION"
        and (record.get("family") == "model" or str(record.get("source", "")).startswith("model:"))
    ]
    ordered, seen = [], set()
    for dependency in dependencies:
        identity = dependency.get("record_id")
        ancestor = by_id.get(identity)
        if ancestor is None:
            return baseline, entry.assertions, "UNSUPPORTED_PRIOR_MODEL_DEPENDENCY"
        if identity == row.request_id or identity in seen:
            return baseline, entry.assertions, "INVALID_REVIEWED_DEPENDENCY_ORDER"
        if {key: dependency.get(key) for key in ancestor.receipt["assertion"]} != ancestor.receipt["assertion"]:
            return baseline, entry.assertions, "REVIEWED_DEPENDENCY_ASSERTION_MISMATCH"
        seen.add(identity)
        ordered.append(ancestor)

    # Resolver traces are canonical bank order, not acceptance order. Rebuild
    # the chronological prefix from each receipt's own dependency set. A real
    # incremental receipt prefix is nested; do not silently invent an order for
    # independent or cyclic histories that cannot reconstruct that prefix.
    def prior_ids(item):
        return {
            record.get("record_id")
            for record in item.receipt["request"]["scaffold"]["proof_trace"]
            if record.get("kind") == "ASSERTION"
            and (record.get("family") == "model" or str(record.get("source", "")).startswith("model:"))
        }

    ordered.sort(key=lambda item: (len(prior_ids(item)), item.request_id))
    ordered.append(row)
    assertions, state = entry.assertions, baseline
    replayed_ids = set()
    for current in ordered:
        payload = current.receipt["request"]
        if pattern.consequent[0] in payload["known"] or current.bank == pattern.consequent[0]:
            return baseline, entry.assertions, "TARGET_LEAKAGE_IN_ANTECEDENT_REQUEST"
        if prior_ids(current) != replayed_ids:
            return baseline, entry.assertions, "INVALID_REVIEWED_DEPENDENCY_ORDER"
        from .rule_history import receipt_relations

        historical = receipt_relations(
            current.receipt,
            relations,
            None,
            entry.rule_history,
            definition=entry.definition,
            observations=entry.observations,
        )
        historical_context = lexical_context(entry.definition, entry.observations, historical)
        state = resolve_dictionary(
            BANKS,
            assertions,
            historical,
            historical_context,
            evidence_banks=entry.evidence_banks,
            domain_restrictions=entry.restrictions,
        )
        fresh = build_request(
            entry.definition.entry_id,
            current.bank,
            state,
            entry.observations,
            definition=entry.definition,
            relations=historical,
            context=historical_context,
            request_format=payload["format"],
        )
        if fresh.request_id != current.request_id:
            return baseline, entry.assertions, "ANTECEDENT_BASELINE_MISMATCH"
        replay = complete_bank(
            fresh,
            BANKS,
            assertions,
            historical,
            _ReviewedAnswer(current),
            historical_context,
            evidence_banks=entry.evidence_banks,
            domain_restrictions=entry.restrictions,
        )
        if replay.code != "ASSIGNED" or replay.assertion is None or replay.resolution is None:
            return baseline, entry.assertions, "ANTECEDENT_CONTRADICTION"
        assertions += (replay.assertion,)
        state = replay.resolution
        replayed_ids.add(current.request_id)
    state = resolve_dictionary(
        BANKS,
        assertions,
        relations,
        entry.context,
        evidence_banks=entry.evidence_banks,
        domain_restrictions=entry.restrictions,
    )
    if state.code == "CONFLICT":
        return baseline, entry.assertions, "ANTECEDENT_CONTRADICTION"
    return state, assertions, "READY"


class _ReviewedAnswer:
    """Replay a pinned accepted answer through the ordinary acceptance checks."""

    def __init__(self, ruling):
        self.identity = ruling.source.removeprefix("model:")
        self.raw = _canonical_json({ruling.bank: ruling.value})

    def __call__(self, payload, schema):
        return self.raw


def stage_pattern(pattern, entry, relations, rulings):
    """Temporarily test one conditional relation; return no approved relation."""
    baseline, assertions, code = _antecedent_state(pattern, entry, relations, rulings)
    result = {"entry_id": entry.definition.entry_id, "code": code, "writes": False}
    if code != "READY":
        return result
    if not pattern.relation.provenance:
        return {**result, "code": "NO_REVIEWED_PATTERN_PROVENANCE"}
    staged_relations = relations + (replace(pattern.relation, approved=True),)
    staged = resolve_dictionary(
        BANKS,
        assertions,
        staged_relations,
        lexical_context(entry.definition, entry.observations, staged_relations),
        evidence_banks=entry.evidence_banks,
        domain_restrictions=entry.restrictions,
    )
    previous = [record for record in baseline.trace if record["kind"] == "CONDITIONAL_EXCEPTION"]
    previous_keys = {_canonical_json(record) for record in previous}
    exceptions = [
        record
        for record in staged.trace
        if record["kind"] == "CONDITIONAL_EXCEPTION" and _canonical_json(record) not in previous_keys
    ]
    return {
        **result,
        "code": "STAGED_CONFLICT" if staged.code == "CONFLICT" else "STAGED_EXCEPTION" if exceptions else "STAGED_ONLY",
        "changed_domains": {
            bank: {"before": sorted(baseline.domains[bank]), "after": sorted(domain)}
            for bank, domain in staged.domains.items()
            if domain != baseline.domains[bank]
        },
        "conditional_exceptions": exceptions,
        "baseline_conditional_exceptions": previous,
        "conflicts": staged.conflicts,
        "production_rule_approved": False,
    }


class _CapturedTransport:
    def __init__(self, transport):
        self.transport, self.identity, self.raw = transport, transport.identity, None
        self.calls = 0

    def __call__(self, payload, schema):
        self.calls += 1
        self.raw = self.transport(payload, schema)
        return self.raw


def audit_pattern(pattern, entry, relations, rulings, transport=None, *, allow_call=False):
    """Ask only the withheld target using baseline closure, never staged answers."""
    if entry.definition.entry_id not in pattern.audit_entry_ids:
        raise ValueError("AUDIT_DEFINITION_NOT_HELD_OUT")
    baseline, assertions, code = _antecedent_state(pattern, entry, relations, rulings)
    result = {
        "entry_id": entry.definition.entry_id,
        "bank": pattern.consequent[0],
        "code": code,
        "model_calls": 0,
        "comparison_authority": "UNAPPROVED_PATTERN_NOT_GOLD",
    }
    if code != "READY":
        return result
    bank, expected = pattern.consequent
    if bank in baseline.assignments:
        return {**result, "code": "SYMBOLICALLY_RESOLVED_PREEXISTING", "value": baseline.assignments[bank]}
    request = build_request(
        entry.definition.entry_id,
        bank,
        baseline,
        entry.observations,
        definition=entry.definition,
        relations=relations,
        context=entry.context,
    )
    result.update(request=request.payload(), schema=request.output_schema(), request_id=request.request_id)
    if not allow_call or transport is None:
        return {**result, "code": "AUDIT_CALL_BUDGET_EXHAUSTED"}
    captured = _CapturedTransport(transport)
    completion = complete_bank(
        request,
        BANKS,
        assertions,
        relations,
        captured,
        entry.context,
        evidence_banks=entry.evidence_banks,
        domain_restrictions=entry.restrictions,
    )
    if completion.code == "ASSIGNED":
        assert completion.assertion is not None
        value = completion.assertion.value
        code = "MODEL_AGREEMENT" if value == expected else "MODEL_COUNTEREXAMPLE"
        result["value"] = value
        result["accepted_assertion"] = asdict(completion.assertion)
    else:
        code = {"ABSTAINED": "MODEL_ABSTAINED", "CONTRADICTION": "MODEL_CONFLICT"}.get(completion.code, completion.code)
    return {
        **result,
        "code": code,
        "model_calls": captured.calls,
        "details": completion.details,
        "raw_output": captured.raw,
        "transport_identity": captured.identity,
        "proposed_value": expected,
        "writes": False,
    }


def run_workflow(path: str | Path, transport=None, *, max_calls=0):
    """Strict file-based proposal/staging/audit; never opens a lexicon database."""
    if type(max_calls) is not int or max_calls < 0:
        raise ValueError("INVALID_PATTERN_CALL_BUDGET")
    return run_workflow_input(read_json(path), transport, max_calls=max_calls)


def run_workflow_input(raw: dict, transport=None, *, max_calls=0):
    """Run the same strict workflow over an embedded input without filesystem I/O."""
    if type(max_calls) is not int or max_calls < 0:
        raise ValueError("INVALID_PATTERN_CALL_BUDGET")
    _fields(
        raw,
        ("format", "rulings", "discovery_entry_ids", "audit_entry_ids", "entries", "relations"),
        ("candidates", "guarded_candidates", "rule_history"),
    )
    if (
        type(raw["format"]) is not str
        or raw["format"] not in {INPUT_FORMAT, LEGACY_INPUT_FORMAT}
        or type(raw["entries"]) is not list
        or type(raw["relations"]) is not list
    ):
        raise ValueError("INVALID_PATTERN_INPUT_FORMAT")
    native_premises = raw["format"] == INPUT_FORMAT
    rulings = reviewed_rulings(raw["rulings"])
    relations = tuple(_relation(record) for record in raw["relations"])
    entries = {}
    for record in raw["entries"]:
        entry = _definition_input(record, relations)
        if entry.definition.entry_id in entries:
            raise ValueError("DUPLICATE_PATTERN_DEFINITION")
        entries[entry.definition.entry_id] = entry
    baselines = (
        {
            key: resolve_dictionary(
                BANKS,
                entry.assertions,
                relations,
                entry.context,
                evidence_banks=entry.evidence_banks,
                domain_restrictions=entry.restrictions,
            )
            for key, entry in entries.items()
        }
        if native_premises
        else None
    )
    patterns = propose_patterns(
        rulings,
        discovery_entry_ids=raw["discovery_entry_ids"],
        audit_entry_ids=raw["audit_entry_ids"],
        candidates=raw.get("candidates", [] if "guarded_candidates" in raw else None),
        baselines=baselines,
        relations=relations,
    )
    requested = set(raw["discovery_entry_ids"]) | set(raw["audit_entry_ids"])
    if not requested <= entries.keys() or any(row.entry_id not in requested for row in rulings):
        raise ValueError("UNKNOWN_PATTERN_DEFINITION")
    history = _input_rule_history(raw.get("rule_history"), relations, rulings, entries)
    if history is not None:
        entries = {key: replace(entry, rule_history=history) for key, entry in entries.items()}
    patterns += guarded_patterns(
        raw.get("guarded_candidates", []),
        discovery_entry_ids=raw["discovery_entry_ids"],
        audit_entry_ids=raw["audit_entry_ids"],
        entries=entries,
        rulings=rulings,
        relations=relations,
        native_premises=native_premises,
    )
    for row in rulings:
        definition = entries[row.entry_id].definition
        exact = {key: getattr(definition, key) for key in ("entry_id", "lemma", "pos", "definition")}
        if row.receipt["request"]["definition"] != exact:
            raise ValueError("REVIEWED_RULING_DEFINITION_MISMATCH")
    for entry in entries.values():
        resolve_dictionary(
            BANKS,
            entry.assertions,
            relations,
            entry.context,
            evidence_banks=entry.evidence_banks,
            domain_restrictions=entry.restrictions,
        )
    calls, reports = 0, []
    for pattern in patterns:
        stages, audits = [], []
        for entry_id in pattern.audit_entry_ids:
            entry = entries[entry_id]
            stages.append(stage_pattern(pattern, entry, relations, rulings))
            audit = audit_pattern(pattern, entry, relations, rulings, transport, allow_call=calls < max_calls)
            calls += audit["model_calls"]
            audits.append(audit)
        reports.append(
            {
                "relation": asdict(pattern.relation),
                "antecedent": pattern.antecedent,
                **({"premises": pattern.premises} if pattern.premises else {}),
                "consequent": pattern.consequent,
                "proposal_kind": "GUARDED_WARRANTED_PROPOSAL" if pattern.warrant else "OBSERVED_PAIR",
                "warrant": pattern.warrant,
                "warrant_sha256": _request_id(pattern.warrant) if pattern.warrant else None,
                "discovery_entry_ids": pattern.discovery_entry_ids,
                "audit_entry_ids": pattern.audit_entry_ids,
                "discovery": pattern.records,
                "discovery_outcomes": dict(Counter(record["code"] for record in pattern.records)),
                "staging": stages,
                "audits": audits,
                "audit_outcomes": dict(Counter(record["code"] for record in audits)),
                "admission": "UNAPPROVED_CANDIDATE",
            }
        )
    audit_requests = defaultdict(list)
    for report in reports:
        for audit in report["audits"]:
            if "request_id" in audit:
                audit_requests[audit["request_id"]].append((report["relation"]["rule_id"], audit["model_calls"]))
    guards = {key for rule in (*relations, *(p.relation for p in patterns)) for key, _ in rule.guards}
    if any(key.startswith(NATIVE_FRAME_PREFIX) for key in guards):
        context_limit = "CONTEXT_BEYOND_POS_AND_EXACT_NATIVE_DEFINITION"
    elif guards - {"pos"}:
        context_limit = "CONTEXT_BEYOND_DEFINITION_POS_AND_EXACT_WORDNET_ANCESTRY"
    else:
        context_limit = "CONTEXT_BEYOND_DEFINITION_POS"
    return {
        "format": REPORT_FORMAT if native_premises else LEGACY_REPORT_FORMAT,
        "input_sha256": _request_id(raw),
        "model_calls": calls,
        "max_model_calls": max_calls,
        "discovery_entry_ids": raw["discovery_entry_ids"],
        "audit_entry_ids": raw["audit_entry_ids"],
        "candidates": reports,
        "repeated_audit_requests": [
            {
                "code": "REPEATED_AUDIT_REQUEST",
                "request_id": request_id,
                "candidate_rule_ids": [rule for rule, _ in items],
                "evaluations": len(items),
                "model_calls": sum(calls for _, calls in items),
            }
            for request_id, items in sorted(audit_requests.items())
            if len(items) > 1
        ],
        "lexicon_writes": False,
        "authority": (
            "REPLAYED_BASELINE_AND_EXPLICIT_REVIEWED_MODEL_RULINGS_NOT_INDEPENDENT_GOLD"
            if native_premises
            else "EXPLICIT_REVIEWED_MODEL_RULINGS_NOT_NATIVE_SOURCE_OR_INDEPENDENT_GOLD"
        ),
        "unsupported": [
            "UNREVIEWED_PRIOR_MODEL_DEPENDENCIES",
            context_limit,
            "AUTOMATIC_RULE_PROMOTION",
            "PRODUCTION_RULE_REPLAY_MIGRATION",
        ],
    }
