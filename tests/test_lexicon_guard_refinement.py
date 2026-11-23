"""An open target supplies reach and an excluding domain supplies opposition."""

import pytest

from scripts.refine_lexicon_pattern import _disposition


@pytest.mark.parametrize(
    ("code", "premise", "target", "expected"),
    [
        ("PARTIAL", [0], [-1, 0, 1], "PROVISIONAL_FORWARD_FILL"),
        ("PARTIAL", [0], [0], "ALREADY_SUPPORTED"),
        ("PARTIAL", [0], [-1, 1], "CONTRADICTION"),
        ("PARTIAL", [-1, 0, 1], [1], "PREMISE_UNRESOLVED"),
        ("PARTIAL", [1], [1], "PREMISE_EXCLUDED"),
        ("CONFLICT", [0], [], "BASELINE_REQUIRES_REVIEW"),
    ],
)
def test_zero_hypothesis_population_disposition(code, premise, target, expected):
    assert _disposition(code, premise, target, 0, 0) == expected
