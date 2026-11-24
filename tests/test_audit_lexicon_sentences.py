"""Pin the distinct sentence-audit outcomes for absence, zero, and sign."""

import pytest

from scripts.audit_lexicon_sentences import checkpoint_result, compare_reports, load_workload, main, score_domain


@pytest.mark.parametrize(
    "domain,expected,code",
    [
        ([-1, 0, 1], 0, "OPEN"),
        ([0], 0, "CORRECT"),
        ([-1, 0, 1], None, "OPEN_AS_EXPECTED"),
        ([0], None, "UNSUPPORTED_ASSIGNMENT"),
        ([-1, 0], 1, "WRONG"),
        (None, 0, "INVALID_DOMAIN"),
        ([], 1, "INVALID_DOMAIN"),
        ([True], 1, "INVALID_DOMAIN"),
        ([0, 0], 0, "INVALID_DOMAIN"),
    ],
)
def test_score_domain(domain, expected, code):
    assert score_domain(domain, expected) == code


def test_comparison_separates_exact_gain_from_runtime_and_rejects_false_zero():
    def report(domain, outcome):
        return {
            "benchmark_sha256": "benchmark",
            "lexicon_sha256": str(domain),
            "cases": [
                {
                    "id": "blocked",
                    "class": "action",
                    "sense_outcome": "ABSTAINED",
                    "banks": {
                        "DO": {
                            "expected": 1,
                            "domain": domain,
                            "exact_sense": outcome,
                            "runtime": "BLOCKED_BY_SENSE",
                        }
                    },
                }
            ],
        }

    baseline = report([-1, 0, 1], "OPEN")
    gained = compare_reports(baseline, report([1], "CORRECT"))
    assert gained["code"] == "SENTENCE_BENCHMARK_VALIDATED"
    assert gained["by_class"]["action"]["exact_sense_new_correct"] == 1
    assert "runtime_new_correct" not in gained["by_class"]["action"]
    wrong = compare_reports(baseline, report([0], "WRONG"))
    assert wrong["code"] == "SENTENCE_BENCHMARK_REGRESSION"
    assert wrong["failures"][0]["field"] == "exact_sense"


@pytest.fixture
def acceptance_inputs():
    report = {
        "lexicon_sha256": "lexicon",
        "benchmark_sha256": "benchmark",
        "snapshot_pins": {
            "definition_cohort_sha256": "cohort",
            "definitions": 100,
            "representation_sha256": "basis",
            "rule_version": "rules",
        },
        "cases": [
            {
                "id": "test",
                "class": "own-state",
                "sense": "native:test",
                "sense_outcome": "CORRECT",
                "banks": {"BE": {"runtime": "CORRECT", "exact_sense": "CORRECT"}},
            }
        ],
    }
    runtime = {"code": "SPARSE_RUNTIME_VALIDATED", "lexicon_sha256": "lexicon", "records": []}
    workload = {
        "format": "GSE.checkpoint-workload/1",
        "pins": {"lexicon_sha256": "lexicon", "benchmark_sha256": "benchmark", **report["snapshot_pins"]},
        "evaluation": {
            "split": "FINAL_UNEXPOSED",
            "development_senses": ["native:other"],
            "final_senses": ["native:test"],
            "development_families": ["other"],
            "final_families": ["state"],
        },
        "critical_case_ids": ["test"],
        "operations": [{"id": "state-query", "case_ids": ["test"], "required_banks": {"test": ["BE"]}}],
        "token_demand": {
            "common_forms": ["the"],
            "frequency_counts": {"the": 90, "tail": 10},
            "corpus_genres": {"news": {"the": 91, "tail": 9}},
            "denominator_rules": "all tokens",
            "exclusions": [],
            "frequency_source_sha256": "freq",
            "corpus_source_sha256": "corpus",
        },
        "gates": {
            name: {"code": "PASSED", "lexicon_sha256": "lexicon", "receipt_sha256": name}
            for name in ("full_replay", "repository_gate", "two_sided_semantic_audit")
        },
    }
    return report, runtime, workload


def test_checkpoint_consumes_exact_critical_answers_and_separate_token_mass(acceptance_inputs):
    report, runtime, workload = acceptance_inputs
    result = checkpoint_result(report, runtime, workload)
    assert result["code"] == "CHECKPOINT_ACCEPTED_FOR_DECLARED_WORKLOAD"
    assert result["token_mass"]["frequency"] == {"eligible": 100, "in_cohort": 90, "meets_90_percent": True}
    report["cases"][0]["banks"]["BE"]["runtime"] = "OPEN"
    result = checkpoint_result(report, runtime, workload)
    assert result["code"] == "CHECKPOINT_BLOCKED"  # 100% homing cannot excuse one critical missing bank
    assert result["by_class"]["own-state"] == {"PARTIAL": 1}


def test_genre_slices_are_reported_not_individual_ninety_percent_gates(acceptance_inputs):
    report, runtime, workload = acceptance_inputs
    workload["token_demand"]["corpus_genres"] = {
        "news": {"the": 950, "tail": 50},
        "fiction": {"the": 1, "tail": 9},
    }
    result = checkpoint_result(report, runtime, workload)
    assert result["code"] == "CHECKPOINT_ACCEPTED_FOR_DECLARED_WORKLOAD"
    assert result["token_mass"]["independent_corpus"]["meets_90_percent"]
    assert not result["token_mass"]["genres"]["fiction"]["meets_90_percent"]


@pytest.mark.parametrize("outcome", ["ABSTAINED", "UNAVAILABLE", "WRONG", "TOKEN_MISMATCH"])
def test_no_semantic_error_allowance_at_ninety_percent_token_mass(acceptance_inputs, outcome):
    report, runtime, workload = acceptance_inputs
    report["cases"][0]["sense_outcome"] = outcome
    result = checkpoint_result(report, runtime, workload)
    assert result["code"] == "CHECKPOINT_BLOCKED"
    assert any(b["code"] == "CRITICAL_ANSWER_NOT_ESTABLISHED" for b in result["blockers"])


@pytest.mark.parametrize(
    "change,blocker",
    [
        ("genre", "ELIGIBLE_TOKEN_MASS_BELOW_90_PERCENT"),
        ("lineage", "HOLDOUT_LINEAGE_OVERLAP"),
        ("development", "FINAL_HOLDOUT_NOT_UNEXPOSED"),
        ("pins", "WORKLOAD_PINS_MISMATCH"),
        ("runtime", "RUNTIME_RESOURCE_MISMATCH"),
        ("bank", "REQUIRED_BANK_NOT_TESTED"),
        ("gate", "REQUIRED_GATE_NOT_ESTABLISHED"),
    ],
)
def test_checkpoint_refuses_incomplete_or_changed_proofs(acceptance_inputs, change, blocker):
    report, runtime, workload = acceptance_inputs
    if change == "genre":
        workload["token_demand"]["corpus_genres"]["fiction"] = {"the": 1, "tail": 99}
    elif change == "lineage":
        workload["evaluation"]["development_families"] = ["state"]
    elif change == "development":
        workload["evaluation"]["split"] = "DEVELOPMENT"
    elif change == "pins":
        workload["pins"]["definition_cohort_sha256"] = "different"
    elif change == "runtime":
        runtime["lexicon_sha256"] = "different"
    elif change == "bank":
        workload["operations"][0]["required_banks"]["test"] = ["BODY"]
    else:
        workload["gates"].pop("full_replay")
    assert any(b["code"] == blocker for b in checkpoint_result(report, runtime, workload)["blockers"])


def test_sparse_runtime_and_nonregression_are_not_checkpoint_acceptance(acceptance_inputs):
    report, runtime, _ = acceptance_inputs
    result = checkpoint_result(report, runtime)
    assert result["code"] == "CHECKPOINT_BLOCKED"
    assert result["blockers"] == [{"code": "WORKLOAD_MANIFEST_NOT_FROZEN"}]


def test_workload_declared_digests_require_retained_matching_artifacts(tmp_path):
    import hashlib
    import json

    source = tmp_path / "source.json"
    source.write_text("{}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = tmp_path / "workload.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": [{"path": source.name, "sha256": digest}],
                "token_demand": {"frequency_source_sha256": digest, "corpus_source_sha256": "absent"},
            }
        )
    )
    with pytest.raises(ValueError, match="CHECKPOINT_ARTIFACT_UNPINNED"):
        load_workload(manifest)
    source.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="CHECKPOINT_ARTIFACT_CHANGED"):
        load_workload(manifest)


def test_sentence_cli_cannot_overwrite_input_even_before_parsing(tmp_path):
    source = tmp_path / "lexicon.db"
    source.write_bytes(b"preserve")
    with pytest.raises(SystemExit):
        main(["--lexicon", str(source), "--benchmark", str(source), "--report", str(source)])
    assert source.read_bytes() == b"preserve"


def test_workload_loader_cannot_narrow_pre_frozen_public_operation_inventory(tmp_path):
    import hashlib
    import json

    artifacts = []

    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts.append({"path": name, "sha256": digest})
        return digest

    frequency = save("frequency.json", {"the": 100})
    corpus = save("corpus.json", {"the": 101})
    counts = {
        "common_forms": ["the"],
        "frequency_source_sha256": frequency,
        "corpus_source_sha256": corpus,
        "frequency_counts": {"the": 100},
        "corpus_genres": {"news": {"the": 101}},
        "denominator_rules": "all tokens",
        "exclusions": [],
    }
    count_digest = save("counts.json", counts)
    scope_digest = save(
        "scope.json",
        {
            "format": "GSE.checkpoint-workload-scope-freeze/1",
            "token_demand_sha256": count_digest,
            "operations": {"lexical": "all banks", "inference": "exact claims"},
        },
    )
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "artifacts": artifacts,
                "token_demand": {**counts, "counts_receipt_sha256": count_digest},
                "scope_freeze_sha256": scope_digest,
                "operations": [{"id": "lexical", "case_ids": ["some-passing-fixture"]}],
            }
        )
    )
    with pytest.raises(ValueError, match="CHECKPOINT_FROZEN_SCOPE_CHANGED"):
        load_workload(path)


@pytest.mark.parametrize("failure", [None, "known_wrong", "missing_required", "must_not"])
def test_finite_two_sided_audit_is_not_whole_common_form_label_requirement(tmp_path, failure):
    """Synthetic loader fixtures, never production semantic certificates."""
    import hashlib
    import json

    artifacts = []

    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts.append({"path": name, "sha256": digest})
        return digest

    frequency = save("frequency.json", {"the": 100})
    corpus = save("corpus.json", {"the": 101})
    counts = {
        "common_forms": ["the", "teacher", "tree"],
        "frequency_source_sha256": frequency,
        "corpus_source_sha256": corpus,
        "frequency_counts": {"the": 100},
        "corpus_genres": {"news": {"the": 101}},
        "denominator_rules": "all tokens",
        "exclusions": [],
    }
    count_digest = save("counts.json", counts)
    scope_digest = save(
        "scope.json",
        {
            "format": "GSE.checkpoint-workload-scope-freeze/1",
            "token_demand_sha256": count_digest,
            "operations": {"lexical": "all banks", "inference": "exact claims"},
        },
    )
    audit = {
        "code": "PASSED",
        "lexicon_sha256": "lexicon",
        "command": "synthetic loader unit test only",
        "exit_code": 0,
        "audited_forms": ["teacher", "unranked-anatomy-form"],
        "known_wrong": 0,
        "missing_required": 0,
        "checks": dict.fromkeys(
            [
                "positive",
                "must_not",
                "missing_sign",
                "source_warrants",
                "morphology",
                "pos_roles",
                "tail_strata",
                "genre_strata",
            ],
            "PASSED",
        ),
    }
    if failure == "must_not":
        audit["checks"]["must_not"] = "FAILED"
    elif failure:
        audit[failure] = 1
    gate_digest = save("audit.json", audit)
    manifest = {
        "artifacts": artifacts,
        "token_demand": {**counts, "counts_receipt_sha256": count_digest},
        "scope_freeze_sha256": scope_digest,
        "operations": [{"id": "lexical"}, {"id": "inference"}],
        "gates": {
            "two_sided_semantic_audit": {"code": "PASSED", "lexicon_sha256": "lexicon", "receipt_sha256": gate_digest}
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    if failure:
        with pytest.raises(ValueError, match="CHECKPOINT_TWO_SIDED_AUDIT_INCOMPLETE"):
            load_workload(path)
    else:
        assert load_workload(path) == manifest
