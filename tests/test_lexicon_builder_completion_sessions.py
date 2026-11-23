"""Sustained completion reuses one validated snapshot without unbounded contexts."""

import json
import sqlite3
import sys

import pytest

from GSE.curation.lexicon_builder import completion
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import DomainRestriction
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.validation import validate_build


class Transport:
    identity = "session-fixture:pinned"

    def __init__(self, answer=1):
        self.answer = answer
        self.requests = []

    def pin(self):
        return {"model": self.identity, "digest": "a" * 64}

    def __call__(self, payload, schema):
        self.requests.append(payload)
        value = self.answer(payload) if callable(self.answer) else self.answer
        return json.dumps({payload["bank"]: value})


def dictionary(tmp_path, count=3, banks=("GOOD",), extra=()):
    definitions, observations, restrictions = [], [], []
    for index in range(count):
        entry = f"entry:{index}"
        record = f"native:{index}"
        definitions.append(Definition(entry, entry, "verb", "explicit synthetic session fixture"))
        observations.append(Observation(entry, "fixture", record, "fixture", {"index": index}, "lexical"))
        restrictions.extend(
            DomainRestriction(bank, (-1, 1) if bank in banks else (0,), "fixture", record, "fixture") for bank in BANKS
        )
    path = tmp_path / "session.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations) + extra, (), (), tuple(restrictions)), path)
    return path


def assignment(path, entry, bank="GOOD"):
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT p.value FROM primitive_values p JOIN definition_states d ON p.lexeme_id=d.lexeme_id WHERE d.entry_id=? AND p.primitive=?",
            (entry, bank),
        ).fetchone()
        return None if row is None else row[0]


def test_one_preflight_and_index_across_bounded_cohorts(tmp_path, monkeypatch):
    path = dictionary(tmp_path, 5)
    actual_validate, actual_index, actual_contexts = (
        completion.validate_build,
        completion._prepare_context_index,
        completion._contexts,
    )
    validations, indexes, contexts = [], [], []

    def validate(file):
        validations.append(file)
        return actual_validate(file)

    def index(conn):
        indexes.append(id(conn))
        return actual_index(conn)

    def context(conn, selected, *, indexed=False):
        contexts.append((id(conn), tuple(selected), indexed))
        return actual_contexts(conn, selected, indexed=indexed)

    monkeypatch.setattr(completion, "validate_build", validate)
    monkeypatch.setattr(completion, "_prepare_context_index", index)
    monkeypatch.setattr(completion, "_contexts", context)
    report = complete_dictionary(path, Transport(), 5, banks=("GOOD",), max_entries_per_pass=2, continue_cohorts=True)
    assert len(validations) == len(indexes) == 1
    assert [len(ids) for _, ids, _ in contexts] == [2, 2, 1]
    assert all(conn == indexes[0] and indexed for conn, _, indexed in contexts)
    assert report["model_calls"] == 5
    assert report["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert report["scheduling"]["cohorts_processed"] == 3
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_nulls_visit_every_bank_then_stop_without_consuming_huge_budget(tmp_path):
    path = dictionary(tmp_path, 5, ("GOOD", "WANT"))
    transport = Transport(None)
    report = complete_dictionary(
        path,
        transport,
        10**9,
        banks=("GOOD", "WANT"),
        max_calls_per_entry=1,
        max_entries_per_pass=2,
        continue_cohorts=True,
    )
    assert report["model_calls"] == 10
    assert report["outcomes"] == {"ABSTAINED": 10}
    assert len({(p["entry_id"], p["bank"]) for p in transport.requests}) == 10
    assert report["code"] == "RESIDUAL_REMAINS"
    assert report["scheduling"]["code"] == "NO_NEW_ATTEMPTS_IN_PASS"
    assert report["dictionary_status"] == "INCOMPLETE"
    assert report["dictionary_cells"]["unresolved"] == 10
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_sustained_matches_separate_invocations_request_by_request(tmp_path):
    separate_dir, sustained_dir = tmp_path / "separate", tmp_path / "sustained"
    separate_dir.mkdir()
    sustained_dir.mkdir()
    separate = dictionary(separate_dir, 3, ("GOOD", "WANT"))
    sustained = dictionary(sustained_dir, 3, ("GOOD", "WANT"))
    first, second = Transport(), Transport()
    for _ in range(6):
        complete_dictionary(separate, first, 1, max_calls_per_entry=1, banks=("GOOD", "WANT"))
    complete_dictionary(
        sustained,
        second,
        6,
        max_calls_per_entry=1,
        max_entries_per_pass=1,
        banks=("GOOD", "WANT"),
        continue_cohorts=True,
    )
    assert completion._json(first.requests) == completion._json(second.requests)
    snapshots = []
    for path in (separate, sustained):
        with sqlite3.connect(path) as conn:
            snapshots.append(conn.execute("SELECT * FROM definition_states ORDER BY entry_id").fetchall())
        assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    assert snapshots[0] == snapshots[1]


def test_budgeted_restart_resumes_untouched_definitions(tmp_path):
    path = dictionary(tmp_path)
    first = Transport()
    report = complete_dictionary(path, first, 2, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True)
    assert [p["entry_id"] for p in first.requests] == ["entry:0", "entry:1"]
    assert report["scheduling"]["cursor_after"][2] == "entry:1"
    second = Transport()
    resumed = complete_dictionary(path, second, 10, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True)
    assert [p["entry_id"] for p in second.requests] == ["entry:2"]
    assert resumed["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_interrupted_cohort_keeps_accepted_prefix_and_skips_running_request_on_restart(tmp_path):
    path = dictionary(tmp_path)

    def interrupt(payload):
        if payload["entry_id"] == "entry:1":
            raise KeyboardInterrupt()
        return 1

    with pytest.raises(KeyboardInterrupt):
        complete_dictionary(
            path, Transport(interrupt), 10, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True
        )
    assert assignment(path, "entry:0") == 1
    assert assignment(path, "entry:1") is None
    resumed = Transport()
    report = complete_dictionary(path, resumed, 10, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True)
    assert [p["entry_id"] for p in resumed.requests] == ["entry:2"]
    assert report["skipped_attempts"]["RUNNING"] >= 1
    assert report["scheduling"]["code"] == "NO_NEW_ATTEMPTS_IN_PASS"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_explicit_retry_applies_once_per_request_per_invocation(tmp_path):
    path = dictionary(tmp_path, 1)
    complete_dictionary(path, Transport(None), 1, banks=("GOOD",))
    transport = Transport(None)
    report = complete_dictionary(path, transport, 10**9, banks=("GOOD",), continue_cohorts=True, retry=True)
    assert report["model_calls"] == len(transport.requests) == 1
    assert report["scheduling"]["code"] == "NO_NEW_ATTEMPTS_IN_PASS"
    assert report["skipped_attempts"] == {"ABSTAINED": 1}
    assert assignment(path, "entry:0") is None


def test_no_eligible_cells_stops_without_a_phantom_cohort(tmp_path):
    path = dictionary(tmp_path, 1)
    complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    transport = Transport()
    report = complete_dictionary(path, transport, 10**9, banks=("GOOD",), continue_cohorts=True)
    assert transport.requests == []
    assert report["model_calls"] == 0
    assert report["scheduling"]["code"] == "NO_ELIGIBLE_ENTRIES"
    assert report["scheduling"]["cohorts_processed"] == 0


def test_changed_known_context_is_a_new_request_in_a_later_pass(tmp_path):
    path = dictionary(tmp_path, 1, ("GOOD", "WANT"))

    def answer(payload):
        return None if payload["bank"] == "GOOD" and payload["known"].get("WANT") != 1 else 1

    transport = Transport(answer)
    report = complete_dictionary(
        path, transport, 10, banks=("GOOD", "WANT"), max_calls_per_entry=1, continue_cohorts=True
    )
    assert [p["bank"] for p in transport.requests] == ["GOOD", "WANT", "GOOD"]
    assert report["model_calls"] == 3
    assert report["outcomes"] == {"ABSTAINED": 1, "ASSIGNED": 2}
    assert report["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_external_write_in_later_cohort_cannot_publish_its_ruling(tmp_path):
    path = dictionary(tmp_path)

    def answer(payload):
        if payload["entry_id"] == "entry:1":
            with sqlite3.connect(path) as conn:
                conn.execute("INSERT INTO builder_metadata VALUES ('external-marker','1')")
        return 1

    transport = Transport(answer)
    with pytest.raises(ValueError, match="COMPLETION_SNAPSHOT_CHANGED"):
        complete_dictionary(path, transport, 10, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True)
    assert [p["entry_id"] for p in transport.requests] == ["entry:0", "entry:1"]
    assert assignment(path, "entry:0") == 1
    assert assignment(path, "entry:1") is None
    assert assignment(path, "entry:2") is None
    with sqlite3.connect(path) as conn:
        assert (
            conn.execute("SELECT code FROM completion_attempts WHERE entry_id='entry:1'").fetchone()[0]
            == "STALE_SNAPSHOT"
        )


def test_indexed_and_scanned_contexts_are_byte_identical_and_index_is_temporary(tmp_path):
    extra = (
        Observation(
            None, "rating", "a:shared", "rating", {"native": [None, False, -1, 0, 1]}, "lexical", ("entry:1", "entry:0")
        ),
        Observation(None, "conceptnet", "z:world", "graph", {"relation": "association"}, "lexical", ("entry:0",)),
        Observation(None, "rating", "unlinked", "rating", {"raw": "retained"}, "lexical"),
    )
    path = dictionary(tmp_path, extra=extra)
    with sqlite3.connect(path) as conn:
        before = conn.execute("SELECT * FROM source_observations ORDER BY record_id").fetchall()
        completion._prepare_context_index(conn)
        for selected in ((), ("entry:0",), ("entry:1", "entry:0"), ("entry:2",)):
            scanned = completion._contexts(conn, selected)
            indexed = completion._contexts(conn, selected, indexed=True)
            assert completion._json(scanned[0]) == completion._json(indexed[0])
            assert scanned[1] == indexed[1]
        assert conn.execute("PRAGMA temp_store").fetchone()[0] == 1
        assert conn.execute("SELECT * FROM source_observations ORDER BY record_id").fetchall() == before
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='completion_context_targets'").fetchall() == []
    with sqlite3.connect(path) as conn:
        assert (
            conn.execute("SELECT name FROM sqlite_temp_master WHERE name='completion_context_targets'").fetchall() == []
        )


def test_restart_rebuilds_candidate_index_from_changed_native_context(tmp_path):
    extra = (Observation(None, "rating", "candidate", "rating", {"score": 1}, "lexical", ("entry:0",)),)
    path = dictionary(tmp_path, 2, extra=extra)
    complete_dictionary(path, Transport(None), 10, banks=("GOOD",), continue_cohorts=True)
    with sqlite3.connect(path) as conn:
        raw = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE record_id='candidate'").fetchone()[0]
        )
        raw["candidate_entry_ids"] = ["entry:1"]
        conn.execute("UPDATE source_observations SET payload=? WHERE record_id='candidate'", (json.dumps(raw),))
    transport = Transport()
    report = complete_dictionary(path, transport, 10, banks=("GOOD",), max_entries_per_pass=1, continue_cohorts=True)
    assert report["model_calls"] == 2
    by_entry = {p["entry_id"]: {o["record_id"] for o in p["observations"]} for p in transport.requests}
    assert by_entry == {"entry:0": {"native:0"}, "entry:1": {"native:1", "candidate"}}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_snapshot_change_while_building_temporary_index_is_refused(tmp_path, monkeypatch):
    path = dictionary(tmp_path)
    actual = completion._prepare_context_index

    def index(conn):
        actual(conn)
        with sqlite3.connect(path) as other:
            other.execute("INSERT INTO builder_metadata VALUES ('external-marker','1')")

    monkeypatch.setattr(completion, "_prepare_context_index", index)
    transport = Transport()
    with pytest.raises(ValueError, match="COMPLETION_SNAPSHOT_CHANGED"):
        complete_dictionary(path, transport, 10, continue_cohorts=True)
    assert transport.requests == []
    assert assignment(path, "entry:0") is None


@pytest.mark.parametrize("value", [None, 0, 1, "yes", []])
def test_sustained_flag_requires_a_boolean_before_database_access(tmp_path, value):
    with pytest.raises(ValueError, match="INVALID_COMPLETION_OPTIONS"):
        complete_dictionary(tmp_path / "missing.db", Transport(), 1, continue_cohorts=value)


def test_real_cli_continues_past_one_bounded_cohort(tmp_path, monkeypatch, capsys):
    from GSE.curation.cli import commands
    from GSE.curation.lexicon_builder import residual

    path = dictionary(tmp_path)
    transport = Transport()
    monkeypatch.setattr(residual, "OllamaTransport", lambda *args, **kwargs: transport)
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
            "--max-entries",
            "1",
            "--bank",
            "GOOD",
            "--continue-cohorts",
        ],
    )
    commands.main()
    report = json.loads(capsys.readouterr().out)
    assert report["continue_cohorts"] is True
    assert report["model_calls"] == 3
    assert report["scheduling"]["cohorts_processed"] == 3
    assert report["dictionary_status"] == "ALL_BANKS_ASSIGNED"
