"""The lexicon gate's frozen comparison: named outcomes, complete reports, data versus code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.lexicon_frozen_build import main


def write_build(path: Path, records: list[dict], files: dict[str, str]) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("words.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    path.joinpath("summary.json").write_text(json.dumps({"PARTIAL": len(records)}) + "\n")
    manifest = {
        "sources": [
            {"source": "usas", "status": "AVAILABLE", "files": [{"id": k, "sha256": v} for k, v in files.items()]}
        ]
    }
    path.joinpath("manifest.json").write_text(json.dumps(manifest))
    return path


@pytest.fixture
def gate(tmp_path):
    records = [{"word": "happy", "code": "PARTIAL", "readings": []}, {"word": "sad", "code": "PARTIAL", "readings": []}]
    build = write_build(tmp_path / "base", records, {"external:usas/semantic_lexicon_en.tsv": "a" * 64})
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir()
    assert main(["", "write", str(build), str(gate_dir)]) == 0
    return tmp_path, records, gate_dir


def test_an_identical_build_passes(gate):
    root, records, gate_dir = gate
    build = write_build(root / "same", records, {"external:usas/semantic_lexicon_en.tsv": "a" * 64})
    assert main(["", "check", str(build), str(gate_dir)]) == 0
    assert not build.joinpath("frozen_report.json").exists()


def test_reordered_keys_pass_because_key_order_is_not_the_contract(gate, capsys):
    root, records, gate_dir = gate
    reordered = [dict(reversed(list(r.items()))) for r in records]
    build = write_build(root / "reordered", reordered, {"external:usas/semantic_lexicon_en.tsv": "a" * 64})
    assert main(["", "check", str(build), str(gate_dir)]) == 0
    assert "KEY_ORDER_ONLY" in capsys.readouterr().out


def test_a_changed_value_fails_and_names_every_changed_word(gate):
    root, records, gate_dir = gate
    changed = [{**records[0], "code": "CONSTRUCTED_READINGS"}, records[1]]
    build = write_build(root / "changed", changed, {"external:usas/semantic_lexicon_en.tsv": "a" * 64})
    assert main(["", "check", str(build), str(gate_dir)]) == 1
    report = json.loads(build.joinpath("frozen_report.json").read_text())
    assert report["status"] == "CHANGED"
    assert report["changed_records"] == ["happy"]


def test_a_source_change_is_reported_as_data_never_as_code(gate):
    root, records, gate_dir = gate
    build = write_build(root / "data", records, {"external:usas/semantic_lexicon_en.tsv": "b" * 64})
    assert main(["", "check", str(build), str(gate_dir)]) == 3
    report = json.loads(build.joinpath("frozen_report.json").read_text())
    assert report == {
        "status": "DATA_CHANGED",
        "sources": {
            "usas": {
                "status": ["AVAILABLE", "AVAILABLE"],
                "added": [],
                "removed": [],
                "changed": ["external:usas/semantic_lexicon_en.tsv"],
            }
        },
    }
