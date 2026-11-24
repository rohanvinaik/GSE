"""Exact request/source guards for the grouped own-coordinate transition."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "checkpoint_canonical_projection",
    ROOT / "docs/readings/2026-11-13-ssl-explicit-genera/ssl_api_checkpoint_canonical_projection.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path, value):
    path.write_text(json.dumps(value))


def fixture(tmp_path, monkeypatch, value=1):
    baseline = tmp_path / "baseline.db"
    baseline.write_bytes(b"immutable candidate")
    source = tmp_path / "source.txt"
    source.write_text("exact primary meaning")
    claim = {
        "entry_id": "exact:think",
        "unit_id": "think",
        "bank": "THINK",
        "value": 1,
        "scope": "EXACT_SOURCE_DEFINITION_AND_OWN_COORDINATE_ONLY",
        "derivation": "Reviewed exact primary meaning and fixed basis definition",
    }
    review = {
        "baseline": {"path": str(baseline), "sha256": MODULE.fingerprint(baseline)},
        "source_pins": {str(source): MODULE.fingerprint(source)},
        "claims": [claim],
    }
    review_path = tmp_path / "review.json"
    write(review_path, review)
    request = SimpleNamespace(
        request_id="original-wire-id",
        entry_id=claim["entry_id"],
        bank="THINK",
        allowed_values=(-1, 0, 1),
        payload=lambda: {"source": "complete exact source", "bank": "THINK"},
        output_schema=lambda: {"type": "object"},
    )
    monkeypatch.setattr(MODULE, "make_questions", lambda *args: [request])
    directory = tmp_path / "witnesses"
    directory.mkdir()
    write(
        directory / "questions.json",
        {
            "format": "GSE.ssl-checkpoint-local-questions/1",
            "baseline_sha256": MODULE.fingerprint(baseline),
            "coordinates": [[claim["entry_id"], "THINK"]],
            "questions": [
                {"request_id": request.request_id, "request": request.payload(), "schema": request.output_schema()}
            ],
        },
    )
    write(
        directory / "answers.json",
        {
            "questions_sha256": MODULE.fingerprint(directory / "questions.json"),
            "transport": "true-98k-identity",
            "answers": [{"request_id": request.request_id, "raw_output": json.dumps({"THINK": value})}],
        },
    )
    audit = {
        "code": "TYPED_WITNESSES_RECORDED_NOT_ADMISSION",
        "baseline": review["baseline"],
        "review_sha256": MODULE.fingerprint(review_path),
        "questions_sha256": MODULE.fingerprint(directory / "questions.json"),
        "answers_sha256": MODULE.fingerprint(directory / "answers.json"),
        "transport": "true-98k-identity",
        "bank_writes": 0,
        "is_final_holdout": False,
        "records": [{"entry_id": claim["entry_id"], "bank": "THINK", "value": value, "request_id": request.request_id}],
    }
    write(directory / "audit.json", audit)
    return review_path, directory, review, audit


def test_matching_original_witness_only_creates_reviewed_own_anchor(tmp_path, monkeypatch):
    path, directory, _, _ = fixture(tmp_path, monkeypatch)
    _, claims, reservations = MODULE.verify_witnesses(path, directory)
    assert reservations == []
    manifest = MODULE.manifest_payload(claims, "review-pin", "audit-pin")
    assert set(manifest) == {"format", "anchors"}
    assert manifest["anchors"] == {
        "exact:think": [
            {
                "bank": "THINK",
                "value": 1,
                "source": "nsm_basis_correspondence:canonical-source-review-v1",
                "record_id": "think:review-pin:audit-pin:THINK",
                "family": "nsm_basis_correspondence",
                "scope": "lexical",
            }
        ]
    }


def test_explicit_null_reserves_without_assertion(tmp_path, monkeypatch):
    path, directory, _, _ = fixture(tmp_path, monkeypatch, None)
    _, claims, reservations = MODULE.verify_witnesses(path, directory)
    assert claims == []
    assert reservations == [{"entry_id": "exact:think", "bank": "THINK", "reason": "EXPLICIT_NULL"}]


def test_opposing_witness_is_not_silently_discarded(tmp_path, monkeypatch):
    path, directory, _, _ = fixture(tmp_path, monkeypatch, -1)
    with pytest.raises(ValueError, match="INDEPENDENT_DISAGREEMENT"):
        MODULE.verify_witnesses(path, directory)


@pytest.mark.parametrize("change", ["baseline", "source", "request", "transport", "scope", "duplicate", "outcome"])
def test_changed_authority_refused(tmp_path, monkeypatch, change):
    path, directory, review, audit = fixture(tmp_path, monkeypatch)
    if change == "baseline":
        Path(review["baseline"]["path"]).write_bytes(b"different head")
    elif change == "source":
        Path(next(iter(review["source_pins"]))).write_text("different meaning")
    elif change == "request":
        packet = MODULE.read(directory / "questions.json")
        packet["questions"][0]["request"]["source"] = "discarded context"
        write(directory / "questions.json", packet)
        audit["questions_sha256"] = MODULE.fingerprint(directory / "questions.json")
    elif change == "transport":
        audit["transport"] = "mislabelled-65k"
    elif change in ("scope", "duplicate"):
        if change == "scope":
            review["claims"][0]["scope"] = "ALL_SPELLINGS"
        else:
            review["claims"] *= 2
        write(path, review)
        audit["review_sha256"] = MODULE.fingerprint(path)
    else:
        audit["records"][0]["value"] = 0
    write(directory / "audit.json", audit)
    with pytest.raises(ValueError, match="CANONICAL_PROJECTION"):
        MODULE.verify_witnesses(path, directory)


def test_actual_pinned_storage_reader_relocation_is_exact():
    certificate = MODULE.read(
        ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint/postwriter-validation.json"
    )
    pins, relocations = MODULE.checked_builder_pins(certificate["builder_source_pins"])
    assert len(relocations) == 1
    assert relocations[0]["reader"] in pins


@pytest.mark.parametrize("change", ["writer", "reader", "reader_extra", "other_pin"])
def test_relocation_does_not_authorize_other_changed_code(tmp_path, monkeypatch, change):
    storage = Path("GSE/curation/lexicon_builder/storage.py")
    reader = Path("GSE/lexicon/definitions.py")
    old = MODULE.subprocess.check_output(["git", "show", "HEAD:" + str(storage)])
    current, moved = (ROOT / storage).read_text(), (ROOT / reader).read_text()
    monkeypatch.chdir(tmp_path)
    storage.parent.mkdir(parents=True)
    reader.parent.mkdir(parents=True)
    storage.write_text(current + ("\nUNREVIEWED = True\n" if change == "writer" else ""))
    reader.write_text(
        moved.replace('"NOT_FOUND"', '"IDENTIFIED"')
        if change == "reader"
        else moved + ("\nUNREVIEWED = True\n" if change == "reader_extra" else "")
    )
    monkeypatch.setattr(MODULE.subprocess, "check_output", lambda *args: old)
    pin = {"path": str(storage), "sha256": MODULE.hashlib.sha256(old).hexdigest()}
    if change == "other_pin":
        pin = {"path": str(reader), "sha256": "not-the-current-pin"}
    with pytest.raises(ValueError, match="CANONICAL_PROJECTION"):
        MODULE.checked_builder_pins([pin])
