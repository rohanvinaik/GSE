"""Sourced lexical-unit profiles, reconstructed by the ordinary reading constructor.

Grammar identifies a reading and constrains combinations. Only an identity,
component, explicit absence, silence proof, or separately warranted projection
writes a cell. An examined prime's authored decisions cover all 58 coordinates:
its content and explicit absences are rebuilt by the shared rules and checked,
and only its authored boundary declares silence (F151-F152, F158). The boundary
is the author's decision; reconstruction checks it for consistency with the
rules, not for semantic completeness (F159). A draft profile closes nothing.
Ordinary words never inherit a prime's boundary.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import partial
from pathlib import Path

from gse.lexicon_builder.basis import BASIS_ID, PRIMES
from gse.lexicon_builder.core import (
    CANONICAL_COORDINATES,
    Cell,
    Law,
    Observation,
    admitted_laws,
    canonical_pole,
    legal_domain,
    rooted_law_status,
)
from gse.lexicon_builder.reading import Construction, ReadingSeed, construct_reading

FOUNDATION = Path(__file__).with_name("foundation.json")
CLAIM_TYPES = {
    "IDENTIFIES_PRIME",
    "ASSERTS_COMPONENT",
    "ASSERTS_ABSENCE",
    "ASSERTS_SILENCE",
    "CLASSIFIES_HEAD",
    "CLASSIFIES_FAMILY",
    "CLASSIFIES_SEMANTIC_KIND",
    "ESTABLISHES_DEGREE_DOMAIN",
    "PERMITS_COMBINATION",
    "REQUIRES_ARGUMENT",
    "FORBIDS_CONSTRUCTION",
    "BINDS_REFERENCE",
}
DECISION_FIELDS = {"decision_id", "coordinates", "state", "authority", "location", "derived_by", "warrant"}
DECISION_AUTHORITIES = {"FOUNDER", "NSM", "GSE_CONVENTION"}
# A judged chart line is typed by a claim of the matching kind in the same profile.
EXAMINATION_TYPES = {
    "COMBINATION": {"PERMITS_COMBINATION"},
    "DEGREE_DOMAIN": {"ESTABLISHES_DEGREE_DOMAIN"},
    "PROHIBITION": {"FORBIDS_CONSTRUCTION"},
    "COMPONENT": {"IDENTIFIES_PRIME", "ASSERTS_COMPONENT"},
}
PROVENANCE_FAILURES = {
    "CITED_LAW_UNKNOWN",
    "CITED_LAW_INACTIVE",
    "CITED_LAW_DOES_NOT_COVER",
    "CITED_LAW_DOES_NOT_FORCE",
    "CITED_LAW_NOT_ROOTED",
    "PROVENANCE_BACKGROUND_CONFLICT",
    "PROVENANCE_SOLVER_LIMIT",
}


def _strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def definition_status(axiom: object) -> str:
    """Validate an authored prime definition; only an examined one may close cells."""
    if not isinstance(axiom, dict):
        return "MISSING_DEFINITION"
    if axiom.get("review") == "DRAFT":
        return "DRAFT_WITH_DECISIONS" if "decisions" in axiom else "VALID_DRAFT"
    if axiom.get("review") != "EXAMINED":
        return "UNKNOWN_REVIEW"
    examination = axiom.get("examination")
    if not isinstance(examination, list) or not examination:
        return "MISSING_EXAMINATION"
    for line in examination:
        if (
            not isinstance(line, dict)
            or not isinstance(line.get("line"), str)
            or not line["line"]
            or not isinstance(line.get("judgment"), str)
            or line["judgment"] not in EXAMINATION_TYPES
        ):
            return "MALFORMED_EXAMINATION"
    decisions = axiom.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        return "MISSING_DECISIONS"
    covered, ids = [], set()
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != DECISION_FIELDS:
            return "MALFORMED_DECISION"
        decision_id, coordinates, state = decision["decision_id"], decision["coordinates"], decision["state"]
        if not isinstance(decision_id, str) or not decision_id or decision_id in ids:
            return "MALFORMED_DECISION"
        if not _strings(coordinates) or not coordinates or not isinstance(state, str):
            return "MALFORMED_DECISION"
        ids.add(decision_id)
        if any(c not in CANONICAL_COORDINATES for c in coordinates):
            return "UNKNOWN_COORDINATE"
        if any(state not in legal_domain(c) for c in coordinates):
            return "ILLEGAL_STATE"
        authority = decision["authority"]
        if not _strings(authority) or not authority or any(a not in DECISION_AUTHORITIES for a in authority):
            return "UNKNOWN_AUTHORITY"
        if not all(isinstance(decision[k], str) and decision[k] for k in ("location", "warrant")):
            return "MISSING_WARRANT"
        if not _strings(decision["derived_by"]):
            return "MALFORMED_DECISION"
        if state == Cell.SILENT and decision["derived_by"]:
            return "SILENCE_CLAIMS_DERIVATION"
        if state != Cell.SILENT and not decision["derived_by"]:
            return "UNDERIVED_DECISION"
        covered.extend(coordinates)
    if sorted(covered) != sorted(CANONICAL_COORDINATES):
        return "NOT_A_PARTITION"
    return "VALID_EXAMINED"


def examination_status(examination: object, claims: object) -> str:
    """Each judged chart line must be typed by a claim of its kind in the same profile."""
    if not isinstance(examination, list) or not isinstance(claims, list):
        return "MALFORMED_EXAMINATION"
    kinds = {c["claim_id"]: c.get("kind") for c in claims if isinstance(c, dict) and isinstance(c.get("claim_id"), str)}
    for line in examination:
        if not isinstance(line, dict):
            return "MALFORMED_EXAMINATION"
        typed_as, judgment = line.get("typed_as"), line.get("judgment")
        if not isinstance(typed_as, str) or typed_as not in kinds:
            return "UNTYPED_EXAMINATION_LINE"
        if not isinstance(kinds[typed_as], str):
            return "MALFORMED_CLAIM"
        if not isinstance(judgment, str) or kinds[typed_as] not in EXAMINATION_TYPES.get(judgment, ()):
            return "MISTYPED_EXAMINATION_LINE"
    return "VALID_EXAMINATION"


def decision_check(
    state: str, derived_by: list[str], coordinates: list[str], vector: dict, fired: list, laws: dict
) -> str:
    """Check a decision's value and independently rooted supporting laws.

    A cited law earns credit only if it fired, covers the decision's coordinates and, given the
    final states of its coordinates outside the decision, allows nothing but the decided state on
    every coordinate inside it. The decision's own cells never vouch for each other. Every cited law
    must qualify: redundant forcing laws all count, and a merely permissive law is refused (F159).

    Local forcing is checked first. Rooted proof then erases every target
    coordinate from the other relations before establishing outside premises.
    Final values can therefore neither directly nor indirectly vouch for
    themselves. Redundant independently forcing rules are all preserved.
    """
    if any(c not in vector for c in coordinates):
        return "COORDINATE_NOT_RECONSTRUCTED"
    found = {vector[c] for c in coordinates}
    if "conflict" in found:
        return "CONFLICT"
    if "unresolved" in found:
        return "UNRESOLVED"
    if found != {state}:
        return "VALUE_MISMATCH"
    for rule_id in derived_by:
        if rule_id not in laws:
            return "CITED_LAW_UNKNOWN"
        if rule_id not in fired:
            return "CITED_LAW_INACTIVE"
        law_coordinates, allowed = laws[rule_id]
        if not set(coordinates) <= set(law_coordinates):
            return "CITED_LAW_DOES_NOT_COVER"
        inside = [i for i, c in enumerate(law_coordinates) if c in coordinates]
        outside = [(i, c) for i, c in enumerate(law_coordinates) if c not in coordinates]
        outside_known = all(vector.get(c) not in {None, "unresolved", "conflict"} for _, c in outside)
        surviving = [row for row in allowed if all(row[i] == vector.get(c) for i, c in outside)]
        if outside_known and (not surviving or any(row[i] != state for row in surviving for i in inside)):
            return "CITED_LAW_DOES_NOT_FORCE"
        rooted = rooted_law_status(state, coordinates, rule_id, laws, fired)
        if rooted != "ROOTED":
            return rooted
    return "RECONSTRUCTED"


def load_foundation(path: Path = FOUNDATION) -> dict:
    book = json.loads(path.read_text())
    if book["basis_id"] != BASIS_ID:
        raise ValueError("foundation basis mismatch")
    profiles = book["profiles"]
    if len(profiles) != 72 or {p["prime"] for p in profiles} != set(PRIMES):
        raise ValueError("foundation must cover each of the 72 lexical units exactly once")
    ids = []
    for profile in profiles:
        if not profile["reading_id"] or not profile["surfaces"]:
            raise ValueError("a profile needs an explicit reading and surface routing")
        axiom = profile.get("definition_axiom")
        status = definition_status(axiom)
        if status not in {"VALID_EXAMINED", "VALID_DRAFT"}:
            raise ValueError(f"{profile['prime']}: {status}")
        if status == "VALID_EXAMINED":
            typed = examination_status(axiom["examination"], profile["claims"])
            if typed != "VALID_EXAMINATION":
                raise ValueError(f"{profile['prime']}: {typed}")
        for claim in profile["claims"]:
            ids.append(claim["claim_id"])
            if (
                not isinstance(claim.get("kind"), str)
                or claim["kind"] not in CLAIM_TYPES
                or not claim["source"]
                or not claim["location"]
                or not claim["warrant"]
            ):
                raise ValueError("a claim requires a supported type, source, location and warrant")
            if claim["source"] not in book["sources"]:
                raise ValueError("unknown foundation source")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate foundation claim ID")
    return book


def profile_seed(
    profile: dict, word: str, retained_claims: set[str] | None = None, retained_decisions: set[str] | None = None
) -> ReadingSeed:
    """Compile claims as facts and guarded laws; ablation removes their support and their premise IDs."""
    observations, laws, compiled = [], [], []
    for claim in profile["claims"]:
        if retained_claims is not None and claim["claim_id"] not in retained_claims:
            continue
        compiled.append(claim)
        kind, claim_id = claim["kind"], claim["claim_id"]
        field, value = "claim:" + claim_id, "ESTABLISHED"
        coordinate, state = None, None
        if kind == "IDENTIFIES_PRIME":
            coordinate, direction = canonical_pole(profile["prime"])
            state = "+1" if direction > 0 else "-1"
            reading_id, source = profile["reading_id"], claim["source"]
            observations.append(Observation(reading_id, source, claim_id, "prime_lexical_unit", profile["prime"], True))
            observations.append(Observation(reading_id, source, claim_id, "lexical_unit_kind", "PRIME", True))
        elif kind in {"ASSERTS_COMPONENT", "ASSERTS_ABSENCE", "ASSERTS_SILENCE"}:
            coordinate = claim["coordinate"]
            state = claim["state"]
            if (
                kind == "ASSERTS_COMPONENT"
                and state not in {"+1", "-1"}
                or kind == "ASSERTS_ABSENCE"
                and state != "0"
                or kind == "ASSERTS_SILENCE"
                and state != "empty"
            ):
                raise ValueError("claim type and coordinate state disagree")
        elif kind in {"CLASSIFIES_HEAD", "CLASSIFIES_FAMILY", "CLASSIFIES_SEMANTIC_KIND", "ESTABLISHES_DEGREE_DOMAIN"}:
            field = {
                "CLASSIFIES_HEAD": "own_role",
                "CLASSIFIES_FAMILY": "semantic_family",
                "CLASSIFIES_SEMANTIC_KIND": "own_semantic_kind",
                "ESTABLISHES_DEGREE_DOMAIN": "own_degree_domain",
            }[kind]
            value = claim["value"]
        else:
            # A permission, argument slot, reference binding or forbidden construction stays in the
            # profile. It is not a fact asserting the slot's content on the word.
            continue
        observations.append(Observation(profile["reading_id"], claim["source"], claim_id, field, value, True))
        if coordinate is not None:
            laws.append(
                Law("PROFILE:" + claim_id, (coordinate,), ((Cell(state),),), ((field, value),), claim["warrant"])
            )
    axiom = profile.get("definition_axiom") or {}
    withheld_decisions = []
    if axiom.get("review") == "EXAMINED":
        # Only the authored boundary declares silence, and only for the identified lexical unit.
        for decision in axiom["decisions"]:
            if decision["state"] != Cell.SILENT:
                continue
            if retained_decisions is not None and decision["decision_id"] not in retained_decisions:
                withheld_decisions.append(decision["decision_id"])
                continue
            laws.extend(
                Law(
                    f"PRIME_BOUNDARY:{decision['decision_id']}:{c}",
                    (c,),
                    ((Cell.SILENT,),),
                    (("prime_lexical_unit", profile["prime"]),),
                    decision["warrant"],
                )
                for c in decision["coordinates"]
            )
    ablated = {
        "claims": [c["claim_id"] for c in profile["claims"] if c not in compiled],
        "decisions": withheld_decisions,
    }
    return ReadingSeed(
        word=word,
        reading_id=profile["reading_id"],
        observations=tuple(observations),
        laws=laws,
        layout=partial(_profile_record, profile, word, compiled, ablated),
    )


def _profile_record(profile: dict, word: str, compiled: list[dict], ablated: dict, c: Construction) -> dict:
    return {
        "word": word,
        "reading_id": profile["reading_id"],
        "prime": profile["prime"],
        "code": "CONFLICT" if c.state.code == "CONFLICT" else "CANDIDATE_COMPLETE" if c.candidate else "PARTIAL",
        "source_scope": profile.get("source_scope", "SOURCED_PRIME_LEXICAL_UNIT"),
        "profile_status": profile["profile_status"],
        "production_eligible": False,
        "claims": compiled,
        "ablated": ablated,
        "definition_review": (profile.get("definition_axiom") or {}).get("review"),
        "definition_axiom": profile.get("definition_axiom"),
        "premise_record_ids": [claim["claim_id"] for claim in compiled],
        "rule_id": "LEXICAL_PROFILE:" + profile["reading_id"],
        "symbolic_before": c.initial.to_json(),
        "after_selection": c.state.to_json(),
        "after_closure": c.closed.to_json() if c.closed is not None else None,
        "candidate_vector": c.candidate,
        "model_calls": c.calls,
        "decisions": c.decisions,
        "number_scale": {
            "status": "NO_GAIN_ASSUMED",
            "family": profile.get("scale_family"),
            "native_ordinal_rank": None,
            "numeric_gain": None,
        },
    }


def foundation_readings(word: str, rulebook: dict, foundation: dict | None = None) -> list[dict]:
    """Explicit lexical-unit routing preserves homographs and native alternatives."""
    foundation = load_foundation() if foundation is None else foundation
    profiles = [profile for profile in foundation["profiles"] if word in profile["surfaces"]]
    profiles.extend(
        {
            **entry,
            "prime": None,
            "profile_status": "STRUCTURAL_LEXICAL_PROJECTION",
            "source_scope": "SCOPED_FUNCTION_WORD",
        }
        for entry in foundation["structural_entries"]
        if word in entry["surfaces"] and entry["claims"]
    )
    return [construct_reading(profile_seed(profile, word), rulebook, None) for profile in profiles]


def structural_entries(word: str, foundation: dict) -> list[dict]:
    """Function words retain constructions, binding requirements and basis gaps."""
    return [dict(entry) for entry in foundation["structural_entries"] if word in entry["surfaces"]]


def reconstruct_profile(
    profile: dict, rulebook: dict, retained_claims: set[str] | None = None, retained_decisions: set[str] | None = None
) -> dict:
    """Rebuild one profile with the shared solver and check each authored decision against it."""
    seed = profile_seed(profile, profile["surfaces"][0], retained_claims, retained_decisions)
    record = construct_reading(seed, rulebook, None)
    vector = {
        coordinate: domain[0] if len(domain) == 1 else "conflict" if not domain else "unresolved"
        for coordinate, domain in record["after_selection"]["domains"].items()
    }
    record["vector"] = vector
    axiom = profile.get("definition_axiom") or {}
    if axiom.get("review") != "EXAMINED":
        record["decision_checks"] = {}
        record["definition_check"] = "CONFLICT" if "conflict" in vector.values() else "BOUNDARY_PENDING"
        return record
    fired = record["after_selection"]["fired_rules"]
    laws = {
        law.rule_id: (law.coordinates, tuple(tuple(v.value for v in row) for row in law.allowed))
        for law in (*admitted_laws(rulebook), *seed.laws)
    }
    checks = {
        d["decision_id"]: decision_check(d["state"], d["derived_by"], d["coordinates"], vector, fired, laws)
        for d in axiom["decisions"]
    }
    record["decision_checks"] = checks
    record["provenance_policy"] = "INDEPENDENT_TARGET_ERASURE_V1"
    found = set(checks.values())
    record["definition_check"] = next(
        (
            code
            for code, members in (
                ("CONFLICT", {"CONFLICT"}),
                ("PROFILE_CONFLICT", {"VALUE_MISMATCH"}),
                ("PROVENANCE_MISMATCH", PROVENANCE_FAILURES),
                ("UNRESOLVED", {"UNRESOLVED"}),
            )
            if found & members
        ),
        "RECONSTRUCTED",
    )
    return record


def reconstruction(rulebook: dict, foundation: dict | None = None) -> dict:
    """Profiles are consequences of sourced facts and shared rules, not masks supplied as answers."""
    foundation = load_foundation() if foundation is None else foundation
    records = [reconstruct_profile(profile, rulebook) for profile in foundation["profiles"]]
    checks = Counter(r["definition_check"] for r in records)
    failed = any(
        r["code"] == "CONFLICT" or r["definition_check"] in {"CONFLICT", "PROFILE_CONFLICT", "PROVENANCE_MISMATCH"}
        for r in records
    )
    return {
        "basis_id": BASIS_ID,
        "schema": "GSE_FOUNDATION_RECONSTRUCTION_V3",
        "code": "FOUNDATION_CONFLICT"
        if failed
        else "RECONSTRUCTED_PRIME_FOUNDATION"
        if checks["RECONSTRUCTED"] == len(records)
        else "INCOMPLETE_PRIME_FOUNDATION",
        "definition_checks": dict(checks),
        "scope": "Examined primes rebuilt by the shared rules and checked decision by decision; an authored boundary "
        "is checked for consistency, not completeness; drafts close nothing; no ordinary word inherits a boundary",
        "lexical_primes": 72,
        "canonical_coordinates": 58,
        "number_is_lexical_prime": False,
        "records": records,
    }
