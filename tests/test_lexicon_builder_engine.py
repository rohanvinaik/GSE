"""Intent tests for lexical constraint closure and its refusal boundaries."""

from copy import deepcopy
from itertools import product
from random import Random

import pytest

from gse.curation.lexicon_builder.engine import Assertion, Relation, propagate


def claim(bank, value, record="r", source="dictionary"):
    return Assertion(bank, value, source, record, source)


def rule(name, banks, rows, **kwargs):
    return Relation(name, banks, rows, ("founder:test",), approved=True, **kwargs)


def test_silence_and_explicit_zero_are_different():
    result = propagate(("A", "B"), (claim("A", 0),), ())
    assert result.code == "PARTIAL"
    assert result.assignments == {"A": 0}
    assert result.domains == {"A": frozenset({0}), "B": frozenset({-1, 0, 1})}
    assert result.trace[0]["source"] == "dictionary"
    assert result.trace[0]["remaining"] == (0,)


def test_any_conflicting_assertion_blocks_majority_and_zero_conflict():
    evidence = (claim("A", 1, "a"), claim("A", 1, "b"), claim("A", 0, "c", "other"))
    result = propagate(("A",), evidence, ())
    assert result.code == "CONFLICT"
    assert result.domains["A"] == frozenset()
    assert "A" not in result.assignments
    assert result.conflicts[0]["code"] == "ASSERTION_CONFLICT"
    assert len(result.conflicts[0]["assertions"]) == 3


def test_higher_order_joint_constraint_performs_inverse_narrowing():
    one = rule("exactly-one", ("A", "B", "C"), ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    result = propagate(("A", "B", "C"), (claim("A", 0), claim("B", 0)), (one,))
    assert result.code == "RESOLVED"
    assert result.assignments == {"A": 0, "B": 0, "C": 1}
    assert any(row.get("rule_id") == "exactly-one" and row.get("bank") == "C" for row in result.trace)


def test_conjunctive_constraint_does_not_fire_from_one_antecedent():
    rows = tuple(row for row in product((-1, 0, 1), repeat=3) if row[:2] != (1, 1) or row[2] == 0)
    relation = rule("joint", ("A", "B", "C"), rows)
    partial = propagate(("A", "B", "C"), (claim("A", 1),), (relation,))
    assert partial.domains["C"] == frozenset({-1, 0, 1})
    complete = propagate(("A", "B", "C"), (claim("A", 1), claim("B", 1)), (relation,))
    assert complete.assignments["C"] == 0


def test_fixed_point_revisits_earlier_relation_and_is_order_independent():
    relation_ab = rule("first", ("A", "B"), ((-1, -1), (0, 0), (1, 1)))
    relation_bc = rule("second", ("B", "C"), ((-1, -1), (0, 0), (1, 1)))
    result = propagate(("A", "B", "C"), (claim("C", -1),), (relation_ab, relation_bc))
    reversed_result = propagate(("C", "B", "A"), (claim("C", -1),), (relation_bc, relation_ab))
    assert result == reversed_result
    assert result.assignments == {"A": -1, "B": -1, "C": -1}


def test_unapproved_and_unmatched_guards_never_fire():
    candidate = Relation("candidate", ("A",), ((1,),), ())
    guarded = rule("guarded", ("A",), ((0,),), guards=(("pos", "noun"),))
    result = propagate(("A",), (), (candidate, guarded), {"pos": "verb"})
    assert result.domains["A"] == frozenset({-1, 0, 1})
    assert {receipt["reason"] for receipt in result.trace if receipt["kind"] == "RELATION_SKIPPED"} == {
        "UNAPPROVED",
        "GUARD_MISMATCH",
    }
    applied = propagate(("A",), (), (guarded,), {"pos": "noun"})
    assert applied.assignments == {"A": 0}


def test_empty_relation_is_impossible_not_silent():
    result = propagate(("A",), (), (rule("impossible", ("A",), ()),))
    assert result.code == "CONFLICT"
    assert result.domains["A"] == frozenset()
    assert result.conflicts[0]["rule_id"] == "impossible"


def test_rule_conflict_cannot_overwrite_source_assertion():
    result = propagate(("A",), (claim("A", 1),), (rule("only-zero", ("A",), ((0,),)),))
    assert result.code == "CONFLICT"
    assert result.assignments == {}
    assert next(row for row in result.trace if row["kind"] == "RELATION")["domains_before"] == {"A": (1,)}


def test_arc_consistency_does_not_claim_complete_global_satisfiability():
    unequal = ((0, 1), (1, 0))
    relations = (
        rule("ab", ("A", "B"), unequal),
        rule("bc", ("B", "C"), unequal),
        rule("ac", ("A", "C"), unequal),
    )
    result = propagate(("A", "B", "C"), (), relations)
    assert result.code == "PARTIAL"
    assert result.assignments == {}
    assert result.trace[-1]["complete_search"] is False
    for value in (0, 1):
        assert propagate(("A", "B", "C"), (claim("A", value),), relations).code == "CONFLICT"


def test_no_input_mutation_and_repeatable_receipts():
    assertions = (claim("A", 0, "z"), claim("A", 0, "a"))
    relations = (rule("same", ("A", "B"), ((0, 0), (1, 1))),)
    context = {"pos": "noun"}
    original = deepcopy((assertions, relations, context))
    result = propagate(("B", "A"), assertions, relations, context)
    assert (assertions, relations, context) == original
    assert result == propagate(("A", "B"), tuple(reversed(assertions)), relations, context)


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, -2, 2])
def test_assertions_reject_nonternary_values(value):
    with pytest.raises(ValueError):
        Assertion("A", value, "source", "record", "family")


def test_nonlexical_assertion_is_refused():
    with pytest.raises(ValueError, match="NONLEXICAL"):
        Assertion("A", 1, "source", "record", "family", scope="participant")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"banks": ("A", "A")},
        {"allowed_rows": ((True,),)},
        {"allowed_rows": ((1, 0),)},
        {"approved": 1},
        {"approved": True, "provenance": ()},
        {"approved": True, "authority": "candidate"},
        {"guards": (("pos", "n"), ("pos", "v"))},
    ],
)
def test_malformed_relation_refused(kwargs):
    base = {"rule_id": "r", "banks": ("A",), "allowed_rows": ((1,),), "provenance": ("p",)}
    base.update(kwargs)
    with pytest.raises(ValueError):
        Relation(**base)


def test_invalid_inputs_validated_even_when_evidence_already_conflicts():
    with pytest.raises(ValueError, match="UNKNOWN_RELATION_BANK"):
        propagate(("A",), (claim("A", 0), claim("A", 1)), (Relation("bad", ("UNKNOWN",), (), ()),))
    with pytest.raises(ValueError, match="DUPLICATE_BANK"):
        propagate(("A", "A"), (), ())
    with pytest.raises(ValueError, match="UNKNOWN_BANK"):
        propagate(("A",), (claim("B", 0),), ())
    with pytest.raises(ValueError, match="INVALID_CONTEXT"):
        propagate(("A",), (), (), {"pos": None})
    repeated = rule("duplicate", ("A",), ((0,),))
    with pytest.raises(ValueError, match="DUPLICATE_RULE_ID"):
        propagate(("A",), (), (repeated, repeated))


def test_empty_problem_is_resolved_without_invented_assignments():
    result = propagate((), (), ())
    assert result.code == "RESOLVED"
    assert result.assignments == result.domains == {}


def test_propagation_never_eliminates_a_complete_joint_witness():
    """Compare against exhaustive assignments, independent of the GAC procedure."""
    generator = Random(20261029)
    banks = ("A", "B", "C")
    for case in range(30):
        relations = tuple(
            rule(
                f"case-{case}-{index}",
                coordinates,
                tuple(row for row in product((-1, 0, 1), repeat=len(coordinates)) if generator.randrange(3)),
            )
            for index, coordinates in enumerate((("A", "B"), ("B", "C"), ("A", "B", "C")))
        )
        evidence = (claim("A", generator.choice((-1, 0, 1))),) if case % 2 else ()
        solutions = []
        for values in product((-1, 0, 1), repeat=3):
            assignment = dict(zip(banks, values))
            if all(assignment[item.bank] == item.value for item in evidence) and all(
                tuple(assignment[bank] for bank in relation.banks) in relation.allowed_rows for relation in relations
            ):
                solutions.append(assignment)
        result = propagate(banks, evidence, relations)
        for solution in solutions:
            assert all(value in result.domains[bank] for bank, value in solution.items())
        if result.code == "CONFLICT":
            assert solutions == []
        if result.code == "RESOLVED":
            assert result.assignments in solutions


def test_direct_propagation_fails_closed_on_unevaluated_evidence_guard():
    default = rule("default", ("A",), ((0,),), absent_evidence=("A",))
    result = propagate(("A",), (), (default,))
    assert result.assignments == {}
    assert any(record.get("reason") == "EVIDENCE_GUARD_NOT_EVALUATED" for record in result.trace)


@pytest.mark.parametrize("absence", [["A"], ("A", "A"), ("",), (1,), "A", None])
def test_relation_rejects_malformed_absence_guards(absence):
    with pytest.raises(ValueError):
        rule("default", ("A",), ((0,),), absent_evidence=absence)


def test_unknown_absence_bank_is_rejected_even_when_default_unapproved():
    default = Relation("candidate", ("A",), ((0,),), (), absent_evidence=("UNKNOWN",))
    with pytest.raises(ValueError, match="UNKNOWN_ABSENT_EVIDENCE_BANK"):
        propagate(("A",), (), (default,))
