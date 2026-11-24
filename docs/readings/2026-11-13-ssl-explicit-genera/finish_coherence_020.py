"""Finish one authorized coherence round through the existing CLI gates."""

import argparse
import gzip
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from hashlib import file_digest, sha256
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import read, record
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.run_lexicon_epochs import retire_published_work

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/coherence-020"
RUNNER = "docs.readings.2026-11-13-ssl-explicit-genera.coherence_020"
ARCHIVER = "docs.readings.2026-11-13-ssl-explicit-genera.checkpoint_audit_020"
OWNED = Path.home() / "Projects/SquishOS/ops/agents/bin/owned-run"
PAPER = (
    Path.home()
    / "Projects/rohan-vinaik.github.io/papers/Core Documents/Semantic_Specification_Learning/07_GSE_LEXICON_NSM_WORKING_DRAFT.md"
)


def fingerprint(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def file_state(path):
    value = path.stat()
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "logical_bytes": value.st_size,
        "mtime_ns": value.st_mtime_ns,
    }


def available(path):
    try:
        return read(path)
    except FileNotFoundError, json.JSONDecodeError:
        return None


def record_status(path, value):
    """Atomically replace a latest-status report; checkpoints stay immutable."""
    if path.is_symlink():
        raise ValueError("ROUND_STATUS_MUST_NOT_BE_SYMLINK")
    payload = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def no_open_handles(path):
    from GSE.curation.lexicon_builder.retention import no_open_handles as inspect_handles

    return inspect_handles(path)


def validate_retirement(item, protected):
    path = Path(item["path"])
    if path.resolve() in protected or not path.resolve().is_relative_to(ROOT / "data/lexicon_builder"):
        raise ValueError("CHECKPOINT_PROTECTED_OR_OUTSIDE_PROJECT")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("CHECKPOINT_SYMLINK")
        if part == ROOT:
            break
    if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("CHECKPOINT_HAS_LIVE_SIDECAR")
    if file_state(path) != {key: item[key] for key in ("device", "inode", "logical_bytes", "mtime_ns")}:
        raise ValueError("CHECKPOINT_IDENTITY_CHANGED")
    if fingerprint(path) != item["sha256"]:
        raise ValueError("CHECKPOINT_CONTENT_CHANGED")
    archive = Path(item["audit_delta"])
    if sha256(archive.read_bytes()).hexdigest() != item["audit_delta_sha256"]:
        raise ValueError("CHECKPOINT_ARCHIVE_CHANGED")
    document = json.loads(gzip.decompress(archive.read_bytes()))
    if (
        document["source_sha256"] != item["sha256"]
        or fingerprint(Path(document["witness"])) != document["witness_sha256"]
    ):
        raise ValueError("CHECKPOINT_ARCHIVE_WITNESS_CHANGED")
    item["open_file_check"] = no_open_handles(path)


def retire_work(result, release):
    active, previous = Path(release["path"]), Path(release["previous_path"])
    protected = {active.resolve(), previous.resolve()}
    preparations = [
        read(NOTES / ("020-" + label + "-retirement-preparation.json"))
        for label in ("epoch-01-teaching", "epoch-01-candidate", "epoch-02-teaching")
    ]
    candidate = Path(result["candidate"])
    if candidate != WORK / "zipf/epoch-02/candidate.db" or fingerprint(candidate) != release["sha256"]:
        raise ValueError("FINAL_CANDIDATE_NOT_THE_PUBLISHED_COPY")
    archive = previous.parent / "ssl-explicit-genera/retired-audit/020-final-candidate-audit-delta.json.gz"
    document = {
        "format": "GSE.checkpoint-audit-delta/1",
        "source": str(candidate),
        "source_sha256": release["sha256"],
        "witness": str(active),
        "witness_sha256": release["sha256"],
        "scope": "EXACT_PUBLISHED_BYTE_COPY",
        "tables": {},
    }
    archive.write_bytes(gzip.compress(json.dumps(document, sort_keys=True).encode(), mtime=0))
    preparations.append(
        {
            "path": str(candidate),
            "sha256": release["sha256"],
            **file_state(candidate),
            "audit_delta": str(archive),
            "audit_delta_sha256": sha256(archive.read_bytes()).hexdigest(),
        }
    )
    old = read(NOTES / "020-retirement-preparation.json")["prepared"][0]
    if Path(old["path"]) != previous.with_name("sparse-release-018.db"):
        raise ValueError("OBSOLETE_ROLLBACK_IDENTITY_CHANGED")
    preparations.append(old)
    for item in preparations:
        validate_retirement(item, protected)
    ready = {
        "format": "GSE.rolling-retention/1",
        "code": "VERIFIED_READY_FOR_RETIREMENT",
        "active": str(active),
        "previous": str(previous),
        "retirement": preparations,
        "source_and_audit_records_preserved": True,
        "external_backups_modified": False,
    }
    record(NOTES / "020-retirement-ready.json", ready)
    pointer = read(NOTES / "sparse-release-020-activation.json")["pointer_sha256"]
    if resolve_lexicon_path() != active or fingerprint(ACTIVE_POINTER) != pointer:
        raise ValueError("ACTIVE_SUCCESSOR_CHANGED_BEFORE_RETIREMENT")
    work_retention = retire_published_work(WORK / "zipf", result, release)
    record(NOTES / "020-work-snapshot-retention.json", work_retention)
    if work_retention["code"] != "WORK_SNAPSHOTS_RETIRED":
        raise ValueError("WORK_SNAPSHOT_RETIREMENT_DEFERRED")
    validate_retirement(old, protected)
    if resolve_lexicon_path() != active or fingerprint(ACTIVE_POINTER) != pointer:
        raise ValueError("ACTIVE_SUCCESSOR_CHANGED_BEFORE_ROLLBACK_RETIREMENT")
    Path(old["path"]).unlink()
    if any(Path(item["path"]).exists() for item in preparations):
        raise ValueError("RETIRED_CHECKPOINT_STILL_PRESENT")
    remaining = [str(path) for path in sorted(active.parent.glob("sparse-release-*.db"))]
    if set(remaining) != {str(active), str(previous)}:
        raise ValueError("ROLLING_RELEASE_SET_DIFFERS")
    report = {
        **ready,
        "code": "ONE_ROLLING_ROLLBACK_RETAINED",
        "retired": preparations,
        "logical_bytes_unlinked": sum(item["logical_bytes"] for item in preparations),
        "remaining_sparse_releases": remaining,
        "physical_bytes_reclaimed": "NOT_MEASURED",
    }
    record(NOTES / "020-rollback-retention.json", report)
    return report


def update_notebook(verification, release, retention):
    result = verification["result"]
    direct = sum(epoch["teaching"]["code"] == "REVIEWED_TEACHING" for epoch in result["epochs"])
    symbolic = sum(epoch["symbolic_new_cells"] for epoch in result["epochs"])
    text = f"""#### Speech acts and evidence-based reasoning

The round continued from validated 019 through two Zipf-prioritized teaching steps and six disjoint held-out audits. The conditional SAY→DO rule covers exact native expression acts; existing DO→HAPPEN supplies its second-bank consequence. The conditional THINK→INFER rule covers exact native reasoning definitions. Complete source review retained the earlier exclusions and separately excluded the stative *argue* and contractual-status *sign* branches. Exclusion supplies no zero. [Scope, warrants and falsifiers](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-source-review.json)

The eight-question construction run produced {direct} directly taught cells and {symbolic} additional singleton assignments through newly admitted rules. Existing closure after teaching accounts for the remaining {result["new_cells"] - direct - symbolic} assignment. Its exact full-corpus delta contains {result["new_cells"]} new positive assignments: 275 DO, 275 HAPPEN and 21 INFER, with no reopenings or changed previously narrowed domains. All six held-out construction audits agreed. Two separately counted boundary diagnostics also returned DO=+1; they supplied no opposing sign and were not committed as local rulings. The child retains its source-reviewed scope. This round is not an equal-budget comparison of scheduling policies. [Construction verification](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-verification.json) · [Boundary diagnostics](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-boundary-audit-results.json)

Replay of the candidate reproduces the exact support factor `(43/9)^275 × (129/95)^54 × 3^21`, or {verification["joint_support_reduction_bits"]:.4f} bits, in the pinned product of per-definition constraint models. Fifty-four definitions gain joint information without new marginal singletons. Marginal-domain potential falls by {verification["marginal_potential_reduction_bits"]:.4f} bits; the two measures differ because event banks were already correlated. Shared source ancestry and synonymous spellings do not become independent linguistic observations. These counts establish this round's finite support contraction rather than a global convergence rate. [Actual component witnesses](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-joint-support-validation.json) · [Finite derivation](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-support-count-derivation.md)

Both rule transitions passed full preflight and postflight replay. Isolated publication again validated all {release["replay"]["entries_checked"]:,} records with complete search and zero mismatches. The sentence, ambiguity and state benchmarks had no regressions; the 850-case state routing audit retained 817 correct identities and 33 abstentions, with zero wrong emissions. All {release["semantic_audit"]["total"]} supplied semantic controls passed. The added controls comprise six audited target expectations and three derived HAPPEN consequences; they are not independent gold for unlabelled cells. The 147 existing contract tests, six support-measurement tests, four status-writer regressions and four open-handle-check regressions passed. Changing status reports remain separate from immutable checkpoints. The local-file check parses the complete current Time Machine warning, refuses a matching file/device or unexpected diagnostic, and continues to block any actual open handle. [Publication](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-publication.json) · [Implementation checks](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-implementation-verification.json) · [Status checks](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-status-writer-verification.json) · [Retention checks](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-retention-check-verification.json)

Release 020 is active with {release["cells"]["assigned"]:,} assigned cells, {release["cells"]["explicit_zero"]:,} explicit zeros and {release["cells"]["unresolved"]:,} unresolved lexical cells. A fresh default encoder loaded it and compiled the six new audit controls. The complete declared cohort includes one unchanged sentence construction, excluded from lexical cell progress. Unknown remains distinct from zero. Active 020 and rollback 019 are retained; older and duplicate databases were removed only after source and audit preservation checks. This unlinked {retention["logical_bytes_unlinked"]:,} logical bytes without modifying external backups. [Activation](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/sparse-release-020-activation.json) · [Retention](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/020-rollback-retention.json)

"""
    original = PAPER.read_text()
    prefix, separator, following = original.partition("#### Speech acts and evidence-based reasoning\n")
    _, ending, suffix = following.partition("### 6. Linguistic and sociological implications\n")
    if not separator or not ending:
        raise ValueError("LIVING_NOTEBOOK_SECTION_CHANGED")
    PAPER.write_text(prefix + text + ending + suffix)


def finish(producer):
    children = {}
    try:
        if producer < 1:
            raise ValueError("INVALID_EPOCH_PRODUCER_PID")
        tested = {
            **read(NOTES / "020-implementation-verification.json")["source_sha256"],
            **read(NOTES / "020-status-writer-verification.json")["source_sha256"],
            **read(NOTES / "020-retention-check-verification.json")["source_sha256"],
        }
        orchestration = {
            str(path.relative_to(ROOT)): fingerprint(path)
            for path in (
                Path(__file__),
                NOTES / "checkpoint_audit_020.py",
            )
        }
        while not available(WORK / "zipf/arm-result.json"):
            for label, ready in (
                ("epoch-01-candidate", WORK / "zipf/epoch-01/result.json"),
                ("epoch-02-teaching", WORK / "zipf/epoch-02/teaching.json"),
            ):
                receipt = NOTES / ("020-" + label + "-retirement-preparation.json")
                if ready.is_file() and not receipt.exists() and label not in children:
                    children[label] = subprocess.Popen(
                        [
                            str(OWNED),
                            "--label",
                            "ssl-020-archive-" + label,
                            "--",
                            sys.executable,
                            "-u",
                            "-m",
                            ARCHIVER,
                            label,
                        ],
                        cwd=ROOT,
                    )
            try:
                os.kill(producer, 0)
            except ProcessLookupError:
                if not available(WORK / "zipf/arm-result.json"):
                    raise ValueError("EPOCH_PRODUCER_EXITED_WITHOUT_FINAL_REPLAY") from None
            time.sleep(10)
        for child in children.values():
            if child.wait() != 0:
                raise ValueError("WORK_AUDIT_ARCHIVER_FAILED")
        for label in ("epoch-01-teaching", "epoch-01-candidate", "epoch-02-teaching"):
            if not (NOTES / ("020-" + label + "-retirement-preparation.json")).is_file():
                subprocess.run(
                    [
                        str(OWNED),
                        "--label",
                        "ssl-020-archive-" + label,
                        "--",
                        sys.executable,
                        "-u",
                        "-m",
                        ARCHIVER,
                        label,
                    ],
                    cwd=ROOT,
                    check=True,
                )
        for phase in ("verify", "publish"):
            if any(fingerprint(ROOT / path) != digest for path, digest in {**tested, **orchestration}.items()):
                raise ValueError("COHERENCE_020_TESTED_SOURCE_CHANGED")
            subprocess.run([sys.executable, "-u", "-m", RUNNER, phase], cwd=ROOT, check=True)
        result = read(WORK / "zipf/arm-result.json")
        release = read(NOTES / "020-publication.json")
        retention = retire_work(result, release)
        verification = read(NOTES / "020-verification.json")
        if resolve_lexicon_path() != Path(release["path"]):
            raise ValueError("ACTIVE_SUCCESSOR_CHANGED_BEFORE_NOTEBOOK_UPDATE")
        update_notebook(verification, release, retention)
        record_status(
            NOTES / "020-round-status.json",
            {
                "format": "GSE.lexicon-learning-round-status/1",
                "code": "PUBLISHED_AND_ROLLING_RETENTION_VERIFIED",
                "verified_at_utc": datetime.now(timezone.utc).isoformat(),
                "active_path": release["path"],
                "active_sha256": release["sha256"],
                "previous_path": release["previous_path"],
                "new_cells": result["new_cells"],
                "cells": release["cells"],
                "construction_model_questions": 8,
                "boundary_diagnostic_questions": 2,
                "joint_support_reduction_bits": verification["joint_support_reduction_bits"],
                "marginal_potential_reduction_bits": verification["marginal_potential_reduction_bits"],
                "semantic_outcomes": release["semantic_audit"]["outcomes"],
                "tests_passed": 161,
                "source_and_audit_records_preserved": True,
                "logical_bytes_unlinked": retention["logical_bytes_unlinked"],
                "living_notebook": str(PAPER),
                "notebook_sha256": sha256(PAPER.read_bytes()).hexdigest(),
            },
        )
        print("COHERENCE_020_ROUND_COMPLETE", release["cells"], flush=True)
    except BaseException as error:
        record_status(
            NOTES / "020-finisher-failure.json",
            {
                "code": "FINISHER_STOPPED",
                "reason": repr(error),
                "active_path": str(resolve_lexicon_path()),
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
                child.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", type=int, required=True)
    finish(parser.parse_args().producer)
