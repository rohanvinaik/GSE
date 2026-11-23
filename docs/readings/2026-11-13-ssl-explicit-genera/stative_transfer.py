"""Audit qualified stative conditions across native sources from release 018."""

import argparse
import json
from collections import Counter
from contextlib import closing
from dataclasses import replace
from importlib import import_module
from math import log2
from pathlib import Path

from gse.curation.lexicon_builder.completion import _priority_source
from gse.curation.lexicon_builder.epoch import (
    JournaledTransport,
    admit_and_migrate,
    census,
    choose,
    connect,
    exact_delta,
    fingerprint,
    forecast,
    parse_plan,
    read,
    record,
    run_arm,
    scope_rows,
)
from gse.curation.lexicon_builder.foundation import EXCEPTION_GUARD_PREFIX, lexical_context
from gse.curation.lexicon_builder.reviewed_export import export_reviewed_input
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from gse.curation.lexicon_builder.rule_admission import _AuditReplay, admit_records
from gse.curation.lexicon_builder.rule_history import digest
from gse.curation.lexicon_builder.rule_migration import migrate_revision
from gse.curation.lexicon_builder.rule_reservations import reservation_source
from gse.curation.lexicon_builder.rule_revisions import RESERVATION_FORMAT
from gse.curation.lexicon_builder.validation import validate_build
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports, load_benchmark
from scripts.run_lexicon_epochs import publish_round

previous = import_module("docs.readings.2026-11-13-ssl-explicit-genera.stative")
NOTES = Path(__file__).resolve().parent
BASE = previous.BASE.with_name("sparse-release-018.db")
WORK = BASE.parent / "ssl-explicit-genera" / "stative-019"
PREVIEW = NOTES / "019-stative-being-preview.json"
HOLDOUTS = (
    "wordnet:inconceivability:inconceivability.n.01",
    "wordnet:unattainableness:unattainableness.n.01",
    "wiktionary:en-unreality-en-noun-kI5sOzXu:6baad8e4ab794c0eba496fc9a1f04fdd3dc6152f8e5c3d4d1e473ce0e67d95be",
    "wiktionary:en-annihilation-en-noun-N-HM9F9z:6467b1b20733fc3a44f3fea82ccb253e336244ca369f7650b163521360b748c0",
    "wiktionary:en-living-en-noun-PndBZpbk:86e92b89618e6fc3db9c3182c9622b3650ec8352a73cccdb84418082956a9811",
)
GOLD = (
    "wiktionary:en-employment-en-noun-vk5buKuT:3c7c192a5279a2a6e902747abf2d131e437c14de431e68897744a8d0fd39de00",
    "wiktionary:en-freedom-en-noun-S4DkRkex:36d004c6d4afe100472ab160a148f865700a2c4d93d4ac7ad13ce2463a9da5d5",
    "wiktionary:en-plurality-en-noun-GtIBIkRo:54c3b61905e19ed9ca138a59927d9a8bb5a1ce53f4c3a65b33fecd2d864819ad",
    "wordnet:senility:senility.n.02",
)
RESERVED = (
    "wordnet:nonbeing:nonbeing.n.01",
    "wordnet:nonexistence:nonexistence.n.01",
    "wordnet:life:life.n.03",
)


def family_record():
    preview = read(PREVIEW)
    boredom = [
        row["entry_id"] for row in preview["definitions"]
        if row["lemma"] == "boredom" and row["gloss"].casefold() == "the state of being bored."
        and row["entry_id"].startswith("wiktionary:")
    ]
    if len(boredom) != 1:
        raise ValueError("STATIVE_TRANSFER_AUDIT_IDENTITY_AMBIGUOUS")
    return {
        "id": "native-stative-being",
        "antecedent": None,
        "consequent": ["BE", 1],
        "guards": [["pos", "noun"], ["native_noun_frame:stative_being", "true"]],
        "holdouts": [*HOLDOUTS, *boredom],
        "warrant": {
            "warrant_id": "native-qualified-stative-being",
            "review_id": "native-qualified-stative-being-source-review",
            "kind": "DEFINITIONAL_DERIVATION",
            "reviewer": "Source-backed construction review",
            "statement": "The exact native noun definition denotes a state of being in an explicitly stated "
            "condition. Its own stative predication supports BE=+1 under the approved GSE convention. The "
            "condition can concern a quality, relation, capacity, biological status, or a passive result. "
            "This assigns no truth of existence and no value to another bank. A lexical predicate must "
            "follow being; alternate genera, multiple glosses, bare existence and political-state genera "
            "are outside this construction. Source identity and the complete gloss must establish the guard.",
            "source_refs": [
                str(NOTES / "SOURCE_SCOPE.md"),
                str(NOTES.parent.parent / "program/LEXICON_CONSTRUCTION_DESIGN.md") + "#be-stative-content-scope",
            ],
        },
    }


def freeze():
    parent = read(NOTES / "sparse-release-018-activation.json")
    if (
        resolve_lexicon_path() != BASE or fingerprint(BASE) != parent["sha256"]
        or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]
    ):
        raise ValueError("STATIVE_TRANSFER_BASELINE_CHANGED")
    return parent


def prepare():
    parent = freeze()
    WORK.mkdir(exist_ok=True)
    family = family_record()
    evaluated = []
    for path in (
        previous.anatomy.previous.prior.SOURCE_CASES,
        previous.anatomy.previous.prior.CONTRAST_CASES,
        NOTES / "018-stative-diagnostic-cases.json",
    ):
        evaluated.extend(load_benchmark(path))
    plan = {
        "format": "gse.lexicon-epoch-plan/1", "baseline_sha256": parent["sha256"],
        "active_pointer_sha256": parent["pointer_sha256"], "epochs": 1,
        "audits_per_epoch": len(family["holdouts"]), "families": [family],
        "evaluation_holdout": {
            "lemmas": sorted({case["lemma"] for case in evaluated}),
            "entries": sorted({*GOLD, *(case["sense"] for case in evaluated if case["sense"] is not None)}),
        },
    }
    families = parse_plan(plan)
    inventory = census(BASE, families)
    everyone = {row["entry_id"]: row for rows in inventory.values() for row in rows}
    if not set(GOLD) <= everyone.keys():
        raise ValueError("STATIVE_TRANSFER_GOLD_OUTSIDE_SCOPE")
    plan["evaluation_holdout"]["lemmas"] = sorted(
        set(plan["evaluation_holdout"]["lemmas"]) | {everyone[entry]["lemma"] for entry in GOLD}
    )
    rules, rows = scope_rows(BASE, everyone.values())
    staged = forecast(rows, rules, tuple(f.relation() for f in families.values()))
    if staged["contradictions"] or any(
        r["bank"] != "BE" or r["before"] != [-1, 0, 1] or r["after"] != [1] for r in staged["changes"]
    ):
        raise ValueError("STATIVE_TRANSFER_UNSAFE_STAGE")
    expected = read(PREVIEW)["changes"]
    def order(row):
        return row["entry_id"], row["bank"]
    if sorted(staged["changes"], key=order) != sorted(expected, key=order):
        raise ValueError("STATIVE_TRANSFER_SCOPE_CHANGED_SINCE_REVIEW")
    priority, frequencies = _priority_source("zipf", None)
    selected = choose(BASE, inventory, families, set(), set(), "zipf", frequencies, plan["evaluation_holdout"])
    if selected is None:
        raise ValueError("STATIVE_TRANSFER_NO_TEACHING_QUESTION")
    record(WORK / "plan.json", plan)
    record(WORK / "inventory.json", inventory)
    record(NOTES / "019-population-stage.json", {
        **staged, "inventory": inventory, "selected": selected, "frequency_source": priority,
        "baseline_sha256": parent["sha256"], "active_pointer_sha256": parent["pointer_sha256"],
    })
    print("STATIVE_TRANSFER_PREPARED", len(staged["changes"]), selected["entry_id"], selected["subtlex"], flush=True)


def run():
    freeze()
    result = run_arm(
        read(WORK / "plan.json"), BASE, ACTIVE_POINTER, WORK / "zipf", read(WORK / "inventory.json"),
        "zipf", previous.anatomy.previous.prior.previous.model(), WORK / "model.lock",
    )
    if len(result["epochs"]) != 1 or result["epochs"][0]["code"] != "RULE_ADMITTED":
        record(NOTES / "019-rule-withheld.json", result)
        raise ValueError("STATIVE_TRANSFER_RULE_WITHHELD")
    verify_result(result)


def seed():
    """Continue from prior symbolic proofs; retain the unsuccessful teaching arm."""
    freeze()
    plan = read(WORK / "plan.json")
    [family] = parse_plan(plan).values()
    prior_attempt = read(NOTES / "019-rule-withheld.json")
    teaching_path = WORK / "zipf/epoch-01/teaching.json"
    teaching = read(teaching_path)
    if (
        prior_attempt["candidate"] != str(BASE) or prior_attempt["changes"]
        or prior_attempt["typed_questions_used"] != 1
        or teaching["code"] != "TEACHING_ABSTAINED" or teaching["answer"] != {"BE": None}
    ):
        raise ValueError("STATIVE_TRANSFER_PRIOR_ATTEMPT_CHANGED")
    inventory = read(WORK / "inventory.json")[family.id]
    rules, rows = scope_rows(BASE, inventory)
    excluded = set(plan["evaluation_holdout"]["entries"]) | set(family.holdouts)
    excluded_lemmas = set(plan["evaluation_holdout"]["lemmas"])
    _, frequencies = _priority_source("zipf", None)
    eligible = [
        item for item in inventory
        if rows[item["entry_id"]][-1]["BE"] == [1] and item["entry_id"] not in excluded
        and item["lemma"].casefold() not in excluded_lemmas
    ]
    seeds, groups = [], set()
    for item in sorted(eligible, key=lambda item: (-frequencies.get(item["lemma"].casefold(), 0), item["entry_id"])):
        if item["sense_group"] not in groups:
            seeds.append(item["entry_id"])
            groups.add(item["sense_group"])
        if len(seeds) == 5:
            break
    if len(seeds) != 5:
        raise ValueError("STATIVE_TRANSFER_INSUFFICIENT_JUSTIFIED_SEEDS")
    phase = WORK / "seeded"
    phase.mkdir(exist_ok=True)
    transport = previous.anatomy.previous.prior.previous.model()
    manifest = {
        "format": "gse.seeded-rule-round/1", "baseline_sha256": fingerprint(BASE),
        "active_pointer_sha256": fingerprint(ACTIVE_POINTER), "original_plan_sha256": digest(plan),
        "discovery_entry_ids": seeds, "audit_entry_ids": list(family.holdouts),
        "prior_teaching": teaching, "prior_teaching_sha256": fingerprint(teaching_path),
        "typed_question_budget": 7, "new_audit_budget": 6, "transport": transport.identity,
    }
    record(phase / "plan.json", manifest)
    selection = {
        "format": "gse.reviewed-pattern-selection/1", "discovery_entry_ids": seeds,
        "audit_entry_ids": list(family.holdouts), "reviews": [], "guarded_candidates": [family.proposal()],
    }
    exported = export_reviewed_input(BASE, selection)
    raw = exported["input"]
    record(phase / "selection.json", selection)
    record(phase / "reviewed-input.json", raw)
    staged = forecast(rows, rules, (family.relation(),))
    record(phase / "staged.json", staged)
    def order(row):
        return row["entry_id"], row["bank"]
    if staged["contradictions"] or sorted(staged["changes"], key=order) != sorted(read(PREVIEW)["changes"], key=order):
        raise ValueError("STATIVE_TRANSFER_SEEDED_SCOPE_CHANGED")
    auditing = JournaledTransport(transport, phase, "audit", 6, WORK / "model.lock")
    audit_path = phase / "audit.json"
    audited = read(audit_path) if audit_path.exists() else run_workflow_input(raw, auditing, max_calls=6)
    record(audit_path, audited)
    [candidate] = audited["candidates"]
    if (
        candidate["discovery_outcomes"] != {"OBSERVED_AGREEMENT": 5}
        or any(row.get("consequent_witness", {}).get("value") != 1 or row["rulings"] for row in candidate["discovery"])
        or candidate["audit_outcomes"] != {"MODEL_AGREEMENT": 6}
        or any(row["code"] != "STAGED_ONLY" for row in candidate["staging"])
    ):
        record(NOTES / "019-seeded-rule-withheld.json", audited)
        raise ValueError("STATIVE_TRANSFER_SEEDED_AUDIT_WITHHELD")
    print("STATIVE_TRANSFER_SEEDED_AUDITS_PASSED", len(seeds), auditing.count(), flush=True)
    output = phase / "candidate.db"
    migration = admit_and_migrate(BASE, output, phase, raw, audited, family, staged)
    if fingerprint(teaching_path) != manifest["prior_teaching_sha256"]:
        raise ValueError("STATIVE_TRANSFER_ABSTENTION_CHANGED")
    result = {
        "format": "gse.lexicon-seeded-round/1", "policy": "zipf-grounded-seeds",
        "candidate": str(output), "candidate_sha256": fingerprint(output),
        "plan_sha256": digest(manifest), "active_pointer_sha256": manifest["active_pointer_sha256"],
        "definitions_compared": migration["definitions_replayed"], "changes": staged["changes"],
        "new_cells": migration["symbolic_new_cells"], "reopened_cells": 0,
        "typed_question_budget": 7, "typed_questions_used": 1 + auditing.count(),
        "discovery_seed_count": len(seeds), "prior_teaching": teaching,
        "admitted": [{"family": family.id, "rule_id": migration["rule_id"]}],
        "replay": migration["replay"], "activation_performed": False,
    }
    record(phase / "result.json", result)
    verify_result(result)


def refine_prepare():
    """Reserve unresolved parent audits and freeze fresh cross-source holdouts."""
    freeze()
    plan = read(WORK / "plan.json")
    [parent_family] = parse_plan(plan).values()
    parent = read(WORK / "seeded/audit.json")
    [tested] = parent["candidates"]
    if set(tested["audit_outcomes"]) != {"MODEL_AGREEMENT", "MODEL_ABSTAINED"}:
        raise ValueError("STATIVE_TRANSFER_PARENT_NEEDS_SEMANTIC_REVIEW")
    reserved = sorted(row["entry_id"] for row in tested["audits"] if row["code"] == "MODEL_ABSTAINED")
    seed_plan = read(WORK / "seeded/plan.json")
    inventory = read(WORK / "inventory.json")[parent_family.id]
    rules, rows = scope_rows(BASE, inventory)
    excluded = set(seed_plan["discovery_entry_ids"] + seed_plan["audit_entry_ids"] + plan["evaluation_holdout"]["entries"])
    care = read(WORK / "zipf/epoch-01/selection.json")["entry_id"]
    excluded.add(care)
    excluded_groups = {item["sense_group"] for item in inventory if item["entry_id"] in excluded}
    excluded_lemmas = set(plan["evaluation_holdout"]["lemmas"]) | {
        item["lemma"].casefold() for item in inventory if item["entry_id"] in excluded
    }
    _, frequencies = _priority_source("zipf", None)
    holdouts = []
    for source in ("wordnet", "wiktionary"):
        eligible = [
            item for item in inventory if item["entry_id"].startswith(source + ":")
            and rows[item["entry_id"]][-1]["BE"] == [-1, 0, 1]
            and item["sense_group"] not in excluded_groups and item["lemma"].casefold() not in excluded_lemmas
        ]
        if not eligible:
            raise ValueError("STATIVE_TRANSFER_NO_FRESH_SOURCE_AUDIT:" + source)
        chosen = min(eligible, key=lambda item: (-frequencies.get(item["lemma"].casefold(), 0), item["entry_id"]))
        holdouts.append(chosen["entry_id"])
    family = replace(parent_family, holdouts=tuple(holdouts), warrant={
        **parent_family.warrant,
        "warrant_id": parent_family.warrant["warrant_id"] + ":reserved-audits",
        "review_id": "qualified-stative-unresolved-audit-reservations",
        "required_reservation_ids": reserved,
        "statement": parent_family.warrant["statement"] + " Exact definitions with unresolved parent audits "
        "are withheld through explicit reservations. Those null rulings establish no contrary sign and no "
        "general exception condition. The residual cases remain open for further learning.",
    })
    staging_rule = replace(family.relation(), guards=tuple(sorted((
        *family.guards, *((EXCEPTION_GUARD_PREFIX + entry, "true") for entry in reserved),
    ))))
    staged = forecast(rows, rules, (staging_rule,))
    if staged["contradictions"] or any(
        r["bank"] != "BE" or r["before"] != [-1, 0, 1] or r["after"] != [1] for r in staged["changes"]
    ):
        raise ValueError("STATIVE_TRANSFER_REFINED_STAGE_UNSAFE")
    selection = {
        "format": "gse.reviewed-pattern-selection/1", "discovery_entry_ids": seed_plan["discovery_entry_ids"],
        "audit_entry_ids": holdouts, "reviews": [], "guarded_candidates": [family.proposal()],
    }
    raw = export_reviewed_input(BASE, selection)["input"]
    phase = WORK / "refined"
    phase.mkdir(exist_ok=True)
    record(phase / "selection.json", selection)
    record(phase / "reviewed-input.json", raw)
    record(phase / "plan.json", {
        "format": "gse.seeded-rule-refinement/1", "baseline_sha256": fingerprint(BASE),
        "active_pointer_sha256": fingerprint(ACTIVE_POINTER), "parent_audit_sha256": digest(parent),
        "prior_teaching_sha256": seed_plan["prior_teaching_sha256"],
        "reserved_entry_ids": reserved, "audit_entry_ids": holdouts, "new_audit_budget": 2,
        "prior_questions": 1 + parent["model_calls"], "typed_question_budget": 3 + parent["model_calls"],
    })
    record(phase / "staged.json", staged)
    record(NOTES / "019-refined-stage.json", {
        **staged, "reserved_entry_ids": reserved, "audit_definitions": [
            {"entry_id": entry, "definition": rows[entry][0].definition, "lemma": rows[entry][0].lemma}
            for entry in holdouts
        ], "parent_audit_outcomes": tested["audit_outcomes"], "independent_audit_budget": 2,
    })
    print("STATIVE_TRANSFER_REFINEMENT_PREPARED", len(staged["changes"]), reserved, holdouts, flush=True)


def refine():
    freeze()
    phase = WORK / "refined"
    plan, raw = read(phase / "plan.json"), read(phase / "reviewed-input.json")
    parent = read(WORK / "seeded/audit.json")
    if digest(parent) != plan["parent_audit_sha256"]:
        raise ValueError("STATIVE_TRANSFER_PARENT_AUDIT_CHANGED")
    transport = previous.anatomy.previous.prior.previous.model()
    auditing = JournaledTransport(transport, phase, "audit", 2, WORK / "model.lock")
    audit_path = phase / "audit.json"
    audited = read(audit_path) if audit_path.exists() else run_workflow_input(raw, auditing, max_calls=2)
    record(audit_path, audited)
    [candidate] = audited["candidates"]
    if candidate["audit_outcomes"] != {"MODEL_AGREEMENT": 2}:
        record(NOTES / "019-refined-rule-withheld.json", audited)
        raise ValueError("STATIVE_TRANSFER_REFINED_AUDIT_WITHHELD")
    warrant = candidate["warrant"]
    admission = admit_records(raw, audited, {
        "rule_id": candidate["relation"]["rule_id"], "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "qualified-stative-refined-admission", "reviewer": warrant["reviewer"],
        "decision": "APPROVE_DEFINITIONAL_RULE", "source_refs": warrant["source_refs"], "rationale": warrant["statement"],
    })
    reservations = []
    with closing(connect(BASE)) as conn:
        for audit_row in parent["candidates"][0]["audits"]:
            if audit_row["code"] != "MODEL_ABSTAINED":
                continue
            reservations.append({
                "rule_id": admission["relation"]["rule_id"], "entry_id": audit_row["entry_id"], "bank": "BE",
                "source_sha256": digest(reservation_source(conn, audit_row["entry_id"])), "audit": audit_row,
                "review_id": "reserved-audit:" + audit_row["request_id"], "reviewer": warrant["reviewer"],
                "source_refs": warrant["source_refs"], "rationale": "The parent audit abstained. Preserve its "
                "open domain while withholding this exact identity from the population prior; assign no sign.",
            })
    revision = {
        "format": RESERVATION_FORMAT, "baseline_version": admission["baseline_version"],
        "admissions": [admission], "retirements": [], "exceptions": [], "reservations": reservations,
    }
    record(phase / "revision.json", revision)
    print("STATIVE_TRANSFER_REFINED_AUDITS_PASSED", auditing.count(), "STARTING_FULL_REPLAY", flush=True)
    output, migration_path = phase / "candidate.db", phase / "migration.json"
    if not output.exists():
        record(migration_path, migrate_revision(BASE, output, revision))
    elif not migration_path.exists():
        # The migration installs the output atomically before its report is
        # recorded. Revalidate that installed snapshot after an interruption.
        recovered = validate_build(output)
        with closing(connect(output)) as conn:
            [payload] = conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()
        import json

        expected = {
            **admission["relation"], "guards": sorted([
                *admission["relation"]["guards"],
                *([EXCEPTION_GUARD_PREFIX + review["entry_id"], "true"] for review in reservations),
            ]),
        }
        if digest(expected) not in {digest(rule) for rule in json.loads(payload)}:
            raise ValueError("STATIVE_TRANSFER_RECOVERED_RULE_MISSING")
        record(migration_path, {"code": "RECOVERED_ATOMIC_MIGRATION", "postflight": recovered})
    migration = read(migration_path)
    if migration["postflight"]["code"] != "REPLAY_VALIDATED" or not migration["postflight"]["complete_search"]:
        raise ValueError("STATIVE_TRANSFER_REFINED_REPLAY_FAILED")
    definitions, changes = exact_delta(BASE, output)
    def by_cell(rows):
        return {(row["entry_id"], row["bank"]): row for row in rows}
    if by_cell(changes) != by_cell(read(phase / "staged.json")["changes"]):
        raise ValueError("STATIVE_TRANSFER_REFINED_DELTA_DIFFERS_FROM_STAGE")
    teaching_path = WORK / "zipf/epoch-01/teaching.json"
    if fingerprint(teaching_path) != plan["prior_teaching_sha256"]:
        raise ValueError("STATIVE_TRANSFER_ABSTENTION_CHANGED")
    result = {
        "format": "gse.lexicon-seeded-round/1", "policy": "zipf-grounded-seeds-with-reservations",
        "candidate": str(output), "candidate_sha256": fingerprint(output), "plan_sha256": digest(plan),
        "active_pointer_sha256": plan["active_pointer_sha256"], "definitions_compared": definitions,
        "changes": changes, "new_cells": len(changes), "reopened_cells": 0, "discovery_seed_count": 5,
        "typed_question_budget": plan["typed_question_budget"],
        "typed_questions_used": plan["prior_questions"] + auditing.count(),
        "prior_teaching": read(teaching_path), "reserved_entry_ids": plan["reserved_entry_ids"],
        "admitted": [{"family": "native-stative-being", "rule_id": admission["relation"]["rule_id"]}],
        "replay": migration["postflight"], "activation_performed": False,
    }
    record(phase / "result.json", result)
    verify_result(result)


def calibrate():
    """Blindly audit established seeds with their old BE law withheld; write no cells."""
    freeze()
    prior = read(WORK / "seeded/reviewed-input.json")
    proof = read(WORK / "seeded/audit.json")["candidates"][0]["discovery"]
    removed = sorted({
        step["rule_id"] for row in proof for step in row["consequent_witness"]["proof_trace"]
        if step.get("bank") == "BE" and step["kind"] == "RELATION"
    })
    if len(removed) != 1:
        raise ValueError("STATIVE_CALIBRATION_UNEXPECTED_PROOF_ROOTS")
    from gse.curation.lexicon_builder.validation import _relations

    relations = [rule for rule in prior["relations"] if rule["rule_id"] not in removed]
    seeds = prior["discovery_entry_ids"]
    entries = [row for row in prior["entries"] if row["definition"]["entry_id"] in seeds]
    for entry in entries:
        entry["context"] = lexical_context(entry["definition"], entry["observations"], _relations(relations))
    raw = {
        "format": prior["format"], "relations": relations, "rulings": [], "entries": entries,
        "discovery_entry_ids": [], "audit_entry_ids": seeds, "guarded_candidates": prior["guarded_candidates"],
    }
    checked = run_workflow_input(raw)
    if checked["candidates"][0]["audit_outcomes"] != {"AUDIT_CALL_BUDGET_EXHAUSTED": 5}:
        raise ValueError("STATIVE_CALIBRATION_TARGETS_NOT_OPEN")
    phase = WORK / "calibration"
    phase.mkdir(exist_ok=True)
    transport = previous.anatomy.previous.prior.previous.model()
    record(phase / "plan.json", {
        "format": "gse.bank-auditor-calibration/1", "seed_entry_ids": seeds,
        "withheld_rule_ids": removed, "baseline_sha256": fingerprint(BASE),
        "questions": 5, "transport": transport.identity, "lexicon_writes": False,
        "authority": "COMPARISON_WITH_RELEASE_018_ADMITTED_RULE_NOT_INDEPENDENT_SEMANTIC_GOLD",
    })
    record(phase / "input.json", raw)
    journal = JournaledTransport(transport, phase, "calibration", 5, WORK / "model.lock")
    report = run_workflow_input(raw, journal, max_calls=5)
    record(phase / "report.json", report)
    record(NOTES / "019-auditor-calibration.json", report)
    print("STATIVE_AUDITOR_CALIBRATION", report["candidates"][0]["audit_outcomes"], journal.count(), flush=True)


def convention():
    """Apply the founder's new sufficient condition, retaining all old audits."""
    freeze()
    phase = WORK / "convention"
    phase.mkdir(exist_ok=True)
    approval = read(NOTES / "019-approved-be-convention.json")
    parent = read(WORK / "seeded/plan.json")
    family = family_record()
    family["warrant"].update(
        kind="APPROVED_GSE_CONVENTION", warrant_id=approval["convention_id"],
        review_id="founder-own-state-denotation-be",
        statement="Rohan approved: own noun-state denotation is sufficient for BE=+1, including relational "
        "and resultative conditions. An exact complete native noun definition headed by a/the state of "
        "being and a lexical condition witnesses that sufficient condition. A grammatical copula alone "
        "does not. This scoped projection assigns no other bank or zero, and makes no ontological "
        "existence claim. Original null and dissenting model replies remain diagnostic history.",
    )
    family["warrant"]["source_refs"].append(str(NOTES / "019-approved-be-convention.json"))
    records = [
        a for path in (WORK / "seeded/audit.json", WORK / "refined/audit.json")
        for a in read(path)["candidates"][0]["audits"]
    ]
    audit_ids = [a["entry_id"] for a in records]
    if len(set(audit_ids)) != 8:
        raise ValueError("STATIVE_CONVENTION_DIAGNOSTIC_IDENTITIES_CHANGED")
    family["holdouts"] = audit_ids
    selection = {
        "format": "gse.reviewed-pattern-selection/1", "discovery_entry_ids": parent["discovery_entry_ids"],
        "audit_entry_ids": audit_ids, "reviews": [],
        "guarded_candidates": [{
            "antecedent": None, "consequent": family["consequent"], "guards": family["guards"],
            "absent_evidence": [], "warrant": family["warrant"],
        }],
    }
    raw = export_reviewed_input(BASE, selection)["input"]
    by_entry = {a["entry_id"]: a for a in records}
    replay_transport = _AuditReplay([by_entry[entry] for entry in raw["audit_entry_ids"]])
    audited = run_workflow_input(raw, replay_transport, max_calls=8)
    if replay_transport.index != 8 or audited["candidates"][0]["audit_outcomes"] != {
        "MODEL_AGREEMENT": 4, "MODEL_ABSTAINED": 3, "MODEL_COUNTEREXAMPLE": 1,
    }:
        raise ValueError("STATIVE_CONVENTION_DIAGNOSTIC_REPLAY_CHANGED")
    [candidate] = audited["candidates"]
    review = {
        "rule_id": candidate["relation"]["rule_id"], "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "founder-stative-convention-admission", "reviewer": "Rohan (representation); Codex (source scope)",
        "decision": "APPROVE_REPRESENTATIONAL_CONVENTION", "convention": approval,
        "source_refs": family["warrant"]["source_refs"], "rationale": family["warrant"]["statement"],
    }
    admission = admit_records(raw, audited, review)
    from gse.curation.lexicon_builder.validation import _relations

    inventory = read(WORK / "inventory.json")[family["id"]]
    rules, rows = scope_rows(BASE, inventory)
    [new_rule] = _relations(json.loads(json.dumps([admission["relation"]])))
    staged = forecast(rows, rules, (new_rule,))
    def by_cell(changes):
        return {(row["entry_id"], row["bank"]): row for row in changes}
    if staged["contradictions"] or by_cell(staged["changes"]) != by_cell(read(PREVIEW)["changes"]):
        raise ValueError("STATIVE_CONVENTION_SCOPE_CHANGED")
    revision = {
        "format": "gse.rule-revision/1", "baseline_version": admission["baseline_version"],
        "admissions": [admission], "retirements": [], "exceptions": [],
    }
    for name, payload in (
        ("selection", selection), ("reviewed-input", raw), ("audit", audited), ("review", review),
        ("admission", admission), ("staged", staged), ("revision", revision),
    ):
        record(phase / (name + ".json"), payload)
    record(NOTES / "019-convention-stage.json", {
        **staged, "semantic_authority": admission["semantic_authority"], "convention": approval,
        "diagnostic_outcomes": candidate["audit_outcomes"], "new_model_questions": 0,
    })
    print("STATIVE_CONVENTION_STAGED", len(staged["changes"]), "STARTING_FULL_REPLAY", flush=True)
    output, migration_path = phase / "candidate.db", phase / "migration.json"
    if not output.exists():
        record(migration_path, migrate_revision(BASE, output, revision))
    elif not migration_path.exists():
        record(migration_path, {"code": "RECOVERED_ATOMIC_MIGRATION", "postflight": validate_build(output)})
    migration = read(migration_path)
    if migration["postflight"]["code"] != "REPLAY_VALIDATED" or not migration["postflight"]["complete_search"]:
        raise ValueError("STATIVE_CONVENTION_REPLAY_FAILED")
    definitions, changes = exact_delta(BASE, output)
    if by_cell(changes) != by_cell(staged["changes"]):
        raise ValueError("STATIVE_CONVENTION_DELTA_DIFFERS_FROM_STAGE")
    care = read(WORK / "zipf/epoch-01/selection.json")["entry_id"]
    controls = [care, *read(WORK / "refined/plan.json")["reserved_entry_ids"], *[
        a["entry_id"] for a in records if a["code"] == "MODEL_COUNTEREXAMPLE"
    ]]
    if fingerprint(WORK / "zipf/epoch-01/teaching.json") != parent["prior_teaching_sha256"]:
        raise ValueError("STATIVE_CONVENTION_ORIGINAL_ABSTENTION_CHANGED")
    result = {
        "format": "gse.lexicon-convention-round/1", "policy": "founder-approved-scoped-convention",
        "candidate": str(output), "candidate_sha256": fingerprint(output), "plan_sha256": digest(revision),
        "active_pointer_sha256": parent["active_pointer_sha256"], "definitions_compared": definitions,
        "changes": changes, "new_cells": len(changes), "reopened_cells": 0,
        "typed_question_budget": 9, "typed_questions_used": 9,
        "calibration_questions_used": 5, "new_model_questions": 0, "convention_controls": sorted(controls),
        "admitted": [{"family": family["id"], "rule_id": new_rule.rule_id}],
        "replay": migration["postflight"], "activation_performed": False,
        "semantic_authority": admission["semantic_authority"],
    }
    record(phase / "result.json", result)
    verify_result(result)


def verify_result(result):
    if result["reopened_cells"] or any(
        r["bank"] != "BE" or r["before"] != [-1, 0, 1] or r["after"] != [1] for r in result["changes"]
    ):
        raise ValueError("STATIVE_TRANSFER_UNEXPECTED_DOMAIN_CHANGE")
    state_corpus = import_module("docs.readings.2026-11-13-ssl-explicit-genera.state_corpus")
    corpus = state_corpus.audit(Path(result["candidate"]))
    record(NOTES / "019-candidate-state-corpus.json", corpus)
    if corpus["code"] != "STATE_CORPUS_GROUNDING_VALIDATED":
        raise ValueError("STATIVE_TRANSFER_GROUNDING_CORPUS_REVIEW_REQUIRED")
    comparisons = {}
    for name, path, baseline in (
        ("sentences", previous.anatomy.previous.prior.SOURCE_CASES, NOTES / "019-grounding-sentences.json"),
        ("contrasts", previous.anatomy.previous.prior.CONTRAST_CASES, NOTES / "019-grounding-contrasts.json"),
        ("states", NOTES / "018-stative-diagnostic-cases.json", NOTES / "019-state-grounding-diagnostic.json"),
    ):
        report = audit(Path(result["candidate"]), path)
        comparison = compare_reports(read(baseline), report)
        record(NOTES / ("019-candidate-" + name + ".json"), {**report, "comparison": comparison})
        if comparison["failures"]:
            raise ValueError("STATIVE_TRANSFER_RUNTIME_REGRESSION:" + name)
        comparisons[name] = comparison
    record(NOTES / "019-verification.json", {
        "code": "VALIDATED_CROSS_SOURCE_STATIVE_EPOCH", "result": result, "comparisons": comparisons,
        "bits_removed": sum(log2(len(r["before"]) / len(r["after"])) for r in result["changes"]),
        "changes_by_source": dict(Counter(r["entry_id"].split(":", 1)[0] for r in result["changes"])),
    })
    print("STATIVE_TRANSFER_VALIDATED", result["new_cells"], result["typed_questions_used"], flush=True)


def publish():
    parent = freeze()
    verified = read(NOTES / "019-verification.json")
    if verified["code"] != "VALIDATED_CROSS_SOURCE_STATIVE_EPOCH":
        raise ValueError("STATIVE_TRANSFER_VERIFICATION_REQUIRED")
    corpus = read(NOTES / "019-candidate-state-corpus.json")
    if (
        corpus["code"] != "STATE_CORPUS_GROUNDING_VALIDATED"
        or corpus["lexicon_sha256"] != verified["result"]["candidate_sha256"]
    ):
        raise ValueError("STATIVE_TRANSFER_GROUNDING_CORPUS_NOT_VALIDATED")
    result = verified["result"]
    from gse.api.encoder import GSEEncoder

    with GSEEncoder(result["candidate"]) as encoder:
        for entry in (*GOLD, *result.get("convention_controls", ())):
            if encoder.lookup_definition(entry)["selected"]["domains"]["BE"] != [1]:
                raise ValueError("STATIVE_TRANSFER_GOLD_FAILED:" + entry)
            encoder.encode_definition(entry)
        for entry in (*RESERVED, *result.get("reserved_entry_ids", ())):
            if encoder.lookup_definition(entry)["selected"]["domains"]["BE"] != [-1, 0, 1]:
                raise ValueError("STATIVE_TRANSFER_RESERVED_CELL_CHANGED:" + entry)
    gold = read(NOTES / "sparse-release-018-gold.json")
    gold["records"].extend(
        {"entry_id": entry, "bank": "BE", "expected": 1} for entry in (*GOLD, *result.get("convention_controls", ()))
    )
    gold_path = NOTES / "sparse-release-019-gold.json"
    record(gold_path, gold)
    destination = BASE.with_name("sparse-release-019.db")
    publication = WORK / "publication"
    publication.mkdir(exist_ok=True)
    release = publish_round(result, publication, destination, gold_path)
    record(NOTES / "019-publication.json", release)
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        raise ValueError("STATIVE_TRANSFER_PUBLICATION_BLOCKED")
    if (
        resolve_lexicon_path() != destination or Path(release["previous_path"]) != BASE
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"]
        or release["cells"]["assigned"] != parent["cells"]["assigned"] + result["new_cells"]
    ):
        raise ValueError("STATIVE_TRANSFER_ACTIVE_RELEASE_MISMATCH")
    record(NOTES / "sparse-release-019-activation.json", {
        "code": "ACTIVE_CROSS_SOURCE_STATIVE_EPOCH_VERIFIED", "path": str(destination),
        "previous_path": str(BASE), "sha256": release["sha256"], "pointer_sha256": fingerprint(ACTIVE_POINTER),
        "cells": release["cells"], "replay": release["replay"],
        "semantic_outcomes": release["semantic_audit"]["outcomes"],
    })
    print("ACTIVE_CROSS_SOURCE_STATIVE_EPOCH_VERIFIED", release["cells"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run", "seed", "refine-prepare", "refine", "calibrate", "convention", "publish"))
    phase = parser.parse_args().phase
    {"prepare": prepare, "run": run, "seed": seed, "refine-prepare": refine_prepare, "refine": refine,
     "calibrate": calibrate, "convention": convention, "publish": publish}[phase]()
