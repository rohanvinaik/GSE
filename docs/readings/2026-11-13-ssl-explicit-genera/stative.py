"""Run the next persistent Zipf epoch on explicit native state definitions."""

import argparse
from importlib import import_module
from pathlib import Path

from gse.curation.lexicon_builder.epoch import census, fingerprint, parse_plan, read, record, run_arm
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports
from scripts.run_lexicon_epochs import publish_round

anatomy = import_module("docs.readings.2026-11-14-ssl-anatomical-want.transfer")
NOTES = Path(__file__).resolve().parent
BASE = anatomy.BASE.with_name("sparse-release-017.db")
WORK = BASE.parent / "ssl-explicit-genera" / "stative-018"
FAMILY = {
    "id": "explicit-native-state-be",
    "antecedent": ["SOMETHING", 1],
    "consequent": ["BE", 1],
    "guards": [
        ["pos", "noun"],
        ["wordnet_native_lemma", "true"],
        ["wordnet_ancestor:state.n.02", "true"],
        ["wordnet_outside_ancestor:nonbeing.n.01", "true"],
        ["native_noun_frame:explicit_stative", "true"],
    ],
    "holdouts": ["wordnet:absence:absence.n.01", "wordnet:balance:balance.n.01", "wordnet:motion:motion.n.04"],
    "warrant": {
        "warrant_id": "explicit-native-state-be",
        "review_id": "explicit-native-state-be-source-review",
        "kind": "DEFINITIONAL_DERIVATION",
        "reviewer": "Source-backed construction review",
        "statement": "The complete noun definition explicitly identifies a state of something or a state in which "
        "a condition holds. Exact native WordNet state ancestry corroborates the state genus. Its own stative "
        "content supports BE=+1 under the approved GSE convention. The nonbeing branch is reserved for separate "
        "polarity review, and mixed genera and multiple glosses remain outside this construction.",
        "source_refs": [
            str(NOTES / "SOURCE_SCOPE.md"),
            str(NOTES.parent.parent / "program/LEXICON_CONSTRUCTION_DESIGN.md") + "#be-stative-content-scope",
        ],
    },
}


def freeze():
    parent = read(anatomy.NOTES / "sparse-release-017-activation.json")
    if (
        resolve_lexicon_path() != BASE
        or fingerprint(BASE) != parent["sha256"]
        or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]
    ):
        raise ValueError("STATIVE_EPOCH_BASELINE_CHANGED")
    return parent


def prepare():
    parent = freeze()
    WORK.mkdir(exist_ok=True)
    plan = {
        "format": "gse.lexicon-epoch-plan/1",
        "baseline_sha256": parent["sha256"],
        "active_pointer_sha256": parent["pointer_sha256"],
        "epochs": 1,
        "audits_per_epoch": 3,
        "families": [FAMILY],
    }
    families = parse_plan(plan)
    inventory = census(BASE, families)
    record(WORK / "plan.json", plan)
    record(WORK / "inventory.json", inventory)
    print("STATIVE_EPOCH_PREPARED", len(inventory[FAMILY["id"]]), flush=True)


def run():
    freeze()
    result = run_arm(
        read(WORK / "plan.json"),
        BASE,
        ACTIVE_POINTER,
        WORK / "zipf",
        read(WORK / "inventory.json"),
        "zipf",
        anatomy.previous.prior.previous.model(),
        WORK / "model.lock",
    )
    if len(result["epochs"]) != 1 or result["epochs"][0]["code"] != "RULE_ADMITTED":
        record(NOTES / "018-rule-withheld.json", result)
        raise ValueError("STATIVE_EPOCH_RULE_WITHHELD")
    if any(row["bank"] != "BE" or row["before"] != [-1, 0, 1] or row["after"] != [1] for row in result["changes"]):
        raise ValueError("STATIVE_EPOCH_UNEXPECTED_DOMAIN_DELTA")
    benchmark = audit(Path(result["candidate"]), anatomy.previous.prior.SOURCE_CASES)
    comparison = compare_reports(read(anatomy.NOTES / "017-grounded-benchmark.json"), benchmark)
    contrasts = audit(Path(result["candidate"]), anatomy.previous.prior.CONTRAST_CASES)
    if comparison["failures"] or contrasts["cases"] != read(anatomy.NOTES / "017-grounded-contrasts.json")["cases"]:
        raise ValueError("STATIVE_EPOCH_RUNTIME_REGRESSION")
    record(NOTES / "018-grounded-benchmark.json", {**benchmark, "comparison": comparison})
    record(NOTES / "018-grounded-contrasts.json", contrasts)
    record(
        NOTES / "018-verification.json",
        {"code": "VALIDATED_STATIVE_EPOCH", "result": result, "sentence_comparison": comparison},
    )
    print("STATIVE_EPOCH_VALIDATED", result["new_cells"], flush=True)


def publish():
    parent = freeze()
    verified = read(NOTES / "018-verification.json")
    if verified["code"] != "VALIDATED_STATIVE_EPOCH" or verified["sentence_comparison"]["failures"]:
        raise ValueError("STATIVE_EPOCH_VERIFICATION_REQUIRED")
    result = verified["result"]
    gold = read(anatomy.NOTES / "sparse-release-017-gold.json")
    controls = ("wordnet:arrest:arrest.n.02", "wordnet:sleeping:sleeping.n.01", "wordnet:anger:anger.n.02")
    gold["records"].extend({"entry_id": entry, "bank": "BE", "expected": 1} for entry in controls)
    from gse.api.encoder import GSEEncoder

    with GSEEncoder(result["candidate"]) as encoder:
        for entry in controls:
            if encoder.lookup_definition(entry)["selected"]["domains"]["BE"] != [1]:
                raise ValueError("STATIVE_EPOCH_RELEASE_LABEL_FAILED:" + entry)
            encoder.encode_definition(entry)
        for entry in (
            "wordnet:nonbeing:nonbeing.n.01",
            "wordnet:nonexistence:nonexistence.n.01",
            "wordnet:life:life.n.03",
        ):
            if encoder.lookup_definition(entry)["selected"]["domains"]["BE"] != [-1, 0, 1]:
                raise ValueError("STATIVE_EPOCH_RESERVED_CONTROL_CHANGED:" + entry)
    diagnostic_baseline = read(NOTES / "018-stative-diagnostic-baseline.json")
    if diagnostic_baseline["lexicon_sha256"] != parent["sha256"]:
        raise ValueError("STATIVE_EPOCH_DIAGNOSTIC_BASELINE_CHANGED")
    diagnostic = audit(Path(result["candidate"]), NOTES / "018-stative-diagnostic-cases.json")
    diagnostic_comparison = compare_reports(diagnostic_baseline, diagnostic)
    record(NOTES / "018-stative-diagnostic-candidate.json", {**diagnostic, "comparison": diagnostic_comparison})
    if diagnostic["lexicon_sha256"] != result["candidate_sha256"]:
        raise ValueError("STATIVE_EPOCH_DIAGNOSTIC_CANDIDATE_CHANGED")
    if diagnostic_comparison["failures"]:
        raise ValueError("STATIVE_EPOCH_DIAGNOSTIC_REGRESSION")
    for case in diagnostic["cases"]:
        if case["banks"]["BE"]["expected"] is None and case["banks"]["BE"]["emitted"] is not None:
            raise ValueError("STATIVE_EPOCH_UNKNOWN_BANK_EMITTED:" + case["id"])
    gold_path = NOTES / "sparse-release-018-gold.json"
    record(gold_path, gold)
    destination = BASE.with_name("sparse-release-018.db")
    publication = WORK / "publication"
    publication.mkdir(exist_ok=True)
    release = publish_round(result, publication, destination, gold_path)
    record(NOTES / "018-publication.json", release)
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        raise ValueError("STATIVE_EPOCH_PUBLICATION_BLOCKED")
    if (
        resolve_lexicon_path() != destination
        or Path(release["previous_path"]) != BASE
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"]
    ):
        raise ValueError("STATIVE_EPOCH_ACTIVE_RELEASE_MISMATCH")
    record(
        NOTES / "sparse-release-018-activation.json",
        {
            "code": "ACTIVE_STATIVE_EPOCH_VERIFIED",
            "path": str(destination),
            "previous_path": str(BASE),
            "sha256": release["sha256"],
            "pointer_sha256": fingerprint(ACTIVE_POINTER),
            "cells": release["cells"],
            "replay": release["replay"],
            "semantic_outcomes": release["semantic_audit"]["outcomes"],
        },
    )
    print("ACTIVE_STATIVE_EPOCH_VERIFIED", release["cells"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run", "publish"))
    phase = parser.parse_args().phase
    {"prepare": prepare, "run": run, "publish": publish}[phase]()
