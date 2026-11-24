"""Witness orchestration never teaches its reviewed answer or mutates a bank."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "checkpoint_canonical_audit",
    ROOT / "docs/readings/2026-11-13-ssl-explicit-genera/ssl_api_checkpoint_canonical_audit.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def setup_audit(tmp_path, monkeypatch):
    database = tmp_path / "candidate.db"
    database.write_bytes(b"immutable candidate")
    source = tmp_path / "source.txt"
    source.write_text("primary source")
    review = {
        "baseline": {"path": str(database), "sha256": MODULE.fingerprint(database)},
        "source_pins": {str(source): MODULE.fingerprint(source)},
        "claims": [{"entry_id": "exact:unit", "bank": "THINK", "value": 1, "derivation": "REVIEW_ONLY"}],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review))
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "configuration": {
                    "model": "local-test",
                    "timeout_seconds": 1,
                    "context_tokens": 98304,
                    "thinking": False,
                    "output_tokens": 256,
                    "identity": "test-exact-identity",
                }
            }
        )
    )
    transport = SimpleNamespace(identity="test-exact-identity", pin=lambda: None)
    monkeypatch.setattr(MODULE, "OllamaTransport", lambda *args, **kwargs: transport)
    request = SimpleNamespace(
        request_id="exact-request",
        entry_id="exact:unit",
        bank="THINK",
        allowed_values=(-1, 0, 1),
        payload=lambda: {"bank": "THINK", "native": "complete evidence"},
        output_schema=lambda: {"type": "object"},
    )
    monkeypatch.setattr(MODULE, "make_questions", lambda *args: [request])
    calls = []

    class Journal:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, payload, schema):
            calls.append((payload, schema))
            return '{"THINK":null}'

        def count(self):
            return len(calls)

    monkeypatch.setattr(MODULE, "JournaledTransport", Journal)
    return database, source, review_path, settings, calls


def test_null_is_preserved_without_answer_leak_or_bank_write(tmp_path, monkeypatch):
    database, _, review, settings, calls = setup_audit(tmp_path, monkeypatch)
    before = database.read_bytes()
    result = MODULE.audit(review, tmp_path / "audit", settings)
    assert result["records"][0]["value"] is None
    assert result["bank_writes"] == 0 and not result["is_final_holdout"]
    assert database.read_bytes() == before
    assert len(calls) == 1
    assert "REVIEW_ONLY" not in json.dumps(calls)
    assert "value" not in calls[0][0]


@pytest.mark.parametrize("changed", ["database", "source", "duplicate"])
def test_changed_authority_or_duplicate_coordinate_refused_before_service(tmp_path, monkeypatch, changed):
    database, source, review, settings, calls = setup_audit(tmp_path, monkeypatch)
    if changed == "database":
        database.write_bytes(b"changed head")
    elif changed == "source":
        source.write_text("changed source")
    else:
        payload = json.loads(review.read_text())
        payload["claims"] *= 2
        review.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="CANONICAL_AUDIT"):
        MODULE.audit(review, tmp_path / "audit", settings)
    assert calls == []
