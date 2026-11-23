"""Rulebook fixtures for builder tests: admit or withhold named rules explicitly.

A test of construction mechanism states which rules it depends on. The live rulebook's own
review states are untouched; each helper returns a fresh copy for the test.
"""

from __future__ import annotations

from gse.lexicon_builder.core import rule_contract_digest
from gse.lexicon_builder.registry import RULE_FAMILIES, load_rulebook


def certify_rule(
    record: dict,
    *,
    positive: str = "tests/test_lexicon_unified_admission.py::test_admitting_the_same_source_rule_restores_every_path",
    must_not: str = "tests/test_lexicon_unified_admission.py::test_an_unadmitted_source_rule_writes_no_restriction_companion_or_fact",
) -> dict:
    """Explicit test-only receipt for a synthetic or deliberately altered rule.

    This is not a production review mechanism. Each caller owns the positive
    and must-not assertions for its altered contract; native associations still
    cannot acquire lexical authority through this helper.
    """
    record.update(
        review_state="SOURCE_JUSTIFIED",
        lifecycle="ACTIVE",
        tier=record.get("tier", "CONDITIONAL"),
        authority={"kind": "GSE_CONVENTION", "refs": ["TEST_FIXTURE_ONLY"]},
    )
    record.setdefault("warrant", "Test-only altered contract, not a production approval")
    record.setdefault("source_refs", ["TEST_FIXTURE_ONLY"])
    record["validation"] = {
        "status": "VALIDATED",
        "contract_sha256": rule_contract_digest(record),
        "positive": [positive],
        "must_not": [must_not],
    }
    return record


def _with_state(state: str, rule_ids: tuple[str, ...]) -> dict:
    book = load_rulebook()
    found = set()
    for family in RULE_FAMILIES:
        for rule in book.get(family, []):
            if rule["rule_id"] in rule_ids:
                if state == "VALIDATED_TEST_FIXTURE":
                    certify_rule(rule)
                else:
                    rule["review_state"] = state
                found.add(rule["rule_id"])
    if found != set(rule_ids):
        raise KeyError(f"unknown rule IDs: {sorted(set(rule_ids) - found)}")
    return book


def admitted_rulebook(*rule_ids: str) -> dict:
    """The live rulebook with explicit test-only receipts for the named rules."""
    return _with_state("VALIDATED_TEST_FIXTURE", rule_ids)


def withheld_rulebook(*rule_ids: str) -> dict:
    """The live rulebook with the named rules not admitted, for a MUST-NOT test only."""
    return _with_state("WITHHELD_FOR_TEST", rule_ids)
