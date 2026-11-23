"""Approved representation laws through build, replay, and runtime boundaries."""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from gse.api.encoder import GSEEncoder
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle
from gse.curation.lexicon_builder.foundation import BANKS, representation_contract
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.validation import validate_build
from gse.primitives_v2 import get_hierarchy_encoding
from scripts.encode_modifiers import encode_modifiers

APPROVED_MANIFEST = Path(__file__).resolve().parents[1] / "docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json"
WANT_ID = "wordnet:want:desire.v.01"
VERY_ID = "wordnet:very:very.r.01"
EXTREMELY_ID = "wordnet:extremely:extremely.r.02"


def _anchor_only_manifest(tmp_path):
    """This fixture exercises authored anchors, independently of the grammar cohort."""
    manifest = json.loads(APPROVED_MANIFEST.read_text())
    manifest["prime_entries"] = {
        unit: manifest["prime_entries"][unit]
        for unit in ("nsm:v20:want", "nsm:v20:very", "nsm:v20:this", "nsm:v20:dont-want")
    }
    path = tmp_path / "anchor-only-rules.json"
    path.write_text(json.dumps(manifest))
    return path


def test_approved_intensity_contract_matches_runtime():
    contract = representation_contract()
    assert contract["ordinal_intensity"] == {"VERY": 1, "EXTREMELY": 2}
    assert get_hierarchy_encoding("VERY") == ("INTENSITY", 1, 1)
    assert get_hierarchy_encoding("EXTREMELY") == ("INTENSITY", 2, 2)
    assert contract["other_ordinal_levels"] == "EXPLICIT_JUSTIFIED_MANIFEST_ONLY"
    assert contract["want_polarity"] == {"-1": "NOT_WANT", "0": "ORTHOGONAL_TO_WANTING", "1": "WANT"}


def test_basis_fingerprint_is_stable_until_an_explicit_migration():
    contract = representation_contract()
    assert contract["basis"] == list(BANKS)
    assert len(contract["basis"]) == len(set(contract["basis"]))
    assert not {"NUMBER", "HIER_PLUS", "HIER_MINUS"}.intersection(contract["basis"])
    assert contract["basis_sha256"] == "c181d9e3ac3f3ca6004dfdafeb8e1bb666610bafd428e3d32bbf29ee52af2492"
    contract["basis"].clear()
    assert representation_contract()["basis"] == list(BANKS)


@pytest.mark.parametrize(
    "modifier,replacement",
    [("VERY", ("INTENSITY", 2, 2)), ("EXTREMELY", ("INTENSITY", 4, 4)), ("VERY", None)],
)
def test_runtime_ordinal_drift_is_named_and_prevents_output(tmp_path, monkeypatch, modifier, replacement):
    monkeypatch.setattr(
        "gse.primitives_v2.get_hierarchy_encoding",
        lambda word: replacement if word == modifier else get_hierarchy_encoding(word),
    )
    with pytest.raises(ValueError, match="^ORDINAL_REPRESENTATION_DRIFT$"):
        representation_contract()
    output = tmp_path / "must-not-exist.db"
    with pytest.raises(ValueError, match="^ORDINAL_REPRESENTATION_DRIFT$"):
        build_dictionary(EvidenceBundle((), (), (), ()), output)
    assert not output.exists()


@pytest.fixture
def approved_build(tmp_path):
    definitions = (
        Definition(WANT_ID, "want", "v", "feel or have a desire for; want strongly"),
        Definition(VERY_ID, "very", "adv", "used as intensifiers"),
        Definition(EXTREMELY_ID, "extremely", "adv", "to an extreme degree"),
    )
    output = tmp_path / "approved.db"
    report = build_dictionary(EvidenceBundle(definitions, (), (), ()), output, manifest=_anchor_only_manifest(tmp_path))
    return output, report


def test_approved_anchors_preserve_unknown_banks_and_definition_identity(approved_build):
    path, report = approved_build
    assert report["definitions"] == 5
    assert report["source_observations"] == {}
    assert report["model_calls"] == 0
    expected = {
        WANT_ID: {"WANT": 1},
        "gse:prime:dont-want": {"WANT": -1},
        "gse:prime:this": {"SOMETHING": 1},
        VERY_ID: {"SOMETHING": 0, "INTENSITY": 1},
        EXTREMELY_ID: {"SOMETHING": 0, "INTENSITY": 1},
    }
    with GSEEncoder(str(path)) as encoder:
        for entry_id, assignments in expected.items():
            selection = encoder.lookup_definition(entry_id)
            assert selection["code"] == "IDENTIFIED"
            entry = selection["selected"]
            assert entry["entry_id"] == entry_id
            assert entry["assignments"] == assignments
            assert entry["domains"] == {
                bank: [assignments[bank]] if bank in assignments else [-1, 0, 1] for bank in BANKS
            }
        assert encoder.lookup_definition("gse:prime:this")["selected"]["domains"]["HAVE"] == [-1, 0, 1]
    replay = validate_build(path)
    assert replay["code"] == "REPLAY_VALIDATED", replay
    assert replay["entries_validated"] == 5
    assert replay["metadata_verification"]["representation_contract"] == "VERIFIED"


def test_approved_intensifier_definitions_preserve_base_and_distinguish_degree(approved_build):
    path, _ = approved_build
    with GSEEncoder(str(path)) as encoder:
        very = encoder.lookup_definition(VERY_ID)["selected"]
        extremely = encoder.lookup_definition(EXTREMELY_ID)["selected"]
        assert very["assignments"] == extremely["assignments"] == {"SOMETHING": 0, "INTENSITY": 1}
        assert very["hierarchy"] == {"INTENSITY": 1}
        assert extremely["hierarchy"] == {"INTENSITY": 2}
        very_vector = encoder.encode_definition(VERY_ID)
        extreme_vector = encoder.encode_definition(EXTREMELY_ID)
        assert very_vector.nnz > 0
        assert extreme_vector.nnz > 0
        assert not np.array_equal(very_vector.to_dense(), extreme_vector.to_dense())


def test_intensity_anchors_do_not_leak_into_other_definitions(tmp_path):
    other_id = "wordnet:very:identical.s.02"
    definitions = (
        Definition(WANT_ID, "want", "v", "feel or have a desire for; want strongly"),
        Definition(VERY_ID, "very", "adv", "used as intensifiers"),
        Definition(EXTREMELY_ID, "extremely", "adv", "to an extreme degree"),
        Definition(other_id, "very", "adj", "being the exact same one; not any other"),
    )
    path = tmp_path / "other-definitions.db"
    build_dictionary(EvidenceBundle(definitions, (), (), ()), path, manifest=_anchor_only_manifest(tmp_path))
    with GSEEncoder(str(path)) as encoder:
        assert encoder.lexical_lookup("very")["selection_status"] == "AMBIGUOUS"
        other = encoder.lookup_definition(other_id)["selected"]
        assert "INTENSITY" not in other["assignments"]
        assert other["domains"]["INTENSITY"] == [-1, 0, 1]
        assert other["hierarchy"] == {}


@pytest.mark.parametrize(
    "key,value",
    [
        ("representation_contract", {"ordinal_intensity": {"VERY": 2, "EXTREMELY": 4}}),
        ("convention_version", "unapproved-representation/99"),
        ("want_polarity", {"-1": "ORTHOGONAL_TO_WANTING", "0": "NOT_WANT", "1": "WANT"}),
    ],
)
def test_tampered_representation_metadata_has_a_named_mismatch(approved_build, key, value):
    path, _ = approved_build
    conn = sqlite3.connect(path)
    try:
        conn.execute("UPDATE builder_metadata SET value=? WHERE key=?", (json.dumps(value), key))
        conn.commit()
    finally:
        conn.close()
    replay = validate_build(path)
    assert replay["code"] == "REPLAY_MISMATCH"
    assert replay["mismatch_counts"] == {"REPRESENTATION_CONTRACT_MISMATCH": 1}
    assert replay["metadata_verification"]["representation_contract"] == "MISMATCH"


def test_signed_want_anchors_reach_runtime_without_extra_coordinates(approved_build):
    path, _ = approved_build
    with GSEEncoder(str(path)) as encoder:
        base = encoder.word_basis.get_primitive("WANT")
        assert base is not None
        positive = encoder.encode_definition(WANT_ID)
        negative = encoder.encode_definition("gse:prime:dont-want")
        np.testing.assert_array_equal(positive.to_dense(), base.to_dense())
        np.testing.assert_array_equal(negative.to_dense(), base.negate().to_dense())
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        stored = json.loads(
            conn.execute("SELECT value FROM builder_metadata WHERE key='representation_contract'").fetchone()[0]
        )
        assert stored == representation_contract()
        assert conn.execute("SELECT COUNT(*) FROM source_observations").fetchone()[0] == 0
    finally:
        conn.close()


def test_superseded_modifier_writer_rejects_before_opening_database(tmp_path, monkeypatch):
    path = tmp_path / "must-not-exist.db"

    def forbidden_connect(*args, **kwargs):
        pytest.fail("Superseded writer reached database connection")

    monkeypatch.setattr(sqlite3, "connect", forbidden_connect)
    with pytest.raises(ValueError, match="^SUPERSEDED_ORDINAL_WRITER:"):
        encode_modifiers(path)
    assert not path.exists()


def test_modifier_dry_run_never_creates_a_missing_database(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        encode_modifiers(path, dry_run=True)
    assert not path.exists()


def test_modifier_dry_run_uses_a_read_only_connection(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT)")
    conn.execute("INSERT INTO lexemes VALUES (1,'very')")
    conn.commit()
    conn.close()
    before = path.read_bytes()
    connect = sqlite3.connect
    opened = []

    def read_only_connect(database, **kwargs):
        assert database == path.resolve().as_uri() + "?mode=ro"
        assert kwargs == {"uri": True}
        connection = connect(database, **kwargs)
        opened.append(connection)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("CREATE TABLE forbidden (value INTEGER)")
        return connection

    monkeypatch.setattr(sqlite3, "connect", read_only_connect)
    assert encode_modifiers(path, dry_run=True)["found"] == 1
    assert path.read_bytes() == before
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
