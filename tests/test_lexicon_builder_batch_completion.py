"""Batched transport retains independent, durable single-bank adjudication."""

import json
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import asdict
from functools import partial

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import DomainRestriction, Relation, propagate
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.residual import ModelTransportError
from GSE.curation.lexicon_builder.validation import validate_build


class BatchTransport:
    identity = "batch-fixture:typed-protocol"
    prepare: Callable[[tuple], object] | None = None

    def __init__(self, answer=None):
        self.answer = answer
        self.batches = []

    def pin(self):
        return {"model": self.identity, "digest": "a" * 64}

    def __call__(self, payload, schema):
        pytest.fail("batch completion dispatched an individual transport call")

    def callable_batch(self, items):
        self.batches.append(items)
        assert len({payload["entry_id"] for payload, _ in items}) == len(items)
        if self.answer is not None:
            return self.answer(items)
        return tuple(json.dumps({payload["bank"]: payload["allowed_values"][-1]}) for payload, _ in items)


def dictionary(tmp_path, count=3, banks=("GOOD",), manifest=None):
    definitions, observations, restrictions = [], [], []
    for index in range(count):
        entry, record = f"entry:{index}", f"native:{index}"
        definitions.append(Definition(entry, entry, "verb", "explicit synthetic batch fixture"))
        observations.append(Observation(entry, "fixture", record, "fixture", {"index": index}, "lexical"))
        # Fixture zeros are explicit source restrictions, never a production default.
        restrictions.extend(
            DomainRestriction(bank, (-1, 1) if bank in banks else (0,), "fixture", record, "fixture") for bank in BANKS
        )
    path = tmp_path / "batch.db"
    build_dictionary(
        EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions)), path, manifest=manifest
    )
    return path


def states(path):
    with sqlite3.connect(path) as conn:
        return {
            entry: (code, json.loads(domains))
            for entry, code, domains in conn.execute("SELECT entry_id,code,domains FROM definition_states")
        }


def attempts(path):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT entry_id,bank,code FROM completion_attempts ORDER BY entry_id,bank").fetchall()


def metadata(path, key):
    with sqlite3.connect(path) as conn:
        return json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchone()[0])


def test_all_running_items_commit_before_batch_and_each_acceptance_replays(tmp_path):
    path = dictionary(tmp_path)

    def observe(items):
        assert {(entry, bank) for entry, bank, code in attempts(path) if code == "RUNNING"} == {
            (payload["entry_id"], payload["bank"]) for payload, _ in items
        }
        assert metadata(path, "last_report")["model_calls"] == len(items)
        assert all(state[1]["GOOD"] == [-1, 1] for state in states(path).values())
        return tuple(json.dumps({payload["bank"]: 1}) for payload, _ in items)

    transport = BatchTransport(observe)
    report = complete_dictionary(path, transport, 3, batch_size=3, banks=("GOOD",))
    assert report["model_calls"] == 3
    assert report["transport_invocations"] == len(transport.batches) == 1
    assert report["batch_size"] == 3
    assert report["outcomes"] == {"ASSIGNED": 3}
    assert report["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert metadata(path, "last_completion_report") == report
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0] == 3
        assert conn.execute("SELECT count(*) FROM builder_domain_restrictions").fetchone()[0] == 3 * len(BANKS)
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_budget_counts_questions_and_batches_have_distinct_definitions(tmp_path):
    path = dictionary(tmp_path, 5)
    transport = BatchTransport()
    report = complete_dictionary(path, transport, 3, batch_size=2, banks=("GOOD",))
    assert [len(items) for items in transport.batches] == [2, 1]
    assert report["model_calls"] == 3
    assert report["transport_invocations"] == 2
    assert sum(state[1]["GOOD"] == [1] for state in states(path).values()) == 3
    assert report["dictionary_status"] == "INCOMPLETE"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_later_bank_uses_its_definitions_new_known_values(tmp_path):
    path = dictionary(tmp_path, 2, ("GOOD", "WANT"))

    def answer(items):
        result = []
        for payload, _ in items:
            sign = 1 if payload["entry_id"] == "entry:0" else -1
            if payload["bank"] == "WANT":
                assert payload["known"]["GOOD"] == sign
            result.append(json.dumps({payload["bank"]: sign}))
        return tuple(result)

    transport = BatchTransport(answer)
    report = complete_dictionary(path, transport, 4, batch_size=2, max_calls_per_entry=2, banks=("GOOD", "WANT"))
    assert [[payload["bank"] for payload, _ in items] for items in transport.batches] == [
        ["GOOD", "GOOD"],
        ["WANT", "WANT"],
    ]
    assert report["model_calls"] == 4 and report["transport_invocations"] == 2
    assert states(path)["entry:0"][1]["GOOD"] == states(path)["entry:0"][1]["WANT"] == [1]
    assert states(path)["entry:1"][1]["GOOD"] == states(path)["entry:1"][1]["WANT"] == [-1]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("malformed", ['{"GOOD":true}', '{"GOOD":0}', '{"GOOD":1,"WANT":1}', "not json"])
def test_mixed_items_preserve_null_and_reject_only_malformed_cell(tmp_path, malformed):
    path = dictionary(tmp_path)
    before = states(path)
    transport = BatchTransport(lambda _: ('{"GOOD":1}', '{"GOOD":null}', malformed))
    report = complete_dictionary(path, transport, 3, batch_size=3, banks=("GOOD",))
    assert report["outcomes"] == {"ASSIGNED": 1, "ABSTAINED": 1, "INVALID_OUTPUT": 1}
    after = states(path)
    assert after["entry:0"][1]["GOOD"] == [1]
    assert after["entry:1"] == before["entry:1"]
    assert after["entry:2"] == before["entry:2"]
    assert all(state[1]["WANT"] == [0] for state in after.values())
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("output", [('{"GOOD":1}',), ['{"GOOD":1}', '{"GOOD":1}']])
def test_wrong_batch_shape_cannot_shift_answers_between_definitions(tmp_path, output):
    path = dictionary(tmp_path, 2)
    before = states(path)
    report = complete_dictionary(path, BatchTransport(lambda _: output), 2, batch_size=2)
    assert report["outcomes"] == {"TRANSPORT_ERROR": 2}
    assert report["transport_invocations"] == 1 and report["model_calls"] == 2
    assert states(path) == before
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_transport_exception_leaves_every_cell_unknown(tmp_path):
    path = dictionary(tmp_path)
    before = states(path)

    def fail(_):
        raise OSError("fixture batch transport unavailable")

    report = complete_dictionary(path, BatchTransport(fail), 3, batch_size=3)
    assert report["outcomes"] == {"TRANSPORT_ERROR": 3}
    assert report["model_calls"] == 3 and report["transport_invocations"] == 1
    assert states(path) == before
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_interruption_journals_whole_batch_and_requires_explicit_retry(tmp_path):
    path = dictionary(tmp_path)
    before = states(path)

    def interrupt(items):
        assert len(attempts(path)) == len(items) == 3
        assert {row[2] for row in attempts(path)} == {"RUNNING"}
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        complete_dictionary(path, BatchTransport(interrupt), 3, batch_size=3)
    assert states(path) == before
    assert metadata(path, "last_report")["model_calls"] == 3
    resumed = BatchTransport(lambda _: pytest.fail("interrupted requests repeated without retry"))
    report = complete_dictionary(path, resumed, 3, batch_size=3)
    assert report["model_calls"] == report["transport_invocations"] == 0
    assert report["skipped_attempts"] == {"RUNNING": 3}
    assert report["code"] == "RESIDUAL_REMAINS"
    retried = complete_dictionary(path, BatchTransport(), 3, batch_size=3, retry=True)
    assert retried["outcomes"] == {"ASSIGNED": 3}
    assert metadata(path, "last_report")["model_calls"] == 6
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_external_mutation_during_batch_prevents_all_semantic_writes(tmp_path):
    path = dictionary(tmp_path)
    before = states(path)

    def mutate(items):
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT INTO builder_metadata VALUES ('external-batch-marker','1')")
        return tuple(json.dumps({payload["bank"]: 1}) for payload, _ in items)

    with pytest.raises(ValueError, match="COMPLETION_SNAPSHOT_CHANGED"):
        complete_dictionary(path, BatchTransport(mutate), 3, batch_size=3)
    assert states(path) == before
    assert metadata(path, "external-batch-marker") == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM accepted_model_receipts").fetchone()[0] == 0
    assert {row[2] for row in attempts(path)} <= {"RUNNING", "STALE_SNAPSHOT"}


def test_receipt_failure_rolls_back_one_item_preserving_committed_prefix(tmp_path):
    path = dictionary(tmp_path)
    before = states(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TRIGGER reject_second_receipt BEFORE INSERT ON accepted_model_receipts "
            "WHEN NEW.entry_id='entry:1' BEGIN SELECT RAISE(ABORT,'fixture receipt failure'); END"
        )
    transport = BatchTransport()
    with pytest.raises(sqlite3.IntegrityError, match="fixture receipt failure"):
        complete_dictionary(path, transport, 3, batch_size=3)
    after = states(path)
    assert after["entry:0"][1]["GOOD"] == [1]
    assert after["entry:1"] == before["entry:1"] and after["entry:2"] == before["entry:2"]
    assert attempts(path) == [
        ("entry:0", "GOOD", "ASSIGNED"),
        ("entry:1", "GOOD", "RUNNING"),
        ("entry:2", "GOOD", "RUNNING"),
    ]
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT entry_id FROM accepted_model_receipts").fetchall() == [("entry:0",)]
    assert metadata(path, "last_report")["model_calls"] == 3
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_single_bank_validation_rejects_contradiction_inside_otherwise_valid_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "GSE.curation.lexicon_builder.resolution.propagate", partial(propagate, max_joint_assignments=7)
    )
    names = ("GOOD", "WANT", "THINK")
    relations = [
        Relation(
            f"fixture-cycle:{i}",
            (names[i], names[(i + 1) % 3]),
            ((-1, -1), (1, 1)) if i < 2 else ((-1, -1), (-1, 1), (1, -1)),
            ("synthetic satisfiable constraint cycle",),
            approved=True,
        )
        for i in range(3)
    ]
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps({"format": "gse.lexicon-rules/1", "relations": [asdict(r) for r in relations]}))
    path = dictionary(tmp_path, 2, names, manifest)
    before = states(path)
    report = complete_dictionary(
        path, BatchTransport(lambda _: ('{"GOOD":1}', '{"GOOD":-1}')), 2, batch_size=2, banks=("GOOD",)
    )
    assert report["outcomes"] == {"CONTRADICTION": 1, "ASSIGNED": 1}
    assert states(path)["entry:0"] == before["entry:0"]
    assert all(states(path)["entry:1"][1][bank] == [-1] for bank in names)
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_prepare_shrinks_group_without_dropping_question_context(tmp_path):
    path = dictionary(tmp_path)
    transport = BatchTransport()
    prepared = []

    def prepare(items):
        prepared.append(items)
        if len(items) > 1:
            raise ModelTransportError("BATCH_INPUT_TOO_LARGE")

    transport.prepare = prepare
    report = complete_dictionary(path, transport, 3, batch_size=3)
    assert [len(items) for items in transport.batches] == [1, 1, 1]
    assert report["model_calls"] == report["transport_invocations"] == 3
    originals = {payload["entry_id"]: payload for payload, _ in prepared[0]}
    assert {payload["entry_id"]: payload for items in transport.batches for payload, _ in items} == originals
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_oversized_question_is_journaled_without_transport_and_later_entries_continue(tmp_path):
    path = dictionary(tmp_path)
    before = states(path)
    transport = BatchTransport()

    def prepare(items):
        if any(payload["entry_id"] == "entry:0" for payload, _ in items):
            raise ModelTransportError("BATCH_INPUT_TOO_LARGE")

    transport.prepare = prepare
    report = complete_dictionary(path, transport, 3, batch_size=3)
    assert report["model_calls"] == 3 and report["transport_invocations"] == 1
    assert report["outcomes"] == {"TRANSPORT_ERROR": 1, "ASSIGNED": 2}
    assert [[payload["entry_id"] for payload, _ in items] for items in transport.batches] == [["entry:1", "entry:2"]]
    assert states(path)["entry:0"] == before["entry:0"]
    assert all(state[1]["WANT"] == [0] for state in states(path).values())
    with sqlite3.connect(path) as conn:
        code, raw = conn.execute("SELECT code,details FROM completion_attempts WHERE entry_id='entry:0'").fetchone()
        assert code == "TRANSPORT_ERROR"
        details = json.loads(raw)
        assert details["transport_started"] is False
        assert details["reason"] == "BATCH_INPUT_TOO_LARGE"
        assert conn.execute("SELECT count(*) FROM accepted_model_receipts WHERE entry_id='entry:0'").fetchone()[0] == 0
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_all_prepare_refusals_use_no_transport_and_do_not_repeat_without_retry(tmp_path):
    path = dictionary(tmp_path, 1)
    before = states(path)
    transport = BatchTransport()

    def prepare(_):
        raise ModelTransportError("BATCH_INPUT_TOO_LARGE")

    transport.prepare = prepare
    report = complete_dictionary(path, transport, 1, batch_size=2)
    assert report["model_calls"] == 1 and report["transport_invocations"] == 0
    assert report["outcomes"] == {"TRANSPORT_ERROR": 1}
    assert transport.batches == [] and states(path) == before
    resumed = BatchTransport(lambda _: pytest.fail("unchanged refused question dispatched"))
    again = complete_dictionary(path, resumed, 1, batch_size=2)
    assert again["model_calls"] == again["transport_invocations"] == 0
    assert again["skipped_attempts"] == {"TRANSPORT_ERROR": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("batch_size", [None, True, 0, -1, 1.5, "2"])
def test_invalid_batch_size_is_rejected_before_file_or_transport_access(tmp_path, batch_size):
    with pytest.raises(ValueError, match="BATCH"):
        complete_dictionary(tmp_path / "absent.db", BatchTransport(), 1, batch_size=batch_size)


def test_resolved_scope_does_not_create_phantom_batch(tmp_path):
    path = dictionary(tmp_path, 2, banks=())
    transport = BatchTransport(lambda _: pytest.fail("resolved scope reached model"))
    report = complete_dictionary(path, transport, 2, batch_size=2)
    assert report["model_calls"] == report["transport_invocations"] == 0
    assert report["code"] == "SELECTED_SCOPE_RESOLVED"
    assert transport.batches == []
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_real_cli_forwards_batch_size_and_reports_question_and_invocation_counts(tmp_path, monkeypatch, capsys):
    from GSE.curation.cli import commands
    from GSE.curation.lexicon_builder import model_batch, residual

    path = dictionary(tmp_path)
    transport = BatchTransport()
    monkeypatch.setattr(residual, "OllamaTransport", lambda *args, **kwargs: transport)

    def wrap(client, *, max_items):
        assert client is transport and max_items == 3
        return transport

    monkeypatch.setattr(model_batch, "OllamaBatchTransport", wrap)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gse",
            "--lexicon-db",
            str(path),
            "complete",
            "--priority",
            "constraint",
            "--model",
            transport.identity,
            "--max-model-calls",
            "3",
            "--batch-size",
            "3",
            "--bank",
            "GOOD",
        ],
    )
    commands.main()
    report = json.loads(capsys.readouterr().out)
    assert report["model_calls"] == 3 and report["transport_invocations"] == 1
    assert report["batch_size"] == 3
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
