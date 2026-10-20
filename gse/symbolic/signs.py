"""Public located evidence from the builder's existing sign ownership decisions."""

from collections import defaultdict

from gse.api.trace import OperationTrace
from gse.nlp.morphology import NEGATION, REVERSAL
from gse.symbolic.expression import _sign_owners, node_negation_count, node_polarity


def negation_signs(trace: OperationTrace) -> dict:
    """Retain cancelled syntactic signs and verified lexical negations separately.

    Owner polarity is a construction decision, not categorical commitment.
    Hierarchy direction is explicit and excluded from clause-negation counts.
    Reversals do not contribute a negative sign. No word prefix is inferred here.
    """
    if not isinstance(trace, OperationTrace):
        return {
            "schema": "gse.signs/1",
            "state": "unread",
            "reason": "invalid_trace",
            "owners": [],
            "lexical": [],
            "count": None,
        }
    grouped = defaultdict(list)
    unresolved, lexical, reversals = [], [], []
    for position, (code, owner, lemma) in _sign_owners(trace.tokens).items():
        item = {"position": position, "lemma": lemma, "owner": owner, "decision": code}
        if code == "none":
            unresolved.append(item)
        else:
            grouped[(code, owner)].append(item)
    owners: list[dict] = []
    for (code, owner), items in sorted(grouped.items()):
        lemmas = [item["lemma"] for item in items]
        owners.append(
            {
                "owner": owner,
                "decision": code,
                "sources": items,
                "count": node_negation_count(lemmas),
                "polarity": node_polarity(lemmas),
                "mechanism": "hierarchy_direction" if code == "hierarchy" else "syntactic_negation",
            }
        )
    for token in trace.tokens:
        evidence = token.negation_evidence
        if evidence.get("feature") == NEGATION and evidence.get("state") == "resolved":
            lexical.append(
                {
                    "position": token.position,
                    "lemma": token.lemma,
                    "base": evidence.get("base"),
                    "mechanism": "lexical_negation",
                    "count": 1,
                    "evidence": evidence,
                }
            )
        elif evidence.get("feature") == REVERSAL:
            reversals.append({"position": token.position, "lemma": token.lemma, "evidence": evidence})
        elif evidence.get("state") in {"unread", "unresolved"}:
            unresolved.append({"position": token.position, "lemma": token.lemma, "evidence": evidence})
    count = sum(item["count"] for item in owners if item["mechanism"] == "syntactic_negation") + len(lexical)
    return {
        "schema": "gse.signs/1",
        "state": "partial" if unresolved else "read",
        "count": count,
        "owners": owners,
        "lexical": lexical,
        "reversals": reversals,
        "unresolved": unresolved,
        "policy": "builder_sign_owners_correlative_count/1",
    }
