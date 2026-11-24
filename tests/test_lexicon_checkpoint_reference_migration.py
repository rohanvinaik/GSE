"""Exercise the checkpoint transition through real source, writer and replay APIs."""

import hashlib
import importlib
import json
import sqlite3
from dataclasses import replace

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.evidence import collect_evidence, load_local_sources
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.reconsideration import reconsider_many
from GSE.curation.lexicon_builder.storage import _json, read_entries
from GSE.curation.lexicon_builder.validation import validate_build

migration = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.checkpoint_reference_migration")


class SyntheticRuling:
    model = "synthetic-checkpoint-mechanics-only"

    def __call__(self, payload, schema):
        return json.dumps({payload["bank"]: 0})


def fixture(tmp_path):
    parsers, _ = load_local_sources(("gse_closed_class",))
    bundle = collect_evidence(parsers, ())
    # Reproduce the older adapter's omitted reference claims, not a gold vector.
    bundle = replace(bundle, assertions=tuple(a for a in bundle.assertions if a.bank not in {"I", "YOU"}))
    path = tmp_path / "candidate.db"
    build_dictionary(bundle, path)
    claims = []
    for entry, bank in (("gse_closed_class:pronoun:i", "I"), ("gse_closed_class:pronoun:you", "YOU")):
        report = complete_dictionary(path, SyntheticRuling(), 1, entry_ids=(entry,), banks=("BODY",))
        assert report["outcomes"] == {"ASSIGNED": 1}
        observation = next(o for o in bundle.observations if o.entry_id == entry)
        with sqlite3.connect(path) as conn:
            payload = json.loads(
                conn.execute(
                    "SELECT payload FROM source_observations WHERE record_id=?", (observation.record_id,)
                ).fetchone()[0]
            )
        claims.append(
            {
                "entry_id": entry,
                "bank": bank,
                "value": 1,
                "native_record_id": observation.record_id,
                "native_observation_sha256": hashlib.sha256(_json(payload).encode()).hexdigest(),
            }
        )
    return path, claims


def test_real_retirement_then_source_projection_replays_without_complement_zeros(tmp_path):
    path, claims = fixture(tmp_path)
    with sqlite3.connect(path) as conn:
        roots = [row[0] for row in conn.execute("SELECT request_id FROM accepted_model_receipts")]
    reconsider_many(path, roots, convention="fixture/1", reason="source proof changes context", apply=True)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        changes = migration.apply_reference_proofs(conn, claims)
        rows = {row["entry_id"]: row for row in read_entries(conn)}
    assert len(changes) == 2
    for claim in claims:
        row = rows[claim["entry_id"]]
        assert row["assignments"][claim["bank"]] == 1
        assert row["domains"]["BODY"] == [-1, 0, 1]
        assert "BODY" not in row["assignments"]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_projection_refuses_model_prefix_and_changed_source_witness(tmp_path):
    path, claims = fixture(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        with pytest.raises(ValueError, match="REQUIRES_RETIRED_MODEL_PREFIX"):
            migration.apply_reference_proofs(conn, claims)
        roots = [row[0] for row in conn.execute("SELECT request_id FROM accepted_model_receipts")]
    reconsider_many(path, roots, convention="fixture/1", reason="source proof changes context", apply=True)
    before = path.read_bytes()
    claims[1] = {**claims[1], "native_observation_sha256": "0" * 64}
    with pytest.raises(ValueError, match="NATIVE_WITNESS_CHANGED"):
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            migration.apply_reference_proofs(conn, claims)
    assert path.read_bytes() == before
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
