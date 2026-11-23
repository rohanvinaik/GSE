"""Run the approved BODY convention through existing enrichment and epoch CLIs."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path

from gse.curation.lexicon_builder.epoch import (
    fingerprint,
    forecast,
    parse_plan,
    read,
    record,
    scope_rows,
    snapshot_copy,
)
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
BASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-020.db"
WORK = BASE.parent / "ssl-explicit-genera/coherence-021-approved"
HOLDOUTS = (
    "wordnet:cat:cat.n.01", "wordnet:duck:duck.n.01",
    "wordnet:shark:shark.n.01", "wordnet:salamander:salamander.n.01",
)
MODEL = "qwen3.8:27b-q4_K_M"
MODEL_DIGEST = "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e"
helpers = import_module("docs.readings.2026-11-13-ssl-explicit-genera.finish_coherence_020")


def status(code, **details):
    helpers.record_status(NOTES / "021-approved-round-status.json", {
        "format": "gse.lexicon-learning-round-status/1", "code": code,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": str(BASE), "unknown_is_not_zero": True,
        "activation_performed": False, **details,
    })
    print(code, json.dumps(details), flush=True)


def verify_sources():
    verification = read(NOTES / "021-approved-implementation-verification.json")
    if any(fingerprint(ROOT / name) != digest for name, digest in verification["source_sha256"].items()):
        raise ValueError("APPROVED_BODY_IMPLEMENTATION_CHANGED")
    parent = read(NOTES / "sparse-release-020-activation.json")
    if resolve_lexicon_path() != BASE or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]:
        raise ValueError("APPROVED_BODY_ACTIVE_BASELINE_CHANGED")
    return parent


def cli(module, *args):
    subprocess.run([sys.executable, "-u", "-m", module, *map(str, args)], cwd=ROOT, check=True)


def run():
    parent = verify_sources()
    approval = read(NOTES / "021-body-convention-approval.json")
    if approval["code"] != "FOUNDER_APPROVED_CONSTITUTIVE_ANATOMY_BODY_SUFFICIENCY":
        raise ValueError("BODY_CONVENTION_APPROVAL_REQUIRED")
    budgets = read(NOTES / "021-approved-input-budget-81920.json")
    if not all(row["fits"] for row in budgets["records"]):
        raise ValueError("BODY_CONTEXT_BUDGET_NOT_VERIFIED")
    if fingerprint(BASE) != parent["sha256"]:
        raise ValueError("APPROVED_BODY_BASELINE_HASH_CHANGED")
    WORK.mkdir(exist_ok=True)
    source, enriched = WORK / "source.db", WORK / "enriched.db"
    enrichment_report = NOTES / "021-approved-source-enrichment.json"
    if not enrichment_report.exists():
        status("ENRICHING_VERIFIED_DEFINING_GENUS_CONTEXT")
        snapshot_copy(BASE, source)
        cli("scripts.enrich_lexicon_sources", "--candidate", source, "--output", enriched,
            "--input", NOTES / "021-approved-source-context.json", "--report", enrichment_report)
    enrichment = read(enrichment_report)
    if enrichment["code"] != "ENRICHED_CANDIDATE" or enrichment["bank_changes"] or enrichment["added_records"] != 5:
        raise ValueError("BODY_CONTEXT_ENRICHMENT_NOT_VERIFIED")
    verify_sources()
    # The input snapshot was only a baseline backup. It has no added source or
    # audit rows; the real enrichment report binds its unmodified file digest.
    retirement = NOTES / "021-approved-source-copy-retirement.json"
    if not retirement.exists() and source.exists():
        before = helpers.file_state(source)
        if fingerprint(source) != enrichment["source_file_sha256"]:
            raise ValueError("BODY_SOURCE_BACKUP_CHANGED")
        helpers.no_open_handles(source)
        source.unlink()
        record(retirement, {
            "code": "UNMODIFIED_BASELINE_BACKUP_RETIRED_AFTER_ENRICHMENT_VALIDATION",
            "source": str(source), "retained_baseline": str(BASE), "identity": before,
            "sha256": enrichment["source_file_sha256"], "unique_source_or_audit_writes": 0,
        })
    original = read(NOTES / "021-vertebrate-source-review.json")
    family = original["family"]
    family["id"] = "approved-constitutive-vertebrate-alive-body"
    family["holdouts"] = list(HOLDOUTS)
    family["warrant"].update({
        "review_id": "021:approved-constitutive-anatomy-and-exact-genus",
        "warrant_id": "021:approved-constitutive-vertebrate-alive-body",
        "reviewer": "Founder-approved BODY projection and exact native-source review",
        "source_refs": [*family["warrant"]["source_refs"],
                        str(NOTES / "021-body-convention-approval.json"), str(enrichment_report)],
        "statement": (
            "Rohan explicitly approved constitutive anatomy, including verified defining-genus content, "
            "as sufficient for BODY=+1. Exact native vertebrate noun senses inherit the defining skeletal, "
            "spinal and cranial structure of the witnessed vertebrate genus. ALIVE=+1 must already be "
            "independently proved. The fresh teaching and four disjoint audits receive complete verified "
            "native ancestry definitions through the existing context-only enrichment path. "
            "This excludes reference-only roles, association, uncertain derived identities and other taxa; "
            "excluded cases stay unresolved. It supplies no other sign, no complement zeros, and does not "
            "treat the original five diagnostic replies as held-out confirmations."
        ),
    })
    plan = {
        "format": "gse.lexicon-epoch-plan/1", "baseline_sha256": enrichment["candidate_sha256"],
        "active_pointer_sha256": parent["pointer_sha256"], "epochs": 1,
        "audits_per_epoch": 4, "families": [family],
    }
    parse_plan(plan)
    plan_path = NOTES / "021-approved-coherence-plan.json"
    record(plan_path, plan)
    args = ("--plan", plan_path, "--baseline", enriched, "--directory", WORK)
    if not (WORK / "inventory.json").exists():
        cli("scripts.run_lexicon_epochs", *args, "init")
    inventory = read(WORK / "inventory.json")
    rules, rows = scope_rows(enriched, inventory[family["id"]])
    staged: dict = {"baseline_sha256": plan["baseline_sha256"], "scope_definitions": len(rows), **forecast(rows, rules, (parse_plan(plan)[family["id"]].relation(),))}
    record(NOTES / "021-approved-population-stage.json", staged)
    if staged["contradictions"] or any(len(row["before"]) == 1 for row in staged["changes"]):
        raise ValueError("APPROVED_BODY_STAGE_REQUIRES_ADJUDICATION")
    status("RUNNING_FRESH_BODY_TEACHING_AND_DISJOINT_AUDITS", scope_definitions=len(rows), provisional_cells=len(staged["changes"]))
    cli("scripts.run_lexicon_epochs", *args, "run", "--policy", "zipf", "--model", MODEL,
        "--model-digest", MODEL_DIGEST, "--model-context-tokens", 81920)
    verify_sources()
    result = read(WORK / "zipf/arm-result.json")
    if result["replay"]["code"] != "REPLAY_VALIDATED" or not result["replay"]["complete_search"]:
        raise ValueError("APPROVED_BODY_FULL_REPLAY_REQUIRED")
    status("CANDIDATE_REPLAY_VALIDATED_PENDING_PUBLICATION_CHECKS" if result["admitted"] else "FRESH_BODY_RULE_WITHHELD_REPLAY_VALIDATED",
           candidate=result["candidate"], candidate_sha256=result["candidate_sha256"],
           new_cells=result["new_cells"], typed_questions_used=result["typed_questions_used"],
           admitted=result["admitted"], replay_records=result["replay"]["entries_checked"])


if __name__ == "__main__":
    try:
        run()
    except BaseException as error:
        status("APPROVED_BODY_CYCLE_STOPPED", reason=repr(error))
        raise
