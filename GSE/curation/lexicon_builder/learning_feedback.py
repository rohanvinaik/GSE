"""Durable typed feedback and reviewed joint revisions on the ordinary learner.

These records grant no new semantic authority. Additions carry the existing
independently audited admissions; retirements, exceptions and reservations
retain their ordinary reviewed migration contracts and complete replay.
"""

from contextlib import closing
from pathlib import Path

from .rule_history import digest
from .rule_revisions import validate_revision_shape
from .specification import CONTRACT, compare_measurements, measure_dictionary


def refresh_intake(directory, learning):
    from .epoch import read
    from .reviewed_patterns import reviewed_rulings

    path = directory / "revision-reviews.json"
    if path.exists():
        raw = read(path)
        if (
            type(raw) is not dict
            or raw.keys() != {"format", "records"}
            or raw["format"] != "GSE.lexicon-learning-revisions/1"
        ):
            raise ValueError("INVALID_LEARNING_REVISION_INTAKE")
        if type(raw["records"]) is not list:
            raise ValueError("INVALID_LEARNING_REVISION_INTAKE")
        for revision in raw["records"]:
            validate_revision_shape(revision)
            # Admission and source witnesses are rechecked by migrate_revision,
            # not trusted because this queue accepted a shape-valid packet.
            learning.retain_work("REVIEWED_RULE_REVISION", revision, disposition="READY")
    path = directory / "receipt-reviews.json"
    if path.exists():
        raw = read(path)
        if (
            type(raw) is not dict
            or raw.keys() != {"format", "records"}
            or raw["format"] != "GSE.lexicon-learning-receipt-reviews/1"
        ):
            raise ValueError("INVALID_LEARNING_RECEIPT_REVIEW_INTAKE")
        reviewed_rulings(raw["records"])
        for row in raw["records"]:
            learning.retain_work("MODEL_PREFIX_REVIEW", row, disposition="READY")
        available = {
            row["payload"]["receipt"]["request_id"]
            for row in learning.work(kind="MODEL_PREFIX_REVIEW", disposition="READY")
        }
        for mechanism in learning.reviewed():
            if mechanism["disposition"] != "AWAITING_PREFIX_REVIEW":
                continue
            requests = [
                work["payload"]["reason"].split(":", 1)[1].split(",")
                for work in learning.work(kind="MODEL_PREFIX_REVIEW_REQUIRED")
                if work["payload"]["selected"].get("family") == mechanism["family"]["id"]
            ]
            if requests and all(set(required) <= available for required in requests):
                learning.disposition(
                    mechanism["mechanism_id"], "READY_FOR_TEACHING", {"code": "EXPLICIT_PREFIX_REVIEWS_RECEIVED"}
                )


def revision_choice(candidate, learning):
    from .epoch import connect
    from .rule_history import relation_records
    from .validation import _metadata, _relations

    with closing(connect(candidate)) as conn:
        version = digest(relation_records(_relations(_metadata(conn, "relations"))))
    for row in learning.work(kind="REVIEWED_RULE_REVISION", disposition="READY"):
        if row["payload"]["baseline_version"] == version:
            return {
                "task": "REVIEWED_RULE_REVISION",
                "family": None,
                "work_sha256": row["work_sha256"],
                "revision": row["payload"],
            }
        learning.retain_work(
            "STALE_DEPENDENCY",
            {
                "revision_sha256": row["work_sha256"],
                "current_rule_version": version,
                "remedy": "REBASE_AND_REAUDIT_CHANGED_DEPENDENCIES",
            },
        )
    return None


def apply_revision(base, phase, selected):
    from .epoch import exact_delta, fingerprint, gains, read, record
    from .rule_migration import migrate_revision
    from .validation import validate_build

    revision = selected["revision"]
    if digest({"kind": "REVIEWED_RULE_REVISION", "payload": revision}) != selected["work_sha256"]:
        raise ValueError("LEARNING_REVISION_WORK_CHANGED")
    before_path, after_path = phase / "space-baseline.json", phase / "space-post-revision.json"
    if not before_path.exists():
        record(before_path, measure_dictionary(base))
    before = read(before_path)
    output, migration_path = phase / "candidate.db", phase / "migration.json"
    if not output.exists():
        record(migration_path, migrate_revision(base, output, revision))
    replay = read(migration_path)["postflight"] if migration_path.exists() else validate_build(output)
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("LEARNING_REVISION_REPLAY_FAILED")
    if not migration_path.exists():
        # Refuse an unrelated installed output after the atomic-link boundary.
        from .epoch import connect
        from .rule_history import read_history
        from .validation import _metadata, _relations

        with closing(connect(output)) as conn:
            history = read_history(conn, _relations(_metadata(conn, "relations")))
        if not history or digest(history["events"][-1].get("revision")) != digest(revision):
            raise ValueError("LEARNING_RECOVERED_REVISION_CHANGED")
        record(phase / "recovered-replay.json", replay)
    if not after_path.exists():
        record(after_path, measure_dictionary(output))
    after = read(after_path)
    count, changes = exact_delta(Path(base), output)
    return {
        "code": "RULE_REVISION_APPLIED",
        "selected": selected,
        "candidate": str(output),
        "candidate_sha256": fingerprint(output),
        "definitions_replayed": count,
        "replay": replay,
        "changes": changes,
        "symbolic_new_cells": len(gains({"changes": changes})),
        "reopened_cells": sum(len(row["before"]) == 1 and len(row["after"]) > 1 for row in changes),
        "typed_questions_used": 0,
        "retained_admission_audit_questions": sum(a["audit"]["model_calls"] for a in revision["admissions"]),
        "semantic_review_kind": "EXPLICIT_JOINT_REVISION_NOT_AUTOMATIC_MODEL_CORRECTION",
        "specification_learning": {
            "contract": CONTRACT,
            "baseline": before,
            "post_teaching": before,
            "post_revision": after,
            "direct_teaching": compare_measurements(before, before),
            "rule_revision": compare_measurements(before, after),
            "total": compare_measurements(before, after),
        },
    }


def retain_feedback(learning, outcome):
    """Keep every available challenge, rival derivation and named next action."""
    if "surprise" in outcome:
        learning.retain_work("MODEL_DISAGREEMENT", outcome["surprise"])
    if outcome.get("reason", "").startswith("LEARNING_MODEL_PREFIX_REVIEW_REQUIRED:"):
        learning.retain_work(
            "MODEL_PREFIX_REVIEW_REQUIRED",
            {"selected": outcome["selected"], "reason": outcome["reason"], "remedy": "EXPLICIT_EXACT_RECEIPT_REVIEWS"},
        )
    for row in outcome.get("scope_surprises", ()):
        learning.retain_work(row["code"], row)
    refinement = outcome.get("refinement", {})
    for row in refinement.get("counterexamples", ()):
        learning.retain_work("SCOPE_CHALLENGE", {"parent_mechanism_id": refinement["parent_mechanism_id"], **row})
    for row in refinement.get("reservations", ()):
        learning.retain_work(
            "UNRESOLVED_AUDIT_RESERVATION", {"parent_mechanism_id": refinement["parent_mechanism_id"], "audit": row}
        )
