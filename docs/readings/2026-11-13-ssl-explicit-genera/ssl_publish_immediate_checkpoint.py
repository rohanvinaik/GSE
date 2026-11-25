"""Execute the owner's immediate sparse release through the existing publisher."""
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

from GSE.curation.lexicon_builder.publication import publish_sparse
from GSE.lexicon_resource import resolve_lexicon_path

ROOT = Path(__file__).resolve().parents[3]
NOTES = Path(__file__).resolve().parent
SOURCE = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint/candidate-canonical-auxiliary.db"
DEST = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-022.db"
POINTER = ROOT / "data/lexicon_active.json"
DIGEST = "8d87c5284e91af72cd4f89494e3e89979f9c638a2daf7356180660988cbbb62e"


def save(name, data):
    (NOTES / name).write_text(json.dumps(data, indent=2, default=str) + "\n")


def main():
    prior = json.loads(POINTER.read_text())
    pointer_digest = hashlib.sha256(POINTER.read_bytes()).hexdigest()
    with SOURCE.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == DIGEST, "SOURCE_CHANGED"
    save("ssl-root-immediate-publication-status.json", {
        "code": "EXISTING_SPARSE_PUBLICATION_RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(SOURCE), "source_sha256": DIGEST, "destination": str(DEST), "prior_pointer": prior,
        "owner_change": "Downstream functionality gaps no longer block immediate sparse lexicon release; unknowns remain explicit.",
    })
    result = publish_sparse(
        SOURCE, DEST, NOTES / "ssl-api-controller-publication-regression-gold.json",
        expected_sha256=DIGEST, expected_pointer_sha256=pointer_digest,
    )
    save("ssl-root-immediate-publication-result.json", result)
    if result["code"] != "PUBLISHED_SPARSE_LEXICON":
        raise RuntimeError(f"PUBLICATION_REFUSED: {result.get('blockers')}")
    assert resolve_lexicon_path().resolve() == DEST.resolve(), "DEFAULT_RESOURCE_MISMATCH"
    from GSE.api import GSEEncoder
    from GSE.symbolic import from_trace
    encoder = GSEEncoder()
    smoke = []
    for text in ["The dog runs.", "I want to go home.", "This is a person."]:
        trace = encoder.encode(text)
        expression = from_trace(trace)
        smoke.append({"text": text, "trace_type": type(trace).__name__, "expression_type": type(expression).__name__})
        assert expression is not None, "DEFAULT_ENCODING_FAILED"
    delivery = {
        "code": "CHECKPOINT_PUBLISHED_VALIDATED", "at_utc": datetime.now(timezone.utc).isoformat(),
        "active_pointer": json.loads(POINTER.read_text()), "artifact": str(DEST), "sha256": result["sha256"],
        "previous_path": result.get("previous_path"), "publication_receipt": str(NOTES / "ssl-root-immediate-publication-result.json"),
        "validation_scope": "Existing sparse publication: full replay, declared cohort/basis/model scope and supplied semantic regression; default consumer smoke.",
        "acceptance_changed_by_owner": "2026-11-24: publish now; owner will debug downstream functionality gaps. Full eight-operation workload and repository freeze are not claimed passed.",
        "sparse_not_exhaustively_complete": True, "unknown_is_zero": False,
        "remaining_limitations": ["Unresolved banks remain unknown", "Full downstream usability acceptance remains unfinished", "Moral profile successor remains separate pending work"],
        "default_consumer_smoke": smoke,
    }
    save("ssl-api-checkpoint-delivery.json", delivery)
    save("ssl-root-immediate-publication-status.json", delivery)
    print(json.dumps(delivery), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        save("ssl-root-immediate-publication-failure.json", {"code": "IMMEDIATE_PUBLICATION_FAILED", "error": str(exc), "traceback": traceback.format_exc()})
        raise
