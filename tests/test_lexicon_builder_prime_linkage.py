"""Complete primary-unit identity coverage without invented prime signatures."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest

from gse.curation.external_sources.nsm_chart import NSMChartParser
from gse.curation.external_sources.source_scope import SOURCE_PRIMITIVE_SCOPE
from gse.curation.lexicon_builder.catalog import (
    SOURCE,
    catalog_inventory,
    chart_definition_records,
    foundation_prime_links,
    native_foundation_words,
)
from gse.curation.lexicon_builder.evidence import collect_evidence, load_local_sources
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.model_evidence import evidence_view
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.validation import validate_build

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json"


def test_complete_link_inventory_preserves_known_identity_without_adding_anchors():
    links = foundation_prime_links()
    assert len(links) == 65
    assert set(links) == {unit["unit_id"] for unit in catalog_inventory()["units"]}
    entries = [entry for ids in links.values() for entry in ids]
    assert len(entries) == len(set(entries)) == 65
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["prime_entries"] == {key: list(value) for key, value in links.items()}
    standalone = json.loads((ROOT / "docs/program/LEXICON_APPROVED_PRIME_LINKS_2026-10-29.json").read_text())
    assert standalone["prime_entries"] == manifest["prime_entries"]
    assert len(manifest["anchors"]) == 5
    assert len(manifest["definitions"]) == 2
    assert links["nsm:v20:do"] == ("wordnet:do:perform.v.01",)
    assert links["nsm:v20:before"] == ("gse_closed_class:conjunction:before",)
    assert links["nsm:v20:be-somewhere"] != links["nsm:v20:be-someone-something"]


def test_chart_records_preserve_complete_boxes_and_unassigned_scope():
    boxes = {unit["unit_id"]: unit for unit in catalog_inventory()["units"]}
    records = chart_definition_records()
    assert len(records) == 29
    for record in records:
        box = boxes[record["unit_id"]]
        assert record["frame_text"] == box["frame_text"]
        assert record["forms"] == tuple(box["forms"])
        assert record["chart_heading"] == box["chart_heading"]
        assert record["source_reference"] == SOURCE
        assert record["frames_are"] == "COMBINATORIAL_NOT_OWN_WORD_ASSIGNMENTS"
        assert "assertions" not in record and "mapping" not in record
    by_unit = {record["unit_id"]: record for record in records}
    assert by_unit["nsm:v20:some-time"]["definition_kind"] == "GRAMMATICAL_CONSTRUCTION"
    assert by_unit["nsm:v20:good"]["definition_kind"] == "LEXICAL_UNIT"
    assert by_unit["nsm:v20:some-time"]["pos"] == "nsm_construction"
    # Fresh return values cannot mutate the primary inventory or later calls.
    records[0]["source_reference"]["version"] = "corrupted"
    assert chart_definition_records()[0]["source_reference"]["version"] == "v20"


def test_chart_adapter_declares_no_bank_authority_and_rejects_changed_source(monkeypatch):
    parser = NSMChartParser()
    assert parser.load()
    assert SOURCE_PRIMITIVE_SCOPE["nsm_chart"] == set()
    for word in parser.get_all_words():
        assert parser.to_primitives(word) == {}
        for entry in parser.get_entries(word):
            assert parser.to_primitives_for_entry(entry) == {}
    assert parser.get_entries("missing") == ()
    with pytest.raises(ValueError, match="UNKNOWN_NSM_CHART_DEFINITION"):
        parser.to_primitives_for_entry(None)  # ty: ignore[invalid-argument-type]
    monkeypatch.setitem(SOURCE, "sha256", "0" * 64)
    with pytest.raises(ValueError, match="NSM_CHART_SOURCE_REVISION_MISMATCH"):
        NSMChartParser().load()


def test_chart_collector_empty_requested_words_retains_mandatory_context():
    parsers, diagnostics = load_local_sources(("nsm_chart",))
    assert diagnostics[0]["mandatory_definitions"] == 29
    bundle = collect_evidence(parsers, ())
    assert len(bundle.definitions) == len(bundle.observations) == 29
    assert bundle.assertions == bundle.domain_restrictions == ()
    definitions = {definition.entry_id: definition for definition in bundle.definitions}
    for observation in bundle.observations:
        assert observation.entry_id is not None
        definition = definitions[observation.entry_id]
        assert definition.source_ids == (observation.record_id,)
        assert observation.candidate_entry_ids == (definition.entry_id,)
        assert observation.scope == "source_structure"
        assert observation.features["frame_text"]
        view = evidence_view([asdict(observation)], "GOOD")
        kept = view["records"][0]["features"]
        assert kept["frame_text"] == observation.features["frame_text"]
        assert kept["source_reference"] == observation.features["source_reference"]
        assert kept["definition_kind"] == observation.features["definition_kind"]
        assert not view["records"][0]["omitted_fields"]


def test_all_foundation_links_build_and_replay_with_native_sources(tmp_path):
    parsers, diagnostics = load_local_sources(("nsm_chart", "gse_closed_class", "wordnet_hierarchy"))
    assert all(diagnostic["code"] == "LOADED" for diagnostic in diagnostics)
    bundle = collect_evidence(parsers, ("extremely",))
    assert set(native_foundation_words()) <= {definition.lemma for definition in bundle.definitions}
    db = tmp_path / "lexicon.db"
    build_dictionary(bundle, db, manifest=MANIFEST)
    with sqlite3.connect(db) as conn:
        catalog = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='catalog'").fetchone()[0])
        assert catalog["readiness"]["all_units_linked"]
        assert not catalog["readiness"]["all_foundation_domains_resolved"]
        for record in chart_definition_records():
            state = conn.execute(
                "SELECT code,domains FROM definition_states WHERE entry_id=?", (record["entry_id"],)
            ).fetchone()
            assert state[0] == "PARTIAL"
            domains = json.loads(state[1])
            assert domains == {bank: [-1, 0, 1] for bank in BANKS}
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"
