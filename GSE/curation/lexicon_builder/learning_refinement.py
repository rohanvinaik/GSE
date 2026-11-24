"""Verified audit contrasts feed the existing Regenesis guard imputer.

Native paths establish scope membership; model signs remain model evidence.
An imputed feature grants neither a warrant nor production rule authority.
"""

import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from GSE.namespace import identity_form

from .foundation import _attested_wordnet_lemma, _exact_wordnet_ancestry
from .learning_state import mechanism_id
from .residual import _request_id
from .reviewed_patterns import run_workflow_input
from .rule_history import digest


def provider_identity():
    try:
        from regenesis import induction, promotion_ledger
    except ModuleNotFoundError as error:
        if error.name == "regenesis" or (error.name or "").startswith("regenesis."):
            return {"code": "GUARD_IMPUTER_UNAVAILABLE", "provider": "regenesis.promotion_ledger"}
        raise
    return {
        "code": "GUARD_IMPUTER_AVAILABLE",
        "modules": {
            module.__name__: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            for module in (induction, promotion_ledger)
        },
    }


class _RecordedAudit:
    def __init__(self, records):
        identities = {row["transport_identity"] for row in records if row["model_calls"]}
        if len(identities) != 1:
            raise ValueError("REFINEMENT_REQUIRES_ONE_PINNED_AUDIT_TRANSPORT")
        [self.identity] = identities
        self.records = {row["request_id"]: row for row in records if row["model_calls"]}

    def __call__(self, payload, schema):
        row = self.records[_request_id(payload)]
        if identity_form(payload) != identity_form(row["request"]) or schema != row["schema"]:
            raise ValueError("REFINEMENT_AUDIT_REQUEST_CHANGED")
        return row["raw_output"]


def propose_refinements(raw, audited, family, selected, taught, witness):
    """Replay the saved audit before using positive/negative observations."""
    result = {
        "code": "REFINEMENT_REQUIRES_TYPED_CONTRAST",
        "provider": provider_identity(),
        "parent_mechanism_id": mechanism_id(family.relation()),
        "input_sha256": digest(raw),
        "audit_sha256": digest(audited),
        "candidates": [],
        "reservations": [],
        "counterexamples": [],
        "model_calls": 0,
        "bank_writes": 0,
    }
    [report] = audited["candidates"]
    records = report["audits"]
    if not any(row["code"] == "MODEL_COUNTEREXAMPLE" for row in records):
        result["reservations"] = [row for row in records if row["code"] != "MODEL_AGREEMENT"]
        return result
    if any(row["model_calls"] and type(row.get("raw_output")) is not str for row in records):
        return {**result, "code": "REFINEMENT_AUDIT_REPLAY_UNAVAILABLE"}
    replayed = run_workflow_input(raw, _RecordedAudit(records), max_calls=audited["max_model_calls"])
    if digest(identity_form(replayed)) != digest(identity_form(audited)):
        raise ValueError("REFINEMENT_AUDIT_REPLAY_MISMATCH")
    entries = {row["definition"]["entry_id"]: row for row in raw["entries"]}

    def types(identity):
        entry = entries[identity]
        if entry["definition"]["pos"] != "noun":
            return frozenset()
        return frozenset().union(
            *(
                _exact_wordnet_ancestry(entry["definition"], observation)
                for observation in entry["observations"]
                if _attested_wordnet_lemma(entry["definition"], observation)
            )
        )

    positives = {selected["entry_id"]: types(selected["entry_id"])}
    negatives = {}
    for row in records:
        if row["code"] == "MODEL_AGREEMENT":
            positives[row["entry_id"]] = types(row["entry_id"])
        elif row["code"] == "MODEL_COUNTEREXAMPLE":
            negatives[row["entry_id"]] = types(row["entry_id"])
            result["counterexamples"].append(
                {
                    "entry_id": row["entry_id"],
                    "bank": row["bank"],
                    "value": row["value"],
                    "request_id": row["request_id"],
                    "audit_sha256": digest(row),
                    "native_types": sorted(negatives[row["entry_id"]]),
                    "sign_authority": "BOUNDED_MODEL_AUDIT_NOT_NATIVE_ASSERTION",
                }
            )
        else:
            result["reservations"].append(row)
    if not positives or not negatives or any(not evidence for evidence in (*positives.values(), *negatives.values())):
        return {**result, "code": "REFINEMENT_NATIVE_CONTRAST_UNAVAILABLE"}
    if result["provider"]["code"] != "GUARD_IMPUTER_AVAILABLE":
        return {**result, "code": "GUARD_IMPUTER_UNAVAILABLE"}
    from regenesis.promotion_ledger import impute_guard_candidates

    def fillers(records):
        return [
            SimpleNamespace(name=identity, bundle=[SimpleNamespace(types=sorted(evidence))])
            for identity, evidence in sorted(records.items())
        ]

    guards = impute_guard_candidates(fillers(positives), fillers(negatives))
    for ancestor in guards:
        guard = ("wordnet_ancestor:" + ancestor, "true")
        if guard in family.guards:
            continue
        child = replace(
            family, id="unadmitted-refinement", guards=tuple(sorted((*family.guards, guard))), holdouts=(), warrant={}
        )
        result["candidates"].append(
            {
                "proposal": child.proposal(),
                "origin": "COUNTEREXAMPLE_GUARD_IMPUTATION",
                "authority": "UNADMITTED_SCOPE_HYPOTHESIS_REQUIRES_WARRANT_AND_FRESH_AUDIT",
                "evidence": {
                    "entry_id": selected["entry_id"],
                    "source_sha256": witness["source_sha256"],
                    "taught": taught,
                    "parent_mechanism_id": result["parent_mechanism_id"],
                    "audit_sha256": digest(audited),
                    "provider": result["provider"],
                    "positive_native_types": {identity: sorted(values) for identity, values in positives.items()},
                    "counterexamples": result["counterexamples"],
                },
            }
        )
    result["code"] = "IMPUTED_GUARDS_AWAITING_WARRANT" if result["candidates"] else "NO_SEPARATING_ATOMIC_GUARD"
    return result
