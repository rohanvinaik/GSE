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

from GSE.api import GSEEncoder
from GSE.discourse.speech import encode_document_utterance_events
from GSE.symbolic import emit_contract, negation_signs, resolve_references
from GSE.symbolic.queries import is_logically_equal_to

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
    ("single_degree", "The dog is very good.", "TYPE_ASSERT"),
    ("repeated_degree", "The dog is very very good.", "TYPE_ASSERT"),
    ("extreme_degree", "The dog is extremely good.", "TYPE_ASSERT"),
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
ORDINAL_ANCHOR_RECORD = "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#ordinal-stability"


def ordinal_anchor_isolation(entry):
    """Check anchor provenance, without requiring unrelated senses to stay unknown.

    A later definition-scoped ruling may legitimately resolve INTENSITY. This
    probe only checks that the two approved degree anchors were not copied into
    another identity. Whole-build replay checks the remaining proof obligations.
    """
    leaked = [
        record
        for record in entry["trace"]
        if record.get("kind") == "ASSERTION"
        and record.get("bank") == "INTENSITY"
        and record.get("record_id") == ORDINAL_ANCHOR_RECORD
    ]
    return {"outcome": "WRONG" if leaked else "IDENTIFIED", "copied_anchor_assertions": leaked}


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
    trees = {}
    levels = {"not_very_scope": -1, "very_not_scope": 1, "single_degree": 1, "repeated_degree": 2, "extreme_degree": 2}
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
        trees[name] = event["tree"]
        matched = actual == expectations[name]
        if name in {"not_very_scope", "very_not_scope"}:
            expected = "hierarchy_direction" if name == "not_very_scope" else "syntactic_negation"
            matched = matched and any(owner["mechanism"] == expected for owner in signs["owners"])
        if name in levels:
            assertion = predicate["args"][0] if actual == "NOT" else predicate
            matched = matched and assertion.get("features", {}).get("degree") == [
                {"argument": 1, "target": "good", "scale": "INTENSITY", "level": levels[name]}
            ]
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
    for name, left, right, expected in (
        ("repeated_extreme_equivalence", "repeated_degree", "extreme_degree", True),
        ("degree_scope_distinction", "not_very_scope", "very_not_scope", False),
        ("ordinal_distinction", "single_degree", "repeated_degree", False),
    ):
        actual = is_logically_equal_to(trees[left], trees[right]) if left in trees and right in trees else None
        records.append(
            {
                "class": name,
                "expected_equal": expected,
                "actual_equal": actual,
                "outcome": "ABSTAINED" if actual is None else "IDENTIFIED" if actual == expected else "WRONG",
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
                    # Completing an unknown with justified orthogonality is
                    # allowed; object-reference must not become possession.
                    if entry["assignments"].get("HAVE") in {-1, 1}:
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
        record = {"class": "other_very_senses_anchor_isolation", "entry_id": entry_id}
        try:
            selection = encoder.lookup_definition(entry_id)
            if selection["code"] != "IDENTIFIED":
                record.update(outcome="ABSTAINED", selection=selection["code"])
            else:
                entry = selection["selected"]
                domain = entry["domains"].get("INTENSITY")
                record.update(
                    **ordinal_anchor_isolation(entry),
                    intensity_domain=domain,
                    hierarchy=entry["hierarchy"],
                    property="Approved ordinal anchors are confined to their exact definition identities.",
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
        "format": "GSE.runtime-compatibility-audit/1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "lexicon_db": str(path),
        "file_identity": {"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns},
        "scope": {
            "structure": "Fourteen hand-authored top-operation probes; degree cases also check emitted levels, scope and logical comparison. Not full semantic gold.",
            "anchors": "Explicit founder-approved definition IDs, signed bases, ordinal 1/2, and sense isolation.",
            "genealogy": "EXPLICIT_NULL_GENEALOGY",
            "world_grounding": "UNVERIFIED",
            "corpus_semantic_accuracy": "NOT_MEASURED",
            "degree_composition": "Canonical adjective degree, signed scope, repeated-VERY/extremely equivalence and ordinal distinction; not exhaustive grammar coverage.",
        },
        "by_class": {name: dict(outcomes) for name, outcomes in sorted(counts.items())},
        "records": records,
    }


def audit_sparse_runtime(lexicon_db):
    """Check the production encoder's exact selection and abstention cases."""
    from GSE.api.encoder import GrammaticalDefinitionError
    from GSE.symbolic.expression import from_trace

    report = audit_runtime(lexicon_db)
    checks = (
        ("The river rose above the bank.", "bank", "wordnet:bank:bank.n.01"),
        ("A bank approved the mortgage.", "bank", "wordnet:bank:depository_financial_institution.n.01"),
        ("I saw a bank.", "bank", None),
        ("An electrician repaired the light.", "light", None),
    )
    results = []
    with GSEEncoder(str(lexicon_db)) as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        for text, lemma, expected in checks:
            token = next((t for t in encoder.encode(text).tokens if t.lemma == lemma), None)
            if token is None:
                results.append({"text": text, "expected": expected, "code": "MISSING_TOKEN", "passed": False})
                continue
            evidence = token.lexical_evidence
            observed = (evidence.get("selected_record") or {}).get("entry_id")
            accepted = observed == expected and (
                evidence.get("selection_status") == "AMBIGUOUS" and not token.word_primitives
                if expected is None
                else evidence.get("contextual_grounding", {}).get("code") == "EXACT_WORDNET_SENSE"
            )
            results.append({"text": text, "expected": expected, "observed": observed, "passed": accepted})
        modal_text = "She might leave."
        try:
            modal = encoder.encode(modal_text)
        except GrammaticalDefinitionError as error:
            results.append(
                {"text": modal_text, "code": "GRAMMATICAL_DEFINITION_ERROR", "error": str(error), "passed": False}
            )
        else:
            modal_token = next((t for t in modal.tokens if t.lemma == "might"), None)
            selected = modal_token.lexical_evidence.get("selected_record") if modal_token else None
            observed = selected.get("entry_id") if selected else None
            results.append(
                {"text": modal_text, "observed": observed, "passed": observed == "gse_closed_class:modal:might"}
            )
        for text, expected in (("I waited for some time.", "unspecified"), ("I waited for a long time.", "long")):
            expression = from_trace(encoder.encode(text))
            duration = getattr(expression, "duration", None)
            observed = (duration.extent, duration.relation) if duration is not None else None
            results.append({"text": text, "observed": observed, "passed": observed == (expected, "during")})
    report["sparse_controls"] = results
    report["code"] = (
        "SPARSE_RUNTIME_VALIDATED"
        if (
            all(row["passed"] for row in results)
            and all(set(group) == {"IDENTIFIED"} for group in report["by_class"].values())
        )
        else "SPARSE_RUNTIME_REJECTED"
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon-db", required=True, type=Path)
    parser.add_argument("--report", type=Path, help="Save the JSON report; otherwise print it.")
    parser.add_argument("--sparse", action="store_true", help="Include exact sense and ambiguity controls")
    args = parser.parse_args(argv)
    if args.report is not None and args.report.resolve() == args.lexicon_db.resolve():
        parser.error("REPORT_MUST_NOT_REPLACE_LEXICON")
    report = (audit_sparse_runtime if args.sparse else audit_runtime)(args.lexicon_db)
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.report is None:
        print(payload, end="")
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload)
        print(json.dumps({"report": str(args.report.resolve()), "by_class": report["by_class"]}))
    return 2 if report.get("code") == "SPARSE_RUNTIME_REJECTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
