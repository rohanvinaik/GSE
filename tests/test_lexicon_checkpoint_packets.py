"""Retained checkpoint evidence cannot be rebound to a new wire or model."""

import json
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

from GSE.curation.lexicon_builder.epoch import fingerprint
from GSE.curation.lexicon_builder.residual import OllamaTransport, _request_id


@pytest.fixture
def packet_fixture(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Retained packet reader must not contact a model")

    monkeypatch.setattr(OllamaTransport, "pin", forbidden)
    monkeypatch.setattr(OllamaTransport, "__call__", forbidden)
    helper = (
        Path(__file__).resolve().parents[1]
        / "docs/readings/2026-11-13-ssl-explicit-genera/ssl_api_checkpoint_packets.py"
    )
    module = runpy.run_path(str(helper))
    config = {
        "model": "synthetic:local",
        "timeout_seconds": 60,
        "context_tokens": 98304,
        "thinking": False,
        "output_tokens": 256,
        "artifact": {"model": "synthetic:local", "digest": "a" * 64},
    }
    protocol = OllamaTransport(
        config["model"], timeout=60, context_tokens=98304, thinking=False, output_tokens=256
    )._protocol_digest
    config["identity"] = f"{config['model']}#{config['artifact']['digest']}@{protocol}"
    payload = {"entry_id": "synthetic:exact-native-sense", "bank": "HERE", "allowed_values": [-1, 0, 1]}
    schema = {"properties": {"HERE": {"enum": [-1, 0, 1, None]}}}
    identity = _request_id(payload)
    packet = {
        "format": "GSE.ssl-checkpoint-local-questions/1",
        "coordinates": [[payload["entry_id"], payload["bank"]]],
        "questions": [{"request_id": identity, "request": payload, "schema": schema}],
    }
    answers = {
        "format": "GSE.ssl-checkpoint-local-answers/1",
        "transport": config["identity"],
        "answers": [{"request_id": identity, "raw_output": '{"HERE":null}'}],
    }
    paths = tmp_path / "packet.json", tmp_path / "answers.json"

    def save():
        paths[0].write_text(json.dumps(packet))
        answers["questions_sha256"] = fingerprint(paths[0])
        paths[1].write_text(json.dumps(answers))

    save()
    return module, config, packet, answers, paths, save


def test_exact_packet_preserves_null_and_never_calls_service(packet_fixture):
    module, config, packet, _, paths, _ = packet_fixture
    model = module["PacketTransport"](*paths, {"configuration": config})
    row = packet["questions"][0]
    assert model(row["request"], row["schema"]) == '{"HERE":null}'
    assert model.replayed == [row["request_id"]]
    for payload, schema in [({**row["request"], "bank": "I"}, row["schema"]), (row["request"], {})]:
        with pytest.raises(ValueError, match="FRESH_QUESTION_CHANGED"):
            model(payload, schema)


@pytest.mark.parametrize("damage", ["context", "model", "packet", "coordinate", "request", "duplicate", "raw_type"])
def test_packet_identity_tampering_fails_closed(packet_fixture, damage):
    module, config, packet, answers, paths, save = packet_fixture
    if damage == "context":
        config["context_tokens"] = 65536
    elif damage == "model":
        answers["transport"] = "synthetic:other"
    elif damage == "packet":
        answers["questions_sha256"] = "0" * 64
        paths[1].write_text(json.dumps(answers))
    elif damage == "coordinate":
        packet["coordinates"][0][1] = "I"
    elif damage == "request":
        packet["questions"][0]["request"]["bank"] = "I"
    elif damage == "duplicate":
        answers["answers"].append(deepcopy(answers["answers"][0]))
    else:
        answers["answers"][0]["raw_output"] = None
    if damage != "packet":
        save()
    with pytest.raises(ValueError, match="CHECKPOINT_PACKET_"):
        module["PacketTransport"](*paths, {"configuration": config})


def test_missing_answer_is_not_a_semantic_null(packet_fixture):
    module, config, packet, answers, paths, save = packet_fixture
    answers["answers"] = []
    save()
    model = module["PacketTransport"](*paths, {"configuration": config})
    row = packet["questions"][0]
    with pytest.raises(ValueError, match="EXACT_REPLY_MISSING"):
        model(row["request"], row["schema"])
    assert model.replayed == []


def test_packet_set_refuses_mixed_models_and_duplicate_questions(packet_fixture):
    module, config, _, _, paths, _ = packet_fixture
    model = module["PacketTransport"](*paths, {"configuration": config})
    with pytest.raises(ValueError, match="DUPLICATE_QUESTION"):
        module["PacketSet"]([model, model])
    other = deepcopy(model)
    other.identity = "synthetic:old-65K-protocol"
    with pytest.raises(ValueError, match="MIXED_TRANSPORT_IDENTITIES"):
        module["PacketSet"]([model, other])
