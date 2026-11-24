"""Journal the six prepared checkpoint residual/child questions, without DB writes."""

import json
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import JournaledTransport, fingerprint, make_questions, read, record
from GSE.curation.lexicon_builder.learning_state import LearningState
from GSE.curation.lexicon_builder.residual import OllamaTransport, _read_value, _request_id


def main():
    root = Path(__file__).resolve().parents[3]
    notes = Path(__file__).resolve().parent
    packet_path = notes / "ssl-api-controller-child-questions.json"
    destination = notes / "ssl-api-controller-child-answers.json"
    if destination.exists():
        raise ValueError("CHILD_ANSWERS_ALREADY_RECORDED_DO_NOT_REPEAT")
    packet = read(packet_path)
    base = root / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/checkpoint-foundation.db"
    if fingerprint(base) != packet["baseline_sha256"]:
        raise ValueError("CHILD_BASELINE_CHANGED")
    settings = read(notes / "ssl-root-prime-transport.json")["configuration"]
    transport = OllamaTransport(
        settings["model"],
        timeout=settings["timeout_seconds"],
        context_tokens=settings["context_tokens"],
        thinking=settings["thinking"],
        output_tokens=settings["output_tokens"],
    )
    transport.pin()
    if transport.identity != settings["identity"]:
        raise ValueError("CHILD_TRANSPORT_CHANGED")
    requests = make_questions(base, [tuple(row) for row in packet["coordinates"]])
    for request, original in zip(requests, packet["questions"], strict=True):
        if (
            request.request_id != original["request_id"]
            or _request_id(original["request"]) != request.request_id
            or request.output_schema() != original["schema"]
            or request.payload() != original["request"]
        ):
            raise ValueError("CHILD_REQUEST_CHANGED")
    phase = base.parent / "ssl-v2-reference-current/closure/epoch-01"
    store = LearningState(
        phase / "checkpoint-child-98k-requests.sqlite",
        {
            "question_packet_sha256": fingerprint(packet_path),
            "baseline_sha256": packet["baseline_sha256"],
            "transport": transport.identity,
            "authority": "QUESTION_ARCHIVE_ONLY",
        },
    )
    journal = JournaledTransport(
        transport,
        phase,
        "checkpoint-child-98k",
        len(requests),
        base.parent / "checkpoint-local-model.lock",
        context_store=store,
    )
    answers, records = [], []
    for request, original in zip(requests, packet["questions"], strict=True):
        raw = journal(original["request"], original["schema"])
        value = _read_value(raw, request)
        answers.append({"request_id": request.request_id, "raw_output": raw})
        row = {
            "entry_id": request.entry_id,
            "bank": request.bank,
            "request_id": request.request_id,
            "value": value,
            "code": "MODEL_ABSTAINED" if value is None else "TYPED_MODEL_PROPOSAL",
        }
        records.append(row)
        print(json.dumps(row), flush=True)
    record(
        destination,
        {
            "format": "GSE.ssl-checkpoint-local-answers/1",
            "questions_sha256": fingerprint(packet_path),
            "transport": transport.identity,
            "answers": answers,
        },
    )
    record(
        notes / "ssl-api-controller-child-audit.json",
        {
            "format": "GSE.checkpoint-child-audit/1",
            "authority": "MODEL_PROPOSALS_REQUIRE_EXISTING_TYPED_WRITER_AND_REPLAY",
            "baseline_sha256": packet["baseline_sha256"],
            "questions_sha256": fingerprint(packet_path),
            "transport": transport.identity,
            "request_archive": str(store.path),
            "journal_directory": str(phase),
            "fresh_attempts": journal.count(),
            "bank_writes": 0,
            "records": records,
        },
    )


if __name__ == "__main__":
    main()
