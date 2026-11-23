"""Pin the distinct sentence-audit outcomes for absence, zero, and sign."""

import pytest

from scripts.audit_lexicon_sentences import compare_reports, score_domain


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
