"""Explicit warranted rule admission after replaying a held-out audit packet.

This verifies the review contract and recorded model execution, not the truth of
an authored warrant. The warrant/review remains named authority, never model gold.
"""

import json
from dataclasses import asdict, replace

from .interchange import read_json
from .residual import _request_id
from .rule_history import digest, relation_records

CONVENTION_DECISION = "APPROVE_REPRESENTATIONAL_CONVENTION"


def _convention_authority(record, candidate):
    """Validate an explicit operator attestation, not a model-derived approval."""
    fields = {"format", "convention_id", "approval", "premises", "consequent", "guards"}
    if type(record) is not dict or set(record) != fields or record["format"] != "gse.approved-convention/1":
        raise ValueError("INVALID_CONVENTION_APPROVAL")
    approval = record["approval"]
    if (
        type(record["convention_id"]) is not str or not record["convention_id"].strip()
        or type(approval) is not dict or set(approval) != {"actor", "code", "question", "answer", "date"}
        or approval["actor"] != "Rohan" or approval["code"] != "APPROVED"
        or any(type(approval[k]) is not str or not approval[k].strip() for k in ("question", "answer", "date"))
    ):
        raise ValueError("EXPLICIT_FOUNDER_CONVENTION_APPROVAL_REQUIRED")
    left = candidate.get("premises") or ([candidate["antecedent"]] if candidate["antecedent"] else [])
    for pair in [record["consequent"], *(record["premises"] if type(record["premises"]) is list else [None])]:
        if (
            type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str
            or type(pair[1]) is not int or pair[1] not in (-1, 0, 1)
        ):
            raise ValueError("INVALID_CONVENTION_COORDINATES")
    if (
        record["premises"] != json.loads(json.dumps(left))
        or record["consequent"] != list(candidate["consequent"])
        or record["guards"] != json.loads(json.dumps(candidate["relation"]["guards"]))
        or candidate["warrant"]["kind"] != "APPROVED_GSE_CONVENTION"
    ):
        raise ValueError("CONVENTION_SCOPE_OR_WARRANT_MISMATCH")
    return "FOUNDER_APPROVED_CONVENTION_MODEL_AUDITS_DIAGNOSTIC"


class _AuditReplay:
    def __init__(self, records):
        self.records, self.index = records, 0

    @property
    def identity(self):
        if self.index >= len(self.records):
            raise ValueError("ADMISSION_AUDIT_EXHAUSTED")
        return self.records[self.index]["transport_identity"]

    def __call__(self, payload, schema):
        record = self.records[self.index]
        if _request_id(payload) != record["request_id"] or schema != record["schema"]:
            raise ValueError("ADMISSION_AUDIT_REQUEST_MISMATCH")
        self.index += 1
        return record["raw_output"]


def admit_records(raw, saved, review):
    """Return a pinned additive migration manifest; write no database or file."""
    from .reviewed_patterns import _relation, run_workflow_input

    required = {"rule_id", "review_id", "reviewer", "decision", "rationale", "source_refs", "warrant_sha256"}
    convention = type(review) is dict and review.get("decision") == CONVENTION_DECISION
    if type(review) is not dict or set(review) != required | ({"convention"} if convention else set()):
        raise ValueError("INVALID_RULE_ADMISSION_REVIEW")
    if review["decision"] not in ("APPROVE_DEFINITIONAL_RULE", CONVENTION_DECISION):
        raise ValueError("RULE_ADMISSION_NOT_APPROVED")
    if any(type(review[k]) is not str or not review[k].strip() for k in required - {"source_refs"}):
        raise ValueError("INVALID_RULE_ADMISSION_REVIEW")
    if (
        type(review["source_refs"]) is not list
        or not review["source_refs"]
        or any(type(v) is not str or not v.strip() for v in review["source_refs"])
    ):
        raise ValueError("RULE_ADMISSION_SOURCE_REQUIRED")
    if type(saved) is not dict or saved.get("input_sha256") != _request_id(raw):
        raise ValueError("RULE_ADMISSION_INPUT_MISMATCH")
    records = [a for c in saved["candidates"] for a in c["audits"] if a.get("model_calls") == 1]
    replay_transport = _AuditReplay(records)
    replay = run_workflow_input(raw, replay_transport, max_calls=saved["max_model_calls"])
    if replay_transport.index != len(records) or _request_id(replay) != _request_id(saved):
        raise ValueError("RULE_ADMISSION_AUDIT_REPLAY_MISMATCH")
    matches = [c for c in replay["candidates"] if c["relation"]["rule_id"] == review["rule_id"]]
    if len(matches) != 1:
        raise ValueError("RULE_ADMISSION_CANDIDATE_NOT_IDENTIFIED")
    candidate = matches[0]
    if (
        candidate["proposal_kind"] != "GUARDED_WARRANTED_PROPOSAL"
        or not candidate["warrant"]
        or candidate["warrant_sha256"] != review["warrant_sha256"]
    ):
        raise ValueError("RULE_ADMISSION_WARRANT_REQUIRED")
    if not candidate["discovery"] or any(r["code"] != "OBSERVED_AGREEMENT" for r in candidate["discovery"]):
        raise ValueError("RULE_ADMISSION_DISCOVERY_INCOMPLETE")
    if (
        not candidate["audits"]
        or any(
            r["code"] not in {"MODEL_AGREEMENT", "MODEL_COUNTEREXAMPLE", "MODEL_ABSTAINED"}
            if convention else r["code"] != "MODEL_AGREEMENT"
            for r in candidate["audits"]
        )
        or any(r["code"] != "STAGED_ONLY" for r in candidate["staging"])
    ):
        raise ValueError("RULE_ADMISSION_AUDIT_INCOMPLETE")
    authority = (
        _convention_authority(review["convention"], candidate)
        if convention else "SOURCE_BACKED_EXPLICIT_REVIEW_NOT_MODEL_GOLD"
    )
    relation = replace(_relation(json.loads(json.dumps(candidate["relation"]))), approved=True)
    if convention:
        relation = replace(
            relation, authority="foundational",
            provenance=(*relation.provenance, f"convention:{review['convention']['convention_id']}:{digest(review['convention'])}"),
        )
    baseline = tuple(_relation(r) for r in raw["relations"])
    if relation.rule_id in {r.rule_id for r in baseline}:
        raise ValueError("RULE_ADMISSION_ALREADY_PRESENT")
    return {
        "format": "gse.admitted-rule/2" if convention else "gse.admitted-rule/1",
        "code": "EXPLICIT_REPRESENTATIONAL_CONVENTION" if convention else "EXPLICIT_REVIEWED_RULE",
        "baseline_version": digest(relation_records(baseline)),
        "relation": asdict(relation),
        "warrant": candidate["warrant"],
        "review": review,
        "input_sha256": _request_id(raw),
        "audit_sha256": _request_id(saved),
        "audit": saved,
        "input": raw,
        "semantic_authority": authority,
        "lexicon_writes": False,
    }


def admit_rule(input_path, audit_path, review):
    """Strict file entry point for explicit admission; no database writes."""
    return admit_records(read_json(input_path), read_json(audit_path), review)


def verify_admission(record):
    """Recompute historical review, audit execution and relation from full inputs."""
    expected = admit_records(record["input"], record["audit"], record["review"])
    if digest(record) != digest(expected):
        raise ValueError("HISTORICAL_RULE_ADMISSION_MISMATCH")
