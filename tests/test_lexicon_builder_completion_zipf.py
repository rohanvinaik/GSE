"""Frequency schedules typed questions; it never supplies semantic answers."""

import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from GSE.curation.lexicon_builder import completion
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import DomainRestriction
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.validation import validate_build


class Transport:
    identity = "zipf-fixture:pinned"

    def __init__(self, answer=None):
        self.answer = answer
        self.requests = []
        self.batches = []

    def __call__(self, payload, schema):
        self.requests.append(payload)
        value = self.answer(payload) if callable(self.answer) else self.answer
        return json.dumps({payload["bank"]: value})

    def callable_batch(self, items):
        self.batches.append(tuple(payload["entry_id"] for payload, _ in items))
        assert len(set(self.batches[-1])) == len(items)
        return tuple(self(payload, schema) for payload, schema in items)


def frequency(tmp_path, rows):
    path = tmp_path / "frequency.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Word", "SUBTLEX"))
        writer.writerows(rows)
    return path


def dictionary(tmp_path, records, *, extra_unknown=()):
    """Complete zero fixtures are authored for scheduling tests, never corpus gold."""
    definitions, observations, restrictions = [], [], []
    for entry, word, narrowed in records:
        record = "native:" + entry
        definitions.append(Definition(entry, word, "verb", "Synthetic scheduling fixture"))
        observations.append(Observation(entry, "fixture", record, "fixture", {"native": word}, "lexical"))
        for bank in BANKS:
            if bank in extra_unknown or bank == "GOOD" and not narrowed:
                continue
            restrictions.append(
                DomainRestriction(bank, (-1, 1) if bank == "GOOD" else (0,), "fixture", record, "fixture")
            )
    path = tmp_path / "dictionary.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions)), path)
    return path


def test_zipf_common_first_then_domain_size_then_known_values_then_identity(tmp_path):
    path = dictionary(
        tmp_path,
        (
            ("a:rare", "rare", True),
            ("z:common", "common", False),
            ("b:tie", "tie", True),
            ("c:tie", "tie", False),
            ("d:zero", "zero", True),
            ("e:absent", "absent", True),
        ),
    )
    source = frequency(tmp_path, (("rare", 2), ("common", 100), ("tie", 10), ("zero", 0)))
    transport = Transport()
    report = complete_dictionary(path, transport, 20, banks=("GOOD",), priority="zipf", frequency_path=source)
    assert [request["entry_id"] for request in transport.requests] == [
        "z:common",
        "b:tie",
        "c:tie",
        "a:rare",
        "d:zero",
        "e:absent",
    ]
    assert report["priority"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report["priority"]["ranked_words"] == 3
    assert report["priority"]["zero_count_words"] == 1
    assert report["priority"]["semantic_authority"] == "NONE_SCHEDULING_ONLY"
    assert report["outcomes"] == {"ABSTAINED": 6}
    assert report["dictionary_status"] == "INCOMPLETE"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_equal_frequency_and_domain_size_keep_known_count_tiebreak(tmp_path):
    path = dictionary(tmp_path, (("a:fewer", "fewer", True), ("z:more", "more", True)))
    # A second admissible value is explicit fixture evidence, not a frequency inference.
    with sqlite3.connect(path) as conn:
        row = json.loads(conn.execute("SELECT domains FROM definition_states WHERE entry_id='a:fewer'").fetchone()[0])
        row["WANT"] = [-1, 0, 1]
        conn.execute("UPDATE definition_states SET domains=? WHERE entry_id='a:fewer'", (json.dumps(row),))
        source = {"fewer": 10, "more": 10}
        cohort, _ = completion._select_entries(conn, None, ("GOOD",), 2, frequencies=source)
    # Selection-only test intentionally manipulates state; no model/publication is run.
    assert [key[2] for key in cohort] == ["z:more", "a:fewer"]


def test_fair_zipf_resume_and_wrap_preserve_nulls_and_budgets(tmp_path):
    path = dictionary(tmp_path, (("a", "rare", True), ("b", "medium", True), ("c", "common", True)))
    source = frequency(tmp_path, (("rare", 1), ("medium", 2), ("common", 3)))
    transport = Transport()
    reports = [
        complete_dictionary(path, transport, 1, banks=("GOOD",), priority="zipf", frequency_path=source)
        for _ in range(3)
    ]
    assert [report["selected_entry_ids"] for report in reports] == [["c"], ["b"], ["a"]]
    assert all(report["model_calls"] == 1 for report in reports)
    wrapped = complete_dictionary(path, transport, 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    assert wrapped["selected_entry_ids"] == ["c"]
    assert wrapped["scheduling"]["wrapped"] is True
    assert wrapped["model_calls"] == 0
    assert wrapped["skipped_attempts"] == {"ABSTAINED": 1}
    assert wrapped["code"] == "RESIDUAL_REMAINS"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_legacy_cursor_and_zipf_cursor_are_independent(tmp_path):
    path = dictionary(tmp_path, (("a", "rare", True), ("b", "common", True)))
    source = frequency(tmp_path, (("rare", 1), ("common", 9)))
    first = complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    second = complete_dictionary(path, Transport(), 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    assert first["selected_entry_ids"] == ["a"]
    assert second["selected_entry_ids"] == ["b"]
    assert second["scheduling"]["cursor_before"] is None
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM completion_schedule").fetchone()[0] == 2


def test_changed_source_gets_new_scope_same_bytes_reuse_scope(tmp_path):
    path = dictionary(tmp_path, (("a", "first", True), ("b", "second", True), ("c", "third", True)))
    source = frequency(tmp_path, (("first", 9), ("second", 5), ("third", 1)))
    complete_dictionary(path, Transport(), 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    copy = tmp_path / "copy.csv"
    copy.write_bytes(source.read_bytes())
    same = complete_dictionary(path, Transport(), 1, banks=("GOOD",), priority="zipf", frequency_path=copy)
    assert same["selected_entry_ids"] == ["b"]
    frequency(tmp_path, (("first", 1), ("second", 5), ("third", 9)))
    changed = complete_dictionary(path, Transport(), 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    assert changed["selected_entry_ids"] == ["c"]
    assert changed["scheduling"]["cursor_before"] is None
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM completion_schedule").fetchone()[0] == 2


def test_zipf_frequency_does_not_enter_bank_requests_or_change_native_values(tmp_path):
    path = dictionary(tmp_path, (("a", "rare", True), ("b", "common", True)))
    source = frequency(tmp_path, (("rare", 1), ("common", 9)))
    first, second = Transport(), Transport()
    complete_dictionary(path, first, 2, banks=("GOOD",))
    complete_dictionary(path, second, 2, banks=("GOOD",), priority="zipf", frequency_path=source, retry=True)
    assert {p["entry_id"]: p for p in first.requests} == {p["entry_id"]: p for p in second.requests}
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM primitive_values WHERE primitive='GOOD'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM primitive_values WHERE value<>0").fetchone()[0] == 0
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_zipf_sustained_batches_keep_contexts_bounded(tmp_path, monkeypatch):
    path = dictionary(tmp_path, tuple((str(i), f"word{i}", True) for i in range(5)))
    source = frequency(tmp_path, tuple((f"word{i}", i + 1) for i in range(5)))
    original = completion._contexts
    sizes = []

    def contexts(conn, selected, *, indexed=False):
        sizes.append(len(selected))
        return original(conn, selected, indexed=indexed)

    monkeypatch.setattr(completion, "_contexts", contexts)
    transport = Transport(1)
    report = complete_dictionary(
        path,
        transport,
        5,
        banks=("GOOD",),
        priority="zipf",
        frequency_path=source,
        max_entries_per_pass=2,
        batch_size=2,
        continue_cohorts=True,
    )
    assert transport.batches == [("4", "3"), ("2", "1"), ("0",)]
    assert sizes == [2, 2, 1]
    assert report["model_calls"] == 5
    assert report["transport_invocations"] == 3
    assert report["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_interrupted_zipf_batch_keeps_running_journal_and_resumes_fairly(tmp_path):
    path = dictionary(tmp_path, (("a", "rare", True), ("b", "medium", True), ("c", "common", True)))
    source = frequency(tmp_path, (("rare", 1), ("medium", 2), ("common", 3)))

    def interrupt(payload):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        complete_dictionary(
            path,
            Transport(interrupt),
            3,
            banks=("GOOD",),
            priority="zipf",
            frequency_path=source,
            max_entries_per_pass=2,
            batch_size=2,
            continue_cohorts=True,
        )
    transport = Transport(1)
    report = complete_dictionary(
        path,
        transport,
        3,
        banks=("GOOD",),
        priority="zipf",
        frequency_path=source,
        max_entries_per_pass=2,
        batch_size=2,
        continue_cohorts=True,
    )
    assert [p["entry_id"] for p in transport.requests] == ["a"]
    assert report["skipped_attempts"]["RUNNING"] >= 2
    assert report["model_calls"] == 1
    assert report["dictionary_status"] == "INCOMPLETE"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "Word,Other\na,1\n",
        "Word,SUBTLEX\na,-1\n",
        "Word,SUBTLEX\na,1.5\n",
        "Word,SUBTLEX\na,NaN\n",
        "Word,SUBTLEX\na,1\nA,2\n",
        "Word,SUBTLEX\na,\n",
        "Word,SUBTLEX\n,NaN\n",
        "Word,SUBTLEX,SUBTLEX\na,1,2\n",
        "Word,SUBTLEX\na,0\n",
    ],
)
def test_malformed_frequency_is_refused_before_dictionary_access(tmp_path, raw):
    source = tmp_path / "bad.csv"
    source.write_text(raw)
    missing = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="^INVALID_COMPLETION_FREQUENCY_SOURCE$"):
        complete_dictionary(missing, Transport(), 1, priority="zipf", frequency_path=source)
    assert not missing.exists()


@pytest.mark.parametrize("value", [None, True, "", "frequency", [], 1])
def test_invalid_priority_is_named_before_dictionary_access(tmp_path, value):
    with pytest.raises(ValueError, match="^INVALID_COMPLETION_PRIORITY$"):
        complete_dictionary(tmp_path / "missing.db", Transport(), 1, priority=value)


def test_missing_frequency_is_not_silently_defaulted(tmp_path):
    source = tmp_path / "missing.csv"
    with pytest.raises(ValueError, match="^COMPLETION_FREQUENCY_UNAVAILABLE$"):
        complete_dictionary(tmp_path / "missing.db", Transport(), 1, priority="zipf", frequency_path=source)
    assert not source.exists()


def test_frequency_option_cannot_be_silently_ignored(tmp_path):
    with pytest.raises(ValueError, match="^FREQUENCY_PATH_REQUIRES_ZIPF_PRIORITY$"):
        complete_dictionary(tmp_path / "missing.db", Transport(), 1, frequency_path=tmp_path / "frequency.csv")


@pytest.mark.parametrize(
    "cursor", [None, [], [2, -1, "a"], [[-1, True], -1, "a"], [[1, 2], -1, "a"], [[-1, 4], -1, "a"]]
)
def test_malformed_zipf_cursor_is_not_interpreted_as_legacy(tmp_path, cursor):
    path = dictionary(tmp_path, (("a", "first", True), ("b", "second", True)))
    source = frequency(tmp_path, (("first", 9), ("second", 5)))
    complete_dictionary(path, Transport(), 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE completion_schedule SET cursor=?", (json.dumps(cursor),))
    transport = Transport()
    with pytest.raises(ValueError, match="^INVALID_COMPLETION_SCHEDULE$"):
        complete_dictionary(path, transport, 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    assert transport.requests == []


def test_zipf_batch_budget_does_not_visit_unfinished_entry(tmp_path):
    path = dictionary(tmp_path, (("a", "rare", True), ("b", "common", True)), extra_unknown=("WANT",))
    source = frequency(tmp_path, (("rare", 1), ("common", 9)))
    first = Transport(1)
    report = complete_dictionary(
        path, first, 1, banks=("GOOD", "WANT"), priority="zipf", frequency_path=source, batch_size=2
    )
    assert [(p["entry_id"], p["bank"]) for p in first.requests] == [("b", "GOOD")]
    assert report["scheduling"]["visited_entry_ids"] == []
    second = Transport(1)
    complete_dictionary(path, second, 1, banks=("GOOD", "WANT"), priority="zipf", frequency_path=source, batch_size=2)
    assert [(p["entry_id"], p["bank"]) for p in second.requests] == [("b", "WANT")]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_source_changes_during_run_do_not_reorder_pinned_snapshot(tmp_path):
    path = dictionary(tmp_path, (("a", "rare", True), ("b", "common", True)))
    source = frequency(tmp_path, (("rare", 1), ("common", 9)))
    original_digest = hashlib.sha256(source.read_bytes()).hexdigest()

    def answer(payload):
        frequency(tmp_path, (("rare", 99), ("common", 1)))
        return 1

    transport = Transport(answer)
    report = complete_dictionary(
        path,
        transport,
        2,
        banks=("GOOD",),
        priority="zipf",
        frequency_path=source,
        max_entries_per_pass=1,
        continue_cohorts=True,
    )
    assert [p["entry_id"] for p in transport.requests] == ["b", "a"]
    assert report["priority"]["sha256"] == original_digest
    assert report["priority"]["sha256"] != hashlib.sha256(source.read_bytes()).hexdigest()
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_real_cli_defaults_to_zipf_using_explicit_temporary_frequency_source(tmp_path, monkeypatch, capsys):
    from GSE.curation.cli import commands
    from GSE.curation.lexicon_builder import residual

    path = dictionary(tmp_path, (("a", "rare", True), ("b", "common", True)))
    source = frequency(tmp_path, (("rare", 1), ("common", 99)))
    transport = Transport(1)
    monkeypatch.setattr(transport, "pin", lambda: {"model": transport.identity, "digest": "a" * 64}, raising=False)
    monkeypatch.setattr(residual, "OllamaTransport", lambda *args, **kwargs: transport)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gse",
            "--lexicon-db",
            str(path),
            "complete",
            "--model",
            transport.identity,
            "--max-model-calls",
            "2",
            "--bank",
            "GOOD",
            "--frequency-file",
            str(source),
        ],
    )
    commands.main()
    report = json.loads(capsys.readouterr().out)
    assert report["priority"]["mode"] == "zipf"
    assert report["priority"]["source"] == str(source)
    assert report["priority"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert [request["entry_id"] for request in transport.requests] == ["b", "a"]
    assert report["model_calls"] == 2
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("word", ["", "  ", "\t"])
def test_blank_frequency_word_is_excluded_with_exact_native_record_receipt(tmp_path, word):
    source = frequency(tmp_path, (("known", 99), (word, 27), ("zero", 0)))
    report, frequencies = completion._priority_source("zipf", source)
    assert frequencies == {"known": 99}
    assert report["rows"] == 3
    assert report["included_words"] == 2
    assert report["ranked_words"] == 1
    assert report["zero_count_words"] == 1
    assert report["excluded_count"] == 1
    assert report["excluded_records"] == [{"code": "MISSING_WORD", "record_number": 2, "csv_line": 3, "count": 27}]
    assert report["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_actual_local_subtlex_source_loads_with_missing_word_diagnostic():
    """Optional local-data integration; portable unit cases cover the same contract."""
    source = Path(completion.__file__).resolve().parents[3] / "data" / "external" / "concreteness.csv"
    if not source.exists():
        pytest.skip("Local gitignored SUBTLEX corpus is unavailable; fixture contract remains tested")
    report, frequencies = completion._priority_source("zipf", None)
    with source.open(newline="", encoding="utf-8-sig") as stream:
        records = list(csv.DictReader(stream))
    expected = {
        row["Word"].strip().casefold(): int(row["SUBTLEX"])
        for row in records
        if row["Word"].strip() and int(row["SUBTLEX"]) > 0
    }
    excluded = [
        {"code": "MISSING_WORD", "record_number": index, "count": int(row["SUBTLEX"])}
        for index, row in enumerate(records, start=1)
        if not row["Word"].strip()
    ]
    assert frequencies == expected
    assert report["rows"] == len(records)
    assert report["ranked_words"] == len(expected)
    assert report["excluded_count"] == len(excluded)
    assert [
        {key: receipt[key] for key in ("code", "record_number", "count")} for receipt in report["excluded_records"]
    ] == excluded
    assert report["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert "" not in frequencies


def uneven_dictionary(tmp_path, *, peer_remaining=False):
    """Explicit fixture banks expose non-prefix completion and changed sort keys."""
    definitions, observations, restrictions = [], [], []
    for entry in ("common", "medium", "rare"):
        definitions.append(Definition(entry, entry, "verb", "Synthetic unfinished-entry scheduler fixture"))
        observations.append(Observation(entry, "fixture", entry, "fixture", {}, "lexical"))
        for bank in BANKS:
            unresolved = (
                bank == "GOOD" or bank == "WANT" and (entry == "common" or peer_remaining and entry == "medium")
            )
            restrictions.append(DomainRestriction(bank, (-1, 1) if unresolved else (0,), "fixture", entry, "fixture"))
    path = tmp_path / "uneven.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions)), path)
    return path


def test_later_finished_batch_entry_cannot_hide_earlier_unfinished_entry(tmp_path):
    path = uneven_dictionary(tmp_path)
    source = frequency(tmp_path, (("common", 100), ("medium", 10), ("rare", 1)))
    first = Transport(1)
    before = complete_dictionary(
        path,
        first,
        2,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=2,
        max_calls_per_entry=3,
    )
    assert [(p["entry_id"], p["bank"]) for p in first.requests] == [("common", "GOOD"), ("medium", "GOOD")]
    assert before["scheduling"]["visited_entry_ids"] == ["medium"]
    assert before["scheduling"]["cursor_after"][2] == "medium"
    second = Transport(1)
    after = complete_dictionary(
        path,
        second,
        1,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=2,
        max_calls_per_entry=3,
    )
    assert [(p["entry_id"], p["bank"]) for p in second.requests] == [("common", "WANT")]
    assert after["scheduling"]["wrapped"] is False
    assert after["scheduling"]["resume_frontier"] == "COMPLETED_OR_PER_ENTRY_LIMIT_VISITS"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_single_entry_interrupted_only_by_global_budget_stays_unvisited(tmp_path):
    path = uneven_dictionary(tmp_path)
    source = frequency(tmp_path, (("common", 100), ("medium", 10), ("rare", 1)))
    first = Transport(1)
    before = complete_dictionary(
        path, first, 1, banks=("GOOD", "WANT"), priority="zipf", frequency_path=source, max_calls_per_entry=3
    )
    assert [(p["entry_id"], p["bank"]) for p in first.requests] == [("common", "GOOD")]
    assert before["scheduling"]["visited_entry_ids"] == []
    assert before["scheduling"]["cursor_after"] is None
    second = Transport(1)
    complete_dictionary(
        path, second, 1, banks=("GOOD", "WANT"), priority="zipf", frequency_path=source, max_calls_per_entry=3
    )
    assert [(p["entry_id"], p["bank"]) for p in second.requests] == [("common", "WANT")]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("batch_size", [1, 2])
def test_explicit_per_entry_cap_still_visits_partial_definition_for_this_pass(tmp_path, batch_size):
    path = uneven_dictionary(tmp_path)
    source = frequency(tmp_path, (("common", 100), ("medium", 10), ("rare", 1)))
    first = Transport(1)
    before = complete_dictionary(
        path,
        first,
        1,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=batch_size,
        max_calls_per_entry=1,
    )
    assert before["scheduling"]["visited_entry_ids"] == ["common"]
    second = Transport(1)
    complete_dictionary(
        path,
        second,
        1,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=batch_size,
        max_calls_per_entry=1,
    )
    assert [(p["entry_id"], p["bank"]) for p in second.requests] == [("medium", "GOOD")]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("batch_size", [1, 2])
def test_new_known_value_moving_priority_before_cursor_does_not_hide_pending_work(tmp_path, batch_size):
    path = uneven_dictionary(tmp_path, peer_remaining=True)
    source = frequency(tmp_path, (("common", 100), ("medium", 100), ("rare", 1)))
    complete_dictionary(
        path,
        Transport(1),
        1,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=batch_size,
        max_calls_per_entry=1,
    )
    second = Transport(1)
    report = complete_dictionary(
        path,
        second,
        1,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=batch_size,
        max_calls_per_entry=3,
    )
    assert [(p["entry_id"], p["bank"]) for p in second.requests] == [("medium", "GOOD")]
    assert report["scheduling"]["visited_entry_ids"] == []
    assert report["scheduling"]["cursor_after"][2] == "common"
    third = Transport(1)
    after = complete_dictionary(
        path,
        third,
        1,
        banks=("GOOD", "WANT"),
        priority="zipf",
        frequency_path=source,
        batch_size=batch_size,
        max_calls_per_entry=3,
    )
    assert [(p["entry_id"], p["bank"]) for p in third.requests] == [("medium", "WANT")]
    assert after["scheduling"]["wrapped"] is False
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_legacy_cursor_scope_starts_new_visit_pass_without_reasking_same_request(tmp_path):
    path = uneven_dictionary(tmp_path)
    source = frequency(tmp_path, (("common", 100), ("medium", 10), ("rare", 1)))
    old = complete_dictionary(
        path, Transport(), 1, entry_ids=("common",), banks=("GOOD", "WANT"), priority="zipf", frequency_path=source
    )
    identity = {"policy": old["priority"]["policy"], "sha256": old["priority"]["sha256"]}
    old_scope = hashlib.sha256(completion._json([Transport.identity, ("GOOD", "WANT"), identity]).encode()).hexdigest()
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO completion_schedule VALUES (?,?,?,?,?)",
            (old_scope, Transport.identity, '["GOOD","WANT"]', '[[-10,2],-55,"medium"]', 1),
        )
        conn.execute("INSERT INTO completion_visits VALUES (?,?,?)", (old_scope, 1, "common"))
        previous = conn.execute("SELECT request_id,code FROM completion_attempts").fetchall()
    transport = Transport(1)
    report = complete_dictionary(path, transport, 2, banks=("GOOD", "WANT"), priority="zipf", frequency_path=source)
    assert report["scheduling"]["policy"] == "gse.completion-schedule/2"
    assert report["scheduling"]["cursor_before"] is None
    assert [(p["entry_id"], p["bank"]) for p in transport.requests] == [("common", "WANT"), ("medium", "GOOD")]
    assert report["skipped_attempts"] == {"ABSTAINED": 1}
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM completion_schedule").fetchone()[0] == 2
        assert (
            conn.execute(
                "SELECT request_id,code FROM completion_attempts WHERE request_id=?", (previous[0][0],)
            ).fetchall()
            == previous
        )
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
