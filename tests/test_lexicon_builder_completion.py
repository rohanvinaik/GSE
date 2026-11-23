"""Exercise durable, bounded post-build completion through real stored artifacts."""

import json
import sqlite3
import sys
from dataclasses import asdict

import pytest

from GSE.curation.cli import commands
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import DomainRestriction, Relation
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.validation import validate_build


class Transport:
    model = "fixture-model"

    def __init__(self, answer=None):
        self.answer = answer
        self.requests = []

    def __call__(self, payload, schema):
        self.requests.append((payload, schema))
        if callable(self.answer):
            return self.answer(payload, schema)
        return self.answer if self.answer is not None else json.dumps({payload["bank"]: payload["allowed_values"][-1]})


class VersionedTransport(Transport):
    def __init__(self, identity, answer=None):
        super().__init__(answer)
        self.identity = identity


def fixture_bundle(specs):
    """Explicit synthetic restrictions are fixture data, never a production zero rule."""
    definitions, observations, restrictions = [], [], []
    for entry_id, unknown in specs.items():
        definitions.append(Definition(entry_id, entry_id, "verb", "synthetic test definition"))
        record_id = f"record:{entry_id}"
        observations.append(Observation(entry_id, "fixture", record_id, "fixture", {}, "lexical"))
        for bank in BANKS:
            values = unknown.get(bank, (0,))
            if len(values) < 3:
                restrictions.append(DomainRestriction(bank, values, "fixture", record_id, "fixture"))
    return EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions))


def built(tmp_path, specs=None, manifest=None):
    path = tmp_path / "dictionary.db"
    bundle = fixture_bundle(specs or {"d": {"GOOD": (-1, 1)}})
    build_dictionary(bundle, path, manifest=manifest)
    return path, bundle


def metadata(path, key):
    with sqlite3.connect(path) as conn:
        return json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchone()[0])


def state(path, entry="d"):
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT code,domains,trace,hierarchy FROM definition_states WHERE entry_id=?", (entry,)
        ).fetchone()


def test_acceptance_mutates_file_atomically_and_replays(tmp_path):
    path, _ = built(tmp_path)
    before = state(path)
    transport = Transport()
    report = complete_dictionary(path, transport, 1, banks=("GOOD",))
    assert report["code"] == "SELECTED_SCOPE_RESOLVED"
    assert report["model_calls"] == 1
    assert report["dictionary_outcomes"] == {"RESOLVED": 1}
    assert report["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert report["outside_selected_scope"] == {"unresolved_or_conflicted_cells": 0}
    assert metadata(path, "last_completion_report") == report
    assert metadata(path, "last_report")["model_calls"] == 1
    assert state(path) != before
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    payload, schema = transport.requests[0]
    assert payload["allowed_values"] == [-1, 1]
    assert schema["properties"]["GOOD"]["enum"] == [-1, 1, None]
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM primitive_values WHERE primitive='GOOD'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM builder_domain_restrictions").fetchone()[0] == len(BANKS)
        assert conn.execute("SELECT code FROM completion_attempts").fetchone()[0] == "ASSIGNED"
    again = complete_dictionary(
        path, Transport(lambda *_: pytest.fail("assigned cell reasked")), 1, entry_ids=("d",), banks=("GOOD",)
    )
    assert again["model_calls"] == 0
    assert again["code"] == "SELECTED_SCOPE_RESOLVED"


@pytest.mark.parametrize(
    "answer,code",
    [
        ('{"GOOD":null}', "ABSTAINED"),
        ('{"GOOD":0}', "INVALID_OUTPUT"),
        ('{"GOOD":true}', "INVALID_OUTPUT"),
        ('{"GOOD":1,"WANT":1}', "INVALID_OUTPUT"),
        ("not json", "INVALID_OUTPUT"),
    ],
)
def test_rejected_or_abstained_output_keeps_original_dictionary(tmp_path, answer, code):
    path, _ = built(tmp_path)
    before = state(path)
    report = complete_dictionary(path, Transport(answer), 1, banks=("GOOD",))
    assert report["outcomes"] == {code: 1}
    assert report["code"] == "BUDGET_EXHAUSTED"
    assert state(path) == before
    assert metadata(path, "model_completions") == []
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    resumed = complete_dictionary(
        path, Transport(lambda *_: pytest.fail("unchanged attempt repeated")), 1, banks=("GOOD",)
    )
    assert resumed["code"] == "RESIDUAL_REMAINS"
    assert resumed["skipped_attempts"] == {code: 1}
    assert resumed["model_calls"] == 0


def test_interruption_journal_is_durable_and_retry_is_explicit(tmp_path):
    path, _ = built(tmp_path)

    def interrupted(*_):
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT code FROM completion_attempts").fetchone()[0] == "RUNNING"
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        complete_dictionary(path, Transport(interrupted), 1, entry_ids=("d",), banks=("GOOD",))
    assert metadata(path, "last_report")["model_calls"] == 1
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    resumed = complete_dictionary(
        path, Transport(lambda *_: pytest.fail("interrupted call repeated")), 1, entry_ids=("d",), banks=("GOOD",)
    )
    assert resumed["model_calls"] == 0
    assert resumed["skipped_attempts"] == {"RUNNING": 1}
    assert resumed["code"] == "RESIDUAL_REMAINS"
    retried = complete_dictionary(path, Transport(), 1, entry_ids=("d",), banks=("GOOD",), retry=True)
    assert retried["outcomes"] == {"ASSIGNED": 1}
    assert metadata(path, "last_report")["model_calls"] == 2
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_changed_source_context_is_a_new_request_even_when_domains_match(tmp_path):
    path, _ = built(tmp_path)
    complete_dictionary(path, Transport('{"GOOD":null}'), 1, banks=("GOOD",))
    with sqlite3.connect(path) as conn:
        record = json.loads(conn.execute("SELECT payload FROM source_observations").fetchone()[0])
        record["features"]["new_native_context"] = "fixture clarification"
        conn.execute("UPDATE source_observations SET payload=?", (json.dumps(record),))
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    report = complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    assert report["outcomes"] == {"ASSIGNED": 1}
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(DISTINCT request_id) FROM completion_attempts").fetchone()[0] == 2


def test_new_transport_protocol_identity_is_not_skipped(tmp_path):
    path, _ = built(tmp_path)
    first = VersionedTransport("fixture-model@protocol-one", '{"GOOD":null}')
    complete_dictionary(path, first, 1, banks=("GOOD",))
    second = VersionedTransport("fixture-model@protocol-two")
    report = complete_dictionary(path, second, 1, banks=("GOOD",))
    assert report["model_calls"] == 1
    assert report["model"] == second.identity
    with sqlite3.connect(path) as conn:
        assert {row[0] for row in conn.execute("SELECT model FROM completion_attempts")} == {
            first.identity,
            second.identity,
        }
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_no_eligible_entries_does_not_claim_conflicted_dictionary_resolved(tmp_path):
    path, initial = built(tmp_path)
    conflict = DomainRestriction("GOOD", (0,), "fixture", "record:d", "fixture")
    bundle = EvidenceBundle(
        initial.definitions, initial.observations, (), (), initial.domain_restrictions + (conflict,)
    )
    build_dictionary(bundle, path)
    report = complete_dictionary(path, Transport(lambda *_: pytest.fail("conflict sent to model")), 1)
    assert report["selected_entry_ids"] == []
    assert report["unselected_residual"] is True
    assert report["code"] == "RESIDUAL_REMAINS"


def test_transport_error_stays_distinct_and_does_not_overwrite(tmp_path):
    path, _ = built(tmp_path)
    before = state(path)

    def broken(*_):
        raise OSError("fixture offline")

    report = complete_dictionary(path, Transport(broken), 1)
    assert report["outcomes"] == {"TRANSPORT_ERROR": 1}
    assert state(path) == before


def test_global_and_per_entry_limits_and_priority(tmp_path):
    path, _ = built(
        tmp_path,
        {"wide": {"GOOD": (-1, 0, 1)}, "narrow": {"GOOD": (-1, 1), "WANT": (-1, 0, 1)}, "single": {"GOOD": (-1, 1)}},
    )
    transport = Transport()
    report = complete_dictionary(path, transport, 2, max_calls_per_entry=1)
    assert report["selected_entry_ids"] == ["single", "narrow"]
    assert [p["entry_id"] for p, _ in transport.requests] == ["single", "narrow"]
    assert len(transport.requests) == 2
    assert report["code"] == "BUDGET_EXHAUSTED"
    assert report["dictionary_outcomes"] == {"PARTIAL": 2, "RESOLVED": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_per_entry_limit_leaves_partial_scope_without_using_global_budget(tmp_path):
    path, _ = built(tmp_path, {"d": {"GOOD": (-1, 1), "WANT": (-1, 1)}})
    report = complete_dictionary(path, Transport(), 10, max_calls_per_entry=1)
    assert report["model_calls"] == 1
    assert report["code"] == "RESIDUAL_REMAINS"
    assert report["dictionary_outcomes"] == {"PARTIAL": 1}


def test_candidate_observations_are_included_in_request_and_replay(tmp_path):
    bundle = fixture_bundle({"d": {"GOOD": (-1, 1)}})
    extra = Observation(None, "rating", "ambiguous:r", "rating", {"score": 0.5}, "lexical", ("d",))
    bundle = EvidenceBundle(bundle.definitions, bundle.observations + (extra,), (), (), bundle.domain_restrictions)
    path = tmp_path / "context.db"
    build_dictionary(bundle, path)
    transport = Transport()
    complete_dictionary(path, transport, 1, entry_ids=("d",))
    assert {r["record_id"] for r in transport.requests[0][0]["observations"]} == {"record:d", "ambiguous:r"}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_conditional_contradiction_does_not_replace_hard_values(tmp_path, monkeypatch):
    from functools import partial

    from GSE.curation.lexicon_builder.engine import propagate

    # The all-negative assignment satisfies this cycle. A seven-combination
    # search limit leaves the unsupported positive choice for the residual tail.
    monkeypatch.setattr(
        "GSE.curation.lexicon_builder.resolution.propagate", partial(propagate, max_joint_assignments=7)
    )
    names = ("GOOD", "WANT", "THINK")
    relations = [
        Relation(
            f"cycle:{i}",
            (names[i], names[(i + 1) % 3]),
            ((-1, -1), (1, 1)) if i < 2 else ((-1, -1), (-1, 1), (1, -1)),
            ("synthetic satisfiable cycle",),
            approved=True,
        )
        for i in range(3)
    ]
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps({"format": "gse.lexicon-rules/1", "relations": [asdict(r) for r in relations]}))
    path, _ = built(tmp_path, {"d": {bank: (-1, 1) for bank in names}}, manifest)
    before = state(path)
    assert any(record["kind"] == "SOLVER_LIMIT" for record in json.loads(before[2]))
    assert propagate(names, (), tuple(relations)).assignments == dict.fromkeys(names, -1)
    report = complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    assert report["outcomes"] == {"CONTRADICTION": 1}
    assert state(path) == before
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_preflight_rejects_corruption_before_any_model_call_or_journal_write(tmp_path):
    path, _ = built(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE primitive_values SET value=1 WHERE primitive='WANT'")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="REQUIRES_VALIDATED_BUILD"):
        complete_dictionary(path, Transport(lambda *_: pytest.fail("invalid artifact reached model")), 1)
    assert path.read_bytes() == before


def test_external_write_during_transport_cannot_be_overwritten(tmp_path):
    path, _ = built(tmp_path)
    before = state(path)

    def other_writer(payload, _):
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT INTO builder_metadata VALUES ('external-marker','1')")
        return json.dumps({payload["bank"]: 1})

    with pytest.raises(ValueError, match="SNAPSHOT_CHANGED"):
        complete_dictionary(path, Transport(other_writer), 1)
    assert state(path) == before
    assert metadata(path, "external-marker") == 1
    assert metadata(path, "model_completions") == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT code FROM completion_attempts").fetchone()[0] == "STALE_SNAPSHOT"


def test_rebuild_clears_old_attempts(tmp_path):
    path, bundle = built(tmp_path)
    complete_dictionary(path, Transport('{"GOOD":null}'), 1)
    build_dictionary(bundle, path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM completion_attempts").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM completion_schedule").fetchone()[0] == 0
    assert complete_dictionary(path, Transport(), 1)["model_calls"] == 1


def test_acceptance_transaction_failure_rolls_back_both_assignment_and_receipt(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import completion

    path, _ = built(tmp_path)
    before = state(path)
    original = completion.store_entry

    def fail_after_entry_write(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("fixture storage failure")

    monkeypatch.setattr(completion, "store_entry", fail_after_entry_write)
    with pytest.raises(OSError, match="storage failure"):
        complete_dictionary(path, Transport(), 1)
    assert state(path) == before
    assert metadata(path, "model_completions") == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT code FROM completion_attempts").fetchone()[0] == "RUNNING"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_hierarchy_and_native_source_counts_survive_completion(tmp_path):
    manifest = tmp_path / "hierarchy.json"
    manifest.write_text(json.dumps({"format": "gse.lexicon-rules/1", "hierarchy": {"d": {"INTENSITY": 2}}}))
    path, _ = built(tmp_path, {"d": {"GOOD": (-1, 1), "INTENSITY": (1,)}}, manifest)
    sources = metadata(path, "last_report")["source_observations"]
    complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    assert json.loads(state(path)[3]) == {"INTENSITY": 2}
    assert metadata(path, "last_report")["source_observations"] == sources
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_selected_bank_completion_does_not_claim_entire_dictionary_complete(tmp_path):
    path, _ = built(tmp_path, {"d": {"GOOD": (-1, 1), "WANT": (-1, 1)}})
    report = complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    assert report["code"] == "SELECTED_SCOPE_RESOLVED"
    assert report["dictionary_outcomes"] == {"PARTIAL": 1}
    assert report["dictionary_status"] == "INCOMPLETE"
    assert report["dictionary_cells"]["unresolved"] == 1
    assert report["outside_selected_scope"] == {"unresolved_or_conflicted_cells": 1}
    assert metadata(path, "last_report")["cells"]["unresolved"] == 1


def test_selected_definition_completion_reports_other_unfinished_definitions(tmp_path):
    path, _ = built(tmp_path, {"a": {"GOOD": (-1, 1)}, "b": {"WANT": (-1, 1)}})
    report = complete_dictionary(path, Transport(), 1, entry_ids=("a",), banks=("GOOD",))
    assert report["code"] == "SELECTED_SCOPE_RESOLVED"
    assert report["dictionary_status"] == "INCOMPLETE"
    assert report["outside_selected_scope"] == {"unresolved_or_conflicted_cells": 1}


def test_unfiltered_resume_advances_abstained_cohorts_then_wraps(tmp_path):
    path, _ = built(tmp_path, {entry: {"GOOD": (-1, 1)} for entry in ("a", "b", "c")})
    transport = Transport('{"GOOD":null}')
    reports = [complete_dictionary(path, transport, 1, banks=("GOOD",)) for _ in range(3)]
    assert [r["selected_entry_ids"] for r in reports] == [["a"], ["b"], ["c"]]
    assert [r["scheduling"]["code"] for r in reports] == ["COHORT_EXHAUSTED", "COHORT_EXHAUSTED", "PASS_EXHAUSTED"]
    wrapped = complete_dictionary(
        path, Transport(lambda *_: pytest.fail("unchanged hash repeated")), 1, banks=("GOOD",)
    )
    assert wrapped["selected_entry_ids"] == ["a"]
    assert wrapped["scheduling"]["wrapped"] is True
    assert wrapped["scheduling"]["pass_number"] == 2
    assert wrapped["model_calls"] == 0
    # An unchanged skipped cohort must also advance, rather than pinning a pass.
    next_cohort = complete_dictionary(path, transport, 1, banks=("GOOD",))
    assert next_cohort["selected_entry_ids"] == ["b"]
    assert next_cohort["model_calls"] == 0


def test_cursor_wrap_rechecks_changed_full_request_context(tmp_path):
    path, _ = built(tmp_path, {entry: {"GOOD": (-1, 1)} for entry in ("a", "b")})
    complete_dictionary(path, Transport('{"GOOD":null}'), 1, banks=("GOOD",))
    with sqlite3.connect(path) as conn:
        raw = json.loads(conn.execute("SELECT payload FROM source_observations WHERE entry_id='a'").fetchone()[0])
        raw["features"]["new_context"] = "clarification"
        conn.execute("UPDATE source_observations SET payload=? WHERE entry_id='a'", (json.dumps(raw),))
    assert complete_dictionary(path, Transport('{"GOOD":null}'), 1, banks=("GOOD",))["selected_entry_ids"] == ["b"]
    wrapped = complete_dictionary(path, Transport(), 1, banks=("GOOD",))
    assert wrapped["selected_entry_ids"] == ["a"]
    assert wrapped["model_calls"] == 1
    assert wrapped["outcomes"] == {"ASSIGNED": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_budget_does_not_advance_cursor_past_unvisited_selected_entries(tmp_path):
    path, _ = built(tmp_path, {entry: {"GOOD": (-1, 1), "WANT": (-1, 1)} for entry in ("a", "b", "c")})
    first = complete_dictionary(path, Transport(), 2, max_calls_per_entry=2)
    assert first["selected_entry_ids"] == ["a", "b"]
    assert first["scheduling"]["visited_entry_ids"] == ["a"]
    assert first["scheduling"]["code"] == "COHORT_PARTIAL"
    assert complete_dictionary(path, Transport(), 1)["selected_entry_ids"] == ["b"]


def test_scheduling_scope_is_separate_for_protocol_and_bank_filters(tmp_path):
    path, _ = built(tmp_path, {entry: {"GOOD": (-1, 1), "WANT": (-1, 1)} for entry in ("a", "b")})
    first = VersionedTransport("protocol-one", '{"GOOD":null}')
    complete_dictionary(path, first, 1, banks=("GOOD",))
    different_bank = complete_dictionary(path, Transport('{"WANT":null}'), 1, banks=("WANT",))
    assert different_bank["selected_entry_ids"] == ["a"]
    different_protocol = complete_dictionary(
        path, VersionedTransport("protocol-two", '{"GOOD":null}'), 1, banks=("GOOD",)
    )
    assert different_protocol["selected_entry_ids"] == ["a"]
    assert complete_dictionary(path, first, 1, banks=("GOOD",))["selected_entry_ids"] == ["b"]


def test_priority_changes_do_not_revisit_a_definition_before_untouched_entries(tmp_path):
    path, _ = built(tmp_path, {"a": {"GOOD": (-1, 1), "WANT": (-1, 0, 1)}, "b": {"WANT": (-1, 0, 1)}})
    first = complete_dictionary(path, Transport(), 1, max_calls_per_entry=1)
    assert first["selected_entry_ids"] == ["a"]
    second = complete_dictionary(path, Transport(), 1, max_calls_per_entry=1)
    assert second["selected_entry_ids"] == ["b"]
    third = complete_dictionary(path, Transport(), 1, max_calls_per_entry=1)
    assert third["selected_entry_ids"] == ["a"]
    assert third["scheduling"]["wrapped"] is True


@pytest.mark.parametrize(
    "options",
    [
        {"max_model_calls": 0},
        {"max_model_calls": True},
        {"max_calls_per_entry": 0},
        {"entry_ids": ("missing",)},
        {"banks": ("BAD",)},
        {"banks": ()},
        {"entry_ids": ["d"]},
    ],
)
def test_invalid_selection_and_budgets_do_not_call_transport(tmp_path, options):
    path, _ = built(tmp_path)
    arguments = {"max_model_calls": 1, **options}
    with pytest.raises(ValueError):
        complete_dictionary(path, Transport(lambda *_: pytest.fail("invalid options reached transport")), **arguments)


@pytest.mark.parametrize("timeout", [None, 300])
def test_real_cli_parsing_and_completion_with_mocked_transport(tmp_path, monkeypatch, capsys, timeout):
    from GSE.curation.lexicon_builder import residual

    path, _ = built(tmp_path)
    report = tmp_path / "report.json"
    transport = Transport()
    monkeypatch.setattr(transport, "pin", lambda: {"model": "fixture-model", "digest": "a" * 64}, raising=False)

    def make_transport(model, **kwargs):
        assert kwargs == ({"timeout": timeout} if timeout is not None else {})
        return transport

    monkeypatch.setattr(residual, "OllamaTransport", make_transport)
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
            "fixture-model",
            "--max-model-calls",
            "1",
            "--max-calls-per-entry",
            "1",
            "--entry-id",
            "d",
            "--bank",
            "GOOD",
            "--report",
            str(report),
        ]
        + (["--model-timeout", str(timeout)] if timeout is not None else []),
    )
    commands.main()
    result = json.loads(capsys.readouterr().out)
    assert result == json.loads(report.read_text())
    assert result["outcomes"] == {"ASSIGNED": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
