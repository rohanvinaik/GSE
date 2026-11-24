"""Delayed exact wire authority uses ordinary writer/history, never answer rebinding."""

import copy
import json
import sqlite3

import pytest
from test_lexicon_builder_rule_migration import packet

from GSE.curation.lexicon_builder import completion
from GSE.curation.lexicon_builder.epoch import make_questions
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.rule_history import digest, relation_records
from GSE.curation.lexicon_builder.rule_migration import migrate_rule
from GSE.curation.lexicon_builder.validation import _metadata, _relations, validate_build


class ExactTransport:
    identity = "delayed-98K-fixture-not-linguistic-authority"

    def __init__(self, request, value=1):
        self.request, self.value, self.calls = request, value, 0

    def __call__(self, payload, schema):
        assert payload == self.request["request"]
        assert schema == self.request["schema"]
        self.calls += 1
        return json.dumps({payload["bank"]: self.value})


def prepared(tmp_path, entry="b"):
    path, input_path, audit_path, review = packet(tmp_path)
    request = make_questions(path, ((entry, "HERE"),))[0]
    with sqlite3.connect(path) as conn:
        version = digest(relation_records(_relations(_metadata(conn, "relations"))))
    raw = {
        "rule_version": version,
        "request_id": request.request_id,
        "request": request.payload(),
        "schema": request.output_schema(),
    }
    output = tmp_path / "migrated.db"
    migrate_rule(path, output, input_path, audit_path, review)
    return output, raw


def write(path, raw, transport):
    pair = (raw["request"]["entry_id"], "HERE")
    return completion.complete_dictionary(
        path,
        transport,
        1,
        entry_bank_questions=(pair,),
        historical_questions={pair: raw},
        continue_cohorts=True,
        max_calls_per_entry=1,
    )


def test_delayed_unaffected_request_preserves_wire_version_model_and_resumes(tmp_path):
    path, raw = prepared(tmp_path)
    transport = ExactTransport(raw)
    result = write(path, raw, transport)
    assert result["outcomes"] == {"ASSIGNED": 1}
    assert transport.calls == 1
    with sqlite3.connect(path) as conn:
        receipt = read_model_receipts(conn)["b"][-1]
        assert receipt["request_id"] == raw["request_id"]
        assert receipt["request"] == raw["request"]
        assert receipt["assertion"]["source"] == "model:" + transport.identity
        assert (
            conn.execute("SELECT version FROM model_rule_versions WHERE request_id=?", (raw["request_id"],)).fetchone()[
                0
            ]
            == raw["rule_version"]
        )
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    resumed = write(path, raw, transport)
    assert resumed["model_calls"] == 0
    assert transport.calls == 1


@pytest.mark.parametrize("change", ["definition", "observations", "schema", "request_id", "version"])
def test_changed_complete_input_fails_before_transport(tmp_path, change):
    path, raw = prepared(tmp_path)
    raw = copy.deepcopy(raw)
    if change == "definition":
        raw["request"]["definition"]["definition"] = "changed"
    elif change == "observations":
        raw["request"]["observations"] = []
    elif change == "schema":
        raw["schema"]["additionalProperties"] = True
    elif change == "request_id":
        raw["request_id"] = "0" * 64
    else:
        raw["rule_version"] = "0" * 64
    transport = ExactTransport(raw)
    with pytest.raises(ValueError, match="HISTORICAL_MODEL"):
        write(path, raw, transport)
    assert transport.calls == 0
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_even_unchanged_target_marginal_is_refused_inside_changed_scope(tmp_path):
    path, raw = prepared(tmp_path, "c")
    transport = ExactTransport(raw)
    with pytest.raises(ValueError, match="HISTORICAL_MODEL_CONTEXT_AFFECTED"):
        write(path, raw, transport)
    assert transport.calls == 0


def test_null_is_journaled_not_zero_and_never_repeated(tmp_path):
    path, raw = prepared(tmp_path)
    transport = ExactTransport(raw, None)
    assert write(path, raw, transport)["outcomes"] == {"ABSTAINED": 1}
    assert write(path, raw, transport)["model_calls"] == 0
    assert transport.calls == 1
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_binding_failure_rolls_back_value_and_receipt_but_reserves_running(tmp_path, monkeypatch):
    path, raw = prepared(tmp_path)
    transport = ExactTransport(raw)
    original = completion.receipt_binding_key

    def crash(receipt):
        raise RuntimeError("crash after receipt before binding")

    monkeypatch.setattr(completion, "receipt_binding_key", crash)
    with pytest.raises(RuntimeError, match="crash after receipt"):
        write(path, raw, transport)
    monkeypatch.setattr(completion, "receipt_binding_key", original)
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    assert write(path, raw, transport)["model_calls"] == 0
    assert transport.calls == 1
    with sqlite3.connect(path) as conn:
        assert all(row["request_id"] != raw["request_id"] for row in read_model_receipts(conn)["b"])
        assert (
            conn.execute("SELECT code FROM completion_attempts WHERE request_id=?", (raw["request_id"],)).fetchone()[0]
            == "RUNNING"
        )
