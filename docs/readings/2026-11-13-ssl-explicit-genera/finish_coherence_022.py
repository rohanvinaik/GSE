"""Validate, publish and retain one rollback for the pinned literal-genus round."""

import argparse
import fcntl
import importlib
import json
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from math import log2
from pathlib import Path
from typing import TypedDict

from gse.api.encoder import GSEEncoder
from gse.curation.lexicon_builder.epoch import _resolve, exact_delta, fingerprint, read, record, scope_rows
from gse.curation.lexicon_builder.retention import retire_snapshot
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports
from scripts.run_lexicon_epochs import publish_round

round_ = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.coherence_022")
prior = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.coherence_020")
handles = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.finish_coherence_020")
stative = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.stative_transfer")
state_corpus = importlib.import_module("docs.readings.2026-11-13-ssl-explicit-genera.state_corpus")
NOTES, BASE, WORK = round_.NOTES, round_.BASE, round_.WORK
DESTINATION = BASE.with_name("sparse-release-022.db")
PAPER = Path("/Users/rohanvinaik/Projects/rohan-vinaik.github.io/papers/Core Documents/"
             "Semantic_Specification_Learning/07_GSE_LEXICON_NSM_WORKING_DRAFT.md")


class Control(TypedDict):
    entry_id: str
    bank: str
    expected: int


def status(code, **details):
    document = {"code": code, "observed_at_utc": datetime.now(timezone.utc).isoformat(), **details}
    path = NOTES / "022-publication-status.json"
    with tempfile.NamedTemporaryFile(mode="w", dir=NOTES, delete=False) as stream:
        json.dump(document, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        temporary = Path(stream.name)
    temporary.replace(path)
    print(code, flush=True)


def verify_sources():
    for name in ("022-implementation-verification.json", "022-release-verification.json"):
        for path, expected in read(NOTES / name)["source_sha256"].items():
            if fingerprint(round_.ROOT / path) != expected:
                raise ValueError("LITERAL_GENUS_FROZEN_SOURCE_CHANGED:" + path)


def verify_candidate(result):
    verify_sources()
    plan = read(NOTES / "022-coherence-plan.json")
    if (len(result["epochs"]) != plan["epochs"] or result["typed_questions_used"] != 8
            or result["reopened_cells"] or result["replay"]["code"] != "REPLAY_VALIDATED"
            or not result["replay"]["complete_search"]
            or any(e["code"] != "RULE_ADMITTED" or e["audit_outcomes"] != {"MODEL_AGREEMENT": 3}
                   for e in result["epochs"])):
        raise ValueError("LITERAL_GENUS_COMPLETE_TEACHING_AND_AUDIT_REQUIRED")
    candidate = Path(result["candidate"])
    if fingerprint(candidate) != result["candidate_sha256"]:
        raise ValueError("LITERAL_GENUS_CANDIDATE_CHANGED")
    stage = read(NOTES / "022-population-stage.json")
    expected = {(r["entry_id"], r["bank"]): (r["before"], r["after"]) for r in stage["changes"]}
    count, changes = exact_delta(BASE, candidate)
    observed = {(r["entry_id"], r["bank"]): (r["before"], r["after"]) for r in changes}
    if count != 401596 or expected != observed or len(changes) != result["new_cells"]:
        raise ValueError("LITERAL_GENUS_DELTA_DIFFERS_FROM_FULL_STAGE")
    if any(bank not in {"WHEN", "PEOPLE"} or before != [-1, 0, 1] or after != [1]
           for (_, bank), (before, after) in observed.items()):
        raise ValueError("LITERAL_GENUS_UNEXPECTED_KNOWN_OR_OTHER_BANK_CHANGE")
    controls: list[Control] = []
    families = {f["id"]: f for f in plan["families"]}
    for epoch in result["epochs"]:
        selected = epoch["selected"]
        family = families[selected["family"]]
        controls.extend({"entry_id": entry, "bank": selected["bank"], "expected": 1}
                        for entry in (selected["entry_id"], *family["holdouts"]))
    with GSEEncoder(candidate) as encoder:
        for control in controls:
            row = encoder.lookup_definition(control["entry_id"])["selected"]
            if row["domains"][control["bank"]] != [1]:
                raise ValueError("LITERAL_GENUS_EXACT_CONSUMER_FAILED:" + control["entry_id"])
            encoder.encode_definition(control["entry_id"])
    inventory = read(WORK / "inventory.json")
    scoped = {r["entry_id"]: r for group in inventory.values() for r in group}
    before_rules, before_rows = scope_rows(BASE, scoped.values())
    after_rules, after_rows = scope_rows(candidate, scoped.values())
    factor, support = Fraction(1), []
    for identity, row in sorted(before_rows.items()):
        before = prior.support_count(_resolve(row, before_rules))
        after = prior.support_count(_resolve(after_rows[identity], after_rules))
        if after > before:
            raise ValueError("LITERAL_GENUS_SUPPORT_EXPANDED:" + identity)
        ratio = Fraction(before, after)
        factor *= ratio
        if ratio != 1:
            support.append({"entry_id": identity, "before": before, "after": after, "ratio": str(ratio)})
    joint = {"code": "COMPLETE_SCOPED_JOINT_SUPPORT_REPLAY_VALIDATED", "scope_definitions": len(scoped),
             "records": support, "ratio_frequency": dict(Counter(r["ratio"] for r in support)),
             "reduction_bits": log2(factor.numerator) - log2(factor.denominator),
             "ratio_numerator": factor.numerator, "ratio_denominator": factor.denominator}
    record(NOTES / "022-joint-support.json", joint)
    comparisons = {}
    for name, cases in (
        ("sentences", stative.previous.anatomy.previous.prior.SOURCE_CASES),
        ("contrasts", stative.previous.anatomy.previous.prior.CONTRAST_CASES),
        ("states", NOTES / "018-stative-diagnostic-cases.json"),
    ):
        report = audit(candidate, cases)
        comparison = compare_reports(read(NOTES / f"021-approved-candidate-{name}.json"), report)
        record(NOTES / f"022-candidate-{name}.json", {**report, "comparison": comparison})
        if comparison["failures"]:
            raise ValueError("LITERAL_GENUS_BENCHMARK_REGRESSION:" + name)
        comparisons[name] = comparison
    corpus = state_corpus.audit(candidate)
    old = {(r["entry_id"], r["style"]): r for r in read(NOTES / "021-approved-candidate-state-corpus.json")["results"]}
    regressions = [r for r in corpus["results"] if old[(r["entry_id"], r["style"])]["code"] == "IDENTIFIED_CORRECT"
                   and r["code"] != "IDENTIFIED_CORRECT"]
    if corpus["code"] != "STATE_CORPUS_GROUNDING_VALIDATED" or regressions:
        raise ValueError("LITERAL_GENUS_STATE_CORPUS_REGRESSION")
    record(NOTES / "022-candidate-state-corpus.json", corpus)
    gold = read(NOTES / "sparse-release-021-gold.json")
    gold["records"].extend(controls)
    record(NOTES / "sparse-release-022-gold.json", gold)
    verified = {"code": "LITERAL_GENUS_CANDIDATE_VALIDATED", "candidate": str(candidate),
                "candidate_sha256": result["candidate_sha256"], "new_cells": result["new_cells"],
                "baseline": str(BASE), "benchmark_comparisons": comparisons,
                "state_corpus_outcomes": dict(Counter(r["code"] for r in corpus["results"])),
                "joint_support_reduction_bits": joint["reduction_bits"], "semantic_controls": len(gold["records"]),
                "controls": controls}
    record(NOTES / "022-verification.json", verified)
    return verified


def retire_work(result, release):
    extra = tuple(r["record_id"] for r in read(NOTES / "021-approved-source-context.json")["observations"])
    files = [("020", BASE.with_name("sparse-release-020.db"))]
    files.extend((f"epoch-{e['epoch']:02d}-" + Path(name).stem, WORK / f"zipf/epoch-{e['epoch']:02d}" / name)
                 for e in result["epochs"] for name in ("teaching.db", "candidate.db"))
    retired = []
    for label, path in files:
        retired.append(retire_snapshot(
            path, DESTINATION, BASE, expected_sha256=release["sha256"],
            previous_sha256=read(NOTES / "022-coherence-plan.json")["baseline_sha256"],
            archive_path=BASE.parent / "ssl-explicit-genera/retired-audit" / ("022-" + label + ".json.gz"),
            receipt_path=NOTES / ("022-retirement-" + label + ".json"),
            handle_check=handles.no_open_handles, new_context_ids=extra,
        ))
    receipt = {"code": "ACTIVE_022_ROLLBACK_021_AND_AUDITS_RETAINED", "retired": retired}
    record(NOTES / "022-retention.json", receipt)
    return receipt


def notebook(result, release, verified):
    old = PAPER.read_text()
    receipt_path = NOTES / "022-notebook-update.json"
    if receipt_path.exists():
        if (read(receipt_path)["code"] != "LIVING_DRAFT_UPDATED_WITH_VALIDATED_022"
                or "Sparse release 022 activated after" not in old):
            raise ValueError("LITERAL_GENUS_NOTEBOOK_RECEIPT_MISMATCH")
        return
    marker = "#### Person reference as the next broad exclusion mechanism"
    paragraph = (
        f"The completed cycle admitted both rules using {result['typed_questions_used']} typed questions. "
        f"Its exact full-cohort comparison found {result['new_cells']:,} new assignments and "
        f"{result['reopened_cells']} reopenings. Complete replay checked {result['replay']['entries_checked']:,} records "
        f"with {result['replay']['entries_mismatched']} mismatches. The measured scoped joint-support contraction is "
        f"{verified['joint_support_reduction_bits']:.6f} bits. This is a finite constraint-model measurement; "
        "the round supplies no cross-epoch exponential rate or equal-budget scheduling comparison.\n\n"
        f"Sparse release 022 activated after the runtime gate, cumulative {verified['semantic_controls']} supplied "
        "semantic controls, sentence/ambiguity/state diagnostics and isolated publication replay passed. "
        f"It contains {release['cells']['assigned']:,} assigned cells, including "
        f"{release['cells']['explicit_zero']:,} explicit zeros, and {release['cells']['unresolved']:,} unresolved cells. "
        "The semantic controls include the new teaching/audit expectations and are not independent labels for "
        "the unlabelled corpus. The default encoder compiled the new controls. Active 022 and rollback 021 are "
        "retained; older and working databases were retired only after preserving source streams and unique audit rows. "
        "The added retention path requires a named positive open-handle check and supports resumption after unlink "
        "through an immutable verified intent.\n\n"
        "[Completed round](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/022-verification.json) · "
        "[Publication](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/022-publication.json) · "
        "[Retention](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/022-retention.json)\n\n"
    )
    if "Sparse release 022 activated after" in old or old.count(marker) != 1:
        raise ValueError("LITERAL_GENUS_NOTEBOOK_SECTION_CHANGED")
    PAPER.write_text(old.replace(marker, paragraph + marker))
    record(NOTES / "022-notebook-update.json", {"code": "LIVING_DRAFT_UPDATED_WITH_VALIDATED_022",
                                                "path": str(PAPER), "sha256": fingerprint(PAPER)})


def obtain_release(result):
    if resolve_lexicon_path() == DESTINATION:
        release = read(NOTES / "022-publication.json")
        verified = read(NOTES / "022-verification.json")
        if (release["path"] != str(DESTINATION) or fingerprint(DESTINATION) != release["sha256"]
                or verified["candidate_sha256"] != release["sha256"]
                or fingerprint(BASE) != read(NOTES / "022-coherence-plan.json")["baseline_sha256"]):
            raise ValueError("LITERAL_GENUS_ACTIVE_RELEASE_RECOVERY_MISMATCH")
        return verified, release
    verified = verify_candidate(result)
    verify_sources()
    publication = WORK / "publication"
    publication.mkdir(exist_ok=True)
    release = publish_round(result, publication, DESTINATION, NOTES / "sparse-release-022-gold.json")
    record(NOTES / "022-publication.json", release)
    return verified, release


def run(wait=False):
    verify_sources()
    path = WORK / "zipf/arm-result.json"
    if wait:
        status("WAITING_FOR_PINNED_LITERAL_GENUS_REPLAY", activation_performed=False)
        seen = False
        with (WORK / "zipf.lock").open() as lock:
            while not path.exists():
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    seen = True
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    if seen:
                        raise ValueError("LITERAL_GENUS_PRODUCER_EXITED_WITHOUT_RESULT")
                time.sleep(10)
    result = read(path)
    status("VERIFYING_LITERAL_GENUS_CANDIDATE", activation_performed=False)
    verified, release = obtain_release(result)
    if (release["code"] != "PUBLISHED_SPARSE_LEXICON" or resolve_lexicon_path() != DESTINATION
            or Path(release["previous_path"]) != BASE):
        raise ValueError("LITERAL_GENUS_PUBLICATION_NOT_VERIFIED")
    before = read(NOTES / "sparse-release-021-activation.json")["cells"]
    if (release["cells"]["assigned"] != before["assigned"] + result["new_cells"]
            or release["cells"]["explicit_zero"] != before["explicit_zero"]):
        raise ValueError("LITERAL_GENUS_PUBLICATION_COUNTS_MISMATCH")
    checks = []
    with GSEEncoder() as encoder:
        if encoder.db_path != DESTINATION:
            raise ValueError("LITERAL_GENUS_DEFAULT_ENCODER_NOT_ACTIVE")
        for control in verified["controls"]:
            domain = encoder.lookup_definition(control["entry_id"])["selected"]["domains"][control["bank"]]
            if domain != [1]:
                raise ValueError("LITERAL_GENUS_DEFAULT_CONSUMER_FAILED:" + control["entry_id"])
            encoder.encode_definition(control["entry_id"])
            checks.append({**control, "compiled": True})
    record(NOTES / "sparse-release-022-activation.json", {
        "code": "ACTIVE_LITERAL_GENUS_022_VERIFIED", "path": str(DESTINATION), "previous_path": str(BASE),
        "sha256": release["sha256"], "pointer_sha256": fingerprint(ACTIVE_POINTER), "cells": release["cells"],
        "replay": release["replay"], "semantic_outcomes": release["semantic_audit"]["outcomes"],
        "fresh_default_consumer": checks,
    })
    retire_work(result, release)
    notebook(result, release, verified)
    status("PUBLISHED_AND_ROLLING_RETENTION_VERIFIED", activation_performed=True, active_path=str(DESTINATION),
           previous_path=str(BASE), new_cells=result["new_cells"], typed_questions_used=result["typed_questions_used"],
           joint_support_reduction_bits=verified["joint_support_reduction_bits"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait", action="store_true")
    try:
        run(parser.parse_args().wait)
    except Exception as error:
        status("LITERAL_GENUS_FINALIZATION_STOPPED", reason=str(error),
               activation_performed=resolve_lexicon_path() == DESTINATION)
        raise
