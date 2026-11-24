"""Control records preserve challenges without becoming lexical authority."""

import json
import sqlite3

import pytest

from GSE.curation.lexicon_builder.engine import Relation
from GSE.curation.lexicon_builder.learning_state import LearningState, mechanism_id


def rule(name="synthetic", *, reverse=False):
    return Relation(
        name,
        ("WANT", "THINK") if reverse else ("THINK", "WANT"),
        ((-1, -1), (0, 0), (1, 1)),
        ("synthetic:learning-control",),
        "conditional",
        True,  # Even a staged object's flag cannot grant ledger approval.
        (("pos", "noun"),),
    )


def test_same_mechanism_deduplicates_labels_and_axis_order_without_admission(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    first = state.propose(rule(), {"source_ref": "fixture:one"}, origin="fixture")
    second = state.propose(rule("another-label", reverse=True), {"source_ref": "fixture:one"}, origin="fixture")
    assert first == second == mechanism_id(rule())
    assert state.ready() == []
    assert [row["disposition"] for row in state.pending()] == ["AWAITING_WARRANT"]
    with sqlite3.connect(state.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM mechanisms").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM mechanism_evidence").fetchone()[0] == 1
        assert not {"lexemes", "primitive_values", "definition_states"}.intersection(
            name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )


def test_review_requires_observed_contract_and_blocked_review_does_not_reset_on_resume(tmp_path):
    identity = {"plan": "fixture", "model": "pinned"}
    state = LearningState(tmp_path / "learning.sqlite", identity)
    key = state.propose(rule(), {"source_ref": "fixture:one"}, origin="fixture")
    family = {"id": "synthetic", "warrant": {"source_refs": ["synthetic:review"]}}
    with pytest.raises(ValueError, match="LEARNING_REVIEW_MECHANISM_CHANGED"):
        state.review("0" * 64, rule(), family)
    state.review(key, rule(), family)
    assert state.ready() == [{"mechanism_id": key, "family": family}]
    state.disposition(key, "NEEDS_REFINEMENT", {"counterexample": "fixture:negative"})
    resumed = LearningState(state.path, identity)
    resumed.review(key, rule(), family)
    assert resumed.ready() == []
    assert resumed.pending()[0]["disposition"] == "NEEDS_REFINEMENT"
    with pytest.raises(ValueError, match="LEARNING_REVIEW_CHANGED_REQUIRES_VERSIONED_REVISION"):
        resumed.review(key, rule(), {**family, "id": "silently-changed"})


def test_changed_run_or_missing_schema_never_relabels_existing_control_records(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"plan": "original"})
    state.propose(rule(), {"source_ref": "fixture:one"}, origin="fixture")
    before = state.path.read_bytes()
    with pytest.raises(ValueError, match="LEARNING_RUN_IDENTITY_CHANGED"):
        LearningState(state.path, {"plan": "different"})
    assert state.path.read_bytes() == before
    with sqlite3.connect(state.path) as conn:
        conn.execute("DROP TABLE learning_epochs")
    broken = state.path.read_bytes()
    with pytest.raises(ValueError, match="INCOMPLETE_LEARNING_SCHEMA"):
        LearningState(state.path, {"plan": "original"})
    assert state.path.read_bytes() == broken


def test_epoch_history_is_immutable_and_payload_tampering_is_detected(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    outcome = {"epoch": 1, "code": "RULE_CHALLENGED_BY_TEACHING", "observed": 0}
    state.record_epoch(1, outcome)
    state.record_epoch(1, outcome)
    assert state.epochs() == [outcome]
    with pytest.raises(ValueError, match="LEARNING_EPOCH_CHANGED"):
        state.record_epoch(1, {**outcome, "observed": 1})
    with sqlite3.connect(state.path) as conn:
        conn.execute("UPDATE learning_epochs SET outcome=?", (json.dumps({**outcome, "observed": 1}),))
    with pytest.raises(ValueError, match="LEARNING_EPOCH_HASH_MISMATCH"):
        state.epochs()


def test_unrelated_database_and_busy_writer_have_distinct_refusals(tmp_path):
    foreign = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(foreign) as conn:
        conn.execute("CREATE TABLE unrelated (value TEXT)")
    before = foreign.read_bytes()
    with pytest.raises(ValueError, match="UNRELATED_DATABASE_IS_NOT_LEARNING_STATE"):
        LearningState(foreign, {"run": "fixture"})
    assert foreign.read_bytes() == before
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    with sqlite3.connect(state.path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="LEARNING_STATE_BUSY"):
            state.pending()


@pytest.mark.parametrize("evidence,origin", [(None, "fixture"), ({}, "fixture"), ({"source": "one"}, "")])
def test_missing_evidence_is_not_a_supporting_observation(tmp_path, evidence, origin):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    with pytest.raises(ValueError, match="LEARNING_PROPOSAL_REQUIRES_EVIDENCE_REFERENCE"):
        state.propose(rule(), evidence, origin=origin)
    assert state.pending() == []


def test_unreviewed_mechanism_cannot_be_marked_ready(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    key = state.propose(rule(), {"source_ref": "fixture:one"}, origin="fixture")
    with pytest.raises(ValueError, match="LEARNING_WARRANT_REQUIRED"):
        state.disposition(key, "READY_FOR_TEACHING", {})
    assert state.ready() == []


def test_review_batch_rolls_back_valid_prefix_when_another_review_is_invalid(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    key = state.propose(rule(), {"source_ref": "fixture:one"}, origin="fixture")
    other = Relation("another", ("WANT",), ((0,),), ("synthetic:other",))
    other_key = state.propose(other, {"source_ref": "fixture:two"}, origin="fixture")
    with pytest.raises(ValueError, match="LEARNING_REVIEW_MECHANISM_CHANGED"):
        state.review_many(((key, rule(), {"id": "valid"}), (other_key, rule(), {"id": "wrong-contract"})))
    assert state.ready() == []
    assert {row["disposition"] for row in state.pending()} == {"AWAITING_WARRANT"}


def test_an_old_review_intake_cannot_revive_a_rejected_unreviewed_hypothesis(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"run": "fixture"})
    key = state.propose(rule(), {"source_ref": "fixture:one"}, origin="fixture")
    state.disposition(key, "REJECTED", {"reason": "synthetic:counterexample"})
    with pytest.raises(ValueError, match="LEARNING_REVIEW_NOT_AWAITING_WARRANT"):
        state.review(key, rule(), {"id": "late-review"})
    assert state.ready() == []
