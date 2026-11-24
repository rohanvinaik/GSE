"""Typed second-provider replay preserves provenance, abstentions and bounds."""

import copy
import importlib
import json

import pytest

from GSE.curation.lexicon_builder.residual import _request_id

adjudication = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.adjudicate_vertebrate_021")


def fixture():
    payloads = [{"entry_id": f"word:{i}", "bank": "BODY"} for i in range(5)]
    schema = {"type": "object", "properties": {"BODY": {"enum": [-1, 0, 1, None]}}, "required": ["BODY"]}
    native = [
        {
            "entry_id": p["entry_id"],
            "request_id": _request_id(p),
            "schema": schema,
            "raw_output": json.dumps({"BODY": 0 if i == 1 else 1}),
            "transport": "native",
            "sign": 0 if i == 1 else 1,
        }
        for i, p in enumerate(payloads)
    ]
    correction = {
        native[1]["request_id"]: {
            "entry_id": native[1]["entry_id"],
            "raw_output": '{"BODY":1}',
            "transport": "typed-cli",
        }
    }
    return (
        payloads,
        schema,
        {
            "format": "GSE.source-adjudicated-bank-rulings/1",
            "native_questions": native,
            "corrections": correction,
            "unique_bank_questions": 5,
            "actual_bank_questions": 6,
        },
    )


def test_replay_uses_exact_ruling_and_preserves_original_disagreement():
    payloads, schema, manifest = fixture()
    before = copy.deepcopy(manifest)
    replay = adjudication.RulingReplay(manifest)
    assert replay(payloads[1], schema) == '{"BODY":1}'
    assert json.loads(replay(payloads[2], schema)) == {"BODY": 1}
    assert manifest == before and manifest["native_questions"][1]["sign"] == 0


@pytest.mark.parametrize("fault", ["count", "foreign", "extra", "boolean"])
def test_manifest_refuses_wrong_counts_foreign_or_malformed_rulings(fault):
    _, _, manifest = fixture()
    chosen = next(iter(manifest["corrections"].values()))
    if fault == "count":
        manifest["actual_bank_questions"] = 5
    elif fault == "foreign":
        chosen["entry_id"] = "other-definition"
    elif fault == "extra":
        chosen["raw_output"] = '{"BODY":1,"BE":0}'
    else:
        chosen["raw_output"] = '{"BODY":true}'
    with pytest.raises(ValueError):
        adjudication.RulingReplay(manifest)


def test_stale_question_or_schema_never_gets_a_value():
    payloads, schema, manifest = fixture()
    replay = adjudication.RulingReplay(manifest)
    with pytest.raises(ValueError, match="QUESTION_OR_SCHEMA_MISMATCH"):
        replay({**payloads[1], "other_context": True}, schema)
    with pytest.raises(ValueError, match="QUESTION_OR_SCHEMA_MISMATCH"):
        replay(payloads[1], {"type": "object"})


def test_null_remains_unresolved_and_is_never_zero():
    payloads, schema, manifest = fixture()
    next(iter(manifest["corrections"].values()))["raw_output"] = '{"BODY":null}'
    replay = adjudication.RulingReplay(manifest)
    assert adjudication.ruling(replay(payloads[1], schema)) is None
