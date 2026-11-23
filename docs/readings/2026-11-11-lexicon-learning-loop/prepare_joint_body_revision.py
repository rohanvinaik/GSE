"""Assemble the source-reviewed BODY revision from the recorded cycle receipts."""

import json
from pathlib import Path

from GSE.curation.lexicon_builder.interchange import read_json
from GSE.curation.lexicon_builder.reviewed_export import export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_admission import _AuditReplay, admit_records
from GSE.curation.lexicon_builder.rule_history import digest

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
SOURCE = ROOT / "data/lexicon_builder/2026-11-01/constructed-corpus-joint-teaching.db"


def save(name, value):
    with (FOLDER / name).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main():
    cycle_file = FOLDER / "joint-body-cycle-plan-final.json"
    cycle = read_json(cycle_file)
    scope = read_json(FOLDER / "joint-body-source-scope.json")
    teaching = read_json(FOLDER / "joint-teaching-checkpoint.json")
    evidence_ref = str((FOLDER / "joint-body-source-scope.json").relative_to(ROOT))
    selected = {
        "format": "GSE.reviewed-pattern-selection/1",
        "discovery_entry_ids": teaching["selected_entry_ids"],
        "audit_entry_ids": [],
        "reviews": [],
    }
    inventory = {
        row["entry_id"]: row for row in export_reviewed_input(SOURCE, selected)["inventory"] if row["bank"] == "BODY"
    }
    plan = {"format": "GSE.rule-revision-plan/1", "admissions": [], "retirements": [], "exceptions": []}
    outputs = {}
    for name, family in cycle["families"].items():
        members = {row["definition"]["entry_id"]: row for row in scope[family["ancestor"]]}
        reviews = []
        for entry in family["discovery"]:
            row = inventory.get(entry)
            if row is None or row["receipt"]["assertion"]["value"] != 0:
                raise ValueError("BODY_DISCOVERY_REQUIRES_REVIEW:" + entry)
            reviews.append(
                {
                    "request_id": row["request_id"],
                    "review": {
                        "code": "ACCEPTED",
                        "receipt_sha256": row["receipt_sha256"],
                        "review_id": "joint-body-source-review:" + entry,
                        "reviewer": "Codex source-backed review",
                        "source_refs": [evidence_ref, "exact-source:sha256:" + members[entry]["source_sha256"]],
                        "rationale": (
                            "The exact lexical definition supplies a conventional unit of length or denomination. "
                            "Its defining magnitude is independent of bodily structure."
                        ),
                    },
                }
            )
        selection = {**selected, "discovery_entry_ids": family["discovery"], "reviews": reviews}
        observed = run_workflow_input(export_reviewed_input(SOURCE, selection)["input"])
        pairs = [
            row
            for row in observed["candidates"]
            if tuple(row["antecedent"]) == ("QUANTITY", 1) and tuple(row["consequent"]) == ("BODY", 0)
        ]
        if len(pairs) != 1 or pairs[0]["discovery_outcomes"] != {"OBSERVED_AGREEMENT": len(reviews)}:
            raise ValueError("BODY_DISCOVERY_REQUIRES_SUPPORTED_PAIR")
        selection.update(audit_entry_ids=family["audit"], guarded_candidates=[family["proposal"]])
        raw = export_reviewed_input(SOURCE, selection)["input"]
        [withheld] = read_json(FOLDER / f"joint-{name}-withheld.json")["candidates"]
        replay = _AuditReplay(withheld["audits"])
        audited = run_workflow_input(raw, replay, max_calls=len(withheld["audits"]))
        [candidate] = audited["candidates"]
        if replay.index != len(withheld["audits"]):
            raise ValueError("BODY_WITHHELD_REPLAY_INCOMPLETE")
        review = {
            "rule_id": candidate["relation"]["rule_id"],
            "warrant_sha256": candidate["warrant_sha256"],
            "review_id": "joint-body-admission:" + name,
            "reviewer": "Codex source-backed review",
            "decision": "APPROVE_DEFINITIONAL_RULE",
            "source_refs": [evidence_ref, cycle_file.name, f"joint-{name}-withheld.json"],
            "rationale": family["statement"],
        }
        admission = admit_records(raw, audited, review)
        baseline = plan.setdefault("baseline_version", admission["baseline_version"])
        if admission["baseline_version"] != baseline:
            raise ValueError("BODY_REVISION_BASELINE_CHANGED")
        files = {kind: f"joint-{name}-{kind}.json" for kind in ("input", "audit", "review")}
        plan["admissions"].append(files)
        outputs.update({files["input"]: raw, files["audit"]: audited, files["review"]: review})
        outputs[f"joint-{name}-observed-pair.json"] = pairs[0]
        if name == "linear":
            for entry, rationale in cycle["exceptions"].items():
                record = {
                    "rule_id": review["rule_id"],
                    "entry_id": entry,
                    "source_sha256": members[entry]["source_sha256"],
                    "counterexample": {"QUANTITY": 1, "BODY": 1},
                    "review_id": "joint-body-exception:" + entry,
                    "reviewer": "Codex source-backed review",
                    "rationale": rationale,
                    "source_refs": [evidence_ref],
                }
                teaching_receipt = inventory.get(entry)
                if teaching_receipt is not None and teaching_receipt["receipt"]["assertion"]["value"] != 1:
                    record["withdraw_model_receipt_sha256"] = digest(teaching_receipt["receipt"])
                    record["rationale"] += (
                        " The model's ruling omitted this constitutive bodily reference. "
                        "Retire its exact receipt and preserve any remaining independent support."
                    )
                plan["exceptions"].append(record)
    outputs["joint-body-teaching-review.json"] = [
        {
            "entry_id": entry,
            "code": (
                "UNRESOLVED"
                if entry not in inventory
                else "WITHDRAW_REVIEWED_MODEL_DISAGREEMENT"
                if entry in cycle["exceptions"] and inventory[entry]["receipt"]["assertion"]["value"] != 1
                else "IN_SCOPE_CONTRARY"
                if entry in cycle["exceptions"]
                else "BODY_ORTHOGONALITY"
                if inventory[entry]["receipt"]["assertion"]["value"] == 0
                else "REQUIRES_SOURCE_REVIEW"
            ),
            **(
                {
                    "receipt_sha256": inventory[entry]["receipt_sha256"],
                    "value": inventory[entry]["receipt"]["assertion"]["value"],
                }
                if entry in inventory
                else {}
            ),
        }
        for entry in teaching["selected_entry_ids"]
    ]
    outputs["joint-body-revision-plan.json"] = plan
    for name, value in outputs.items():
        save(name, value)
    print(
        json.dumps(
            {"admissions": len(plan["admissions"]), "exceptions": len(plan["exceptions"]), "plan_sha256": digest(plan)}
        )
    )


if __name__ == "__main__":
    main()
