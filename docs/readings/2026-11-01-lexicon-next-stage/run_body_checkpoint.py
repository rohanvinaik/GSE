"""Execute one bounded BODY batch and persist measured verification artifacts."""

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from gse.curation.lexicon_builder.completion import complete_dictionary
from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.publication import publication_readiness
from gse.curation.lexicon_builder.residual import OllamaTransport
from gse.curation.lexicon_builder.validation import validate_build


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def snapshot(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        states = {}
        for entry, raw in conn.execute("SELECT entry_id,domains FROM definition_states"):
            domains = json.loads(raw)
            body = domains.pop("BODY")
            states[entry] = (body, digest(domains))
        receipts = read_model_receipts(conn)
    return states, {r["request_id"] for rows in receipts.values() for r in rows}


def main():
    candidate = Path(sys.argv[1]).resolve()
    directory = Path(__file__).resolve().parent
    prefix = "zipf-body-batch-004"

    def save(suffix, value):
        target = directory / f"{prefix}{suffix}.json"
        with target.open("x") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")

    if (directory / f"{prefix}-execution.json").exists():
        raise ValueError("CHECKPOINT_ALREADY_STARTED_USE_A_NEW_RUN_ID")
    active = Path("data/lexicon_active.json")
    pointer = active.read_bytes()
    before, prior_receipts = snapshot(candidate)
    base = OllamaTransport("qwen3.8:27b-q4_K_M", timeout=300, context_tokens=65536,
                           thinking=False, output_tokens=1024)
    transport = OllamaBatchTransport(base, max_items=4)
    pin = transport.pin()
    if base.model_digest != "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e":
        raise ValueError("CALIBRATED_MODEL_CHANGED")
    options = dict(banks=("BODY",), max_calls_per_entry=1, max_entries_per_pass=8,
                   continue_cohorts=True, batch_size=4, priority="zipf",
                   cohort_policy="spelling", bank_priority="evidence")
    save("-execution", {"candidate": str(candidate), "model_pin": pin,
         "started_utc": datetime.now(timezone.utc).isoformat(), "max_model_calls": 16,
         "options": options, "context_tokens": 65536, "output_tokens": 1024,
         "thinking": False, "timeout": 300,
         "active_pointer_sha256": hashlib.sha256(pointer).hexdigest()})
    result = complete_dictionary(candidate, transport, 16, **options,
                                 progress=lambda event: print(json.dumps(event), flush=True))
    save("", result)
    after, _ = snapshot(candidate)
    changes, violations = [], []
    if before.keys() != after.keys():
        violations.append({"code": "POPULATION_CHANGED"})
    for entry in before.keys() & after.keys():
        old, old_other = before[entry]
        new, new_other = after[entry]
        if old_other != new_other:
            violations.append({"entry_id": entry, "code": "OTHER_BANK_CHANGED"})
        if old != new:
            changes.append({"entry_id": entry, "bank": "BODY", "before": old, "after": new})
            if len(old) == 1 or not set(new) <= set(old):
                violations.append({"entry_id": entry, "code": "PRIOR_DOMAIN_NOT_PRESERVED"})
    with sqlite3.connect(candidate) as conn:
        receipts = [r for rows in read_model_receipts(conn).values() for r in rows
                    if r["request_id"] not in prior_receipts]
    save("-receipts", {"receipts": receipts, "authority": "UNREVIEWED_MODEL_RULINGS"})
    assignment = {"code": "ASSIGNMENTS_VERIFIED" if not violations else "ASSIGNMENT_AUDIT_FAILED",
                  "changes": changes, "violations": violations,
                  "active_pointer_unchanged": pointer == active.read_bytes()}
    save("-assignment-audit", assignment)
    replay = validate_build(candidate)
    save("-replay", replay)
    publication = publication_readiness(candidate)
    save("-publication", publication)
    print(json.dumps({"outcomes": result["outcomes"], "changes": len(changes),
                      "violations": violations, "replay": replay["code"],
                      "publication": publication["code"], "cells": publication["cells"]}), flush=True)
    if violations or replay["code"] != "REPLAY_VALIDATED" or pointer != active.read_bytes():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
