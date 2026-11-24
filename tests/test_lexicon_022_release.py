"""The live round cannot bypass its stage or repeat publication after activation."""

import json
from importlib import import_module

import pytest

finish = import_module("docs.readings.2026-11-13-ssl-explicit-genera.finish_coherence_022")


@pytest.fixture
def verification(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.db"
    candidate.write_bytes(b"candidate")
    (tmp_path / "022-coherence-plan.json").write_text(json.dumps({"epochs": 2}))
    (tmp_path / "022-population-stage.json").write_text(
        json.dumps(
            {
                "changes": [
                    {"entry_id": "in-scope", "bank": "WHEN", "before": [-1, 0, 1], "after": [1]},
                ]
            }
        )
    )
    monkeypatch.setattr(finish, "NOTES", tmp_path)
    monkeypatch.setattr(finish, "verify_sources", lambda: None)
    result = {
        "epochs": [{"code": "RULE_ADMITTED", "audit_outcomes": {"MODEL_AGREEMENT": 3}} for _ in range(2)],
        "typed_questions_used": 8,
        "reopened_cells": 0,
        "replay": {"code": "REPLAY_VALIDATED", "complete_search": True},
        "candidate": str(candidate),
        "candidate_sha256": finish.fingerprint(candidate),
        "new_cells": 1,
    }
    return tmp_path, result


@pytest.mark.parametrize("mutation", ["budget", "partial", "reopen", "limited", "disagreed"])
def test_incomplete_or_disputed_round_cannot_reach_release_verification(verification, mutation):
    _, result = verification
    if mutation == "budget":
        result["typed_questions_used"] = 7
    elif mutation == "partial":
        result["epochs"][1]["code"] = "RULE_WITHHELD"
    elif mutation == "reopen":
        result["reopened_cells"] = 1
    elif mutation == "limited":
        result["replay"]["complete_search"] = False
    else:
        result["epochs"][1]["audit_outcomes"] = {"MODEL_AGREEMENT": 2, "MODEL_COUNTEREXAMPLE": 1}
    with pytest.raises(ValueError, match="LITERAL_GENUS_COMPLETE_TEACHING_AND_AUDIT_REQUIRED"):
        finish.verify_candidate(result)


def test_full_delta_must_equal_the_frozen_scope(verification, monkeypatch):
    _, result = verification
    monkeypatch.setattr(
        finish,
        "exact_delta",
        lambda *_: (
            401596,
            [
                {"entry_id": "outside", "bank": "WHEN", "before": [-1, 0, 1], "after": [1]},
            ],
        ),
    )
    with pytest.raises(ValueError, match="LITERAL_GENUS_DELTA_DIFFERS_FROM_FULL_STAGE"):
        finish.verify_candidate(result)


def test_extra_bank_cannot_be_published_even_if_present_in_stage(verification, monkeypatch):
    notes, result = verification
    changes = [{"entry_id": "in-scope", "bank": "I", "before": [-1, 0, 1], "after": [0]}]
    (notes / "022-population-stage.json").write_text(json.dumps({"changes": changes}))
    monkeypatch.setattr(finish, "exact_delta", lambda *_: (401596, changes))
    with pytest.raises(ValueError, match="LITERAL_GENUS_UNEXPECTED_KNOWN_OR_OTHER_BANK_CHANGE"):
        finish.verify_candidate(result)


def test_active_successor_recovers_without_deleted_work_or_republishing(tmp_path, monkeypatch):
    base, active = tmp_path / "021.db", tmp_path / "022.db"
    base.write_bytes(b"previous")
    active.write_bytes(b"published")
    digest = finish.fingerprint(active)
    verified = {"candidate_sha256": digest}
    release = {"path": str(active), "sha256": digest}
    for name, document in (
        ("022-verification.json", verified),
        ("022-publication.json", release),
        ("022-coherence-plan.json", {"baseline_sha256": finish.fingerprint(base)}),
    ):
        (tmp_path / name).write_text(json.dumps(document))
    monkeypatch.setattr(finish, "NOTES", tmp_path)
    monkeypatch.setattr(finish, "BASE", base)
    monkeypatch.setattr(finish, "DESTINATION", active)
    monkeypatch.setattr(finish, "resolve_lexicon_path", lambda: active)
    monkeypatch.setattr(finish, "verify_candidate", lambda *_: pytest.fail("reopened retired candidate"))
    monkeypatch.setattr(finish, "publish_round", lambda *_: pytest.fail("republished an active release"))
    assert finish.obtain_release({"candidate": "already-retired.db"}) == (verified, release)


def test_retention_routes_old_and_working_snapshots_with_protected_rollback(tmp_path, monkeypatch):
    base, active = tmp_path / "sparse-release-021.db", tmp_path / "sparse-release-022.db"
    notes, work = tmp_path / "notes", tmp_path / "work"
    notes.mkdir()
    (notes / "021-approved-source-context.json").write_text(
        json.dumps({"observations": [{"record_id": "new-context"}]})
    )
    (notes / "022-coherence-plan.json").write_text(json.dumps({"baseline_sha256": "b" * 64}))
    monkeypatch.setattr(finish, "NOTES", notes)
    monkeypatch.setattr(finish, "BASE", base)
    monkeypatch.setattr(finish, "DESTINATION", active)
    monkeypatch.setattr(finish, "WORK", work)
    calls = []

    def retire(source, installed, previous, **kwargs):
        calls.append((source, installed, previous, kwargs))
        return {"code": "FIXTURE_ARCHIVED", "path": str(source)}

    monkeypatch.setattr(finish, "retire_snapshot", retire)
    result = finish.retire_work({"epochs": [{"epoch": 1}, {"epoch": 2}]}, {"sha256": "a" * 64})
    assert result["code"] == "ACTIVE_022_ROLLBACK_021_AND_AUDITS_RETAINED"
    assert len(calls) == 5
    assert calls[0][0] == base.with_name("sparse-release-020.db")
    assert {c[0] for c in calls[1:]} == {
        work / f"zipf/epoch-{epoch:02d}" / name for epoch in (1, 2) for name in ("teaching.db", "candidate.db")
    }
    for source, installed, previous, options in calls:
        assert installed == active and previous == base and source not in {active, base}
        assert options["expected_sha256"] == "a" * 64 and options["previous_sha256"] == "b" * 64
        assert options["new_context_ids"] == ("new-context",)
        assert options["handle_check"] is finish.handles.no_open_handles
