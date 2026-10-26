"""Evaluation-only diagnosis and trivial-selector challenges.

Gold never supplies construction facts, task nominations, legal options or a
runtime admission verdict. A legal unresolved choice may remain a model task;
this evaluator imposes no source-determinism requirement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from gse.lexicon_builder.artifact import read_sparse
from gse.lexicon_builder.core import CANONICAL_COORDINATES, legal_domain
from gse.lexicon_builder.surprise import comparison_status

RULE_FOR_CLASS = {"adjective_fear": "EMOTION_FEAR_ADJ", "noun_fear": "EMOTION_FEAR_NOUN"}
STATES = ("+1", "-1", "0", "empty")
BASELINES = ("ALWAYS_YES", "ALWAYS_SILENT", "CLASS_MAJORITY")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_states(reference: dict) -> dict[str, str]:
    """Preserve the reference's explicit accounting; missing is not silent."""
    result = {}
    for coordinate, value in reference["written_coordinates"].items():
        if coordinate not in CANONICAL_COORDINATES or type(value) is not int or value not in {-1, 0, 1}:
            raise ValueError("INVALID_REFERENCE_STATE")
        result[coordinate] = "+1" if value == 1 else str(value)
    for coordinate in reference.get("open_coordinates_silent_in_the_explication", []):
        if coordinate not in CANONICAL_COORDINATES or coordinate in result:
            raise ValueError("CONFLICTING_REFERENCE_ACCOUNT")
        result[coordinate] = "empty"
    return result


def exception_status(exception: dict, applications: list[dict]) -> str:
    """Check a supplied review record, never infer an exception from gold."""
    if not isinstance(exception, dict):
        return "MALFORMED_EXCEPTION_REVIEW"
    if exception.get("review_status") != "REVIEWED" or exception.get("evidence_kind") != "SOURCE_RECORD":
        return "UNREVIEWED_OR_DERIVED_EXCEPTION"
    if exception.get("independent") is not True or any(
        not isinstance(exception.get(k), str) or not exception[k] for k in ("source_record_id", "reason")
    ):
        return "UNWARRANTED_EXCEPTION"
    if exception["source_record_id"].startswith(("MODEL:", "FILL:", "BUILDER:")):
        return "UNREVIEWED_OR_DERIVED_EXCEPTION"
    matched = [
        a
        for a in applications
        if a["rule_id"] == exception.get("rule_id") and a["application_id"] == exception.get("application_id")
    ]
    if not matched:
        return "UNMATCHED_EXCEPTION_APPLICATION"
    if any(a["tier"] != "CONDITIONAL" for a in matched):
        return "FOUNDATIONAL_EXCEPTION_REFUSED"
    return "INDEPENDENT_EXCEPTION_REVIEW_RECORDED"


def diagnosis_disposition(
    code: str, expected: str | None, domain: list[str], qualification: str | None
) -> tuple[str | None, str]:
    if code in {"AGREES", "NO_REFERENCE_STATE"}:
        return None, code
    if qualification:
        return "OPEN", "SOURCE_OR_PROJECTION_QUALIFICATION"
    if code == "NO_ALIGNED_READING":
        return "RULE_FIX_PROPOSAL", "MISSING_FAMILY_PROJECTION_OR_TYPED_ALIGNMENT"
    if code == "SOURCE_CONFLICT":
        return "RULE_FIX_PROPOSAL", "CONFLICTING_APPLICATIONS_REQUIRE_REVIEW"
    if code == "ADDITION_CHALLENGE" or expected == "empty":
        return "OPEN", "REFERENCE_OMISSION_DOES_NOT_PROVE_SILENCE"
    if expected in domain:
        return "OPEN", "LEGAL_BOUNDED_RESIDUAL; MODEL_SELECTION_REMAINS_PERMITTED"
    return "RULE_FIX_PROPOSAL", "REFERENCE_STATE_EXCLUDED; REVIEW_SHARED_GUARD_OR_PROJECTION"


def diagnose_symbolic(records: list[dict], references: dict, review: dict | None = None) -> dict:
    """Account for every reference and coordinate, including missing projections."""
    if any(r["provenance"]["model_requests"] for r in records):
        raise ValueError("SYMBOLIC_INPUT_HAS_MODEL_REQUESTS")
    review = review or {}
    qualifications = {(r["word"], r["coordinate"]): r["code"] for r in review.get("qualifications", [])}
    exceptions = {(r["reading_id"], r["coordinate"]): r for r in review.get("exceptions", [])}
    by_word = defaultdict(list)
    for record in records:
        by_word[record["word"]].append(record)
    ledger, word_results = [], {}
    for word, reference in references.items():
        expected = reference_states(reference)
        aligned = [
            r
            for r in by_word[word]
            if r.get("rule_id") == RULE_FOR_CLASS.get(reference["class"]) and r.get("rule_id") is not None
        ]
        word_rows = []
        available_sources = sorted({s for r in by_word[word] for s in r["provenance"]["source_record_ids"]})
        for record in aligned or [None]:
            for coordinate in CANONICAL_COORDINATES:
                value = expected.get(coordinate)
                cell: dict = record["cells"][coordinate] if record else {"state": "unresolved", "domain": []}
                code = (
                    "SOURCE_CONFLICT"
                    if record and record.get("code") == "SOURCE_CONFLICT"
                    else "NO_REFERENCE_STATE"
                    if value is None
                    else comparison_status(value, cell["state"])
                    if record
                    else "NO_ALIGNED_READING"
                )
                qualification = qualifications.get((word, coordinate))
                source_check = reference.get("fixed_cells_check", {}).get(coordinate)
                if source_check in {
                    "NOT_IN_EXPLICATION_SUSPECTED_MISPRINT",
                    "WRITTEN_BY_DEGREE_LAW_NOT_IN_EXPLICATION",
                    "SOURCE_CONFLICTS_WITH_ITSELF",
                }:
                    qualification = source_check
                applications = (
                    [a for a in record["provenance"].get("rule_applications", []) if coordinate in a["coordinates"]]
                    if record
                    else []
                )
                trace = (
                    [t for t in record["provenance"]["trace"] if t.get("coordinate") == coordinate] if record else []
                )
                disposition, reason = diagnosis_disposition(code, value, cell["domain"], qualification)
                exception = exceptions.get((record["reading_id"], coordinate)) if record else None
                exception_review = (
                    exception_status(exception, applications)
                    if exception is not None
                    else "NO_INDEPENDENT_EXCEPTION_REVIEW"
                )
                if disposition is not None and exception_review == "INDEPENDENT_EXCEPTION_REVIEW_RECORDED":
                    disposition, reason = "INDEPENDENTLY_WARRANTED_EXCEPTION", exception_review
                row = {
                    "word": word,
                    "class": reference["class"],
                    "source": reference["source"],
                    "reading_id": record["reading_id"] if record else None,
                    "coordinate": coordinate,
                    "expected": value,
                    "actual": cell["state"],
                    "domain": cell["domain"],
                    "comparison": code,
                    "disposition": disposition,
                    "reason": reason,
                    "qualification": qualification,
                    "responsible_source_rule": record.get("rule_id") if record else None,
                    "available_reading_ids": [r["reading_id"] for r in by_word[word]],
                    "source_record_ids": record["provenance"]["source_record_ids"] if record else available_sources,
                    "coordinate_applications": applications,
                    "coordinate_reduction_trace": trace,
                    "trace_status": "RECORDED_REDUCTIONS; NOT_PROOF_THAT_EVERY_APPLICABLE_RULE_FORCES_THE_VALUE",
                    "exception_review": exception_review,
                }
                word_rows.append(row)
        ledger.extend(word_rows)
        word_results[word] = {
            "class": reference["class"],
            "source": reference["source"],
            "aligned_readings": len(aligned),
            "outcomes": dict(Counter(r["comparison"] for r in word_rows)),
            "dispositions": dict(Counter(r["disposition"] for r in word_rows if r["disposition"])),
        }
    groups = defaultdict(list)
    for row in ledger:
        if row["disposition"] is not None:
            identity = (
                row["responsible_source_rule"] or "MISSING_PROJECTION:" + row["class"],
                row["disposition"],
                row["reason"],
            )
            groups[identity].append(row)
    return {
        "schema": "GSE_SYMBOLIC_DISAGREEMENT_LEDGER_V1",
        "scope": "DEVELOPMENT_REFERENCE_DIAGNOSIS; NOT_HELD_OUT_ACCURACY",
        "code": "SYMBOLIC_DIAGNOSIS_RECORDED",
        "construction_effect": "NONE; REVIEW_PROPOSALS_ONLY",
        "reference_count": len(references),
        "words": word_results,
        "ledger": ledger,
        "outcomes": dict(Counter(r["comparison"] for r in ledger)),
        "dispositions": dict(Counter(r["disposition"] for r in ledger if r["disposition"])),
        "shared_review_groups": [
            {
                "source_rule_or_gap": identity[0],
                "disposition": identity[1],
                "reason": identity[2],
                "coordinates": sorted({r["coordinate"] for r in rows}),
                "words": sorted({r["word"] for r in rows}),
                "reading_ids": sorted({r["reading_id"] for r in rows if r["reading_id"]}),
                "cell_count": len(rows),
            }
            for identity, rows in sorted(groups.items())
        ],
    }


def task_status(task: object) -> str:
    if not isinstance(task, dict) or any(
        not isinstance(task.get(k), str) or not task[k] for k in ("id", "family", "coordinate")
    ):
        return "MALFORMED_EVALUATION_TASK"
    if task["coordinate"] not in CANONICAL_COORDINATES:
        return "UNKNOWN_EVALUATION_COORDINATE"
    options = task.get("options")
    if (
        not isinstance(options, list)
        or not options
        or any(not isinstance(v, str) or v not in STATES for v in options)
        or len(set(options)) != len(options)
    ):
        return "INVALID_EVALUATION_OPTIONS"
    if not set(options) <= {state.value for state in legal_domain(task["coordinate"])}:
        return "ILLEGAL_COORDINATE_OPTIONS"
    if (
        any(not isinstance(task.get(k), str) for k in ("expected", "actual"))
        or task["expected"] not in STATES
        or task["actual"] not in {*STATES, "ABSTAIN"}
    ):
        return "INVALID_EVALUATION_STATE"
    return "VALID_EVALUATION_TASK"


def task_group(task: dict) -> tuple:
    return task["family"], task["coordinate"], tuple(sorted(task["options"]))


def majority_choices(tasks: list[dict]) -> dict[tuple, str]:
    counts = defaultdict(Counter)
    for task in tasks:
        counts[task_group(task)][task["expected"]] += 1
    return {key: max(key[2], key=lambda state: (values[state], -STATES.index(state))) for key, values in counts.items()}


def baseline_choice(strategy: str, task: dict, majority: dict[tuple, str]) -> str:
    if strategy == "ALWAYS_YES":
        return next((state for state in ("+1", "-1") if state in task["options"]), "ABSTAIN")
    if strategy == "ALWAYS_SILENT":
        return "empty" if "empty" in task["options"] else "ABSTAIN"
    if strategy == "CLASS_MAJORITY":
        return majority[task_group(task)]
    raise ValueError("UNKNOWN_EVALUATION_BASELINE")


def selection_outcome(actual: str, expected: str, options: list[str]) -> str:
    if actual == "ABSTAIN":
        return "ABSTAINED"
    if actual not in options:
        return "INVALID_SELECTION"
    return "IDENTIFIED" if actual == expected else "WRONG"


def compare_baselines(tasks: list[dict]) -> dict:
    """A strict development challenge, not lexical admission or completeness."""
    for task in tasks:
        status = task_status(task)
        if status != "VALID_EVALUATION_TASK":
            raise ValueError(status)
    if len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("DUPLICATE_EVALUATION_TASK")
    majority = majority_choices(tasks)
    results: dict[str, dict] = {}
    for selector in ("MODEL", *BASELINES):
        rows: list[dict] = [
            {
                "task_id": task["id"],
                "family": task["family"],
                "coordinate": task["coordinate"],
                "expected": task["expected"],
                "actual": task["actual"] if selector == "MODEL" else baseline_choice(selector, task, majority),
                "options": task["options"],
                "options_basis": task.get("options_basis", "SUPPLIED_EVALUATION_TASK"),
            }
            for task in tasks
        ]
        for row in rows:
            row["code"] = selection_outcome(row["actual"], row["expected"], row["options"])
        results[selector] = {
            "counts": dict(Counter(r["code"] for r in rows)),
            "by_family": {
                family: dict(Counter(r["code"] for r in rows if r["family"] == family))
                for family in sorted({r["family"] for r in rows})
            },
            "ledger": rows,
        }
    model_identified = results["MODEL"]["counts"].get("IDENTIFIED", 0)
    failed = [name for name in BASELINES if model_identified <= results[name]["counts"].get("IDENTIFIED", 0)]
    typed_groups = []
    for family, coordinate, options in sorted({task_group(task) for task in tasks}):
        group_ids = {task["id"] for task in tasks if task_group(task) == (family, coordinate, options)}
        counts = {
            selector: dict(Counter(row["code"] for row in result["ledger"] if row["task_id"] in group_ids))
            for selector, result in results.items()
        }
        group_failed = [
            name for name in BASELINES if counts["MODEL"].get("IDENTIFIED", 0) <= counts[name].get("IDENTIFIED", 0)
        ]
        typed_groups.append(
            {
                "family": family,
                "coordinate": coordinate,
                "options": list(options),
                "task_count": len(group_ids),
                "selectors": counts,
                "failed_against": group_failed,
                "code": "TYPED_GROUP_BASELINE_NOT_EXCEEDED" if group_failed else "TYPED_GROUP_CHALLENGE_PASSED_ONLY",
                "ceiling_baselines": [
                    name for name in BASELINES if counts[name].get("IDENTIFIED", 0) == len(group_ids)
                ],
            }
        )
    group_failure = any(group["failed_against"] for group in typed_groups)
    return {
        "schema": "GSE_TAIL_TRIVIAL_BASELINE_CHALLENGE_V1",
        "scope": "EVALUATION_ONLY_DEVELOPMENT_COHORT",
        "code": "NO_EVALUABLE_TASKS"
        if not tasks
        else "BASELINE_NOT_EXCEEDED"
        if failed or group_failure
        else "BASELINE_CHALLENGE_PASSED_ONLY",
        "task_count": len(tasks),
        "failed_against": failed,
        "typed_groups": typed_groups,
        "failed_typed_group_count": sum(bool(group["failed_against"]) for group in typed_groups),
        "options_basis_counts": dict(Counter(task.get("options_basis", "SUPPLIED_EVALUATION_TASK") for task in tasks)),
        "selectors": results,
        "policy": "Model IDENTIFIED must strictly exceed every trivial selector overall AND in every rule/coordinate/legal-options group. All other outcomes remain separate.",
        "ceiling_interpretation": "A baseline at the group's reference ceiling makes strict improvement impossible on that development cohort; a tie is not evidence against bounded models in general.",
        "majority_scope": "FITTED_TO_THE_SAME_DEVELOPMENT_REFERENCES; OPTIMISTIC_IN_SAMPLE_CONTROL",
        "construction_effect": "NONE; NO_RUNTIME_ADMISSION_DEPENDENCY",
    }


def artifact_tasks(records: list[dict], references: dict) -> list[dict]:
    """Extract attempted decisions from artifacts; never nominate builder work."""
    tasks = []
    for record in records:
        reference = references.get(record["word"])
        if reference is None or RULE_FOR_CLASS.get(reference["class"]) != record.get("rule_id"):
            continue
        expected = reference_states(reference)
        for decision in record["decisions"]:
            coordinate = decision.get("coordinate")
            if (
                coordinate not in CANONICAL_COORDINATES
                or coordinate not in expected
                or decision["code"] not in {"SELECTED", "ABSTAINED"}
            ):
                continue
            if "offered_options" in decision or "options" in decision:
                offered = decision.get("offered_options", decision.get("options"))
                offered = offered.get(coordinate, []) if isinstance(offered, dict) else offered
                options = [state for state in offered if state != "ABSTAIN"]
                options_basis = "RECORDED_OFFERED_OPTIONS"
            elif coordinate in decision.get("before", {}):
                options = decision["before"][coordinate]
                options_basis = "RECORDED_PRE_DECISION_DOMAIN"
            else:
                options = record["cells"][coordinate]["domain"]
                options_basis = "FINAL_DOMAIN_FALLBACK; LATER_PROPAGATION_MAY_HAVE_NARROWED_OFFER"
            tasks.append(
                {
                    "id": decision["task_id"] or record["reading_id"] + ":" + coordinate,
                    "family": record["rule_id"],
                    "coordinate": coordinate,
                    "options": options,
                    "options_basis": options_basis,
                    "expected": expected[coordinate],
                    "actual": decision["selected"][coordinate] if decision["code"] == "SELECTED" else "ABSTAIN",
                }
            )
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["diagnose-symbolic", "compare-baselines"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    records = list(read_sparse(args.input))
    references = json.loads(args.gold.read_text())["gold_from_published_explications"]
    review = json.loads(args.review.read_text()) if args.review else None
    report = (
        diagnose_symbolic(records, references, review)
        if args.command == "diagnose-symbolic"
        else compare_baselines(artifact_tasks(records, references))
    )
    report["input_sha256"] = file_digest(args.input)
    report["reference_sha256"] = file_digest(args.gold)
    report["review_sha256"] = file_digest(args.review) if args.review else None
    report["evaluator_implementation_sha256"] = {
        name: file_digest(Path(__file__).with_name(name))
        for name in ("evaluation.py", "artifact.py", "core.py", "surprise.py")
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("code", "scope")}))
    return 1 if report["code"] in {"BASELINE_NOT_EXCEEDED", "NO_EVALUABLE_TASKS"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
