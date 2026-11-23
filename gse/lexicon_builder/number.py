"""Bounded relative NUMBER values over an unchanged intensity-bearing vector.

Pair ordinals express order, not distance or a globally calibrated gain. The
model supplies two typed comparisons; symbolic inversion checks their coherence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gse.lexicon_builder.artifact import read_vectors
from gse.lexicon_builder.model import DEFAULT_MODEL, OllamaSelector
from gse.lexicon_builder.sources import sha256

ORDER_INVERSE = {"LESS": "MORE", "EQUAL": "EQUAL", "MORE": "LESS"}
ORDER_CODES = ["LESS", "EQUAL", "MORE", "UNRESOLVED"]


def paired_order_status(forward: str, reverse: str) -> str:
    """A direction change in the question must invert the proposed relation."""
    if forward not in ORDER_CODES or reverse not in ORDER_CODES:
        return "ILLEGAL_ORDER_CODE"
    if "UNRESOLVED" in (forward, reverse):
        return "UNRESOLVED_ORDER"
    if ORDER_INVERSE[forward] != reverse:
        return "CONTRADICTORY_ORDER"
    return "VALID_RELATIVE_ORDER"


def pair_precondition(left: dict, right: dict) -> str:
    """Only a shared signed pattern and scale domain admit this operation."""
    if left["states"] != right["states"] or left["mask"] != right["mask"]:
        return "INCOMPATIBLE_PATTERN"
    if left["states"]["INTENSITY"] != "+1":
        return "NO_INTENSITY_DOMAIN"
    if left["number_scale"]["family"] != right["number_scale"]["family"]:
        return "INCOMPATIBLE_SCALE_DOMAIN"
    return "REFLEXIVE_EQUALITY" if left["reading_id"] == right["reading_id"] else "COMPARABLE"


def resolve_number_pair(left: dict, right: dict, selector: OllamaSelector) -> dict:
    precondition = pair_precondition(left, right)
    result = {
        "schema": "GSE_RELATIVE_NUMBER_V1",
        "scope": "PAIR_ORDINAL; NOT_DISTANCE_OR_GLOBAL_GAIN",
        "left": left["reading_id"],
        "right": right["reading_id"],
        "code": precondition,
        "model_calls": [],
        "number_values": None,
        "numeric_gain": None,
        "production_eligible": False,
        "coordinate_changes": [],
    }
    if precondition not in {"COMPARABLE", "REFLEXIVE_EQUALITY"}:
        return result
    if precondition == "REFLEXIVE_EQUALITY":
        order = "EQUAL"
    else:
        answers = []
        for first, second in [(left, right), (right, left)]:
            payload = {
                "schema": "GSE_NUMBER_RELATIVE_ORDER_V1",
                "operation": "COMPARE_RELATIVE_INTENSITY_OF_THE_SAME_DEFINITION_PATTERN",
                "domain": left["number_scale"]["family"],
                "left": {
                    "word": first["word"],
                    "reading_id": first["reading_id"],
                    "source_ordinal": first["number_scale"]["native_ordinal_rank"],
                },
                "right": {
                    "word": second["word"],
                    "reading_id": second["reading_id"],
                    "source_ordinal": second["number_scale"]["native_ordinal_rank"],
                },
                "shared_written_coordinates": {c: v for c, v in first["states"].items() if v != "empty"},
                "invariant": "NO_CHANGE_TO_ANY_COORDINATE_SIGN_OR_MASK",
                "decision": {"LEFT_INTENSITY_RELATIVE_TO_RIGHT": None},
                "comparison_codes": {
                    "LESS": "left measure < right measure",
                    "EQUAL": "same degree",
                    "MORE": "left measure > right measure",
                    "UNRESOLVED": "degree relation cannot be resolved",
                },
            }
            call = selector.select(payload, {"LEFT_INTENSITY_RELATIVE_TO_RIGHT": ORDER_CODES})
            result["model_calls"].append(call)
            answers.append(call["answer"]["LEFT_INTENSITY_RELATIVE_TO_RIGHT"])
        status = paired_order_status(*answers)
        result["code"] = status
        if status != "VALID_RELATIVE_ORDER":
            return result
        order = answers[0]
    pair = sorted([left["reading_id"], right["reading_id"]])
    result.update(
        {
            "code": "RESOLVED_RELATIVE_NUMBER",
            "relation": order,
            "scale_id": "PAIR_" + hashlib.sha256(json.dumps(pair).encode()).hexdigest()[:16],
            "number_values": {"left": 0 if order != "MORE" else 1, "right": 0 if order != "LESS" else 1},
            "authority": "ATOMIC_EQUALITY"
            if precondition == "REFLEXIVE_EQUALITY"
            else "MODEL_CANDIDATE_INVERSION_CHECKED",
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["number-order"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--left", required=True, help="word or exact reading ID; must identify one candidate")
    parser.add_argument("--right", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = list(read_vectors(args.input))
    chosen = []
    for name in [args.left, args.right]:
        matches = [r for r in records if name in (r["word"], r["reading_id"])]
        if len(matches) != 1:
            parser.error(f"{name}: expected one complete reading, found {len(matches)}")
        chosen.append(matches[0])
    result = resolve_number_pair(*chosen, OllamaSelector(args.model))
    result["input_sha256"] = sha256(args.input)
    result["implementation"] = {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ["code", "left", "right", "number_values"]}, indent=2))
    return 0 if result["code"] == "RESOLVED_RELATIVE_NUMBER" else 2
