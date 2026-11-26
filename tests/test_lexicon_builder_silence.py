"""The silent state (Rohan, F118: "0 is explicit absence; empty is silence") in the constraint engine."""

import pytest

from GSE.curation.lexicon_builder.engine import (
    EMPTY,
    STATES,
    TERNARY,
    Assertion,
    DomainRestriction,
    Relation,
    propagate,
)
from GSE.curation.lexicon_builder.resolution import resolve_dictionary

BIPOLAR = frozenset(STATES)
UNPAIRED = frozenset((EMPTY, 0, 1))

# F067, as October's EVALUATOR_EXCLUDES_SIZE writes it: an own evaluator is an explicit size absence, never silence.
EVALUATOR_EXCLUDES_SIZE = Relation(
    "evaluator-excludes-size",
    ("GOOD", "BIG"),
    tuple((good, big) for good in (EMPTY, -1, 0, 1) for big in (EMPTY, -1, 0, 1) if good in (EMPTY, 0) or big == 0),
    ("FOUNDER:F067",),
    "foundational",
    True,
)


def _assert(bank, value):
    return Assertion(bank, value, "src", f"r:{bank}", "fam")


def test_without_starting_domains_nothing_changes():
    result = propagate(("A", "B"), (_assert("A", 1),), ())
    assert result.domains == {"A": frozenset({1}), "B": TERNARY}
    assert result.silent == () and result.assignments == {"A": 1} and result.code == "PARTIAL"


def test_a_relation_can_require_explicit_absence_rather_than_silence():
    start = {"GOOD": BIPOLAR, "BIG": BIPOLAR}
    good = propagate(("GOOD", "BIG"), (_assert("GOOD", 1),), (EVALUATOR_EXCLUDES_SIZE,), initial_domains=start)
    assert good.domains["BIG"] == frozenset({0}) and good.assignments == {"GOOD": 1, "BIG": 0}
    silent = propagate(
        ("GOOD", "BIG"),
        (),
        (EVALUATOR_EXCLUDES_SIZE,),
        initial_domains=start,
        domain_restrictions=(DomainRestriction("GOOD", (EMPTY,), "type", "t:1", "applicability"),),
    )
    assert silent.domains["BIG"] == BIPOLAR  # a silent GOOD constrains nothing
    assert silent.silent == ("GOOD",) and "GOOD" not in silent.assignments


def test_silence_is_never_an_assignment_and_a_decided_silence_counts_as_resolved():
    result = propagate(
        ("A",),
        (),
        (),
        initial_domains={"A": UNPAIRED},
        domain_restrictions=(DomainRestriction("A", (EMPTY,), "type", "t:1", "applicability"),),
    )
    assert result.code == "RESOLVED" and result.assignments == {} and result.silent == ("A",)


def test_unpaired_banks_cannot_take_the_negative_sign():
    result = propagate(("FEEL",), (_assert("FEEL", -1),), (), initial_domains={"FEEL": UNPAIRED})
    assert result.code == "CONFLICT"


def test_content_against_a_silence_restriction_is_a_named_conflict():
    result = propagate(
        ("A",),
        (_assert("A", 1),),
        (),
        initial_domains={"A": BIPOLAR},
        domain_restrictions=(DomainRestriction("A", (EMPTY,), "type", "t:1", "applicability"),),
    )
    assert result.code == "CONFLICT" and result.conflicts[0]["code"] == "DOMAIN_RESTRICTION_CONFLICT"


def test_applicability_restriction_excludes_only_silence():
    result = propagate(
        ("A",),
        (),
        (),
        initial_domains={"A": BIPOLAR},
        domain_restrictions=(DomainRestriction("A", (-1, 0, 1), "type", "t:1", "applicability"),),
    )
    assert result.domains["A"] == TERNARY and result.silent == ()


def test_assertions_stay_signed():
    with pytest.raises(ValueError):
        Assertion("A", EMPTY, "src", "r", "fam")


@pytest.mark.parametrize(
    "start", [{"Z": BIPOLAR}, {"A": frozenset()}, {"A": frozenset({2})}, {"A": frozenset({True})}, ["A"]]
)
def test_invalid_starting_domains_are_refused(start):
    with pytest.raises(ValueError):
        propagate(("A",), (), (), initial_domains=start)


def test_joint_support_orders_silence_with_signs():
    pair = Relation("pair", ("A", "B"), ((EMPTY, EMPTY), (1, 1)), ("law",), "foundational", True)
    third = Relation("third", ("B", "C"), ((EMPTY, 0), (1, 1)), ("law",), "foundational", True)
    start = {bank: BIPOLAR for bank in "ABC"}
    result = propagate(("A", "B", "C"), (_assert("C", 0),), (pair, third), initial_domains=start)
    assert result.silent == ("A", "B") and result.assignments == {"C": 0} and result.code == "RESOLVED"


def test_the_resolver_carries_silence_through():
    start = {"GOOD": BIPOLAR, "BIG": BIPOLAR}
    restriction = DomainRestriction("GOOD", (EMPTY,), "type", "t:1", "applicability")
    result = resolve_dictionary(
        ("GOOD", "BIG"), (), (EVALUATOR_EXCLUDES_SIZE,), initial_domains=start, domain_restrictions=(restriction,)
    )
    assert result.silent == ("GOOD",)
