"""Mask-aware, finite-domain foundation for a source-guided lexical definition.

This module deliberately does not use the dense curation database or the older
source-voting paths. A source adapter supplies *typed, certified observations*;
reviewed laws restrict the feasible vector. Unresolved coordinates stay open.
"""

from __future__ import annotations

import argparse
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

    def __post_init__(self) -> None:
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


def _reviewed_laws() -> tuple[Law, ...]:
    """Load the same saved laws consumed by the batch constructor."""
    book = json.loads(Path(__file__).with_name("bank_laws.json").read_text())
    return tuple(
        Law(
            r["rule_id"],
            tuple(r["coordinates"]),
            tuple(tuple(Cell(v) for v in row) for row in r["allowed"]),
            tuple(tuple(g) for g in r["guard"]),
            r["warrant"],
        )
        for r in book["laws"]
        if r["review_state"] == "FOUNDER_APPROVED"
    )


REVIEWED_LAWS = _reviewed_laws()


@dataclass(frozen=True)
class Resolution:
    reading_id: str
    code: str
    domains: dict[str, tuple[Cell, ...]]
    fired_rules: tuple[str, ...]
    trace: tuple[dict[str, Any], ...]

    def forced(self) -> dict[str, Cell]:
        return {coordinate: domain[0] for coordinate, domain in self.domains.items() if len(domain) == 1}

    def to_json(self) -> dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "code": self.code,
            "forced": {key: value.value for key, value in self.forced().items()},
            "domains": {key: [value.value for value in domain] for key, domain in self.domains.items()},
            "fired_rules": list(self.fired_rules),
            "trace": list(self.trace),
        }


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
) -> Resolution:
    """Propagate typed laws, then check joint support within connected groups.

    A limit yields PARTIAL_SOLVER_LIMIT; it never manufactures a forced value.
    """
    if not reading_id:
        raise ValueError("reading_id is required")
    domains = {coordinate: set(legal_domain(coordinate)) for coordinate in CANONICAL_COORDINATES}
    trace: list[dict[str, Any]] = []
    active = _active_laws(reading_id, observations, laws)
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
    )


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
        observations = tuple(Observation(**item) for item in payload.get("observations", ()))
        result = resolve(payload["reading_id"], observations, payload.get("seed")).to_json()
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.write_text(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
