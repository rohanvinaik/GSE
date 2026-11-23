"""Resume the existing bounded epoch CLI after verified 020 publication."""

import json
import subprocess
import sys
import time
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
)
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

record_status = import_module(
    "docs.readings.2026-11-13-ssl-explicit-genera.finish_coherence_020"
).record_status

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/coherence-021"
REVIEW = NOTES / "021-vertebrate-source-review.json"
MODEL = "qwen3.8:27b-q4_K_M"
MODEL_DIGEST = "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e"


def available(path):
    try:
        return read(path)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def verify_pins(pins):
    if any(fingerprint(ROOT / path) != expected for path, expected in pins.items()):
        raise ValueError("COHERENCE_021_REVIEWED_SOURCE_CHANGED")


def freeze_plan(baseline, review):
    plan = {
        "format": "gse.lexicon-epoch-plan/1",
        "baseline_sha256": fingerprint(baseline),
        "active_pointer_sha256": fingerprint(ACTIVE_POINTER),
        "epochs": 1,
        "audits_per_epoch": review["audits_per_epoch"],
        "families": [review["family"]],
    }
    parse_plan(plan)
    path = NOTES / "021-coherence-plan.json"
    if path.exists() and read(path) != plan:
        raise ValueError("COHERENCE_021_FROZEN_PLAN_CHANGED")
    record(path, plan)
    return path, plan


def run():
    reviewed = read(REVIEW)
    pins = {
        **read(NOTES / "020-implementation-verification.json")["source_sha256"],
        **read(NOTES / "020-status-writer-verification.json")["source_sha256"],
        **read(NOTES / "020-retention-check-verification.json")["source_sha256"],
    }
    pins.update({
        str(REVIEW.relative_to(ROOT)): fingerprint(REVIEW),
        str(Path(__file__).relative_to(ROOT)): fingerprint(Path(__file__)),
        reviewed["primary_source"]["pdf"]: reviewed["primary_source"]["pdf_sha256"],
        reviewed["primary_source"]["text"]: reviewed["primary_source"]["text_sha256"],
    })
    verify_pins(pins)
    print("COHERENCE_021_WAITING_FOR_VALIDATED_020_AND_ROLLING_RETENTION", flush=True)
    while True:
        status = available(NOTES / "020-round-status.json")
        if status and status.get("code") == "PUBLISHED_AND_ROLLING_RETENTION_VERIFIED":
            break
        failure = available(NOTES / "020-finisher-failure.json")
        if failure:
            raise ValueError("COHERENCE_020_FINISHER_FAILED:" + failure["reason"])
        time.sleep(10)
    verify_pins(pins)
    baseline = resolve_lexicon_path()
    expected = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-020.db"
    activation = read(NOTES / "sparse-release-020-activation.json")
    if (
        baseline != expected
        or str(baseline) != status["active_path"]
        or fingerprint(baseline) != status["active_sha256"]
        or fingerprint(ACTIVE_POINTER) != activation["pointer_sha256"]
    ):
        raise ValueError("COHERENCE_021_REQUIRES_EXACT_VALIDATED_ACTIVE_020")
    plan_path, plan = freeze_plan(baseline, reviewed)
    record_status(NOTES / "021-round-status.json", {
        "format": "gse.lexicon-learning-round-status/1",
        "code": "INITIALIZING_FROM_VALIDATED_020",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": str(baseline),
        "baseline_sha256": plan["baseline_sha256"],
        "construction_question_budget": reviewed["construction_question_budget"],
        "unknown_is_not_zero": True,
        "activation_performed": False,
    })
    common = [
        sys.executable, "-u", "-m", "scripts.run_lexicon_epochs",
        "--plan", str(plan_path), "--baseline", str(baseline), "--directory", str(WORK),
    ]
    subprocess.run([*common, "init"], cwd=ROOT, check=True)
    inventory = read(WORK / "inventory.json")
    families = parse_plan(plan)
    family = families[reviewed["family"]["id"]]
    rules, rows = scope_rows(baseline, inventory[family.id])
    staged = forecast(rows, rules, (family.relation(),))
    record(NOTES / "021-rebased-population-stage.json", {
        "baseline_sha256": plan["baseline_sha256"],
        "scope_definitions": len(rows),
        "authority": "UNADMITTED_READ_ONLY_STAGE",
        **staged,
    })
    if staged["contradictions"]:
        raise ValueError("COHERENCE_021_REBASED_STAGE_HAS_CONTRADICTIONS")
    verify_pins(pins)
    print("COHERENCE_021_STARTING_ZIPF_TEACHING_AND_FOUR_DISJOINT_AUDITS", flush=True)
    subprocess.run([
        *common, "run", "--policy", "zipf", "--model", MODEL, "--model-digest", MODEL_DIGEST,
    ], cwd=ROOT, check=True)
    verify_pins(pins)
    result = read(WORK / "zipf/arm-result.json")
    if (
        result["replay"]["code"] != "REPLAY_VALIDATED"
        or not result["replay"]["complete_search"]
        or result["typed_questions_used"] > reviewed["construction_question_budget"]
        or fingerprint(ACTIVE_POINTER) != plan["active_pointer_sha256"]
    ):
        raise ValueError("COHERENCE_021_RESULT_CONTRACT_FAILED")
    report = {
        "format": "gse.lexicon-learning-round-status/1",
        "code": "CANDIDATE_REPLAY_VALIDATED_PENDING_PUBLICATION_REVIEW"
        if result["admitted"] else "RULE_WITHHELD_CANDIDATE_REPLAY_VALIDATED",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": str(baseline),
        "candidate": result["candidate"],
        "candidate_sha256": result["candidate_sha256"],
        "new_cells": result["new_cells"],
        "typed_questions_used": result["typed_questions_used"],
        "admitted": result["admitted"],
        "epoch_outcomes": [epoch["code"] for epoch in result["epochs"]],
        "replay": result["replay"],
        "unknown_is_not_zero": True,
        "activation_performed": False,
    }
    record_status(NOTES / "021-round-status.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    try:
        run()
    except BaseException as error:
        record_status(NOTES / "021-continuation-failure.json", {
            "code": "CONTINUATION_STOPPED",
            "reason": repr(error),
            "active_path": str(resolve_lexicon_path()),
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        raise
