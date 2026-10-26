"""The release preserves sparse evidence and publishes atomically through real inputs."""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import subprocess
import sys

import pytest

from gse.api.encoder import GSEEncoder
from gse.api.errors import EncodingError
from gse.lexical_evidence import close_lexical_connections, lookup_lexeme
from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.core import CANONICAL_COORDINATES
from gse.lexicon_builder.runtime import (
    RELEASE_SOURCE,
    ReleaseReader,
    build_release,
    read_released_reading,
    read_released_structures,
    release_manifest_status,
)


def sparse(word, reading_id, *, partial=False, conflict=False):
    cells: dict[str, dict] = {
        c: {"state": "empty", "domain": ["empty"], "written": False, "value": None} for c in CANONICAL_COORDINATES
    }
    cells["GOOD"] = {"state": "+1", "domain": ["+1"], "written": True, "value": 1}
    cells["I"] = {"state": "0", "domain": ["0"], "written": True, "value": 0}
    if partial:
        cells["FEEL"] = {"state": "unresolved", "domain": ["empty", "0", "+1"], "written": None, "value": None}
    if conflict:
        cells["KNOW"] = {"state": "conflict", "domain": [], "written": None, "value": None}
    return {
        "schema": "GSE_LEXICON_SPARSE_V1",
        "basis_id": BASIS_ID,
        "word": word,
        "reading_id": reading_id,
        "code": "CONFLICT" if conflict else "PARTIAL" if partial else "CANDIDATE_COMPLETE",
        "source_scope": "AUTHORED_TEST_FIXTURE",
        "rule_id": "fixture",
        "coordinate_order": list(CANONICAL_COORDINATES),
        "cells": cells,
        "number_scale": {"family": "INTENSITY", "native_ordinal_rank": 2, "numeric_gain": None},
        "constructions": [{"operation": "BOUND_TEST_SCOPE", "reference": "$referent"}],
        "decisions": [],
        "production_eligible": False,
        "provenance": {
            "source_record_ids": ["fixture:1"],
            "fired_rules": ["fixture"],
            "trace": [{"code": "AUTHORED_FIXTURE"}],
            "model_requests": [],
        },
    }


@pytest.fixture
def build_dir(tmp_path):
    directory = tmp_path / "build"
    directory.mkdir()
    manifest = {
        "schema_version": 1,
        "basis_id": BASIS_ID,
        "coordinate_order": list(CANONICAL_COORDINATES),
        "words": ["broken", "good", "the", "vague"],
        "rulebook_sha256": "0" * 64,
        "foundation_sha256": "1" * 64,
        "implementation": {"fixture.py": "2" * 64},
        "sources": [
            {
                "source": "fixture",
                "units": "authored test fixture",
                "scope": "READING",
                "status": "UNAVAILABLE",
                "files": [],
            }
        ],
        "model": None,
    }
    records = [
        sparse("good", "reading:good"),
        sparse("vague", "reading:vague", partial=True),
        sparse("broken", "reading:broken", conflict=True),
    ]
    structure = {
        "word": "the",
        "basis_id": BASIS_ID,
        "reading_id": "construction:definite",
        "surfaces": ["the"],
        "operation": "BIND_DEFINITE_REFERENCE",
        "source": "fixture",
        "location": "authored fixture",
        "basis_gaps": [],
        "claims": [],
        "lexical_projection": {"code": "CONSTRUCTION_ONLY", "warrant": "No invented cells"},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    (directory / "sparse.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    (directory / "structures.jsonl").write_text(json.dumps(structure) + "\n")
    return directory


def test_release_round_trips_every_sparse_state_and_keeps_conflicts_auditable(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    receipt = build_release(build_dir, destination)
    assert receipt["code"] == "PUBLISHED_SYMBOLIC_RELEASE"
    assert receipt["counts"] == {"symbolic_conflict": 1, "symbolic_complete": 1, "symbolic_partial": 1, "structures": 1}
    expected = {r["reading_id"]: r for r in map(json.loads, (build_dir / "sparse.jsonl").read_text().splitlines())}
    with sqlite3.connect(destination) as conn:
        for lexeme_id, reading_id in conn.execute("SELECT lexeme_id,reading_id FROM released_readings"):
            assert read_released_reading(conn, lexeme_id) == expected[reading_id]
        selected = conn.execute("SELECT lemma,source,validation_status FROM lexemes ORDER BY lemma").fetchall()
        assert selected == [
            ("good", RELEASE_SOURCE, "symbolic_complete"),
            ("vague", RELEASE_SOURCE, "symbolic_partial"),
        ]
        assert conn.execute("SELECT count(*) FROM sentence_primitive_values").fetchone()[0] == 0
        assert not conn.execute("SELECT 1 FROM primitive_values WHERE primitive='NUMBER'").fetchall()
        vague_id = conn.execute("SELECT id FROM lexemes WHERE lemma='vague'").fetchone()[0]
        values = dict(conn.execute("SELECT primitive,value FROM primitive_values WHERE lexeme_id=?", (vague_id,)))
        assert values == {"GOOD": 1, "I": 0}  # silence and unresolved cells create no compatibility rows
        assert read_released_structures(conn, "the")[0]["lexical_projection"]["code"] == "CONSTRUCTION_ONLY"
        assert read_released_structures(conn, "absent") == []


def test_partial_compatibility_rows_are_consumable_and_explicit_zero_is_stored(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    try:
        found = lookup_lexeme("vague", destination)
        assert found["state"] == "primes" and found["primitives"] == {"GOOD": 1}
        assert found["selected_record"]["validation_status"] == "symbolic_partial"
        assert any(r["primitive"] == "I" and r["value"] == 0 for r in found["primitive_evidence"])
        assert lookup_lexeme("broken", destination)["state"] == "no_row"
    finally:
        close_lexical_connections()


def test_real_encoder_consumes_settled_cells_and_retains_the_full_definition(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    try:
        with GSEEncoder(db_path=str(destination)) as encoder:
            evidence = encoder.lexical_lookup("vague")
            assert evidence["definition_status"] == "symbolic_partial"
            assert len(evidence["definition"]["cells"]) == 58
            assert evidence["definition"]["cells"]["FEEL"]["state"] == "unresolved"
            assert evidence["definition"]["cells"]["I"]["written"] is True
            trace = encoder.encode("good")
            assert trace.tokens[0].word_primitives == {"GOOD": 1}
            assert trace.tokens[0].lexical_evidence["definition"]["cells"]["I"]["value"] == 0
            assert trace.final_nnz > 0 and trace.vector_hash == encoder.encode("good").vector_hash
    finally:
        close_lexical_connections()


def test_a_modified_compatibility_projection_cannot_supply_an_encoding(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    try:
        with GSEEncoder(db_path=str(destination), strict=True) as encoder:
            assert encoder.lexical_lookup("vague")["state"] == "primes"
            with sqlite3.connect(destination) as conn:
                lexeme_id = conn.execute("SELECT id FROM lexemes WHERE lemma='vague'").fetchone()[0]
                conn.execute(
                    "UPDATE primitive_values SET value=-1 WHERE lexeme_id=? AND primitive='GOOD'", (lexeme_id,)
                )
            refused = encoder.lexical_lookup("vague")
            assert refused["state"] == "unread"
            assert refused["reason"] == "RELEASE_COMPATIBILITY_PROJECTION_MISMATCH"
            assert refused["primitives"] == {}
            with pytest.raises(EncodingError, match="RELEASE_COMPATIBILITY_PROJECTION_MISMATCH"):
                encoder.encode("vague")
    finally:
        close_lexical_connections()


def test_native_source_conflicts_are_audit_only_even_without_empty_domains(build_dir, tmp_path):
    path = build_dir / "sparse.jsonl"
    record = sparse("broken", "native:scoped-collision", partial=True)
    record["code"] = "SOURCE_CONFLICT"
    path.write_text(json.dumps(record) + "\n")
    destination = tmp_path / "release.db"
    receipt = build_release(build_dir, destination)
    assert receipt["counts"]["symbolic_conflict"] == 1
    with sqlite3.connect(destination) as conn:
        assert conn.execute("SELECT count(*) FROM lexemes").fetchone()[0] == 0
        restored = read_released_reading(conn, 1)
        assert restored["code"] == "SOURCE_CONFLICT"
        assert not any(cell["state"] == "conflict" for cell in restored["cells"].values())


def test_fully_resolved_native_records_have_structurally_complete_status(build_dir, tmp_path):
    path = build_dir / "sparse.jsonl"
    record = sparse("good", "native:resolved")
    record["code"] = "RESOLVED"
    path.write_text(json.dumps(record) + "\n")
    destination = tmp_path / "release.db"
    receipt = build_release(build_dir, destination)
    assert receipt["counts"]["symbolic_complete"] == 1
    with sqlite3.connect(destination) as conn:
        assert conn.execute("SELECT validation_status FROM lexemes").fetchone()[0] == "symbolic_complete"


def test_identical_inputs_produce_identical_sqlite_bytes(build_dir, tmp_path):
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    assert build_release(build_dir, first)["sha256"] == build_release(build_dir, second)["sha256"]
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    ("code", "damage"),
    [
        ("INVALID_RELEASE_MANIFEST", lambda m: m.update(schema_version=True)),
        ("INCOMPATIBLE_RELEASE_BASIS", lambda m: m.update(basis_id="wrong")),
        ("INCOMPATIBLE_RELEASE_BASIS", lambda m: m.update(coordinate_order=[])),
        ("INVALID_RELEASE_WORKLIST", lambda m: m.update(words=[])),
        ("DUPLICATE_RELEASE_WORKLIST_ID", lambda m: m.update(words=["good", "GOOD"])),
        ("MISSING_RELEASE_CONTRACT_PIN", lambda m: m.pop("foundation_sha256")),
        ("MISSING_RELEASE_IMPLEMENTATION_PIN", lambda m: m.update(implementation={})),
        ("MISSING_RELEASE_SOURCE_PINS", lambda m: m.update(sources=[])),
        ("INCONSISTENT_RELEASE_SOURCE_PIN", lambda m: m["sources"][0].update(status="AVAILABLE")),
        ("INVALID_RELEASE_SOURCE_PIN", lambda m: m["sources"][0].update(source=[])),
        ("DUPLICATE_RELEASE_SOURCE_ID", lambda m: m["sources"].append(copy.deepcopy(m["sources"][0]))),
    ],
)
def test_manifest_refusals_are_named_and_leave_prior_release_untouched(build_dir, tmp_path, code, damage):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    before = destination.read_bytes()
    path = build_dir / "manifest.json"
    manifest = json.loads(path.read_text())
    damage(manifest)
    assert release_manifest_status(manifest) == code
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=code):
        build_release(build_dir, destination)
    assert destination.read_bytes() == before


@pytest.mark.parametrize(
    "filename,code",
    [("sparse.jsonl", "DUPLICATE_RELEASE_READING_ID"), ("structures.jsonl", "DUPLICATE_RELEASE_STRUCTURE_ID")],
)
def test_duplicate_located_ids_are_refused(build_dir, tmp_path, filename, code):
    path = build_dir / filename
    records = path.read_text().splitlines()
    path.write_text("\n".join([*records, records[0]]) + "\n")
    with pytest.raises(ValueError, match=code):
        build_release(build_dir, tmp_path / "release.db")
    assert not (tmp_path / "release.db").exists()


def test_distinct_surfaces_may_share_one_prime_reading_identity(build_dir, tmp_path):
    path = build_dir / "sparse.jsonl"
    records = list(map(json.loads, path.read_text().splitlines()))
    records[0]["reading_id"] = records[1]["reading_id"] = "prime:SHARED_ALIAS_FIXTURE"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    receipt = build_release(build_dir, tmp_path / "release.db")
    assert receipt["counts"]["symbolic_partial"] == 1 and receipt["counts"]["symbolic_complete"] == 1


def test_corrupted_sparse_cell_never_replaces_an_existing_release(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    before = destination.read_bytes()
    path = build_dir / "sparse.jsonl"
    records = list(map(json.loads, path.read_text().splitlines()))
    records[0]["cells"]["I"]["value"] = False
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    with pytest.raises(ValueError, match="SPARSE_VALUE_MISMATCH"):
        build_release(build_dir, destination)
    assert destination.read_bytes() == before
    assert not list(tmp_path.glob(".gse-lexicon-release-*"))


def test_a_damaged_released_payload_and_basis_are_refused(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    with sqlite3.connect(destination) as conn:
        lexeme_id = conn.execute("SELECT id FROM lexemes WHERE lemma='vague'").fetchone()[0]
        conn.execute("UPDATE released_readings SET payload='{}' WHERE lexeme_id=?", (lexeme_id,))
        with pytest.raises(ValueError, match="RELEASE_READING_DIGEST_MISMATCH"):
            read_released_reading(conn, lexeme_id)
        conn.execute("UPDATE release_metadata SET value=? WHERE key='basis_id'", (json.dumps("wrong"),))
        with pytest.raises(ValueError, match="INCOMPATIBLE_RELEASE_BASIS"):
            read_released_reading(conn, lexeme_id)


def test_a_reader_reuses_validation_only_for_its_unchanged_connection(build_dir, tmp_path, monkeypatch):
    from gse.lexicon_builder import runtime

    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    calls = []
    original = runtime._release_metadata

    def counted(conn):
        calls.append(conn)
        return original(conn)

    monkeypatch.setattr(runtime, "_release_metadata", counted)
    with sqlite3.connect(destination) as conn:
        reader = ReleaseReader(conn)
        assert reader.conn is conn and len(calls) == 1
        read_released_reading(conn, 1, reader=reader)
        read_released_structures(conn, "the", reader=reader)
        assert len(calls) == 1 and reader.validation_status == "REUSED_VALIDATED_RELEASE_CONNECTION"
        with sqlite3.connect(destination) as other:
            with pytest.raises(ValueError, match="RELEASE_READER_CONNECTION_MISMATCH"):
                read_released_reading(other, 1, reader=reader)


def test_same_connection_metadata_mutation_invalidates_the_reader(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    with sqlite3.connect(destination) as conn:
        reader = ReleaseReader(conn)
        conn.execute("UPDATE release_metadata SET value=? WHERE key='basis_id'", (json.dumps("wrong"),))
        with pytest.raises(ValueError, match="INCOMPATIBLE_RELEASE_BASIS"):
            read_released_reading(conn, 1, reader=reader)
        assert reader.invalidation_code == "SAME_CONNECTION_CHANGED"
        assert reader.validation_status == "INVALIDATED_RELEASE_CONNECTION" and reader.metadata == {}


def test_external_connection_metadata_mutation_invalidates_the_reader(build_dir, tmp_path):
    destination = tmp_path / "release.db"
    build_release(build_dir, destination)
    with sqlite3.connect(destination) as conn:
        reader = ReleaseReader(conn)
        with sqlite3.connect(destination) as other:
            other.execute("UPDATE release_metadata SET value=? WHERE key='basis_id'", (json.dumps("wrong"),))
        with pytest.raises(ValueError, match="INCOMPATIBLE_RELEASE_BASIS"):
            read_released_reading(conn, 1, reader=reader)
        assert reader.invalidation_code == "EXTERNAL_CONNECTION_CHANGED"
        assert reader.validation_status == "INVALIDATED_RELEASE_CONNECTION" and reader.metadata == {}


def test_a_missing_source_file_hash_is_refused(build_dir, tmp_path):
    path = build_dir / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["sources"][0].update(status="AVAILABLE", files=[{"id": "fixture:source", "path": "source.tsv"}])
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="MISSING_RELEASE_SOURCE_HASH"):
        build_release(build_dir, tmp_path / "release.db")


def test_real_builder_output_is_released_without_a_model(tmp_path):
    build_dir = tmp_path / "real-build"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "gse.lexicon_builder",
            "build",
            "--words",
            "good",
            "the",
            "they",
            "--sources",
            str(tmp_path / "no-sources"),
            "--nltk",
            str(tmp_path / "no-nltk"),
            "--output",
            str(build_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = build_release(build_dir, tmp_path / "real.db")
    assert receipt["counts"]["structures"] >= 4
    with sqlite3.connect(tmp_path / "real.db") as conn:
        for (lexeme_id,) in conn.execute("SELECT lexeme_id FROM released_readings"):
            assert not read_released_reading(conn, lexeme_id)["provenance"]["model_requests"]
        assert {e["operation"] for e in read_released_structures(conn, "the")} == {"BIND_DEFINITE_REFERENCE"}
    assert hashlib.sha256((tmp_path / "real.db").read_bytes()).hexdigest() == receipt["sha256"]
