"""Execute a bounded lexical checkpoint; always keep activation separate.

Prepared worker, not evidence of execution. Run through SquishOS owned-run.
The selected bank is a question, never an expected answer or approved rule.
"""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.publication import publication_readiness
from gse.curation.lexicon_builder.residual import OllamaTransport
from gse.curation.lexicon_builder.validation import validate_build
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

MODEL = "qwen3.8:27b-q4_K_M"
MODEL_DIGEST = "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e"


class ModelOptions(TypedDict):
    timeout: int
    context_tokens: int
    thinking: bool
    output_tokens: int


MODEL_OPTIONS: ModelOptions = {"timeout": 300, "context_tokens": 65536, "thinking": False, "output_tokens": 1024}
BATCH_SIZE = 4
COHORT_SIZE = 8
MAX_CHECKPOINT_QUESTIONS = 16
DISCOVERY_IDS = ("wordnet:in:inch.n.01", "wordnet:are:are.n.01", "wordnet:at:at.n.02")


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def pointer_bytes():
    return ACTIVE_POINTER.read_bytes() if ACTIVE_POINTER.exists() else None


def snapshot(path, bank, prior_receipts=None):
    """Materialize lazy receipts before closing the read-only transaction."""
    states, receipt_ids, new_receipts = {}, set(), []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        for entry, raw in conn.execute("SELECT entry_id,domains FROM definition_states ORDER BY entry_id"):
            domains = json.loads(raw)
            selected = domains.pop(bank)
            states[entry] = (selected, digest(domains))
        for receipts in read_model_receipts(conn).values():
            for receipt in receipts:
                receipt_ids.add(receipt["request_id"])
                if prior_receipts is not None and receipt["request_id"] not in prior_receipts:
                    new_receipts.append(receipt)
    return states, receipt_ids, new_receipts


def summary(states, receipt_ids):
    return {
        "definitions": len(states),
        "selected_bank_domains": dict(Counter(json.dumps(value[0]) for value in states.values())),
        "logical_state_sha256": digest(states),
        "active_receipt_count": len(receipt_ids),
        "active_request_ids_sha256": digest(sorted(receipt_ids)),
    }


def assignment_audit(before, after, old_ids, new_ids, receipts, bank, entries, pointer):
    changes, violations = [], []
    if before.keys() != after.keys():
        violations.append({"code": "POPULATION_CHANGED"})
    if old_ids - new_ids:
        violations.append({"code": "PRIOR_RECEIPTS_REMOVED", "request_ids": sorted(old_ids - new_ids)})
    received = {}
    for receipt in receipts:
        entry, assertion = receipt["entry_id"], receipt["assertion"]
        if assertion["bank"] != bank or entries is not None and entry not in entries:
            violations.append({"entry_id": entry, "code": "RECEIPT_OUTSIDE_SELECTED_SCOPE"})
        if entry in received:
            violations.append({"entry_id": entry, "code": "MORE_THAN_ONE_NEW_RULING_FOR_ENTRY"})
        received[entry] = assertion["value"]
        if entry not in before or entry not in after:
            violations.append({"entry_id": entry, "code": "RECEIPT_DEFINITION_MISSING"})
        elif len(before[entry][0]) <= 1 or after[entry][0] != [assertion["value"]]:
            violations.append({"entry_id": entry, "code": "RECEIPT_ASSIGNMENT_MISMATCH"})
    for entry in sorted(before.keys() & after.keys()):
        old, old_other = before[entry]
        new, new_other = after[entry]
        if old_other != new_other:
            # Conservatively expose even valid symbolic propagation for review;
            # this worker never silently broadens a selected-bank checkpoint.
            violations.append({"entry_id": entry, "code": "OTHER_BANK_CHANGED_REQUIRES_REVIEW"})
        if old != new:
            changes.append({"entry_id": entry, "bank": bank, "before": old, "after": new})
            if len(old) <= 1 or not new or not set(new) <= set(old):
                violations.append({"entry_id": entry, "code": "PRIOR_DOMAIN_NOT_PRESERVED"})
            if entry not in received or new != [received[entry]]:
                violations.append({"entry_id": entry, "code": "CHANGE_WITHOUT_EXACT_NEW_RECEIPT"})
    unchanged = pointer == pointer_bytes()
    if not unchanged:
        violations.append({"code": "ACTIVE_POINTER_CHANGED"})
    return {
        "code": "ASSIGNMENTS_VERIFIED" if not violations else "ASSIGNMENT_AUDIT_FAILED",
        "changes": changes,
        "violations": violations,
        "active_pointer_unchanged": unchanged,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reports-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--gold", type=Path, help="Optional existing semantic labels for readiness only; never activation")
    parser.add_argument("--retry", action="store_true", help="Explicitly retry unchanged prior failed request identities")
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("quantity-discovery", help="Exactly the three fixed QUANTITY discovery questions")
    selected = modes.add_parser("selected", help="One bank across at most eight explicit definitions")
    selected.add_argument("--bank", choices=BANKS, required=True)
    selected.add_argument("--entry-id", action="append", required=True)
    zipf = modes.add_parser("zipf", help="Resume the existing durable Zipf/spelling schedule for one bank")
    zipf.add_argument("--bank", choices=BANKS, required=True)
    zipf.add_argument("--max-model-calls", type=int, default=MAX_CHECKPOINT_QUESTIONS)
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", args.run_id) is None:
        parser.error("run-id must be a short filename identifier")
    if args.mode == "quantity-discovery":
        args.bank, args.entries = "QUANTITY", DISCOVERY_IDS
        args.max_model_calls = len(DISCOVERY_IDS)
    elif args.mode == "selected":
        args.entries = tuple(args.entry_id)
        if not 1 <= len(args.entries) <= COHORT_SIZE or len(set(args.entries)) != len(args.entries):
            parser.error("selected requires one to eight distinct entry IDs")
        if any(not entry.strip() for entry in args.entries):
            parser.error("entry IDs cannot be blank")
        args.max_model_calls = len(args.entries)
    else:
        args.entries = None
        if not 1 <= args.max_model_calls <= MAX_CHECKPOINT_QUESTIONS:
            parser.error("Zipf checkpoint budget must be between one and sixteen bank questions")
    return args


def main():
    args = parse_args()
    candidate = args.candidate.expanduser().resolve(strict=True)
    active = resolve_lexicon_path().resolve()
    if candidate == active or active.exists() and candidate.samefile(active):
        raise ValueError("CHECKPOINT_CANDIDATE_MUST_NOT_BE_ACTIVE_LEXICON")
    if args.gold is not None:
        args.gold = args.gold.expanduser().resolve(strict=True)
    directory = args.reports_dir.expanduser().resolve() / args.run_id
    directory.mkdir(parents=True, exist_ok=False)  # A reused run ID never overwrites evidence.
    outputs = []

    def save(name, value):
        target = directory / f"{name}.json"
        with target.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        outputs.append({"file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})

    pointer = pointer_bytes()
    options = {
        "banks": (args.bank,),
        "entry_ids": args.entries,
        "max_calls_per_entry": 1,
        "max_entries_per_pass": COHORT_SIZE,
        "continue_cohorts": True,
        "batch_size": BATCH_SIZE,
        "priority": "zipf",
        "cohort_policy": "spelling",
        "bank_priority": "evidence",
        "retry": args.retry,
    }
    save("plan", {
        "candidate": str(candidate), "mode": args.mode, "max_model_calls": args.max_model_calls,
        "options": options, "model": MODEL, "expected_model_digest": MODEL_DIGEST,
        "model_options": MODEL_OPTIONS, "started_utc": datetime.now(timezone.utc).isoformat(),
        "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "active_pointer_sha256": hashlib.sha256(pointer).hexdigest() if pointer is not None else None,
        "automatic_activation": False, "semantic_rule_approval": False,
    })
    failed = False
    try:
        before, prior_ids, _ = snapshot(candidate, args.bank)
        save("before", summary(before, prior_ids))
        if args.entries is not None:
            missing = sorted(set(args.entries) - before.keys())
            if missing:
                raise ValueError(f"UNKNOWN_SELECTED_DEFINITIONS:{missing}")
        base = OllamaTransport(MODEL, **MODEL_OPTIONS)
        transport = OllamaBatchTransport(base, max_items=BATCH_SIZE)
        pin = transport.pin()
        if base.model_digest != MODEL_DIGEST:
            raise ValueError("CALIBRATED_MODEL_CHANGED")
        save("execution", {"model_pin": pin, "transport_identity": transport.identity, "options": options})
        try:
            with (directory / "progress.jsonl").open("x", encoding="utf-8") as progress_file:
                def progress(event):
                    line = json.dumps(event, sort_keys=True, allow_nan=False)
                    progress_file.write(line + "\n")
                    progress_file.flush()
                    print(line, flush=True)

                result = complete_dictionary(candidate, transport, args.max_model_calls, **options, progress=progress)
            save("completion", result)
        except Exception as error:
            failed = True
            failure = {"code": "COMPLETION_RAISED", "error_type": type(error).__name__, "reason": str(error)}
            failure_receipt = getattr(error, "receipt", None)
            if isinstance(failure_receipt, dict):
                failure["failure_receipt"] = failure_receipt
            save("completion-error", failure)
        # Even an interrupted/failed completion can have committed valid cells.
        # Inspect and replay them instead of claiming the entire run rolled back.
        after, current_ids, receipts = snapshot(candidate, args.bank, prior_ids)
        save("after", summary(after, current_ids))
        save("receipts", {"receipts": receipts, "authority": "UNREVIEWED_MODEL_RULINGS_NOT_GOLD"})
        assignment = assignment_audit(before, after, prior_ids, current_ids, receipts, args.bank, args.entries, pointer)
        save("assignment-audit", assignment)
        try:
            replay = validate_build(candidate)
        except Exception as error:
            replay = {"code": "REPLAY_RAISED", "error_type": type(error).__name__, "reason": str(error)}
        save("replay", replay)
        try:
            publication = publication_readiness(candidate, args.gold)
        except Exception as error:
            publication = {"code": "PUBLICATION_AUDIT_RAISED", "error_type": type(error).__name__, "reason": str(error)}
        save("publication", publication)
        failed = failed or bool(assignment["violations"]) or replay["code"] != "REPLAY_VALIDATED"
        failed = failed or not replay.get("complete_search", False) or pointer != pointer_bytes()
        failed = failed or publication["code"] not in {"PUBLICATION_BLOCKED", "READY_FOR_PUBLICATION"}
        save("verification", {
            "code": "CHECKPOINT_FAILED" if failed else "CHECKPOINT_VERIFIED",
            "new_receipts": len(receipts), "changed_cells": len(assignment["changes"]),
            "replay": replay["code"], "publication": publication["code"],
            "active_pointer_unchanged": pointer == pointer_bytes(),
            "candidate_complete": publication["code"] == "READY_FOR_PUBLICATION",
            "activation_performed": False, "semantic_reviews_created": 0,
        })
    except BaseException as error:
        failed = True
        save("worker-error", {"error_type": type(error).__name__, "reason": str(error)})
        if not isinstance(error, Exception):
            raise
    finally:
        progress_path = directory / "progress.jsonl"
        if progress_path.exists():
            outputs.append({"file": progress_path.name, "sha256": hashlib.sha256(progress_path.read_bytes()).hexdigest()})
        save("manifest", {"format": "gse.bounded-worker-artifacts/1", "artifacts": list(outputs),
                          "hash_scope": "FILE_BYTES_EXCLUDING_THIS_MANIFEST", "worker_failed": failed})
    print(json.dumps({"reports": str(directory), "worker_failed": failed, "activation_performed": False}), flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
