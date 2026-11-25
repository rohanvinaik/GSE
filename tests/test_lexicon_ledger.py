"""The promotion gate for type-guarded lexical rules is computed from stated facts only."""

from GSE.curation.lexicon_builder.ledger import (
    ADMISSIBLE,
    EXCEEDS_REVIEWED,
    FINDING,
    NO_REACH,
    SPECIALIZED,
    UNCONFIRMED,
    impute_guard_candidates,
    verdict,
)


def test_guard_is_shared_by_every_confirming_and_held_by_no_contradicting_definition():
    confirming = [frozenset({"group", "gathering", "crowd"}), frozenset({"group", "gathering", "party"})]
    contradicting = [frozenset({"group", "organization", "airline"})]
    assert impute_guard_candidates(confirming, contradicting) == ("gathering",)


def test_no_guard_without_both_witness_sets_or_without_a_separating_type():
    assert impute_guard_candidates([frozenset({"a"})], []) == ()
    assert impute_guard_candidates([frozenset({"a", "b"})], [frozenset({"a", "b"})]) == ()


def test_verdicts():
    assert verdict(0, 0, 50, (), False) == UNCONFIRMED
    assert verdict(3, 0, 50, (), False) == ADMISSIBLE
    assert verdict(3, 0, 0, (), False) == NO_REACH
    assert verdict(3, 2, 50, ("gathering",), False) == SPECIALIZED
    assert verdict(3, 2, 50, (), False) == FINDING
    assert verdict(3, 0, 50, (), True) == EXCEEDS_REVIEWED


def test_reviewed_implication_tables_are_read_mechanically():
    from GSE.curation.lexicon_builder.stated_channels import implication

    rows = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if x != 1 or y == 1]
    assert implication({"banks": ["SOMETHING", "BE"], "allowed_rows": rows}) == (("SOMETHING", 1), ("BE", 1))
    assert implication({"banks": ["WHEN"], "allowed_rows": [[1]]}) == (None, ("WHEN", 1))
    assert implication({"banks": ["A", "B"], "allowed_rows": [[0, 0], [1, 1]]}) is None
