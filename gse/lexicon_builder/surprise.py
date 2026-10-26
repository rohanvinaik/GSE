"""Compare emitted sparse artifacts with independent reference profiles.

No reference answer enters construction. Missing source expressions produce
addition challenges, never automatic silence laws or rule demotion.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from gse.lexicon_builder.artifact import read_sparse
from gse.lexicon_builder.sources import sha256


def comparison_status(expected: str, actual: str) -> str:
    """Two-sided comparison; unresolved is neither absence nor an asserted sign."""
    if not isinstance(expected, str) or expected not in {"+1", "-1", "0", "empty"}:
        return "INVALID_REFERENCE_STATE"
    if not isinstance(actual, str) or actual not in {"+1", "-1", "0", "empty", "unresolved", "conflict"}:
        return "INVALID_ACTUAL_STATE"
    if actual == "conflict":
        return "SOURCE_CONFLICT"
    if actual == "unresolved":
        return "UNRESOLVED_REFERENCE_COMPONENT" if expected in {"+1", "-1"} else "UNRESOLVED_REFERENCE_STATE"
    if actual == expected:
        return "AGREES"
    if expected in {"+1", "-1"}:
        return "FALSE_OMISSION" if actual in {"empty", "0"} else "WRONG_POLE"
    if actual in {"+1", "-1"}:
        return "ADDITION_CHALLENGE" if expected == "empty" else "FALSE_ADDITION"
    return "ZERO_SILENCE_DISAGREEMENT"


def compare_artifact(path: Path, references: dict) -> dict:
    by_word: dict[str, list[dict]] = defaultdict(list)
    for record in read_sparse(path):
        by_word[record["word"]].append(record)
    outcomes: dict[str, Counter] = defaultdict(Counter)
    ledger = []
    for word, reference in references.items():
        family = reference["class"]
        rule_id = {"adjective_fear": "EMOTION_FEAR_ADJ", "noun_fear": "EMOTION_FEAR_NOUN"}.get(family)
        aligned = [r for r in by_word.get(word, []) if rule_id is not None and r.get("rule_id") == rule_id]
        if not aligned:
            code = "UNIMPLEMENTED_PROJECTION" if word in by_word else "NO_SPARSE_READING_IN_INPUT"
            outcomes[family][code] += 1
            ledger.append({"word": word, "class": family, "code": code, "source": reference["source"]})
            continue
        expected = {c: str(v) if v <= 0 else "+1" for c, v in reference["written_coordinates"].items()}
        expected.update(dict.fromkeys(reference.get("open_coordinates_silent_in_the_explication", []), "empty"))
        for record in aligned:
            for coordinate, value in expected.items():
                cell = record["cells"][coordinate]
                code = comparison_status(value, cell["state"])
                outcomes[family][code] += 1
                evidence = record["provenance"]
                ledger.append(
                    {
                        "word": word,
                        "reading_id": record["reading_id"],
                        "class": family,
                        "coordinate": coordinate,
                        "expected": value,
                        "actual": cell["state"],
                        "code": code,
                        "source": reference["source"],
                        "rule_id": record["rule_id"],
                        "source_record_ids": evidence["source_record_ids"],
                        "applicable_rules": evidence["fired_rules"],
                        "coordinate_trace": [t for t in evidence["trace"] if t.get("coordinate") == coordinate],
                    }
                )
    return {
        "schema": "GSE_LEXICON_SURPRISE_V1",
        "input_sha256": sha256(path),
        "scope": "SOURCE_PROJECTION_COMPARISON; NOT_HELD_OUT_FOR_TEMPLATE_DERIVATION",
        "outcomes_by_class": {c: dict(v) for c, v in outcomes.items()},
        "ledger": ledger,
        "policy": "Diagnose wrong link, projection, missing law or conditional exception before model use. Reference absence does not prove silence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit-sparse"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.gold.read_text())
    report = compare_artifact(args.input, source["gold_from_published_explications"])
    report["reference_sha256"] = sha256(args.gold)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "surprises.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["outcomes_by_class"], indent=2))
    return (
        1
        if any(
            v.get(code, 0)
            for v in report["outcomes_by_class"].values()
            for code in ("FALSE_OMISSION", "FALSE_ADDITION", "WRONG_POLE", "SOURCE_CONFLICT")
        )
        else 0
    )
