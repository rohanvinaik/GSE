"""Exact genus context reaches both writers without assigning unknown banks."""

import copy
import json
import sqlite3
from dataclasses import asdict

import pytest

from GSE.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser
from GSE.curation.lexicon_builder.engine import propagate
from GSE.curation.lexicon_builder.evidence import EvidenceBundle, collect_evidence
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.model_batch import OllamaBatchTransport
from GSE.curation.lexicon_builder.model_evidence import restore_candidate_links
from GSE.curation.lexicon_builder.model_protocol import model_input
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.residual import OllamaTransport, build_request
from GSE.curation.lexicon_builder.source_enrichment import FORMAT
from GSE.curation.lexicon_builder.wordnet_identity import (
    DEFINING_CONTEXT_FORMAT,
    validate_wordnet_identity,
    wordnet_defining_context,
    wordnet_identity_evidence,
    wordnet_identity_observation,
)
from scripts import enrich_lexicon_sources


@pytest.fixture(scope="module")
def native():
    from nltk.corpus import wordnet

    try:
        wordnet.ensure_loaded()
    except LookupError:
        pytest.skip("Requires the existing local WordNet source")
    parser = WordNetHierarchyParser()
    assert parser.load()
    bundle = collect_evidence({"wordnet_hierarchy": parser}, ("man",))
    identity = "wordnet:man:homo.n.02"
    definition = next(d for d in bundle.definitions if d.entry_id == identity)
    subset = EvidenceBundle(
        (definition,),
        tuple(r for r in bundle.observations if r.record_id == identity),
        tuple(a for a in bundle.assertions if a.record_id == identity),
        (),
    )
    return parser, wordnet.synset("homo.n.02"), definition, subset


def test_complete_ancestry_is_context_only_and_legacy_packet_stays_reproducible(native):
    parser, synset, definition, _ = native
    legacy = wordnet_identity_evidence(parser, "man", synset, pos="noun")
    packet = wordnet_defining_context(parser, "man", synset, pos="noun")
    assert packet["format"] == DEFINING_CONTEXT_FORMAT
    assert packet["assigns_banks"] is False and packet["selects_sense"] is False
    assert "skeleton" in packet["defining_ancestry"]["synsets"]["vertebrate.n.01"]["definition"]
    assert all(path[-1] == "homo.n.02" for path in packet["defining_ancestry"]["paths"])
    assert validate_wordnet_identity(packet, definition) == packet
    assert wordnet_identity_evidence(parser, "man", synset, pos="noun") == legacy
    assert "defining_ancestry" not in legacy


@pytest.mark.parametrize("fault", ["missing", "cycle", "foreign_root", "extra_witness", "malformed", "bank_transfer"])
def test_ancestry_refuses_missing_cyclic_foreign_or_malformed_context(native, fault):
    parser, synset, definition, _ = native
    packet = wordnet_defining_context(parser, "man", synset)
    ancestry = packet["defining_ancestry"]
    if fault == "missing":
        del ancestry["synsets"]["vertebrate.n.01"]
    elif fault == "cycle":
        ancestry["paths"][0].insert(0, "homo.n.02")
    elif fault == "foreign_root":
        ancestry["paths"][0][-1] = "vertebrate.n.01"
    elif fault == "extra_witness":
        ancestry["synsets"]["foreign.n.01"] = copy.deepcopy(packet["native_synset"])
    elif fault == "malformed":
        ancestry["synsets"]["vertebrate.n.01"]["definition"] = None
    else:
        packet["assigns_banks"] = True
    with pytest.raises(ValueError):
        validate_wordnet_identity(packet, definition)


def test_both_writer_views_keep_genus_witness_and_unknown_target(native):
    parser, synset, definition, bundle = native
    packet = wordnet_defining_context(parser, "man", synset)
    observation = wordnet_identity_observation(packet, definition)
    state = propagate(BANKS, bundle.assertions, ())
    observations = tuple(asdict(o) for o in (*bundle.observations, observation))
    request = build_request(definition.entry_id, "BODY", state, observations, definition=definition)
    original = copy.deepcopy(request.payload())
    wire = model_input(original)
    base = OllamaTransport("fixture", thinking=False, output_tokens=256, context_tokens=65536)
    batch = OllamaBatchTransport(base, max_items=2).prepare(((original, request.output_schema()),))
    batch_wire = json.loads(json.loads(batch.body)["prompt"])
    assert batch_wire["items"][0]["coordinate"] == wire["coordinate"]
    assert batch_wire["items"][0]["input"] == wire["input"]
    records = restore_candidate_links(wire["input"]["evidence"])["records"]
    context = next(r for r in records if "definition_identity" in r["features"])
    assert context["features"]["definition_identity"]["defining_ancestry"] == packet["defining_ancestry"]
    assert wire["coordinate"]["scope_convention"]["positive_sufficient"]["authority"] == "FOUNDER_APPROVED"
    assert request.allowed_values == (-1, 0, 1) and "BODY" not in request.known
    assert request.output_schema()["required"] == ["BODY"]
    assert request.payload() == original


def test_real_enrichment_cli_rechecks_native_genus_and_preserves_all_cells(native, tmp_path, monkeypatch):
    parser, synset, definition, bundle = native
    source, output = tmp_path / "source.db", tmp_path / "enriched.db"
    inputs, report = tmp_path / "input.json", tmp_path / "report.json"
    build_dictionary(bundle, source)
    packet = wordnet_defining_context(parser, "man", synset)
    inputs.write_text(json.dumps({"format": FORMAT, "observations": [asdict(wordnet_identity_observation(packet, definition))]}))
    monkeypatch.setattr("sys.argv", ["enrich", "--candidate", str(source), "--output", str(output), "--input", str(inputs), "--report", str(report)])
    assert enrich_lexicon_sources.main() == 0
    result = json.loads(report.read_text())
    assert result["bank_changes"] == 0 and result["preexisting_state_unchanged"] is True
    with sqlite3.connect(output) as conn:
        assert json.loads(conn.execute("SELECT domains FROM definition_states").fetchone()[0])["BODY"] == [-1, 0, 1]
    # This is structurally valid and has a freshly computed observation digest.
    # The real native-source verifier must still refuse its fabricated meaning.
    packet["defining_ancestry"]["synsets"]["vertebrate.n.01"]["definition"] = "fabricated defining genus"
    inputs.write_text(json.dumps({"format": FORMAT, "observations": [asdict(wordnet_identity_observation(packet, definition))]}))
    forged = tmp_path / "forged.db"
    monkeypatch.setattr("sys.argv", ["enrich", "--candidate", str(source), "--output", str(forged), "--input", str(inputs), "--report", str(tmp_path / "forged.json")])
    with pytest.raises(ValueError, match="SOURCE_IDENTITY_MISMATCH"):
        enrich_lexicon_sources.main()
    assert not forged.exists()
