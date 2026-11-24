"""The public pipeline must consume the same immutable definition checkpoint."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from GSE.api import GSEEncoder
from GSE.curation.lexicon_builder.evidence import collect_evidence, load_local_sources
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.pipeline_v2 import GSEPipeline


@pytest.fixture(scope="module")
def checkpoint(tmp_path_factory):
    path = tmp_path_factory.mktemp("pipeline-definition") / "checkpoint.db"
    manifest = Path(__file__).resolve().parents[1] / "docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json"
    parsers, _ = load_local_sources(("gse_closed_class", "nsm_chart", "wordnet_hierarchy"))
    build_dictionary(collect_evidence(parsers, words=("extremely",)), path, manifest=manifest)
    return path


def test_load_and_sentence_delegate_without_translator_or_database_mutation(checkpoint, monkeypatch):
    before = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

    def no_ddl(*args, **kwargs):
        raise AssertionError("Definition stores cannot enter the legacy translator")

    monkeypatch.setattr("GSE.pipeline_v2.SQLiteMerkleTranslator", no_ddl)
    pipeline = GSEPipeline(str(checkpoint))
    try:
        with GSEEncoder(checkpoint) as encoder:
            expected = encoder.encode("He is not very happy.")
        actual = pipeline.encode_sentence("He is not very happy.", with_trace=True)
        assert actual.trace.to_dict() == expected.to_dict()
        assert np.array_equal(actual.vector, expected.vector.to_dense())
        assert actual.words == [token.token for token in expected.tokens]
        assert pipeline.encode_sentence("He is happy.").trace is None
        assert pipeline.encode_sentence("He is happy.", include_word_vectors=False).word_vectors == []
        assert pipeline.verify_integrity() == (True, [])
        assert pipeline.get_statistics()["lexicon"]["read_only"]
        with pytest.raises(PermissionError):
            pipeline.save_lexicon()
        with pytest.raises(PermissionError):
            pipeline.add_word("fake", "n", [("GOOD", "", 1)])
    finally:
        pipeline.close()
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == before


def test_exact_definition_and_ambiguous_word_are_not_interchanged(checkpoint):
    pipeline = GSEPipeline(str(checkpoint))
    try:
        result = pipeline.decompose_word("this", "PRON", entry_id="gse:prime:this")
        assert result.source == "lexicon"
        assert result.lexical_evidence["selected_record"]["entry_id"] == "gse:prime:this"
        with GSEEncoder(checkpoint) as encoder:
            expected = encoder.encode_definition("gse:prime:this")
        assert result.vector.cosine(expected) == pytest.approx(1)
        assert pipeline.encode_word("this", entry_id="gse:prime:this").cosine(expected) == pytest.approx(1)
        assert pipeline.get_lexeme("gse:prime:this")["entry_id"] == "gse:prime:this"
        assert pipeline.get_lexeme("this") is None
        missing = pipeline.decompose_word("unattested-spelling", "n")
        assert missing.source == "unknown" and missing.vector is None
        assert missing.lexical_evidence["selection_status"] == "NOT_FOUND"
        assert pipeline.find_similar("unattested-spelling").matches == []
        matches = pipeline.find_similar(expected, top_k=3)
        assert matches.matches
        assert matches.route_info["identity_selection"] is False
        assert all(key.isdigit() for key, score in matches.matches)
        records = list(pipeline.iter_lexemes())
        assert len(records) == pipeline.get_statistics()["lexicon"]["total_lexemes"]
    finally:
        pipeline.close()
