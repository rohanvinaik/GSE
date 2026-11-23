"""Large call budgets cannot expand an invocation into all source contexts."""

import json
import sys

import pytest

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import DomainRestriction
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.validation import validate_build


class Transport:
    model = "cohort-fixture"

    def __init__(self, value=1):
        self.value = value
        self.entries = []

    def pin(self):
        return {"model": self.model, "digest": "a" * 64}

    def __call__(self, payload, schema):
        self.entries.append(payload["entry_id"])
        assert len(payload["observations"]) == 1
        assert payload["observations"][0]["entry_id"] == payload["entry_id"]
        return json.dumps({payload["bank"]: self.value})


def dictionary(tmp_path, count):
    definitions, observations, restrictions = [], [], []
    for index in range(count):
        entry = f"fixture:{index:04}"
        record = "record:" + entry
        definitions.append(Definition(entry, entry, "verb", "authored cohort fixture"))
        observations.append(Observation(entry, "fixture", record, "fixture", {"index": index}, "lexical"))
        for bank in BANKS:
            # Explicit fixture restrictions; no production complement-zero rule.
            restrictions.append(
                DomainRestriction(bank, (-1, 1) if bank == "GOOD" else (0,), "fixture", record, "fixture")
            )
    path = tmp_path / "dictionary.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), (), (), tuple(restrictions)), path)
    return path


def test_huge_call_budget_keeps_default_cohort_bounded_and_resumes(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import completion

    path = dictionary(tmp_path, 65)
    actual_contexts = completion._contexts
    retained_counts = []

    def contexts(conn, selected):
        retained_counts.append(len(selected))
        return actual_contexts(conn, selected)

    monkeypatch.setattr(completion, "_contexts", contexts)
    transport = Transport()
    first = complete_dictionary(path, transport, 10**9, banks=("GOOD",))
    assert first["max_entries_per_pass"] == 64
    assert len(first["selected_entry_ids"]) == first["model_calls"] == 64
    assert first["dictionary_status"] == "INCOMPLETE"
    assert first["scheduling"]["code"] == "COHORT_EXHAUSTED"
    second = complete_dictionary(path, transport, 10**9, banks=("GOOD",))
    assert second["selected_entry_ids"] == ["fixture:0064"]
    assert second["dictionary_status"] == "ALL_BANKS_ASSIGNED"
    assert retained_counts == [64, 1]
    assert len(transport.entries) == len(set(transport.entries)) == 65
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_small_cohorts_remain_fair_across_abstentions_and_wrap(tmp_path):
    path = dictionary(tmp_path, 5)
    transport = Transport(None)
    reports = [complete_dictionary(path, transport, 1000, max_entries_per_pass=2, banks=("GOOD",)) for _ in range(3)]
    assert [report["selected_entry_ids"] for report in reports] == [
        ["fixture:0000", "fixture:0001"],
        ["fixture:0002", "fixture:0003"],
        ["fixture:0004"],
    ]
    wrapped = complete_dictionary(path, transport, 1000, max_entries_per_pass=2, banks=("GOOD",))
    assert wrapped["selected_entry_ids"] == ["fixture:0000", "fixture:0001"]
    assert wrapped["scheduling"]["wrapped"] is True
    assert wrapped["model_calls"] == 0
    assert wrapped["skipped_attempts"] == {"ABSTAINED": 2}
    assert wrapped["dictionary_status"] == "INCOMPLETE"
    assert len(transport.entries) == 5


@pytest.mark.parametrize("limit", [0, -1, True, None, 1.5, "64"])
def test_invalid_entry_limit_is_refused_before_database_access(tmp_path, limit):
    missing = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="^INVALID_COMPLETION_ENTRY_LIMIT$"):
        complete_dictionary(missing, Transport(), 1000, max_entries_per_pass=limit)
    assert not missing.exists()


def test_oversized_explicit_scope_is_refused_without_truncation_or_writes(tmp_path):
    path = dictionary(tmp_path, 3)
    before = path.read_bytes()
    transport = Transport()
    with pytest.raises(ValueError, match="^EXPLICIT_SCOPE_EXCEEDS_ENTRY_LIMIT$"):
        complete_dictionary(
            path,
            transport,
            1000,
            max_entries_per_pass=2,
            entry_ids=("fixture:0000", "fixture:0001", "fixture:0002"),
        )
    assert path.read_bytes() == before
    assert transport.entries == []


def test_explicit_scope_at_limit_preserves_requested_identities(tmp_path):
    path = dictionary(tmp_path, 3)
    report = complete_dictionary(
        path, Transport(), 1000, max_entries_per_pass=2, entry_ids=("fixture:0002", "fixture:0000"), banks=("GOOD",)
    )
    assert set(report["selected_entry_ids"]) == {"fixture:0000", "fixture:0002"}
    assert report["scheduling"]["code"] == "EXPLICIT_SCOPE"
    assert report["outside_selected_scope"]["unresolved_or_conflicted_cells"] == 1
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_real_cli_forwards_entry_cap_to_journaled_completion(tmp_path, monkeypatch, capsys):
    from GSE.curation.cli import commands
    from GSE.curation.lexicon_builder import residual

    path = dictionary(tmp_path, 3)
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
            transport.model,
            "--max-model-calls",
            "1000",
            "--max-entries",
            "2",
            "--bank",
            "GOOD",
        ],
    )
    commands.main()
    report = json.loads(capsys.readouterr().out)
    assert report["max_entries_per_pass"] == 2
    assert report["model_calls"] == 2
    assert report["dictionary_status"] == "INCOMPLETE"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
