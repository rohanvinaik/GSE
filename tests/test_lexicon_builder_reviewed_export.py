"""The exporter reads a real candidate and never converts inventory into review."""

import json
import sqlite3

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.residual import _request_id
from GSE.curation.lexicon_builder.reviewed_export import SELECTION_FORMAT, export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow
from scripts import export_lexicon_patterns as script


class Transport:
    identity = "synthetic-export-fixture"

    def __call__(self, payload, schema):
        return json.dumps({payload["bank"]: 1 if payload["bank"] == "WANT" else 0})


def build(tmp_path):
    definitions = tuple(Definition(name, name, "verb", "synthetic source definition") for name in ("a", "b"))
    observations = tuple(
        Observation(name, "websters1913", name, "dictionary", {"definition": "synthetic source definition"}, "lexical")
        for name in ("a", "b")
    )
    path = tmp_path / "candidate.db"
    build_dictionary(EvidenceBundle(definitions, observations, (), ()), path)
    complete_dictionary(path, Transport(), 4, banks=("SEE", "WANT"), max_calls_per_entry=2)
    return path


def select():
    return {
        "format": SELECTION_FORMAT,
        "discovery_entry_ids": ["a"],
        "audit_entry_ids": ["b"],
        "reviews": [],
        "candidates": [["WANT", 1, "GOOD", 0]],
    }


def review_all(path):
    with sqlite3.connect(path) as conn:
        records = read_model_receipts(conn)
        result = []
        for entry in records:
            for receipt in records[entry]:
                result.append(
                    {
                        "request_id": receipt["request_id"],
                        "review": {
                            "review_id": "synthetic:" + receipt["request_id"],
                            "reviewer": "synthetic:test",
                            "receipt_sha256": _request_id(receipt),
                            "code": "ACCEPTED",
                            "source_refs": ["synthetic:test-only"],
                            "rationale": "Fixture authority, not linguistic gold.",
                        },
                    }
                )
        return result


def test_exporter_inventory_preserves_unreviewed_receipts_and_database_bytes(tmp_path):
    path = build(tmp_path)
    before = path.read_bytes()
    report = export_reviewed_input(path, select())
    assert report["lexicon_writes"] is False
    assert report["model_calls"] == 0
    assert report["selected_provenance"] == "REPLAY_VALIDATED"
    assert report["review_outcomes"] == {"NOT_INDEPENDENTLY_REVIEWED": 4}
    assert report["input"]["rulings"] == []
    assert len(report["inventory"]) == 4
    assert {item["dependency_status"] for item in report["inventory"]} == {
        "NATIVE_ANCHOR_BASELINE",
        "PRIOR_MODEL_DEPENDENCIES",
    }
    assert all(item["receipt_sha256"] == _request_id(item["receipt"]) for item in report["inventory"])
    assert path.read_bytes() == before


def test_real_export_cli_feeds_existing_workflow_with_full_dependency_replay(tmp_path, monkeypatch):
    path = build(tmp_path)
    selected = select()
    selected["reviews"] = review_all(path)
    selection = tmp_path / "selection.json"
    output, report_path = tmp_path / "input.json", tmp_path / "report.json"
    selection.write_text(json.dumps(selected))
    before = path.read_bytes()
    monkeypatch.setattr(
        "sys.argv",
        [
            "export",
            "--candidate",
            str(path),
            "--selection",
            str(selection),
            "--input",
            str(output),
            "--report",
            str(report_path),
        ],
    )
    assert script.main() == 0
    export = json.loads(report_path.read_text())
    assert export["review_outcomes"] == {"EXPLICIT_REVIEW_SUPPLIED": 4}
    workflow = run_workflow(output)
    assert workflow["candidates"][0]["staging"][0]["code"] == "STAGED_ONLY"
    assert workflow["candidates"][0]["audit_outcomes"] == {"AUDIT_CALL_BUDGET_EXHAUSTED": 1}
    assert workflow["model_calls"] == 0
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("hash", "STALE_RULING_REVIEW"),
        ("evidence", "SOURCE_BACKED_REVIEW_REQUIRED"),
        ("unknown", "REVIEW_NOT_IN_SELECTED_ACTIVE_RECEIPTS"),
        ("duplicate", "DUPLICATE_PATTERN_REVIEW"),
    ],
)
def test_export_refuses_stale_unbacked_unknown_or_duplicate_reviews(tmp_path, mutation, code):
    path = build(tmp_path)
    selection = select()
    selection["reviews"] = review_all(path)
    review = selection["reviews"][0]
    if mutation == "hash":
        review["review"]["receipt_sha256"] = "0" * 64
    elif mutation == "evidence":
        review["review"].pop("source_refs")
    elif mutation == "unknown":
        review["request_id"] = "missing"
    else:
        selection["reviews"].append(review)
    before = path.read_bytes()
    with pytest.raises(ValueError, match=code):
        export_reviewed_input(path, selection)
    assert path.read_bytes() == before


def test_selected_native_context_tampering_is_detected_before_export(tmp_path):
    path = build(tmp_path)
    with sqlite3.connect(path) as conn:
        raw = json.loads(conn.execute("SELECT payload FROM source_observations WHERE record_id='a'").fetchone()[0])
        raw["features"]["changed"] = "stale model context"
        conn.execute("UPDATE source_observations SET payload=? WHERE record_id='a'", (json.dumps(raw),))
    with pytest.raises(ValueError, match="MODEL_OBSERVATIONS_MISMATCH"):
        export_reviewed_input(path, select())


def test_export_cli_cannot_overwrite_candidate_or_selection(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.db"
    candidate.write_bytes(b"must survive")
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps(select()))
    monkeypatch.setattr(
        "sys.argv",
        [
            "export",
            "--candidate",
            str(candidate),
            "--selection",
            str(selection),
            "--input",
            str(candidate),
            "--report",
            str(tmp_path / "out.json"),
        ],
    )
    with pytest.raises(ValueError, match="PATTERN_EXPORT_PATH_COLLISION"):
        script.main()
    assert candidate.read_bytes() == b"must survive"


def test_selection_identity_and_shape_boundaries(tmp_path):
    path = build(tmp_path)
    for mutation, code in [
        ({"audit_entry_ids": ["a"]}, "DISCOVERY_AUDIT_ID_OVERLAP"),
        ({"audit_entry_ids": ["absent"]}, "UNKNOWN_PATTERN_DEFINITION"),
        ({"discovery_entry_ids": [], "audit_entry_ids": []}, "EMPTY_PATTERN_EXPORT"),
    ]:
        with pytest.raises(ValueError, match=code):
            export_reviewed_input(path, {**select(), **mutation})
