"""Run the pinned acquisition and event rule cycle on sparse release 013."""

import argparse
from contextlib import closing
from math import log2
from pathlib import Path

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.epoch import (
    Family,
    JournaledTransport,
    census,
    connect,
    exact_delta,
    fingerprint,
    forecast,
    make_questions,
    read,
    record,
    scope_rows,
    snapshot_copy,
)
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.residual import OllamaTransport, _request_id
from gse.curation.lexicon_builder.reviewed_export import export_reviewed_input
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from gse.curation.lexicon_builder.rule_admission import admit_records
from gse.curation.lexicon_builder.rule_migration import migrate_revision
from gse.curation.lexicon_builder.rule_revisions import FORMAT
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports
from scripts.run_lexicon_epochs import publish_round

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-grounded-event-action"
BASE = WORK.parent / "sparse-release-013.db"
PARENT = NOTES.parent / "2026-11-13-ssl-sentence-event-action"
GROUNDING = NOTES.parent / "2026-11-13-ssl-contextual-grounding"
BASE_RECEIPT = PARENT / "sparse-release-013-activation.json"
MODEL = "qwen3.8:27b-q4_K_M"
MODEL_DIGEST = "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e"


def family(name, frame, bank, held, statement):
    return Family(
        name,
        None,
        (bank, 1),
        (("pos", "noun"), (f"native_noun_frame:{frame}", "true")),
        held,
        {
            "warrant_id": name,
            "review_id": name + "-source-review",
            "kind": "DEFINITIONAL_DERIVATION",
            "reviewer": "Source-backed construction review",
            "statement": statement,
            "source_refs": [
                str(NOTES / "SOURCE_SCOPE.md"),
                str(ROOT / "data/external/references/nsm-primes-chart-v20-2022.txt"),
            ],
        },
    )


FAMILIES = {
    "acquisition": family(
        "acquisition",
        "agentive_acquisition",
        "DO",
        (
            "wordnet:capture:capture.n.01",
            "wordnet:purchase:purchase.n.01",
        ),
        "The exact noun definition denotes taking custody or possession, forcible dispossession, "
        "or an explicitly named purchase or acquisition in exchange for payment.",
    ),
    "event": family(
        "event",
        "qualified_occurrence",
        "HAPPEN",
        (
            "wordnet:dislocation:dislocation.n.01",
            "wordnet:death:death.n.01",
            "wiktionary:en-calamity-en-noun-x-MTRlvm:8de6b57de211e4278c07f9469153a5d4ec47fb710614e4bb84149ae156366f0b",
        ),
        "The native noun gloss defines the event itself. Complements and restricted examples specify "
        "what happens without supplying an actor or another defining genus.",
    ),
}
TEACHING = {
    "acquisition": ("wordnet:arrest:apprehension.n.04", "wordnet:buying:buying.n.01"),
    "event": ("wordnet:finish:finish.n.05", "wordnet:change:change.n.01"),
}


def freeze():
    parent = read(BASE_RECEIPT)
    if resolve_lexicon_path() != BASE or fingerprint(BASE) != parent["sha256"]:
        raise ValueError("GROUNDED_ROUND_BASELINE_CHANGED")
    if fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]:
        raise ValueError("GROUNDED_ROUND_POINTER_CHANGED")
    return parent


def stage():
    inventory = census(BASE, FAMILIES)
    benchmark = read(GROUNDING / "final-corrected-benchmark.json")["cases"]
    held_lemmas = {case["lemma"] for case in benchmark}
    held_groups = {
        "wordnet:" + case["sense"].rsplit(":", 1)[-1]
        for case in benchmark
        if (case["sense"] or "").startswith("wordnet:")
    }
    target = {
        (case["sense"], bank) for case in benchmark for bank, cell in case["banks"].items() if cell["runtime"] == "OPEN"
    }
    everyone = {item["entry_id"]: item for group in inventory.values() for item in group}
    for name, scope in FAMILIES.items():
        if any(
            everyone[i]["lemma"] in held_lemmas or everyone[i]["sense_group"] in held_groups for i in scope.holdouts
        ):
            raise ValueError("GROUNDED_ROUND_AUDIT_LEAKAGE")
        if not set(TEACHING[name]) <= {item["entry_id"] for item in inventory[name]}:
            raise ValueError("GROUNDED_ROUND_TEACHING_OUTSIDE_SCOPE")
    rules, rows = scope_rows(BASE, everyone.values())
    joint = forecast(rows, rules, tuple(scope.relation() for scope in FAMILIES.values()))
    changes = {(r["entry_id"], r["bank"]) for r in joint["changes"]}
    if (
        joint["contradictions"]
        or not target <= changes
        or any(r["before"] != [-1, 0, 1] or r["after"] != [1] for r in joint["changes"])
    ):
        raise ValueError("GROUNDED_ROUND_UNSAFE_STAGE")
    record(WORK / "refined-inventory.json", inventory)
    record(
        NOTES / "refined-population-stage.json",
        {
            **joint,
            "baseline_sha256": fingerprint(BASE),
            "targets": sorted(target),
            "teaching": TEACHING,
            "holdouts": {name: scope.holdouts for name, scope in FAMILIES.items()},
            "population": {name: len(group) for name, group in inventory.items()},
        },
    )
    return joint


def model():
    transport = OllamaTransport(MODEL, context_tokens=131072, timeout=600, thinking=False, output_tokens=256)
    if transport.pin()["digest"] != MODEL_DIGEST:
        raise ValueError("GROUNDED_ROUND_MODEL_CHANGED")
    return transport


def teach(scope, name, working, transport, directory):
    bank = scope.consequent[0]
    requests = make_questions(BASE, [(entry, bank) for entry in TEACHING[name]])
    journal = JournaledTransport(transport, directory, "teach", len(requests), WORK / "model.lock")
    # Pre-journal in the specified teaching order. The production writer
    # regenerates every exact request and consumes the same signed response.
    for question in requests:
        journal(question.payload(), question.output_schema())
    path = directory / "typed-writer.json"
    if not path.is_file():
        result = complete_dictionary(
            working,
            journal,
            len(requests),
            entry_ids=TEACHING[name],
            banks=(bank,),
            max_calls_per_entry=1,
            max_entries_per_pass=len(requests),
            priority="zipf",
            progress=lambda row: print(row, flush=True),
        )
        record(path, result)
    with closing(connect(working)) as conn:
        all_receipts = read_model_receipts(conn)
        receipts = []
        for question in requests:
            choices = [r for r in all_receipts.get(question.entry_id, ()) if r["request_id"] == question.request_id]
            if len(choices) != 1 or choices[0]["assertion"]["value"] != scope.consequent[1]:
                raise ValueError(f"GROUNDED_ROUND_TEACHING_UNCONFIRMED:{question.entry_id}")
            receipts.extend(choices)
    return receipts


def reviewed(scope, name, working, receipts, transport, directory):
    warrant = scope.warrant
    raw = export_reviewed_input(
        working,
        {
            "format": "gse.reviewed-pattern-selection/1",
            "discovery_entry_ids": list(TEACHING[name]),
            "audit_entry_ids": list(scope.holdouts),
            "guarded_candidates": [scope.proposal()],
            "reviews": [
                {
                    "request_id": r["request_id"],
                    "review": {
                        "code": "ACCEPTED",
                        "receipt_sha256": _request_id(r),
                        "review_id": f"{name}:{r['entry_id']}",
                        "reviewer": warrant["reviewer"],
                        "source_refs": warrant["source_refs"],
                        "rationale": warrant["statement"],
                    },
                }
                for r in receipts
            ],
        },
    )["input"]
    record(directory / "reviewed-input.json", raw)
    journal = JournaledTransport(transport, directory, "audit", len(scope.holdouts), WORK / "model.lock")
    path = directory / "audit.json"
    report = read(path) if path.is_file() else run_workflow_input(raw, journal, max_calls=len(scope.holdouts))
    record(path, report)
    [candidate] = report["candidates"]
    print(name, candidate["discovery_outcomes"], candidate["audit_outcomes"], flush=True)
    admission = admit_records(
        raw,
        report,
        {
            "rule_id": candidate["relation"]["rule_id"],
            "warrant_sha256": candidate["warrant_sha256"],
            "review_id": name + "-admission",
            "reviewer": warrant["reviewer"],
            "decision": "APPROVE_DEFINITIONAL_RULE",
            "source_refs": warrant["source_refs"],
            "rationale": warrant["statement"],
        },
    )
    record(directory / "admission.json", admission)
    return admission


def contrast_controls(candidate):
    controls = {
        "wordnet:arrest:arrest.n.02": ("DO", "HAPPEN"),
        "wordnet:purchase:purchase.n.02": ("DO", "HAPPEN"),
        "wordnet:inheritance:inheritance.n.01": ("DO", "HAPPEN"),
        "wordnet:catching:catching.n.03": ("DO", "HAPPEN"),
        "wordnet:obtention:obtainment.n.01": ("DO", "HAPPEN"),
        "wordnet:buyback:redemption.n.03": ("DO", "HAPPEN"),
        "wordnet:fire:fire.n.04": ("HAPPEN",),
        "wordnet:finish:finish.n.04": ("HAPPEN",),
        "wordnet:destruction:destruction.n.02": ("HAPPEN",),
        "wordnet:arrival:arrival.n.03": ("DO", "HAPPEN"),
    }
    from gse.api.encoder import GSEEncoder

    with GSEEncoder(candidate) as encoder:
        findings = []
        for entry, banks in controls.items():
            selected = encoder.lookup_definition(entry)["selected"]
            for bank in banks:
                domain = selected["domains"][bank]
                if domain != [-1, 0, 1]:
                    raise ValueError(f"GROUNDED_ROUND_CONTRAST_CHANGED:{entry}:{bank}")
                findings.append({"entry_id": entry, "bank": bank, "domain": domain})
    return findings


def main():
    parent = freeze()
    staged = stage()
    transport = model()
    WORK.mkdir(exist_ok=True)
    teaching = WORK / "teaching.db"
    snapshot_copy(BASE, teaching)
    admissions = []
    for name, scope in FAMILIES.items():
        phase = WORK / name
        phase.mkdir(exist_ok=True)
        review_phase = phase / "explicit-transaction-refinement" if name == "acquisition" else phase
        review_phase.mkdir(exist_ok=True)
        path = review_phase / "admission.json"
        if path.is_file():
            admission = read(path)
        else:
            receipts = teach(scope, name, teaching, transport, phase)
            admission = reviewed(scope, name, teaching, receipts, transport, review_phase)
        admissions.append(admission)
    if len({a["baseline_version"] for a in admissions}) != 1:
        raise ValueError("GROUNDED_ROUND_ADMISSION_BASELINE_MISMATCH")
    revision = {
        "format": FORMAT,
        "baseline_version": admissions[0]["baseline_version"],
        "admissions": admissions,
        "retirements": [],
        "exceptions": [],
    }
    candidate = WORK / "candidate.db"
    migration_path = WORK / "migration.json"
    if not migration_path.is_file():
        record(migration_path, migrate_revision(teaching, candidate, revision))
    replay = read(migration_path)["postflight"]
    count, changes = exact_delta(BASE, candidate)
    if (
        sorted(changes, key=lambda row: (row["entry_id"], row["bank"]))
        != sorted(staged["changes"], key=lambda row: (row["entry_id"], row["bank"]))
        or replay["entries_validated"] != count
        or not replay["complete_search"]
        or replay["entries_mismatched"]
    ):
        raise ValueError("GROUNDED_ROUND_REPLAY_DIFFERS_FROM_STAGE")
    sentence_report = audit(candidate, GROUNDING / "sentences-corrected.json")
    comparison = compare_reports(read(GROUNDING / "final-corrected-benchmark.json"), sentence_report)
    record(NOTES / "candidate-sentences.json", {**sentence_report, "comparison": comparison})
    if comparison["failures"] or any(
        cell["runtime"] == "OPEN" for case in sentence_report["cases"] for cell in case["banks"].values()
    ):
        raise ValueError("GROUNDED_ROUND_BENCHMARK_GAPS")
    freeze()
    result = {
        "code": "GROUNDED_EVENT_ACTION_REPLAY_VALIDATED",
        "candidate": str(candidate),
        "candidate_sha256": fingerprint(candidate),
        "active_pointer_sha256": parent["pointer_sha256"],
        "baseline_sha256": parent["sha256"],
        "replay": replay,
        "changes": changes,
        "new_cells": len(changes),
        "bits_removed": sum(log2(len(row["before"]) / len(row["after"])) for row in changes),
        "rules": [a["relation"]["rule_id"] for a in admissions],
        "sentence_comparison": comparison,
    }
    record(NOTES / "verification.json", result)
    print(result["code"], len(changes), flush=True)


def publish():
    parent = freeze()
    result = read(NOTES / "verification.json")
    sentence = read(NOTES / "candidate-sentences.json")
    if (
        result["code"] != "GROUNDED_EVENT_ACTION_REPLAY_VALIDATED"
        or result["sentence_comparison"]["failures"]
        or not result["replay"]["complete_search"]
        or result["replay"]["entries_mismatched"]
        or not result["changes"]
        or any(row["before"] != [-1, 0, 1] or row["after"] != [1] for row in result["changes"])
        or result["candidate_sha256"] != sentence["lexicon_sha256"]
        or fingerprint(Path(result["candidate"])) != result["candidate_sha256"]
        or result["active_pointer_sha256"] != parent["pointer_sha256"]
    ):
        raise ValueError("GROUNDED_ROUND_PUBLICATION_REQUIRES_REPLAY_AND_BENCHMARK")
    controls = contrast_controls(Path(result["candidate"]))
    record(NOTES / "contrast-controls.json", {"controls": controls})
    gold = PARENT / "sparse-release-013-gold.json"
    destination = WORK.parent / "sparse-release-014.db"
    release = publish_round(result, WORK, destination, gold)
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        record(NOTES / "publication-blocked.json", release)
        raise ValueError("GROUNDED_ROUND_PUBLICATION_BLOCKED")
    if (
        resolve_lexicon_path() != destination
        or Path(release["previous_path"]) != BASE
        or fingerprint(destination) != result["candidate_sha256"]
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"]
    ):
        raise ValueError("GROUNDED_ROUND_ACTIVE_SNAPSHOT_MISMATCH")
    record(
        NOTES / "sparse-release-014-activation.json",
        {
            "format": "gse.active-ssl-grounded-event-action/1",
            "code": "ACTIVE_SSL_GROUNDED_EVENT_ACTION_VERIFIED",
            "path": str(destination),
            "previous_path": str(BASE),
            "sha256": release["sha256"],
            "pointer_sha256": fingerprint(ACTIVE_POINTER),
            "cells": release["cells"],
            "records_replayed": release["replay"]["entries_checked"],
            "mismatches": release["replay"]["entries_mismatched"],
            "semantic_outcomes": release["semantic_audit"]["outcomes"],
            "sentence_comparison": result["sentence_comparison"],
            "publication_receipt": str(WORK / "sparse-publication.json"),
        },
    )
    print("ACTIVE_SSL_GROUNDED_EVENT_ACTION_VERIFIED", release["cells"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    if parser.parse_args().publish:
        publish()
    else:
        main()
