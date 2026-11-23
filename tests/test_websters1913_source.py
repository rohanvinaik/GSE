"""Historical native definitions enter the ordinary typed source pipeline."""

import hashlib
import json
from dataclasses import asdict

import pytest

from GSE.curation.external_sources.source_scope import SOURCE_PRIMITIVE_SCOPE
from GSE.curation.external_sources.websters1913 import Websters1913Parser
from GSE.curation.lexicon_builder.evidence import collect_evidence, load_local_sources
from GSE.curation.lexicon_builder.model_evidence import FORMAT, evidence_view


def _snapshot(tmp_path, body):
    raw = body.encode()
    (tmp_path / "Auf.html").write_bytes(raw)
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "format": "GSE.websters1913-snapshots/1",
                "records": [
                    {
                        "native_id": "Auf",
                        "url": "https://www.websters1913.com/words/Auf",
                        "file": "Auf.html",
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "retrieved_utc": "2026-10-29T00:00:00+00:00",
                    }
                ],
            }
        )
    )
    return path


def test_all_native_definitions_keep_identity_and_no_signs(tmp_path):
    path = _snapshot(
        tmp_path,
        "<meaning><p><hw>Auf</hw>, <pos><i>n.</i></pos>"
        "[Also spelt oaf.] <def>A changeling.</def> <def>A simpleton.</def> [Obs.]</p></meaning>",
    )
    parser = Websters1913Parser(path)
    assert parser.load()
    entries = list(parser.get_definition_entries(("auf",)))
    assert [entry.definition for entry in entries] == ["A changeling.", "A simpleton."]
    assert len({entry.entry_id for entry in entries}) == 2
    assert all(entry.word == "Auf" and entry.lemma == "auf" and entry.pos == "noun" for entry in entries)
    assert all(
        "[Also spelt oaf.]" in entry.native_entry_text and "[Obs.]" in entry.native_entry_text for entry in entries
    )
    assert parser.to_primitives("auf") == parser.to_primitives_with_confidence("auf") == {}
    assert all(parser.to_primitives_for_entry(entry) == {} for entry in entries)
    assert SOURCE_PRIMITIVE_SCOPE["websters1913"] == set()
    bundle = collect_evidence({"websters1913": parser}, ("auf", "oaf"))
    assert len(bundle.definitions) == len(bundle.observations) == 2
    assert bundle.assertions == ()
    assert [d["lemma"] for d in bundle.unresolved if d["code"] == "NO_IDENTIFIED_DEFINITION"] == ["oaf"]
    view = evidence_view([asdict(observation) for observation in bundle.observations], "WANT")
    assert view["format"] == FORMAT
    for observation, record in zip(bundle.observations, view["records"]):
        assert record["features"]["definition"] == observation.features["definition"]
        assert record["features"]["native_entry_text"] == observation.features["native_entry_text"]
        assert record["scope"] == "lexical"
        assert record["omitted_fields"] == [
            {"field": "/features/source_html", "code": "SOURCE_MARKUP_NOT_INCLUDED_IN_DEFINITION_VIEW"}
        ]
    assert len(collect_evidence({"websters1913": parser}).definitions) == 2


@pytest.mark.parametrize(
    "body,code",
    [
        ("", "WEBSTERS_MISSING_NATIVE_MEANING"),
        ("<meaning><hw>Auf</hw><pos>n.</pos></meaning>", "WEBSTERS_MISSING_DEFINITION_IDENTITY"),
        ("<meaning><hw>Auf</hw><pos>n.</pos><def> </def></meaning>", "WEBSTERS_EMPTY_NATIVE_DEFINITION"),
        ("<meaning><hw>Auf</hw><pos>unknown</pos><def>Text.</def></meaning>", "WEBSTERS_MISSING_DEFINITION_IDENTITY"),
        ("<meaning><hw>Auf</hw>", "WEBSTERS_UNCLOSED_MEANING"),
    ],
)
def test_missing_or_malformed_native_definition_refuses(tmp_path, body, code):
    parser = Websters1913Parser(_snapshot(tmp_path, body))
    with pytest.raises(ValueError, match=f"^{code}$"):
        parser.load()
    assert not parser._loaded
    assert not parser.entries


def test_changed_snapshot_is_not_silently_used(tmp_path):
    path = _snapshot(tmp_path, "<meaning><hw>Auf</hw><pos>n.</pos><def>A child.</def></meaning>")
    (tmp_path / "Auf.html").write_text("changed source")
    with pytest.raises(ValueError, match="^WEBSTERS_SOURCE_HASH_MISMATCH$"):
        Websters1913Parser(path).load()


def test_registered_local_loader_loads_native_data_without_download(tmp_path, monkeypatch):
    from GSE.curation.external_sources import websters1913

    path = _snapshot(tmp_path, "<meaning><hw>Auf</hw><pos>n.</pos><def>A child.</def></meaning>")
    monkeypatch.setattr(websters1913, "WEBSTERS_MANIFEST", path)
    parsers, diagnostics = load_local_sources(("websters1913",))
    assert diagnostics == ({"source": "websters1913", "code": "LOADED", "words": 1, "native_records": 1},)
    assert collect_evidence(parsers, ("auf",)).definitions[0].definition == "A child."
    path.unlink()
    parsers, diagnostics = load_local_sources(("websters1913",))
    assert parsers == {}
    assert diagnostics[0]["code"] == "UNAVAILABLE"
    assert diagnostics[0]["reason"] == "MISSING_LOCAL_FILE"
