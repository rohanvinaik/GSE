"""Question evidence survives rejection/interruption without becoming a value."""

import copy
import json
import sqlite3

import pytest

from GSE.curation.lexicon_builder.epoch import EpochTransportRefusal, JournaledTransport
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.learning_state import LearningState
from GSE.curation.lexicon_builder.residual import _request_id
from GSE.namespace import identity_form


def question(bank="WANT"):
    return {
        "format": "GSE.bank-request/2",
        "entry_id": "synthetic:question",
        "bank": bank,
        "known": {},
        "allowed_values": [-1, 0, 1],
        "definition": {"entry_id": "synthetic:question", "definition": "Synthetic archival fixture."},
        "observations": [
            {
                "source": "synthetic",
                "features": {
                    "format": "GSE.synthetic-evidence/1",
                    "full_context": "Original source evidence. " * 4096,
                },
            }
        ],
        "scaffold": {"domains": {bank: [-1, 0, 1]}, "proof_trace": []},
        "future_field": [0, False, None, "", -1, 1],
    }


def schema(bank="WANT"):
    return {
        "type": "object",
        "properties": {bank: {"enum": [-1, 0, 1, None]}},
        "required": [bank],
        "additionalProperties": False,
    }


def test_full_bank_questions_share_source_and_proof_records_and_restore_exactly(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "archive-fixture"})
    originals, references, proof = [], [], []
    for index, bank in enumerate(BANKS):
        payload = question(bank)
        proof.append({"kind": "SYNTHETIC_PROOF", "ordinal": index, "evidence": "Unchanged proof. " * 128})
        payload["scaffold"]["proof_trace"] = [*proof, proof[0]]
        untouched = copy.deepcopy(payload)
        ref = state.archive_request(payload, schema(bank), "fixture:typed-bank")
        assert payload == untouched
        assert ref == state.archive_request(payload, schema(bank), "fixture:typed-bank")
        restored = state.request(ref)
        assert restored["request"] == payload and restored["schema"] == schema(bank)
        assert restored["request_id"] == _request_id(payload)
        assert restored["request"]["future_field"][1] is False
        assert restored["request"]["future_field"][2] is None
        originals.append(payload)
        references.append(ref)
    with sqlite3.connect(state.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM learning_requests").fetchone()[0] == len(BANKS)
        contexts = [row[0] for row in conn.execute("SELECT payload FROM model_receipt_contexts")]
        stored = sum(map(len, contexts)) + sum(
            len(row[0]) for row in conn.execute("SELECT payload FROM learning_requests")
        )
        assert stored < sum(len(json.dumps(payload)) for payload in originals) / 10
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='accepted_model_receipts'").fetchone() is None
    # Callers cannot mutate another archived request via a shared Python object.
    changed = state.request(references[0])
    changed["request"]["observations"].clear()
    assert state.request(references[0])["request"] == originals[0]


def test_namespace_equivalence_keeps_both_original_literal_inputs(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "aliases"})
    modern = question()
    legacy = identity_form(modern)
    first = state.archive_request(modern, schema(), "fixture")
    second = state.archive_request(legacy, schema(), "fixture")
    assert first != second
    assert state.request(first)["request"] == modern
    assert state.request(second)["request"] == legacy
    assert state.request(first)["request_id"] == state.request(second)["request_id"]
    assert state.request(second)["literal_fallback"] is not None


@pytest.mark.parametrize("damage", ["missing_context", "changed_context", "changed_envelope"])
def test_question_context_damage_is_refused_without_model_authority(tmp_path, damage):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "damage"})
    ref = state.archive_request(question(), schema(), "fixture")
    with sqlite3.connect(state.path) as conn:
        encoded = json.loads(
            conn.execute("SELECT payload FROM learning_requests WHERE archive_sha256=?", (ref,)).fetchone()[0]
        )
        context = encoded["request"]["contexts"]["observations"]
        if damage == "missing_context":
            conn.execute("DELETE FROM model_receipt_contexts WHERE context_sha256=?", (context,))
            expected = "MISSING_MODEL_RECEIPT_CONTEXT"
        elif damage == "changed_context":
            conn.execute("UPDATE model_receipt_contexts SET payload='[]' WHERE context_sha256=?", (context,))
            expected = "MODEL_RECEIPT_CONTEXT_HASH_MISMATCH"
        else:
            encoded["schema"] = {}
            conn.execute("UPDATE learning_requests SET payload=? WHERE archive_sha256=?", (json.dumps(encoded), ref))
            expected = "LEARNING_QUESTION_HASH_MISMATCH"
    with pytest.raises(ValueError, match=expected):
        state.request(ref)


def test_interrupted_model_keeps_its_full_original_question_and_budget_slot(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "interrupted"})
    payload, output = question(), schema()
    calls = []

    class Interrupted:
        identity = "fixture:interrupted"

        def __call__(self, current, current_schema):
            calls.append(current)
            [path] = tmp_path.glob("teach-*.intent.json")
            intent = json.loads(path.read_text())
            archived = state.request(intent["request_archive"])
            assert archived["request"] == payload and archived["schema"] == output
            raise RuntimeError("simulated termination")

    transport = JournaledTransport(Interrupted(), tmp_path, "teach", 1, tmp_path / "model.lock", context_store=state)
    with pytest.raises(RuntimeError, match="simulated termination"):
        transport(payload, output)
    assert transport.count() == len(calls) == 1
    assert not list(tmp_path.glob("teach-*.result.json"))
    with pytest.raises(EpochTransportRefusal, match="EPOCH_INTERRUPTED_MODEL_ATTEMPT"):
        transport(payload, output)
    assert len(calls) == 1


def test_cached_reply_verifies_context_and_reuses_namespace_equivalent_question(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "cached"})
    calls = []

    class Answer:
        identity = "fixture:cached"

        def __call__(self, payload, output):
            calls.append(payload)
            return '{"WANT":null}'

    transport = JournaledTransport(Answer(), tmp_path, "teach", 1, tmp_path / "model.lock", context_store=state)
    assert transport(question(), schema()) == '{"WANT":null}'
    assert transport(identity_form(question()), schema()) == '{"WANT":null}'
    assert len(calls) == 1
    [path] = tmp_path.glob("teach-*.intent.json")
    intent = json.loads(path.read_text())
    assert state.request(intent["request_archive"])["request"] == question()
    with sqlite3.connect(state.path) as conn:
        conn.execute("DELETE FROM model_receipt_contexts")
    with pytest.raises(ValueError, match="MISSING_MODEL_RECEIPT_CONTEXT"):
        transport(question(), schema())
    assert len(calls) == 1
