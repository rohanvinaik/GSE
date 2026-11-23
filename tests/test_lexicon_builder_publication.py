"""Synthetic release fixtures test publication, not the semantics of NSM primes."""

import hashlib
import json
import sqlite3
from dataclasses import asdict

import pytest

from GSE.curation.lexicon_builder.catalog import (
    SENTENCE_DURATION_SOURCE_RECORD,
    SENTENCE_DURATION_UNIT,
    catalog_inventory,
)
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, collect_evidence, load_local_sources
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.publication import publication_readiness, publish_complete, publish_sparse
from GSE.lexicon_resource import resolve_lexicon_path


@pytest.fixture
def candidate(tmp_path):
    units = catalog_inventory()["units"]
    definitions = tuple(
        Definition(f"fixture:{i}", f"fixture_{i}", "x", "Synthetic test identity") for i in range(len(units))
    )
    manifest = {
        "format": "GSE.lexicon-rules/1",
        "anchors": {
            d.entry_id: [asdict(Assertion(bank, 0, "fixture", f"{d.entry_id}:{bank}", "test")) for bank in BANKS]
            for d in definitions
        },
        "prime_entries": {u["unit_id"]: [d.entry_id] for u, d in zip(units, definitions)},
    }
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps(manifest))
    path = tmp_path / "candidate.db"
    bundle = EvidenceBundle(definitions, (), (), ())
    build_dictionary(bundle, path, manifest=rules)
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps(
            {
                "format": "GSE.lexicon-gold/1",
                "records": [{"entry_id": "fixture:0", "bank": bank, "expected": 0} for bank in BANKS],
            }
        )
    )
    return path, gold, rules, bundle


def test_complete_snapshot_requires_semantic_audit_and_preserves_zeros(candidate):
    path, gold, _, _ = candidate
    missing = publication_readiness(path)
    assert missing["code"] == "PUBLICATION_BLOCKED"
    assert missing["blockers"] == ["SEMANTIC_AUDIT_NOT_SUPPLIED"]
    ready = publication_readiness(path, gold)
    assert ready["code"] == "READY_FOR_PUBLICATION"
    assert ready["cells"]["explicit_zero"] == 65 * len(BANKS)
    assert ready["cells"].get("unresolved", 0) == 0
    assert ready["replay"]["code"] == "REPLAY_VALIDATED"


def test_unknown_is_not_zero_and_refusal_preserves_pointer(candidate, tmp_path):
    path, gold, rules, bundle = candidate
    raw = json.loads(rules.read_text())
    raw["anchors"]["fixture:0"] = [a for a in raw["anchors"]["fixture:0"] if a["bank"] != "WANT"]
    rules.write_text(json.dumps(raw))
    build_dictionary(bundle, path, manifest=rules)
    pointer = tmp_path / "active.json"
    pointer.write_text("previous pointer\n")
    destination = tmp_path / "release.db"
    report = publish_complete(path, destination, gold, pointer_path=pointer)
    assert report["code"] == "PUBLICATION_BLOCKED"
    assert report["cells"]["unresolved"] == 1
    assert "INCOMPLETE_DEFINITIONS" in report["blockers"]
    assert pointer.read_text() == "previous pointer\n"
    assert not destination.exists()


def test_sparse_release_preserves_open_domain_and_can_advance_to_a_validated_successor(candidate, tmp_path):
    path, gold, rules, bundle = candidate
    manifest = json.loads(rules.read_text())
    original = rules.read_text()
    manifest["anchors"]["fixture:0"] = [row for row in manifest["anchors"]["fixture:0"] if row["bank"] != "WANT"]
    rules.write_text(json.dumps(manifest))
    build_dictionary(bundle, path, manifest=rules)
    pointer = tmp_path / "active.json"
    first = tmp_path / "sparse-1.db"
    installed = publish_sparse(path, first, gold, pointer_path=pointer)
    assert installed["code"] == "PUBLISHED_SPARSE_LEXICON"
    assert installed["cells"]["unresolved"] == 1
    assert installed["semantic_audit"]["outcomes"]["ABSTAINED"] == 1
    assert resolve_lexicon_path(pointer_path=pointer) == first
    with sqlite3.connect(first) as conn:
        [domains] = conn.execute("SELECT domains FROM definition_states WHERE entry_id='fixture:0'").fetchone()
        assert json.loads(domains)["WANT"] == [-1, 0, 1]
    pointer_sha = hashlib.sha256(pointer.read_bytes()).hexdigest()

    rules.write_text(original)
    build_dictionary(bundle, path, manifest=rules)
    second = tmp_path / "sparse-2.db"
    mismatch = publish_sparse(path, second, gold, pointer_path=pointer, expected_pointer_sha256="wrong")
    assert mismatch["blockers"] == ["ACTIVE_POINTER_CHANGED"]
    assert not second.exists()
    installed = publish_sparse(path, second, gold, pointer_path=pointer, expected_pointer_sha256=pointer_sha)
    assert installed["code"] == "PUBLISHED_SPARSE_LEXICON"
    assert installed["previous_path"] == str(first)
    assert resolve_lexicon_path(pointer_path=pointer) == second
    assert first.is_file()


def test_sentence_duration_replays_as_a_construction_and_is_outside_lexical_completion(candidate):
    path, gold, rules, bundle = candidate
    raw = json.loads(rules.read_text())
    [placeholder] = raw["prime_entries"][SENTENCE_DURATION_UNIT]
    raw["prime_entries"][SENTENCE_DURATION_UNIT] = [SENTENCE_DURATION_SOURCE_RECORD]
    del raw["anchors"][placeholder]
    rules.write_text(json.dumps(raw))
    parsers, _ = load_local_sources(("nsm_chart",))
    chart = collect_evidence(parsers, ())
    definitions = tuple(row for row in bundle.definitions if row.entry_id != placeholder)
    duration = tuple(row for row in chart.definitions if row.entry_id == SENTENCE_DURATION_SOURCE_RECORD)
    observations = tuple(row for row in chart.observations if row.entry_id == SENTENCE_DURATION_SOURCE_RECORD)
    scoped = EvidenceBundle(definitions + duration, observations, (), ())

    class NoModelCalls:
        identity = "fixture-no-lexical-work"

        def __call__(self, *args, **kwargs):
            pytest.fail("Sentence construction reached the lexical writer")

    report = build_dictionary(scoped, path, manifest=rules, transport=NoModelCalls(), max_model_calls=1)
    assert report["model_calls"] == 0
    with pytest.raises(ValueError, match="SENTENCE_CONSTRUCTION_OUTSIDE_LEXICAL_SCOPE"):
        complete_dictionary(path, NoModelCalls(), 1, entry_ids=(SENTENCE_DURATION_SOURCE_RECORD,))
    report = publication_readiness(path, gold)
    assert report["code"] == "READY_FOR_PUBLICATION"
    assert report["replay"]["entries_validated"] == 65
    assert report["cells"]["explicit_zero"] == 64 * len(BANKS)
    assert report["cells"].get("unresolved", 0) == 0
    assert report["outcomes"] == {"RESOLVED": 64, "SENTENCE_CONSTRUCTION": 1}
    assert report["sentence_constructions"][SENTENCE_DURATION_UNIT]["entry_id"] == SENTENCE_DURATION_SOURCE_RECORD

    with sqlite3.connect(path) as conn:
        [serialized] = conn.execute(
            "SELECT domains FROM definition_states WHERE entry_id=?", (SENTENCE_DURATION_SOURCE_RECORD,)
        ).fetchone()
        domains = json.loads(serialized)
        assert all(domain == [-1, 0, 1] for domain in domains.values())
        domains["LONG_TIME"] = [0]
        conn.execute(
            "UPDATE definition_states SET domains=? WHERE entry_id=?", (json.dumps(domains), SENTENCE_DURATION_SOURCE_RECORD)
        )
    blocked = publication_readiness(path, gold)
    assert blocked["code"] == "PUBLICATION_BLOCKED"
    assert "INVALID_SENTENCE_CONSTRUCTION_RECORD" in blocked["blockers"]


def test_deleting_a_difficult_definition_cannot_shrink_scope(candidate):
    path, gold, _, _ = candidate
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM definition_states WHERE entry_id='fixture:0'")
    report = publication_readiness(path, gold)
    assert "DEFINITION_COHORT_MISMATCH" in report["blockers"]
    assert report["missing_definition_ids"] == ["fixture:0"]


def test_unrepresented_requested_word_blocks_release(candidate):
    path, gold, _, _ = candidate
    with sqlite3.connect(path) as conn:
        words = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='requested_words'").fetchone()[0])
        words.append("missing_requested_word")
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='requested_words'", (json.dumps(words),))
    report = publication_readiness(path, gold)
    assert report["missing_words"] == ["missing_requested_word"]
    assert "REQUESTED_WORDS_MISSING" in report["blockers"]


def test_incorrect_or_narrow_semantic_audit_blocks_release(candidate):
    path, gold, _, _ = candidate
    raw = json.loads(gold.read_text())
    raw["records"] = [{"entry_id": "fixture:0", "bank": "WANT", "expected": 1}]
    gold.write_text(json.dumps(raw))
    report = publication_readiness(path, gold)
    assert set(report["blockers"]) == {"SEMANTIC_AUDIT_FAILURE", "SEMANTIC_AUDIT_MISSING_COORDINATES"}
    assert report["semantic_audit"]["outcomes"]["WRONG"] == 1


def test_publication_switches_to_validated_copy_and_keeps_source(candidate, tmp_path):
    path, gold, _, _ = candidate
    pointer, destination = tmp_path / "active.json", tmp_path / "release.db"
    report = publish_complete(path, destination, gold, pointer_path=pointer)
    assert report["code"] == "PUBLISHED_COMPLETE_LEXICON"
    assert len(report["sha256"]) == 64
    assert resolve_lexicon_path(pointer_path=pointer) == destination
    assert path.is_file()
    with pytest.raises(ValueError, match="PUBLICATION_REQUIRES_NEW_DESTINATION"):
        publish_complete(path, destination, gold, pointer_path=pointer)


def test_change_between_preflight_and_copy_is_revalidated(candidate, tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import publication

    path, gold, _, _ = candidate
    original = publication.publication_readiness
    calls = []

    def checked(file, gold_file):
        result = original(file, gold_file)
        calls.append(file)
        if len(calls) == 1:
            with sqlite3.connect(path) as conn:
                conn.execute("DELETE FROM definition_states WHERE entry_id='fixture:0'")
        return result

    monkeypatch.setattr(publication, "publication_readiness", checked)
    pointer, destination = tmp_path / "active.json", tmp_path / "release.db"
    pointer.write_text("previous pointer")
    report = publish_complete(path, destination, gold, pointer_path=pointer)
    assert len(calls) == 2
    assert report["code"] == "PUBLICATION_BLOCKED"
    assert pointer.read_text() == "previous pointer"
    assert not destination.exists()


def test_real_cli_refuses_incomplete_checkpoint(candidate, monkeypatch, capsys):
    from GSE.curation.cli.commands import main

    path, _, _, _ = candidate
    monkeypatch.setattr("sys.argv", ["lexicon", "--lexicon-db", str(path), "publish"])
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 2
    assert json.loads(capsys.readouterr().out)["code"] == "PUBLICATION_BLOCKED"
