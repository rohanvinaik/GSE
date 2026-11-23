"""Verify the one-cell sparse successor and benchmark before atomic publication."""

from importlib import import_module
from pathlib import Path

from gse.curation.lexicon_builder.epoch import exact_delta, fingerprint, read, record
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports
from scripts.run_lexicon_epochs import publish_round

previous = import_module("docs.readings.2026-11-13-ssl-grounded-event-action.run_round")
NOTES = Path(__file__).resolve().parent
BASE = previous.WORK.parent / "sparse-release-014.db"
WORK = BASE.parent / "ssl-incident-accident"
ENTRY = "wordnet:accident:accident.n.02"
EXPECTED_DELTA = [{"entry_id": ENTRY, "bank": "HAPPEN", "before": [-1, 0, 1], "after": [1]}]
SOURCE_CASES = previous.GROUNDING / "sentences-corrected.json"
CONTRAST_CASES = NOTES / "sense-contrasts.json"
UNRESOLVED = {"unexpected-incident", "unplanned-accident"}


def main():
    parent = read(previous.NOTES / "sparse-release-014-activation.json")
    if (
        resolve_lexicon_path() != BASE
        or fingerprint(BASE) != parent["sha256"]
        or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]
    ):
        raise ValueError("ACCIDENT_ROUND_BASELINE_CHANGED")
    writer = read(WORK / "typed-writer.json")
    if (
        writer["code"] != "SELECTED_SCOPE_RESOLVED"
        or writer["preflight"] != "REPLAY_VALIDATED"
        or writer["selected_entry_ids"] != [ENTRY]
        or writer["banks"] != ["HAPPEN"]
        or writer["outcomes"] != {"ASSIGNED": 1}
    ):
        raise ValueError("ACCIDENT_ROUND_TYPED_AUDIT_UNCONFIRMED")
    candidate = WORK / "candidate.db"
    count, delta = exact_delta(BASE, candidate)
    if count != parent["records_replayed"] or delta != EXPECTED_DELTA:
        raise ValueError("ACCIDENT_ROUND_UNEXPECTED_BANK_DELTA")
    main_report = audit(candidate, SOURCE_CASES)
    comparison = compare_reports(read(previous.NOTES / "candidate-sentences.json"), main_report)
    if comparison["failures"]:
        raise ValueError("ACCIDENT_ROUND_SENTENCE_REGRESSION")
    original_targets = {row["id"]: row for row in main_report["cases"] if row["id"] in UNRESOLVED}
    if original_targets.keys() != UNRESOLVED or any(
        row["sense_outcome"] != "ABSTAINED"
        or row["banks"]["HAPPEN"]["runtime"] != "BLOCKED_BY_SENSE"
        or row["banks"]["HAPPEN"]["exact_sense"] != "CORRECT"
        for row in original_targets.values()
    ):
        raise ValueError("ACCIDENT_ROUND_AMBIGUITY_CONTROL_FAILED")
    contrast = audit(candidate, CONTRAST_CASES)
    if any(
        row["sense_outcome"] != ("ABSTAINED_AS_EXPECTED" if row["sense"] is None else "CORRECT")
        or any(
            cell["runtime"] != ("CORRECT" if cell["expected"] is not None else "OPEN_AS_EXPECTED")
            for cell in row["banks"].values()
        )
        for row in contrast["cases"]
    ):
        raise ValueError("ACCIDENT_ROUND_SENSE_CONTRAST_FAILED")
    record(NOTES / "grounded-benchmark.json", {**main_report, "comparison": comparison})
    record(NOTES / "grounded-contrasts.json", contrast)
    result = {
        "candidate": str(candidate),
        "candidate_sha256": main_report["lexicon_sha256"],
        "active_pointer_sha256": parent["pointer_sha256"],
        "changes": delta,
    }
    if contrast["lexicon_sha256"] != result["candidate_sha256"]:
        raise ValueError("ACCIDENT_ROUND_CANDIDATE_CHANGED")
    print("BENCHMARKS_VALIDATED", count, delta, flush=True)
    destination = BASE.with_name("sparse-release-015.db")
    release = publish_round(result, WORK, destination, previous.PARENT / "sparse-release-013-gold.json")
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        record(NOTES / "publication-blocked.json", release)
        raise ValueError("ACCIDENT_ROUND_PUBLICATION_BLOCKED")
    if (
        resolve_lexicon_path() != destination
        or Path(release["previous_path"]) != BASE
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"]
        or release["replay"]["entries_validated"] != count
    ):
        raise ValueError("ACCIDENT_ROUND_RELEASE_MISMATCH")
    record(
        NOTES / "sparse-release-015-activation.json",
        {
            "code": "ACTIVE_SSL_INCIDENT_ACCIDENT_VERIFIED",
            "path": str(destination),
            "previous_path": str(BASE),
            "sha256": release["sha256"],
            "pointer_sha256": fingerprint(ACTIVE_POINTER),
            "cells": release["cells"],
            "replay": release["replay"],
            "semantic_outcomes": release["semantic_audit"]["outcomes"],
            "changes": delta,
            "sentence_comparison": comparison,
        },
    )
    print("ACTIVE_SSL_INCIDENT_ACCIDENT_VERIFIED", release["cells"], flush=True)


if __name__ == "__main__":
    main()
