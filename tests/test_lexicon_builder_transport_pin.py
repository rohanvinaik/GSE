"""Artifact identity and bounded transport failures through the real adapter."""

import json
import sys
from email.message import Message
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from GSE.curation.lexicon_builder.engine import propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.residual import (
    ModelTransportError,
    OllamaTransport,
    build_request,
    complete_bank,
)


def request():
    return build_request(
        "fixture:want",
        "WANT",
        propagate(("WANT",), (), ()),
        (),
        definition=Definition("fixture:want", "want", "verb", "feel a desire for"),
    )


def envelope(value):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(value).encode()
    return response


def tags(digest="a" * 64):
    return envelope({"models": [{"name": "fixture-model", "digest": digest}]})


def test_constructor_is_network_free_and_unpinned_generation_is_refused():
    with patch("GSE.curation.lexicon_builder.residual.urlopen") as opening:
        transport = OllamaTransport("fixture-model")
        question = request()
        result = complete_bank(question, ("WANT",), (), (), transport)
    opening.assert_not_called()
    assert result.code == "TRANSPORT_ERROR"
    assert result.details["reason"] == "MODEL_IDENTITY_NOT_PINNED"
    assert result.assertion is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"models": None},
        {"models": []},
        {"models": [{"name": "fixture-model", "digest": None}]},
        {"models": [{"name": "fixture-model", "digest": "bad"}]},
        {"models": [{"name": "fixture-model", "digest": "a" * 64}] * 2},
    ],
)
def test_bad_or_ambiguous_identity_cannot_pin(value):
    transport = OllamaTransport("fixture-model")
    before = transport.identity
    with patch("GSE.curation.lexicon_builder.residual.urlopen", return_value=envelope(value)):
        with pytest.raises(ModelTransportError):
            transport.pin()
    assert transport.model_digest is None
    assert transport.identity == before


def test_pin_checks_before_and_after_generation_and_retains_its_digest():
    responses = [tags(), tags(), envelope({"response": '{"WANT":-1}', "done_reason": "stop"}), tags()]
    question = request()
    transport = OllamaTransport("fixture-model", output_tokens=2048, timeout=300)
    with (
        patch("GSE.curation.lexicon_builder.residual.urlopen", side_effect=responses) as opening,
        patch("GSE.curation.llm.ollama_client.register_model"),
    ):
        assert transport.pin() == {"model": "fixture-model", "digest": "a" * 64}
        result = complete_bank(question, ("WANT",), (), (), transport)
    assert result.code == "ASSIGNED"
    assert result.assertion is not None
    assert result.assertion.value == -1
    assert "a" * 64 in result.assertion.source
    requests = [call.args[0] for call in opening.call_args_list]
    assert [item.full_url.rsplit("/", 1)[-1] for item in requests] == ["tags", "tags", "generate", "tags"]
    body = json.loads(requests[2].data)
    assert body["options"]["num_predict"] == 2048
    assert body["format"] == question.output_schema()
    assert all(call.kwargs["timeout"] == 300 for call in opening.call_args_list)


@pytest.mark.parametrize("when", ["before", "after"])
def test_changed_tag_refuses_the_answer_without_a_lexical_assignment(when):
    responses = (
        [tags(), tags("b" * 64)]
        if when == "before"
        else [tags(), tags(), envelope({"response": '{"WANT":0}'}), tags("b" * 64)]
    )
    transport = OllamaTransport("fixture-model")
    with patch("GSE.curation.lexicon_builder.residual.urlopen", side_effect=responses):
        transport.pin()
        result = complete_bank(request(), ("WANT",), (), (), transport)
    assert result.code == "TRANSPORT_ERROR"
    assert result.details["reason"] == "MODEL_IDENTITY_CHANGED"
    assert result.assertion is None
    assert result.resolution is not None
    assert result.resolution.assignments == {}


def test_repin_cannot_silently_accept_a_new_model():
    transport = OllamaTransport("fixture-model")
    with patch("GSE.curation.lexicon_builder.residual.urlopen", side_effect=[tags(), tags("b" * 64)]):
        transport.pin()
        before = transport.identity
        with pytest.raises(ModelTransportError, match="MODEL_IDENTITY_CHANGED"):
            transport.pin()
    assert transport.identity == before


@pytest.mark.parametrize("tokens", [0, -1, True, 1.5, "2048", 32769])
def test_output_budget_is_bounded_integer(tokens):
    with pytest.raises(ValueError, match="invalid_output_tokens"):
        OllamaTransport("fixture-model", output_tokens=tokens)


def test_output_budget_must_leave_room_for_context_and_changes_protocol_identity():
    with pytest.raises(ValueError, match="invalid_output_tokens"):
        OllamaTransport("fixture-model", context_tokens=2048, output_tokens=1024)
    assert OllamaTransport("fixture-model").identity != OllamaTransport("fixture-model", output_tokens=2048).identity


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("private context"), "MODEL_TIMEOUT"),
        (URLError("private endpoint"), "MODEL_CONNECTION_ERROR"),
        (HTTPError("http://private/secret", 500, "private", Message(), None), "MODEL_HTTP_ERROR"),
    ],
)
def test_named_network_errors_do_not_copy_sensitive_details(error, code):
    transport = OllamaTransport("fixture-model")
    with patch("GSE.curation.lexicon_builder.residual.urlopen", side_effect=[tags(), error]):
        transport.pin()
        result = complete_bank(request(), ("WANT",), (), (), transport)
    assert result.details == {"error_type": "ModelTransportError", "reason": code}
    assert result.assertion is None


def test_refusal_reason_survives_complete_bank_and_cannot_be_arbitrary_text():
    def refused(payload, schema):
        raise ModelTransportError("MODEL_CONTEXT_EXCEEDED")

    result = complete_bank(request(), ("WANT",), (), (), refused)
    assert result.details["reason"] == "MODEL_CONTEXT_EXCEEDED"
    with pytest.raises(ValueError, match="invalid_transport_error_code"):
        ModelTransportError("private request content")


@pytest.mark.parametrize("command", ["build", "complete"])
@pytest.mark.parametrize("no_thinking", [False, True])
def test_real_cli_pins_before_dispatch_and_forwards_explicit_limits(
    command, no_thinking, monkeypatch, capsys, tmp_path
):
    from GSE.curation.cli import commands
    from GSE.curation.lexicon_builder import completion, pipeline, residual

    events = []
    output_tokens = 128 if no_thinking else 2048

    class Adapter:
        def __init__(self, model, **options):
            assert model == "fixture-model"
            expected = {"output_tokens": output_tokens, "timeout": 300.0, "base_url": "http://fixture.invalid:11435"}
            if no_thinking:
                expected["thinking"] = False
            assert options == expected
            events.append("constructed")

        def pin(self):
            events.append("pinned")
            return {"model": "fixture-model", "digest": "a" * 64}

    def dispatch(*args, **kwargs):
        assert events == ["constructed", "pinned"]
        transport = kwargs.get("transport") if command == "build" else args[1]
        assert isinstance(transport, Adapter)
        events.append("dispatched")
        return {"code": "FIXTURE_DISPATCHED"}

    monkeypatch.setattr(residual, "OllamaTransport", Adapter)
    monkeypatch.setattr(pipeline, "load_evidence", lambda path: object())
    monkeypatch.setattr(pipeline, "build_dictionary", dispatch)
    monkeypatch.setattr(completion, "complete_dictionary", dispatch)
    arguments = [
        "gse",
        "--lexicon-db",
        str(tmp_path / "unused.db"),
        command,
        "--model",
        "fixture-model",
        "--max-model-calls",
        "1",
        "--model-output-tokens",
        str(output_tokens),
        "--model-timeout",
        "300",
        "--model-base-url",
        "http://fixture.invalid:11435",
    ]
    if no_thinking:
        arguments.append("--no-thinking")
    if command == "build":
        arguments.extend(["--evidence", str(tmp_path / "unused.json")])
    else:
        arguments.extend(["--priority", "constraint"])
        (tmp_path / "unused.db").write_bytes(b"dispatch fixture; no database operation")
    monkeypatch.setattr(sys, "argv", arguments)
    commands.main()
    assert json.loads(capsys.readouterr().out) == {"code": "FIXTURE_DISPATCHED"}
    assert events == ["constructed", "pinned", "dispatched"]
    if command == "build":
        assert not (tmp_path / "unused.db").exists()
    else:
        assert (tmp_path / "unused.db").read_bytes() == b"dispatch fixture; no database operation"
