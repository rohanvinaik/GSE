"""The public evidence preserves signs even when the resulting polarity cancels."""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import negation_signs
from gse.symbolic.expression import node_negation_count


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as instance:
        yield instance


def test_node_sign_count_keeps_correlative_and_independent_mechanisms_apart():
    assert node_negation_count(["never", "not"]) == 2
    assert node_negation_count(["neither", "nor"]) == 1
    assert node_negation_count(["not", "nor"]) == 1
    assert node_negation_count([]) == 0


@pytest.mark.parametrize(
    "text,count",
    [
        ("He never did not answer.", 2),
        ("He did not go.", 1),
        ("He is not unhappy.", 2),
        ("He is unhappy.", 1),
        ("He is happy.", 0),
        ("He did unlock it.", 0),
    ],
)
def test_real_entry_preserves_licensed_sign_population(encoder, text, count):
    evidence = negation_signs(encoder.encode(text))
    assert evidence["state"] == "read"
    assert evidence["count"] == count


def test_cancelled_signs_retain_source_and_owner(encoder):
    evidence = negation_signs(encoder.encode("He never did not answer."))
    owner = evidence["owners"][0]
    assert owner["polarity"] == "affirmed"
    assert owner["count"] == 2
    assert [item["lemma"] for item in owner["sources"]] == ["never", "not"]
    assert len({item["owner"] for item in owner["sources"]}) == 1


def test_unresolved_uptake_and_invalid_trace_are_not_observed_zero(encoder):
    assert negation_signs(encoder.encode("I hope not."))["state"] == "partial"
    assert negation_signs(None)["count"] is None


def test_reversal_and_hierarchy_are_separate_from_negative_clauses(encoder):
    reversal = negation_signs(encoder.encode("He did unlock it."))
    assert reversal["reversals"] and reversal["count"] == 0
    hierarchy = negation_signs(encoder.encode("He is not very good."))
    assert hierarchy["count"] == 0
    assert hierarchy["owners"][0]["mechanism"] == "hierarchy_direction"
