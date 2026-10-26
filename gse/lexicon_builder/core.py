"""Mask-aware, finite-domain foundation for a source-guided lexical definition.

This module deliberately does not use the dense curation database or the older
source-voting paths. A source adapter supplies *typed, certified observations*;
reviewed laws restrict the feasible vector. Unresolved coordinates stay open.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from itertools import product
from math import prod
from pathlib import Path
from typing import Any

from gse.lexicon_builder.basis import OPPOSITE_POLES, PRIME_TO_BANK, PRIMES


class Cell(StrEnum):
    """Definition states, not epistemic confidence or source availability.

    ZERO is explicit absence in an applicable unpaired domain (F118), or
    neither pole in an applicable bipolar domain. SILENT is not addressed.
    """

    SILENT = "empty"
    ZERO = "0"
    PLUS = "+1"
    MINUS = "-1"


_NEGATIVE_POLES = {negative: positive for positive, negative in OPPOSITE_POLES}
CANONICAL_COORDINATES = tuple(name for name in PRIMES if name not in _NEGATIVE_POLES)
_BIPOLAR_COORDINATES = {positive for positive, _ in OPPOSITE_POLES}
assert len(PRIMES) == 72 and len(CANONICAL_COORDINATES) == 58
assert "NUMBER" not in PRIMES and "NUMBER" not in CANONICAL_COORDINATES


def canonical_pole(name: str) -> tuple[str, int]:
    """Return the canonical coordinate and its pole's direction."""
    if name not in PRIMES:
        raise ValueError(f"not one of the 72 lexical primes: {name}")
    return (_NEGATIVE_POLES[name], -1) if name in _NEGATIVE_POLES else (name, 1)


def legal_domain(coordinate: str) -> frozenset[Cell]:
    """Unpaired primes have no negative state; silence differs from zero."""
    if coordinate not in CANONICAL_COORDINATES:
        raise ValueError(f"not a canonical lexical coordinate: {coordinate}")
    states = {Cell.SILENT, Cell.ZERO, Cell.PLUS}
    if coordinate in _BIPOLAR_COORDINATES:
        states.add(Cell.MINUS)
    return frozenset(states)


@dataclass(frozen=True)
class AtomicSeed:
    """A literal prime's signed coordinate, before combinatorial closure."""

    prime: str
    coordinate: str
    sign: Cell
    bank: int
    profile_status: str = "NEEDS_COMBINATORIAL_REVIEW"


def atomic_seed(prime: str) -> AtomicSeed:
    coordinate, pole = canonical_pole(prime)
    return AtomicSeed(prime, coordinate, Cell.PLUS if pole > 0 else Cell.MINUS, PRIME_TO_BANK[prime])


@dataclass(frozen=True)
class Observation:
    """One typed fact about one located reading; no prose or primitive vote."""

    reading_id: str
    source: str
    record_id: str
    field: str
    value: str
    certified: bool = False


@dataclass(frozen=True)
class Law:
    """Allowed states for one or more coordinates under a typed fact guard."""

    rule_id: str
    coordinates: tuple[str, ...]
    allowed: tuple[tuple[Cell, ...], ...]
    guard: tuple[tuple[str, str], ...]
    warrant: str
    tier: str = "FOUNDATIONAL"
    application_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("a law requires a nonempty rule ID")
        if self.application_id is not None and (
            not isinstance(self.application_id, str) or not self.application_id.strip()
        ):
            raise ValueError(f"{self.rule_id}: application ID must be a nonempty string")
        if not isinstance(self.tier, str) or self.tier not in {"FOUNDATIONAL", "CONDITIONAL", "MODEL_CANDIDATE"}:
            raise ValueError(f"{self.rule_id}: unknown rule tier")
        if not self.coordinates or len(set(self.coordinates)) != len(self.coordinates):
            raise ValueError(f"{self.rule_id}: coordinates must be distinct and nonempty")
        for coordinate in self.coordinates:
            legal_domain(coordinate)
        if not self.allowed:
            raise ValueError(f"{self.rule_id}: empty allowed relation")
        for row in self.allowed:
            if len(row) != len(self.coordinates):
                raise ValueError(f"{self.rule_id}: relation arity mismatch")
            if any(value not in legal_domain(coordinate) for coordinate, value in zip(self.coordinates, row)):
                raise ValueError(f"{self.rule_id}: illegal coordinate state")


# Recorded approvals retained at the v1 -> v2 admission migration. The IDs occur
# as founder-approved in d2c2e52; the hashes pin the reviewed migration records.
# Editing a record, including its authority or lifecycle, requires v2 validation.
LEGACY_APPROVAL_CONTRACTS = {
    "OWN_AFFECTIVE_FEELING": "8279bf6d0c509cb5c0c43e47eaadff3da341ee3bba13eee983ac5bf1d4ae20a0",
    "OWN_PHYSICAL_CHANGE_OF_PLACE": "f3ebf228110dacc67779c5f43a29b860c7d975112645aad359dad5d141193a30",
    "MODIFIER_LACKS_INDEPENDENT_OBJECTNESS": "595176bd46d84142969b02bb51a4504de4b874263f109cf8f23cf326382b1fa8",
    "FEELING_DENOTATUM_IS_NOT_A_CATEGORY": "50bc660da8d29169f4f3f6f557e0ec789d365a14c5493d7940e71f004a3e7d9e",
    "OWN_DEGREE_BEARING_CONTENT": "38476afaef09fa6ba7b0fe9344ec9f91ede6648f2a4cff166d39ebfe030cefb6",
    "MODIFIER_HEADS_NO_SUBSTANTIVE": "ab164dd7cff4871b86a0a381f9ee7791575154b90910272ae752b6af519a794a",
    "USAS_OWN_QUALITY_POLE": "9680dc7e769b61a292054e72d878f8edf56ef2bfa961d7731c2c14148179ce4c",
    "USAS_OWN_SIZE_POLE": "b8206b10871ee6b1bb49d35dc9cab8b8130d441ffeaec1606e01ed160ce7afe6",
    "EMOTION_FEAR_ADJ": "8efe741ec49e0d39b8669c33f37b4ff56119c27e501bebae75943a9cb7a104df",
    "VN_EVENT_MOTION": "3d2c5edbdfc8f833951660231874e355af5a772bafc27dca56315444569638ac",
    "VN_EVENT_CONTACT": "980f1101761a941bfe8e9edb23816cfcf45c73dfb9b3cdfa7ba9837ab3b8ebef",
    "VN_DESIRE": "444407b716c317e395ddaeec6eecd5cdcc3ac2b081e7192f14e175159dcb4e4d",
    "VN_VITALITY": "e3aa77bd85e29d434eaba6e54acd9ef75afda0496382a071f8498a44ba788935",
    "VN_POSSESSION": "f0ea9d61aa90b5a6c75e6cb38f7c0d9f00f0cf60fcc213c17dc6abdaf0687e0c",
    "VN_BEGIN": "0e4a0bf02ee5d5c93862ba8d87e04cccac061196c937f65bac4eda47de88025e",
    "VN_END": "87d32f58cbcd28ea480d80de14d0aaff159309a5cf87083122ec552126b3e7c3",
    "VN_USAS_PERCEPTION_MODE": "b332a63e7fab211f19ac9a3c0b7f69a96ee2dd92e1feafba7bfa48a55480e731",
}


def rule_contract_digest(record: dict) -> str:
    """Pin every rule field except the validation receipt itself."""
    contract = {key: value for key, value in record.items() if key != "validation"}
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _reference_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def _test_references(value: object) -> bool:
    if not isinstance(value, list) or not _reference_list(value):
        return False
    return all(
        ref.startswith("tests/")
        and ".." not in ref.split("/")
        and ".py::" in ref
        and ref.rsplit("::", 1)[-1].startswith("test_")
        for ref in value
    )


def rule_admission_reason(record: object) -> str:
    """Distinguish semantic-review admission from shape, lifecycle and stale receipts.

    A validation receipt records a reviewed contract and real intent-test node
    IDs. It is not produced by native association scores or by the builder's own
    answers. The release gate owns execution of the referenced tests.
    """
    if not isinstance(record, dict):
        return "MALFORMED_RULE"
    if not isinstance(record.get("rule_id"), str) or not record["rule_id"].strip():
        return "MALFORMED_RULE"
    if "may_write_lexical_cells" in record and not isinstance(record["may_write_lexical_cells"], bool):
        return "MALFORMED_RULE"
    if record.get("kind") == "NATIVE_ASSOCIATION" or record.get("may_write_lexical_cells") is False:
        return "NON_LEXICAL_RULE"
    lifecycle = record.get("lifecycle")
    if lifecycle is not None and lifecycle != "ACTIVE":
        return "RULE_NOT_ACTIVE"
    review_state = record.get("review_state")
    if not isinstance(review_state, str) or review_state not in {"FOUNDER_APPROVED", "SOURCE_JUSTIFIED"}:
        return "UNREVIEWED_RULE"
    try:
        digest = rule_contract_digest(record)
    except TypeError, ValueError:
        return "MALFORMED_RULE"
    if "validation" not in record and record.get("review_state") == "FOUNDER_APPROVED":
        rule_id = record.get("rule_id")
        legacy = LEGACY_APPROVAL_CONTRACTS.get(rule_id) if isinstance(rule_id, str) else None
        if legacy is None:
            return "UNRECORDED_FOUNDER_APPROVAL"
        return "ADMITTED_LEGACY_APPROVAL" if digest == legacy else "STALE_LEGACY_APPROVAL"
    if lifecycle != "ACTIVE":
        return "MISSING_RULE_LIFECYCLE"
    tier = record.get("tier")
    if not isinstance(tier, str) or tier not in {"FOUNDATIONAL", "CONDITIONAL"}:
        return "UNKNOWN_RULE_TIER"
    authority = record.get("authority")
    if (
        not isinstance(authority, dict)
        or not isinstance(authority.get("kind"), str)
        or authority["kind"] not in {"FOUNDER", "NSM", "GSE_CONVENTION", "EMPIRICAL"}
        or not _reference_list(authority.get("refs"))
    ):
        return "MISSING_RULE_AUTHORITY"
    if authority["kind"] == "EMPIRICAL" and record["tier"] != "CONDITIONAL":
        return "EMPIRICAL_REQUIRES_CONDITIONAL"
    if (
        not isinstance(record.get("warrant"), str)
        or not record["warrant"].strip()
        or not _reference_list(record.get("source_refs"))
    ):
        return "MISSING_RULE_WARRANT"
    validation = record.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "VALIDATED":
        return "UNVALIDATED_RULE"
    if not _test_references(validation.get("positive")) or not _test_references(validation.get("must_not")):
        return "MISSING_RULE_WITNESSES"
    if validation.get("contract_sha256") != digest:
        return "STALE_RULE_VALIDATION"
    return "ADMITTED_VALIDATED"


def law_admission_status(record: object) -> str:
    """The compatibility verdict; reports retain the more specific reason."""
    return (
        "ADMITTED"
        if rule_admission_reason(record) in {"ADMITTED_VALIDATED", "ADMITTED_LEGACY_APPROVAL"}
        else "NOT_ADMITTED"
    )


def compile_law(record: dict) -> Law:
    """Compile a relation without granting it permission to run."""
    return Law(
        record["rule_id"],
        tuple(record["coordinates"]),
        tuple(tuple(Cell(v) for v in row) for row in record["allowed"]),
        tuple(tuple(g) for g in record["guard"]),
        record["warrant"],
        record.get("tier", "FOUNDATIONAL"),
        record.get("application_id"),
    )


def admitted_laws(book: dict) -> tuple[Law, ...]:
    """One admission policy for default resolution, word builds and atomic proofs."""
    return tuple(compile_law(r) for r in book["laws"] if law_admission_status(r) == "ADMITTED")


REVIEWED_LAWS = admitted_laws(json.loads(Path(__file__).with_name("bank_laws.json").read_text()))


@dataclass(frozen=True)
class Resolution:
    reading_id: str
    code: str
    domains: dict[str, tuple[Cell, ...]]
    fired_rules: tuple[str, ...]
    trace: tuple[dict[str, Any], ...]
    rule_applications: tuple[dict[str, Any], ...] = ()

    def forced(self) -> dict[str, Cell]:
        return {coordinate: domain[0] for coordinate, domain in self.domains.items() if len(domain) == 1}

    def to_json(self) -> dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "code": self.code,
            "forced": {key: value.value for key, value in self.forced().items()},
            "domains": {key: [value.value for value in domain] for key, domain in self.domains.items()},
            "fired_rules": list(self.fired_rules),
            "rule_applications": list(self.rule_applications),
            "trace": list(self.trace),
        }


@dataclass(frozen=True)
class RuleException:
    """Independent evidence withdrawing one conditional rule on one reading.

    Re-resolution starts from the remaining facts, so independent warrants survive.
    A builder-derived vector is never evidence for its own exception or confirmation.
    """

    reading_id: str
    rule_id: str
    source: str
    record_id: str
    reason: str
    evidence_kind: str = "SOURCE_RECORD"
    application_id: str | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.reading_id, self.rule_id, self.source, self.record_id, self.reason)
        ):
            raise RuleExceptionError(
                "MALFORMED_RULE_EXCEPTION", self, "requires reading, rule, source, record and reason"
            )
        if self.application_id is not None and (
            not isinstance(self.application_id, str) or not self.application_id.strip()
        ):
            raise RuleExceptionError("MALFORMED_RULE_EXCEPTION", self, "application ID must be a nonempty string")
        if not isinstance(self.evidence_kind, str) or self.evidence_kind not in {"SOURCE_RECORD", "USER_CORRECTION"}:
            raise RuleExceptionError(
                "NONINDEPENDENT_RULE_EXCEPTION", self, "requires independent evidence, never builder output"
            )
        source = self.source.casefold().replace("-", "_")
        record = self.record_id.casefold()
        if source.split(":", 1)[0] in {
            "builder",
            "gse_builder",
            "gse.lexicon_builder",
            "model",
            "ollama",
            "generated",
            "derived",
            "lexicon_output",
            "sparse",
            "vectors",
        } or record.startswith(("model:", "fill:", "builder:", "vector:", "provisional_coverage:")):
            raise RuleExceptionError(
                "NONINDEPENDENT_RULE_EXCEPTION", self, "requires independent evidence, never builder output"
            )


class RuleExceptionError(ValueError):
    """A named refusal; malformed, ambiguous and foundational failures differ."""

    def __init__(self, code: str, exception: RuleException, reason: str):
        self.code = code
        self.reading_id = exception.reading_id
        self.rule_id = exception.rule_id
        self.application_id = exception.application_id
        super().__init__(f"{code}: {reason}: {exception.rule_id}")


def law_application_id(law: Law) -> str:
    """An explicit native application, or the immutable relation contract itself."""
    if law.application_id is not None:
        return law.application_id
    contract = {
        "rule_id": law.rule_id,
        "coordinates": law.coordinates,
        "allowed": law.allowed,
        "guard": law.guard,
        "warrant": law.warrant,
        "tier": law.tier,
    }
    return (
        "RELATION:" + hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )


def _retract_exceptions(
    reading_id: str, active: tuple[Law, ...], exceptions: tuple[RuleException, ...]
) -> tuple[tuple[Law, ...], list[dict[str, Any]]]:
    """Withdraw exact reading/rule/application matches, retaining independent support.

    Evidence authenticity is the source adapter's boundary; this layer refuses
    derived kinds and known builder/model origins, and never mines its result
    to manufacture an exception. No correction confirms or demotes a global law.
    """
    if not exceptions:
        return active, []
    trace: list[dict[str, Any]] = []
    selected: set[tuple[str, str]] = set()
    for exception in exceptions:
        if exception.reading_id != reading_id:
            continue
        matches = [law for law in active if law.rule_id == exception.rule_id]
        if exception.application_id is not None:
            matches = [law for law in matches if law_application_id(law) == exception.application_id]
        if not matches:
            raise RuleExceptionError("RULE_EXCEPTION_NOT_APPLICABLE", exception, "names no applicable rule application")
        applications = {law_application_id(law) for law in matches}
        if len(applications) != 1:
            raise RuleExceptionError("AMBIGUOUS_RULE_EXCEPTION", exception, "requires one exact application ID")
        if any(law.tier != "CONDITIONAL" for law in matches):
            raise RuleExceptionError(
                "FOUNDATIONAL_RULE_EXCEPTION", exception, "cannot retract a foundational or model rule"
            )
        application = applications.pop()
        key = exception.rule_id, application
        if key in selected:
            raise RuleExceptionError("DUPLICATE_RULE_EXCEPTION", exception, "duplicate rule application correction")
        selected.add(key)
        trace.append(
            {
                "rule": exception.rule_id,
                "application_id": application,
                "reading_id": reading_id,
                "code": "CONDITIONAL_RULE_RETRACTED",
                "source": exception.source,
                "record_id": exception.record_id,
                "evidence_kind": exception.evidence_kind,
                "reason": exception.reason,
            }
        )
    if not selected:
        return active, trace
    return tuple(law for law in active if (law.rule_id, law_application_id(law)) not in selected), trace


def _active_laws(reading_id: str, observations: tuple[Observation, ...], laws: tuple[Law, ...]) -> tuple[Law, ...]:
    certified = {
        (observation.field, observation.value)
        for observation in observations
        if observation.reading_id == reading_id
        and observation.certified
        and observation.source
        and observation.record_id
    }
    return tuple(law for law in laws if all(fact in certified for fact in law.guard))


def _components(laws: tuple[Law, ...]) -> tuple[tuple[str, ...], ...]:
    """Connected coordinate groups; unrelated cells need no Cartesian product."""
    adjacency: dict[str, set[str]] = {}
    for law in laws:
        for coordinate in law.coordinates:
            adjacency.setdefault(coordinate, set()).update(law.coordinates)
    groups = []
    while adjacency:
        first = next(iter(adjacency))
        seen = {first}
        frontier = [first]
        while frontier:
            for neighbor in adjacency[frontier.pop()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    frontier.append(neighbor)
        groups.append(tuple(sorted(seen)))
        for coordinate in seen:
            del adjacency[coordinate]
    return tuple(groups)


def resolve(
    reading_id: str,
    observations: tuple[Observation, ...] = (),
    seed: str | None = None,
    laws: tuple[Law, ...] = REVIEWED_LAWS,
    max_joint_assignments: int = 100_000,
    exceptions: tuple[RuleException, ...] = (),
) -> Resolution:
    """Propagate typed laws, then check joint support within connected groups.

    A limit yields PARTIAL_SOLVER_LIMIT; it never manufactures a forced value.
    """
    if not reading_id:
        raise ValueError("reading_id is required")
    domains = {coordinate: set(legal_domain(coordinate)) for coordinate in CANONICAL_COORDINATES}
    trace: list[dict[str, Any]] = []
    active = _active_laws(reading_id, observations, laws)
    active, exception_trace = _retract_exceptions(reading_id, active, exceptions)
    trace.extend(exception_trace)
    if seed is not None:
        atom = atomic_seed(seed)
        domains[atom.coordinate] = {atom.sign}
        trace.append({"rule": "ATOMIC_SEED", "coordinate": atom.coordinate, "remaining": [atom.sign.value]})
    changed = True
    while changed:
        changed = False
        for law in active:
            compatible = tuple(
                row
                for row in law.allowed
                if all(value in domains[coordinate] for coordinate, value in zip(law.coordinates, row))
            )
            for index, coordinate in enumerate(law.coordinates):
                supported = {row[index] for row in compatible}
                narrowed = domains[coordinate] & supported
                if narrowed != domains[coordinate]:
                    domains[coordinate] = narrowed
                    trace.append(
                        {
                            "rule": law.rule_id,
                            "coordinate": coordinate,
                            "remaining": sorted(value.value for value in narrowed),
                        }
                    )
                    changed = True
                if not narrowed:
                    return _resolution(reading_id, "CONFLICT", domains, active, trace)

    # Arc consistency is not enough for cyclic relations. Enumerate only
    # connected active groups and retain states with a joint witness.
    limited = False
    for group in _components(active):
        group_laws = tuple(law for law in active if set(law.coordinates) <= set(group))
        ordered_domains = tuple(tuple(sorted(domains[coordinate], key=lambda cell: cell.value)) for coordinate in group)
        if prod(len(domain) for domain in ordered_domains) > max_joint_assignments:
            limited = True
            continue
        supported = {coordinate: set() for coordinate in group}
        witnesses = 0
        for assignment in product(*ordered_domains):
            candidate = dict(zip(group, assignment))
            if all(tuple(candidate[coordinate] for coordinate in law.coordinates) in law.allowed for law in group_laws):
                witnesses += 1
                for coordinate, state in candidate.items():
                    supported[coordinate].add(state)
        if witnesses == 0:
            trace.append({"rule": "JOINT_CONFLICT", "coordinates": list(group)})
            return _resolution(reading_id, "CONFLICT", domains, active, trace)
        for coordinate in group:
            if supported[coordinate] != domains[coordinate]:
                domains[coordinate] = supported[coordinate]
                trace.append(
                    {
                        "rule": "JOINT_SUPPORT",
                        "coordinate": coordinate,
                        "remaining": sorted(value.value for value in supported[coordinate]),
                    }
                )
    code = (
        "PARTIAL_SOLVER_LIMIT"
        if limited
        else "RESOLVED"
        if all(len(value) == 1 for value in domains.values())
        else "PARTIAL"
    )
    return _resolution(reading_id, code, domains, active, trace)


def _resolution(
    reading_id: str, code: str, domains: dict[str, set[Cell]], active: tuple[Law, ...], trace: list[dict[str, Any]]
) -> Resolution:
    return Resolution(
        reading_id,
        code,
        {coordinate: tuple(sorted(values, key=lambda cell: cell.value)) for coordinate, values in domains.items()},
        tuple(law.rule_id for law in active),
        tuple(trace),
        tuple(
            {
                "rule_id": law.rule_id,
                "application_id": law_application_id(law),
                "tier": law.tier,
                "coordinates": list(law.coordinates),
            }
            for law in active
        ),
    )


def _proof_background(laws: dict, active: list[str], blocked: set[str]) -> tuple[Law, ...]:
    """Existentially erase the target columns from every active relation.

    Each relation is weakened independently, so two relations cannot transmit
    an assumed target value around a cycle and return it as independent proof.
    Direct consequences on other columns remain available as real roots.
    """
    background = []
    for rule_id in active:
        if rule_id not in laws:
            continue
        coordinates, allowed = laws[rule_id]
        kept = [(i, c) for i, c in enumerate(coordinates) if c not in blocked]
        if not kept:
            continue
        rows = tuple(sorted({tuple(Cell(row[i]) for i, _ in kept) for row in allowed}))
        background.append(
            Law("BACKGROUND:" + rule_id, tuple(c for _, c in kept), rows, (), "Independent target-erased relation")
        )
    return tuple(background)


def rooted_law_status(
    state: str,
    coordinates: list[str],
    rule_id: str,
    laws: dict,
    active: list[str],
    max_joint_assignments: int = 100_000,
) -> str:
    """Check whether a cited law forces a decision from independent premises.

    The target coordinates never occur in the proof background. For each row
    with a different target value, the existing solver checks whether its
    outside assignment has an independent joint witness. A surviving wrong
    row means the attribution is unrooted; a limit never becomes proof.
    """
    if rule_id not in laws:
        return "CITED_LAW_UNKNOWN"
    if rule_id not in active:
        return "CITED_LAW_INACTIVE"
    target = set(coordinates)
    law_coordinates, allowed = laws[rule_id]
    if not target <= set(law_coordinates):
        return "CITED_LAW_DOES_NOT_COVER"
    inside = [i for i, c in enumerate(law_coordinates) if c in target]
    outside = [(i, c) for i, c in enumerate(law_coordinates) if c not in target]
    if not outside:
        return (
            "ROOTED"
            if allowed and all(row[i] == state for row in allowed for i in inside)
            else "CITED_LAW_DOES_NOT_FORCE"
        )
    background = _proof_background(laws, active, target)
    independent = resolve("provenance-background", laws=background, max_joint_assignments=max_joint_assignments)
    if independent.code == "CONFLICT":
        return "PROVENANCE_BACKGROUND_CONFLICT"
    if independent.code == "PARTIAL_SOLVER_LIMIT":
        return "PROVENANCE_SOLVER_LIMIT"
    supported_correct = False
    limited = False
    for index, row in enumerate(allowed):
        if any(Cell(row[i]) not in independent.domains[c] for i, c in outside):
            continue
        assumptions = tuple(
            Law(
                f"OUTSIDE_WITNESS:{index}:{c}", (c,), ((Cell(row[i]),),), (), "Candidate independent outside assignment"
            )
            for i, c in outside
        )
        witness = resolve("provenance-row", laws=background + assumptions, max_joint_assignments=max_joint_assignments)
        if witness.code == "CONFLICT":
            continue
        if witness.code == "PARTIAL_SOLVER_LIMIT":
            limited = True
            continue
        if any(row[i] != state for i in inside):
            return "CITED_LAW_NOT_ROOTED"
        supported_correct = True
    if limited:
        return "PROVENANCE_SOLVER_LIMIT"
    return "ROOTED" if supported_correct else "CITED_LAW_DOES_NOT_FORCE"


@dataclass(frozen=True)
class NumberScale:
    """Relative rank plus an optional positive realized gain for selected rows."""

    family: str
    rank: int
    coordinates: tuple[str, ...]
    gain: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.family or not self.coordinates or len(set(self.coordinates)) != len(self.coordinates):
            raise ValueError("scale requires a family and distinct selected coordinates")
        for coordinate in self.coordinates:
            legal_domain(coordinate)
        if self.gain is not None and (not self.gain.is_finite() or self.gain <= 0):
            raise ValueError("a realized NUMBER gain must be finite and positive")


def apply_number_scale(forced: dict[str, Cell], scale: NumberScale) -> dict[str, Decimal]:
    """Realize NUMBER without changing presence, zero, or polarity.

    Unknown calibration is an explicit error, not a fabricated gain.
    """
    if scale.gain is None:
        raise ValueError("relative scale has no reviewed numeric gain")
    if any(forced.get(coordinate) not in (Cell.PLUS, Cell.MINUS) for coordinate in scale.coordinates):
        raise ValueError("NUMBER can select only already written, nonzero coordinates")
    realized: dict[str, Decimal] = {}
    for coordinate, state in forced.items():
        if state is Cell.SILENT:
            continue
        value = Decimal(1 if state is Cell.PLUS else -1 if state is Cell.MINUS else 0)
        realized[coordinate] = value * scale.gain if coordinate in scale.coordinates else value
    return realized


def cli_law_contract(payload: object) -> str:
    """Reviewed records and explicit scratch equations are distinct interfaces."""
    if not isinstance(payload, dict):
        return "MALFORMED_RESOLVE_PAYLOAD"
    mode = payload.get("law_contract")
    if mode is not None and (not isinstance(mode, str) or mode not in {"DIRECT_CONSTRAINTS", "ADMITTED_RULEBOOK"}):
        return "UNKNOWN_LAW_CONTRACT"
    if "laws" not in payload:
        return "DIRECT_CONSTRAINTS_REQUIRE_LAWS" if mode == "DIRECT_CONSTRAINTS" else "ADMITTED_RULEBOOK"
    laws = payload["laws"]
    if not isinstance(laws, list) or any(not isinstance(record, dict) for record in laws):
        return "MALFORMED_CLI_LAWS"
    review_fields = {"review_state", "lifecycle", "authority", "validation", "may_write_lexical_cells", "kind"}
    metadata = any(review_fields & set(record) for record in laws)
    if mode == "DIRECT_CONSTRAINTS":
        return "DIRECT_CONSTRAINTS_WITH_REVIEW_METADATA" if metadata else "DIRECT_CONSTRAINTS"
    if mode == "ADMITTED_RULEBOOK" or metadata:
        return "ADMITTED_RULEBOOK"
    return "MISSING_LAW_CONTRACT"


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="Mask-aware lexical-definition foundation")
    parser.add_argument("command", choices=("prime-proof", "resolve"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "prime-proof":
        from gse.lexicon_builder.atomics import atomic_proof

        result = atomic_proof()
    else:
        if args.input is None:
            parser.error("resolve requires --input")
        payload = json.loads(args.input.read_text())
        contract = cli_law_contract(payload)
        if contract not in {"DIRECT_CONSTRAINTS", "ADMITTED_RULEBOOK"}:
            parser.error(contract)
        observations = tuple(Observation(**item) for item in payload.get("observations", ()))
        try:
            laws = (
                tuple(compile_law(item) for item in payload["laws"])
                if contract == "DIRECT_CONSTRAINTS"
                else admitted_laws(payload)
                if "laws" in payload
                else REVIEWED_LAWS
            )
        except (KeyError, TypeError, ValueError) as error:
            parser.error(f"INVALID_CLI_LAW: {error}")
        exceptions = tuple(RuleException(**item) for item in payload.get("exceptions", ()))
        result = resolve(
            payload["reading_id"], observations, payload.get("seed"), laws=laws, exceptions=exceptions
        ).to_json()
        result["constraint_mode"] = contract
        if "laws" in payload and contract == "ADMITTED_RULEBOOK":
            result["rule_admission"] = [
                {"rule_id": record.get("rule_id"), "reason": rule_admission_reason(record)}
                for record in payload["laws"]
            ]
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.write_text(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
