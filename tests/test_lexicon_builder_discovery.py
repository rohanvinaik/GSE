"""Discovery diagnoses evidence; observation counts never admit causal rules."""

import math
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from gse.curation.lexicon_builder.discovery import BankObservation, discover_bundle, discover_relations
from gse.curation.lexicon_builder.engine import Assertion, propagate


def observation(entry, bank, value, source="dictionary", record=None, family="dictionary", **kwargs):
    return BankObservation(entry, bank, value, source, record or f"{entry}:{bank}:{value}", family, **kwargs)


def test_zero_is_support_but_silence_is_unknown():
    observations = (
        observation("one", "A", 1),
        observation("one", "B", 0),
        observation("two", "A", 1),
        observation("two", "B", None),
        observation("three", "A", 1),
    )
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),))
    assert [r["entry_id"] for r in report.support] == ["one"]
    assert [r["entry_id"] for r in report.unknown] == ["three", "two"]
    assert report.counterexamples == ()
    assert report.by_family["dictionary"]["eligible"] == 1
    assert report.relation.approved is False
    assert propagate(("A", "B"), (), (report.relation,)).assignments == {}


def test_counterexamples_do_not_disappear_under_large_weights():
    observations = (
        observation("common", "A", 1),
        observation("common", "B", 0),
        observation("rare", "A", 1),
        observation("rare", "B", 1),
    )
    (report,) = discover_relations(observations, {"common": 100000, "rare": 0.1}, (("A", 1, "B", 0),))
    assert report.by_family["dictionary"]["support"] == 1
    assert report.by_family["dictionary"]["counterexamples"] == 1
    assert report.by_family["dictionary"]["weighted_support"] == 100000
    assert report.counterexamples[0]["entry_id"] == "rare"
    assert report.relation.approved is False


def test_conflicting_source_records_are_not_voted_or_averaged():
    observations = (
        observation("word", "A", 1),
        observation("word", "B", 0, record="first"),
        observation("word", "B", 0, record="second"),
        observation("word", "B", 1, record="third"),
    )
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),))
    assert report.support == report.counterexamples == ()
    assert report.conflicting[0]["code"] == "CONSEQUENT_CONFLICT"
    assert report.conflicting[0]["consequent_values"] == (0, 1)
    assert len(report.conflicting[0]["observations"]) == 4


def test_sources_stay_separate_and_disagreement_remains_visible():
    observations = (
        observation("word", "A", 1, source="first"),
        observation("word", "B", 0, source="first"),
        observation("word", "A", 1, source="second", family="other"),
        observation("word", "B", 1, source="second", family="other"),
    )
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),))
    assert len(report.support) == len(report.counterexamples) == 1
    assert report.by_family["dictionary"]["support"] == 1
    assert report.by_family["other"]["counterexamples"] == 1


def test_models_derivations_and_nonlexical_records_never_validate_candidates():
    observations = (
        observation("source", "A", 1),
        observation("source", "B", 0),
        observation("derived", "A", 1, origin="derived"),
        observation("derived", "B", 0, origin="derived"),
        observation("model", "B", 0, origin="model"),
        observation("nested", "B", 0, scope="embedded"),
    )
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),))
    assert len(report.support) == 1
    assert len(report.ineligible) == 4
    assert report.by_family["dictionary"]["support"] == 1
    assert all("source:" in item for item in report.relation.provenance)


def test_unknown_antecedent_and_different_antecedent_not_confirmations():
    observations = (
        observation("silent", "B", 0),
        observation("different", "A", -1),
        observation("different", "B", 0),
    )
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),))
    assert report.support == report.counterexamples == report.unknown == ()
    assert report.by_family["dictionary"]["antecedent_unknown"] == 1
    assert report.by_family["dictionary"]["antecedent_other"] == 1
    assert report.relation.provenance == ()


def test_automatic_candidates_require_observed_joint_values_and_are_deterministic():
    observations = (observation("one", "A", 1), observation("one", "B", 0), observation("one", "C", None))
    reports = discover_relations(observations)
    assert {(r.antecedent, r.consequent) for r in reports} == {(("A", 1), ("B", 0)), (("B", 0), ("A", 1))}
    assert reports == discover_relations(tuple(reversed(observations)))
    assert discover_relations(()) == ()


def test_candidate_relation_table_encodes_only_the_proposed_implication():
    (report,) = discover_relations((), candidates=(("A", 1, "B", 0),))
    rows = set(report.relation.allowed_rows)
    assert (1, 0) in rows
    assert (1, 1) not in rows
    assert (1, -1) not in rows
    assert (-1, 1) in rows
    assert (0, -1) in rows


@pytest.mark.parametrize("weight", [-1, math.inf, math.nan, True, "1"])
def test_invalid_weights_are_refused(weight):
    with pytest.raises(ValueError, match="INVALID_WEIGHT"):
        discover_relations((), {"entry": weight})


def test_weight_overflow_cannot_escape_into_nonstandard_json():
    with pytest.raises(ValueError, match="INVALID_WEIGHT"):
        discover_relations((), {"entry": 10**1000})
    observations = (observation("one", "A", 1), observation("two", "A", 1))
    with pytest.raises(ValueError, match="WEIGHT_TOTAL_OVERFLOW"):
        discover_relations(observations, {"one": 1e308, "two": 1e308})


@pytest.mark.parametrize("value", [True, 1.0, "1", 2])
def test_invalid_observation_value_refused(value):
    with pytest.raises(ValueError):
        BankObservation("e", "A", value, "s", "r", "f")


def test_malformed_candidates_refused():
    for candidate in [("A", 1, "A", 0), ("A", True, "B", 1), ("A", 1, "B")]:
        with pytest.raises(ValueError):
            discover_relations((), candidates=(candidate,))


def test_bundle_uses_exact_source_record_identity_without_vector_merging():
    bundle = SimpleNamespace(
        definitions=(SimpleNamespace(entry_id="dog"), SimpleNamespace(entry_id="cat")),
        observations=tuple(
            SimpleNamespace(entry_id=entry, source="dictionary", record_id=entry, family="dictionary", scope="lexical")
            for entry in ("dog", "cat")
        ),
        assertions=tuple(
            Assertion(bank, value, "dictionary", entry, "dictionary")
            for entry in ("dog", "cat")
            for bank, value in (("A", 1), ("B", 0))
        ),
    )
    reports = discover_bundle(bundle)
    assert len(reports) == 2
    assert {row["entry_id"] for row in reports[0].support} == {"dog", "cat"}
    assert asdict(reports[0])["admission"] == "UNAPPROVED_CANDIDATE"
    assert asdict(reports[0])["propagation_scope"] == "LOCAL_ARC_CONSISTENCY"


def test_bundle_does_not_link_by_record_id_across_different_sources():
    bundle = SimpleNamespace(
        definitions=(SimpleNamespace(entry_id="one"),),
        observations=(SimpleNamespace(entry_id="one", source="other", record_id="r", family="f", scope="lexical"),),
        assertions=(Assertion("A", 1, "source", "r", "f"),),
    )
    with pytest.raises(ValueError, match="UNRESOLVED_ASSERTION_LINK"):
        discover_bundle(bundle)


def test_bundle_rejects_ambiguous_links_instead_of_duplicating_definitions():
    bundle = SimpleNamespace(
        definitions=(SimpleNamespace(entry_id="one"), SimpleNamespace(entry_id="two")),
        observations=tuple(
            SimpleNamespace(entry_id=entry, source="s", record_id="r", family="f", scope="lexical")
            for entry in ("one", "two")
        ),
        assertions=(Assertion("A", 1, "s", "r", "f"),),
    )
    with pytest.raises(ValueError, match="UNRESOLVED_ASSERTION_LINK"):
        discover_bundle(bundle)


def test_exact_definition_join_meets_distinct_source_measurements():
    observations = (
        observation("one", "A", 1, source="left", family="taxonomy"),
        observation("one", "B", 0, source="right", family="lexical"),
        observation("two", "A", 1, source="left", family="taxonomy"),
    )
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),), cross_source=True)
    assert [r["entry_id"] for r in report.support] == ["one"]
    assert [r["entry_id"] for r in report.unknown] == ["two"]
    assert report.support[0]["source"] == "definition:one"
    assert {r["source"] for r in report.support[0]["observations"]} == {"left", "right"}
    assert report.by_family["taxonomy"]["support"] == report.by_family["lexical"]["support"] == 1
    assert report.relation.approved is False
    assert discover_relations(tuple(reversed(observations)), candidates=(("A", 1, "B", 0),), cross_source=True) == (
        report,
    )


def test_cross_source_disagreement_survives_repetition_and_weights():
    observations = (
        observation("one", "A", 1, source="left"),
        observation("one", "B", 0, source="right", record="zero1"),
        observation("one", "B", 0, source="right", record="zero2"),
        observation("one", "B", 1, source="other"),
    )
    (report,) = discover_relations(observations, {"one": 100000}, (("A", 1, "B", 0),), cross_source=True)
    assert report.support == report.counterexamples == ()
    assert report.conflicting[0]["consequent_values"] == (0, 1)
    assert len(report.conflicting[0]["observations"]) == 4


def test_cross_source_join_does_not_join_distinct_definitions():
    observations = (observation("same:1", "A", 1), observation("same:2", "B", 0, source="other"))
    (report,) = discover_relations(observations, candidates=(("A", 1, "B", 0),), cross_source=True)
    assert not report.support
    assert report.unknown[0]["entry_id"] == "same:1"
