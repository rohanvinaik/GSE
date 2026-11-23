"""Replay isolated model audits and join them to the full population stage."""

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from gse.curation.lexicon_builder.completion import _entry
from gse.curation.lexicon_builder.evidence import Observation
from gse.curation.lexicon_builder.foundation import (
    BANKS,
    _attested_wordnet_lemma,
    _exact_wordnet_ancestry,
    lexical_context,
)
from gse.curation.lexicon_builder.relevance import observation_relevance
from gse.curation.lexicon_builder.residual import build_request, complete_bank
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.validation import _metadata, _relations

FOLDER = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


class CapturedAnswer:
    def __init__(self, question, answer):
        self.question, self.answer = question, answer
        self.identity = answer["transport_identity"]

    def __call__(self, payload, schema):
        if self.question["request"] != payload or self.question["schema"] != schema:
            raise ValueError("UNIT_AUDIT_REQUEST_CHANGED")
        return self.answer["raw_output"]


def audit_answer(conn, relations, question, answer, expected):
    payload = question["request"]
    identity, bank = payload["entry_id"], payload["bank"]
    if answer["request_id"] != question["request_id"]:
        raise ValueError("UNIT_AUDIT_ANSWER_ID_MISMATCH")
    if "raw_output" not in answer:
        return {"code": "OPERATIONAL_REFUSAL", "transport_code": answer["code"]}
    definition, assertions, restrictions, _ = _entry(conn, identity)
    observations = tuple(payload["observations"])
    relevant = set()
    for raw in observations:
        observation = Observation(
            raw["entry_id"],
            raw["source"],
            raw["record_id"],
            raw["family"],
            raw["features"],
            raw["scope"],
            tuple(raw["candidate_entry_ids"]),
        )
        relevant.update(observation_relevance(observation))
    evidence_banks = tuple(sorted(relevant))
    context = lexical_context(definition, observations, relations)
    state = resolve_dictionary(
        BANKS,
        assertions,
        relations,
        context,
        evidence_banks=evidence_banks,
        domain_restrictions=restrictions,
    )
    fresh = build_request(
        identity,
        bank,
        state,
        observations,
        definition=definition,
        relations=relations,
        context=context,
    )
    if fresh.request_id != question["request_id"]:
        raise ValueError("UNIT_AUDIT_BASELINE_CHANGED")
    checked = complete_bank(
        fresh,
        BANKS,
        assertions,
        relations,
        CapturedAnswer(question, answer),
        context,
        evidence_banks=evidence_banks,
        domain_restrictions=restrictions,
    )
    if checked.code != "ASSIGNED" or checked.assertion is None:
        return {"code": checked.code, "details": checked.details}
    value = checked.assertion.value
    return {"code": "MODEL_AGREEMENT" if value == expected else "MODEL_DISAGREEMENT", "value": value}


def scope_reviews(stage):
    rows = []
    for case in stage["scope_reviews"]:
        definition = case["definition"]
        in_scope = any(
            "unit_of_measurement.n.01" in _exact_wordnet_ancestry(definition, record)
            and _attested_wordnet_lemma(definition, record)
            for record in case["observations"]
        )
        rows.append(
            {
                "definition": definition,
                "challenge": case["challenge"],
                "code": "IN_SCOPE_REVIEW" if in_scope else "OUTSIDE_ATTESTED_NATIVE_SCOPE",
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--answers", type=Path, action="append", required=True)
    args = parser.parse_args()
    plan = read(FOLDER / "unit-banks-probe-plan.json")
    prepared = read(FOLDER / "unit-banks-probe-requests.json")
    stage = read(FOLDER / "unit-banks-stage-report.json")
    if not plan["candidate_sha256"] == prepared["candidate_sha256"] == stage["candidate_sha256"]:
        raise ValueError("UNIT_AUDIT_SNAPSHOT_MISMATCH")
    questions = {(row["entry_id"], row["bank"]): row for row in plan["questions"]}
    audit, counts = [], {"QUANTITY": Counter(), "WANT": Counter()}
    candidate = args.candidate.resolve(strict=True)
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        relations = _relations(_metadata(conn, "relations"))
        for question in prepared["questions"]:
            payload = question["request"]
            identity, bank = payload["entry_id"], payload["bank"]
            if bank == "BODY":
                continue
            expected = questions[identity, bank]["expected"]
            records = []
            for folder in args.answers:
                path = folder / (question["request_id"] + ".json")
                if not path.exists():
                    continue
                answer = read(path)
                outcome = audit_answer(conn, relations, question, answer, expected)
                records.append({**outcome, "transport_identity": answer["transport_identity"]})
            if not records:
                raise ValueError("UNIT_AUDIT_ANSWER_MISSING:" + identity)
            counts[bank][records[0]["code"]] += 1
            audit.append(
                {
                    "definition": payload["definition"],
                    "bank": bank,
                    "expected": expected,
                    "request_id": question["request_id"],
                    "baseline_known": payload["known"],
                    "outcomes": records,
                }
            )
    result = {
        "format": "gse.unit-banks-audit/1",
        "baseline_sha256": stage["candidate_sha256"],
        "population": stage["population"],
        "stage_rules": stage["rules"],
        "joint_stage": stage["joint"],
        "solver_contradictions": len(stage["contradictions"]),
        "scope_reviews": scope_reviews(stage),
        "primary_audit_outcomes": {bank: dict(value) for bank, value in counts.items()},
        "audits": audit,
        "admission": "UNADMITTED_STAGE_AND_WITHHELD_ANSWERS",
        "lexicon_writes": False,
    }
    with (FOLDER / "unit-banks-audit.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key not in {"audits", "scope_reviews"}}))


if __name__ == "__main__":
    main()
