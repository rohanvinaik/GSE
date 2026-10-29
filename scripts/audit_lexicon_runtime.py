#!/usr/bin/env python3
"""Finite runtime compatibility probes, not a corpus-wide semantic gold evaluation.

Run with --lexicon-db PATH [--report PATH]. The database is queried only;
world grounding is deliberately unverified using the public empty provider.
Successful report generation exits zero regardless of the measured outcomes.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gse.api import GSEEncoder
from gse.discourse.speech import encode_document_utterance_events
from gse.symbolic import emit_contract, negation_signs, resolve_references

PROBES = (
    ("event", "Alice helps Bob.", "EVENT"),
    ("causal", "Alice helps Bob because Bob helps Carol.", "CAUSATION"),
    ("coordination", "Alice helps Bob and Carol helps Dave.", "CLAUSE_COORD"),
    ("comparison", "The dog is bigger than the cat.", "COMPARISON"),
    ("restriction", "Only the dog runs.", "SET_RESTRICT"),
    ("control", "Alice wants to leave.", "CONTROL"),
    ("temporal", "When Alice leaves, Bob sleeps.", "TEMPORAL"),
    ("demonstrative", "This is a dog.", "TYPE_ASSERT"),
    ("negation", "Alice does not help Bob.", "NOT"),
    ("not_very_scope", "The dog is not very good.", "TYPE_ASSERT"),
    ("very_not_scope", "The dog is very not good.", "NOT"),
)
ANCHORS = (
    ("this_object", "gse:prime:this", "SOMETHING", 1, None),
    ("want_positive", "wordnet:want:desire.v.01", "WANT", 1, None),
    ("want_negative", "gse:prime:dont-want", "WANT", -1, None),
    ("very_degree", "wordnet:very:very.r.01", "INTENSITY", 1, 1),
    ("extremely_degree", "wordnet:extremely:extremely.r.02", "INTENSITY", 1, 2),
)
OTHER_VERY_IDS = (
    "wordnet:very:identical.s.02",
    "wordnet:very:very.r.02",
    "wordnet:very:very.s.01",
)


def anchor_outcome(selection, bank, value, level):
    """Missing evidence abstains; an evidenced contradiction is wrong."""
    if selection["code"] != "IDENTIFIED":
        return "ABSTAINED"
    entry = selection["selected"]
    assignments = entry["assignments"]
    hierarchy = entry["hierarchy"]
    if bank in assignments and assignments[bank] != value:
        return "WRONG"
    if level is not None and bank in hierarchy and hierarchy[bank] != level:
        return "WRONG"
    if bank not in assignments or (level is not None and bank not in hierarchy):
        return "ABSTAINED"
    return "IDENTIFIED"


def _structure(encoder):
    expectations = {name: operation for name, _, operation in PROBES}
    records = []
    for event in encode_document_utterance_events(encoder, [{"id": name, "text": text} for name, text, _ in PROBES]):
        if event["type"] != "utterance":
            continue
        name = event["source_sentence_id"]
        record = {"class": name, "text": event["content"], "expected_top_operation": expectations[name]}
        if event["state"] != "read" or event["tree"] is None:
            records.append({**record, "outcome": "ABSTAINED", "error": event["error"]})
            continue
        # Explicit DB-free genealogy: this exercises the public v2 emit shape,
        # and never silently claims that real world grounding was verified.
        contract = emit_contract(resolve_references(event["tree"]))
        predicate = contract["predicate"]
        actual = predicate.get("op") if isinstance(predicate, dict) else None
        signs = negation_signs(event["trace"])
        matched = actual == expectations[name]
        if name in {"not_very_scope", "very_not_scope"}:
            expected = "hierarchy_direction" if name == "not_very_scope" else "syntactic_negation"
            matched = matched and any(owner["mechanism"] == expected for owner in signs["owners"])
        records.append(
            {
                **record,
                "outcome": "IDENTIFIED" if matched else "WRONG",
                "actual_top_operation": actual,
                "contract": contract,
                "sign_owners": signs["owners"],
                "structural_loss": event["structural_loss"],
                "lexical_selection_counts": dict(
                    Counter(
                        token.lexical_evidence.get("selection_status", token.lexical_evidence["state"])
                        for token in event["trace"].tokens
                    )
                ),
            }
        )
    return records


def _definitions(encoder):
    records, degree_vectors = [], {}
    for name, entry_id, bank, value, level in ANCHORS:
        record = {"class": name, "entry_id": entry_id, "expected_bank": bank, "expected_value": value}
        if level is not None:
            record["expected_hierarchy"] = level
        try:
            selection = encoder.lookup_definition(entry_id)
            outcome = anchor_outcome(selection, bank, value, level)
            record.update(outcome=outcome, selection=selection["code"])
            if selection["code"] == "IDENTIFIED":
                entry = selection["selected"]
                vector = encoder.encode_definition(entry_id)
                record.update(assignments=entry["assignments"], hierarchy=entry["hierarchy"], vector_nnz=vector.nnz)
                if outcome == "IDENTIFIED":
                    base = encoder.word_basis.get_primitive(bank)
                    if base is None:
                        raise ValueError("ANCHOR_BASE_UNAVAILABLE")
                    signed = base.negate() if value == -1 else base
                    # Hierarchy markers share INTENSITY's vector bank. For degree
                    # anchors, the signed semantic assignment is the invariant;
                    # extra marker positions are deliberately part of the vector.
                    preserved = (
                        entry["assignments"][bank] == value
                        if level is not None
                        else np.array_equal(vector.with_bank_only(base.bank).to_dense(), signed.to_dense())
                    )
                    record["signed_base_preserved"] = bool(preserved)
                    if not preserved or vector.nnz == 0:
                        record["outcome"] = "WRONG"
                    if level is not None and record["outcome"] == "IDENTIFIED":
                        degree_vectors[name] = vector.to_dense()
                if name == "this_object":
                    record["have_domain"] = entry["domains"].get("HAVE")
                    if record["have_domain"] != [-1, 0, 1]:
                        record["outcome"] = "WRONG"
        except (ValueError, RuntimeError) as error:
            record.update(outcome="ABSTAINED", error=str(error))
        records.append(record)
    records.append(
        {
            "class": "degree_vector_distinction",
            "outcome": "ABSTAINED"
            if len(degree_vectors) != 2
            else "WRONG"
            if np.array_equal(degree_vectors["very_degree"], degree_vectors["extremely_degree"])
            else "IDENTIFIED",
            "property": "Two approved nonzero degree vectors differ while retaining their positive base.",
        }
    )
    for entry_id in OTHER_VERY_IDS:
        record = {"class": "other_very_senses_unknown", "entry_id": entry_id}
        try:
            selection = encoder.lookup_definition(entry_id)
            if selection["code"] != "IDENTIFIED":
                record.update(outcome="ABSTAINED", selection=selection["code"])
            else:
                entry = selection["selected"]
                domain = entry["domains"].get("INTENSITY")
                record.update(
                    outcome="IDENTIFIED" if domain == [-1, 0, 1] and not entry["hierarchy"] else "WRONG",
                    intensity_domain=domain,
                    hierarchy=entry["hierarchy"],
                )
        except ValueError as error:
            record.update(outcome="ABSTAINED", error=str(error))
        records.append(record)
    return records


def audit_runtime(lexicon_db):
    path = Path(lexicon_db).expanduser().resolve()
    with GSEEncoder(str(path)) as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        records = _structure(encoder) + _definitions(encoder)
    counts = defaultdict(Counter)
    for record in records:
        counts[record["class"]][record["outcome"]] += 1
    return {
        "format": "gse.runtime-compatibility-audit/1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "lexicon_db": str(path),
        "file_identity": {"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns},
        "scope": {
            "structure": "Eleven hand-authored top-operation probes; two also check sign ownership. Not full semantic gold.",
            "anchors": "Explicit founder-approved definition IDs, signed bases, ordinal 1/2, and sense isolation.",
            "genealogy": "EXPLICIT_NULL_GENEALOGY",
            "world_grounding": "UNVERIFIED",
            "corpus_semantic_accuracy": "NOT_MEASURED",
            "degree_composition": "Only not-very versus very-not scope; repeated-VERY normalization is not measured.",
        },
        "by_class": {name: dict(outcomes) for name, outcomes in sorted(counts.items())},
        "records": records,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon-db", required=True, type=Path)
    parser.add_argument("--report", type=Path, help="Save the JSON report; otherwise print it.")
    args = parser.parse_args(argv)
    if args.report is not None and args.report.resolve() == args.lexicon_db.resolve():
        parser.error("REPORT_MUST_NOT_REPLACE_LEXICON")
    report = audit_runtime(args.lexicon_db)
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.report is None:
        print(payload, end="")
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload)
        print(json.dumps({"report": str(args.report.resolve()), "by_class": report["by_class"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
