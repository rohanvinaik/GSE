"""Connected recovery/revision consumers, with explicitly synthetic label authority."""

import gzip
import json
import sqlite3
from pathlib import Path

import pytest
from test_lexicon_epoch import Rulings, family, open_curriculum_inputs

from GSE.curation.lexicon_builder import epoch, retention
from GSE.curation.lexicon_builder.learning_curriculum import REVIEW_FORMAT
from GSE.curation.lexicon_builder.learning_state import LearningState
from GSE.curation.lexicon_builder.rule_history import digest


def state_at(directory):
    return LearningState(directory / "learning.sqlite", json.loads((directory / "arm.json").read_text()))


def warrant(directory, pending):
    item = family("learned-unit-quantity", "time_unit.n.01", ["SOMETHING", 1], ["QUANTITY", 1], "beta")
    item.update(antecedent=None, holdouts=["wordnet:beta:beta.n.01", "wordnet:gamma:gamma.n.01"])
    (directory / "reviews.json").write_text(
        json.dumps({"format": REVIEW_FORMAT, "records": [{"mechanism_id": pending, "family": item}]})
    )


@pytest.mark.parametrize(
    "boundary", ["teaching_result", "migration_result", "head_before", "head_after", "retirement_unlink"]
)
def test_resume_each_boundary_after_old_databases_are_retired(tmp_path, monkeypatch, boundary):
    base, pointer, plan, inventory = open_curriculum_inputs(tmp_path)
    directory, model = tmp_path / "learner", Rulings()
    args = (plan, base, pointer, directory, inventory, "closure", model, tmp_path / "model.lock")
    # The no-open-handles instrument itself is covered in retention's tests.
    monkeypatch.setattr(retention, "no_open_handles", lambda p: {"code": "NO_OPEN_LOCAL_FILE_MATCHES"})
    original_record, original_advance = epoch.record, LearningState.advance_head
    armed = True

    def record(path, value):
        nonlocal armed
        fail = (boundary == "teaching_result" and path.name == "teaching.json") or (
            boundary == "migration_result" and path.name == "migration.json"
        )
        if armed and fail:
            armed = False
            raise RuntimeError("simulated crash")
        original_record(path, value)

    def advance(self, outcome, transition):
        nonlocal armed
        if armed and boundary in {"head_before", "head_after"}:
            armed = False
            if boundary == "head_after":
                original_advance(self, outcome, transition)
            raise RuntimeError("simulated crash")
        return original_advance(self, outcome, transition)

    original_retirement_record = retention.record

    def retirement_record(path, value):
        nonlocal armed
        if armed and boundary == "retirement_unlink" and path.name.endswith(".retirement.json"):
            armed = False
            raise RuntimeError("simulated crash")
        return original_retirement_record(path, value)

    monkeypatch.setattr(epoch, "record", record)
    monkeypatch.setattr(LearningState, "advance_head", advance)
    monkeypatch.setattr(retention, "record", retirement_record)
    if boundary in {"teaching_result", "head_before", "head_after"}:
        with pytest.raises(RuntimeError, match="simulated crash"):
            epoch.run_arm(*args)
    first = epoch.run_arm(*args)
    assert len(model.calls) == 1
    [pending] = first["learning_state"]["pending"]
    warrant(directory, pending["mechanism_id"])
    if boundary in {"migration_result", "retirement_unlink"}:
        with pytest.raises(RuntimeError, match="simulated crash"):
            epoch.run_arm(*args)
    result = epoch.run_arm(*args)
    assert len(model.calls) == result["typed_questions_used"] == 3
    assert result["replay"]["complete_search"]
    head = state_at(directory).head()
    assert Path(head["candidate"]).is_file()
    assert len(list(directory.glob("epoch-*/*.db"))) == 1
    assert not (directory / "epoch-01/teaching.db").exists()
    [archive] = directory.glob("epoch-01/*.audit.json.gz")
    preserved = json.loads(gzip.decompress(archive.read_bytes()))
    assert preserved["source_data_checks"]["definitions"]["rows"] == 4
    assert preserved["source_data_checks"]["native_observations"]["rows"] == 4
    assert epoch.run_arm(*args) == result and len(model.calls) == 3


def test_learning_head_cas_hash_and_epoch_outcome_are_bound(tmp_path):
    state = LearningState(tmp_path / "learning.sqlite", {"synthetic": "head-cas"})
    opening = state.initialize_head(tmp_path / "opening.db", "a" * 64)
    outcome = {"epoch": 1, "candidate": str(tmp_path / "new.db"), "candidate_sha256": "b" * 64}
    transition = {
        "format": "GSE.lexicon-learning-transition/1",
        "epoch": 1,
        "prior_head": opening,
        "candidate": outcome["candidate"],
        "candidate_sha256": outcome["candidate_sha256"],
        "outcome_sha256": digest(outcome),
        "staging": [],
    }
    head = state.advance_head(outcome, transition)
    assert state.advance_head(outcome, transition) == head
    changed = {**transition, "candidate_sha256": "c" * 64}
    with pytest.raises(ValueError, match="INVALID_LEARNING_HEAD_TRANSITION"):
        state.advance_head(outcome, changed)
    with sqlite3.connect(state.path) as conn:
        conn.execute("UPDATE learning_heads SET payload='{}'")
    with pytest.raises(ValueError, match="LEARNING_HEAD_TRANSITION_HASH_MISMATCH"):
        state.head()


def test_rule_warrant_cannot_review_the_unreviewed_model_prefix(tmp_path):
    from test_lexicon_builder_source_guard_migration import AUDIT, UNIT, source_guard_packet

    from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
    from GSE.curation.lexicon_builder.residual import _request_id

    base, _, _, _ = source_guard_packet(tmp_path)
    with sqlite3.connect(base) as conn:
        prefix, target = read_model_receipts(conn)[UNIT]
    candidate = epoch.Family(
        "synthetic-prefix-review",
        None,
        ("BE", 0),
        (("pos", "noun"), ("wordnet_ancestor:linear_unit.n.01", "true")),
        (AUDIT,),
        {
            "reviewer": "fixture",
            "source_refs": ["synthetic:new-law-warrant"],
            "statement": "A new law does not review an earlier model answer.",
        },
    )
    taught = {"request_id": target["request_id"], "receipt_sha256": _request_id(target), "value": 0}
    with pytest.raises(ValueError, match="LEARNING_MODEL_PREFIX_REVIEW_REQUIRED:" + prefix["request_id"]):
        epoch.reviewed_input(base, candidate, {"entry_id": UNIT}, taught)
    review = {
        "request_id": prefix["request_id"],
        "review": {
            "code": "ACCEPTED",
            "receipt_sha256": _request_id(prefix),
            "review_id": "synthetic:prefix-review",
            "reviewer": "fixture",
            "source_refs": ["synthetic:separate-prefix-review"],
            "rationale": "Independent explicit fixture review of the exact prior answer.",
        },
    }
    raw = epoch.reviewed_input(base, candidate, {"entry_id": UNIT}, taught, prefix_reviews=[review])
    assert {row["receipt"]["request_id"] for row in raw["rulings"]} == {prefix["request_id"], target["request_id"]}
    assert raw["rulings"][0]["receipt"] in (prefix, target)


def test_joint_revision_is_consumed_by_same_frozen_controller_and_retraction_reopens(tmp_path, monkeypatch):
    from dataclasses import replace

    import test_lexicon_builder_source_guard_migration as fixture
    from test_lexicon_builder_source_guard_migration import AUDIT, HOMOGRAPH, source_guard_packet, states

    from GSE.curation.lexicon_builder.learning_curriculum import plan_inventory
    from GSE.curation.lexicon_builder.rule_admission import admit_rule
    from GSE.curation.lexicon_builder.rule_revisions import FORMAT

    native = fixture.native_definition

    def attested(*args, **kwargs):
        definition, observation = native(*args, **kwargs)
        return definition, replace(observation, features={**observation.features, "lemma_names": [definition.lemma]})

    monkeypatch.setattr(fixture, "native_definition", attested)
    base, input_path, audit_path, review = source_guard_packet(tmp_path)
    admission = admit_rule(input_path, audit_path, review)
    pointer = tmp_path / "pointer.json"
    pointer.write_text("{}")
    directory = tmp_path / "learner"
    directory.mkdir()
    revision = {
        "format": FORMAT,
        "baseline_version": admission["baseline_version"],
        "admissions": [admission],
        "retirements": [],
        "exceptions": [],
    }
    intake = {"format": "GSE.lexicon-learning-revisions/1", "records": [revision]}
    (directory / "revision-reviews.json").write_text(json.dumps(intake))

    # The revision path needs no new lexical model answer.
    class NoCall:
        identity = "synthetic:no-new-labels"

        def __call__(self, payload, schema):
            raise AssertionError("joint migration must use retained audit evidence")

    plan = {
        "format": "GSE.lexicon-epoch-plan/2",
        "baseline_sha256": epoch.fingerprint(base),
        "active_pointer_sha256": epoch.fingerprint(pointer),
        "epochs": 2,
        "audits_per_epoch": 1,
        "families": [],
        "teaching_entry_ids": [AUDIT],
        "curriculum": {
            "banks": ["WANT"],
            "frontier_limit": 4,
            "banks_per_entry": 1,
            "candidate_limit": 1,
            "audit_entry_ids": [AUDIT],
            "scopes": [
                {
                    "id": "curriculum:unit",
                    "guards": [
                        ["pos", "noun"],
                        ["wordnet_native_lemma", "true"],
                        ["wordnet_ancestor:linear_unit.n.01", "true"],
                    ],
                }
            ],
        },
    }
    inventory = plan_inventory(base, plan)
    monkeypatch.setattr(retention, "no_open_handles", lambda p: {"code": "NO_OPEN_LOCAL_FILE_MATCHES"})
    args = (plan, base, pointer, directory, inventory, "closure", NoCall(), tmp_path / "model.lock")
    # Stop exactly after first head installation to enqueue the reviewed
    # retirement under the same immutable plan and remaining epoch budget.
    original = retention.retire_learning_stages

    def pause(*args):
        original(*args)
        raise RuntimeError("pause for explicit retirement review")

    monkeypatch.setattr(retention, "retire_learning_stages", pause)
    with pytest.raises(RuntimeError, match="pause for explicit"):
        epoch.run_arm(*args)
    first = state_at(directory).head()
    assert states(first["candidate"])[AUDIT]["domains"]["WANT"] == [0]
    with sqlite3.connect(first["candidate"]) as conn:
        rules = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
    rule = next(row for row in rules if row["rule_id"] == review["rule_id"])
    retirement = {
        "format": FORMAT,
        "baseline_version": digest(rules),
        "admissions": [],
        "retirements": [
            {
                "rule_id": rule["rule_id"],
                "rule_sha256": digest(rule),
                "review_id": "synthetic:retire",
                "reviewer": "fixture",
                "source_refs": ["synthetic:retraction"],
                "rationale": "Explicit synthetic retraction.",
            }
        ],
        "exceptions": [],
    }
    (directory / "revision-reviews.json").write_text(
        json.dumps({"format": intake["format"], "records": [revision, retirement]})
    )
    monkeypatch.setattr(retention, "retire_learning_stages", original)
    result = epoch.run_arm(*args)
    assert [row["code"] for row in result["epochs"]] == ["RULE_REVISION_APPLIED"] * 2
    assert result["typed_questions_used"] == 0 and result["replay"]["complete_search"]
    assert states(result["candidate"])[AUDIT]["domains"]["WANT"] == [-1, 0, 1]
    assert states(result["candidate"])[HOMOGRAPH]["domains"]["WANT"] == [1]
    assert len(list(directory.glob("epoch-*/*.db"))) == 1
    assert epoch.run_arm(*args) == result
