"""Independent typed witnesses for reviewed canonical correspondences; no DB writes.

Uses the existing exact request builder, local transport and durable journal.
The review's proposed values are deliberately not passed to the model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import JournaledTransport, fingerprint, make_questions, read, record
from GSE.curation.lexicon_builder.learning_state import LearningState
from GSE.curation.lexicon_builder.residual import OllamaTransport, _read_value


def audit(review_path: Path, directory: Path, settings_path: Path):
    review = read(review_path)
    database = Path(review["baseline"]["path"])
    if fingerprint(database) != review["baseline"]["sha256"]:
        raise ValueError("CANONICAL_AUDIT_BASELINE_CHANGED")
    if any(fingerprint(Path(path)) != digest for path, digest in review["source_pins"].items()):
        raise ValueError("CANONICAL_AUDIT_REVIEWED_SOURCES_CHANGED")
    directory.mkdir(exist_ok=True)
    settings = read(settings_path)["configuration"]
    transport = OllamaTransport(
        settings["model"],
        timeout=settings["timeout_seconds"],
        context_tokens=settings["context_tokens"],
        thinking=settings["thinking"],
        output_tokens=settings["output_tokens"],
    )
    transport.pin()
    if transport.identity != settings["identity"]:
        raise ValueError("CANONICAL_AUDIT_TRANSPORT_CHANGED")
    coordinates = [(claim["entry_id"], claim["bank"]) for claim in review["claims"]]
    if not coordinates or len(set(coordinates)) != len(coordinates):
        raise ValueError("CANONICAL_AUDIT_DUPLICATE_COORDINATES")
    requests = make_questions(database, coordinates)
    packet = directory / "questions.json"
    record(
        packet,
        {
            "format": "GSE.ssl-checkpoint-local-questions/1",
            "baseline_sha256": fingerprint(database),
            "coordinates": coordinates,
            "questions": [
                {"request_id": request.request_id, "request": request.payload(), "schema": request.output_schema()}
                for request in requests
            ],
        },
    )
    store = LearningState(
        directory / "requests.sqlite",
        {
            "question_packet_sha256": fingerprint(packet),
            "baseline_sha256": fingerprint(database),
            "transport": transport.identity,
            "authority": "QUESTION_ARCHIVE_ONLY",
        },
    )
    journal = JournaledTransport(
        transport,
        directory,
        "canonical-correspondence-98k",
        len(requests),
        database.parent.parent / "checkpoint-local-model.lock",
        context_store=store,
    )
    answers, outcomes = [], []
    for request in requests:
        raw = journal(request.payload(), request.output_schema())
        value = _read_value(raw, request)
        answers.append({"request_id": request.request_id, "raw_output": raw})
        outcome = {"entry_id": request.entry_id, "bank": request.bank, "value": value, "request_id": request.request_id}
        outcomes.append(outcome)
        print(json.dumps(outcome), flush=True)
    if fingerprint(database) != review["baseline"]["sha256"]:
        raise ValueError("CANONICAL_AUDIT_INPUT_CHANGED")
    record(
        directory / "answers.json",
        {
            "format": "GSE.ssl-checkpoint-local-answers/1",
            "questions_sha256": fingerprint(packet),
            "transport": transport.identity,
            "answers": answers,
        },
    )
    result = {
        "format": "GSE.canonical-correspondence-independent-witnesses/1",
        "code": "TYPED_WITNESSES_RECORDED_NOT_ADMISSION",
        "review_sha256": fingerprint(review_path),
        "baseline": review["baseline"],
        "transport": transport.identity,
        "questions_sha256": fingerprint(packet),
        "answers_sha256": fingerprint(directory / "answers.json"),
        "request_archive": str(store.path),
        "attempts": journal.count(),
        "records": outcomes,
        "bank_writes": 0,
        "is_final_holdout": False,
    }
    record(directory / "audit.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--settings", required=True, type=Path)
    args = parser.parse_args()
    audit(args.review, args.directory, args.settings)
