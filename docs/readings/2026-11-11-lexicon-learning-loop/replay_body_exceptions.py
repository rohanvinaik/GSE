"""Review recorded BODY answers and complete a separate candidate."""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.publication import publication_readiness
from GSE.curation.lexicon_builder.residual import _request_id
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.rule_revisions import exception_source
from GSE.curation.lexicon_builder.validation import validate_build

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError("BODY_RESUMPTION_REPORT_CHANGED:" + str(path))
        return
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class ReviewedReplay:
    """Return only independently reviewed answers for exact unchanged questions."""

    def __init__(self, records):
        self.records = {item["request_id"]: item for item in records}
        models = {item["transport_identity"] for item in records}
        self.identity = next(iter(models)) if len(models) == 1 else "reviewed-audit-replay@" + digest(records)

    def __call__(self, payload, schema):
        item = self.records.get(_request_id(payload))
        if item is None or item["request"] != payload or item["schema"] != schema:
            raise ValueError("REVIEWED_BODY_REQUEST_CHANGED")
        return item["raw_output"]


def positive_body_answer(record):
    if record["code"] != "TYPED_ANSWER":
        return False
    value = json.loads(record["raw_output"])
    return type(value) is dict and set(value) == {"BODY"} and type(value["BODY"]) is int and value["BODY"] == 1


def review(candidate, answer_folders):
    prepared = read(FOLDER / "unit-banks-probe-requests.json")
    plan = read(FOLDER / "joint-body-revision-plan.json")
    expectations = {item["entry_id"]: item for item in plan["exceptions"]}
    questions = {
        item["request"]["entry_id"]: item for item in prepared["questions"] if item["request"]["bank"] == "BODY"
    }
    if questions.keys() != expectations.keys():
        raise ValueError("BODY_EXCEPTION_WORKLIST_MISMATCH")
    accepted, ledger = [], []
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        for identity, question in questions.items():
            exception = expectations[identity]
            source = exception_source(conn, identity)
            if digest(source) != exception["source_sha256"] or exception["counterexample"].get("BODY") != 1:
                raise ValueError("BODY_EXCEPTION_WARRANT_CHANGED:" + identity)
            answers = [
                read(folder / (question["request_id"] + ".json"))
                for folder in answer_folders
                if (folder / (question["request_id"] + ".json")).is_file()
            ]
            if not answers or any(row["request_id"] != question["request_id"] for row in answers):
                raise ValueError("BODY_EXCEPTION_ANSWER_MISSING:" + identity)
            matching = next((row for row in answers if positive_body_answer(row)), None)
            ledger.append(
                {
                    "entry_id": identity,
                    "definition": source["definition"],
                    "source_sha256": exception["source_sha256"],
                    "source_review": exception["rationale"],
                    "request_id": question["request_id"],
                    "answers": answers,
                    "code": "ACCEPTED_SOURCE_AND_MODEL_AGREE" if matching else "UNRESOLVED_NO_AGREEING_MODEL_ANSWER",
                }
            )
            if matching:
                accepted.append({**question, **matching})
    return accepted, ledger


def compare(candidate, baseline, accepted):
    expected = {item["request"]["entry_id"] for item in accepted}
    actual = set()
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("ATTACH DATABASE ? AS original", (baseline.as_uri() + "?mode=ro",))
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        count, baseline_count, matched = conn.execute(
            "SELECT (SELECT count(*) FROM main.definition_states),"
            "(SELECT count(*) FROM original.definition_states),count(*) "
            "FROM main.definition_states n JOIN original.definition_states b USING(entry_id)"
        ).fetchone()
        if count != baseline_count or count != matched:
            raise ValueError("BODY_COMPLETION_POPULATION_CHANGED")
        for entry, before, after in conn.execute(
            "SELECT n.entry_id,b.domains,n.domains FROM main.definition_states n "
            "JOIN original.definition_states b USING(entry_id) WHERE b.domains<>n.domains"
        ):
            old, new = json.loads(before), json.loads(after)
            if entry not in expected or old["BODY"] != [-1, 0, 1] or new != {**old, "BODY": [1]}:
                raise ValueError("UNEXPECTED_BODY_COMPLETION_DELTA:" + entry)
            actual.add(entry)
    if actual != expected:
        raise ValueError("BODY_COMPLETION_DELTA_INCOMPLETE")
    return count, sorted(actual)


def pending_entries(candidate, accepted, transport):
    """Skip an already committed cell only when it has the exact recorded authority."""
    pending = []
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        receipts = read_model_receipts(conn)
        for item in accepted:
            identity = item["request"]["entry_id"]
            row = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (identity,)).fetchone()
            if row is None:
                raise ValueError("BODY_EXCEPTION_DEFINITION_MISSING:" + identity)
            domain = json.loads(row[0])["BODY"]
            if len(domain) > 1:
                pending.append(identity)
                continue
            if domain != [1] or not any(
                rec["request_id"] == item["request_id"]
                and rec["request"] == item["request"]
                and rec["schema"] == item["schema"]
                and rec["assertion"]["bank"] == "BODY"
                and rec["assertion"]["value"] == 1
                and rec["assertion"]["source"] == "model:" + transport.identity
                for rec in receipts.get(identity, ())
            ):
                raise ValueError("BODY_EXCEPTION_UNEXPECTED_EXISTING_AUTHORITY:" + identity)
    return tuple(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--answers", type=Path, action="append", required=True)
    args = parser.parse_args()
    candidate = args.candidate.resolve(strict=True)
    parent = read(FOLDER / "joint-body-verification.json")
    baseline = Path(parent["candidate"])
    if candidate.samefile(baseline):
        raise ValueError("BODY_COMPLETION_REQUIRES_SEPARATE_COPY")
    accepted, ledger = review(candidate, args.answers)
    write(FOLDER / "body-exception-model-review.json", ledger)
    transport = ReviewedReplay(accepted)
    pending = pending_entries(candidate, accepted, transport)
    if pending:
        result = complete_dictionary(
            candidate,
            transport,
            len(pending),
            entry_ids=pending,
            banks=("BODY",),
            max_calls_per_entry=1,
            max_entries_per_pass=len(pending),
            priority="zipf",
            progress=lambda row: print(json.dumps(row), flush=True),
        )
        if result["outcomes"] != {"ASSIGNED": len(pending)}:
            raise ValueError("REVIEWED_BODY_COMPLETION_FAILED")
        write(FOLDER / "body-exception-completion.json", result)
    print('{"phase":"FULL_POST_COMPLETION_REPLAY"}', flush=True)
    replay = validate_build(candidate)
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("BODY_COMPLETION_REPLAY_FAILED")
    count, changed = compare(candidate, baseline, accepted)
    active = sha256(ROOT / "data/lexicon_active.json")
    baseline_hash = sha256(baseline)
    if active != parent["active_pointer_sha256"] or baseline_hash != parent["candidate_sha256"]:
        raise ValueError("BODY_COMPLETION_BASELINE_OR_ACTIVE_CHANGED")
    publication = publication_readiness(candidate)
    result = {
        "format": "gse.body-exception-resumption/1",
        "candidate": str(candidate),
        "candidate_sha256": sha256(candidate),
        "baseline_sha256": baseline_hash,
        "definitions_compared": count,
        "new_BODY_positive": changed,
        "remaining_exception_ids": sorted({item["entry_id"] for item in ledger} - set(changed)),
        "active_pointer_sha256": active,
        "activation_performed": False,
        "live_model_calls_during_completion": 0,
        "replay": replay,
        "publication": publication,
    }
    write(FOLDER / "body-exception-resumption-verification.json", result)
    print(
        json.dumps(
            {
                "replay": replay["code"],
                "definitions": count,
                "new_BODY_positive": len(changed),
                "publication": publication["code"],
                "cells": publication["cells"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
