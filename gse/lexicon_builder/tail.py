"""Explicit, diagnosed tail tasks; unresolved cells alone never spend a model call."""

from __future__ import annotations

import argparse
import hashlib
import json
from functools import partial
from pathlib import Path

from gse.lexicon_builder.artifact import read_sparse
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Resolution, legal_domain
from gse.lexicon_builder.model import OllamaSelector
from gse.lexicon_builder.reading import CoordinateDecision, ReadingSeed


def nominated_components(source_rule: dict) -> list[str]:
    """F151/F152: DO, IF and KNOW are per-word Fear choices, not class entailments.

    Nomination is independent of any word's published answer. It changes no
    domain or sign and applies to every located member of the admitted source
    class, including members absent from the evaluation references.
    """
    optional = ("DO", "IF", "KNOW") if source_rule["rule_id"] == "EMOTION_FEAR_ADJ" else ()
    return list(dict.fromkeys([*source_rule.get("residual", []), *optional]))


class BudgetedSelector(OllamaSelector):
    """A per-run call ceiling; abstention and failed requests also spend a call."""

    def __init__(self, backend: OllamaSelector, limit: int):
        if type(limit) is not int or limit < 0:
            raise ValueError("INVALID_MODEL_BUDGET")
        self.backend = backend
        self.limit = limit
        self.used = 0

    @property
    def available(self) -> bool:
        return self.used < self.limit

    def select(self, payload: dict, options: dict[str, list[str]]) -> dict:
        if not self.available:
            raise ValueError("BUDGET_EXHAUSTED")
        self.used += 1
        return self.backend.select(payload, options)


def task_id(task: dict) -> str:
    return hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()


def tail_task_status(task: dict) -> str:
    """Validate a bounded decision; every rule-surviving lexical state is legal."""
    if not isinstance(task, dict):
        return "MALFORMED_TASK"
    if set(task) != {"reading_id", "coordinate", "options", "reason", "source_record_ids"}:
        return "FIELD_MISMATCH"
    if not isinstance(task["reading_id"], str) or not task["reading_id"]:
        return "MISSING_READING"
    coordinate = task["coordinate"]
    if not isinstance(coordinate, str) or coordinate not in CANONICAL_COORDINATES:
        return "UNKNOWN_COORDINATE"
    if not isinstance(task["reason"], str) or task["reason"] not in {
        "UNRESOLVED_COMPONENT",
        "CONDITIONAL_RULE_DISAGREEMENT",
        "SOURCE_ALIGNMENT_DISAGREEMENT",
    }:
        return "UNDIAGNOSED_TASK"
    options = task["options"]
    if not isinstance(options, list) or not 2 <= len(options) <= 4 or any(not isinstance(v, str) for v in options):
        return "MALFORMED_OPTIONS"
    if len(set(options)) != len(options) or any(v not in legal_domain(coordinate) for v in options):
        return "ILLEGAL_OPTIONS"
    records = task["source_record_ids"]
    if not isinstance(records, list) or not records or any(not isinstance(v, str) or not v for v in records):
        return "MISSING_SOURCE_EVIDENCE"
    return "VALID_TAIL_TASK"


def _payload(seed: ReadingSeed, task: dict, state: Resolution) -> dict:
    return {
        "schema": "GSE_DIAGNOSED_TAIL_V1",
        "word": seed.word,
        "reading_id": seed.reading_id,
        "reason": task["reason"],
        "source_record_ids": task["source_record_ids"],
        "facts": [
            {"field": o.field, "value": o.value, "source": o.source, "record_id": o.record_id}
            for o in seed.observations
        ],
        "fixed_coordinates": {c: v.value for c, v in state.forced().items()},
        "coordinate": task["coordinate"],
        "surviving_domain": [v.value for v in state.domains[task["coordinate"]]],
        "scope": "TARGET_READING_OWN_DEFINITION; NO_GOLD_OR_BLANKET_MASK_CLOSURE",
        "native_observations": seed.context,
    }


def attach_tail(seed: ReadingSeed, tasks: list[dict]) -> ReadingSeed:
    # An explicit queue replaces all recipe-level model dispatch, including review
    # and bank fill. Unqueued work must never spend the queue's budget.
    seed.decisions = []
    seed.fill = None
    seed.review = None
    for task in tasks:
        status = tail_task_status(task)
        if status != "VALID_TAIL_TASK":
            raise ValueError(status)
        if task["reading_id"] == seed.reading_id:
            established = {record for o in seed.observations for record in o.record_id.split("+")}
            if not set(task["source_record_ids"]) <= established:
                raise ValueError("UNBOUND_SOURCE_EVIDENCE")
            seed.decisions.append(
                CoordinateDecision(
                    task["coordinate"], partial(_payload, seed, task), tuple(task["options"]), task_id(task), True
                )
            )
    return seed


def plan_tail(path: Path, max_tasks: int = 256, max_per_reading: int = 2) -> list[dict]:
    """Only projector-nominated components, bounded independently of any gold."""
    if any(type(n) is not int or n < 0 for n in (max_tasks, max_per_reading)):
        raise ValueError("INVALID_TAIL_LIMIT")
    tasks = []
    seen = set()
    for record in read_sparse(path):
        sources = record["provenance"]["source_record_ids"]
        if not sources:
            continue
        nominated = record.get("residual_coordinates", [])
        if not isinstance(nominated, list) or any(c not in CANONICAL_COORDINATES for c in nominated):
            raise ValueError("INVALID_RESIDUAL_COORDINATES")
        emitted = 0
        for coordinate in sorted(set(nominated), key=lambda c: (len(record["cells"][c]["domain"]), c)):
            cell = record["cells"][coordinate]
            identity = (record["reading_id"], coordinate)
            if len(tasks) >= max_tasks:
                return tasks
            if emitted >= max_per_reading:
                break
            if cell["state"] == "unresolved" and identity not in seen:
                emitted += 1
                seen.add(identity)
                tasks.append(
                    {
                        "reading_id": record["reading_id"],
                        "coordinate": coordinate,
                        "options": cell["domain"],
                        "reason": "UNRESOLVED_COMPONENT",
                        "source_record_ids": sources,
                    }
                )
    return tasks


def tail_ledger(tasks: list[dict], decisions: list[dict]) -> list[dict]:
    """Every queued task has a disposition, even if no reading matched it."""
    by_id = {d["task_id"]: d for d in decisions if d.get("task_id") is not None}
    return [
        {"task": task, **by_id.get(task_id(task), {"task_id": task_id(task), "code": "UNMATCHED_READING"})}
        for task in tasks
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan-tail"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tasks", type=int, default=256)
    parser.add_argument("--max-per-reading", type=int, default=2)
    args = parser.parse_args()
    tasks = plan_tail(args.input, args.max_tasks, args.max_per_reading)
    args.output.write_text(json.dumps(tasks, indent=2) + "\n")
    print(json.dumps({"tasks": len(tasks), "selection_basis": "CONSTRUCTION_RESIDUALS; NO_GOLD_INPUT"}))
    return 0
