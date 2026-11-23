"""Hard evidence survives local, order-independent conditional exceptions."""

from itertools import permutations

import pytest

from gse.curation.lexicon_builder.engine import Assertion, Relation, propagate
from gse.curation.lexicon_builder.resolution import resolve_dictionary


def assertion(bank, value):
    return Assertion(bank, value, "native", "record:" + bank, "dictionary")


def rule(name, banks, rows, *, hard=False, approved=True, guards=()):
    return Relation(name, banks, rows, ("source:" + name,), "foundational" if hard else "conditional", approved, guards)


def exceptions(result):
    return [record for record in result.trace if record["kind"] == "CONDITIONAL_EXCEPTION"]


def test_consistent_rules_preserve_normal_engine_result():
    banks = ("A", "B")
    rules = (rule("equal", banks, ((-1, -1), (0, 0), (1, 1))),)
    assertions = (assertion("A", 1),)
    assert resolve_dictionary(banks, assertions, rules) == propagate(banks, assertions, rules)


def test_direct_native_fact_excepting_conditional_keeps_its_value():
    rules = (rule("negative", ("A",), ((-1,),)),)
    result = resolve_dictionary(("A",), (assertion("A", 1),), rules)
    assert result.code == "RESOLVED"
    assert result.assignments == {"A": 1}
    assert result.conflicts == ()
    receipt = exceptions(result)[0]
    assert receipt["reason"] == "HARD_CONTRADICTION"
    assert receipt["rule_ids"] == ("negative",)
    assert receipt["rules"][0]["provenance"] == ("source:negative",)
    assert receipt["hard_domains"] == {"A": (1,)}
    assert receipt["conflicts"]
    assert receipt["specialization"] == "NOT_INFERRED"


def test_foundational_derivation_is_hard_even_without_direct_assertion():
    rules = (
        rule("hard-equal", ("A", "B"), ((0, 0), (1, 1)), hard=True),
        rule("default-negative", ("B",), ((-1,),)),
    )
    result = resolve_dictionary(("A", "B"), (assertion("A", 1),), rules)
    assert result.assignments == {"A": 1, "B": 1}
    assert exceptions(result)[0]["rule_ids"] == ("default-negative",)


def test_hard_assertion_conflict_is_never_relaxed():
    assertions = (assertion("A", 1), assertion("A", -1))
    result = resolve_dictionary(("A", "B"), assertions, (rule("b", ("B",), ((1,),)),))
    assert result.code == "CONFLICT"
    assert result.domains["A"] == frozenset()
    assert exceptions(result) == []


def test_hard_rule_conflict_is_never_relaxed():
    result = resolve_dictionary(("A",), (assertion("A", 1),), (rule("hard-negative", ("A",), ((-1,),), hard=True),))
    assert result.code == "CONFLICT"
    assert exceptions(result) == []


def test_jointly_conflicting_component_abstains_without_choosing_first_rule():
    rules = (
        rule("positive", ("A",), ((1,),)),
        rule("negative", ("A",), ((-1,),)),
        rule("independent", ("B",), ((0,),)),
    )
    results = [resolve_dictionary(("A", "B"), (), order) for order in permutations(rules)]
    assert all(result == results[0] for result in results)
    result = results[0]
    assert result.code == "PARTIAL"
    assert result.assignments == {"B": 0}
    assert result.domains["A"] == frozenset({-1, 0, 1})
    assert exceptions(result)[0]["rule_ids"] == ("negative", "positive")
    assert exceptions(result)[0]["reason"] == "CONDITIONAL_COMPONENT_CONFLICT"


def test_foundational_edges_connect_conditional_conflict_components():
    rules = (
        rule("bridge", ("A", "B"), ((-1, -1), (0, 0), (1, 1)), hard=True),
        rule("positive", ("A",), ((1,),)),
        rule("negative", ("B",), ((-1,),)),
        rule("independent", ("C",), ((1,),)),
    )
    result = resolve_dictionary(("A", "B", "C"), (), rules)
    assert result.assignments == {"C": 1}
    assert result.domains["A"] == result.domains["B"] == frozenset({-1, 0, 1})
    assert exceptions(result)[0]["rule_ids"] == ("negative", "positive")


def test_whole_component_retraction_removes_dependent_and_harmless_rules():
    rules = (
        rule("positive", ("A",), ((1,),)),
        rule("negative", ("A",), ((-1,),)),
        rule("downstream", ("A", "B"), ((-1, -1), (0, 0), (1, 1))),
    )
    result = resolve_dictionary(("A", "B"), (), rules)
    assert result.assignments == {}
    assert exceptions(result)[0]["rule_ids"] == ("downstream", "negative", "positive")


def test_individually_excepted_rule_does_not_poison_valid_neighbor():
    rules = (
        rule("wrong", ("A", "B"), ((-1, 0),)),
        rule("valid", ("A", "B"), ((1, 1),)),
    )
    result = resolve_dictionary(("A", "B"), (assertion("A", 1),), rules)
    assert result.assignments == {"A": 1, "B": 1}
    assert exceptions(result)[0]["rule_ids"] == ("wrong",)


def test_candidate_and_unmatched_guards_never_fire_or_connect_components():
    rules = (
        rule("positive", ("A",), ((1,),)),
        rule("negative", ("A",), ((-1,),)),
        rule("b", ("B",), ((0,),)),
        rule("inactive-bridge", ("A", "B"), (), guards=(("pos", "noun"),)),
        rule("candidate-bridge", ("A", "B"), (), approved=False),
    )
    result = resolve_dictionary(("A", "B"), (), rules, {"pos": "verb"})
    assert result.assignments == {"B": 0}
    skipped = {item["rule_id"]: item["reason"] for item in result.trace if item["kind"] == "RELATION_SKIPPED"}
    assert skipped == {"candidate-bridge": "UNAPPROVED", "inactive-bridge": "GUARD_MISMATCH"}


def test_empty_guard_has_universal_scope_and_matching_guard_is_exact():
    universal = rule("universal", ("A",), ((1,),))
    conditional = rule("noun-only", ("B",), ((0,),), guards=(("pos", "noun"),))
    assert resolve_dictionary(("A", "B"), (), (universal, conditional), {"pos": "noun"}).assignments == {"A": 1, "B": 0}
    assert resolve_dictionary(("A", "B"), (), (universal, conditional), {"pos": "NOUN"}).assignments == {"A": 1}


def test_exception_is_local_not_a_global_rule_deletion():
    rules = (rule("positive", ("A",), ((1,),)),)
    first = resolve_dictionary(("A",), (assertion("A", -1),), rules)
    second = resolve_dictionary(("A",), (), rules)
    assert first.assignments == {"A": -1}
    assert second.assignments == {"A": 1}
    assert exceptions(second) == []
    assert rules[0].approved is True


def test_joint_relation_conflict_retracts_even_without_direct_assertions():
    rules = (
        rule("equal", ("A", "B"), ((0, 0), (1, 1))),
        rule("unequal", ("A", "B"), ((0, 1), (1, 0))),
        rule("a", ("A",), ((1,),)),
    )
    result = resolve_dictionary(("A", "B"), (), rules)
    assert result.code == "PARTIAL"
    assert result.assignments == {}
    assert exceptions(result)[0]["rule_ids"] == ("a", "equal", "unequal")


def test_input_validation_is_not_bypassed_by_partitioning():
    duplicate = rule("same", ("A",), ((1,),))
    with pytest.raises(ValueError, match="DUPLICATE_RULE_ID"):
        resolve_dictionary(("A",), (), (duplicate, duplicate))
    with pytest.raises(ValueError, match="UNKNOWN_RELATION_BANK"):
        resolve_dictionary(("A",), (), (rule("unknown", ("B",), ((1,),)),))
    with pytest.raises(ValueError, match="INVALID_ASSERTIONS"):
        resolve_dictionary(("A",), [], ())


def test_joint_inconsistency_excepts_conditional_component_before_model():
    rules = tuple(
        rule(name, pair, ((0, 1), (1, 0)))
        for name, pair in (("ab", ("A", "B")), ("bc", ("B", "C")), ("ac", ("A", "C")))
    )
    result = resolve_dictionary(("A", "B", "C"), (), rules)
    assert result.code == "PARTIAL"
    assert exceptions(result)[0]["rule_ids"] == ("ab", "ac", "bc")
    assert exceptions(result)[0]["conflicts"][0]["code"] == "JOINT_CONFLICT"
    assert result.assignments == {}
    scope = next(item for item in result.trace if item["kind"] == "INFERENCE_SCOPE")
    assert scope["complete_search"] is True
    assert scope["satisfiability"] == "SATISFIABLE"


def evaluative_default():
    return Relation(
        "evaluative-size-default",
        ("GOOD", "BIG"),
        tuple((good, big) for good in (-1, 0, 1) for big in (-1, 0, 1) if good == 0 or big == 0),
        ("approved:own-word-evaluation-default",),
        "conditional",
        True,
        (("pos", "adjective"),),
        ("BIG",),
    )


def evidence_guards(result):
    return [record for record in result.trace if record["kind"] == "EVIDENCE_GUARD"]


def test_pure_evaluative_gets_zero_only_without_relevant_size_evidence():
    default = evaluative_default()
    result = resolve_dictionary(("GOOD", "BIG"), (assertion("GOOD", 1),), (default,), {"pos": "adjective"})
    assert result.assignments == {"BIG": 0, "GOOD": 1}
    receipt = evidence_guards(result)[0]
    assert receipt["status"] == "ELIGIBLE"
    assert receipt["reason"] == "NO_RELEVANT_EVIDENCE"
    assert receipt["witnesses"] == ()
    assert receipt["relation"]["absent_evidence"] == ("BIG",)
    assert default.absent_evidence == ("BIG",)
    assert exceptions(result) == []


def test_unknown_but_relevant_size_evidence_blocks_default():
    result = resolve_dictionary(
        ("GOOD", "BIG"), (assertion("GOOD", 1),), (evaluative_default(),), {"pos": "adjective"}, evidence_banks=("BIG",)
    )
    assert result.assignments == {"GOOD": 1}
    assert result.domains["BIG"] == frozenset((-1, 0, 1))
    witness = evidence_guards(result)[0]["witnesses"][0]
    assert witness["supplied_evidence"] is True
    assert witness["baseline_narrowed"] is False
    assert witness["assertions"] == ()
    assert exceptions(result) == []


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_every_explicit_size_value_blocks_default_and_survives(value):
    assertions = (assertion("GOOD", 1), assertion("BIG", value))
    result = resolve_dictionary(("GOOD", "BIG"), assertions, (evaluative_default(),), {"pos": "adjective"})
    assert result.assignments == {"BIG": value, "GOOD": 1}
    assert evidence_guards(result)[0]["reason"] == "RELEVANT_EVIDENCE"
    assert evidence_guards(result)[0]["witnesses"][0]["assertions"][0]["value"] == value
    assert exceptions(result) == []
    assert not any(
        record.get("rule_id") == "evaluative-size-default" and record["kind"] == "RELATION" for record in result.trace
    )


@pytest.mark.parametrize("rows", [((1,),), ((-1,), (1,))])
def test_ordinary_rule_information_blocks_default_before_firing(rows):
    ordinary = rule("size-information", ("BIG",), rows, hard=True)
    result = resolve_dictionary(
        ("GOOD", "BIG"), (assertion("GOOD", 1),), (ordinary, evaluative_default()), {"pos": "adjective"}
    )
    assert result.domains["BIG"] == frozenset(row[0] for row in rows)
    receipt = evidence_guards(result)[0]
    assert receipt["status"] == "BLOCKED"
    assert receipt["witnesses"][0]["baseline_rule_ids"] == ("size-information",)
    assert receipt["witnesses"][0]["baseline_narrowed"] is True
    assert exceptions(result) == []


def test_noun_scope_never_admits_adjective_default():
    result = resolve_dictionary(("GOOD", "BIG"), (assertion("GOOD", 1),), (evaluative_default(),), {"pos": "noun"})
    assert result.assignments == {"GOOD": 1}
    assert evidence_guards(result)[0]["reason"] == "GUARD_MISMATCH"


def test_non_evaluative_does_not_get_size_default_from_guard_alone():
    result = resolve_dictionary(("GOOD", "BIG"), (assertion("GOOD", 0),), (evaluative_default(),), {"pos": "adjective"})
    assert result.assignments == {"GOOD": 0}
    assert result.domains["BIG"] == frozenset((-1, 0, 1))


def test_defaults_share_ordinary_baseline_and_are_order_independent():
    first = Relation("a-first", ("A",), ((0,),), ("declared",), approved=True, absent_evidence=("A",))
    second = Relation("b-second", ("B",), ((1,),), ("declared",), approved=True, absent_evidence=("A",))
    results = [resolve_dictionary(("A", "B"), (), rules) for rules in permutations((first, second))]
    assert results[0] == results[1]
    assert results[0].assignments == {"A": 0, "B": 1}
    assert all(record["status"] == "ELIGIBLE" for record in evidence_guards(results[0]))
    assert all(record["witnesses"] == () for record in evidence_guards(results[0]))


def test_unapproved_default_remains_blocked_after_guard_check():
    default = Relation("candidate", ("A",), ((0,),), (), absent_evidence=("A",))
    result = resolve_dictionary(("A",), (), (default,))
    assert result.assignments == {}
    assert evidence_guards(result)[0]["reason"] == "UNAPPROVED"


def test_hard_conflict_survives_and_defaults_are_not_evaluated_as_repairs():
    assertions = (assertion("GOOD", -1), assertion("GOOD", 1))
    result = resolve_dictionary(("GOOD", "BIG"), assertions, (evaluative_default(),), {"pos": "adjective"})
    assert result.code == "CONFLICT"
    assert result.domains["GOOD"] == frozenset()
    assert evidence_guards(result)[0]["reason"] == "BASELINE_CONFLICT"
    assert exceptions(result) == []


@pytest.mark.parametrize(
    "banks,code",
    [
        (["BIG"], "INVALID_EVIDENCE_BANKS"),
        (("BIG", "BIG"), "DUPLICATE_EVIDENCE_BANK"),
        (("unknown",), "UNKNOWN_EVIDENCE_BANK"),
        ((None,), "INVALID_EVIDENCE_BANKS"),
        (("",), "INVALID_EVIDENCE_BANKS"),
    ],
)
def test_malformed_evidence_banks_rejected_even_without_defaults(banks, code):
    with pytest.raises(ValueError, match=code):
        resolve_dictionary(("GOOD", "BIG"), (), (), evidence_banks=banks)
