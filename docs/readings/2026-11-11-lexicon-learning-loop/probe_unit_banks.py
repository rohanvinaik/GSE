"""Capture bounded bank answers without changing the candidate."""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from gse.curation.lexicon_builder.completion import _contexts, _entry
from gse.curation.lexicon_builder.foundation import BANKS, lexical_context
from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport
from gse.curation.lexicon_builder.residual import ModelTransportError, OllamaTransport, _request_id, build_request
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.validation import _metadata, _relations


def write(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def prepare(candidate, plan):
    entries = tuple(dict.fromkeys(item["entry_id"] for item in plan["questions"]))
    with candidate.open("rb") as handle:
        snapshot = hashlib.file_digest(handle, "sha256").hexdigest()
    if snapshot != plan["candidate_sha256"]:
        raise ValueError("PROBE_CANDIDATE_CHANGED")
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        relations = _relations(_metadata(conn, "relations"))
        observations, relevance = _contexts(conn, entries)
        prepared = []
        for item in plan["questions"]:
            identity, bank = item["entry_id"], item["bank"]
            definition, assertions, restrictions, _ = _entry(conn, identity)
            context = lexical_context(definition, observations[identity], relations)
            state = resolve_dictionary(
                BANKS,
                assertions,
                relations,
                context,
                evidence_banks=tuple(sorted(relevance[identity])),
                domain_restrictions=restrictions,
            )
            request = build_request(
                identity,
                bank,
                state,
                tuple(observations[identity]),
                definition=definition,
                relations=relations,
                context=context,
            )
            prepared.append(
                {
                    "request_id": request.request_id,
                    "request": request.payload(),
                    "schema": request.output_schema(),
                }
            )
    return {"plan_sha256": _request_id(plan), "candidate_sha256": snapshot, "questions": prepared}


def pairs(rows):
    return tuple((item["request"], item["schema"]) for item in rows)


def execute(questions, folder, transport):
    pending = []
    for item in questions:
        file = folder / (item["request_id"] + ".json")
        if file.exists():
            saved = json.loads(file.read_text())
            if saved["request_id"] != item["request_id"] or saved["transport_identity"] != transport.identity:
                raise ValueError("PROBE_SAVED_ANSWER_MISMATCH")
        else:
            pending.append(item)
    groups = []
    current = []
    for item in pending:
        try:
            transport.prepare(pairs([*current, item]))
        except ModelTransportError:
            if current:
                groups.append(current)
            try:
                transport.prepare(pairs([item]))
            except ModelTransportError as error:
                write(
                    folder / (item["request_id"] + ".json"),
                    {
                        "request_id": item["request_id"],
                        "transport_identity": transport.identity,
                        "code": error.code,
                    },
                )
                current = []
                continue
            current = [item]
        else:
            current.append(item)
    if current:
        groups.append(current)
    for group in groups:
        print(json.dumps({"questions": [[r["request"]["entry_id"], r["request"]["bank"]] for r in group]}), flush=True)
        try:
            responses = transport.callable_batch(pairs(group))
        except ModelTransportError as error:
            answers = [{"code": error.code} for _ in group]
        else:
            answers = [
                {
                    "code": "MODEL_ABSTAINED" if next(iter(json.loads(raw).values())) is None else "TYPED_ANSWER",
                    "raw_output": raw,
                }
                for raw in responses
            ]
        for item, answer in zip(group, answers, strict=True):
            write(
                folder / (item["request_id"] + ".json"),
                {
                    "request_id": item["request_id"],
                    "transport_identity": transport.identity,
                    **answer,
                },
            )
            print(
                json.dumps({"entry_id": item["request"]["entry_id"], "bank": item["request"]["bank"], **answer}),
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--context-tokens", type=int, default=65536)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if args.prepared.exists():
        prepared = json.loads(args.prepared.read_text())
        if prepared["plan_sha256"] != _request_id(plan):
            raise ValueError("PROBE_PREPARATION_CHANGED")
    else:
        prepared = prepare(args.candidate.resolve(strict=True), plan)
        write(args.prepared, prepared)
    args.answers.mkdir(exist_ok=True)
    transport = OllamaBatchTransport(
        OllamaTransport(args.model, context_tokens=args.context_tokens, timeout=240, thinking=False, output_tokens=256),
        max_items=args.batch_size,
    )
    print(
        json.dumps({"phase": "TYPED_PROBES", "pin": transport.pin(), "count": len(prepared["questions"])}), flush=True
    )
    execute(prepared["questions"], args.answers, transport)


if __name__ == "__main__":
    main()
