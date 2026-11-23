"""A speculative journal can be reused only for the later exact real question."""

import importlib
import json
from dataclasses import asdict

from gse.curation.lexicon_builder.epoch import fingerprint, make_question
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.source_enrichment import FORMAT, enrich_sources
from gse.curation.lexicon_builder.wordnet_identity import wordnet_defining_context, wordnet_identity_observation

prefetch = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.prefetch_vertebrate_021")
pytest_plugins = ("test_lexicon_builder_defining_genus",)


def test_preview_is_identical_to_real_post_enrichment_question_and_never_writes_source(native, tmp_path):
    parser, synset, definition, bundle = native
    source, output = tmp_path / "source.db", tmp_path / "enriched.db"
    inputs = tmp_path / "context.json"
    build_dictionary(bundle, source)
    packet = wordnet_defining_context(parser, "man", synset)
    raw = json.loads(json.dumps([asdict(wordnet_identity_observation(packet, definition))]))
    before = fingerprint(source)
    [preview] = prefetch.prepare_requests(source, raw)
    assert fingerprint(source) == before
    inputs.write_text(json.dumps({"format": FORMAT, "observations": raw}))
    result = enrich_sources(source, output, inputs)
    actual = make_question(output, definition.entry_id, "BODY")
    assert result["bank_changes"] == 0
    assert preview.payload() == actual.payload()
    assert preview.request_id == actual.request_id
    assert preview.output_schema() == actual.output_schema()
    assert "BODY" not in actual.known and actual.allowed_values == (-1, 0, 1)
