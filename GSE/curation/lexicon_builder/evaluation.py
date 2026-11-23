"""Compare published definition coordinates to explicitly supplied gold labels.

Gold is never inferred from this build, source agreement, or model outputs.
Source groups are overlapping cohorts of exact-linked evidence, not claims that
each source caused a prediction. Replay validation remains a separate check.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from GSE.namespace import current_id

from .foundation import BANKS, definition_context
from .interchange import read_json
from .storage import VERSION, read_entries

OUTCOMES = ("IDENTIFIED_CORRECT", "ABSTAINED", "CONFLICT", "WRONG", "NOT_FOUND")


def _load_gold(path: Path) -> tuple[list[dict], bool]:
    raw = read_json(path)
    if not isinstance(raw, dict) or set(raw) != {"format", "records"} or current_id(raw["format"]) != "GSE.lexicon-gold/1":
        raise ValueError("INVALID_GOLD_FORMAT")
    records = raw["records"]
    if not isinstance(records, list) or not records:
        raise ValueError("EMPTY_OR_INVALID_GOLD_RECORDS")
    seen = set()
    weighted = []
    for record in records:
        if not isinstance(record, dict) or not {"entry_id", "bank", "expected"} <= set(record):
            raise ValueError("INVALID_GOLD_RECORD")
        if set(record) - {"entry_id", "bank", "expected", "weight"}:
            raise ValueError("UNKNOWN_GOLD_FIELD")
        if type(record["entry_id"]) is not str or not record["entry_id"].strip():
            raise ValueError("INVALID_GOLD_DEFINITION_ID")
        if type(record["bank"]) is not str or record["bank"] not in BANKS:
            raise ValueError("UNKNOWN_GOLD_BANK")
        if type(record["expected"]) is not int or record["expected"] not in {-1, 0, 1}:
            raise ValueError("INVALID_GOLD_TRIT")
        key = (record["entry_id"], record["bank"])
        if key in seen:
            raise ValueError("DUPLICATE_GOLD_CELL")
        seen.add(key)
        weighted.append("weight" in record)
        if "weight" in record:
            weight = record["weight"]
            try:
                valid = type(weight) in (int, float) and math.isfinite(weight) and weight >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("INVALID_GOLD_WEIGHT")
    if any(weighted) and not all(weighted):
        raise ValueError("INCOMPLETE_GOLD_WEIGHTS")
    if all(weighted):
        try:
            math.fsum(record["weight"] for record in records)
        except OverflowError as error:
            raise ValueError("INVALID_TOTAL_GOLD_WEIGHT") from error
    return sorted(records, key=lambda record: (record["entry_id"], record["bank"])), all(weighted)


def _source_index(conn: sqlite3.Connection, entry_ids: set[str]) -> dict[str, list[str]]:
    """Scan unindexed observation linkage once, not once per gold cell."""
    sources = {entry_id: set() for entry_id in entry_ids}

    def add(entry_id, source):
        if type(source) is not str or not source.strip():
            raise ValueError("INVALID_BUILD_SOURCE")
        sources[entry_id].add(source)

    for entry_id, source in conn.execute("SELECT entry_id,source FROM source_observations"):
        if entry_id in sources:
            add(entry_id, source)
    for entry_id, raw in conn.execute("SELECT entry_id,payload FROM builder_assertions"):
        if entry_id in sources:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("INVALID_BUILD_ASSERTION")
            add(entry_id, payload.get("source"))
    return {entry_id: sorted(values) if values else ["NO_LINKED_SOURCE"] for entry_id, values in sources.items()}


def _cell(conn: sqlite3.Connection, gold: dict, cache: dict, source_index: dict) -> dict:
    entry_id, bank = gold["entry_id"], gold["bank"]
    if entry_id not in cache:
        entries = read_entries(conn, entry_id=entry_id)
        if len(entries) > 1:
            raise ValueError("DUPLICATE_BUILD_DEFINITION")
        cache[entry_id] = (entries[0], source_index[entry_id]) if entries else (None, [])
    entry, sources = cache[entry_id]
    result = {**gold, "observed": None, "pos": None, "sources": sources}
    if entry is None:
        result["code"] = "NOT_FOUND"
        return result
    if type(entry["pos"]) is not str or not entry["pos"].strip():
        raise ValueError("INVALID_BUILD_POS")
    result["pos"] = definition_context(entry["pos"])["pos"]
    if entry["code"] not in {"PARTIAL", "RESOLVED", "CONFLICT"}:
        raise ValueError("INVALID_BUILD_RESOLUTION")
    assignments = entry["assignments"]
    if any(
        name not in BANKS or type(value) is not int or value not in {-1, 0, 1} for name, value in assignments.items()
    ):
        raise ValueError("INVALID_PUBLISHED_ASSIGNMENT")
    if entry["code"] == "CONFLICT":
        if assignments:
            raise ValueError("CONFLICT_PUBLISHED_ASSIGNMENTS")
        result["code"] = "CONFLICT"
    elif bank not in assignments:
        result["code"] = "ABSTAINED"
    else:
        result["observed"] = assignments[bank]
        result["code"] = "IDENTIFIED_CORRECT" if assignments[bank] == gold["expected"] else "WRONG"
    return result


def _summary(records: list[dict], weighted: bool) -> dict:
    counts = {code: sum(record["code"] == code for record in records) for code in OUTCOMES}
    identified = counts["IDENTIFIED_CORRECT"] + counts["WRONG"]
    result = {
        "total": len(records),
        "outcomes": counts,
        "coverage": {
            "identified": identified,
            "total": len(records),
            "fraction": identified / len(records) if records else None,
        },
    }
    if weighted:
        weights = {
            code: math.fsum(record["weight"] for record in records if record["code"] == code) for code in OUTCOMES
        }
        total = math.fsum(record["weight"] for record in records)
        identified_weight = weights["IDENTIFIED_CORRECT"] + weights["WRONG"]
        result["weighted"] = {
            "total": total,
            "outcomes": weights,
            "coverage": {
                "identified": identified_weight,
                "total": total,
                "fraction": identified_weight / total if total else None,
            },
        }
    return result


def evaluate_build(path: str | Path, gold_path: str | Path) -> dict:
    """Read exact entry/bank labels and return named outcomes without writing files.

    Gold format: ``{"format":"GSE.lexicon-gold/1","records":[
    {"entry_id":"...","bank":"GOOD","expected":0}]}``.
    Optional nonnegative finite ``weight`` must appear on every record or none.
    Coverage counts identified cells (correct plus wrong) over all supplied gold
    cells, including NOT_FOUND. Zero total weight has undefined weighted coverage.
    """
    gold_file = Path(gold_path).expanduser().resolve()
    if not gold_file.is_file():
        raise ValueError("GOLD_NOT_FOUND")
    gold, weighted = _load_gold(gold_file)
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    try:
        with closing(sqlite3.connect(file.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            row = conn.execute("SELECT value FROM builder_metadata WHERE key='format'").fetchone()
            if row is None or current_id(json.loads(row[0])) != VERSION:
                raise ValueError("UNSUPPORTED_BUILD_FORMAT")
            cache = {}
            source_index = _source_index(conn, {record["entry_id"] for record in gold})
            records = [_cell(conn, record, cache, source_index) for record in gold]
    except sqlite3.DatabaseError as error:
        raise ValueError("INVALID_BUILD_DATABASE") from error
    per_bank, per_pos, per_source = defaultdict(list), defaultdict(list), defaultdict(list)
    for record in records:
        per_bank[record["bank"]].append(record)
        per_pos[record["pos"] or "NOT_FOUND"].append(record)
        for source in record["sources"] or ["NOT_FOUND"]:
            per_source[source].append(record)
    return {
        "format": "GSE.lexicon-gold-report/1",
        "code": "GOLD_EVALUATED",
        "gold": {
            "path": str(gold_file),
            "sha256": hashlib.sha256(gold_file.read_bytes()).hexdigest(),
            "origin": "SUPPLIED_LABELS",
        },
        "build": {"path": str(file), "format": VERSION},
        "verification": "PUBLISHED_PROJECTION_ONLY",
        "source_grouping": "OVERLAPPING_EXACT_DEFINITION_EVIDENCE_COHORTS_NOT_CAUSAL_ATTRIBUTION",
        **_summary(records, weighted),
        "per_bank": {key: _summary(values, weighted) for key, values in sorted(per_bank.items())},
        "per_pos": {key: _summary(values, weighted) for key, values in sorted(per_pos.items())},
        "per_source": {key: _summary(values, weighted) for key, values in sorted(per_source.items())},
        "records": records,
    }
