"""Compare identical bounded questions across single and batch presentations.

This read-only assay consumes explicit labels; it cannot approve a rule, supply
independent gold, or write a candidate lexicon. Scope exclusions are scored as
exclusions rather than converted into an expected zero.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.interchange import read_json
from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport
from gse.curation.lexicon_builder.model_protocol import model_input
from gse.curation.lexicon_builder.residual import BankRequest, OllamaTransport
from scripts.audit_lexicon_model_protocol import calibration_results, prepare_case

INPUT_FORMAT = "gse.lexicon-contrast-cases/1"
REPORT_FORMAT = "gse.lexicon-contrast-audit/1"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def prepare_contrast(payload, *, production_scaffold=True):
    """Replay an explicitly pinned historical question without rebuilding it.

    This audit-only route checks serialization and wire validity. It does not
    certify the archived source semantics or authorize any database assignment.
    Fresh fixtures continue through the existing production-scaffold preparer.
    """
    if payload.get("format") != "gse.bank-request/2":
        return prepare_case(payload, production_scaffold=production_scaffold)
    try:
        request = BankRequest(
            entry_id=payload["entry_id"],
            bank=payload["bank"],
            allowed_values=tuple(payload["allowed_values"]),
            known=payload["known"],
            observations=tuple(payload["observations"]),
            request_id=digest(payload),
            definition=Definition(**payload["definition"]),
            scaffold=payload["scaffold"],
        )
        if request.payload() != payload or request.entry_id != request.definition.entry_id:
            raise ValueError("ARCHIVED_CONTRAST_REQUEST_MISMATCH")
        model_input(request.payload())
    except (KeyError, TypeError) as exc:
        raise ValueError("INVALID_ARCHIVED_CONTRAST_REQUEST") from exc
    return request, None


def validate_cases(fixture):
    """Reject ambiguous labels and direct target leakage before any dispatch."""
    if type(fixture) is not dict or set(fixture) != {"format", "cases"} or fixture["format"] != INPUT_FORMAT:
        raise ValueError("INVALID_CONTRAST_FIXTURE")
    cases = fixture["cases"]
    if type(cases) is not list or not 2 <= len(cases) <= 64:
        raise ValueError("INVALID_CONTRAST_CASE_COUNT")
    ids = set()
    for case in cases:
        if (
            type(case) is not dict
            or not {"id", "class", "input", "expectation", "authority"} <= case.keys()
            or set(case) - {"id", "class", "input", "expectation", "authority", "archived_request_sha256"}
        ):
            raise ValueError("INVALID_CONTRAST_CASE")
        for key in ("id", "class"):
            if type(case[key]) is not str or not case[key].strip():
                raise ValueError("INVALID_CONTRAST_CASE")
        if case["id"] in ids:
            raise ValueError("DUPLICATE_CONTRAST_CASE")
        ids.add(case["id"])
        authority = case["authority"]
        if type(authority) is not dict or set(authority) != {"kind", "source", "rationale"}:
            raise ValueError("INVALID_CONTRAST_AUTHORITY")
        if any(type(value) is not str or not value.strip() for value in authority.values()):
            raise ValueError("INVALID_CONTRAST_AUTHORITY")
        expectation = case["expectation"]
        if type(expectation) is not dict:
            raise ValueError("INVALID_CONTRAST_EXPECTATION")
        kind = expectation.get("kind")
        if kind == "EXACT" and set(expectation) == {"kind", "value"}:
            value = expectation["value"]
            if value is not None and (type(value) is not int or value not in (-1, 0, 1)):
                raise ValueError("INVALID_CONTRAST_EXPECTATION")
        elif kind == "FORBIDDEN_VALUES" and set(expectation) == {"kind", "values"}:
            values = expectation["values"]
            if (
                type(values) is not list
                or not values
                or any(type(value) is not int or value not in (-1, 0, 1) for value in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError("INVALID_CONTRAST_EXPECTATION")
        elif expectation != {"kind": "OBSERVE"}:
            raise ValueError("INVALID_CONTRAST_EXPECTATION")
        payload = case["input"]
        if type(payload) is not dict or type(payload.get("known", {})) is not dict:
            raise ValueError("INVALID_CONTRAST_INPUT")
        if payload.get("bank") in payload.get("known", {}):
            raise ValueError("CONTRAST_TARGET_ALREADY_SUPPLIED")
        if payload.get("format") == "gse.bank-request/2":
            if case.get("archived_request_sha256") != digest(payload):
                raise ValueError("ARCHIVED_CONTRAST_REQUEST_HASH_MISMATCH")
        elif "archived_request_sha256" in case:
            raise ValueError("ARCHIVED_CONTRAST_REQUEST_FORMAT_REQUIRED")
        # Preparation validates definitions and all supplied source/restriction
        # fields. Expected outcomes and review metadata never enter this input.
        try:
            prepare_contrast(payload, production_scaffold=True)
        except (KeyError, TypeError) as exc:
            raise ValueError("INVALID_CONTRAST_INPUT") from exc
    return copy.deepcopy(cases)


def assess(expectation, result):
    """A non-forbidden sign is unadjudicated, not an identified zero."""
    if "value" not in result:
        return result["code"]
    value = result["value"]
    if result["code"] == "SYMBOLICALLY_RESOLVED":
        if expectation["kind"] == "EXACT" and value != expectation["value"]:
            return "SYMBOLIC_EXPECTATION_MISMATCH"
        return "SYMBOLICALLY_RESOLVED_NOT_MODEL_TESTED"
    kind = expectation["kind"]
    if kind == "EXACT":
        if value is None:
            return "EXPECTED_ABSTENTION" if expectation["value"] is None else "ABSTAINED"
        return "IDENTIFIED" if value == expectation["value"] else "WRONG"
    if kind == "FORBIDDEN_VALUES" and value in expectation["values"]:
        return "SCOPE_VIOLATION"
    return "ABSTAINED" if value is None else "NOT_ADJUDICATED"


def summarize(records, cases, *, expected_presentations=4):
    """Keep semantic outcomes and context sensitivity as separate measurements."""
    groups, per_class = defaultdict(list), defaultdict(Counter)
    for record in records:
        groups[record["case_id"]].append(record)
        per_class[record["class"]][record["assessment"]] += 1
    comparisons = []
    for case in cases:
        rows = groups[case["id"]]
        answers = [row for row in rows if row["model_answer"]]
        request_ids = {row["request_id"] for row in answers}
        values = {json.dumps(row["value"]) for row in answers}
        code = (
            "REQUEST_CHANGED"
            if len(request_ids) > 1
            else "CONTEXT_SENSITIVE"
            if len(values) > 1
            else "BATCH_COMPARISON_NOT_EXERCISED"
            if len(answers) == expected_presentations
            and any(
                row["presentation"] not in {"SINGLE", "BATCH_SINGLETON"} and len(row["invocation_case_ids"]) < 2
                for row in answers
            )
            else "STABLE_OBSERVED"
            if len(answers) == expected_presentations
            else "INCOMPLETE_COMPARISON"
        )
        comparisons.append(
            {
                "case_id": case["id"],
                "code": code,
                "model_answers": len(answers),
                "request_ids": sorted(request_ids),
                "conditions": [
                    {
                        "presentation": row["presentation"],
                        "assessment": row["assessment"],
                        "value": row.get("value"),
                        "value_present": "value" in row,
                        "invocation_case_ids": row["invocation_case_ids"],
                    }
                    for row in rows
                ],
            }
        )
    return {
        "per_class": {key: dict(counts) for key, counts in sorted(per_class.items())},
        "comparisons": comparisons,
        "semantic_findings": sum(
            row["assessment"] in {"WRONG", "SCOPE_VIOLATION", "SYMBOLIC_EXPECTATION_MISMATCH"} for row in records
        ),
        "context_sensitive_cases": sum(row["code"] == "CONTEXT_SENSITIVE" for row in comparisons),
        "request_changed_cases": sum(row["code"] == "REQUEST_CHANGED" for row in comparisons),
    }


def contrast_reports(fixture, single, batched, *, budget, batch_size=4, include_singleton_batch=False):
    """Yield durable report snapshots; budget counts questions across all arms."""
    cases = validate_cases(fixture)
    if type(budget) is not int or budget < 0:
        raise ValueError("INVALID_CONTRAST_BUDGET")
    if type(batch_size) is not int or batch_size < 2:
        raise ValueError("INVALID_CONTRAST_BATCH_SIZE")
    positions = list(range(len(cases)))
    presentations = (
        ("SINGLE", positions, single, 1),
        ("BATCH_FORWARD", positions, batched, batch_size),
        ("BATCH_REVERSED", positions[::-1], batched, batch_size),
        ("BATCH_ROTATED", positions[1:] + positions[:1], batched, batch_size),
    )
    if include_singleton_batch:
        presentations = (presentations[0], ("BATCH_SINGLETON", positions, batched, 1), *presentations[1:])
    records, questions, invocations = [], 0, 0
    for presentation, order, transport, size in presentations:
        selected = [cases[index] for index in order]
        calibration = [
            {
                "input": case["input"],
                # This label is retained only by the existing audit scorer;
                # our assessment below handles exclusion-only/observation cases.
                "expected": case["expectation"].get("value"),
            }
            for case in selected
        ]
        spent, dispatched = questions, invocations
        for index, result, used, calls in calibration_results(
            calibration,
            transport,
            budget=budget - spent,
            batch_size=size,
            production_scaffold=True,
            prepare=prepare_contrast,
        ):
            case = selected[index]
            questions, invocations = spent + used, dispatched + calls
            model_answer = "value" in result and result["code"] != "SYMBOLICALLY_RESOLVED"
            assessment = assess(case["expectation"], result)
            record = {
                **result,
                "case_id": case["id"],
                "class": case["class"],
                "authority": case["authority"],
                "expectation": case["expectation"],
                "assessment": assessment,
                "code": assessment,
                "legacy_calibration_label_diagnostic": result["code"],
                "presentation": presentation,
                "transport_identity": transport.identity,
                "request_id": digest(result["input"])
                if result["input"].get("format") == "gse.bank-request/2"
                else None,
                "model_answer": model_answer,
                "invocation_case_ids": [selected[position]["id"] for position in result["invocation_case_indices"]],
            }
            for key in ("expected", "expected_class", "expected_agreement", "invocation_case_indices"):
                record.pop(key, None)
            records.append(record)
            summary = summarize(records, cases, expected_presentations=len(presentations))
            completed = len(records) == len(cases) * len(presentations)
            has_failure = any(
                summary[key] for key in ("semantic_findings", "context_sensitive_cases", "request_changed_cases")
            )
            compared = all(row["code"] == "STABLE_OBSERVED" for row in summary["comparisons"])
            code = (
                "AUDIT_FINDINGS"
                if has_failure
                else "AUDIT_RECORDED"
                if completed and compared
                else "AUDIT_INCOMPLETE"
                if completed
                else "RUNNING"
            )
            yield {
                "format": REPORT_FORMAT,
                "code": code,
                "execution_complete": completed,
                "fixture_sha256": digest(fixture),
                "database_writes": 0,
                "rule_promotions": 0,
                "semantic_gold": "CALLER_LABELS_NOT_INDEPENDENTLY_CERTIFIED_BY_RUNNER",
                "comparison_scope": "IDENTICAL_QUESTION_DIFFERENT_PRESENTATION; NOT_CORRECTNESS_FROM_AGREEMENT",
                "scaffold_mode": "FULL_BASIS_PROJECTION_WITH_SUPPLIED_EVIDENCE",
                "archived_request_scope": "PINNED_SERIALIZATION_AND_WIRE_VALIDITY_NOT_FRESH_CORPUS_REPLAY",
                "fixture_known_authority": "SUPPLIED_FIXTURE_NOT_NATIVE_DERIVED_OR_INDEPENDENT_GOLD",
                "max_cell_questions": budget,
                "cell_questions": questions,
                "transport_invocations": invocations,
                "presentations": [item[0] for item in presentations],
                "expected_records": len(cases) * len(presentations),
                "completed_records": len(records),
                **summary,
                "records": copy.deepcopy(records),
            }


def validate_report_path(report: Path, cases: Path, fixture_sha256: str) -> Path:
    """Only this audit's JSON checkpoints may be replaced; never its input."""
    if report.suffix != ".json":
        raise ValueError("CONTRAST_REPORT_JSON_REQUIRED")
    if report.is_symlink():
        raise ValueError("CONTRAST_REPORT_SYMLINK_REFUSED")
    target = report.resolve()
    if target == cases.resolve() or (report.exists() and cases.exists() and report.samefile(cases)):
        raise ValueError("CONTRAST_REPORT_INPUT_COLLISION")
    if not target.parent.is_dir():
        raise ValueError("CONTRAST_REPORT_DIRECTORY_REQUIRED")
    if target.exists():
        if not target.is_file():
            raise ValueError("CONTRAST_REPORT_NOT_FILE")
        try:
            prior = read_json(target)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("CONTRAST_REPORT_NOT_OWN_CHECKPOINT") from exc
        if (
            type(prior) is not dict
            or prior.get("format") != REPORT_FORMAT
            or prior.get("fixture_sha256") != fixture_sha256
            or prior.get("database_writes") != 0
            or prior.get("rule_promotions") != 0
        ):
            raise ValueError("CONTRAST_REPORT_NOT_OWN_CHECKPOINT")
    return target


def write_checkpoint(report: Path, cases: Path, value: dict) -> None:
    """Create an exclusive private temporary file, then atomically replace."""
    target = validate_report_path(report, cases, value["fixture_sha256"])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-base-url", default="http://localhost:11434")
    parser.add_argument("--context-tokens", type=int, default=65536)
    parser.add_argument("--output-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--include-singleton-batch", action="store_true")
    parser.add_argument("--max-cell-questions", type=int, required=True)
    args = parser.parse_args()
    fixture = read_json(args.cases)
    validate_cases(fixture)
    report_path = validate_report_path(args.report, args.cases, digest(fixture))
    if args.max_cell_questions < 0 or args.batch_size < 2:
        parser.error("nonnegative question budget and batch size >= 2 required")
    single = OllamaTransport(
        args.model,
        base_url=args.model_base_url,
        context_tokens=args.context_tokens,
        output_tokens=args.output_tokens,
        timeout=args.timeout,
        thinking=args.thinking,
    )
    model_pin = single.pin()
    batched = OllamaBatchTransport(single, max_items=args.batch_size)
    for report in contrast_reports(
        fixture,
        single,
        batched,
        budget=args.max_cell_questions,
        batch_size=args.batch_size,
        include_singleton_batch=args.include_singleton_batch,
    ):
        report["model_pin"] = model_pin
        report["generation"] = {
            "context_tokens": single.context_tokens,
            "output_tokens": single.output_tokens,
            "thinking": single.thinking,
            "timeout": single.timeout,
        }
        write_checkpoint(report_path, args.cases, report)
        last = report["records"][-1]
        print(
            f"{report['completed_records']}/{report['expected_records']} {last['presentation']} {last['case_id']} {last['assessment']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
