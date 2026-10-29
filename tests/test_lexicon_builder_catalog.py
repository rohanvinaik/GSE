"""A primary inventory is compiler input, not automatic lexical authority."""

import hashlib
import json
from pathlib import Path

import pytest

from gse.curation.lexicon_builder.catalog import SOURCE, catalog_inventory, catalog_report
from gse.curation.lexicon_builder.engine import Assertion, Relation
from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.foundation import BANKS, projection_relations


def test_inventory_preserves_every_chart_box_and_notes_exactly():
    inventory = catalog_inventory()
    units = inventory["units"]
    assert len(units) == len({unit["unit_id"] for unit in units}) == 65
    reconstructed = "".join(unit["chart_heading"] + "\n" + unit["frame_text"] + "\n" for unit in units)
    reconstructed += inventory["chart_notes"]
    source = Path(__file__).resolve().parents[1] / SOURCE["path"]
    assert reconstructed == source.read_text()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE["sha256"]
    assert all(unit["mapping"]["assignment_approved"] is False for unit in units)
    assert all(unit["mapping"]["bank"] is None or unit["mapping"]["bank"] in BANKS for unit in units)
    json.dumps(inventory, allow_nan=False)


def test_chart_polysemy_and_allolexes_are_not_flat_lemmas():
    units = {unit["unit_id"]: unit for unit in catalog_inventory()["units"]}
    assert units["nsm:v20:i"]["forms"] == ["I", "ME"]
    assert units["nsm:v20:place"]["forms"] == ["PLACE", "WHERE", "SOMEWHERE"]
    assert units["nsm:v20:be-somewhere"]["unit_id"] != units["nsm:v20:be-someone-something"]["unit_id"]
    assert units["nsm:v20:this"]["mapping"]["code"] == "MISSING"
    assert units["nsm:v20:dont-want"]["mapping"]["code"] == "MISSING"
    assert units["nsm:v20:some-time"]["mapping"]["code"] == "MISSING"
    assert units["nsm:v20:die"]["mapping"]["code"] == "ADAPTED"
    assert units["nsm:v20:more"]["mapping"]["code"] == "METADATA"


def test_returned_inventory_is_independent():
    inventory = catalog_inventory()
    inventory["units"][0]["mapping"]["bank"] = "FORGED"
    inventory["units"][0]["forms"].clear()
    inventory["source"]["version"] = "forged"
    fresh = catalog_inventory()
    assert fresh["units"][0]["mapping"]["bank"] == "I"
    assert fresh["units"][0]["forms"] == ["I", "ME"]
    assert fresh["source"]["version"] == "v20"


def test_spelling_and_even_existing_anchors_do_not_link_prime_identity():
    definition = Definition("dictionary:good", "good", "adj", "a designated adjective meaning")
    anchors = {definition.entry_id: (Assertion("GOOD", 1, "declared", "source:good", "anchor"),)}
    report = catalog_report(anchors, (definition,), projection_relations())
    assert report["coverage_counts"] == {"UNLINKED": 65}
    assert report["readiness"]["all_units_linked"] is False


def test_explicit_prime_link_replays_non_one_hot_closure_and_keeps_unknowns():
    definition = Definition("dictionary:good", "good", "adj", "a designated adjective meaning")
    anchors = {definition.entry_id: (Assertion("GOOD", 1, "declared", "source:good", "anchor"),)}
    report = catalog_report(
        anchors, (definition,), projection_relations(), prime_entries={"nsm:v20:good": (definition.entry_id,)}
    )
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")
    assert unit["code"] == "PARTIAL_ANCHOR_CLOSURE"
    record = unit["definitions"][0]
    assert record["assignments"] == {"GOOD": 1, "BIG": 0, "SOMETHING": 0}
    assert "THINK" in record["unresolved_banks"]
    assert record["gold"] == "NOT_CHECKED"
    assert report["readiness"]["founder_signature_completeness"] == "NOT_ESTABLISHED"
    json.dumps(report, allow_nan=False)


def test_rules_alone_are_not_declared_prime_anchors():
    definition = Definition("definition:good", "good", "adj", "a designated adjective meaning")
    report = catalog_report(
        {}, (definition,), projection_relations(), prime_entries={"nsm:v20:good": (definition.entry_id,)}
    )
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")
    assert unit["code"] == "MISSING_DECLARED_ANCHORS"
    assert unit["definitions"][0]["code"] == "NO_DECLARED_ANCHORS"


def test_conflict_has_no_published_catalog_assignments():
    definition = Definition("definition:good", "good", "noun", "a deliberately conflicting test meaning")
    anchors = {definition.entry_id: (Assertion("GOOD", 1, "declared", "source:good", "anchor"),)}
    report = catalog_report(
        anchors, (definition,), projection_relations(), prime_entries={"nsm:v20:good": (definition.entry_id,)}
    )
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")
    assert unit["code"] == "CONFLICT"
    assert unit["definitions"][0]["assignments"] == {}


def test_resolved_domains_do_not_imply_semantic_gold_correctness():
    definition = Definition("definition:good", "good", "adj", "a deliberately complete but unvalidated test vector")
    assertions = tuple(
        Assertion(bank, 1 if bank == "GOOD" else 0, "declared", f"source:{bank}", "anchor") for bank in BANKS
    )
    report = catalog_report(
        {definition.entry_id: assertions},
        (definition,),
        projection_relations(),
        prime_entries={"nsm:v20:good": (definition.entry_id,)},
    )
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")
    assert unit["code"] == "RESOLVED_ANCHOR_CLOSURE"
    assert report["readiness"]["code"] == "SEMANTIC_FOUNDATION_NOT_VALIDATED"
    assert report["readiness"]["gold"] == "NOT_CHECKED"
    assert report["complete_search"] is False


@pytest.mark.parametrize(
    "links,code",
    [
        ({"not-a-unit": ("entry",)}, "UNKNOWN_CATALOG_UNIT"),
        ({"nsm:v20:good": ("missing",)}, "UNKNOWN_CATALOG_DEFINITION"),
        ({"nsm:v20:good": "entry"}, "UNKNOWN_CATALOG_DEFINITION"),
        ({"nsm:v20:good": ("entry", "entry")}, "AMBIGUOUS_CATALOG_DEFINITION"),
        ({"nsm:v20:good": ("entry",), "nsm:v20:bad": ("entry",)}, "AMBIGUOUS_CATALOG_DEFINITION"),
    ],
)
def test_unknown_and_ambiguous_definition_links_are_rejected(links, code):
    with pytest.raises(ValueError, match=code):
        catalog_report({}, (Definition("entry", "good", "adj", "test meaning"),), (), prime_entries=links)


def test_unapproved_relations_cannot_create_prime_coverage():
    definition = Definition("entry", "good", "adj", "test meaning")
    anchors = {"entry": (Assertion("GOOD", 1, "declared", "source:good", "anchor"),)}
    relation = Relation("candidate:think", ("THINK",), ((1,),), ("candidate",), "candidate", False)
    report = catalog_report(anchors, (definition,), (relation,), prime_entries={"nsm:v20:good": ("entry",)})
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")
    assert "THINK" in unit["definitions"][0]["unresolved_banks"]


def test_distinct_allolex_definitions_can_be_explicitly_linked():
    definitions = (
        Definition("i:prime", "i", "pronoun", "first person"),
        Definition("me:prime", "me", "pronoun", "first person"),
    )
    report = catalog_report({}, definitions, (), prime_entries={"nsm:v20:i": tuple(d.entry_id for d in definitions)})
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:i")
    assert [record["entry_id"] for record in unit["definitions"]] == ["i:prime", "me:prime"]


def test_basis_audit_separates_ordinary_coordinates_markers_and_meta_number():
    from gse.curation.lexicon_builder.catalog import basis_audit

    audit = basis_audit()
    assert audit["legacy_schema_symbols"] == 72
    assert audit["bipolar_pairs"] == 14
    assert audit["legacy_collapsed_coordinates"] == 58
    assert audit["collapsed_count_equation"] == {"ordinary": 56, "hierarchy": 2, "total": 58}
    assert audit["ordinary_lexical_coordinates"] == 56
    assert audit["runtime_registry_symbols"] == 73
    assert audit["runtime_only_symbols"] == ["NUMBER"]
    assert audit["number"]["classification"] == "META"
    assert audit["number"]["ordinary_coordinate"] is False
    assert audit["build_basis_matches_ordinary_collapsed_schema"] is True


def test_proposal_template_exposes_all_unit_decisions_without_assigning_cells():
    from gse.curation.lexicon_builder.catalog import proposal_template

    template = proposal_template()
    assert template["code"] == "REVIEW_TEMPLATE_UNAPPROVED"
    assert len(template["entries"]) == 65
    for entry in template["entries"]:
        assert entry["approved"] is False
        assert entry["definition_ids"] == entry["proposed_assertions"] == entry["proposed_relations"] == []
        assert set(entry["bank_values"]) == set(BANKS)
        assert set(entry["bank_values"].values()) == {None}
        assert len(entry["undefined_decisions"]) == 6
        assert all(
            decision["status"] == "UNDECIDED" and decision["answer"] is None
            for decision in entry["undefined_decisions"]
        )
        assert entry["mapping_candidate"]["assignment_approved"] is False
    json.dumps(template, allow_nan=False)


def test_catalog_replays_conditional_exception_instead_of_hard_conflict():
    definition = Definition("entry", "good", "adj", "test meaning")
    anchors = {"entry": (Assertion("GOOD", 1, "declared", "source:good", "anchor"),)}
    conditional = Relation("conditional:good-zero", ("GOOD",), ((0,),), ("reviewed",), "conditional", True)
    report = catalog_report(
        anchors, (definition,), projection_relations() + (conditional,), prime_entries={"nsm:v20:good": ("entry",)}
    )
    unit = next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")
    assert unit["code"] == "PARTIAL_ANCHOR_CLOSURE"
    assert unit["definitions"][0]["assignments"]["GOOD"] == 1
    assert unit["definitions"][0]["conditional_exceptions"][0]["rule_ids"] == ("conditional:good-zero",)
