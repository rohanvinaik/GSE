"""Contrasts separate typed transport behavior, semantic labels and stability."""

import copy
import json

import pytest

from scripts import audit_lexicon_contrasts as audit


def fixture():
    cases = []
    for index, value in enumerate((1, -1, 0, None)):
        entry = f"audit:{index}"
        cases.append(
            {
                "id": entry,
                "class": f"SIGN_{value}",
                "authority": {
                    "kind": "TEST_ONLY",
                    "source": __file__,
                    "rationale": "Transport test, not semantic gold.",
                },
                "expectation": {"kind": "EXACT", "value": value},
                "input": {
                    "entry_id": entry,
                    "bank": "WANT",
                    "definition": {"entry_id": entry, "lemma": "test", "pos": "verb", "definition": "test definition"},
                    "known": {},
                    "observations": [],
                },
            }
        )
    return {"format": audit.INPUT_FORMAT, "cases": cases}


class Transport:
    identity = "test:pinned"

    def __init__(self, answers=None):
        self.answers = answers or {f"audit:{i}": value for i, value in enumerate((1, -1, 0, None))}
        self.calls = []

    def prepare(self, items):
        assert all(
            "expectation" not in payload and "expected" not in payload and "authority" not in payload
            for payload, _ in items
        )

    def __call__(self, payload, schema):
        self.calls.append([payload["entry_id"]])
        return json.dumps({payload["bank"]: self.answers[payload["entry_id"]]})

    def callable_batch(self, items):
        self.calls.append([payload["entry_id"] for payload, _ in items])
        return tuple(json.dumps({payload["bank"]: self.answers[payload["entry_id"]]}) for payload, _ in items)


def test_identical_requests_comparison_retains_actual_companions_and_independent_scores():
    single, batch = Transport(), Transport()
    report = list(audit.contrast_reports(fixture(), single, batch, budget=16, batch_size=2))[-1]
    assert report["cell_questions"] == 16
    assert report["transport_invocations"] == 10
    assert report["database_writes"] == report["rule_promotions"] == 0
    assert report["code"] == "AUDIT_RECORDED"
    assert all(row["code"] == "STABLE_OBSERVED" for row in report["comparisons"])
    assert all(len(row["request_ids"]) == 1 for row in report["comparisons"])
    assert report["per_class"]["SIGN_None"] == {"EXPECTED_ABSTENTION": 4}
    comparisons = report["comparisons"][0]["conditions"]
    assert comparisons[0]["invocation_case_ids"] == ["audit:0"]
    assert comparisons[1]["invocation_case_ids"] == ["audit:0", "audit:1"]
    assert comparisons[2]["invocation_case_ids"] == ["audit:1", "audit:0"]
    assert comparisons[3]["invocation_case_ids"] == ["audit:3", "audit:0"]


def test_optional_singleton_batch_is_distinguished_from_plain_single_transport():
    single, batch = Transport(), Transport()
    report = list(audit.contrast_reports(fixture(), single, batch, budget=20, include_singleton_batch=True))[-1]
    assert report["cell_questions"] == report["completed_records"] == 20
    assert report["presentations"] == ["SINGLE", "BATCH_SINGLETON", "BATCH_FORWARD", "BATCH_REVERSED", "BATCH_ROTATED"]
    assert all(row["code"] == "STABLE_OBSERVED" for row in report["comparisons"])
    assert len(single.calls) == 4
    assert len(batch.calls) == 7


def test_batch_disagreement_is_a_finding_even_when_both_answers_pass_schema():
    single, batch = Transport(), Transport({f"audit:{i}": 0 for i in range(4)})
    report = list(audit.contrast_reports(fixture(), single, batch, budget=16, batch_size=4))[-1]
    assert report["code"] == "AUDIT_FINDINGS"
    assert report["context_sensitive_cases"] == 3
    assert report["semantic_findings"] == 9
    assert report["per_class"]["SIGN_0"] == {"IDENTIFIED": 4}


def test_forbidden_positive_is_not_an_expected_zero_or_semantic_approval():
    cases = fixture()
    cases["cases"][0]["expectation"] = {"kind": "FORBIDDEN_VALUES", "values": [1]}
    single = Transport({f"audit:{i}": 0 for i in range(4)})
    batch = Transport()
    report = list(audit.contrast_reports(cases, single, batch, budget=16))[-1]
    rows = [row for row in report["records"] if row["case_id"] == "audit:0"]
    assert [row["assessment"] for row in rows] == [
        "NOT_ADJUDICATED",
        "SCOPE_VIOLATION",
        "SCOPE_VIOLATION",
        "SCOPE_VIOLATION",
    ]
    assert [row["code"] for row in rows] == [row["assessment"] for row in rows]
    assert rows[0]["legacy_calibration_label_diagnostic"] == "WRONG"
    assert all("expected" not in row for row in rows)


def test_budget_is_global_and_unasked_cases_have_no_value_or_zero():
    single, batch = Transport(), Transport()
    report = list(audit.contrast_reports(fixture(), single, batch, budget=5))[-1]
    assert report["cell_questions"] == 5
    assert len(single.calls) == 4
    assert len(batch.calls) == 1
    unasked = [row for row in report["records"] if row["code"] == "MODEL_BUDGET_EXHAUSTED"]
    assert len(unasked) == 11
    assert all("value" not in row and not row["model_answer"] for row in unasked)
    assert all(row["code"] == "INCOMPLETE_COMPARISON" for row in report["comparisons"])
    assert report["code"] == "AUDIT_INCOMPLETE"


@pytest.mark.parametrize("bad", [None, {}, {"format": audit.INPUT_FORMAT, "cases": []}])
def test_malformed_fixture_is_rejected_before_any_call(bad):
    with pytest.raises(ValueError, match="INVALID_CONTRAST"):
        list(audit.contrast_reports(bad, Transport(), Transport(), budget=1))


def test_direct_target_leakage_and_boolean_labels_are_rejected():
    cases = fixture()
    cases["cases"][0]["input"]["known"] = {"WANT": 1}
    with pytest.raises(ValueError, match="TARGET_ALREADY_SUPPLIED"):
        audit.validate_cases(cases)
    cases = fixture()
    cases["cases"][0]["expectation"]["value"] = True
    with pytest.raises(ValueError, match="INVALID_CONTRAST_EXPECTATION"):
        audit.validate_cases(cases)


def test_authority_and_unique_case_identity_are_required():
    cases = fixture()
    cases["cases"][0]["authority"] = {}
    with pytest.raises(ValueError, match="INVALID_CONTRAST_AUTHORITY"):
        audit.validate_cases(cases)
    cases = fixture()
    cases["cases"][1]["id"] = cases["cases"][0]["id"]
    with pytest.raises(ValueError, match="DUPLICATE_CONTRAST_CASE"):
        audit.validate_cases(cases)


def test_stable_abstention_does_not_identify_nonzero_labels():
    single = Transport({f"audit:{i}": None for i in range(4)})
    batch = Transport({f"audit:{i}": None for i in range(4)})
    report = list(audit.contrast_reports(fixture(), single, batch, budget=16))[-1]
    assert report["per_class"]["SIGN_1"] == {"ABSTAINED": 4}
    assert report["per_class"]["SIGN_None"] == {"EXPECTED_ABSTENTION": 4}
    assert report["semantic_findings"] == 0


def test_report_snapshots_are_not_mutated_by_later_presentations():
    reports = list(audit.contrast_reports(fixture(), Transport(), Transport(), budget=16))
    first = copy.deepcopy(reports[0])
    assert first["completed_records"] == len(first["records"]) == 1
    assert reports[-1]["completed_records"] == 16
    assert first == reports[0]


def test_archived_question_reuses_exact_hash_and_scaffold_in_every_condition():
    cases = fixture()
    payload = cases["cases"][0]["input"]
    payload["known"] = {"ALIVE": 0}
    request, _ = audit.prepare_case(payload, production_scaffold=True)
    cases["cases"][0]["input"] = request.payload()
    cases["cases"][0]["archived_request_sha256"] = request.request_id
    report = list(audit.contrast_reports(cases, Transport(), Transport(), budget=16))[-1]
    rows = [row for row in report["records"] if row["case_id"] == "audit:0"]
    assert all(row["input"] == request.payload() for row in rows)
    assert all(row["request_id"] == request.request_id for row in rows)
    cases["cases"][0]["input"]["known"]["ALIVE"] = 1
    with pytest.raises(ValueError, match="ARCHIVED_CONTRAST_REQUEST_HASH_MISMATCH"):
        audit.validate_cases(cases)


def test_archived_serialization_cannot_hide_extra_fields():
    cases = fixture()
    request, _ = audit.prepare_case(cases["cases"][0]["input"], production_scaffold=True)
    raw = request.payload()
    raw["unexpected"] = "do not discard me silently"
    cases["cases"][0]["input"] = raw
    cases["cases"][0]["archived_request_sha256"] = audit.digest(raw)
    with pytest.raises(ValueError, match="ARCHIVED_CONTRAST_REQUEST_MISMATCH"):
        audit.validate_cases(cases)


def test_symbolic_label_disagreement_is_recorded_without_model_test_claim():
    cases = fixture()
    cases["cases"][0]["input"]["bank"] = "GOOD"
    cases["cases"][0]["input"]["definition"]["pos"] = "noun"
    report = list(audit.contrast_reports(cases, Transport(), Transport(), budget=16))[-1]
    rows = [row for row in report["records"] if row["case_id"] == "audit:0"]
    assert all(row["assessment"] == "SYMBOLIC_EXPECTATION_MISMATCH" for row in rows)
    assert all(not row["model_answer"] for row in rows)
    assert report["semantic_findings"] == 4


def test_cli_runs_real_entry_point_and_records_transport_pin(tmp_path, monkeypatch):
    single = Transport()
    single.pin = lambda: {"model": "test", "digest": "a" * 64}
    single.context_tokens, single.output_tokens, single.thinking, single.timeout = 65536, 1024, False, 300
    monkeypatch.setattr(audit, "OllamaTransport", lambda *args, **kwargs: single)
    monkeypatch.setattr(audit, "OllamaBatchTransport", lambda *args, **kwargs: Transport())
    cases, report = tmp_path / "cases.json", tmp_path / "report.json"
    cases.write_text(json.dumps(fixture()))
    monkeypatch.setattr(
        "sys.argv",
        ["audit", "--cases", str(cases), "--report", str(report), "--model", "test", "--max-cell-questions", "16"],
    )
    audit.main()
    result = json.loads(report.read_text())
    assert result["model_pin"]["digest"] == "a" * 64
    assert result["execution_complete"] is True
    assert result["cell_questions"] == 16
    assert not report.with_suffix(".json.tmp").exists()


def checkpoint_value():
    return {
        "format": audit.REPORT_FORMAT,
        "fixture_sha256": audit.digest(fixture()),
        "database_writes": 0,
        "rule_promotions": 0,
    }


def test_checkpoint_ignores_predictable_temp_symlink_and_replaces_only_own_report(tmp_path):
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(fixture()))
    report, victim = tmp_path / "report.json", tmp_path / "candidate.db"
    victim.write_bytes(b"unchanged candidate")
    bait = report.with_suffix(".json.tmp")
    bait.symlink_to(victim)
    value = checkpoint_value()
    audit.write_checkpoint(report, cases, value)
    value["completed_records"] = 2
    audit.write_checkpoint(report, cases, value)
    assert victim.read_bytes() == b"unchanged candidate"
    assert bait.is_symlink()
    assert json.loads(report.read_text()) == value
    assert not list(tmp_path.glob(".report.json.*.tmp"))


@pytest.mark.parametrize("destination", ["input", "hardlink", "symlink", "db", "unrelated"])
def test_cli_refuses_input_aliases_database_and_foreign_reports_before_model(tmp_path, monkeypatch, destination):
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(fixture()))
    report = tmp_path / "report.json"
    if destination == "input":
        report = cases
    elif destination == "hardlink":
        report.hardlink_to(cases)
    elif destination == "symlink":
        report.symlink_to(cases)
    elif destination == "db":
        report = tmp_path / "candidate.db"
        report.write_bytes(b"SQLite database")
    else:
        report.write_text('{"unrelated":"do not overwrite"}')
    before = report.read_bytes()

    def no_model(*args, **kwargs):
        raise AssertionError("destination refusal must precede model access")

    monkeypatch.setattr(audit, "OllamaTransport", no_model)
    monkeypatch.setattr(
        "sys.argv",
        ["audit", "--cases", str(cases), "--report", str(report), "--model", "test", "--max-cell-questions", "16"],
    )
    with pytest.raises(ValueError, match="CONTRAST_REPORT"):
        audit.main()
    assert report.read_bytes() == before


def test_checkpoint_failure_cleans_only_exclusive_temp_and_preserves_previous(tmp_path, monkeypatch):
    cases, report = tmp_path / "cases.json", tmp_path / "report.json"
    cases.write_text(json.dumps(fixture()))
    value = checkpoint_value()
    audit.write_checkpoint(report, cases, value)
    before = report.read_bytes()

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(audit.Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        audit.write_checkpoint(report, cases, {**value, "completed_records": 3})
    assert report.read_bytes() == before
    assert not list(tmp_path.glob(".report.json.*.tmp"))
