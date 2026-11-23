"""Review the native measurement scope and replay disjoint QUANTITY audits."""

from replay_body_exceptions import FOLDER, ROOT, read, write

from GSE.curation.lexicon_builder.reviewed_export import export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_admission import _AuditReplay, admit_records

SOURCE = ROOT / "data/lexicon_builder/2026-11-01/constructed-corpus-unit-quantity-teaching.db"
SCOPE = FOLDER / "native-unit-quantity-scope.json"
SEED = "wordnet:unit:unit_of_measurement.n.01"
EXCLUSIONS = {
    "partition.n.02": "Allocation and access as a single logical volume define this sense. No measurement standard or quantitative granule is specified.",
    "word.n.07": "The gloss defines a stored string of bits. The example's machine-dependent size does not establish a measuring standard for this exact sense.",
    "em.n.01": "The gloss defines a printing spacer by square shape. The separate em.n.02 sense defines a linear measure.",
    "electromagnetic_unit.n.01": "The gloss identifies a system of units. Membership in that system alone does not give the system its own magnitude.",
    "exposure.n.06": "The gloss defines intensity at a film or plate. A separate warrant is needed for the measured property itself.",
}
PRIOR_BRANCHES = ("linear_unit.n.01", "monetary_unit.n.01")
STATEMENT = (
    "For the reviewed native noun senses, the quantitative standard, amount, or counted granule is part of the "
    "exact definition. This grounds QUANTITY=+1 when the noun denotes SOMETHING. The WordNet membership guard "
    "selects that role within the audited population. The explicitly listed exact boundary senses require a "
    "separate derivation. Linear and monetary branches already have a QUANTITY proof and are outside this revision."
)


def main():
    scope = read(SCOPE)
    teaching = read(FOLDER / "native-unit-quantity-teaching.json")
    if teaching["outcomes"] != {"ASSIGNED": 1} or teaching["selected_entry_ids"] != [SEED]:
        raise ValueError("QUANTITY_TEACHING_NOT_RECORDED")
    native = [row for row in scope["witnesses"] if row["native_lemma"]]
    prior = [row for row in native if any(set(PRIOR_BRANCHES).intersection(path) for path in row["paths"])]
    if any(row["domains"]["QUANTITY"] != [1] for row in prior):
        raise ValueError("PRIOR_MEASUREMENT_BRANCH_NOT_RESOLVED")
    excluded = [row for row in native if row["synset"] in EXCLUSIONS]
    eligible = [
        row
        for row in native
        if row not in prior and row["synset"] not in EXCLUSIONS and row["domains"]["SOMETHING"] == [1]
    ]
    if len(native) != len(prior) + len(excluded) + len(eligible):
        raise ValueError("UNCLASSIFIED_MEASUREMENT_SCOPE")
    expected_delta = sorted(row["definition"]["entry_id"] for row in eligible if len(row["domains"]["QUANTITY"]) > 1)
    scope_review = FOLDER / "unit-quantity-scope-review.json"
    scope_ref = str(scope_review.relative_to(ROOT))
    prepared = read(FOLDER / "unit-banks-probe-requests.json")
    all_questions = {
        item["request"]["entry_id"]: item for item in prepared["questions"] if item["request"]["bank"] == "QUANTITY"
    }
    excluded_ids = {row["definition"]["entry_id"] for row in excluded}
    audits = sorted(set(all_questions) - excluded_ids)
    if len(audits) != 5 or set(audits) & {SEED}:
        raise ValueError("QUANTITY_DISJOINT_AUDIT_MISMATCH")
    write(
        scope_review,
        {
            "format": "GSE.unit-quantity-scope-review/1",
            "baseline_sha256": scope["candidate_sha256"],
            "scope_census": str(SCOPE.relative_to(ROOT)),
            "native_entries": len(native),
            "previously_proved_branches": {"ancestors": list(PRIOR_BRANCHES), "entries": len(prior)},
            "eligible_entries": len(eligible),
            "expected_new_quantity_positive": expected_delta,
            "scope_exclusions": [{**row, "rationale": EXCLUSIONS[row["synset"]]} for row in excluded],
            "audit_scope_exclusions": sorted(set(all_questions) & excluded_ids),
            "statement": STATEMENT,
        },
    )
    selection = {
        "format": "GSE.reviewed-pattern-selection/1",
        "discovery_entry_ids": [SEED],
        "audit_entry_ids": [],
        "reviews": [],
    }
    [seed] = export_reviewed_input(SOURCE, selection)["inventory"]
    if seed["bank"] != "QUANTITY" or seed["receipt"]["assertion"]["value"] != 1:
        raise ValueError("QUANTITY_SEED_REQUIRES_EXACT_POSITIVE")
    [seed_scope] = [row for row in eligible if row["definition"]["entry_id"] == SEED]
    reviewer = "Codex source-backed review"
    selection.update(
        audit_entry_ids=audits,
        reviews=[
            {
                "request_id": seed["request_id"],
                "review": {
                    "code": "ACCEPTED",
                    "receipt_sha256": seed["receipt_sha256"],
                    "review_id": "native-measurement-unit-quantity-seed",
                    "reviewer": reviewer,
                    "source_refs": [scope_ref, "exact-source:sha256:" + seed_scope["source_sha256"]],
                    "rationale": "The exact source defines a unit as a division of quantity adopted as a measurement or exchange standard.",
                },
            }
        ],
        guarded_candidates=[
            {
                "antecedent": ["SOMETHING", 1],
                "consequent": ["QUANTITY", 1],
                "guards": [
                    ["pos", "noun"],
                    ["wordnet_native_lemma", "true"],
                    ["wordnet_ancestor:unit_of_measurement.n.01", "true"],
                    *[[f"wordnet_outside_ancestor:{ancestor}", "true"] for ancestor in PRIOR_BRANCHES],
                    *[[f"wordnet_other_than_synset:{synset}", "true"] for synset in sorted(EXCLUSIONS)],
                ],
                "absent_evidence": [],
                "warrant": {
                    "kind": "DEFINITIONAL_DERIVATION",
                    "warrant_id": "native-measurement-unit-quantity-refined",
                    "review_id": "native-measurement-unit-quantity-scope-review",
                    "reviewer": reviewer,
                    "source_refs": [scope_ref, str(SCOPE.relative_to(ROOT))],
                    "statement": STATEMENT,
                },
            }
        ],
    )
    print({"phase": "EXACT_AUDIT_EXPORT", "seed": SEED, "held_out": audits}, flush=True)
    raw = export_reviewed_input(SOURCE, selection)["input"]
    [draft] = run_workflow_input(raw)["candidates"]
    captured = []
    for question in draft["audits"]:
        old = all_questions[question["entry_id"]]
        if any(question[k] != old[k] for k in ("request_id", "request", "schema")):
            raise ValueError("QUANTITY_HELD_OUT_QUESTION_CHANGED:" + question["entry_id"])
        answer = read(FOLDER / "unit-banks-gemma4-answers" / (old["request_id"] + ".json"))
        if answer["request_id"] != old["request_id"]:
            raise ValueError("QUANTITY_HELD_OUT_ANSWER_CHANGED")
        captured.append({**old, **answer})
    replay = _AuditReplay(captured)
    audited = run_workflow_input(raw, replay, max_calls=len(captured))
    if replay.index != len(captured):
        raise ValueError("QUANTITY_HELD_OUT_REPLAY_INCOMPLETE")
    [candidate] = audited["candidates"]
    review = {
        "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "native-measurement-unit-quantity-admission",
        "reviewer": reviewer,
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "source_refs": [scope_ref, "unit-quantity-refined-audit.json"],
        "rationale": STATEMENT,
    }
    admission = admit_records(raw, audited, review)
    files = {name: f"unit-quantity-refined-{name}.json" for name in ("input", "audit", "review")}
    for name, record in zip(files.values(), (raw, audited, review), strict=True):
        write(FOLDER / name, record)
    write(
        FOLDER / "unit-quantity-revision-plan.json",
        {
            "format": "GSE.rule-revision-plan/1",
            "baseline_version": admission["baseline_version"],
            "admissions": [files],
            "retirements": [],
            "exceptions": [],
        },
    )
    print(
        {
            "code": admission["code"],
            "audit": candidate["audit_outcomes"],
            "expected_new_quantity_positive": len(expected_delta),
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
