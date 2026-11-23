"""Stage and replay the exact Wiktionary anatomy projection from an active release."""

import argparse
import json
import tempfile
from contextlib import closing
from pathlib import Path

from GSE.curation.external_sources.wiktionary import native_anatomy_witness
from GSE.curation.lexicon_builder.epoch import connect, exact_delta, fingerprint, make_questions, read, record
from GSE.curation.lexicon_builder.residual import _read_value
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.source_enrichment import (
    forecast_wiktionary_projection,
    revise_source_candidate,
    wiktionary_projection_scope,
)
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from GSE.namespace import current_id, identity_form

FORMAT = "GSE.wiktionary-anatomy-projection-revision/2"


def active_baseline(release):
    active = resolve_lexicon_path()
    pointer = fingerprint(ACTIVE_POINTER)
    if (
        release.get("code") != "PUBLISHED_SPARSE_LEXICON"
        or release.get("path") != str(active)
        or fingerprint(active) != release.get("sha256")
    ):
        raise ValueError("WIKTIONARY_ANATOMY_REQUIRES_ACTIVE_RELEASE")
    return active, {
        "candidate_sha256": release["sha256"],
        "active_pointer_sha256": pointer,
        "replay": release["replay"],
    }


def scope_witnesses(scope):
    witnesses = {}
    for entry_id, observations in scope.items():
        features = observations[0]["features"]
        proof = native_anatomy_witness(features["definition"], features["pos"], features["native_sense"])
        if proof is None:
            raise ValueError("WIKTIONARY_ANATOMY_MISSING_WITNESS:" + entry_id)
        genus, construction = proof
        witnesses[entry_id] = {
            "lemma": features["lemma"],
            "definition": features["definition"],
            "genus": genus,
            "construction": construction,
        }
    return witnesses


def audit_support(active, witnesses, audit, baseline):
    if (
        current_id(audit.get("format")) != "GSE.wiktionary-anatomy-genus-audit/1"
        or audit.get("candidate_writes") is not False
        or audit.get("candidate_sha256") != baseline["candidate_sha256"]
        or audit.get("active_pointer_sha256") != baseline["active_pointer_sha256"]
    ):
        raise ValueError("WIKTIONARY_ANATOMY_REQUIRES_ACTIVE_AUDIT")
    cases = audit["results"]
    identities = [case["entry_id"] for case in cases]
    if len(set(identities)) != len(identities) or any(
        case["entry_id"] not in witnesses or case.get("bank") != "BODY" for case in cases
    ):
        raise ValueError("WIKTIONARY_ANATOMY_INVALID_AUDIT_SCOPE")
    questions = make_questions(active, ((entry_id, "BODY") for entry_id in identities))
    supported = {}
    for entry_id, case, question in zip(identities, cases, questions, strict=True):
        if (
            case.get("outcome") != "AGREES"
            or type(case.get("value")) is not int
            or case["value"] != 1
            or len(question.allowed_values) < 2
            or question.request_id != case.get("request_id")
            or identity_form(question.payload()) != identity_form(case.get("request"))
            or identity_form(question.output_schema()) != identity_form(case.get("schema"))
            or _read_value(case["raw"], question) != 1
        ):
            raise ValueError("WIKTIONARY_ANATOMY_AUDIT_DISAGREEMENT:" + entry_id)
        supported[entry_id] = witnesses[entry_id]
    forms = {row["construction"] for row in witnesses.values()} - {"genus"}
    if len({row["genus"] for row in supported.values()}) < 3 or forms - {
        row["construction"] for row in supported.values()
    }:
        raise ValueError("WIKTIONARY_ANATOMY_AUDIT_SCOPE_UNDERCOVERED")
    return supported


def publish_revision(active, stage, destination, gold, revise):
    """Validate and publish using an owned working database with a bounded lifetime."""
    from GSE.curation.lexicon_builder.publication import publish_sparse
    from scripts.audit_lexicon_runtime import audit_sparse_runtime

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".anatomy-round-", dir=destination.parent) as directory:
        candidate = Path(directory) / "candidate.db"
        report = revise(candidate)
        expected = {
            (row["entry_id"], change["bank"]): (change["before"], change["after"])
            for row in stage["changes"]
            for change in row["domains"]
        }
        checked, delta = exact_delta(active, candidate)
        actual = {(row["entry_id"], row["bank"]): (row["before"], row["after"]) for row in delta}
        if checked != report["replay"]["entries_checked"] or actual != expected:
            raise ValueError("WIKTIONARY_ANATOMY_PUBLICATION_DELTA_MISMATCH")
        runtime = audit_sparse_runtime(candidate)
        report.update(definitions_compared=checked, runtime=runtime)
        if runtime["code"] != "SPARSE_RUNTIME_VALIDATED":
            release = {"code": "PUBLICATION_BLOCKED", "blockers": [runtime["code"]]}
        else:
            release = publish_sparse(
                candidate,
                destination,
                gold,
                expected_sha256=report["candidate_sha256"],
                expected_pointer_sha256=report["active_pointer_sha256"],
            )
        report["publication"] = release
        report["activation_performed"] = release["code"] == "PUBLISHED_SPARSE_LEXICON"
        report["candidate"] = release.get("path")
    report["working_database"] = "RETIRED"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage", "apply"))
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--stage-report", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--publish-sparse-to", type=Path)
    parser.add_argument("--release-gold", type=Path)
    args = parser.parse_args()
    if bool(args.publish_sparse_to) != bool(args.release_gold) or (
        args.publish_sparse_to and (args.phase != "apply" or args.output)
    ):
        parser.error("Sparse publication requires apply, --publish-sparse-to, and --release-gold in place of --output")
    if args.report.exists() or args.report.is_symlink():
        raise ValueError("WIKTIONARY_ANATOMY_REPORT_MUST_BE_NEW")
    active, baseline = active_baseline(read(args.release))
    if args.phase == "stage":
        with closing(connect(active)) as conn:
            scope = wiktionary_projection_scope(conn, "BODY", pending_only=True)
            witnesses = scope_witnesses(scope)
            changes = forecast_wiktionary_projection(conn, scope, "BODY")
        if fingerprint(ACTIVE_POINTER) != baseline["active_pointer_sha256"]:
            raise ValueError("WIKTIONARY_ANATOMY_ACTIVE_BASELINE_CHANGED")
        report = {
            "format": FORMAT,
            "code": "WIKTIONARY_ANATOMY_STAGED",
            "baseline": baseline,
            "witnesses": witnesses,
            "changes": changes,
        }
    else:
        if args.stage_report is None or args.audit is None or (args.output is None and args.publish_sparse_to is None):
            parser.error("apply requires --stage-report, --audit, and --output or --publish-sparse-to")
        target = args.publish_sparse_to or args.output
        if args.report.resolve() == target.resolve():
            raise ValueError("WIKTIONARY_ANATOMY_OUTPUT_REPORT_COLLISION")
        stage, audit = read(args.stage_report), read(args.audit)
        if (
            current_id(stage.get("format")) != FORMAT
            or stage.get("code") != "WIKTIONARY_ANATOMY_STAGED"
            or stage.get("baseline") != baseline
        ):
            raise ValueError("WIKTIONARY_ANATOMY_REQUIRES_PINNED_STAGE")
        with closing(connect(active)) as conn:
            scope = wiktionary_projection_scope(conn, "BODY", pending_only=True)
        witnesses = scope_witnesses(scope)
        if not witnesses or witnesses != stage.get("witnesses"):
            raise ValueError("WIKTIONARY_ANATOMY_STAGE_SCOPE_CHANGED")
        audited = audit_support(active, witnesses, audit, baseline)

        def apply_revision(conn):
            current = wiktionary_projection_scope(conn, "BODY", pending_only=True)
            changes = forecast_wiktionary_projection(conn, current, "BODY", apply=True)
            if current != scope or changes != stage["changes"]:
                raise ValueError("WIKTIONARY_ANATOMY_STAGED_EFFECT_CHANGED")
            return changes

        def revise(output):
            return revise_source_candidate(
                active,
                output,
                baseline,
                apply_revision,
                format_tag=FORMAT,
                metadata_key="wiktionary_anatomy_projection_revision:" + baseline["candidate_sha256"],
            )

        if args.publish_sparse_to:
            report = publish_revision(active, stage, args.publish_sparse_to, args.release_gold, revise)
        else:
            report = revise(args.output)
        report.update(stage_sha256=digest(stage), audit_sha256=digest(audit), audit_witnesses=audited)
    record(args.report, report)
    print(json.dumps({"code": report["code"], "definitions_changed": len(report["changes"])}), flush=True)
    publication = report.get("publication")
    if isinstance(publication, dict) and publication.get("code") == "PUBLICATION_BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
