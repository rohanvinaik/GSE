"""Completion CLI forwards explicit context budgets through the real transport contract."""

import json
import sys

import pytest

from gse.curation.cli import commands
from gse.curation.lexicon_builder import completion, residual


def argv(tmp_path, options=()):
    # Only the parser's file-existence gate is exercised; no corpus is opened.
    path = tmp_path / "fixture.db"
    path.touch()
    return [
        "gse",
        "--lexicon-db",
        str(path),
        "complete",
        "--model",
        "fixture:context-budget",
        "--max-model-calls",
        "1",
        *options,
    ]


@pytest.mark.parametrize("explicit,expected", [(None, 32768), ("65536", 65536), ("2049", 2049)])
def test_real_cli_preserves_default_or_forwards_explicit_context(tmp_path, monkeypatch, capsys, explicit, expected):
    original = residual.OllamaTransport
    constructors, pinned, completed = [], [], []

    def transport_factory(model, **kwargs):
        constructors.append(kwargs)
        return original(model, **kwargs)

    def pin(transport):
        pinned.append(transport)
        return {"model": transport.model, "digest": "f" * 64}

    def complete(path, transport, max_model_calls, **kwargs):
        completed.append(transport)
        assert max_model_calls == 1
        assert transport.context_tokens == expected
        return {"code": "CLI_FIXTURE_ONLY"}

    monkeypatch.setattr(residual, "OllamaTransport", transport_factory)
    monkeypatch.setattr(original, "pin", pin)
    monkeypatch.setattr(completion, "complete_dictionary", complete)
    options = () if explicit is None else ("--model-context-tokens", explicit)
    monkeypatch.setattr(sys, "argv", argv(tmp_path, options))
    commands.main()
    assert constructors == ([{}] if explicit is None else [{"context_tokens": expected}])
    assert pinned == completed and len(completed) == 1
    assert json.loads(capsys.readouterr().out) == {"code": "CLI_FIXTURE_ONLY"}


@pytest.mark.parametrize(
    "options,code",
    [
        (("--model-context-tokens", "0"), "invalid_context_tokens"),
        (("--model-context-tokens", "-1"), "invalid_context_tokens"),
        (("--model-context-tokens", "2047"), "invalid_context_tokens"),
        (("--model-context-tokens", "2048"), "invalid_output_tokens"),
        (("--model-context-tokens", "4096", "--model-output-tokens", "3072"), "invalid_output_tokens"),
    ],
)
def test_invalid_budget_uses_transport_contract_before_pin_or_completion(tmp_path, monkeypatch, options, code):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid context reached model pinning or corpus completion")

    monkeypatch.setattr(residual.OllamaTransport, "pin", forbidden)
    monkeypatch.setattr(completion, "complete_dictionary", forbidden)
    monkeypatch.setattr(sys, "argv", argv(tmp_path, options))
    with pytest.raises(ValueError, match=f"^{code}$"):
        commands.main()


@pytest.mark.parametrize("value", ["65536.0", "true", "not-a-number"])
def test_noninteger_context_is_refused_by_real_parser(tmp_path, monkeypatch, capsys, value):
    monkeypatch.setattr(sys, "argv", argv(tmp_path, ("--model-context-tokens", value)))
    with pytest.raises(SystemExit) as failure:
        commands.main()
    assert failure.value.code == 2
    assert "--model-context-tokens: invalid int value" in capsys.readouterr().err
