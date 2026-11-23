"""Run the next pinned literal-genus cycle through the existing epoch CLI."""

import argparse
import subprocess
import sys
from pathlib import Path

from gse.curation.lexicon_builder.epoch import (
    Family,
    fingerprint,
    forecast,
    parse_plan,
    read,
    record,
    scope_rows,
)
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

ROOT = Path(__file__).resolve().parents[3]
NOTES = Path(__file__).resolve().parent
BASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-021.db"
WORK = BASE.parent / "ssl-explicit-genera/coherence-022"


def prepare():
    if resolve_lexicon_path() != BASE:
        raise ValueError("LITERAL_GENUS_REQUIRES_ACTIVE_021")
    inventory = read(NOTES / "022-literal-genus-inventory.json")["families"]
    holdouts = {
        "literal-temporal-extent": (
            "wordnet:shift:shift.n.03",
            next(d["entry_id"] for d in inventory["literal-temporal-extent"]["definitions"]
                 if d["entry_id"].startswith("wiktionary:") and d["lemma"] == "eon"),
            next(d["entry_id"] for d in inventory["literal-temporal-extent"]["definitions"]
                 if d["entry_id"].startswith("wiktionary:") and d["lemma"] == "lapse"),
        ),
        "literal-human-collective": (
            "wordnet:dead:dead.n.01", "wordnet:assembly:assembly.n.04",
            next(d["entry_id"] for d in inventory["literal-human-collective"]["definitions"]
                 if d["entry_id"].startswith("wiktionary:") and d["lemma"] == "population"),
        ),
    }
    families = []
    for key, rows in inventory.items():
        bank, frame = rows["target_bank"], rows["frame"]
        warrant = {
            "kind": "DEFINITIONAL_DERIVATION", "warrant_id": "022:" + key,
            "review_id": "022:complete-own-genus-source-review:" + key,
            "reviewer": "Exact native-source and approved-coordinate review",
            "source_refs": [str(NOTES / "022-source-review.md"),
                            str(ROOT / "data/external/references/nsm-primes-chart-v20-2022.txt"),
                            str(ROOT / "gse/primitives_v2.py"),
                            str(ROOT / "docs/program/LEXICON_CONSTRUCTION_DESIGN.md")],
            "statement": (
                "An exact native noun definition whose own genus explicitly denotes a period, interval, span or duration "
                "of time has temporal WHEN content. Sentence binding, quantitative magnitude and other banks remain "
                "separate. Alternative genera, unrelated heads, missing witnesses and unverified identities are excluded."
                if bank == "WHEN" else
                "An exact native noun definition whose own genus denotes people collectively or an explicitly human "
                "group has PEOPLE content. A single person, objects used by people, mixed genera and unverified "
                "identities are outside scope. This gives no life-status, body, desire or person-deixis sign."
            ),
        }
        families.append(Family(key, None, (bank, 1), (("pos", "noun"), ("native_noun_frame:" + frame, "true")),
                               holdouts[key], warrant))
    plan = {
        "format": "gse.lexicon-epoch-plan/1", "baseline_sha256": fingerprint(BASE),
        "active_pointer_sha256": fingerprint(ACTIVE_POINTER), "epochs": 2, "audits_per_epoch": 3,
        "families": [{"id": f.id, **f.proposal(), "holdouts": list(f.holdouts)} for f in families],
    }
    for item in plan["families"]:
        item.pop("absent_evidence")
    parse_plan(plan)
    WORK.mkdir(exist_ok=True)
    record(NOTES / "022-coherence-plan.json", plan)
    invoke("init")
    frozen = read(WORK / "inventory.json")
    rules, rows = scope_rows(BASE, {r["entry_id"]: r for group in frozen.values() for r in group}.values())
    stage: dict = {"baseline_sha256": plan["baseline_sha256"], "scope_definitions": len(rows),
             **forecast(rows, rules, tuple(f.relation() for f in families))}
    if stage["contradictions"] or any(len(r["before"]) == 1 for r in stage["changes"]):
        raise ValueError("LITERAL_GENUS_STAGE_REQUIRES_REVIEW")
    record(NOTES / "022-population-stage.json", stage)
    print("LITERAL_GENUS_SCOPED_STAGE", {"scope": len(rows), "new_cells": len(stage["changes"])}, flush=True)


def invoke(phase):
    pins = read(NOTES / "022-implementation-verification.json")
    for name, expected in pins["source_sha256"].items():
        if fingerprint(ROOT / name) != expected:
            raise ValueError("LITERAL_GENUS_FROZEN_SOURCE_CHANGED:" + name)
    command = [sys.executable, "-u", "-m", "scripts.run_lexicon_epochs", phase,
               "--plan", str(NOTES / "022-coherence-plan.json"), "--baseline", str(BASE),
               "--directory", str(WORK)]
    if phase == "run":
        model = read(NOTES / "021-approved-live-model-runtime.json")["model"]
        command.extend(["--policy", "zipf", "--model", model["name"], "--model-digest", model["digest"],
                        "--model-context-tokens", "81920"])
    subprocess.run(command, cwd=ROOT, check=True)


def run():
    if not (NOTES / "022-coherence-plan.json").exists():
        prepare()
    invoke("run")
    result = read(WORK / "zipf/arm-result.json")
    record(NOTES / "022-round-status.json", {
        "code": "CANDIDATE_REPLAY_FINISHED_NOT_PUBLISHED", "activation_performed": False,
        "candidate": result["candidate"], "new_cells": result["new_cells"],
        "typed_questions_used": result["typed_questions_used"], "replay": result["replay"],
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    args = parser.parse_args()
    {"prepare": prepare, "run": run}[args.phase]()
