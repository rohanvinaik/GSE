"""The compatibility recognizer never infers authorship or consumes holdout in fit."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rohan_voice  # noqa: E402


def _manifest(tmp_path, *, holdout=True):
    examples = [
        ("authored", "train", "I feel happy."),
        ("llm", "train", "You can help."),
        ("authored", "holdout", "I I I I I feel happy today."),
        ("llm", "holdout", "Here is how you can explain the happy dog."),
    ]
    sources = []
    for index, (label, split, text) in enumerate(examples):
        if not holdout and split == "holdout":
            continue
        path = tmp_path / f"source-{index}.txt"
        raw = text.encode("utf-8")
        path.write_bytes(raw)
        sources.append(
            {
                "path": path.name,
                "label": label,
                "split": split,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "group": f"independent-document-{index}",
                "selection": {"method": "human_review"},
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema": rohan_voice.MANIFEST, "sources": sources}))
    return manifest


def test_fit_requires_explicit_labels_and_holdout_without_scanning_defaults(tmp_path, monkeypatch):
    def no_scan(*args, **kwargs):
        raise AssertionError("a corpus scan is forbidden")

    monkeypatch.setattr(Path, "glob", no_scan)
    assert rohan_voice.fit()["reason"] == "explicit_manifest_required"
    manifest = _manifest(tmp_path, holdout=False)
    output = tmp_path / "model.json"
    assert rohan_voice.fit(manifest, model_path=output)["reason"] == "training_and_holdout_required_per_class"
    assert not output.exists()


def test_manifest_fit_grades_holdout_per_class_and_never_trains_on_it(tmp_path):
    manifest = _manifest(tmp_path)
    output = tmp_path / "model.json"
    result = rohan_voice.fit(manifest, model_path=output)
    assert result["state"] == "fit"
    assert result["trained_on"] == 2
    assert {label: values["n"] for label, values in result["holdout"].items()} == {"authored": 1, "llm": 1}
    assert all(set(values) == {"identified", "wrong", "abstained", "n"} for values in result["holdout"].values())
    model = json.loads(output.read_text())
    # Training first-person rates are 1/2 and 0. Five first-person holdout
    # occurrences must not alter their mean of 1/4.
    assert model["stats"][-4][0] == pytest.approx(0.25)
    assert "profile_dense" not in model
    assert model["schema"] == rohan_voice.SCHEMA
    assert len(model["sources"]) == 4
    observed = rohan_voice.recognize("I feel happy.", model_path=output)
    assert observed["state"] in ("identified", "abstained")
    assert "authentic_similarity" not in observed
    assert "not calibrated probability" in observed["score_definition"]


def test_changed_hash_or_duplicate_holdout_refuses_and_preserves_artifact(tmp_path):
    manifest = _manifest(tmp_path)
    output = tmp_path / "model.json"
    output.write_bytes(b"old artifact")
    (tmp_path / "source-0.txt").write_text("The source changed.")
    assert rohan_voice.fit(manifest, model_path=output)["reason"] == "source_hash_mismatch"
    assert output.read_bytes() == b"old artifact"
    manifest = _manifest(tmp_path)
    document = json.loads(manifest.read_text())
    document["sources"][2] = {**document["sources"][0], "split": "holdout", "group": "duplicate-heldout-document"}
    manifest.write_text(json.dumps(document))
    assert rohan_voice.fit(manifest, model_path=output)["reason"] == "duplicate_source_or_content"
    assert output.read_bytes() == b"old artifact"


def test_legacy_and_resource_changed_models_require_refit(tmp_path, monkeypatch):
    output = tmp_path / "model.json"
    assert rohan_voice.recognize("I feel happy.", model_path=output)["state"] == "refit_required"
    output.write_text(json.dumps({"profile_dense": [1.0], "n_train": 500}))
    assert rohan_voice.recognize("I feel happy.", model_path=output)["reason"] == "legacy_or_malformed_model"
    assert rohan_voice.fit(_manifest(tmp_path), model_path=output)["state"] == "fit"
    model = json.loads(output.read_text())
    model.pop("holdout")
    output.write_text(json.dumps(model))
    assert rohan_voice.recognize("I feel happy.", model_path=output)["reason"] == "legacy_or_malformed_model"
    assert rohan_voice.fit(_manifest(tmp_path), model_path=output)["state"] == "fit"
    monkeypatch.setenv("GSE_LEXICON", str(tmp_path / "unavailable.db"))
    assert rohan_voice.recognize("I feel happy.", model_path=output)["reason"] == "feature_or_resource_identity_changed"


def test_featurize_uses_selected_lexical_row_and_retains_empty_populations(tmp_path, monkeypatch):
    path = tmp_path / "lexicon.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE lexemes(id INTEGER,lemma TEXT,pos TEXT);"
            "CREATE TABLE primitive_values(lexeme_id INTEGER,primitive TEXT,value INTEGER);"
            "INSERT INTO lexemes VALUES(1,'happy','x'); INSERT INTO lexemes VALUES(2,'happy','x');"
            "INSERT INTO primitive_values VALUES(1,'GOOD',1); INSERT INTO primitive_values VALUES(2,'BAD',1);"
        )
    monkeypatch.setenv("GSE_LEXICON", str(path))
    features = rohan_voice.featurize("happy")
    assert features["state"] == "read"
    assert features["dist"][rohan_voice.CURATED.index("GOOD")] == 1
    assert features["dist"][rohan_voice.CURATED.index("BAD")] == 0
    assert rohan_voice.featurize("")["state"] == "empty"
    assert rohan_voice.featurize("xqzzzt")["state"] == "unread"


def test_real_cli_uses_named_manifest_and_reports_refit_without_dense(tmp_path):
    manifest = _manifest(tmp_path)
    output = tmp_path / "model.json"
    command = [sys.executable, str(Path(rohan_voice.__file__).resolve())]
    fitted = subprocess.run(
        [*command, "--fit", str(manifest), "--model", str(output)], check=True, capture_output=True, text=True
    )
    assert json.loads(fitted.stdout)["state"] == "fit"
    observed = subprocess.run(
        [*command, str(tmp_path / "source-0.txt"), "--model", str(output)], check=True, capture_output=True, text=True
    )
    assert json.loads(observed.stdout)["state"] in ("identified", "abstained")
    rejected = subprocess.run([*command, "--dense", str(tmp_path / "source-0.txt")], capture_output=True, text=True)
    assert rejected.returncode == 2


def test_retired_profiler_has_explicit_migration_and_no_old_dependency():
    script = Path(rohan_voice.__file__).with_name("voice_profile.py")
    process = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert process.returncode == 2
    migration = json.loads(process.stdout)
    assert migration["state"] == "retired"
    assert migration["replacement_schema"] == "voice.reading/1"
    assert "read" in migration and "compare" in migration


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing", "independence_groups_required"),
        ("overlap", "source_group_partition_overlap"),
        ("selection", "selection_evaluation_overlap"),
    ],
)
def test_fit_requires_declared_independent_groups_and_selection_evidence(tmp_path, monkeypatch, case, code):
    manifest = _manifest(tmp_path)
    document = json.loads(manifest.read_text())
    if case == "missing":
        document["sources"][0].pop("group")
    elif case == "overlap":
        document["sources"][2]["group"] = document["sources"][0]["group"]
    else:
        document["sources"][2]["selection"] = {"method": "recognizer", "artifact_sha256": "a" * 64}
    manifest.write_text(json.dumps(document))
    output = tmp_path / "model.json"
    output.write_bytes(b"preserved model")
    monkeypatch.setattr(rohan_voice, "featurize", lambda text: pytest.fail("invalid groups reached features"))
    result = rohan_voice.fit(manifest, model_path=output)
    assert result["state"] == "refused" and result["reason"] == code
    assert output.read_bytes() == b"preserved model"


def test_recognition_retains_per_class_grade_and_rejects_forged_overlap(tmp_path):
    manifest = _manifest(tmp_path)
    output = tmp_path / "model.json"
    fitted = rohan_voice.fit(manifest, model_path=output)
    assert fitted["state"] == "fit"
    recognized = rohan_voice.recognize("I feel happy.", model_path=output)
    assert recognized["state"] in {"identified", "abstained"}
    grade = recognized["evaluation"]
    assert grade["independence"] == "declared_source_groups"
    assert grade["per_class"] == fitted["holdout"] == fitted["evaluation"]["per_class"]
    model = json.loads(output.read_text())
    model["sources"][2]["group"] = model["sources"][0]["group"]
    output.write_text(json.dumps(model))
    rejected = rohan_voice.recognize("I feel happy.", model_path=output)
    assert rejected["state"] == "refit_required" and "evaluation" not in rejected
