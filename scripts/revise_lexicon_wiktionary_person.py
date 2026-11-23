"""Stage and replay the native single-person-genus definition projection."""

import argparse
import json
from contextlib import closing
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import connect, fingerprint, read, record
from GSE.curation.lexicon_builder.residual import _request_id
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.source_enrichment import (
    forecast_wiktionary_projection,
    revise_source_candidate,
    wiktionary_projection_scope,
)
from GSE.lexicon_resource import ACTIVE_POINTER

FORMAT = "gse.wiktionary-person-projection-revision/1"


def _audit_support(scope, audit):
    if audit.get("format") != "gse.wiktionary-person-source-audit/1" or audit.get("candidate_writes") is not False:
        raise ValueError("INVALID_WIKTIONARY_PERSON_AUDIT")
    supporting = []
    for case in audit["results"]:
        entry_id = case["entry_id"]
        if entry_id not in scope:
            continue
        if (
            case["bank"] != "SOMEONE"
            or case["outcome"] != "ASSIGNED"
            or type(case["value"]) is not int
            or case["value"] != 1
            or json.loads(case["raw"]) != {"SOMEONE": 1}
            or _request_id(case["request"]) != case["request_id"]
            or case["request"]["entry_id"] != entry_id
            or not any(source in case["request"]["observations"] for source in scope[entry_id])
        ):
            raise ValueError("WIKTIONARY_PERSON_AUDIT_DISAGREEMENT:" + entry_id)
        supporting.append(entry_id)
    lemmas = {scope[entry][0]["features"]["lemma"] for entry in supporting}
    if len(lemmas) < 3:
        raise ValueError("WIKTIONARY_PERSON_AUDIT_SCOPE_UNDERCOVERED")
    return sorted(supporting)


def forecast(conn, audit, *, apply=False):
    scope = wiktionary_projection_scope(conn, "SOMEONE")
    supporting = _audit_support(scope, audit)
    return {
        "changes": forecast_wiktionary_projection(conn, scope, "SOMEONE", apply=apply),
        "independent_audit_entries": supporting,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage", "apply"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-replay", type=Path)
    parser.add_argument("--stage-report", type=Path)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise ValueError("WIKTIONARY_PERSON_REPORT_MUST_BE_NEW")
    audit = read(args.audit)
    if args.phase == "stage":
        source = fingerprint(args.candidate)
        pointer = fingerprint(ACTIVE_POINTER)
        if source != audit["candidate_sha256"] or pointer != audit["active_pointer_sha256"]:
            raise ValueError("WIKTIONARY_PERSON_STAGE_REQUIRES_PINNED_AUDIT")
        with closing(connect(args.candidate)) as conn:
            result = forecast(conn, audit)
        if fingerprint(args.candidate) != source or fingerprint(ACTIVE_POINTER) != pointer:
            raise ValueError("WIKTIONARY_PERSON_STAGE_INPUT_CHANGED")
        report = {
            "format": FORMAT,
            "code": "WIKTIONARY_PERSON_STAGED",
            "candidate_sha256": source,
            "active_pointer_sha256": pointer,
            "audit_sha256": digest(audit),
            "candidate_writes": False,
            **result,
        }
    else:
        if args.output is None or args.baseline_replay is None or args.stage_report is None:
            parser.error("apply requires --output, --baseline-replay, and --stage-report")
        if args.output.resolve() == args.report.resolve():
            raise ValueError("WIKTIONARY_PERSON_OUTPUT_REPORT_COLLISION")
        staged = read(args.stage_report)
        baseline = read(args.baseline_replay)
        if (
            staged["format"] != FORMAT
            or staged["code"] != "WIKTIONARY_PERSON_STAGED"
            or staged["audit_sha256"] != digest(audit)
            or staged["active_pointer_sha256"] != baseline["active_pointer_sha256"]
        ):
            raise ValueError("WIKTIONARY_PERSON_STAGE_REQUIRED")

        def apply_revision(conn):
            result = forecast(conn, audit, apply=True)
            if (
                result["changes"] != staged["changes"]
                or result["independent_audit_entries"] != staged["independent_audit_entries"]
            ):
                raise ValueError("WIKTIONARY_PERSON_STAGED_EFFECT_CHANGED")
            return result["changes"]

        report = revise_source_candidate(
            args.candidate,
            args.output,
            baseline,
            apply_revision,
            format_tag=FORMAT,
            metadata_key="wiktionary_person_projection_revision",
        )
        report["stage_sha256"] = digest(staged)
        report["audit_sha256"] = digest(audit)
    record(args.report, report)
    changes = report["changes"]
    if not isinstance(changes, list):
        raise ValueError("INVALID_SOURCE_REVISION_CHANGES")
    print(json.dumps({"code": report["code"], "definitions_changed": len(changes)}), flush=True)


if __name__ == "__main__":
    main()
