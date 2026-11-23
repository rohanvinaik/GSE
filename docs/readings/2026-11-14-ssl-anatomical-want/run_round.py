"""Audit and replay scoped anatomical WANT assignments from sparse release 015."""

import argparse
from contextlib import closing
from importlib import import_module
from math import log2
from pathlib import Path

from GSE.curation.lexicon_builder.completion import _priority_source
from GSE.curation.lexicon_builder.epoch import (
    Family,
    JournaledTransport,
    census,
    choose,
    connect,
    epoch_discovery,
    exact_delta,
    fingerprint,
    forecast,
    read,
    record,
    reviewed_input,
    scope_rows,
    teach,
)
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_admission import admit_records
from GSE.curation.lexicon_builder.rule_migration import migrate_revision
from GSE.curation.lexicon_builder.rule_revisions import FORMAT
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports
from scripts.run_lexicon_epochs import publish_round

prior = import_module("docs.readings.2026-11-14-ssl-incident-accident.verify_and_publish")
NOTES = Path(__file__).resolve().parent
BASE = prior.BASE.with_name("sparse-release-015.db")
WORK = BASE.parent / "ssl-organ-want"
TEACHING = WORK / "teaching.db"
HEART = "wordnet:heart:heart.n.02"
RELEASE_CONTROLS = (
    "wordnet:liver:liver.n.01",
    "wordnet:colon:colon.n.01",
    "wordnet:finger:finger.n.01",
    "wordnet:thigh:thigh.n.01",
)


def family(name, root, excluded, holdouts, statement):
    return Family(
        name,
        ("BODY", 1),
        ("WANT", 0),
        (
            ("pos", "noun"),
            ("wordnet_native_lemma", "true"),
            (f"wordnet_ancestor:{root}", "true"),
            (f"wordnet_other_than_synset:{excluded}", "true"),
        ),
        holdouts,
        {
            "warrant_id": name,
            "review_id": name + "-scope-review",
            "reviewer": "Source-backed construction review",
            "kind": "DEFINITIONAL_DERIVATION",
            "statement": statement,
            "source_refs": [
                str(NOTES / "SOURCE_SCOPE.md"),
                str(NOTES.parent.parent / "program/LEXICON_CONSTRUCTION_DESIGN.md") + "#want-polarity",
            ],
        },
    )


FAMILIES = {
    "internal": family(
        "internal-organ-want",
        "internal_organ.n.01",
        "megacolon.n.01",
        ("wordnet:kidney:kidney.n.01", "wordnet:lung:lung.n.01"),
        "The exact noun definition specifies anatomical structure, bodily location, or physiological function. "
        "Intent and desire are orthogonal to the anatomical criteria. The separately reviewed pathology is reserved.",
    ),
    "external": family(
        "external-anatomical-part-want",
        "external_body_part.n.01",
        "hood.n.10",
        ("wordnet:head:head.n.01", "wordnet:paw:paw.n.01"),
        "The exact noun definition specifies an external body part by physical anatomy or function. "
        "The part's identity is independent of wanting. The alternative genus of a marking is reserved.",
    ),
}


def freeze():
    parent = read(prior.NOTES / "sparse-release-015-activation.json")
    if (
        resolve_lexicon_path() != BASE
        or fingerprint(BASE) != parent["sha256"]
        or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]
    ):
        raise ValueError("ANATOMICAL_WANT_BASELINE_CHANGED")
    return parent


def stage():
    inv = census(BASE, FAMILIES)
    freq_source, frequencies = _priority_source("zipf", None)
    selected = choose(
        BASE, {"external": inv["external"]}, {"external": FAMILIES["external"]}, set(), set(), "zipf", frequencies
    )
    if selected is None or selected["subtlex"] <= 0:
        raise ValueError("ANATOMICAL_WANT_NO_ZIPF_TEACHER")
    rules, rows = scope_rows(BASE, {r["entry_id"]: r for cohort in inv.values() for r in cohort}.values())
    joint = forecast(rows, rules, tuple(f.relation() for f in FAMILIES.values()))
    if (
        joint["contradictions"]
        or any(row["bank"] != "WANT" or row["before"] != [-1, 0, 1] or row["after"] != [0] for row in joint["changes"])
        or not {HEART, selected["entry_id"]} <= {row["entry_id"] for row in joint["changes"]}
    ):
        raise ValueError("ANATOMICAL_WANT_SCOPE_UNSAFE")
    report = {**joint, "inventory": inv, "frequency_source": freq_source, "zipf_selected": selected}
    record(NOTES / "population-stage.json", report)
    return report


def heart_teaching():
    [question] = prior.previous.make_questions(BASE, [(HEART, "WANT")])
    with closing(connect(TEACHING)) as conn:
        receipts = read_model_receipts(conn).get(HEART, ())
    [receipt] = [r for r in receipts if r["request_id"] == question.request_id]
    if receipt["request"] != question.payload() or receipt["assertion"]["value"] != 0:
        raise ValueError("ANATOMICAL_WANT_HEART_UNCONFIRMED")
    return {
        "code": "REVIEWED_TEACHING",
        "request_id": question.request_id,
        "receipt_sha256": prior.previous._request_id(receipt),
    }


def audit_rule(name, selected, taught, transport):
    scope = FAMILIES[name]
    phase = WORK / name
    phase.mkdir(exist_ok=True)
    raw = reviewed_input(TEACHING, scope, selected, taught)
    record(phase / "reviewed-input.json", raw)
    discovery, observed = epoch_discovery(raw, scope, FAMILIES)
    record(phase / "grounded-discovery.json", discovery)
    record(phase / "observed-pair.json", observed)
    journal = JournaledTransport(transport, phase, "audit", len(scope.holdouts), WORK / "model.lock")
    result = run_workflow_input(raw, journal, max_calls=len(scope.holdouts))
    record(phase / "audit.json", result)
    [report] = result["candidates"]
    print(name, report["discovery_outcomes"], report["audit_outcomes"], flush=True)
    admission = admit_records(
        raw,
        result,
        {
            "rule_id": report["relation"]["rule_id"],
            "warrant_sha256": report["warrant_sha256"],
            "review_id": scope.id + "-admission",
            "reviewer": scope.warrant["reviewer"],
            "decision": "APPROVE_DEFINITIONAL_RULE",
            "source_refs": scope.warrant["source_refs"],
            "rationale": scope.warrant["statement"],
        },
    )
    record(phase / "admission.json", admission)
    return admission


def replay(stage_report):
    candidate = WORK / "candidate.db"
    replay_path = WORK / "migration.json"
    admissions = [read(WORK / name / "admission.json") for name in FAMILIES]
    versions = {a["baseline_version"] for a in admissions}
    if len(versions) != 1:
        raise ValueError("ANATOMICAL_WANT_RULE_BASELINE_CHANGED")
    revision = {
        "format": FORMAT,
        "baseline_version": next(iter(versions)),
        "admissions": admissions,
        "retirements": [],
        "exceptions": [],
    }
    if not replay_path.exists():
        record(replay_path, migrate_revision(TEACHING, candidate, revision))
    audit_report = read(replay_path)["postflight"]
    count, changes = exact_delta(BASE, candidate)
    expected = {(row["entry_id"], row["bank"]): row for row in stage_report["changes"]}
    if (
        audit_report["code"] != "REPLAY_VALIDATED"
        or not audit_report["complete_search"]
        or audit_report["entries_mismatched"]
        or audit_report["entries_validated"] != count
        or {(row["entry_id"], row["bank"]): row for row in changes} != expected
    ):
        raise ValueError("ANATOMICAL_WANT_REPLAY_DELTA_CHANGED")
    sentence = audit(candidate, prior.SOURCE_CASES)
    comparison = compare_reports(read(prior.NOTES / "grounded-benchmark.json"), sentence)
    contrast = audit(candidate, prior.CONTRAST_CASES)
    old_contrast = read(prior.NOTES / "grounded-contrasts.json")
    controls = control_domains(candidate)
    if (
        comparison["failures"]
        or contrast["cases"] != old_contrast["cases"]
        or contrast["lexicon_sha256"] != sentence["lexicon_sha256"]
    ):
        raise ValueError("ANATOMICAL_WANT_RUNTIME_REGRESSION")
    record(NOTES / "grounded-benchmark.json", {**sentence, "comparison": comparison})
    record(NOTES / "grounded-contrasts.json", contrast)
    result = {
        "code": "VALIDATED_ANATOMICAL_WANT_CANDIDATE",
        "candidate": str(candidate),
        "candidate_sha256": sentence["lexicon_sha256"],
        "active_pointer_sha256": freeze()["pointer_sha256"],
        "changes": changes,
        "replay": audit_report,
        "controls": controls,
        "bits_removed": sum(log2(len(row["before"]) / len(row["after"])) for row in changes),
        "sentence_comparison": comparison,
    }
    record(NOTES / "verification.json", result)
    print(result["code"], len(changes), flush=True)


def control_domains(candidate):
    identities = (
        "wordnet:heart:heart.n.01",
        "wordnet:heart:heart.n.06",
        "wordnet:megacolon:megacolon.n.01",
        "wordnet:hood:hood.n.10",
        "wordnet:right:right.n.02",
        "wordnet:right:correct.a.01",
    )
    from GSE.api.encoder import GSEEncoder

    with GSEEncoder(candidate) as encoder:
        controls = {entry: encoder.lookup_definition(entry)["selected"]["domains"]["WANT"] for entry in identities}
        defined = {
            entry: encoder.lookup_definition(entry)["selected"]["domains"]["WANT"]
            for entry in (HEART, *RELEASE_CONTROLS)
        }
    if any(domain != [-1, 0, 1] for domain in controls.values()):
        raise ValueError("ANATOMICAL_WANT_CONTROL_CHANGED")
    if any(domain != [0] for domain in defined.values()):
        raise ValueError("ANATOMICAL_WANT_RELEASE_CONTROL_FAILED")
    return {"open": controls, "explicit_zero": defined}


def publish():
    parent = freeze()
    result = read(NOTES / "verification.json")
    if (
        result["code"] != "VALIDATED_ANATOMICAL_WANT_CANDIDATE"
        or fingerprint(Path(result["candidate"])) != result["candidate_sha256"]
    ):
        raise ValueError("ANATOMICAL_WANT_CANDIDATE_CHANGED")
    destination = BASE.with_name("sparse-release-016.db")
    gold = read(prior.previous.PARENT / "sparse-release-013-gold.json")
    known = {(row["entry_id"], row["bank"]) for row in gold["records"]}
    if any((entry, "WANT") in known for entry in RELEASE_CONTROLS):
        raise ValueError("ANATOMICAL_WANT_RELEASE_CONTROL_OVERLAP")
    gold["records"].extend({"entry_id": entry, "bank": "WANT", "expected": 0} for entry in RELEASE_CONTROLS)
    gold_path = NOTES / "sparse-release-016-gold.json"
    record(gold_path, gold)
    release = publish_round(result, WORK, destination, gold_path)
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        record(NOTES / "publication-blocked.json", release)
        raise ValueError("ANATOMICAL_WANT_PUBLICATION_BLOCKED")
    n = len(result["changes"])
    if (
        resolve_lexicon_path() != destination
        or Path(release["previous_path"]) != BASE
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"] + n
        or release["cells"]["unresolved"] != parent["cells"]["unresolved"] - n
        or release["semantic_audit"]["outcomes"]["IDENTIFIED_CORRECT"] != len(gold["records"])
    ):
        raise ValueError("ANATOMICAL_WANT_RELEASE_MISMATCH")
    record(
        NOTES / "sparse-release-016-activation.json",
        {
            "code": "ACTIVE_SSL_ANATOMICAL_WANT_VERIFIED",
            "path": str(destination),
            "previous_path": str(BASE),
            "sha256": release["sha256"],
            "pointer_sha256": fingerprint(ACTIVE_POINTER),
            "cells": release["cells"],
            "semantic_outcomes": release["semantic_audit"]["outcomes"],
            "replay": release["replay"],
        },
    )
    print("ACTIVE_SSL_ANATOMICAL_WANT_VERIFIED", release["cells"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage", "internal", "external", "replay", "publish"))
    args = parser.parse_args()
    freeze()
    if args.phase == "stage":
        report = stage()
        print(report["zipf_selected"]["entry_id"], len(report["changes"]), flush=True)
    elif args.phase == "publish":
        publish()
    elif args.phase == "replay":
        replay(read(NOTES / "population-stage.json"))
    else:
        transport = prior.previous.model()
        name = args.phase
        if name == "internal":
            selected = {"entry_id": HEART, "bank": "WANT"}
            taught = heart_teaching()
        else:
            selected = read(NOTES / "population-stage.json")["zipf_selected"]
            directory = WORK / name
            directory.mkdir(exist_ok=True)
            j = JournaledTransport(transport, directory, "teach", 1, WORK / "model.lock")
            taught = teach(BASE, TEACHING, selected, FAMILIES[name], j, directory)
            if taught["code"] != "REVIEWED_TEACHING":
                raise ValueError(taught["code"])
        audit_rule(name, selected, taught, transport)


if __name__ == "__main__":
    main()
