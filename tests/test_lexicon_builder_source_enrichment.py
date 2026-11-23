"""Source-only successors preserve every existing cell and receipt boundary."""

import json
import sqlite3
from dataclasses import asdict, replace

import pytest

from GSE.curation.external_sources.wiktionary import WiktionaryParser
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.evidence import collect_evidence
from GSE.curation.lexicon_builder.model_protocol import model_input
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.source_enrichment import FORMAT, _refuse_bound_receipts, enrich_sources
from GSE.curation.lexicon_builder.storage import read_entries
from GSE.curation.lexicon_builder.validation import validate_build
from scripts.enrich_lexicon_sources import main


def fixture(tmp_path, *, other=False):
    from GSE.curation.lexicon_builder.evidence import native_reference_observation

    source = tmp_path / "dictionary.jsonl"
    source.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "word": "IT",
                    "pos": "adj",
                    "lang": "English",
                    "lang_code": "en",
                    "senses": [
                        {
                            "id": "it-adj",
                            "glosses": ["Initialism of intrathecal."],
                            "alt_of": [{"word": "intrathecal"}],
                            "tags": ["abbreviation", "alt-of"],
                        }
                    ],
                },
                {
                    "word": "intrathecal",
                    "pos": "adj",
                    "lang": "English",
                    "lang_code": "en",
                    "senses": [{"id": "intrathecal-adj", "glosses": ["Delivered into the spinal canal."]}],
                },
            ]
        )
        + "\n"
    )
    if other:
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "word": "other",
                        "pos": "adj",
                        "lang": "English",
                        "lang_code": "en",
                        "senses": [{"id": "other-adj", "glosses": ["A different one."]}],
                    }
                )
                + "\n"
            )
    parser = WiktionaryParser(data_path=source)
    assert parser.load()
    entries = tuple(parser.get_definition_entries(("IT",)))
    observation = native_reference_observation(dict(parser.get_definition_references(entries)[0]))
    bundle = collect_evidence({"wiktionary": parser}, ("it", "other") if other else ("it",))
    # Reconstruct a pre-enrichment candidate through the real builder.
    original = replace(
        bundle,
        observations=tuple(record for record in bundle.observations if "native_reference" not in record.features),
    )
    candidate = tmp_path / "candidate.db"
    build_dictionary(original, candidate)
    input_path = tmp_path / "input.json"
    raw = {"format": FORMAT, "observations": [asdict(observation)]}
    input_path.write_text(json.dumps(raw))
    return candidate, source, input_path, observation.entry_id


class Capture:
    identity = "synthetic-source-enrichment-test"

    def __init__(self, value=1):
        self.requests = []
        self.value = value

    def __call__(self, payload, schema):
        self.requests.append(payload)
        return json.dumps({payload["bank"]: self.value})


def states(path):
    with sqlite3.connect(path) as conn:
        return read_entries(conn)


def test_real_cli_preserves_all_cells_and_writer_receives_expansion(tmp_path, monkeypatch):
    candidate, native, input_path, entry = fixture(tmp_path)
    output, report_path = tmp_path / "successor.db", tmp_path / "report.json"
    before, old_states = candidate.read_bytes(), states(candidate)
    monkeypatch.setattr(
        "sys.argv",
        [
            "enrich",
            "--candidate",
            str(candidate),
            "--output",
            str(output),
            "--input",
            str(input_path),
            "--report",
            str(report_path),
            "--wiktionary-source",
            str(native),
        ],
    )
    assert main() == 0
    report = json.loads(report_path.read_text())
    assert report["code"] == "ENRICHED_CANDIDATE"
    assert report["preexisting_state_unchanged"] is True
    assert report["bank_changes"] == 0
    assert report["added_records"] == 1
    assert report["postflight"]["code"] == "REPLAY_VALIDATED"
    assert candidate.read_bytes() == before
    assert states(output) == old_states
    assert old_states[0]["domains"]["BODY"] == [-1, 0, 1]
    transport = Capture()
    result = complete_dictionary(output, transport, 1, entry_ids=(entry,), banks=("BODY",))
    assert result["outcomes"] == {"ASSIGNED": 1}
    request = transport.requests[0]
    reference = next(record for record in request["observations"] if "native_reference" in record["features"])
    assert (
        reference["features"]["native_reference"]["target_entries"][0]["definition"]
        == "Delivered into the spinal canal."
    )
    typed = model_input(request)
    assert "Delivered into the spinal canal." in json.dumps(typed)
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"
    assert states(output)[0]["domains"]["WANT"] == old_states[0]["domains"]["WANT"]


def test_existing_model_receipt_requires_explicit_reconsideration(tmp_path):
    candidate, native, input_path, entry = fixture(tmp_path)
    complete_dictionary(candidate, Capture(), 1, entry_ids=(entry,), banks=("BODY",))
    before = candidate.read_bytes()
    output = tmp_path / "refused.db"
    with pytest.raises(ValueError, match="REQUIRES_MODEL_RECONSIDERATION"):
        enrich_sources(candidate, output, input_path, wiktionary_source=native)
    assert candidate.read_bytes() == before
    assert not output.exists()
    assert not list(tmp_path.glob(".gse-enrichment-*"))


def test_unrelated_model_zero_and_receipt_survive_enrichment_exactly(tmp_path):
    from GSE.curation.lexicon_builder.model_receipts import read_model_receipts

    candidate, native, input_path, entry = fixture(tmp_path, other=True)
    unrelated = next(row["entry_id"] for row in states(candidate) if row["lemma"] == "other")
    complete_dictionary(candidate, Capture(0), 1, entry_ids=(unrelated,), banks=("BODY",))
    before = states(candidate)
    with sqlite3.connect(candidate) as conn:
        old_receipt = tuple(read_model_receipts(conn)[unrelated])
    output = tmp_path / "new.db"
    result = enrich_sources(candidate, output, input_path, wiktionary_source=native)
    assert result["postflight"]["code"] == "REPLAY_VALIDATED"
    assert states(output) == before
    by_id = {row["entry_id"]: row for row in states(output)}
    assert by_id[entry]["domains"]["BODY"] == [-1, 0, 1]
    assert by_id[unrelated]["domains"]["BODY"] == [0]
    with sqlite3.connect(output) as conn:
        assert tuple(read_model_receipts(conn)[unrelated]) == old_receipt


@pytest.mark.parametrize(
    "value", [None, {}, {"format": FORMAT, "observations": []}, {"format": FORMAT, "observations": [None]}]
)
def test_malformed_input_never_installs_output(tmp_path, value):
    candidate, native, input_path, _ = fixture(tmp_path)
    input_path.write_text(json.dumps(value))
    before = candidate.read_bytes()
    with pytest.raises(ValueError):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)
    assert candidate.read_bytes() == before
    assert not (tmp_path / "new.db").exists()


def test_valid_packet_from_different_snapshot_cannot_enrich_candidate(tmp_path):
    candidate, native, input_path, _ = fixture(tmp_path)
    native.write_text(native.read_text() + "\n")
    with pytest.raises(ValueError, match="SOURCE_ROOT_MISMATCH"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)
    assert not (tmp_path / "new.db").exists()


def test_self_consistent_missing_target_packet_is_refused_against_native_source(tmp_path):
    from GSE.curation.lexicon_builder.evidence import native_reference_observation

    candidate, native, input_path, _ = fixture(tmp_path)
    raw = json.loads(input_path.read_text())
    packet = raw["observations"][0]["features"]["native_reference"]
    packet["target_entries"] = []
    packet["code"] = "TARGET_NOT_FOUND"
    raw["observations"] = [asdict(native_reference_observation(packet))]
    input_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="SOURCE_REFERENCE_MISMATCH"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)
    assert not (tmp_path / "new.db").exists()


def test_forged_observation_envelope_cannot_widen_scope(tmp_path):
    candidate, native, input_path, _ = fixture(tmp_path)
    raw = json.loads(input_path.read_text())
    raw["observations"][0]["candidate_entry_ids"].append("some-other-definition")
    input_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="NATIVE_REFERENCE_OBSERVATION_MISMATCH"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)


def test_wrong_digest_and_missing_source_refuse(tmp_path):
    candidate, native, input_path, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match="SOURCE_REQUIRED"):
        enrich_sources(candidate, tmp_path / "new.db", input_path)
    raw = json.loads(input_path.read_text())
    raw["observations"][0]["record_id"] = "forged-id"
    input_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="NATIVE_REFERENCE_OBSERVATION_MISMATCH"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)


@pytest.mark.parametrize("kind", ["same", "existing", "symlink", "dangling"])
def test_existing_outputs_and_symlinks_are_refused(tmp_path, kind):
    candidate, native, input_path, _ = fixture(tmp_path)
    output = tmp_path / "new.db"
    if kind == "same":
        output = candidate
    elif kind == "existing":
        output.write_bytes(b"keep")
    else:
        output.symlink_to(candidate if kind == "symlink" else tmp_path / "absent.db")
    with pytest.raises(ValueError, match="OUTPUT_MUST_BE_NEW"):
        enrich_sources(candidate, output, input_path, wiktionary_source=native)


def test_rule_migration_archives_also_bind_old_context(tmp_path):
    candidate, _, _, entry = fixture(tmp_path)
    with sqlite3.connect(candidate) as conn:
        conn.execute("CREATE TABLE rule_migrations (event_id TEXT, payload TEXT)")
        conn.execute(
            "INSERT INTO rule_migrations VALUES (?,?)",
            ("test", json.dumps({"archived": [{"definition": {"entry_id": entry}}]})),
        )
        with pytest.raises(ValueError, match="RULE_ARCHIVE_CONTEXT_BOUND"):
            _refuse_bound_receipts(conn, {entry})


def test_failed_postflight_never_installs_successor(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import source_enrichment

    candidate, native, input_path, _ = fixture(tmp_path)
    actual = source_enrichment.validate_build
    calls = []

    def fail_second(path):
        calls.append(path)
        report = actual(path)
        if len(calls) == 2:
            report = {**report, "code": "REPLAY_MISMATCH", "mismatch_counts": {"synthetic-failure": 1}}
        return report

    monkeypatch.setattr(source_enrichment, "validate_build", fail_second)
    before = candidate.read_bytes()
    with pytest.raises(ValueError, match="POST_REPLAY_FAILED"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)
    assert candidate.read_bytes() == before
    assert not (tmp_path / "new.db").exists()
    assert not list(tmp_path.glob(".gse-enrichment-*"))


def test_trigger_side_effect_cannot_change_any_preexisting_state(tmp_path):
    candidate, native, input_path, _ = fixture(tmp_path)
    with sqlite3.connect(candidate) as conn:
        conn.execute(
            "CREATE TRIGGER malicious AFTER INSERT ON source_observations "
            "BEGIN UPDATE lexemes SET gloss='changed by a trigger'; END"
        )
    before = candidate.read_bytes()
    with pytest.raises(ValueError, match="CHANGED_EXISTING_STATE"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)
    assert candidate.read_bytes() == before
    assert not (tmp_path / "new.db").exists()


def test_active_candidate_is_refused_even_through_hardlink(tmp_path, monkeypatch):
    import os

    from GSE import lexicon_resource

    candidate, native, input_path, _ = fixture(tmp_path)
    active = tmp_path / "active.db"
    os.link(candidate, active)
    monkeypatch.setattr(lexicon_resource, "resolve_lexicon_path", lambda: active)
    with pytest.raises(ValueError, match="MUST_NOT_BE_ACTIVE"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)


def test_duplicate_packet_is_refused_before_copy(tmp_path):
    candidate, native, input_path, _ = fixture(tmp_path)
    raw = json.loads(input_path.read_text())
    raw["observations"].append(raw["observations"][0])
    input_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="DUPLICATE_ENRICHMENT_OBSERVATION"):
        enrich_sources(candidate, tmp_path / "new.db", input_path, wiktionary_source=native)
    assert not list(tmp_path.glob(".gse-enrichment-*"))


def test_cli_report_cannot_alias_native_source(tmp_path, monkeypatch):
    candidate, native, input_path, _ = fixture(tmp_path)
    output = tmp_path / "new.db"
    monkeypatch.setattr(
        "sys.argv",
        [
            "enrich",
            "--candidate",
            str(candidate),
            "--output",
            str(output),
            "--input",
            str(input_path),
            "--report",
            str(native),
            "--wiktionary-source",
            str(native),
        ],
    )
    before = native.read_bytes()
    with pytest.raises(ValueError, match="REPORT_MUST_BE_NEW"):
        main()
    assert native.read_bytes() == before
    assert not output.exists()


def test_real_wordnet_exception_context_is_verified_without_assigning_a_bank(tmp_path):
    from nltk.corpus import wordnet

    from GSE.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser
    from GSE.curation.lexicon_builder.evidence import EvidenceBundle
    from GSE.curation.lexicon_builder.wordnet_identity import wordnet_identity_evidence, wordnet_identity_observation

    try:
        wordnet.ensure_loaded()
    except LookupError:
        pytest.skip("This source verification test requires the existing local WordNet cache")
    parser = WordNetHierarchyParser()
    assert parser.load()
    bundle = collect_evidence({"wordnet_hierarchy": parser}, ("is",))
    entry = "wordnet:is:embody.v.02"
    definition = next(record for record in bundle.definitions if record.entry_id == entry)
    original = EvidenceBundle(
        (definition,),
        tuple(record for record in bundle.observations if record.record_id == entry),
        tuple(record for record in bundle.assertions if record.record_id == entry),
        (),
    )
    candidate, output, input_path = (tmp_path / name for name in ("source.db", "new.db", "identity.json"))
    build_dictionary(original, candidate)
    packet = wordnet_identity_evidence(parser, "is", wordnet.synset("embody.v.02"), pos="verb")
    assert packet["code"] == "EXCEPTION_DERIVED"
    observation = wordnet_identity_observation(packet, definition)
    raw = {"format": FORMAT, "observations": [asdict(observation)]}
    input_path.write_text(json.dumps(raw))
    old = states(candidate)
    result = enrich_sources(candidate, output, input_path)
    assert result["postflight"]["code"] == "REPLAY_VALIDATED"
    assert result["bank_changes"] == 0
    assert states(output) == old
    # Internal consistency is insufficient: an extra fabricated exception base
    # survives constructor checks but must fail exact native-source regeneration.
    packet["analyses"][0]["derivation"]["exception_bases"].append("fabricated-base")
    raw["observations"] = [asdict(wordnet_identity_observation(packet, definition))]
    input_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="SOURCE_IDENTITY_MISMATCH"):
        enrich_sources(candidate, tmp_path / "forged.db", input_path)
    assert not (tmp_path / "forged.db").exists()
