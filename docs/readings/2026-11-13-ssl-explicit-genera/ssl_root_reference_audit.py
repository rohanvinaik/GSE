"""Execute the already prepared, bounded local reference questions; write no lexicon cells."""

import json
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import JournaledTransport, fingerprint, make_questions, read, record
from GSE.curation.lexicon_builder.learning_state import LearningState
from GSE.curation.lexicon_builder.residual import OllamaTransport, _read_value, _request_id


def main():
    root = Path(__file__).resolve().parents[3]
    notes = Path(__file__).resolve().parent
    packet_path = notes / "ssl-api-controller-local-questions.json"
    packet = read(packet_path)
    base = root / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/checkpoint-foundation.db"
    if fingerprint(base) != packet["baseline_sha256"]:
        raise ValueError("LOCAL_AUDIT_BASELINE_CHANGED")
    settings = read(notes / "ssl-root-reference-transport.json")["configuration"]
    transport = OllamaTransport(
        settings["model"],
        timeout=settings["timeout_seconds"],
        context_tokens=settings["context_tokens"],
        thinking=settings["thinking"],
        output_tokens=settings["output_tokens"],
    )
    transport.pin()
    if transport.identity != settings["identity"]:
        raise ValueError("LOCAL_AUDIT_TRANSPORT_CHANGED")
    requests = make_questions(base, [tuple(row) for row in packet["coordinates"]])
    for request, original in zip(requests, packet["questions"], strict=True):
        if (
            request.request_id != original["request_id"]
            or _request_id(original["request"]) != request.request_id
            or request.output_schema() != original["schema"]
            or request.payload() != original["request"]
        ):
            raise ValueError("LOCAL_AUDIT_REQUEST_CHANGED")
    phase = base.parent / "ssl-v2-reference-current/closure/epoch-01"
    store = LearningState(
        phase / "checkpoint-local-requests.sqlite",
        {
            "question_packet_sha256": fingerprint(packet_path),
            "baseline_sha256": packet["baseline_sha256"],
            "transport": transport.identity,
            "authority": "QUESTION_ARCHIVE_ONLY",
        },
    )
    lock = base.parent / "checkpoint-local-model.lock"
    retained = JournaledTransport(transport, phase, "teach", 1, lock)
    fresh = JournaledTransport(transport, phase, "checkpoint-reference", 7, lock, context_store=store)
    records = []
    for index, (request, original) in enumerate(zip(requests, packet["questions"], strict=True)):
        journal = retained if index == 0 else fresh
        raw = journal(original["request"], original["schema"])
        value = _read_value(raw, request)
        row = {
            "entry_id": request.entry_id,
            "bank": request.bank,
            "request_id": request.request_id,
            "raw_output": raw,
            "value": value,
            "code": "MODEL_ABSTAINED" if value is None else "TYPED_MODEL_PROPOSAL",
            "journal_label": journal.label,
            "reused_original_question": index == 0,
        }
        records.append(row)
        print(json.dumps(row), flush=True)
    receipt = {
        "format": "GSE.checkpoint-reference-audit/1",
        "authority": "MODEL_PROPOSALS_REQUIRE_EXISTING_WRITER_AND_RULE_AUDIT",
        "baseline_sha256": packet["baseline_sha256"],
        "question_packet_sha256": fingerprint(packet_path),
        "transport": transport.identity,
        "journal_directory": str(phase),
        "request_archive": str(store.path),
        "fresh_attempts": fresh.count(),
        "reused_original_questions": 1,
        "bank_writes": 0,
        "records": records,
    }
    record(notes / "ssl-root-reference-audit.json", receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
