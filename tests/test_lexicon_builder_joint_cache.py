"""Complete joint-support reuse must preserve decisions, budgets, and receipts."""

import json
from collections import Counter
from dataclasses import asdict, replace
from itertools import islice, product
from random import Random

import pytest

from gse.curation.lexicon_builder import engine
from gse.curation.lexicon_builder.engine import Assertion, DomainRestriction, Relation, propagate
from gse.curation.lexicon_builder.foundation import BANKS, projection_relations
from gse.curation.lexicon_builder.resolution import resolve_dictionary


@pytest.fixture(autouse=True)
def empty_joint_cache():
    engine._joint_witnesses.cache_clear()
    yield
    engine._joint_witnesses.cache_clear()


def relation(name, banks, rows, **kwargs):
    return Relation(name, banks, rows, (f"provenance:{name}",), approved=True, **kwargs)


def serialized(result):
    return json.dumps(asdict(result), default=sorted, sort_keys=True, separators=(",", ":")).encode()


def test_projection_workload_preserves_distinct_evidence_receipts(monkeypatch, record_property):
    """Measure repeated exact inputs on the existing dictionary-resolution path."""
    original = engine._joint_support
    counts = Counter()

    def observe(domains, active, conflicts, trace, limit):
        for rules in engine._relation_components(active):
            banks = tuple(sorted({bank for rule in rules for bank in rule.banks}))
            key = (
                tuple((bank, tuple(sorted(domains[bank]))) for bank in banks),
                tuple((rule.banks, tuple(sorted(set(rule.allowed_rows)))) for rule in rules),
            )
            counts[key] += 1
        return original(domains, active, conflicts, trace, limit)

    monkeypatch.setattr(engine, "_joint_support", observe)
    relations = projection_relations()
    records = set()
    for index in range(12):
        assertion = Assertion("WANT", -1, "native", f"definition:{index}", "dictionary")
        result = resolve_dictionary(BANKS, (assertion,), relations, {"pos": "adjective"})
        assert result.assignments["WANT"] == -1
        assert result.domains["HAVE"] == engine.TERNARY
        records.update(row["record_id"] for row in result.trace if row["kind"] == "ASSERTION")
    assert records == {f"definition:{index}" for index in range(12)}
    assert sum(counts.values()) > len(counts)
    record_property("component_calls", sum(counts.values()))
    record_property("distinct_component_inputs", len(counts))
    record_property("repeated_component_inputs", sum(counts.values()) - len(counts))


def test_cached_and_uncached_random_constraints_have_identical_complete_receipts(monkeypatch):
    random = Random(20261029)
    banks = ("A", "B", "C", "D")
    cached = engine._joint_witnesses
    for case in range(100):
        relations = tuple(
            relation(
                f"rule:{case}:{index}",
                coordinates,
                tuple(row for row in product((-1, 0, 1), repeat=len(coordinates)) if random.randrange(4)),
                authority="foundational" if index % 2 else "conditional",
                guards=(("pos", "noun"),) if index == 2 else (),
            )
            for index, coordinates in enumerate((("A", "B"), ("B", "C"), ("C", "A", "D")))
        )
        assertions = (
            (Assertion("A", random.choice((-1, 0, 1)), "native", f"entry:{case}", "dictionary"),) if case % 3 else ()
        )
        restrictions = (
            (
                DomainRestriction(
                    "D", random.choice(((-1, 0), (0, 1), (-1, 1))), "native", f"restriction:{case}", "dictionary"
                ),
            )
            if case % 4
            else ()
        )
        context = {"pos": "noun" if case % 2 else "adjective"}
        limit = (1, 7, 8, 27, 81)[case % 5]
        actual = propagate(
            banks, assertions, relations, context, domain_restrictions=restrictions, max_joint_assignments=limit
        )
        dictionary = resolve_dictionary(banks, assertions, relations, context, domain_restrictions=restrictions)
        with monkeypatch.context() as bypass:
            bypass.setattr(engine, "_joint_witnesses", cached.__wrapped__)
            expected = propagate(
                banks, assertions, relations, context, domain_restrictions=restrictions, max_joint_assignments=limit
            )
            expected_dictionary = resolve_dictionary(
                banks, assertions, relations, context, domain_restrictions=restrictions
            )
        assert serialized(actual) == serialized(expected)
        assert serialized(dictionary) == serialized(expected_dictionary)
        if limit == 81:
            # Independent complete-assignment oracle includes unsorted table
            # columns, so key canonicalization cannot silently swap meanings.
            solutions = []
            for values in product((-1, 0, 1), repeat=len(banks)):
                assignment = dict(zip(banks, values, strict=True))
                if (
                    all(assignment[item.bank] == item.value for item in assertions)
                    and all(assignment[item.bank] in item.allowed_values for item in restrictions)
                    and all(
                        tuple(assignment[bank] for bank in rule.banks) in rule.allowed_rows
                        for rule in relations
                        if all(context.get(key) == value for key, value in rule.guards)
                    )
                ):
                    solutions.append(assignment)
            if solutions:
                assert actual.domains == {bank: frozenset(solution[bank] for solution in solutions) for bank in banks}
            else:
                assert actual.code == "CONFLICT"


def test_equivalent_tables_reuse_support_without_reusing_current_provenance():
    first = relation("old", ("A", "B"), ((0, 1), (1, 0)))
    old = propagate(("A", "B"), (), (first,))
    before = engine._joint_witnesses.cache_info()
    second = relation("new", ("B", "A"), ((0, 1), (1, 0), (1, 0)))
    new = propagate(("A", "B"), (), (second,))
    after = engine._joint_witnesses.cache_info()
    assert old.domains == new.domains
    assert after.hits == before.hits + 1
    assert after.misses == before.misses
    receipt = next(row for row in new.trace if row["kind"] == "JOINT_CHECK")
    assert receipt["rule_ids"] == ("new",)
    assert receipt["provenance"] == (("new", ("provenance:new",)),)
    assert serialized(old) != serialized(new)
    old.domains["A"] = frozenset()
    old.trace[-1]["satisfiability"] = "CORRUPTED_BY_CALLER"
    assert propagate(("A", "B"), (), (second,)) == new


def test_rule_order_duplicates_and_coordinate_names_are_not_cache_identity():
    equal = ((-1, -1), (0, 0), (1, 1))
    first = (relation("ab", ("A", "B"), equal), relation("bc", ("B", "C"), equal))
    propagate(("A", "B", "C"), (), first)
    info = engine._joint_witnesses.cache_info()
    renamed = (
        relation("z", ("X", "Y"), equal),
        relation("a", ("Y", "Z"), equal),
        relation("duplicate", ("X", "Y"), equal),
    )
    result = propagate(("X", "Y", "Z"), (), renamed)
    assert engine._joint_witnesses.cache_info().hits == info.hits + 1
    assert all(domain == engine.TERNARY for domain in result.domains.values())
    receipt = next(row for row in result.trace if row["kind"] == "JOINT_CHECK")
    assert receipt["rule_ids"] == ("a", "duplicate", "z")
    assert receipt["witnesses"] == 3


def test_warm_conflict_cache_never_bypasses_smaller_budget(monkeypatch):
    rules = tuple(
        relation(name, banks, ((0, 1), (1, 0)))
        for name, banks in (("ab", ("A", "B")), ("bc", ("B", "C")), ("ac", ("A", "C")))
    )
    assert propagate(("A", "B", "C"), (), rules, max_joint_assignments=8).code == "CONFLICT"
    info = engine._joint_witnesses.cache_info()
    actual = propagate(("A", "B", "C"), (), rules, max_joint_assignments=7)
    assert engine._joint_witnesses.cache_info() == info
    assert actual.code == "PARTIAL"
    assert actual.assignments == {}
    assert actual.trace[-1]["satisfiability"] == "NOT_ESTABLISHED"
    assert any(row["kind"] == "SOLVER_LIMIT" for row in actual.trace)
    with monkeypatch.context() as bypass:
        bypass.setattr(engine, "_joint_witnesses", engine._joint_witnesses.__wrapped__)
        expected = propagate(("A", "B", "C"), (), rules, max_joint_assignments=7)
    assert serialized(actual) == serialized(expected)


def test_cached_joint_zero_preserves_independent_unknown_and_changes_with_domain():
    rules = (
        relation("ab", ("A", "B"), ((0, 0), (1, 1))),
        relation("bc", ("B", "C"), ((0, 0), (1, 1))),
        relation("ac", ("A", "C"), ((0, 0), (0, 1), (1, 0))),
    )
    result = propagate(("A", "B", "C", "UNKNOWN"), (), rules)
    assert result.assignments == {"A": 0, "B": 0, "C": 0}
    assert result.domains["UNKNOWN"] == engine.TERNARY
    assert propagate(("A", "B", "C", "UNKNOWN"), (), rules) == result
    rejected = propagate(("A", "B", "C", "UNKNOWN"), (Assertion("A", 1, "native", "new", "dictionary"),), rules)
    assert rejected.code == "CONFLICT"
    changed = tuple(replace(rule, allowed_rows=((0, 0), (1, 1))) for rule in rules)
    widened = propagate(("A", "B", "C", "UNKNOWN"), (), changed)
    assert widened.assignments == {}
    assert widened.domains["A"] == frozenset((0, 1))


def test_cached_rule_cannot_bypass_approval_or_guards():
    approved = relation("only-zero", ("A",), ((0,),), guards=(("pos", "noun"),))
    assert propagate(("A",), (), (approved,), {"pos": "noun"}).assignments == {"A": 0}
    for rule, context, reason in (
        (replace(approved, approved=False), {"pos": "noun"}, "UNAPPROVED"),
        (approved, {"pos": "verb"}, "GUARD_MISMATCH"),
        (replace(approved, absent_evidence=("A",)), {"pos": "noun"}, "EVIDENCE_GUARD_NOT_EVALUATED"),
    ):
        result = propagate(("A",), (), (rule,), context)
        assert result.domains["A"] == engine.TERNARY
        assert result.trace[0]["reason"] == reason


@pytest.mark.parametrize("limit", [None, True, False, 0, -1, 3.0, "3"])
def test_cached_result_never_bypasses_budget_validation(limit):
    rules = (relation("all", ("A",), ((-1,), (0,), (1,))),)
    propagate(("A",), (), rules)
    with pytest.raises(ValueError, match="INVALID_JOINT_SEARCH_LIMIT"):
        propagate(("A",), (), rules, max_joint_assignments=limit)


def test_cached_support_is_immutable_and_cache_size_is_bounded():
    result = engine._joint_witnesses(((-1, 0, 1),), (((0,), ((-1,), (0,), (1,))),))
    assert result == (3, (frozenset((-1, 0, 1)),))
    assert isinstance(hash(result), int)
    engine._joint_witnesses.cache_clear()
    for values in islice(product((-1, 0, 1), repeat=8), 4097):
        domains = tuple((value,) for value in values)
        assert engine._joint_witnesses(domains, ()) == (1, tuple(frozenset((value,)) for value in values))
    info = engine._joint_witnesses.cache_info()
    assert info.maxsize == info.currsize == 4096
    assert info.misses == 4097
    engine._joint_witnesses(((-1,),) * 8, ())
    assert engine._joint_witnesses.cache_info().misses == info.misses + 1


def test_interrupted_enumeration_cannot_cache_partial_support(monkeypatch):
    def interrupted(*domains):
        yield (-1,)
        raise RuntimeError("enumeration interrupted")

    with monkeypatch.context() as interrupt:
        interrupt.setattr(engine, "product", interrupted)
        with pytest.raises(RuntimeError, match="enumeration interrupted"):
            engine._joint_witnesses(((-1, 0, 1),), ())
    assert engine._joint_witnesses.cache_info().currsize == 0
    assert engine._joint_witnesses(((-1, 0, 1),), ()) == (3, (frozenset((-1, 0, 1)),))
