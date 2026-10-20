"""Receipts must not attribute new files to older in-memory spelling caches."""

from pathlib import Path

from gse.nlp import healing_resources


def _reset(monkeypatch):
    monkeypatch.setattr(healing_resources, "_BASELINE", None)
    monkeypatch.setattr(healing_resources, "_UNVERIFIED", set())


def test_loaded_resource_change_is_stale_with_both_identities(monkeypatch):
    _reset(monkeypatch)
    source = {"state": "read", "path": "/fixture/words", "sha256": "before"}
    loaded = False
    monkeypatch.setattr(healing_resources, "_resources", lambda: ({"wordnet": dict(source)}, {"wordnet": loaded}, {}))
    first = healing_resources.provenance()
    assert first["state"] == "read"
    loaded = True
    source["sha256"] = "after"
    second = healing_resources.provenance()
    assert second["state"] == "stale"
    assert second["files"]["wordnet"]["snapshot"]["sha256"] == "before"
    assert second["files"]["wordnet"]["current"]["sha256"] == "after"


def test_preexisting_cache_never_claims_current_file_was_loaded(monkeypatch):
    _reset(monkeypatch)
    source = {"state": "read", "path": "/fixture/words", "sha256": "current"}
    monkeypatch.setattr(healing_resources, "_resources", lambda: ({"wordnet": source}, {"wordnet": True}, {}))
    receipt = healing_resources.provenance()
    assert receipt["state"] == "unverified_cache"
    assert receipt["files"]["wordnet"]["identity_scope"] == "current_source_only"


def test_unloaded_resource_can_resnapshot_before_first_use(monkeypatch):
    _reset(monkeypatch)
    source = {"state": "missing", "path": "/fixture/words", "sha256": None}
    monkeypatch.setattr(healing_resources, "_resources", lambda: ({"wordnet": dict(source)}, {"wordnet": False}, {}))
    healing_resources.provenance()
    source.update(state="read", sha256="newly-present")
    receipt = healing_resources.provenance()
    assert receipt["state"] == "read"
    assert receipt["files"]["wordnet"]["snapshot"]["sha256"] == "newly-present"


def test_missing_and_directory_resources_remain_named(tmp_path: Path):
    absent = healing_resources._file(tmp_path / "not-downloaded")
    assert absent["state"] == "missing" and absent["sha256"] is None
    directory = healing_resources._file(tmp_path)
    assert directory["state"] == "unread" and directory["reason"] == "unhashed_directory"
