"""Explicit representation decisions retain diagnostic dissent; synthetic semantics."""

import json
from copy import deepcopy

import pytest
from test_lexicon_builder_rule_migration import Transport, packet

from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_admission import admit_records, verify_admission
from GSE.curation.lexicon_builder.validation import validate_build
from scripts.migrate_lexicon_rule import main


def convention_packet(tmp_path, value=0):
    source, input_path, audit_path, review = packet(tmp_path)
    raw = json.loads(input_path.read_text())
    raw["guarded_candidates"][0]["warrant"]["kind"] = "APPROVED_GSE_CONVENTION"
    audited = run_workflow_input(raw, Transport(value), max_calls=1)
    [candidate] = audited["candidates"]
    convention = {
        "format": "GSE.approved-convention/1",
        "convention_id": "synthetic:convention-contract-test",
        "approval": {
            "actor": "Rohan",
            "code": "APPROVED",
            "question": "Synthetic fixture approval?",
            "answer": "Synthetic fixture, not an actual semantic convention.",
            "date": "2026-11-18",
        },
        "premises": [],
        "consequent": ["WANT", 1],
        "guards": [["pos", "verb"]],
    }
    review.update(
        rule_id=candidate["relation"]["rule_id"],
        warrant_sha256=candidate["warrant_sha256"],
        decision="APPROVE_REPRESENTATIONAL_CONVENTION",
        convention=convention,
    )
    input_path.write_text(json.dumps(raw))
    audit_path.write_text(json.dumps(audited))
    return source, input_path, audit_path, raw, audited, review


@pytest.mark.parametrize("value", [-1, 0, None])
def test_real_cli_convention_migration_keeps_the_diagnostic_reply_and_history(tmp_path, monkeypatch, value):
    source, inputs, audit_path, raw, audited, review = convention_packet(tmp_path, value)
    ordinary = {k: v for k, v in review.items() if k != "convention"}
    ordinary["decision"] = "APPROVE_DEFINITIONAL_RULE"
    with pytest.raises(ValueError, match="AUDIT_INCOMPLETE"):
        admit_records(raw, audited, ordinary)
    admission = admit_records(raw, audited, review)
    assert admission["format"] == "GSE.admitted-rule/2"
    assert admission["semantic_authority"] == "FOUNDER_APPROVED_CONVENTION_MODEL_AUDITS_DIAGNOSTIC"
    assert admission["relation"]["authority"] == "foundational"
    assert json.loads(admission["audit"]["candidates"][0]["audits"][0]["raw_output"]) == {"WANT": value}
    verify_admission(admission)
    review_path, output, report = (tmp_path / name for name in ("review.json", "convention.db", "migration.json"))
    review_path.write_text(json.dumps(review))
    monkeypatch.setattr(
        "sys.argv",
        [
            "migrate",
            "--candidate",
            str(source),
            "--output",
            str(output),
            "--input",
            str(inputs),
            "--audit",
            str(audit_path),
            "--review",
            str(review_path),
            "--report",
            str(report),
        ],
    )
    assert main() == 0
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "unapproved",
        "actor",
        "answer",
        "consequent",
        "guards",
        "premises",
        "kind",
        "boolean",
        "audit",
    ],
)
def test_convention_approval_is_explicit_scope_bound_and_cannot_rewrite_the_audit(tmp_path, defect):
    _, _, _, raw, audited, review = convention_packet(tmp_path)
    if defect == "missing":
        review.pop("convention")
    elif defect == "unapproved":
        review["convention"]["approval"]["code"] = "PROPOSED"
    elif defect == "actor":
        review["convention"]["approval"]["actor"] = "model"
    elif defect == "answer":
        review["convention"]["approval"]["answer"] = ""
    elif defect == "consequent":
        review["convention"]["consequent"] = ["BE", 1]
    elif defect == "guards":
        review["convention"]["guards"] = []
    elif defect == "premises":
        review["convention"]["premises"] = [["BE", 1]]
    elif defect == "kind":
        raw["guarded_candidates"][0]["warrant"]["kind"] = "DEFINITIONAL_DERIVATION"
    elif defect == "boolean":
        review["convention"]["consequent"][1] = True
    else:
        audited = deepcopy(audited)
        audited["candidates"][0]["audits"][0]["raw_output"] = '{"WANT":1}'
    with pytest.raises(ValueError):
        admit_records(raw, audited, review)
