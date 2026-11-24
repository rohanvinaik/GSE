"""Review and replay the already source-warranted own-happening checkpoint child.

This is orchestration of the existing exporter/audit/admission/migration path,
not another constructor. It never activates a checkpoint. Historical 66-law
audit replies are retained but are NOT rebound to changed 68-law requests.
"""

import json
from contextlib import closing
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import (
    Family,
    JournaledTransport,
    connect,
    exact_delta,
    fingerprint,
    forecast,
    read,
    record,
    reviewed_input,
    scope_rows,
)
from GSE.curation.lexicon_builder.learning_state import LearningState
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.residual import OllamaTransport, _request_id
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_admission import admit_records
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.rule_migration import migrate_revision
from GSE.curation.lexicon_builder.rule_revisions import FORMAT as REVISION_FORMAT
from GSE.curation.lexicon_builder.specification import compare_measurements, measure_dictionary
from GSE.curation.lexicon_builder.validation import _relations


def child_family(raw):
    """Keep the frozen native child, warrant, and disjoint audit roster exact."""
    if raw["id"] != "native-own-happening-child" or raw["antecedent"] is not None or raw["absent_evidence"]:
        raise ValueError("CHECKPOINT_HAPPENING_FROZEN_CHILD_CHANGED")
    return Family(
        raw["id"],
        None,
        tuple(raw["consequent"]),
        tuple(tuple(pair) for pair in raw["guards"]),
        tuple(raw["holdouts"]),
        raw["warrant"],
    )


def require_audits(report):
    """An abstention is pending scope review, never an opposing sign or zero."""
    [candidate] = report["candidates"]
    if len(candidate["audits"]) != 3 or any(row["code"] != "MODEL_AGREEMENT" for row in candidate["audits"]):
        raise ValueError("CHECKPOINT_HAPPENING_INDEPENDENT_AUDIT_PENDING")
    return candidate


def main():
    notes = Path(__file__).resolve().parent
    work = notes.parents[2] / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint"
    source = work / "candidate.db"
    output = work / "checkpoint-base.db"
    completed = work / "happening-result.json"
    if completed.exists() or output.exists():
        raise ValueError("CHECKPOINT_HAPPENING_ALREADY_INSTALLED_VERIFY_RECEIPTS_DO_NOT_REPEAT")
    writer = read(notes / "ssl-api-controller-prime-child-writer.json")
    source_sha = fingerprint(source)
    if writer["after_sha256"] != source_sha or writer["database"] != str(source):
        raise ValueError("CHECKPOINT_HAPPENING_TEACHING_HEAD_CHANGED")
    before = read(work / "space-post-prime-child-teaching.json")
    family_path = notes / "ssl-api-controller-happening-child.json"
    family = child_family(read(family_path)["family"])
    discovery = "wordnet:explosion:explosion.n.01"
    with closing(connect(source)) as conn:
        receipts = read_model_receipts(conn).get(discovery, ())
    matches = [row for row in receipts if row["assertion"]["bank"] == "HAPPEN"]
    if len(matches) != 1 or matches[0]["assertion"]["value"] != 1:
        raise ValueError("CHECKPOINT_HAPPENING_DISCOVERY_NOT_INDEPENDENTLY_ACCEPTED")
    [receipt] = matches
    raw = reviewed_input(
        source,
        family,
        {"entry_id": discovery},
        {"request_id": receipt["request_id"], "receipt_sha256": _request_id(receipt)},
    )
    record(work / "happening-current-input.json", raw)
    prepared = run_workflow_input(raw, max_calls=0)
    record(work / "happening-current-prepared-audit.json", prepared)
    settings = read(notes / "ssl-root-prime-transport.json")["configuration"]
    transport = OllamaTransport(
        settings["model"],
        timeout=settings["timeout_seconds"],
        context_tokens=settings["context_tokens"],
        thinking=settings["thinking"],
        output_tokens=settings["output_tokens"],
    )
    transport.pin()
    if transport.identity != settings["identity"]:
        raise ValueError("CHECKPOINT_HAPPENING_MODEL_IDENTITY_CHANGED")
    directory = work / "happening-current-audits"
    directory.mkdir(exist_ok=True)
    store = LearningState(
        directory / "requests.sqlite",
        {
            "source_sha256": source_sha,
            "reviewed_input_sha256": _request_id(raw),
            "family_sha256": fingerprint(family_path),
            "transport": transport.identity,
            "authority": "QUESTION_ARCHIVE_ONLY",
        },
    )
    journal = JournaledTransport(
        transport,
        directory,
        "current-happening",
        3,
        work.parent / "checkpoint-local-model.lock",
        context_store=store,
    )
    audited = run_workflow_input(raw, journal, max_calls=3)
    record(work / "happening-current-audit.json", audited)
    candidate = require_audits(audited)
    review = {
        "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "checkpoint-admission:native-own-happening-child",
        "reviewer": family.warrant["reviewer"],
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "source_refs": family.warrant["source_refs"],
        "rationale": family.warrant["statement"],
    }
    admission = admit_records(raw, audited, review)
    record(work / "happening-admission.json", admission)
    inventory = read(work / "happening-child-inventory.json")[family.id]
    rules, rows = scope_rows(source, inventory)
    proposals = _relations(json.loads(json.dumps([admission["relation"]])))
    staged = forecast(rows, rules, proposals)
    record(work / "happening-stage.json", staged)
    if staged["contradictions"] or staged["progress_code"] != "CONTRACTION":
        raise ValueError("CHECKPOINT_HAPPENING_SCOPE_CHALLENGE_OR_NO_CONTRACTION")
    revision = {
        "format": REVISION_FORMAT,
        "baseline_version": admission["baseline_version"],
        "admissions": [admission],
        "retirements": [],
        "exceptions": [],
    }
    record(work / "happening-revision.json", revision)
    migration = migrate_revision(source, output, revision)
    record(work / "happening-migration.json", migration)
    if migration["postflight"]["code"] != "REPLAY_VALIDATED" or not migration["postflight"]["complete_search"]:
        raise ValueError("CHECKPOINT_HAPPENING_FULL_REPLAY_FAILED")
    count, changes = exact_delta(source, output)

    def by_cell(records):
        return {(row["entry_id"], row["bank"]): row for row in records}

    if by_cell(changes) != by_cell(staged["changes"]):
        raise ValueError("CHECKPOINT_HAPPENING_STAGE_COMMIT_DELTA_MISMATCH")
    after = measure_dictionary(output)
    record(work / "space-post-happening-revision.json", after)
    record(
        completed,
        {
            "code": "OWN_HAPPENING_CHILD_REPLAYED_WORKLOAD_GATE_PENDING",
            "candidate": str(output),
            "candidate_sha256": fingerprint(output),
            "source_sha256": source_sha,
            "revision_sha256": digest(revision),
            "definitions_replayed": count,
            "replay": migration["postflight"],
            "actual_fresh_audit_questions": journal.count(),
            "historical_audit_policy": "Old 66-law audit replies retained, never rebound to current 68-law questions.",
            "rule_revision": compare_measurements(before, after),
            "active_pointer_changed": False,
            "activation_performed": False,
        },
    )
    print(json.dumps(read(completed)), flush=True)


if __name__ == "__main__":
    main()
