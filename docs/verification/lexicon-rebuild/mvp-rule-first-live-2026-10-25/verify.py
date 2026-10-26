"""Report exact MVP reading checks; these fixtures are never builder inputs.

Run from the GSE repository: uv run python <this file>.
The fixtures are authored acceptance expectations, not independent linguistic gold.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from gse.lexicon_builder.artifact import read_vectors
from gse.lexicon_builder.core import CANONICAL_COORDINATES


def main() -> int:
    root = Path(__file__).parent
    cases_path = root / "cases.json"
    cases = json.loads(cases_path.read_text())
    native = {r["word"]: r for r in map(json.loads, (root / "words.jsonl").read_text().splitlines())}
    vectors = list(read_vectors(root / "vectors.jsonl"))
    results = []
    for case in cases["cases"]:
        word = case["word"]
        record = native.get(word)
        candidates = [
            r for r in vectors if r["word"] == word and r["provenance"]["rule_id"] == case["rule_id"]
        ]
        if record is None:
            results.append({"word": word, "code": "UNAVAILABLE", "reason": "NO_BUILD_RECORD"})
            continue
        if not candidates:
            readings = [r for r in record["readings"] if r.get("rule_id") == case["rule_id"]]
            results.append(
                {
                    "word": word,
                    "code": "PARTIAL",
                    "reason": "NO_COMPLETE_CANDIDATE",
                    "open_readings": [
                        {"reading_id": r["reading_id"], "omission": r.get("omission_challenge")} for r in readings
                    ],
                }
            )
            continue
        if len(candidates) != 1:
            results.append({"word": word, "code": "WRONG", "reason": "AMBIGUOUS_CASE_SCOPE"})
            continue
        actual = candidates[0]
        expected = dict.fromkeys(CANONICAL_COORDINATES, "empty")
        expected.update(case["expected_written"])
        differences = {
            c: {"expected": expected[c], "actual": actual["states"][c]}
            for c in CANONICAL_COORDINATES
            if expected[c] != actual["states"][c]
        }
        results.append(
            {
                "word": word,
                "reading_id": actual["reading_id"],
                "code": "WRONG" if differences else "IDENTIFIED",
                "differences": differences,
                "written": {c: value for c, value in actual["states"].items() if value != "empty"},
                "silent_count": sum(value == "empty" for value in actual["states"].values()),
                "review_status": actual["review_status"],
            }
        )
    for word in cases["unmatched_controls"]:
        emitted = [r for r in vectors if r["word"] == word]
        results.append(
            {
                "word": word,
                "code": "UNAVAILABLE" if word not in native else "WRONG" if emitted else "ABSTAINED",
                "reason": "UNSUPPORTED_READING_MUST_NOT_RECEIVE_A_COMPLETE_VECTOR",
            }
        )
    counts = Counter({code: 0 for code in ["IDENTIFIED", "WRONG", "PARTIAL", "ABSTAINED", "UNAVAILABLE"]})
    counts.update(r["code"] for r in results)
    number_checks = []
    for case in cases.get("number_checks", []):
        observed = json.loads((root / case["file"]).read_text())
        valid = (
            observed["input_sha256"] == hashlib.sha256((root / "vectors.jsonl").read_bytes()).hexdigest()
            and observed["code"] == case["expected_code"]
            and observed["coordinate_changes"] == []
        )
        if "expected_relation" in case:
            valid = valid and observed.get("relation") == case["expected_relation"]
        if case["expected_code"] != "RESOLVED_RELATIVE_NUMBER":
            valid = valid and observed["number_values"] is None and observed["model_calls"] == []
        if case.get("no_model"):
            valid = valid and observed["model_calls"] == []
        number_checks.append({"file": case["file"], "code": "IDENTIFIED" if valid else "WRONG"})
    report = {
        "reference_status": cases["reference_status"],
        "scope": "Exact 58-state checks of declared MVP readings; not all senses or calibrated NUMBER values",
        "outcomes": dict(counts),
        "results": results,
        "number_checks": number_checks,
        "files": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ["cases.json", "words.jsonl", "vectors.jsonl", "manifest.json"]
        },
    }
    (root / "semantic-check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"outcomes": report["outcomes"], "results": results, "number_checks": number_checks}, indent=2))
    # This reports mismatches, not full-build completion. Partial counts stay explicit.
    return (
        1
        if counts["WRONG"] or any(r["code"] == "WRONG" for r in number_checks)
        else 2
        if counts["UNAVAILABLE"] or not counts["IDENTIFIED"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
