"""Evaluation diagnoses evidence without becoming a construction dependency."""

import ast
from pathlib import Path

import pytest

from gse.lexicon_builder.core import CANONICAL_COORDINATES, legal_domain
from gse.lexicon_builder.evaluation import (
    artifact_tasks,
    baseline_choice,
    compare_baselines,
    diagnose_symbolic,
    diagnosis_disposition,
    exception_status,
    task_status,
)


def reference(word="afraid", family="adjective_fear"):
    return {word: {"class": family, "source": "fixture primary reference", "written_coordinates": {"FEEL": 1}}}


def reading(word="afraid", rule="EMOTION_FEAR_ADJ"):
    return {
        "word": word,
        "reading_id": word + ":fixture",
        "rule_id": rule,
        "cells": {
            c: {"state": "unresolved", "domain": sorted(v.value for v in legal_domain(c))}
            for c in CANONICAL_COORDINATES
        },
        "decisions": [],
        "provenance": {
            "source_record_ids": ["fixture:source"],
            "model_requests": [],
            "rule_applications": [],
            "trace": [],
        },
    }


def task(identifier="one", expected="+1", actual="+1", coordinate="FEEL", options=None):
    return {
        "id": identifier,
        "family": "EMOTION_FEAR_ADJ",
        "coordinate": coordinate,
        "options": options or ["+1", "0", "empty"],
        "expected": expected,
        "actual": actual,
    }


def test_symbolic_ledger_accounts_for_every_coordinate_and_missing_family():
    rows = diagnose_symbolic([reading()], reference())
    assert len(rows["ledger"]) == 58
    feel = next(row for row in rows["ledger"] if row["coordinate"] == "FEEL")
    assert feel["disposition"] == "OPEN"
    assert feel["reason"] == "LEGAL_BOUNDED_RESIDUAL; MODEL_SELECTION_REMAINS_PERMITTED"
    assert feel["responsible_source_rule"] == "EMOTION_FEAR_ADJ"
    missing = diagnose_symbolic([reading("sad", None)], reference("sad", "adjective_other"))
    assert len(missing["ledger"]) == 58
    feel = next(row for row in missing["ledger"] if row["coordinate"] == "FEEL")
    assert feel["comparison"] == "NO_ALIGNED_READING"
    assert feel["disposition"] == "RULE_FIX_PROPOSAL"
    assert feel["responsible_source_rule"] is None
    assert feel["available_reading_ids"] == ["sad:fixture"]


def test_excluded_reference_component_retains_responsible_application():
    record = reading()
    record["cells"]["FEEL"] = {"state": "empty", "domain": ["empty"]}
    record["provenance"]["trace"] = [{"rule": "WRONG_BOUNDARY", "coordinate": "FEEL", "remaining": ["empty"]}]
    record["provenance"]["rule_applications"] = [
        {"rule_id": "WRONG_BOUNDARY", "application_id": "app", "tier": "CONDITIONAL", "coordinates": ["FEEL"]}
    ]
    report = diagnose_symbolic([record], reference())
    feel = next(row for row in report["ledger"] if row["coordinate"] == "FEEL")
    assert feel["comparison"] == "FALSE_OMISSION"
    assert feel["disposition"] == "RULE_FIX_PROPOSAL"
    assert feel["coordinate_applications"][0]["rule_id"] == "WRONG_BOUNDARY"
    assert feel["source_record_ids"] == ["fixture:source"]
    assert diagnosis_disposition("ADDITION_CHALLENGE", "empty", ["+1"], None) == (
        "OPEN",
        "REFERENCE_OMISSION_DOES_NOT_PROVE_SILENCE",
    )


def test_symbolic_diagnosis_refuses_model_contaminated_input():
    record = reading()
    record["provenance"]["model_requests"] = ["model:request"]
    with pytest.raises(ValueError, match="SYMBOLIC_INPUT_HAS_MODEL_REQUESTS"):
        diagnose_symbolic([record], reference())


def test_exception_requires_review_independence_and_conditional_application():
    application = {"rule_id": "rule", "application_id": "app", "tier": "CONDITIONAL"}
    exception = {
        "rule_id": "rule",
        "application_id": "app",
        "review_status": "REVIEWED",
        "evidence_kind": "SOURCE_RECORD",
        "independent": True,
        "source_record_id": "primary:p1",
        "reason": "reviewed scoped counterexample",
    }
    assert exception_status(exception, [application]) == "INDEPENDENT_EXCEPTION_REVIEW_RECORDED"
    assert (
        exception_status({**exception, "source_record_id": "MODEL:answer"}, [application])
        == "UNREVIEWED_OR_DERIVED_EXCEPTION"
    )
    assert exception_status(exception, [{**application, "tier": "FOUNDATIONAL"}]) == "FOUNDATIONAL_EXCEPTION_REFUSED"
    assert exception_status({**exception, "independent": False}, [application]) == "UNWARRANTED_EXCEPTION"


def test_baselines_fail_when_model_does_not_exceed_and_keep_outcomes_separate():
    tasks = [
        task("first"),
        task("second", expected="empty", actual="ABSTAIN"),
        task("third", expected="empty", actual="+1"),
    ]
    report = compare_baselines(tasks)
    assert report["code"] == "BASELINE_NOT_EXCEEDED"
    assert report["selectors"]["MODEL"]["counts"] == {"IDENTIFIED": 1, "ABSTAINED": 1, "WRONG": 1}
    assert report["selectors"]["ALWAYS_SILENT"]["counts"] == {"WRONG": 1, "IDENTIFIED": 2}
    assert "CLASS_MAJORITY" in report["failed_against"]
    assert report["construction_effect"] == "NONE; NO_RUNTIME_ADMISSION_DEPENDENCY"
    assert compare_baselines([])["code"] == "NO_EVALUABLE_TASKS"


def test_zero_and_negative_pole_remain_legal_baseline_states():
    zero = task(expected="0", actual="0")
    assert task_status(zero) == "VALID_EVALUATION_TASK"
    assert compare_baselines([zero])["selectors"]["MODEL"]["counts"] == {"IDENTIFIED": 1}
    now = task(coordinate="THEN", expected="-1", actual="-1", options=["-1", "0", "empty"])
    assert baseline_choice("ALWAYS_YES", now, {}) == "-1"
    assert baseline_choice("ALWAYS_SILENT", task(options=["+1", "0"]), {}) == "ABSTAIN"


def test_a_bounded_selector_can_exceed_all_trivial_baselines():
    report = compare_baselines([task("present"), task("silent", expected="empty", actual="empty")])
    assert report["code"] == "BASELINE_CHALLENGE_PASSED_ONLY"
    assert report["selectors"]["MODEL"]["counts"] == {"IDENTIFIED": 2}
    assert report["failed_against"] == []


def test_invalid_and_duplicate_tasks_receive_named_refusals():
    assert task_status({**task(), "actual": []}) == "INVALID_EVALUATION_STATE"
    assert task_status({**task(), "options": {}}) == "INVALID_EVALUATION_OPTIONS"
    assert task_status(task(coordinate="NONEXISTENT")) == "UNKNOWN_EVALUATION_COORDINATE"
    assert task_status(task(options=["-1", "empty"])) == "ILLEGAL_COORDINATE_OPTIONS"
    with pytest.raises(ValueError, match="DUPLICATE_EVALUATION_TASK"):
        compare_baselines([task(), task()])


def test_artifact_task_extraction_keeps_offered_zero_and_abstention():
    record = reading()
    record["decisions"] = [{"task_id": "choice", "coordinate": "FEEL", "code": "ABSTAINED"}]
    tasks = artifact_tasks([record], reference())
    assert len(tasks) == 1
    assert "0" in tasks[0]["options"]
    assert tasks[0]["actual"] == "ABSTAIN"
    assert tasks[0]["options_basis"].startswith("FINAL_DOMAIN_FALLBACK")
    assert record["cells"]["FEEL"]["state"] == "unresolved"


def test_recorded_offered_options_survive_later_narrowing_and_bank_decisions_are_skipped():
    record = reading()
    record["cells"]["FEEL"] = {"state": "+1", "domain": ["+1"]}
    record["decisions"] = [
        {"code": "ABSTAINED", "bank": "FEELING"},
        {"code": "ABSTAINED", "coordinate": "UNKNOWN"},
        {
            "task_id": "original-offer",
            "coordinate": "FEEL",
            "code": "ABSTAINED",
            "offered_options": ["+1", "0", "empty", "ABSTAIN"],
            "before": {"FEEL": ["+1"]},
        },
    ]
    tasks = artifact_tasks([record], reference())
    assert len(tasks) == 1
    assert tasks[0]["options"] == ["+1", "0", "empty"]
    assert tasks[0]["options_basis"] == "RECORDED_OFFERED_OPTIONS"


def test_source_conflict_quarantines_even_an_individually_matching_cell():
    record = reading()
    record["code"] = "SOURCE_CONFLICT"
    record["cells"]["FEEL"] = {"state": "+1", "domain": ["+1"]}
    report = diagnose_symbolic([record], reference())
    assert report["outcomes"] == {"SOURCE_CONFLICT": 58}
    feel = next(row for row in report["ledger"] if row["coordinate"] == "FEEL")
    assert feel["comparison"] == "SOURCE_CONFLICT"
    assert feel["disposition"] == "RULE_FIX_PROPOSAL"


def test_overall_win_cannot_hide_a_failing_typed_group():
    tasks = [
        task(str(index), expected="+1" if index % 2 else "empty", actual="+1" if index % 2 else "empty")
        for index in range(6)
    ]
    tasks.append(task("bad-do", coordinate="DO", actual="empty"))
    report = compare_baselines(tasks)
    assert report["failed_against"] == []
    assert report["code"] == "BASELINE_NOT_EXCEEDED"
    assert report["failed_typed_group_count"] == 1
    failed = next(group for group in report["typed_groups"] if group["coordinate"] == "DO")
    assert failed["code"] == "TYPED_GROUP_BASELINE_NOT_EXCEEDED"
    assert failed["ceiling_baselines"] == ["ALWAYS_YES", "CLASS_MAJORITY"]


def test_construction_modules_do_not_import_gold_evaluator():
    directory = Path(__file__).resolve().parents[1] / "gse/lexicon_builder"
    for filename in ("build.py", "tail.py", "reading.py", "families.py", "native_constraints.py"):
        tree = ast.parse((directory / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "gse.lexicon_builder.evaluation"
            elif isinstance(node, ast.Import):
                assert all(alias.name != "gse.lexicon_builder.evaluation" for alias in node.names)
