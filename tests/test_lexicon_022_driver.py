"""The recorded round uses the verified model name/digest, never a metadata dict."""

from importlib import import_module

import pytest

driver = import_module("docs.readings.2026-11-13-ssl-explicit-genera.coherence_022")


def test_live_round_command_preserves_native_model_identity_and_context(monkeypatch):
    model = {"name": "fixture:verified-model", "digest": "f" * 64}
    calls = []
    monkeypatch.setattr(driver, "read", lambda path: {"source_sha256": {}} if "verification" in path.name else {"model": model})
    monkeypatch.setattr(driver.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    driver.invoke("run")
    [command] = [c for c, _ in calls]
    assert command[command.index("--model") + 1] == model["name"]
    assert command[command.index("--model-digest") + 1] == model["digest"]
    assert command[command.index("--model-context-tokens") + 1] == "81920"
    assert calls[0][1] == {"cwd": driver.ROOT, "check": True}


def test_changed_pinned_implementation_refuses_before_any_cli_or_model(monkeypatch):
    calls = []
    monkeypatch.setattr(driver, "read", lambda path: {"source_sha256": {"changed.py": "a" * 64}})
    monkeypatch.setattr(driver, "fingerprint", lambda path: "b" * 64)
    monkeypatch.setattr(driver.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="LITERAL_GENUS_FROZEN_SOURCE_CHANGED:changed.py"):
        driver.invoke("run")
    assert calls == []
