"""Continue the anatomical WANT cycle on exact Wiktionary senses from release 016."""

import argparse
from contextlib import closing
from importlib import import_module
from math import log2
from pathlib import Path

from gse.curation.lexicon_builder.completion import _priority_source, complete_dictionary
from gse.curation.lexicon_builder.epoch import (
    Family,
    JournaledTransport,
    census,
    choose,
    connect,
    epoch_discovery,
    exact_delta,
    fingerprint,
    forecast,
    make_questions,
    read,
    record,
    reviewed_input,
    scope_rows,
    snapshot_copy,
)
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.publication import publish_sparse
from gse.curation.lexicon_builder.residual import _request_id
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from gse.curation.lexicon_builder.rule_admission import admit_records
from gse.curation.lexicon_builder.rule_migration import migrate_revision
from gse.curation.lexicon_builder.rule_revisions import FORMAT
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_runtime import audit_sparse_runtime
from scripts.audit_lexicon_sentences import audit, compare_reports

previous = import_module("docs.readings.2026-11-14-ssl-anatomical-want.run_round")
NOTES = Path(__file__).resolve().parent
BASE = previous.BASE.with_name("sparse-release-016.db")
WORK = previous.WORK
TEACHING = WORK / "017-teaching.db"
CANDIDATE = WORK / "017-candidate.db"
HEART = "wiktionary:en-heart-en-noun-en:Q1072:181adf258580fcb213e17539d733e06f42748edd8540a6e0b1d3b165d6257de4"
HOLDOUTS = {
    "organ_gland": (
        "wiktionary:en-lung-en-noun-rbqNN2WD:a17a6d74ce73c390545589b33af042053be94ffe9e17f65863a160ece5067569",
        "wiktionary:en-pancreas-en-noun-y0qWM6Sy:f53e26107a852a1d2cac61e0a561a67570daa747e3c38c6f70618c6d61f94225",
    ),
    "physical_structure": (
        "wiktionary:en-radius-en-noun-BnGNiC-k:454474dc4f700836ee9c922a14d28a327bfb359048348f79efd6a2ed6234774f",
        "wiktionary:en-quadriceps-en-noun-ZH84nFYV:94220b0ebc990049c8603c50aa7e237eccaacd4fd1b1f30f2c38aa513e298ed9",
    ),
}
FAMILIES = {
    frame: Family(
        frame,
        ("BODY", 1),
        ("WANT", 0),
        (("pos", "noun"), ("wiktionary_anatomy_frame:" + frame, "true")),
        held,
        {
            "warrant_id": "wiktionary-anatomy-want-" + frame,
            "review_id": "wiktionary-anatomy-want-" + frame + "-review",
            "kind": "DEFINITIONAL_DERIVATION",
            "reviewer": "Source-backed construction review",
            "statement": "The exact anatomical definition identifies physical structure, bodily location, or "
            "physiological function. The criteria are independent of wanting. Native genus and attachment "
            "evidence must establish the scope, and mental-content attachments are reserved.",
            "source_refs": [
                str(NOTES / "SOURCE_SCOPE.md"),
                str(NOTES.parent.parent / "program/LEXICON_CONSTRUCTION_DESIGN.md") + "#want-polarity",
            ],
        },
    )
    for frame, held in HOLDOUTS.items()
}


def freeze():
    parent = read(NOTES / "sparse-release-016-activation.json")
    if (
        resolve_lexicon_path() != BASE
        or fingerprint(BASE) != parent["sha256"]
        or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]
    ):
        raise ValueError("WIKTIONARY_WANT_BASELINE_CHANGED")
    return parent


def stage():
    parent = freeze()
    inventory = census(BASE, FAMILIES)
    frequency_source, frequencies = _priority_source("zipf", None)
    selected = [
        choose(BASE, inventory, FAMILIES, set(FAMILIES) - {name}, set(), "zipf", frequencies) for name in FAMILIES
    ]
    if any(item is None for item in selected):
        raise ValueError("WIKTIONARY_WANT_NO_ELIGIBLE_TEACHER")
    selected.sort(key=lambda item: (-item["subtlex"], item["entry_id"]))
    everyone = {r["entry_id"]: r for group in inventory.values() for r in group}
    rules, rows = scope_rows(BASE, everyone.values())
    staged = forecast(rows, rules, tuple(f.relation() for f in FAMILIES.values()))
    if staged["contradictions"] or any(
        row["bank"] != "WANT" or row["before"] != [-1, 0, 1] or row["after"] != [0] for row in staged["changes"]
    ):
        raise ValueError("WIKTIONARY_WANT_UNSAFE_FORECAST")
    result = {
        **staged,
        "inventory": inventory,
        "selected": selected,
        "frequency_source": frequency_source,
        "baseline_sha256": parent["sha256"],
        "active_pointer_sha256": parent["pointer_sha256"],
    }
    record(NOTES / "017-population-stage.json", result)
    print(
        "WIKTIONARY_TRANSFER_STAGED",
        len(staged["changes"]),
        [(x["entry_id"], x["subtlex"]) for x in selected],
        flush=True,
    )


def teach():
    freeze()
    selections = read(NOTES / "017-population-stage.json")["selected"]
    requests = make_questions(BASE, [(item["entry_id"], "WANT") for item in selections] + [(HEART, "WANT")])
    transport = previous.prior.previous.model()
    journal = JournaledTransport(transport, WORK, "017-teach", len(selections), WORK / "model.lock")
    for question in requests[:-1]:
        print("TEACHING", question.entry_id, journal(question.payload(), question.output_schema()), flush=True)
    boundary = JournaledTransport(transport, WORK, "017-heart-boundary", 1, WORK / "model.lock")
    question = requests[-1]
    raw = boundary(question.payload(), question.output_schema())
    record(
        NOTES / "017-heart-boundary-audit.json",
        {
            "entry_id": HEART,
            "request": question.payload(),
            "schema": question.output_schema(),
            "request_id": question.request_id,
            "raw_output": raw,
            "transport": boundary.identity,
            "lexicon_writes": False,
            "scope": "MENTAL_ATTACHMENT_REVIEW_PENDING",
        },
    )
    print("HEART_BOUNDARY", raw, flush=True)
    snapshot_copy(BASE, TEACHING)
    path = WORK / "017-typed-writer.json"
    if not path.exists():
        report = complete_dictionary(
            TEACHING,
            journal,
            len(selections),
            entry_ids=tuple(item["entry_id"] for item in selections),
            banks=("WANT",),
            max_calls_per_entry=1,
            max_entries_per_pass=len(selections),
            priority="zipf",
            progress=lambda row: print(row, flush=True),
        )
        record(path, report)
    print("WIKTIONARY_TRANSFER_TEACHING_RECORDED", read(path)["outcomes"], flush=True)


def audit_rules():
    freeze()
    transport = previous.prior.previous.model()
    selections = read(NOTES / "017-population-stage.json")["selected"]
    with closing(connect(TEACHING)) as conn:
        index = read_model_receipts(conn)
        receipts = {item["entry_id"]: index.get(item["entry_id"], ()) for item in selections}
    for selected in selections:
        name = selected["family"]
        family = FAMILIES[name]
        [receipt] = [r for r in receipts.get(selected["entry_id"], ()) if r["assertion"]["bank"] == "WANT"]
        if receipt["assertion"]["value"] != 0:
            raise ValueError("WIKTIONARY_WANT_TEACHING_DISAGREEMENT")
        taught = {
            "code": "REVIEWED_TEACHING",
            "request_id": receipt["request_id"],
            "receipt_sha256": _request_id(receipt),
        }
        raw = reviewed_input(TEACHING, family, selected, taught)
        record(WORK / ("017-" + name + "-input.json"), raw)
        grounding, observed = epoch_discovery(raw, family, FAMILIES)
        record(WORK / ("017-" + name + "-discovery.json"), {"grounding": grounding, "observed": observed})
        journal = JournaledTransport(
            transport, WORK, "017-" + name + "-audit", len(family.holdouts), WORK / "model.lock"
        )
        audit_path = WORK / ("017-" + name + "-audit.json")
        report = (
            read(audit_path)
            if audit_path.exists()
            else run_workflow_input(raw, journal, max_calls=len(family.holdouts))
        )
        record(audit_path, report)
        [candidate] = report["candidates"]
        print(name, candidate["audit_outcomes"], flush=True)
        admission = admit_records(
            raw,
            report,
            {
                "rule_id": candidate["relation"]["rule_id"],
                "warrant_sha256": candidate["warrant_sha256"],
                "review_id": "wiktionary-transfer-" + name,
                "reviewer": family.warrant["reviewer"],
                "decision": "APPROVE_DEFINITIONAL_RULE",
                "source_refs": family.warrant["source_refs"],
                "rationale": family.warrant["statement"],
            },
        )
        record(WORK / ("017-" + name + "-admission.json"), admission)


def heart_fill():
    freeze()
    reviewed = read(NOTES / "017-heart-boundary-audit.json")
    record(
        NOTES / "017-heart-source-review.json",
        {
            "entry_id": HEART,
            "bank": "WANT",
            "value": 0,
            "request_id": reviewed["request_id"],
            "reviewer": "Source-backed construction review",
            "source_refs": [str(NOTES / "SOURCE_SCOPE.md")],
            "rationale": "The complete definition identifies a blood-pumping organ and reports a traditional "
            "association with emotion. Neither criterion encodes wanting or not wanting. Its WANT coordinate "
            "is orthogonal under the approved convention. The additional attachment remains outside the population guard.",
        },
    )
    transport = JournaledTransport(previous.prior.previous.model(), WORK, "017-heart-boundary", 1, WORK / "model.lock")
    path = WORK / "017-heart-writer.json"
    if not path.exists():
        report = complete_dictionary(
            TEACHING,
            transport,
            1,
            entry_ids=(HEART,),
            banks=("WANT",),
            max_calls_per_entry=1,
            max_entries_per_pass=1,
            priority="zipf",
            progress=lambda row: print(row, flush=True),
        )
        record(path, report)
    if read(path)["outcomes"] != {"ASSIGNED": 1}:
        raise ValueError("WIKTIONARY_HEART_LOCAL_RULING_NOT_ACCEPTED")
    print("WIKTIONARY_HEART_LOCAL_RULING_ACCEPTED", flush=True)


def replay():
    freeze()
    staged = read(NOTES / "017-population-stage.json")
    if read(WORK / "017-heart-writer.json")["outcomes"] != {"ASSIGNED": 1}:
        raise ValueError("WIKTIONARY_HEART_LOCAL_RULING_REQUIRED")
    admissions = [read(WORK / ("017-" + name + "-admission.json")) for name in FAMILIES]
    versions = {a["baseline_version"] for a in admissions}
    if len(versions) != 1:
        raise ValueError("WIKTIONARY_TRANSFER_RULE_VERSION_MISMATCH")
    migration = WORK / "017-migration.json"
    if not migration.exists():
        result = migrate_revision(
            TEACHING,
            CANDIDATE,
            {
                "format": FORMAT,
                "baseline_version": next(iter(versions)),
                "admissions": admissions,
                "retirements": [],
                "exceptions": [],
            },
        )
        record(migration, result)
    validation = read(migration)["postflight"]
    count, changes = exact_delta(BASE, CANDIDATE)

    def order(row):
        return row["entry_id"], row["bank"]

    if (
        validation["code"] != "REPLAY_VALIDATED"
        or not validation["complete_search"]
        or validation["entries_mismatched"]
        or validation["entries_validated"] != count
        or sorted(changes, key=order)
        != sorted(
            staged["changes"] + [{"entry_id": HEART, "bank": "WANT", "before": [-1, 0, 1], "after": [0]}], key=order
        )
    ):
        raise ValueError("WIKTIONARY_TRANSFER_REPLAY_DIFFERS_FROM_STAGE")
    benchmark = audit(CANDIDATE, previous.prior.SOURCE_CASES)
    comparison = compare_reports(read(NOTES / "grounded-benchmark.json"), benchmark)
    contrast = audit(CANDIDATE, previous.prior.CONTRAST_CASES)
    if comparison["failures"] or contrast["cases"] != read(NOTES / "grounded-contrasts.json")["cases"]:
        raise ValueError("WIKTIONARY_TRANSFER_RUNTIME_REGRESSION")
    record(NOTES / "017-grounded-benchmark.json", {**benchmark, "comparison": comparison})
    record(NOTES / "017-grounded-contrasts.json", contrast)
    with closing(connect(CANDIDATE)) as conn:
        [domain] = conn.execute(
            "SELECT json_extract(domains,'$.WANT') FROM definition_states WHERE entry_id=?", (HEART,)
        ).fetchone()
    if domain != "[0]":
        raise ValueError("WIKTIONARY_TRANSFER_HEART_LOCAL_RULING_CHANGED")
    record(
        NOTES / "017-verification.json",
        {
            "code": "WIKTIONARY_TRANSFER_REPLAY_VALIDATED",
            "candidate": str(CANDIDATE),
            "candidate_sha256": fingerprint(CANDIDATE),
            "active_pointer_sha256": freeze()["pointer_sha256"],
            "changes": changes,
            "replay": validation,
            "bits_removed": sum(log2(len(r["before"]) / len(r["after"])) for r in changes),
            "sentence_comparison": comparison,
            "local_heart_WANT": [0],
            "rule_projection_cells": len(staged["changes"]),
            "direct_local_cells": 1,
        },
    )
    print("WIKTIONARY_TRANSFER_REPLAY_VALIDATED", len(changes), flush=True)


def publish():
    parent = freeze()
    result = read(NOTES / "017-verification.json")
    if result["code"] != "WIKTIONARY_TRANSFER_REPLAY_VALIDATED" or fingerprint(CANDIDATE) != result["candidate_sha256"]:
        raise ValueError("WIKTIONARY_TRANSFER_CANDIDATE_CHANGED")
    destination = BASE.with_name("sparse-release-017.db")
    gold = read(NOTES / "sparse-release-016-gold.json")
    stage_report = read(NOTES / "017-population-stage.json")
    everyone = {r["entry_id"]: r for group in stage_report["inventory"].values() for r in group}
    selected = {r["entry_id"] for r in stage_report["selected"]} | set().union(*HOLDOUTS.values())
    controls = [
        r["entry_id"]
        for r in everyone.values()
        if r["lemma"] in {"uterus", "humerus", "baroreceptor", "semilunar"} and r["entry_id"] not in selected
    ]
    if len(controls) != 4:
        raise ValueError("WIKTIONARY_TRANSFER_RELEASE_CONTROLS_MISSING")
    gold["records"].extend({"entry_id": entry, "bank": "WANT", "expected": 0} for entry in controls)
    gold["records"].append({"entry_id": HEART, "bank": "WANT", "expected": 0})
    gold_path = NOTES / "sparse-release-017-gold.json"
    record(gold_path, gold)
    runtime = audit_sparse_runtime(CANDIDATE)
    record(NOTES / "017-runtime.json", {k: v for k, v in runtime.items() if k != "measured_at"})
    if runtime["code"] != "SPARSE_RUNTIME_VALIDATED":
        raise ValueError("WIKTIONARY_TRANSFER_RUNTIME_INVALID")
    release = publish_sparse(
        CANDIDATE,
        destination,
        gold_path,
        expected_sha256=result["candidate_sha256"],
        expected_pointer_sha256=result["active_pointer_sha256"],
    )
    record(NOTES / "017-publication.json", release)
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        raise ValueError("WIKTIONARY_TRANSFER_PUBLICATION_BLOCKED")
    n = len(result["changes"])
    if (
        resolve_lexicon_path() != destination
        or Path(release["previous_path"]) != BASE
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"] + n
        or release["cells"]["unresolved"] != parent["cells"]["unresolved"] - n
    ):
        raise ValueError("WIKTIONARY_TRANSFER_ACTIVE_RELEASE_MISMATCH")
    record(
        NOTES / "sparse-release-017-activation.json",
        {
            "code": "ACTIVE_WIKTIONARY_WANT_TRANSFER_VERIFIED",
            "path": str(destination),
            "previous_path": str(BASE),
            "sha256": release["sha256"],
            "pointer_sha256": fingerprint(ACTIVE_POINTER),
            "cells": release["cells"],
            "replay": release["replay"],
            "semantic_outcomes": release["semantic_audit"]["outcomes"],
        },
    )
    print("ACTIVE_WIKTIONARY_WANT_TRANSFER_VERIFIED", release["cells"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage", "teach", "audit", "heart", "replay", "publish"))
    command = parser.parse_args().phase
    {"stage": stage, "teach": teach, "audit": audit_rules, "heart": heart_fill, "replay": replay, "publish": publish}[
        command
    ]()
