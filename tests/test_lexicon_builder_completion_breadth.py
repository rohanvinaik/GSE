"""Ordering changes questions, never evidence, values, or durable coverage."""

import csv
import json
import sqlite3
import sys

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import DomainRestriction, Relation
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.scheduling import pending_banks, spelling_cohort
from GSE.curation.lexicon_builder.validation import validate_build


class Transport:
    identity = "breadth-fixture:pinned"

    def __init__(self, value=None):
        self.value = value
        self.requests = []

    def __call__(self, payload, schema):
        self.requests.append(payload)
        return json.dumps({payload["bank"]: self.value})

    def callable_batch(self, items):
        assert len({payload["entry_id"] for payload, _ in items}) == len(items)
        return tuple(self(payload, schema) for payload, schema in items)


def fixture(tmp_path, rows, *, hints=(), unknown=("GOOD",)):
    definitions, observations, restrictions = [], [], []
    for entry, lemma in rows:
        definitions.append(Definition(entry, lemma, "verb", "Authored scheduling fixture; not corpus gold."))
        features = (
            {"bank_relevance": {"code": "CLASSIFIED", "banks": list(hints), "provenance": ["test:explicit"]}}
            if hints
            else {}
        )
        observations.append(Observation(entry, "fixture", entry, "fixture", features, "lexical"))
        restrictions.extend(
            DomainRestriction(bank, (0,), "fixture", entry, "fixture") for bank in BANKS if bank not in unknown
        )
    path = tmp_path / "breadth.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions)), path)
    source = tmp_path / "frequency.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Word", "SUBTLEX"))
        writer.writerows((("common", 99), ("medium", 10), ("rare", 1)))
    return path, source


@pytest.mark.parametrize("batch_size", [1, 3])
def test_spelling_rounds_cover_every_definition_and_resume_after_abstention(tmp_path, batch_size):
    rows = (("a1", "Common"), ("a2", "common"), ("a3", "common"), ("b", "medium"), ("c", "rare"), ("d", "absent"))
    path, source = fixture(tmp_path, rows)
    transport = Transport()
    options = dict(
        banks=("GOOD",),
        priority="zipf",
        frequency_path=source,
        cohort_policy="spelling",
        bank_priority="evidence",
        max_entries_per_pass=3,
        max_calls_per_entry=1,
        batch_size=batch_size,
    )
    first = complete_dictionary(path, transport, 3, **options)
    second = complete_dictionary(path, transport, 3, **options)
    assert first["selected_entry_ids"] == ["a1", "b", "c"]
    assert second["selected_entry_ids"] == ["a2", "d", "a3"]
    assert [request["entry_id"] for request in transport.requests] == ["a1", "b", "c", "a2", "d", "a3"]
    assert first["scheduling"]["policy"] == "gse.completion-schedule/3"
    assert second["scheduling"]["wrapped"] is False
    assert second["dictionary_cells"]["unresolved"] == len(rows)
    wrapped = complete_dictionary(path, transport, 3, **options)
    assert wrapped["scheduling"]["wrapped"] is True
    assert wrapped["model_calls"] == 0
    assert wrapped["skipped_attempts"] == {"ABSTAINED": 3}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_spelling_rounds_stable_under_row_order_ties_and_small_population():
    rows = [(((-10, 3), 0, "a2"), "a"), (((-1, 3), 0, "b"), "b"), (((-10, 3), 0, "a1"), "a")]
    expected = (((-10, 3), 0, "a1"), ((-1, 3), 0, "b"), ((-10, 3), 0, "a2"))
    assert spelling_cohort(iter(rows), 9) == (expected, False)
    assert spelling_cohort(iter(reversed(rows)), 2) == (expected[:2], True)
    assert spelling_cohort(iter(()), 2) == ((), False)


@pytest.mark.parametrize("batch_size", [1, 2])
def test_typed_evidence_changes_question_order_only_on_both_paths(tmp_path, batch_size):
    path, _ = fixture(tmp_path, (("a", "common"),), hints=("WANT",), unknown=("GOOD", "WANT"))
    transport = Transport(0)
    report = complete_dictionary(path, transport, 1, bank_priority="evidence", batch_size=batch_size)
    assert [request["bank"] for request in transport.requests] == ["WANT"]
    assert "WANT" not in transport.requests[0]["known"]
    assert transport.requests[0]["allowed_values"] == [-1, 0, 1]
    with sqlite3.connect(path) as conn:
        domains = json.loads(conn.execute("SELECT domains FROM definition_states").fetchone()[0])
    assert domains["WANT"] == [0]
    assert domains["GOOD"] == [-1, 0, 1]
    assert report["dictionary_status"] == "INCOMPLETE"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_unknown_relevance_does_not_claim_specific_evidence():
    resolution = resolve_dictionary(BANKS, (), ())
    assert pending_banks(resolution, ("WANT", "GOOD"), set(), policy="evidence", observations=({"features": {}},)) == (
        "GOOD",
        "WANT",
    )
    for value in (-1, 0, 1):
        hints = ({"features": {"projection_candidates": [{"bank": "WANT", "suggested_values": [value]}]}},)
        assert pending_banks(resolution, ("WANT", "GOOD"), set(), policy="evidence", observations=hints) == (
            "WANT",
            "GOOD",
        )
    assert all(domain == frozenset({-1, 0, 1}) for domain in resolution.domains.values())


@pytest.mark.parametrize(
    "approved,guards,expected",
    [
        (True, (), ("WANT", "GOOD")),
        (False, (), ("GOOD", "WANT")),
        (True, (("pos", "noun"),), ("GOOD", "WANT")),
    ],
)
def test_only_active_approved_rule_connections_affect_order(approved, guards, expected):
    rule = Relation(
        "fixture:connected",
        ("WANT", "THINK"),
        ((-1, -1), (0, 0), (1, 1)),
        ("test:relation",),
        approved=approved,
        guards=guards,
    )
    resolution = resolve_dictionary(BANKS, (), (rule,), {"pos": "verb"})
    assert (
        pending_banks(
            resolution, ("WANT", "GOOD"), set(), policy="evidence", relations=(rule,), context={"pos": "verb"}
        )
        == expected
    )
    assert all(domain == frozenset({-1, 0, 1}) for domain in resolution.domains.values())


def test_known_and_attempted_banks_remain_excluded_and_smaller_domain_first():
    restrictions = (
        DomainRestriction("GOOD", (-1, 1), "fixture", "r", "fixture"),
        DomainRestriction("KNOW", (0,), "fixture", "r", "fixture"),
    )
    resolution = resolve_dictionary(BANKS, (), (), domain_restrictions=restrictions)
    hints = ({"features": {"bank_relevance": {"code": "CLASSIFIED", "banks": ["WANT"], "provenance": ["test:hint"]}}},)
    assert pending_banks(
        resolution, ("WANT", "GOOD", "KNOW", "THINK"), {"THINK"}, policy="evidence", observations=hints
    ) == ("GOOD", "WANT")


@pytest.mark.parametrize("option", ["cohort_policy", "bank_priority"])
@pytest.mark.parametrize("value", [None, True, [], {}, 1, "unknown"])
def test_invalid_order_policies_fail_before_database_access(tmp_path, option, value):
    with pytest.raises(ValueError, match="^INVALID_COMPLETION_(COHORT_POLICY|BANK_PRIORITY)$"):
        complete_dictionary(tmp_path / "absent.db", Transport(), 1, **{option: value})
    assert not (tmp_path / "absent.db").exists()


def test_policy_switch_preserves_journals_and_old_visit_scope(tmp_path):
    path, source = fixture(tmp_path, (("a", "common"), ("b", "medium")))
    old = complete_dictionary(path, Transport(), 1, banks=("GOOD",), priority="zipf", frequency_path=source)
    transport = Transport()
    new = complete_dictionary(
        path, transport, 2, banks=("GOOD",), priority="zipf", frequency_path=source, cohort_policy="spelling"
    )
    assert old["scheduling"]["policy"] == "gse.completion-schedule/2"
    assert new["scheduling"]["policy"] == "gse.completion-schedule/3"
    assert new["skipped_attempts"] == {"ABSTAINED": 1}
    assert [request["entry_id"] for request in transport.requests] == ["b"]
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM completion_schedule").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM completion_attempts").fetchone()[0] == 2


@pytest.mark.parametrize("batch_size", [1, 2])
def test_budget_interrupted_definition_remains_unvisited_in_new_policy(tmp_path, batch_size):
    path, source = fixture(tmp_path, (("a", "common"), ("b", "medium")), hints=("WANT",), unknown=("GOOD", "WANT"))
    options = dict(
        priority="zipf",
        frequency_path=source,
        cohort_policy="spelling",
        bank_priority="evidence",
        batch_size=batch_size,
    )
    first = Transport(1)
    report = complete_dictionary(path, first, 1, **options)
    assert [(request["entry_id"], request["bank"]) for request in first.requests] == [("a", "WANT")]
    assert report["scheduling"]["visited_entry_ids"] == []
    second = Transport(1)
    resumed = complete_dictionary(path, second, 1, **options)
    assert [(request["entry_id"], request["bank"]) for request in second.requests] == [("a", "GOOD")]
    assert resumed["scheduling"]["visited_entry_ids"] == ["a"]
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_sustained_breadth_cohorts_do_not_repeat_unchanged_abstentions(tmp_path):
    path, source = fixture(tmp_path, (("a1", "common"), ("a2", "common"), ("b", "medium"), ("c", "rare")))
    transport = Transport()
    report = complete_dictionary(
        path,
        transport,
        100,
        banks=("GOOD",),
        priority="zipf",
        frequency_path=source,
        cohort_policy="spelling",
        max_entries_per_pass=2,
        max_calls_per_entry=1,
        continue_cohorts=True,
        batch_size=2,
    )
    assert [request["entry_id"] for request in transport.requests] == ["a1", "b", "a2", "c"]
    assert report["scheduling"]["code"] == "NO_NEW_ATTEMPTS_IN_PASS"
    assert report["model_calls"] == 4
    assert report["dictionary_cells"]["unresolved"] == 4
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_real_cli_forwards_both_explicit_order_policies(tmp_path, monkeypatch, capsys):
    from GSE.curation.cli import commands
    from GSE.curation.lexicon_builder import residual

    path, source = fixture(
        tmp_path, (("a1", "common"), ("a2", "common"), ("b", "medium")), hints=("WANT",), unknown=("GOOD", "WANT")
    )
    transport = Transport()
    monkeypatch.setattr(transport, "pin", lambda: {}, raising=False)
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
            "fixture",
            "--max-model-calls",
            "2",
            "--max-calls-per-entry",
            "1",
            "--max-entries",
            "2",
            "--frequency-file",
            str(source),
            "--cohort-policy",
            "spelling",
            "--bank-priority",
            "evidence",
        ],
    )
    commands.main()
    report = json.loads(capsys.readouterr().out)
    assert [(request["entry_id"], request["bank"]) for request in transport.requests] == [("a1", "WANT"), ("b", "WANT")]
    assert report["question_order"]["cohort_policy"] == "spelling"
    assert report["question_order"]["bank_priority"] == "evidence"
    assert report["dictionary_cells"]["unresolved"] == 6
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
