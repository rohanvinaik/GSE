"""Complete the four reserved BODY questions after the first signed challenge.

These are diagnostic, independent baseline questions. They write no lexical cell
and do not manufacture a positive discovery seed or authorize a rule.
"""

from collections import Counter
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from gse.curation.lexicon_builder.completion import _contexts, _entry
from gse.curation.lexicon_builder.epoch import JournaledTransport, connect, fingerprint, read, record
from gse.curation.lexicon_builder.foundation import BANKS, lexical_context
from gse.curation.lexicon_builder.residual import OllamaTransport, build_request, complete_bank
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.reviewed_patterns import _CapturedTransport
from gse.curation.lexicon_builder.validation import _metadata, _relations
from gse.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/coherence-021"


def run():
    plan = read(NOTES / "021-coherence-plan.json")
    baseline = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-020.db"
    if (
        resolve_lexicon_path() != baseline
        or fingerprint(baseline) != plan["baseline_sha256"]
        or fingerprint(ACTIVE_POINTER) != plan["active_pointer_sha256"]
    ):
        raise ValueError("VERTEBRATE_DIAGNOSTIC_BASELINE_CHANGED")
    teacher = read(WORK / "zipf/epoch-01/teaching.json")
    if teacher["code"] != "TEACHING_SOURCE_DISAGREEMENT":
        raise ValueError("DIAGNOSTIC_REQUIRES_THE_RECORDED_SIGNED_CHALLENGE")
    entries = tuple(plan["families"][0]["holdouts"])
    directory = WORK / "reserved-body-audits"
    directory.mkdir(exist_ok=True)
    native = OllamaTransport("qwen3.8:27b-q4_K_M", context_tokens=65536, timeout=420, thinking=False, output_tokens=256)
    native.pin()
    if not native.identity.startswith("qwen3.8:27b-q4_K_M#25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e@"):
        raise ValueError("VERTEBRATE_DIAGNOSTIC_MODEL_CHANGED")
    transport = JournaledTransport(native, directory, "audit", 4, WORK / "model.lock")
    with closing(connect(baseline)) as connection:
        connection.execute("BEGIN")
        rules = _relations(_metadata(connection, "relations"))
        observations, evidence = _contexts(connection, entries)
        prepared = []
        for identity in entries:
            definition, assertions, restrictions, _ = _entry(connection, identity)
            context = lexical_context(definition, observations[identity], rules)
            banks = tuple(sorted(evidence[identity]))
            state = resolve_dictionary(BANKS, assertions, rules, context, evidence_banks=banks, domain_restrictions=restrictions)
            request = build_request(identity, "BODY", state, tuple(observations[identity]), definition=definition, relations=rules, context=context)
            if sorted(state.domains["BODY"]) != [-1, 0, 1]:
                raise ValueError("RESERVED_BODY_TARGET_NOT_OPEN:" + identity)
            prepared.append((request, assertions, restrictions, context, banks))
    audits = []
    for request, assertions, restrictions, context, evidence_banks in prepared:
        captured = _CapturedTransport(transport)
        completion = complete_bank(request, BANKS, assertions, rules, captured, context, evidence_banks=evidence_banks, domain_restrictions=restrictions)
        value = completion.assertion.value if completion.assertion is not None else None
        outcome = (
            "MODEL_AGREEMENT" if value == 1 else "MODEL_COUNTEREXAMPLE"
        ) if completion.code == "ASSIGNED" else completion.code
        result = {
            "entry_id": request.entry_id,
            "bank": "BODY",
            "request": request.payload(),
            "schema": request.output_schema(),
            "request_id": request.request_id,
            "completion_code": completion.code,
            "code": outcome,
            "value": value,
            "raw_output": captured.raw,
            "transport_identity": captured.identity,
            "candidate_assertion": asdict(completion.assertion) if completion.assertion is not None else None,
            "details": completion.details,
            "comparison_authority": "UNADMITTED_PROJECTION_NOT_GOLD",
            "lexicon_writes": False,
        }
        record(directory / (request.request_id + ".json"), result)
        audits.append(result)
        print("RESERVED_BODY_AUDIT", request.entry_id, outcome, value, flush=True)
    if fingerprint(baseline) != plan["baseline_sha256"] or fingerprint(ACTIVE_POINTER) != plan["active_pointer_sha256"]:
        raise ValueError("VERTEBRATE_DIAGNOSTIC_SNAPSHOT_CHANGED")
    report = {
        "format": "gse.vertebrate-body-diagnostic/1",
        "code": "RESERVED_BASELINE_QUESTIONS_COMPLETED_AFTER_SIGNED_TEACHING_CHALLENGE",
        "baseline": str(baseline),
        "baseline_sha256": plan["baseline_sha256"],
        "initial_teacher": teacher,
        "audits": audits,
        "audit_outcomes": dict(Counter(row["code"] for row in audits)),
        "typed_questions_used": 1 + transport.count(),
        "rule_admitted": False,
        "lexicon_writes": False,
        "unknown_is_not_zero": True,
    }
    record(NOTES / "021-reserved-body-audits.json", report)
    print("RESERVED_BODY_AUDITS_COMPLETE", report["audit_outcomes"], flush=True)


if __name__ == "__main__":
    run()
