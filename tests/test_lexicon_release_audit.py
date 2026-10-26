"""Coverage counts cannot promote head recognition to semantic completion."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter

import pytest

from gse.lexicon_builder.artifact import export_sparse
from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Law, resolve
from gse.lexicon_builder.release_audit import (
    corpus_counts,
    file_digest,
    lexical_tokens,
    release_audit,
    threshold_status,
)


def _reading(word, cells, complete=False):
    identity = word + ":sense-1"
    assignments = dict.fromkeys(CANONICAL_COORDINATES, "empty") if complete else {}
    assignments.update(cells)
    laws = tuple(
        Law("fixture:" + coordinate, (coordinate,), ((Cell(value),),), (), "Explicit test-only cell warrant")
        for coordinate, value in assignments.items()
    )
    resolution = resolve(identity, laws=laws)
    return {
        "word": word,
        "reading_id": identity,
        "code": "CANDIDATE_COMPLETE" if complete else "PARTIAL",
        "source_scope": "FIXTURE",
        "premise_record_ids": ["native:" + word],
        "after_selection": resolution.to_json(),
        "model_calls": [],
        "candidate_vector": None,
    }


@pytest.fixture
def audit_fixture(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    pin = tmp_path / "native-source.txt"
    pin.write_text("Fixed source content\n")
    words = ["box", "runs", "the", "known", "ghost"]
    manifest = {
        "basis_id": BASIS_ID,
        "coordinate_order": list(CANONICAL_COORDINATES),
        "words": words,
        "sources": [
            {
                "source": "usas",
                "status": "AVAILABLE",
                "files": [{"id": "fixture:source", "path": str(pin), "sha256": file_digest(pin)}],
            },
            {"source": "ratings", "status": "UNAVAILABLE", "files": []},
        ],
    }
    (build_dir / "manifest.json").write_text(json.dumps(manifest))
    readings = {
        "box": [_reading("box", {"SOMETHING": "+1", "KIND": "0"})],
        "runs": [_reading("runs", {"MOVE": "+1", "SOMEONE": "0"})],
        "known": [_reading("known", {"KNOW": "+1"}, complete=True)],
    }
    records = []
    for word in words:
        records.append(
            {
                "word": word,
                "readings": readings.get(word, []),
                "structural_entries": [{"entry_id": "definite-reference"}] if word == "the" else [],
                "native": {
                    "usas": {"status": "OBSERVED" if word in readings else "NO_RECORD"},
                    "ratings": {"status": "UNAVAILABLE"},
                },
                "unhandled_native_alternatives": [],
            }
        )
    (build_dir / "words.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    (build_dir / "sparse.jsonl").write_text(
        "".join(json.dumps(export_sparse(r)) + "\n" for rows in readings.values() for r in rows)
    )
    (build_dir / "structures.jsonl").write_text(json.dumps({"word": "the", "entry_id": "definite-reference"}) + "\n")
    corpus_root = tmp_path / "corpora"
    brown = corpus_root / "brown"
    brown.mkdir(parents=True)
    (brown / "cats.txt").write_text("a01 news\nb01 fiction\n")
    (brown / "a01").write_text("The/at box/nn runs/vb unknown/nn ./.")
    (brown / "b01").write_text("Known/vb box/nn 42/cd !/!")
    gutenberg = corpus_root / "gutenberg"
    gutenberg.mkdir()
    (gutenberg / "independent.txt").write_text("The box unknown known. 123!")
    return build_dir, corpus_root, pin


def test_audit_counts_cells_readings_sources_and_partial_head_profiles(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    report = release_audit(build_dir, corpus_root)
    build = report["build"]
    assert build["code"] == "BUILD_ARTIFACTS_CONSISTENT"
    assert build["declared_words"] == 5 and build["sparse_readings"] == 3
    assert build["cell_classes"] == {
        "SIGNED_CONTENT": 3,
        "HEAD_COORDINATE_ZERO": 2,
        "UNRESOLVED": 112,
        "EXPLICIT_SILENCE": 57,
    }
    assert build["profile_classes"] == {
        "PARTIAL_HEAD_EVIDENCE_ONLY": 1,
        "PARTIAL_DEFINITIONAL_EVIDENCE": 1,
        "FULLY_SETTLED_COORDINATE_PROFILE": 1,
    }
    assert build["native_source_states_by_word"] == {
        "ratings": {"UNAVAILABLE": 5},
        "usas": {"OBSERVED": 3, "NO_RECORD": 2},
    }
    assert build["word_evidence"]["surface_home"] == 4
    assert build["word_evidence"]["signed_evidence"] == 3
    assert build["word_evidence"]["all_readings_coordinate_complete"] == 1
    assert build["model_request_count"] == 0


def test_corpus_mass_and_genres_are_separate_from_completion(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    report = release_audit(build_dir, corpus_root)
    brown = report["corpora"]["brown"]
    assert set(brown["groups"]) == {"news", "fiction"}
    news = brown["groups"]["news"]
    assert news["eligible_tokens"] == 4
    assert news["metrics"]["surface_home"]["matched_tokens"] == 3
    assert news["metrics"]["signed_evidence"]["matched_tokens"] == 2
    assert news["metrics"]["non_head_written_evidence"]["matched_tokens"] == 1
    assert news["metrics"]["any_complete_coordinate_profile"]["matched_tokens"] == 0
    assert news["out_of_declared_vocabulary"] == [{"word": "unknown", "count": 1}]
    assert news["metrics"]["surface_home"]["code"] == "THRESHOLD_NOT_MET"
    assert brown["groups"]["fiction"]["metrics"]["surface_home"]["code"] == "THRESHOLD_MET"
    assert report["corpora"]["gutenberg"]["total"]["eligible_tokens"] == 4
    assert report["interpretation"]["semantic_completion"] == "NOT_ESTABLISHED_BY_COVERAGE_AUDIT"


def test_build_and_corpus_inputs_are_fully_hashed(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    report = release_audit(build_dir, corpus_root)
    manifest = report["manifest"]
    assert manifest["build_manifest_sha256"] == file_digest(build_dir / "manifest.json")
    assert {r["name"] for r in manifest["build_inputs"]} == {
        "manifest.json",
        "words.jsonl",
        "sparse.jsonl",
        "structures.jsonl",
    }
    assert {r["id"] for r in manifest["corpus_inputs"]} == {
        "nltk:brown/cats.txt",
        "nltk:brown/a01",
        "nltk:brown/b01",
        "nltk:gutenberg/independent.txt",
    }
    assert manifest["native_source_pin_verification"]["outcomes"] == {"SOURCE_PIN_MATCH": 1}


def test_changed_native_source_is_reported_without_rewriting_build(audit_fixture):
    build_dir, corpus_root, pin = audit_fixture
    original = (build_dir / "sparse.jsonl").read_bytes()
    pin.write_text("Source changed after build\n")
    report = release_audit(build_dir, corpus_root)
    assert report["manifest"]["native_source_pin_verification"]["outcomes"] == {"SOURCE_PIN_MISMATCH": 1}
    assert (build_dir / "sparse.jsonl").read_bytes() == original


def test_missing_source_and_missing_corpus_have_named_states(audit_fixture):
    build_dir, corpus_root, pin = audit_fixture
    pin.unlink()
    (corpus_root / "brown/cats.txt").unlink()
    report = release_audit(build_dir, corpus_root)
    assert report["manifest"]["native_source_pin_verification"]["outcomes"] == {"SOURCE_FILE_UNAVAILABLE": 1}
    assert report["corpora"]["brown"]["code"] == "CORPUS_UNAVAILABLE"
    assert report["corpora"]["brown"]["total"]["metrics"]["surface_home"]["code"] == "NO_ELIGIBLE_TOKENS"


def test_full_coordinate_profile_requires_every_coordinate_to_be_settled(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    rows = [json.loads(line) for line in (build_dir / "sparse.jsonl").read_text().splitlines()]
    known = next(row for row in rows if row["word"] == "known")
    known["cells"]["MOVE"] = {"state": "unresolved", "domain": ["0", "+1"], "written": None, "value": None}
    (build_dir / "sparse.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    report = release_audit(build_dir, corpus_root)
    assert report["build"]["word_evidence"]["any_complete_coordinate_profile"] == 0
    assert report["build"]["word_evidence"]["surface_home"] == 4


def test_unhandled_sense_prevents_all_readings_complete_claim(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    records = [json.loads(line) for line in (build_dir / "words.jsonl").read_text().splitlines()]
    next(row for row in records if row["word"] == "known")["unhandled_native_alternatives"] = [{"tag": "unhandled"}]
    (build_dir / "words.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    report = release_audit(build_dir, corpus_root)
    assert report["build"]["word_evidence"]["any_complete_coordinate_profile"] == 1
    assert report["build"]["word_evidence"]["all_readings_coordinate_complete"] == 0


def test_conflict_is_not_unknown_silence_or_completion(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    rows = [json.loads(line) for line in (build_dir / "sparse.jsonl").read_text().splitlines()]
    rows[0]["cells"]["MOVE"] = {"state": "conflict", "domain": [], "written": None, "value": None}
    (build_dir / "sparse.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    report = release_audit(build_dir, corpus_root)
    assert report["build"]["cell_classes"]["CONFLICT"] == 1
    assert report["build"]["words_with_conflicts"] == 1
    assert report["build"]["profile_classes"]["CONFLICTED_PROFILE"] == 1


@pytest.mark.parametrize("word", ["runs", "known"])
def test_source_conflict_without_empty_domains_cannot_support_coverage(audit_fixture, word):
    build_dir, corpus_root, _ = audit_fixture
    rows = [json.loads(line) for line in (build_dir / "sparse.jsonl").read_text().splitlines()]
    row = next(r for r in rows if r["word"] == word)
    row["code"] = "SOURCE_CONFLICT"
    assert all(cell["domain"] for cell in row["cells"].values())
    (build_dir / "sparse.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    report = release_audit(build_dir, corpus_root)
    build = report["build"]
    assert build["words_with_conflicts"] == 1
    assert build["cell_classes"]["SIGNED_CONTENT"] == 3  # diagnostic, not coverage support
    assert build["word_evidence"]["signed_evidence"] == 2
    assert build["word_evidence"]["non_head_written_evidence"] == 1
    assert build["word_evidence"]["surface_home"] == 4
    if word == "known":
        assert build["word_evidence"]["any_complete_coordinate_profile"] == 0


def test_head_zeros_are_counted_separately_from_signed_or_non_head_content(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    rows = [json.loads(line) for line in (build_dir / "sparse.jsonl").read_text().splitlines()]
    box = next(r for r in rows if r["word"] == "box")
    box["cells"]["SOMETHING"] = {"state": "0", "domain": ["0"], "written": True, "value": 0}
    (build_dir / "sparse.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    report = release_audit(build_dir, corpus_root)
    assert report["build"]["profile_classes"]["PARTIAL_HEAD_ZEROS_ONLY"] == 1
    assert report["build"]["word_evidence"]["head_zero_evidence"] == 2
    assert report["build"]["word_evidence"]["non_head_zero_evidence"] == 0
    assert report["build"]["word_evidence"]["signed_evidence"] == 2


def test_reference_comparison_cannot_change_construction_or_coverage(audit_fixture, tmp_path):
    build_dir, corpus_root, _ = audit_fixture
    before = file_digest(build_dir / "sparse.jsonl")
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps(
            {
                "gold_from_published_explications": {
                    "box": {
                        "class": "adjective_fear",
                        "source": "independent-test",
                        "written_coordinates": {"WANT": 1},
                    },
                }
            }
        )
    )
    control = release_audit(build_dir, corpus_root)
    compared = release_audit(build_dir, corpus_root, gold=gold)
    assert control["build"] == compared["build"]
    assert control["corpora"] == compared["corpora"]
    assert before == file_digest(build_dir / "sparse.jsonl")
    ledger = compared["published_explication_comparison"]
    assert ledger["input_sha256"] == before
    assert ledger["reference_sha256"] == file_digest(gold)
    assert ledger["ledger"][0]["code"] == "UNIMPLEMENTED_PROJECTION"
    assert ledger["reference_role"] == "EVALUATION_ONLY; NEVER_CONSTRUCTION_OR_TASK_GENERATION"


def test_duplicate_sparse_reading_is_refused(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    path = build_dir / "sparse.jsonl"
    row = next(iter(path.read_text().splitlines()))
    with path.open("a") as stream:
        stream.write(row + "\n")
    with pytest.raises(ValueError, match="DUPLICATE_SPARSE_READING"):
        release_audit(build_dir, corpus_root)


def test_malformed_sparse_cell_is_refused(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    path = build_dir / "sparse.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["cells"]["SOMETHING"]["written"] = False
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="SPARSE_MASK_MISMATCH"):
        release_audit(build_dir, corpus_root)


def test_missing_worklist_record_is_reported_not_silently_ignored(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    manifest = json.loads((build_dir / "manifest.json").read_text())
    manifest["words"].append("missing")
    (build_dir / "manifest.json").write_text(json.dumps(manifest))
    report = release_audit(build_dir, corpus_root)
    assert report["build"]["code"] == "BUILD_ARTIFACT_SET_MISMATCH"
    assert report["build"]["missing_declared_words"] == ["missing"]


@pytest.mark.parametrize("threshold", [-0.1, 1.01, float("nan"), float("inf"), None, True])
def test_invalid_thresholds_have_a_named_refusal(threshold):
    with pytest.raises(ValueError, match="INVALID_COVERAGE_THRESHOLD"):
        threshold_status(0, 1, threshold)


def test_exact_threshold_and_empty_boundary():
    assert threshold_status(9, 10)["code"] == "THRESHOLD_MET"
    assert threshold_status(8, 10)["code"] == "THRESHOLD_NOT_MET"
    assert threshold_status(0, 0)["code"] == "NO_ELIGIBLE_TOKENS"
    with pytest.raises(ValueError, match="INVALID_COVERAGE_COUNTS"):
        threshold_status(2, 1)


def test_token_normalization_preserves_accents_and_internal_apostrophes(audit_fixture):
    _, root, _ = audit_fixture
    (root / "gutenberg/independent.txt").write_bytes("CAFÉ café can't mother-in-law 42.".encode("latin1"))
    counts, _ = corpus_counts(root, "gutenberg")
    assert counts["independent"] == {"café": 2, "can't": 1, "mother-in-law": 1}
    assert Counter(lexical_tokens("CAFÉ cafe\u0301 can't mother-in-law 42.")) == {
        "café": 2,
        "can't": 1,
        "mother-in-law": 1,
    }


def test_release_audit_cli_is_wired_and_preserves_artifacts(audit_fixture, tmp_path):
    build_dir, corpus_root, _ = audit_fixture
    before = file_digest(build_dir / "sparse.jsonl")
    output = tmp_path / "audit-output"
    command = [
        sys.executable,
        "-m",
        "gse.lexicon_builder.release_audit",
        "--build-dir",
        str(build_dir),
        "--nltk",
        str(corpus_root),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["code"] == "RELEASE_AUDIT_COMPUTED"
    assert (output / "release-audit.json").is_file()
    assert before == file_digest(build_dir / "sparse.jsonl")


def test_audit_refuses_missing_required_artifact(audit_fixture):
    build_dir, corpus_root, _ = audit_fixture
    (build_dir / "structures.jsonl").unlink()
    with pytest.raises(ValueError, match="MISSING_BUILD_ARTIFACT:structures.jsonl"):
        release_audit(build_dir, corpus_root)
