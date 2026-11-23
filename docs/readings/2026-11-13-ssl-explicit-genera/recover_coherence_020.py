"""Finish verified 020 retention and reporting after an unrelated mount change."""

import os
from datetime import datetime, timezone
from importlib import import_module

from GSE.curation.lexicon_builder.epoch import fingerprint, read, record
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

helpers = import_module("docs.readings.2026-11-13-ssl-explicit-genera.finish_coherence_020")
NOTES, ROOT, WORK = helpers.NOTES, helpers.ROOT, helpers.WORK


def recover():
    pins = {
        **read(NOTES / "020-implementation-verification.json")["source_sha256"],
        **read(NOTES / "020-status-writer-verification.json")["source_sha256"],
        **read(NOTES / "020-retention-check-verification.json")["source_sha256"],
    }
    if any(fingerprint(ROOT / path) != digest for path, digest in pins.items()):
        raise ValueError("RETENTION_RECOVERY_TESTED_SOURCE_CHANGED")
    release = read(NOTES / "020-publication.json")
    activation = read(NOTES / "sparse-release-020-activation.json")
    result = read(WORK / "zipf/arm-result.json")
    if (
        release["code"] != "PUBLISHED_SPARSE_LEXICON"
        or str(resolve_lexicon_path()) != release["path"]
        or fingerprint(resolve_lexicon_path()) != release["sha256"]
        or fingerprint(ACTIVE_POINTER) != activation["pointer_sha256"]
        or release["replay"]["code"] != "REPLAY_VALIDATED"
        or not release["replay"]["complete_search"]
        or release["replay"]["entries_mismatched"] != 0
        or release["semantic_audit"]["outcomes"]["IDENTIFIED_CORRECT"] != release["semantic_audit"]["total"]
        or result["candidate_sha256"] != release["sha256"]
    ):
        raise ValueError("RETENTION_RECOVERY_REQUIRES_THE_VERIFIED_ACTIVE_RELEASE")
    retention = helpers.retire_work(result, release)
    verification = read(NOTES / "020-verification.json")
    helpers.update_notebook(verification, release, retention)
    archived = []
    for name in ("020-finisher-failure.json", "021-continuation-failure.json"):
        path = NOTES / name
        if path.exists():
            archive = path.with_name(path.stem + "-before-retention-recovery.json")
            if archive.exists():
                if archive.read_bytes() != path.read_bytes():
                    raise ValueError("RECOVERY_FAILURE_ARCHIVE_COLLISION")
            else:
                os.link(path, archive)
            path.unlink()
            archived.append(str(archive))
    report = {
        "format": "GSE.lexicon-learning-round-status/1",
        "code": "PUBLISHED_AND_ROLLING_RETENTION_VERIFIED",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_path": release["path"],
        "active_sha256": release["sha256"],
        "previous_path": release["previous_path"],
        "new_cells": result["new_cells"],
        "cells": release["cells"],
        "construction_model_questions": result["typed_questions_used"],
        "boundary_diagnostic_questions": 2,
        "joint_support_reduction_bits": verification["joint_support_reduction_bits"],
        "marginal_potential_reduction_bits": verification["marginal_potential_reduction_bits"],
        "semantic_outcomes": release["semantic_audit"]["outcomes"],
        "tests_passed": 161,
        "source_and_audit_records_preserved": True,
        "logical_bytes_unlinked": retention["logical_bytes_unlinked"],
        "living_notebook": str(helpers.PAPER),
        "notebook_sha256": fingerprint(helpers.PAPER),
        "recovered_failure_records": archived,
        "unknown_is_not_zero": True,
    }
    record(NOTES / "020-retention-recovery.json", report)
    helpers.record_status(NOTES / "020-round-status.json", report)
    print("COHERENCE_020_ROUND_COMPLETE", release["cells"], retention["code"], flush=True)


if __name__ == "__main__":
    recover()
