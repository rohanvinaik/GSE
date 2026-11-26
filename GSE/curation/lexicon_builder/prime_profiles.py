"""The authored prime profiles and bank laws (data reviewed with Rohan in October; F148, F158-F160), read by the
current engine.

A prime is "*defined*, not imputed" (F083), a "*perfect* recapitulation" of its NSM encoding (F148). Its typed claims
become engine inputs, and only the kinds that carry content write cells (F151: "combinability isn't content"):
IDENTIFIES_PRIME writes its own signed coordinate, ASSERTS_COMPONENT writes its component, ESTABLISHES_DEGREE_DOMAIN
writes INTENSITY +1 (F125-F126). CLASSIFIES_HEAD and CLASSIFIES_SEMANTIC_KIND only switch on the laws keyed on them.
PERMITS_COMBINATION and REQUIRES_ARGUMENT write nothing: "GOOD qualifies SOMETHING" does not put SOMETHING into GOOD.

Content and explicit absence come from the shared laws through the ordinary solver. Silence comes only from the
profile's own explicit silence decision, which names its coordinates (``definition_axiom.decisions``; prime_closure,
F159), so a missing fact reopens its cell instead of being hidden as silence (F158 section 3). Ordinary words never
inherit a prime's boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

from .engine import EMPTY, Assertion, DomainRestriction, Relation, Resolution, propagate
from .foundation import BANKS, NEGATIVE_POLES
from .silence import starting_domains

HERE = Path(__file__).resolve().parent
PROFILES = HERE / "prime_profiles.json"
LAWS = HERE / "bank_laws.json"
STATE = {"empty": EMPTY, "0": 0, "+1": 1, "-1": -1}
CONTENT_CLAIMS = ("IDENTIFIES_PRIME", "ASSERTS_COMPONENT", "ESTABLISHES_DEGREE_DOMAIN")


def load_profiles() -> list[dict]:
    return json.loads(PROFILES.read_text())["profiles"]


def load_laws() -> tuple[Relation, ...]:
    """Every authored law as an engine relation, with its own guards and source references."""
    out = []
    for law in json.loads(LAWS.read_text())["laws"]:
        rows = tuple(tuple(STATE[value] for value in row) for row in law["allowed"])
        refs = tuple(law.get("source_refs") or ()) or (law["rule_id"],)
        guards = tuple((key, value) for key, value in law["guard"])
        out.append(Relation(law["rule_id"], tuple(law["coordinates"]), rows, refs, "foundational", True, guards))
    return tuple(out)


def coordinate(prime: str) -> tuple[str, int] | None:
    """A prime's own basis coordinate and sign (BAD is GOOD -1); None for metadata primes outside the 56 banks."""
    bank, sign = (NEGATIVE_POLES[prime], -1) if prime in NEGATIVE_POLES else (prime, 1)
    return (bank, sign) if bank in BANKS else None


def inputs(profile: dict, drop: frozenset[str] = frozenset()) -> tuple[tuple[Assertion, ...], dict[str, str]]:
    """The profile's content claims as assertions, and its classifications as law context; ``drop`` ablates claims."""
    prime = profile["prime"]
    assertions, context = [], {"lexical_unit_kind": "PRIME"}
    for claim in profile["claims"]:
        if claim["claim_id"] in drop:
            continue
        kind, record = claim["kind"], claim["claim_id"]
        if kind == "IDENTIFIES_PRIME":
            bank, sign = coordinate(prime)
            assertions.append(Assertion(bank, sign, claim["source"], record, "prime_profile"))
        elif kind == "ASSERTS_COMPONENT":
            assertions.append(
                Assertion(claim["coordinate"], STATE[claim["state"]], claim["source"], record, "prime_profile")
            )
        elif kind == "ESTABLISHES_DEGREE_DOMAIN":
            assertions.append(Assertion("INTENSITY", 1, claim["source"], record, "prime_profile"))
        elif kind == "CLASSIFIES_HEAD":
            context["own_role"] = claim["value"]
        elif kind == "CLASSIFIES_SEMANTIC_KIND":
            context["own_semantic_kind"] = claim["value"]
        elif kind == "CLASSIFIES_FAMILY":
            context["family"] = claim["value"]
    return tuple(assertions), context


def authored_decisions(profile: dict) -> list[dict]:
    raw = profile["definition_axiom"].get("decisions") or []
    return json.loads(raw) if isinstance(raw, str) else list(raw)


def declared_silence(profile: dict) -> tuple[str, ...]:
    """The coordinates the profile explicitly declares silent (only those in the 56 banks)."""
    return tuple(
        sorted(b for d in authored_decisions(profile) if d["state"] == "empty" for b in d["coordinates"] if b in BANKS)
    )


def reconstruct(
    profile: dict, laws: tuple[Relation, ...], drop: frozenset[str] = frozenset()
) -> tuple[Resolution, Resolution]:
    """(the laws' closure, the closure after the authored boundary) through the ordinary solver."""
    assertions, context = inputs(profile, drop)
    start = starting_domains(BANKS)
    closed = propagate(BANKS, assertions, laws, context, initial_domains=start)
    if closed.code == "CONFLICT":
        return closed, closed
    boundary = tuple(
        DomainRestriction(bank, (EMPTY,), "AUTHORED_SILENCE", f"{profile['prime']}:silence", "prime_closure")
        for bank in declared_silence(profile)
    )
    final = propagate(BANKS, assertions, laws, context, domain_restrictions=boundary, initial_domains=start)
    return closed, final


def load_structural() -> list[dict]:
    return json.loads(PROFILES.read_text())["structural_entries"]


def structural_inputs(entry: dict) -> tuple[Assertion, ...]:
    """A hand-built function word's own lexical projection (F148; F158 section 4): only its asserted components."""
    out = []
    for claim in entry["claims"]:
        if claim["kind"] == "ASSERTS_COMPONENT":
            value = STATE[claim["state"]]
            out.append(Assertion(claim["coordinate"], value, claim["source"], claim["claim_id"], "function_word"))
        elif claim["kind"] == "ESTABLISHES_DEGREE_DOMAIN":
            out.append(Assertion("INTENSITY", 1, claim["source"], claim["claim_id"], "function_word"))
    return tuple(out)


def reconstruct_structural(entry: dict, laws: tuple[Relation, ...]) -> tuple[str, Resolution]:
    """(status, resolution): LEXICAL_PROJECTION when the entry writes content, else CONSTRUCTION_ONLY. The entries
    declare no silence, so cells their components and the laws leave undecided stay unresolved."""
    assertions = structural_inputs(entry)
    start = starting_domains(BANKS)
    context = {"lexical_unit_kind": "FUNCTION_WORD"}
    closed = propagate(BANKS, assertions, laws, context, initial_domains=start)
    if closed.code == "CONFLICT":
        return "CONFLICT", closed
    return ("LEXICAL_PROJECTION" if assertions else "CONSTRUCTION_ONLY"), closed
