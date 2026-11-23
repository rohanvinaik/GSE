"""End-to-end contracts for identity, silence, persistence and actual CLI wiring."""

import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict

import pytest

from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary, load_evidence
from GSE.curation.lexicon_builder.storage import open_build, read_entries, runtime_lookup


def bundle():
    return EvidenceBundle(
        (
            Definition("bank:river", "bank", "noun", "edge of a river"),
            Definition("bank:finance", "bank", "noun", "financial institution"),
            Definition("hatred:feeling", "hatred", "noun", "named feeling"),
        ),
        (
            Observation("bank:river", "dictionary", "r1", "dictionary", {"kind": "entity"}, "lexical"),
            Observation("bank:finance", "dictionary", "r2", "dictionary", {"kind": "entity"}, "lexical"),
            Observation(
                "hatred:feeling",
                "dictionary",
                "r3",
                "dictionary",
                {"kind": "feeling", "embedded_evaluation": -1},
                "lexical",
            ),
        ),
        (
            Assertion("SOMETHING", 1, "dictionary", "r1", "dictionary"),
            Assertion("SOMETHING", 1, "dictionary", "r2", "dictionary"),
            Assertion("FEEL", 1, "dictionary", "r3", "dictionary"),
        ),
        (),
    )


def test_roundtrip_keeps_zero_silence_identity_and_nested_evidence(tmp_path):
    path = tmp_path / "built.db"
    report = build_dictionary(bundle(), path)
    assert report["definitions"] == 3
    assert report["outcomes"] == {"PARTIAL": 3}
    with sqlite3.connect(path) as conn:
        entries = read_entries(conn, "bank")
        assert len(entries) == 2
        assert entries[0]["assignments"] == entries[1]["assignments"]
        assert runtime_lookup(conn, "bank")["code"] == "AMBIGUOUS"
        assert runtime_lookup(conn, "bank", "bank:river")["selected"]["entry_id"] == "bank:river"
        hatred = read_entries(conn, "hatred")[0]
        assert hatred["assignments"] == {"FEEL": 1, "GOOD": 0}
        assert hatred["domains"]["WANT"] == [-1, 0, 1]
        assert "WANT" not in hatred["assignments"]
        observation = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE record_id='r3'").fetchone()[0]
        )
        assert observation["features"]["embedded_evaluation"] == -1


def test_conflicting_entry_never_publishes_a_winner(tmp_path):
    data = bundle()
    conflict = EvidenceBundle(
        data.definitions,
        data.observations,
        data.assertions + (Assertion("FEEL", -1, "dictionary", "r3", "dictionary"),),
        (),
    )
    report = build_dictionary(conflict, tmp_path / "conflict.db")
    assert report["outcomes"]["CONFLICT"] == 1
    with sqlite3.connect(tmp_path / "conflict.db") as conn:
        assert read_entries(conn, "hatred")[0]["assignments"] == {}
        assert runtime_lookup(conn, "hatred")["code"] == "CONFLICT"


def test_legacy_database_is_never_relabelled(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE lexemes(id INTEGER)")
        conn.execute("INSERT INTO lexemes VALUES (42)")
    with pytest.raises(ValueError, match="LEGACY_DATABASE"):
        open_build(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT id FROM lexemes").fetchall() == [(42,)]
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name='builder_metadata'").fetchall()


def test_adjective_projection_and_invalid_source_link(tmp_path):
    data = EvidenceBundle((Definition("big:1", "big", "adj", "size descriptor"),), (), (), ())
    build_dictionary(data, tmp_path / "adj.db")
    with sqlite3.connect(tmp_path / "adj.db") as conn:
        assert read_entries(conn)[0]["assignments"] == {"SOMETHING": 0}
    bad = EvidenceBundle(data.definitions, (), (Assertion("BIG", 1, "x", "not-linked", "x"),), ())
    with pytest.raises(ValueError, match="EXACT_DEFINITION_LINK"):
        build_dictionary(bad, tmp_path / "bad.db")
    assert not (tmp_path / "bad.db").exists()


def test_real_cli_build_lookup_export(tmp_path):
    data = bundle()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"format": "GSE.lexicon-evidence/1", **asdict(data)}))
    db = tmp_path / "cli.db"
    base = [sys.executable, "-m", "GSE.curation.cli.commands", "--lexicon-db", str(db)]
    built = subprocess.run(base + ["build", "--evidence", str(evidence)], capture_output=True, text=True, check=True)
    assert json.loads(built.stdout)["model_calls"] == 0
    looked = subprocess.run(base + ["lookup", "bank"], capture_output=True, text=True, check=True)
    assert json.loads(looked.stdout)["code"] == "AMBIGUOUS"
    selected = subprocess.run(
        base + ["lookup", "bank", "--entry-id", "bank:river"], capture_output=True, text=True, check=True
    )
    assert json.loads(selected.stdout)["code"] == "IDENTIFIED"
    export = tmp_path / "export.json"
    subprocess.run(base + ["export", "--output", str(export)], capture_output=True, text=True, check=True)
    records = json.loads(export.read_text())["entries"]
    assert {r["entry_id"] for r in records} == {d.entry_id for d in data.definitions}
    assert "NUMBER" not in BANKS
    validated = subprocess.run(base + ["validate"], capture_output=True, text=True, check=True)
    assert json.loads(validated.stdout)["code"] == "REPLAY_VALIDATED"


def test_model_budget_and_repropagation_are_consumed_by_pipeline(tmp_path):
    data = EvidenceBundle((Definition("v:1", "sense", "verb", "typed fixture"),), (), (), ())
    calls = []

    def transport(payload, schema):
        bank = next(iter(schema["properties"]))
        calls.append(bank)
        return json.dumps({bank: 0})

    report = build_dictionary(data, tmp_path / "model.db", transport=transport, max_model_calls=1)
    assert len(calls) == report["model_calls"] == 1
    assert report["model_outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(tmp_path / "model.db") as conn:
        assert read_entries(conn)[0]["assignments"] == {calls[0]: 0}


@pytest.mark.parametrize("level", [True, 1.5, "2"])
def test_hierarchy_rejects_non_integer_levels(tmp_path, level):
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "hierarchy": {"hatred:feeling": {"FEEL": level}}}))
    with pytest.raises(ValueError, match="HIERARCHY"):
        build_dictionary(bundle(), tmp_path / "bad.db", manifest=manifest)


@pytest.mark.parametrize(
    "source,family,scope",
    [
        ("forged", "dictionary", "lexical"),
        ("dictionary", "forged", "lexical"),
        ("dictionary", "dictionary", "association"),
    ],
)
def test_native_assertions_require_matching_lexical_provenance(tmp_path, source, family, scope):
    observation = Observation("d", "dictionary", "r", "dictionary", {}, scope)
    data = EvidenceBundle(
        (Definition("d", "word", "verb", "definition"),),
        (observation,),
        (Assertion("KNOW", 1, source, "r", family),),
        (),
    )
    path = tmp_path / "forged.db"
    with pytest.raises(ValueError, match="ASSERTION_"):
        build_dictionary(data, path)
    assert not path.exists()


def test_duplicate_json_fields_are_rejected_before_build(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"format":"GSE.lexicon-evidence/1","definitions":[],"definitions":[]}')
    with pytest.raises(ValueError, match="DUPLICATE_JSON_FIELD"):
        load_evidence(path)


def test_boolean_definition_identity_is_not_coerced(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "format": "GSE.lexicon-evidence/1",
                "definitions": [{"entry_id": True, "lemma": "word", "pos": "noun", "definition": "text"}],
            }
        )
    )
    with pytest.raises(ValueError, match="INVALID_DEFINITION_ENTRY_ID"):
        load_evidence(path)


def test_failed_snapshot_rolls_back_and_success_removes_old_definitions(tmp_path):
    path = tmp_path / "snapshot.db"
    original = bundle()
    build_dictionary(original, path)
    replacement = EvidenceBundle((Definition("new", "new", "noun", "new entry"),), (), (), ())
    with pytest.raises(ValueError, match="INVALID_FREQUENCY_WEIGHT"):
        build_dictionary(replacement, path, weights={"new": -1})
    with sqlite3.connect(path) as conn:
        assert {r["entry_id"] for r in read_entries(conn)} == {d.entry_id for d in original.definitions}
    build_dictionary(replacement, path)
    with sqlite3.connect(path) as conn:
        assert [r["entry_id"] for r in read_entries(conn)] == ["new"]


def test_conflict_with_requested_hierarchy_never_publishes_hierarchy(tmp_path):
    from GSE.curation.lexicon_builder.validation import validate_build

    data = bundle()
    data = EvidenceBundle(
        data.definitions,
        data.observations,
        data.assertions
        + (
            Assertion("KNOW", 1, "dictionary", "r3", "dictionary"),
            Assertion("KNOW", -1, "dictionary", "r3", "dictionary"),
        ),
        (),
    )
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "hierarchy": {"hatred:feeling": {"FEEL": 2}}}))
    path = tmp_path / "conflict.db"
    build_dictionary(data, path, manifest=manifest)
    with sqlite3.connect(path) as conn:
        assert read_entries(conn, "hatred")[0]["hierarchy"] == {}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_explicit_prime_definition_and_catalog_gold_commands(tmp_path):
    manifest = tmp_path / "rules.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "GSE.lexicon-rules/1",
                "definitions": [
                    {"entry_id": "manual:you", "lemma": "you", "pos": "pronoun", "definition": "the person addressed"}
                ],
                "anchors": {
                    "manual:you": [
                        {
                            "bank": "YOU",
                            "value": 1,
                            "source": "reviewed",
                            "record_id": "review:you",
                            "family": "founder",
                        }
                    ]
                },
                "prime_entries": {"nsm:v20:you": ["manual:you"]},
            }
        )
    )
    path = tmp_path / "manual.db"
    report = build_dictionary(EvidenceBundle((), (), (), ()), path, manifest=manifest)
    assert report["prime_coverage"]["PARTIAL_FOUNDATION_CLOSURE"] == 1
    base = [sys.executable, "-m", "GSE.curation.cli.commands", "--lexicon-db", str(path)]
    catalog = subprocess.run(base + ["catalog"], capture_output=True, text=True, check=True)
    assert json.loads(catalog.stdout)["format"] == "GSE.nsm-catalog-coverage/2"
    assert json.loads(catalog.stdout)["coverage_counts"]["PARTIAL_FOUNDATION_CLOSURE"] == 1
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps(
            {"format": "GSE.lexicon-gold/1", "records": [{"entry_id": "manual:you", "bank": "YOU", "expected": 1}]}
        )
    )
    evaluation = subprocess.run(base + ["evaluate", "--gold", str(gold)], capture_output=True, text=True, check=True)
    assert json.loads(evaluation.stdout)["outcomes"]["IDENTIFIED_CORRECT"] == 1


@pytest.mark.parametrize("command", [["status"], ["validate"], ["lookup", "word"], ["export"], ["catalog"]])
def test_read_commands_never_create_a_missing_database(tmp_path, command):
    path = tmp_path / "missing.db"
    result = subprocess.run(
        [sys.executable, "-m", "GSE.curation.cli.commands", "--lexicon-db", str(path), *command],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "BUILD_NOT_FOUND" in result.stderr
    assert not path.exists()


def test_source_bank_competence_enforced_on_typed_input(tmp_path):
    data = EvidenceBundle(
        (Definition("d", "word", "verb", "definition"),),
        (Observation("d", "sentiwordnet", "r", "wordnet", {}, "lexical"),),
        (Assertion("DO", 1, "sentiwordnet", "r", "wordnet"),),
        (),
    )
    with pytest.raises(ValueError, match="ASSERTION_OUTSIDE_SOURCE_SCOPE"):
        build_dictionary(data, tmp_path / "bad.db")
    assert not (tmp_path / "bad.db").exists()


def test_manifest_provenance_string_is_not_split_into_characters(tmp_path):
    manifest = tmp_path / "rules.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "GSE.lexicon-rules/1",
                "relations": [
                    {"rule_id": "r", "banks": ["KNOW"], "allowed_rows": [[1]], "provenance": "paper", "approved": True}
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="INVALID_RELATION_SEQUENCE"):
        build_dictionary(bundle(), tmp_path / "bad.db", manifest=manifest)


def test_source_record_identifiers_must_be_globally_namespaced(tmp_path):
    data = EvidenceBundle(
        (Definition("d", "word", "verb", "definition"),),
        (Observation("d", "alpha", "r", "a", {}, "lexical"), Observation("d", "beta", "r", "b", {}, "lexical")),
        (),
        (),
    )
    with pytest.raises(ValueError, match="SOURCE_RECORD_ID_COLLISION"):
        build_dictionary(data, tmp_path / "bad.db")
    assert not (tmp_path / "bad.db").exists()


def test_uppercase_short_pos_uses_same_founder_projection(tmp_path):
    data = EvidenceBundle((Definition("d", "large", "ADJ", "size"),), (), (), ())
    path = tmp_path / "upper.db"
    build_dictionary(data, path)
    with sqlite3.connect(path) as conn:
        assert read_entries(conn)[0]["assignments"]["SOMETHING"] == 0


def test_diagnostics_are_rows_not_a_corpus_sized_json_value(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import pipeline

    def limited_open(path):
        conn = open_build(path)
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 131072)
        return conn

    monkeypatch.setattr(pipeline, "open_build", limited_open)
    records = tuple({"code": "UNIDENTIFIED", "detail": "x" * 200} for _ in range(2000))
    path = tmp_path / "large.db"
    build_dictionary(EvidenceBundle((), (), (), records), path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM unresolved_sources").fetchone()[0] == 2000
        metadata = json.loads(
            conn.execute("SELECT value FROM builder_metadata WHERE key='unresolved_sources'").fetchone()[0]
        )
        assert metadata["records"] == 2000
