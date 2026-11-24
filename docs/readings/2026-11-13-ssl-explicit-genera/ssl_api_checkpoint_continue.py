"""Continue the private checkpoint only after exact joint-migration completion.

No service calls or activation. All retained answers are reconstructed at their
original rule version, then consumed by the full-preflight sustained writer.
"""

import importlib.util
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from GSE.curation.lexicon_builder.completion import _contexts, _entry, _historical_request
from GSE.curation.lexicon_builder.epoch import fingerprint, read, record
from GSE.curation.lexicon_builder.rule_history import read_history
from GSE.curation.lexicon_builder.specification import measure_dictionary
from GSE.curation.lexicon_builder.validation import _metadata, _relations


def main():
    notes = Path(__file__).resolve().parent
    root = notes.parents[2]
    work = root / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint"
    result_path = work / "result.json"
    child_answers = notes / "ssl-api-controller-child-answers.json"
    deadline = time.monotonic() + 3 * 3600
    while not result_path.exists() or not child_answers.exists():
        if time.monotonic() > deadline:
            raise TimeoutError("CHECKPOINT_PREREQUISITES_NOT_FINISHED_NO_WRITES")
        time.sleep(30)
    result = read(result_path)
    candidate = work / "candidate.db"
    if (
        result["code"] != "JOINT_REFERENCE_REVISION_REPLAYED_WORKLOAD_GATE_PENDING"
        or Path(result["candidate"]).resolve() != candidate
        or fingerprint(candidate) != result["candidate_sha256"]
    ):
        raise ValueError("CHECKPOINT_JOINT_HEAD_IDENTITY_CHANGED")
    helper = notes / "ssl_api_checkpoint_packets.py"
    spec = importlib.util.spec_from_file_location("checkpoint_packets", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    configuration = read(notes / "ssl-root-prime-transport.json")
    transports = [
        module.PacketTransport(
            notes / ("ssl-api-controller-" + kind + "-questions.json"),
            notes / ("ssl-api-controller-" + kind + "-answers.json"),
            configuration,
        )
        for kind in ("prime", "child")
    ]
    coordinates = [*transports[0].packet["coordinates"], *transports[1].packet["coordinates"][:3]]
    original_version = "9aeb7c65650902cbf3139400c64acff3aa9645a9937069d95015f5b728e06436"
    # This read-only diagnostic refuses obsolete/affected source contexts before
    # paying for the writer's mandatory full preflight. It is NOT a certificate
    # that substitutes for that replay.
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        relations = _relations(_metadata(conn, "relations"))
        history = read_history(conn, relations)
        observations, relevance = _contexts(conn, tuple(pair[0] for pair in coordinates))
        requests = {
            (row["request"]["entry_id"], row["request"]["bank"]): row
            for transport in transports
            for row in transport.requests.values()
        }
        verified = []
        for entry, bank in coordinates:
            definition, assertions, restrictions, _ = _entry(conn, entry)
            raw = {"rule_version": original_version, **requests[(entry, bank)]}
            request, _, _ = _historical_request(
                raw,
                definition,
                bank,
                assertions,
                restrictions,
                observations[entry],
                tuple(sorted(relevance[entry])),
                relations,
                history,
            )
            verified.append(request.request_id)
    record(
        notes / "ssl-api-controller-delayed-precheck.json",
        {
            "code": "EXACT_HISTORICAL_REQUESTS_RECONSTRUCTED_FULL_PREFLIGHT_STILL_REQUIRED",
            "candidate_sha256": result["candidate_sha256"],
            "request_ids": verified,
            "transport": transports[0].identity,
            "service_calls": 0,
            "writes": 0,
        },
    )
    report = module.write_packets(
        candidate,
        transports,
        coordinates,
        notes / "ssl-api-controller-prime-child-writer.json",
        rule_version=original_version,
    )
    print(json.dumps(report), flush=True)
    record(work / "space-post-prime-child-teaching.json", measure_dictionary(candidate))


if __name__ == "__main__":
    main()
