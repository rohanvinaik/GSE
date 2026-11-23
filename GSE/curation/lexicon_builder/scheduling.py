"""Question ordering only: neither frequency nor scheduling supplies a sign."""

from __future__ import annotations

import heapq
from bisect import insort

from .relevance import validate_bank_relevance
from .residual import _scaffold

COHORT_POLICIES = ("definition", "spelling")
BANK_PRIORITIES = ("constraint", "evidence")
POLICY_VERSION = "GSE.completion-question-order/1"


def question_order_policy(cohort_policy, bank_priority):
    """Validate before database access; the version pins resume semantics."""
    if cohort_policy not in COHORT_POLICIES:
        raise ValueError("INVALID_COMPLETION_COHORT_POLICY")
    if bank_priority not in BANK_PRIORITIES:
        raise ValueError("INVALID_COMPLETION_BANK_PRIORITY")
    return {
        "policy": POLICY_VERSION,
        "cohort_policy": cohort_policy,
        "bank_priority": bank_priority,
        "semantic_authority": "NONE_QUESTION_ORDER_ONLY",
        "cohort_order": "CASEFOLDED_SPELLING_ROUNDS_THEN_EXISTING_PRIORITY"
        if cohort_policy == "spelling"
        else "EXISTING_DEFINITION_PRIORITY",
        "bank_order": "DOMAIN_SIZE_THEN_EXPLICIT_EVIDENCE_THEN_ACTIVE_UNRESOLVED_NEIGHBORS_THEN_BANK"
        if bank_priority == "evidence"
        else "DOMAIN_SIZE_THEN_BANK",
    }


def spelling_cohort(rows, limit):
    """Take one definition per spelling per round, retaining every remainder.

    Rows carry compact priority keys and spellings, not source contexts. At
    most ``limit`` keys per spelling are retained: a later member cannot enter
    this cohort. Frequencies still order each round; no sense frequencies are
    inferred. The caller's durable visited IDs remove only completed visits.
    """
    by_spelling = {}
    count = 0
    for key, spelling in rows:
        count += 1
        members = by_spelling.setdefault(spelling, [])
        insort(members, key)
        if len(members) > limit:
            members.pop()
    selected = []
    for depth in range(limit):
        round_keys = (members[depth] for members in by_spelling.values() if len(members) > depth)
        selected.extend(heapq.nsmallest(limit - len(selected), round_keys))
        if len(selected) == limit or len(selected) == count:
            break
    return tuple(selected), count > len(selected)


def pending_banks(
    resolution, chosen_banks, attempted, *, policy="constraint", observations=(), relations=(), context=None
):
    """Order unresolved banks using existing typed evidence and rule proofs.

    Missing relevance is unknown, not affirmative evidence for every bank and
    not absence evidence. Advisory projection banks may select a question but
    their suggested signs are never read. Only ACTIVE approved tables in the
    existing scaffold contribute connectivity; blocked/excepted tables do not.
    """
    if policy not in BANK_PRIORITIES:
        raise ValueError("INVALID_COMPLETION_BANK_PRIORITY")
    remaining = tuple(bank for bank in chosen_banks if len(resolution.domains[bank]) > 1 and bank not in attempted)
    if policy == "constraint" or not remaining:
        return tuple(sorted(remaining, key=lambda bank: (len(resolution.domains[bank]), bank)))
    evidence = set()
    for observation in observations:
        features = observation.get("features", {})
        if "bank_relevance" in features:
            evidence.update(validate_bank_relevance(features["bank_relevance"]))
        # Candidate records have already passed the native evidence contract.
        # This selection never consumes suggested_values or narrows a domain.
        evidence.update(item["bank"] for item in features.get("projection_candidates", ()))
    neighbors = {bank: set() for bank in remaining}
    scaffold = _scaffold(resolution, relations, context, remaining[0])
    for rule in scaffold["approved_relations"]:
        if rule["disposition"] != "ACTIVE":
            continue
        unresolved = {bank for bank in rule["banks"] if len(resolution.domains[bank]) > 1}
        for bank in unresolved.intersection(neighbors):
            neighbors[bank].update(unresolved - {bank})
    return tuple(
        sorted(
            remaining,
            key=lambda bank: (
                len(resolution.domains[bank]),
                -int(bank in evidence),
                -len(neighbors[bank]),
                bank,
            ),
        )
    )
