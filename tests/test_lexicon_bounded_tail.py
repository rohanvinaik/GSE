"""Model dispatch must consume the diagnosed queue and preserve abstention."""

import json
from pathlib import Path

from gse.lexicon_builder.artifact import export_sparse
from gse.lexicon_builder.build import build
from gse.lexicon_builder.core import Observation, legal_domain
from gse.lexicon_builder.model import selection_status
from gse.lexicon_builder.reading import CoordinateDecision, ReadingSeed, construct_reading
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources
from gse.lexicon_builder.tail import BudgetedSelector, attach_tail, plan_tail, tail_ledger, tail_task_status
from tests.lexicon_sources import requires_lexicon_sources


class Recorder:
    def __init__(self, answer="ABSTAIN"):
        self.calls = []
        self.answer = answer

    def select(self, payload, options):
        self.calls.append((payload, options))
        return {"request_sha256": str(len(self.calls)), "answer": {c: self.answer for c in options}}


def task(coordinate="WANT"):
    return {
        "reading_id": "sample:sense1",
        "coordinate": coordinate,
        "options": sorted(legal_domain(coordinate)),
        "reason": "UNRESOLVED_COMPONENT",
        "source_record_ids": ["source:1"],
    }


def layout(result):
    return {
        "word": "sample",
        "reading_id": "sample:sense1",
        "code": result.state.code,
        "after_selection": result.state.to_json(),
        "decisions": result.decisions,
        "model_calls": result.calls,
        "premise_record_ids": ["source:1"],
        "residual_coordinates": ["WANT", "THINK"],
    }


def seed():
    return ReadingSeed(
        "sample",
        "sample:sense1",
        (Observation("sample:sense1", "native", "source:1", "own_role", "test", True),),
        [],
        layout,
        decisions=[CoordinateDecision("SAY", lambda _: {})],
    )


def test_explicit_queue_replaces_recipe_dispatch_and_abstention_retains_unknown():
    backend = Recorder()
    prepared = attach_tail(seed(), [task()])
    result = construct_reading(prepared, {"laws": []}, BudgetedSelector(backend, 2))
    assert len(backend.calls) == 1
    assert set(backend.calls[0][1]) == {"WANT"}
    assert "0" in backend.calls[0][1]["WANT"]
    assert "ABSTAIN" in backend.calls[0][1]["WANT"]
    assert result["after_selection"]["domains"]["WANT"] == sorted(legal_domain("WANT"))
    assert result["decisions"][0]["code"] == "ABSTAINED"


def test_narrowed_queue_must_not_remove_zero_from_a_live_domain():
    narrowed = task()
    narrowed["options"].remove("0")
    backend = Recorder("+1")
    result = construct_reading(attach_tail(seed(), [narrowed]), {"laws": []}, BudgetedSelector(backend, 10))
    assert backend.calls == []
    assert result["decisions"][0]["code"] == "STALE_TASK_DOMAIN"


def test_budget_is_global_across_decisions_and_zero_budget_never_contacts_backend():
    backend = Recorder("0")
    result = construct_reading(attach_tail(seed(), [task(), task("THINK")]), {"laws": []}, BudgetedSelector(backend, 1))
    assert len(backend.calls) == 1
    assert [d["code"] for d in result["decisions"]] == ["SELECTED", "BUDGET_EXHAUSTED"]
    assert result["after_selection"]["forced"]["WANT"] == "0"
    untouched = Recorder()
    result = construct_reading(attach_tail(seed(), [task()]), {"laws": []}, BudgetedSelector(untouched, 0))
    assert untouched.calls == []
    assert result["decisions"][0]["code"] == "BUDGET_EXHAUSTED"


def test_planner_only_nominates_projector_components_with_limits_and_no_gold(tmp_path):
    result = construct_reading(seed(), {"laws": []}, None)
    record = export_sparse(result)
    path = tmp_path / "sparse.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert len(plan_tail(path, max_tasks=10, max_per_reading=1)) == 1
    assert {t["coordinate"] for t in plan_tail(path)} == {"THINK", "WANT"}
    assert plan_tail(path, max_tasks=0) == []
    record["residual_coordinates"] = []
    path.write_text(json.dumps(record) + "\n")
    assert plan_tail(path) == []
    poisoned = {**task(), "gold": "+1"}
    assert tail_task_status(poisoned) == "FIELD_MISMATCH"


def test_every_task_has_a_disposition_even_without_a_matching_reading():
    assert tail_ledger([task()], [])[0]["code"] == "UNMATCHED_READING"


def test_malformed_decoder_contracts_have_named_refusals():
    assert selection_status(None, {}) == "MALFORMED_OPTIONS"
    assert selection_status({"_unread": "x"}, {}) == "MALFORMED_OPTIONS"
    assert selection_status({"WANT": [["+1"]]}, {}) == "MALFORMED_OPTIONS"
    assert selection_status({"WANT": ["+1", "+1"]}, {}) == "MALFORMED_OPTIONS"
    assert selection_status({"WANT": ["+1", "0"]}, None) == "MALFORMED_SELECTION"
    assert selection_status({"WANT": ["+1", "0"]}, {"WANT": "0"}) == "VALID_SELECTION"


@requires_lexicon_sources
def test_real_source_projector_nominates_tasks_without_writing_them_or_using_gold(tmp_path):
    sources = NativeSources(["afraid"], Path("data/external"), Path.home() / "nltk_data/corpora")
    book = load_rulebook()
    before = next(build(["afraid"], sources, book, None, tail_tasks=[]))
    path = tmp_path / "sparse.jsonl"
    path.write_text("".join(json.dumps(export_sparse(r)) + "\n" for r in before["readings"]))
    tasks = plan_tail(path, max_per_reading=3)
    assert {t["coordinate"] for t in tasks} == {"DO", "IF", "KNOW"}
    assert all("0" in t["options"] for t in tasks)
    backend = Recorder()
    after = next(build(["afraid"], sources, book, BudgetedSelector(backend, 0), tail_tasks=tasks))
    assert backend.calls == []
    assert after["readings"][0]["after_selection"]["domains"] == before["readings"][0]["after_selection"]["domains"]
    ledger = tail_ledger(tasks, [d for r in after["readings"] for d in r["decisions"]])
    assert {d["code"] for d in ledger} == {"BUDGET_EXHAUSTED"}
