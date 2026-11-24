"""Initialize, resume, and compare two budgeted lexicon learning arms."""

import argparse
import fcntl
import json
import math
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import (
    POLICIES,
    _domains,
    _resolve,
    fingerprint,
    mine_scope_chains,
    parse_plan,
    read,
    record,
    run_arm,
    scope_rows,
)
from GSE.curation.lexicon_builder.learning_curriculum import curriculum, plan_inventory
from GSE.curation.lexicon_builder.residual import OllamaTransport
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.specification import compare_measurements
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path


def rule_interactions(candidate, inventory, child, parents, bank):
    rules, rows = scope_rows(candidate, inventory)
    result = []
    for parent in parents:
        parent_id = parent["rule_id"]
        exclusions = {
            "both": set(),
            "parent_only": {child},
            "child_only": {parent_id},
            "neither": {parent_id, child},
        }
        singletons = {}
        for variant, dropped in exclusions.items():
            subset = tuple(rule for rule in rules if rule.rule_id not in dropped)
            resolved = set()
            for identity, row in rows.items():
                state = _resolve(row, subset)
                if state.code == "CONFLICT" or any(r["kind"] == "SOLVER_LIMIT" for r in state.trace):
                    raise ValueError("EPOCH_INTERACTION_INCOMPLETE")
                if variant == "both" and _domains(state) != row[-1]:
                    raise ValueError("EPOCH_INTERACTION_BASELINE_MISMATCH")
                if bank in state.assignments:
                    resolved.add(identity)
            singletons[variant] = resolved
        result.append(
            {
                "parent": parent_id,
                "bank": bank,
                "definitions_checked": len(rows),
                "singletons": {key: len(values) for key, values in singletons.items()},
                "joint_only": len(singletons["both"] - singletons["parent_only"] - singletons["child_only"]),
            }
        )
    return result


def conjunctive_results(directory, policy, arm, inventory):
    results = []
    for epoch in arm["epochs"]:
        selected = epoch.get("selected", {})
        if epoch["code"] != "RULE_ADMITTED" or "premises" not in selected:
            continue
        phase = directory / policy / f"epoch-{epoch['epoch']:02d}"
        observed = read(phase / "observed-conjunction.json")
        groundings = read(phase / "grounded-discovery.json")
        parent_ids = sorted(
            {
                rule_id
                for chain in groundings["chains"]
                if chain["consequent"] in selected["premises"]
                for rule_id in chain["rule_ids"]
            }
        )
        interactions = rule_interactions(
            Path(arm["candidate"]),
            inventory[selected["family"]],
            epoch["rule_id"],
            [{"rule_id": rule_id} for rule_id in parent_ids],
            selected["bank"],
        )
        results.append(
            {
                "epoch": epoch["epoch"],
                "rule_id": epoch["rule_id"],
                "family": selected["family"],
                "premises": selected["premises"],
                "consequent": observed["consequent"],
                "audit_outcomes": epoch["audit_outcomes"],
                "symbolic_new_cells": epoch["symbolic_new_cells"],
                "interactions": interactions,
            }
        )
    return results


def joint_learning(arms):
    """Compare actual phase measurements, including zero-singleton contraction."""
    summaries, baselines = {}, {}
    for policy, arm in arms.items():
        epochs = arm["epochs"]
        if not epochs or any("specification_learning" not in epoch for epoch in epochs):
            return {"code": "JOINT_PHASE_MEASUREMENTS_UNAVAILABLE", "policy": policy}
        phases = [epoch["specification_learning"] for epoch in epochs]
        baseline = phases[0]["baseline"]
        previous = baseline
        direct, revisions = [], []
        for phase in phases:
            before, taught, revised = (phase[name] for name in ("baseline", "post_teaching", "post_revision"))
            compare_measurements(previous, before)
            if any(previous[name] != before[name] for name in ("lexicon", "buckets", "sentence_constructions")):
                raise ValueError("EPOCH_JOINT_MEASUREMENT_CHAIN_BROKEN")
            direct.append(compare_measurements(before, taught))
            revisions.append(compare_measurements(taught, revised))
            previous = revised
        total = compare_measurements(baseline, previous)
        if any(change["lexicon"]["joint_count_comparison"] != "EXACT" for change in (*direct, *revisions, total)):
            return {"code": "JOINT_PHASE_COUNTS_UNAVAILABLE", "policy": policy}
        direct_bits = math.fsum(item["lexicon"]["specification_gain_bits"] for item in direct)
        revision_bits = math.fsum(item["lexicon"]["specification_gain_bits"] for item in revisions)
        if not math.isclose(
            direct_bits + revision_bits, total["lexicon"]["specification_gain_bits"], rel_tol=1e-12, abs_tol=1e-7
        ):
            raise ValueError("EPOCH_JOINT_MEASUREMENT_ACCOUNTING_MISMATCH")
        baselines[policy] = baseline
        summaries[policy] = {
            "baseline_specification_bits": baseline["lexicon"]["specification_bits"],
            "final_specification_bits": previous["lexicon"]["specification_bits"],
            "teaching_with_existing_closure_gain_bits": direct_bits,
            "rule_revision_gain_bits": revision_bits,
            "total": total,
        }
    left, right = (baselines[policy] for policy in POLICIES)
    compare_measurements(left, right)
    if any(left[name] != right[name] for name in ("lexicon", "buckets", "sentence_constructions")):
        raise ValueError("EPOCH_JOINT_BASELINES_DIFFER")
    return {
        "code": "EXACT_JOINT_COMPARISON",
        "arms": summaries,
        "closure_minus_zipf_specification_gain_bits": (
            summaries["closure"]["total"]["lexicon"]["specification_gain_bits"]
            - summaries["zipf"]["total"]["lexicon"]["specification_gain_bits"]
        ),
    }


def arm_inventory(arm, initial):
    """Resolve the exact discovered populations used by one learning arm."""
    result = dict(initial)
    for key, reference in arm.get("learned_inventory", {}).items():
        rows = read(Path(reference["path"]))
        if key in result or digest(rows) != reference["sha256"]:
            raise ValueError("EPOCH_LEARNED_INVENTORY_CHANGED")
        result[key] = rows
    return result


def compare(directory, plan):
    arms = {policy: read(directory / policy / "arm-result.json") for policy in POLICIES}
    configuration = {policy: read(directory / policy / "arm.json") for policy in POLICIES}
    if any(arm["plan_sha256"] != digest(plan) for arm in arms.values()):
        raise ValueError("EPOCH_COMPARISON_PLAN_CHANGED")
    shared_keys = ("plan_sha256", "inventory_sha256", "frequency_sha256", "transport")
    if curriculum(plan):
        shared_keys += ("learning_protocol",)
    if any(len({digest(config.get(key)) for config in configuration.values()}) != 1 for key in shared_keys):
        raise ValueError("EPOCH_COMPARISON_INPUTS_DIFFER")
    if any(
        arm["replay"]["code"] != "REPLAY_VALIDATED"
        or not arm["replay"]["complete_search"]
        or fingerprint(Path(arm["candidate"])) != arm["candidate_sha256"]
        for arm in arms.values()
    ):
        raise ValueError("EPOCH_COMPARISON_REPLAY_REQUIRED")
    budgets = {policy: arm["typed_questions_used"] for policy, arm in arms.items()}
    equal = len(set(budgets.values())) == 1 and all(
        arm["typed_questions_used"] == arm["typed_question_budget"] for arm in arms.values()
    )
    if curriculum(plan):
        equal = len(set(budgets.values())) == 1 and all(
            0 < arm["typed_questions_used"] <= arm["typed_question_budget"]
            and arm["code"] in {"LEARNING_DECLARED_FRONTIER_EXHAUSTED", "LEARNING_EPOCH_LIMIT_REACHED"}
            for arm in arms.values()
        )
    inventory = read(directory / "inventory.json")
    if digest(inventory) != configuration["closure"]["inventory_sha256"]:
        raise ValueError("EPOCH_COMPARISON_INVENTORY_CHANGED")
    inventories = {policy: arm_inventory(arm, inventory) for policy, arm in arms.items()}
    feedback = [
        {
            "epoch": epoch["epoch"],
            "rule_id": epoch["rule_id"],
            "family": epoch["selected"]["family"],
            "parents": epoch["premise_depends_on"],
            "audit_outcomes": epoch["audit_outcomes"],
            "interactions": rule_interactions(
                Path(arms["closure"]["candidate"]),
                inventories["closure"][epoch["selected"]["family"]],
                epoch["rule_id"],
                epoch["premise_depends_on"],
                epoch["selected"]["bank"],
            ),
        }
        for epoch in arms["closure"]["epochs"]
        if epoch["code"] == "RULE_ADMITTED" and epoch["premise_depends_on"]
    ]
    grounded_files = {policy: directory / policy / "grounded-chains-final.json" for policy in arms}
    conjunctive = {
        policy: conjunctive_results(directory, policy, arm, inventories[policy]) for policy, arm in arms.items()
    }
    grounded = {policy: len(read(path)["proposals"]) if path.exists() else 0 for policy, path in grounded_files.items()}
    joint = joint_learning(arms)
    if not equal or joint["code"] != "EXACT_JOINT_COMPARISON":
        code = "EPOCH_ACCEPTANCE_INCOMPLETE"
    elif not any(summary["total"]["lexicon"]["specification_gain_bits"] > 0 for summary in joint["arms"].values()):
        code = "EQUAL_BUDGET_NO_JOINT_CONTRACTION"
    elif any(row["joint_only"] for generation in feedback for row in generation["interactions"]):
        code = "EQUAL_BUDGET_FEEDBACK_VALIDATED"
    elif all(
        grounded[policy] and any(w["joint_only"] for case in conjunctive[policy] for w in case["interactions"])
        for policy in arms
    ):
        code = "EQUAL_BUDGET_GROUNDED_DISCOVERY_VALIDATED"
    else:
        code = "EQUAL_BUDGET_JOINT_CONTRACTION_VALIDATED"
    result = {
        "format": "GSE.lexicon-epoch-comparison/2",
        "code": code,
        "budget": budgets,
        "equal_budget": equal,
        "joint_learning": joint,
        "second_generation_rules": feedback,
        **(
            {"conjunctive_admissions": conjunctive, "grounded_chain_proposals": grounded}
            if any(path.exists() for path in grounded_files.values())
            else {}
        ),
        "arms": {
            policy: {
                "candidate": arm["candidate"],
                "new_cells": arm["new_cells"],
                "reopened_cells": arm["reopened_cells"],
                "epoch_families": [e.get("selected", {}).get("family") for e in arm["epochs"]],
                "direct_typed_assignments": sum(
                    e.get("teaching", {}).get("code")
                    in {"TYPED_TEACHING", "REVIEWED_TEACHING", "REVIEWED_TEACHING_COUNTEREXAMPLE"}
                    and not e.get("selected", {}).get("reviewed_teaching")
                    for e in arm["epochs"]
                ),
                "symbolic_new_cells": sum(e.get("symbolic_new_cells", 0) for e in arm["epochs"]),
                "marginal_domain_potential_removed_bits": sum(
                    math.log2(len(row["before"]) / len(row["after"]))
                    for row in arm["changes"]
                    if row["before"] and row["after"]
                ),
                "remaining_unknown": arm["publication"]["cells"]["unresolved"],
                "semantic_reviews": arm.get("semantic_reviews", 0),
            }
            for policy, arm in arms.items()
        },
        "closure_minus_zipf_new_cells": arms["closure"]["new_cells"] - arms["zipf"]["new_cells"],
        "activation_performed": False,
    }
    record(directory / "comparison-joint-v2.json", result)
    return result


def retire_published_work(directory, result, release):
    """Retire the working databases of a newly owned production round."""
    installed = Path(release["path"]).resolve()
    if resolve_lexicon_path().resolve() != installed or release["sha256"] != result["candidate_sha256"]:
        return {"code": "WORK_SNAPSHOT_RETIREMENT_DEFERRED", "reason": "ACTIVE_SUCCESSOR_CHANGED"}
    protected = {installed}
    if release.get("previous_path"):
        protected.add(Path(release["previous_path"]).resolve())
    retired, deferred = [], []
    for epoch in result["epochs"]:
        phase = directory / f"epoch-{epoch['epoch']:02d}"
        for name in ("teaching.db", "candidate.db"):
            path = phase / name
            if not path.exists():
                continue
            label = str(path.relative_to(directory))
            if (
                phase.is_symlink()
                or path.is_symlink()
                or path.resolve() in protected
                or any(path.with_name(name + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
            ):
                deferred.append(label)
                continue
            try:
                path.unlink()
            except OSError:
                deferred.append(label)
            else:
                retired.append(label)
    return {
        "code": "WORK_SNAPSHOTS_RETIRED" if not deferred else "WORK_SNAPSHOT_RETIREMENT_DEFERRED",
        "retired": retired,
        "deferred": deferred,
        "published_snapshot": str(installed),
    }


def publish_round(result, directory, destination, gold):
    from GSE.curation.lexicon_builder.publication import publish_sparse
    from scripts.audit_lexicon_runtime import audit_sparse_runtime

    if not result["changes"]:
        return {"code": "NO_ROUND_DOMAIN_CHANGES"}
    runtime = audit_sparse_runtime(result["candidate"])
    if runtime["code"] != "SPARSE_RUNTIME_VALIDATED":
        return {"code": "PUBLICATION_BLOCKED", "blockers": [runtime["code"]]}
    record(directory / "sparse-runtime.json", {key: value for key, value in runtime.items() if key != "measured_at"})
    release = publish_sparse(
        result["candidate"],
        destination,
        gold,
        expected_sha256=result["candidate_sha256"],
        expected_pointer_sha256=result["active_pointer_sha256"],
    )
    if release["code"] == "PUBLISHED_SPARSE_LEXICON":
        record(directory / "sparse-publication.json", release)
        owner = directory / "production-round.json"
        if owner.is_file() and read(owner) == {"plan_sha256": result["plan_sha256"]}:
            retention = retire_published_work(directory, result, release)
            record(directory / "snapshot-retention.json", retention)
            release = {**release, "retention": retention}
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("init", "run", "compare"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--policy", choices=POLICIES)
    parser.add_argument("--model")
    parser.add_argument("--model-digest")
    parser.add_argument("--model-context-tokens", type=int, default=65536)
    parser.add_argument("--publish-sparse-to", type=Path)
    parser.add_argument("--release-gold", type=Path)
    args = parser.parse_args()
    if bool(args.publish_sparse_to) != bool(args.release_gold) or (args.publish_sparse_to and args.phase != "run"):
        parser.error("Sparse round publication requires run, --publish-sparse-to, and --release-gold")
    plan = read(args.plan)
    parse_plan(plan)
    baseline, directory = args.baseline.resolve(strict=True), args.directory.resolve()
    if fingerprint(baseline) != plan["baseline_sha256"] or fingerprint(ACTIVE_POINTER) != plan["active_pointer_sha256"]:
        raise ValueError("EPOCH_FROZEN_INPUT_MISMATCH")
    if args.publish_sparse_to and baseline != resolve_lexicon_path():
        raise ValueError("EPOCH_PUBLICATION_REQUIRES_ACTIVE_BASELINE")
    directory.mkdir(parents=True, exist_ok=True)
    record(directory / "plan.json", plan)
    inventory_path = directory / "inventory.json"
    if args.phase == "init":
        inventory = plan_inventory(baseline, plan)
        record(inventory_path, inventory)
        groundings = mine_scope_chains(baseline, inventory)
        record(directory / "grounded-chains.json", groundings)
        print(
            json.dumps(
                {
                    "scope_sizes": {key: len(rows) for key, rows in inventory.items()},
                    "grounded_chain_proposals": len(groundings["proposals"]),
                }
            ),
            flush=True,
        )
        return
    if args.phase == "compare":
        result = compare(directory, plan)
        print(json.dumps(result), flush=True)
        return
    if not args.policy or not args.model or not args.model_digest:
        parser.error("run requires --policy, --model, and --model-digest")
    transport = OllamaTransport(
        args.model, context_tokens=args.model_context_tokens, timeout=420, thinking=False, output_tokens=256
    )
    transport.pin()
    if not transport.identity.startswith(f"{args.model}#{args.model_digest}@"):
        raise ValueError("EPOCH_MODEL_DIGEST_CHANGED")
    with (directory / (args.policy + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        arm_directory = directory / args.policy
        if args.publish_sparse_to and not arm_directory.exists():
            arm_directory.mkdir()
            record(arm_directory / "production-round.json", {"plan_sha256": digest(plan)})
        result = run_arm(
            plan,
            baseline,
            ACTIVE_POINTER,
            arm_directory,
            read(inventory_path),
            args.policy,
            transport,
            directory / "model.lock",
        )
        summary = {key: result[key] for key in ("candidate", "new_cells", "typed_questions_used")}
        if args.publish_sparse_to:
            release = publish_round(result, arm_directory, args.publish_sparse_to, args.release_gold)
            summary["publication"] = {
                key: release[key] for key in ("code", "path", "blockers", "retention") if key in release
            }
    print(json.dumps(summary), flush=True)
    if summary.get("publication", {}).get("code") == "PUBLICATION_BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
