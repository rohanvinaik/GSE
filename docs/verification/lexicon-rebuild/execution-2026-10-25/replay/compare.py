"""Data-only historical replay: immutable inputs, complete domain/provenance ledger.

No builder, model, gold or rule compiler is imported. Classifications describe
set differences, not whether any semantic change is justified. No baseline is
changed. The compressed cell ledger includes every coordinate of every reading
in the union, including unchanged, added and removed reading cells.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    words, readings, structures = {}, {}, {}
    with (root / "words.jsonl").open() as stream:
        for line, record in enumerate(stream, 1):
            record = json.loads(record)
            word = record["word"]
            if word in words:
                raise ValueError("DUPLICATE_WORD:" + word)
            words[word] = {"code": record["code"], "line": line, "native": record["native"]}
            for reading in record["readings"]:
                key = word, reading["reading_id"]
                if key in readings:
                    raise ValueError("DUPLICATE_READING_ID:" + canonical(key))
                domains = reading["after_selection"]["domains"]
                if set(domains) != set(manifest["coordinate_order"]):
                    raise ValueError("INCOMPLETE_COORDINATE_ACCOUNT:" + canonical(key))
                readings[key] = reading
            for structure in record.get("structural_entries", []):
                key = word, structure["reading_id"]
                if key in structures:
                    raise ValueError("DUPLICATE_STRUCTURE_ID:" + canonical(key))
                structures[key] = structure
    return {"manifest": manifest, "words": words, "readings": readings, "structures": structures}


def classify(old: list[str] | None, new: list[str] | None) -> str:
    if old is None:
        return "ADDED_READING_CELL"
    if new is None:
        return "REMOVED_READING_CELL"
    a, b = set(old), set(new)
    if a == b:
        return "UNCHANGED" if old == new else "DOMAIN_ORDER_ONLY"
    if not b:
        return "SETTLED_TO_CONFLICT" if len(a) == 1 else "OPEN_TO_CONFLICT"
    if not a:
        return "CONFLICT_TO_SETTLED" if len(b) == 1 else "CONFLICT_TO_OPEN"
    if len(a) == 1:
        if len(b) == 1:
            return "SETTLED_VALUE_CHANGED"
        return "SETTLED_REOPENED" if a <= b else "SETTLED_REOPENED_EXCLUDING_OLD"
    if len(b) == 1:
        return "OPEN_TO_SETTLED" if b <= a else "OPEN_TO_SETTLED_OUTSIDE_OLD_DOMAIN"
    if b < a:
        return "OPEN_DOMAIN_NARROWED"
    if a < b:
        return "OPEN_DOMAIN_WIDENED"
    return "OPEN_DOMAIN_SHIFTED"


def provenance(reading: dict | None, coordinate: str | None = None) -> dict | None:
    if reading is None:
        return None
    resolution = reading["after_selection"]
    trace = resolution.get("trace", [])
    applications = resolution.get("rule_applications")
    if coordinate is not None:
        trace = [t for t in trace if t.get("coordinate") == coordinate]
        if applications is not None:
            applications = [a for a in applications if coordinate in a.get("coordinates", [])]
    return {
        "rule_id": reading.get("rule_id"),
        "source_scope": reading.get("source_scope"),
        "premise_record_ids": reading.get("premise_record_ids"),
        "restricting_trace": trace,
        "rule_applications": applications,
        "application_provenance_status": "RECORDED" if applications is not None else "NOT_PRESENT_IN_INPUT_SCHEMA",
    }


def pins(manifest: dict) -> dict:
    return {(source["source"], file["id"]): file for source in manifest["sources"] for file in source["files"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = {
        side: {p.name: digest(p) for p in root.iterdir() if p.is_file() and p.name.endswith((".json", ".jsonl"))}
        for side, root in [("old", args.old), ("new", args.new)]
    }
    old, new = load(args.old), load(args.new)
    if (
        old["manifest"]["basis_id"] != new["manifest"]["basis_id"]
        or old["manifest"]["coordinate_order"] != new["manifest"]["coordinate_order"]
    ):
        raise ValueError("INCOMPATIBLE_REPLAY_BASIS")
    coordinates = old["manifest"]["coordinate_order"]
    if len(coordinates) != 58:
        raise ValueError("UNEXPECTED_REPLAY_COORDINATE_COUNT")
    args.output.mkdir(parents=True, exist_ok=True)
    cell_counts, coordinate_counts, reading_counts, reading_codes, writer_counts = (
        Counter(),
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    added_scopes, shared_code_changes = Counter(), Counter()
    trace_only_cells = 0
    cell_review, reading_review, model_calls = [], [], {"old": [], "new": []}
    common = set(old["readings"]) & set(new["readings"])
    removed = set(old["readings"]) - set(new["readings"])
    added = set(new["readings"]) - set(old["readings"])
    keys = sorted(set(old["readings"]) | set(new["readings"]))
    with (
        (args.output / "cell-ledger.jsonl.gz").open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as ledger,
        (args.output / "reading-ledger.jsonl").open("w") as reading_ledger,
    ):
        for key in keys:
            a, b = old["readings"].get(key), new["readings"].get(key)
            presence = (
                "SHARED_READING"
                if a is not None and b is not None
                else "REMOVED_READING"
                if b is None
                else "ADDED_READING"
            )
            reading_counts[presence] += 1
            if presence == "ADDED_READING":
                added_scopes[(b.get("source_scope"), b["code"])] += 1
            if presence == "SHARED_READING" and a["code"] != b["code"]:
                shared_code_changes[(a["code"], b["code"])] += 1
            old_domains = a["after_selection"]["domains"] if a is not None else {}
            new_domains = b["after_selection"]["domains"] if b is not None else {}
            changes = []
            for coordinate in coordinates:
                x, y = old_domains.get(coordinate), new_domains.get(coordinate)
                code = classify(x, y)
                if presence == "SHARED_READING" and code in {"UNCHANGED", "DOMAIN_ORDER_ONLY"}:
                    old_trace = provenance(a, coordinate)["restricting_trace"]
                    new_trace = provenance(b, coordinate)["restricting_trace"]
                    if old_trace != new_trace:
                        trace_only_cells += 1
                cell_counts[code] += 1
                if code not in {"UNCHANGED", "DOMAIN_ORDER_ONLY"}:
                    coordinate_counts[(coordinate, code)] += 1
                cell = {
                    "word": key[0],
                    "reading_id": key[1],
                    "coordinate": coordinate,
                    "code": code,
                    "old_domain": x,
                    "new_domain": y,
                }
                if code != "UNCHANGED":
                    cell.update(old_provenance=provenance(a, coordinate), new_provenance=provenance(b, coordinate))
                    changes.append({"coordinate": coordinate, "code": code})
                    for side, reading in [("old", a), ("new", b)]:
                        if reading is not None:
                            writer_counts.update(
                                (side, code, t["rule"])
                                for t in reading["after_selection"].get("trace", [])
                                if t.get("coordinate") == coordinate and "rule" in t
                            )
                ledger.write((canonical(cell) + "\n").encode())
                if presence == "SHARED_READING" and (
                    code.startswith("SETTLED_") or code == "OPEN_TO_SETTLED_OUTSIDE_OLD_DOMAIN"
                ):
                    cell_review.append(cell)
            details = {"word": key[0], "reading_id": key[1], "code": presence, "changed_cells": changes}
            for side, reading, data in [("old", a, old), ("new", b, new)]:
                details[side] = (
                    None
                    if reading is None
                    else {
                        "code": reading["code"],
                        "jsonl_line": data["words"][key[0]]["line"],
                        "provenance": provenance(reading),
                        "fired_rules": reading["after_selection"].get("fired_rules", []),
                        "bindings": reading.get("bindings"),
                        "unmapped": reading.get("unmapped"),
                        "collisions": reading.get("collisions"),
                        "unresolved_projection_scopes": reading.get("unresolved_projection_scopes"),
                        "decisions": reading.get("decisions"),
                        "number_scale": reading.get("number_scale"),
                    }
                )
                if reading is not None:
                    reading_codes[(side, reading["code"])] += 1
                    model_calls[side].extend(
                        {"word": key[0], "reading_id": key[1], "call": call} for call in reading.get("model_calls", [])
                    )
            reading_ledger.write(canonical(details) + "\n")
            if presence == "REMOVED_READING":
                reading_review.append(details)
    (args.output / "settled-cell-review.jsonl").write_text("".join(canonical(row) + "\n" for row in cell_review))
    (args.output / "removed-readings.jsonl").write_text("".join(canonical(row) + "\n" for row in reading_review))
    (args.output / "model-calls.json").write_text(json.dumps(model_calls, indent=2) + "\n")
    reading_path = args.output / "reading-ledger.jsonl"
    with (
        (args.output / "reading-ledger.jsonl.gz").open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed,
        reading_path.open("rb") as source,
    ):
        for block in iter(lambda: source.read(1024 * 1024), b""):
            compressed.write(block)
    reading_path.unlink()
    (args.output / "writers.json").write_text(
        json.dumps(
            [
                {"side": side, "transition": code, "rule": rule, "cell_trace_occurrences": count}
                for (side, code, rule), count in sorted(writer_counts.items())
            ],
            indent=2,
        )
        + "\n"
    )
    old_pins, new_pins = pins(old["manifest"]), pins(new["manifest"])
    source_diff = []
    for key in sorted(set(old_pins) | set(new_pins)):
        a, b = old_pins.get(key), new_pins.get(key)
        code = (
            "ADDED_PIN"
            if a is None
            else "REMOVED_PIN"
            if b is None
            else "HASH_CHANGED"
            if a["sha256"] != b["sha256"]
            else "PATH_ONLY_CHANGED"
            if a.get("path") != b.get("path")
            else "UNCHANGED_PIN"
        )
        source_diff.append({"source": key[0], "id": key[1], "code": code, "old": a, "new": b})
    manifest_diff = {
        key: {"old": old["manifest"].get(key), "new": new["manifest"].get(key)}
        for key in sorted(set(old["manifest"]) | set(new["manifest"]))
        if old["manifest"].get(key) != new["manifest"].get(key) and key != "sources"
    }
    (args.output / "source-pins.json").write_text(
        json.dumps(
            {
                "source_metadata": {
                    side: [{k: v for k, v in source.items() if k != "files"} for source in data["manifest"]["sources"]]
                    for side, data in [("old", old), ("new", new)]
                },
                "files": source_diff,
                "other_manifest_differences": manifest_diff,
            },
            indent=2,
        )
        + "\n"
    )
    structures = []
    for key in sorted(set(old["structures"]) | set(new["structures"])):
        a, b = old["structures"].get(key), new["structures"].get(key)
        structures.append(
            {
                "word": key[0],
                "reading_id": key[1],
                "code": "ADDED_STRUCTURE"
                if a is None
                else "REMOVED_STRUCTURE"
                if b is None
                else "UNCHANGED_STRUCTURE"
                if a == b
                else "CHANGED_STRUCTURE",
                "old": a,
                "new": b,
            }
        )
    (args.output / "structures.jsonl").write_text("".join(canonical(row) + "\n" for row in structures))
    native_changed = [
        word
        for word in sorted(set(old["words"]) & set(new["words"]))
        if old["words"][word]["native"] != new["words"][word]["native"]
    ]
    summary = {
        "schema": "GSE_HISTORICAL_REPLAY_V1",
        "basis_id": old["manifest"]["basis_id"],
        "comparison": "DATA_ONLY; DIFFERENCES_DO_NOT_ESTABLISH_SEMANTIC_APPROVAL",
        "old_dir": str(args.old),
        "new_dir": str(args.new),
        "input_sha256": inputs,
        "word_accounting": {
            "old": len(old["words"]),
            "new": len(new["words"]),
            "removed": sorted(set(old["words"]) - set(new["words"])),
            "added": sorted(set(new["words"]) - set(old["words"])),
            "manifest_worklists_equal": old["manifest"]["words"] == new["manifest"]["words"],
            "native_records_changed_words": len(native_changed),
        },
        "readings": {
            "old": len(old["readings"]),
            "new": len(new["readings"]),
            "SHARED_READING": reading_counts["SHARED_READING"],
            "ADDED_READING": reading_counts["ADDED_READING"],
            "REMOVED_READING": reading_counts["REMOVED_READING"],
            "shared_code_changes": [
                {"old": old_code, "new": new_code, "count": count}
                for (old_code, new_code), count in sorted(shared_code_changes.items())
            ],
            "added_by_source_scope": [
                {"source_scope": scope, "code": code, "count": count}
                for (scope, code), count in sorted(added_scopes.items(), key=lambda item: str(item[0]))
            ],
        },
        "reading_codes": [
            {"side": side, "code": code, "count": count} for (side, code), count in sorted(reading_codes.items())
        ],
        "cells": {
            "coordinates": len(coordinates),
            "ledger_rows": sum(cell_counts.values()),
            "classifications": dict(cell_counts),
            "settled_review_rows": len(cell_review),
            "settled_value_changes": cell_counts["SETTLED_VALUE_CHANGED"],
            "settled_reopened": cell_counts["SETTLED_REOPENED"] + cell_counts["SETTLED_REOPENED_EXCLUDING_OLD"],
            "settled_to_conflict": cell_counts["SETTLED_TO_CONFLICT"],
            "unchanged_domains_with_changed_restricting_trace": trace_only_cells,
            "by_coordinate": [
                {"coordinate": coordinate, "code": code, "count": count}
                for (coordinate, code), count in sorted(coordinate_counts.items())
                if code not in {"ADDED_READING_CELL", "REMOVED_READING_CELL"}
            ],
        },
        "recorded_restricting_writers_for_shared_changes": [
            {"side": side, "transition": code, "rule": rule, "cell_trace_occurrences": count}
            for (side, code, rule), count in sorted(writer_counts.items())
            if code not in {"ADDED_READING_CELL", "REMOVED_READING_CELL"}
        ],
        "source_pins": {
            code: sum(row["code"] == code for row in source_diff)
            for code in ["ADDED_PIN", "REMOVED_PIN", "HASH_CHANGED", "PATH_ONLY_CHANGED", "UNCHANGED_PIN"]
        },
        "model_calls": {side: len(calls) for side, calls in model_calls.items()},
        "manifest_models": {side: data["manifest"].get("model") for side, data in [("old", old), ("new", new)]},
        "structures": dict(Counter(row["code"] for row in structures)),
        "limitations": [
            "A restricting trace records a constraint reduction, not a proof that a semantic change is justified.",
            "Old records do not contain application IDs; absent application metadata is recorded as missing schema evidence, never fabricated.",
            "Reading equality uses the exact (word, reading_id) key; no implicit cross-ID sense matching.",
            "The full cell ledger includes added and removed reading cells and unchanged shared cells; summaries keep these classes separate.",
        ],
    }
    for side, root in [("old", args.old), ("new", args.new)]:
        if inputs[side] != {
            p.name: digest(p) for p in root.iterdir() if p.is_file() and p.name.endswith((".json", ".jsonl"))
        }:
            raise ValueError("REPLAY_INPUT_CHANGED_DURING_COMPARISON:" + side)
    assert summary["readings"]["old"] == len(common) + len(removed)
    assert summary["readings"]["new"] == len(common) + len(added)
    assert summary["cells"]["ledger_rows"] == len(keys) * len(coordinates)
    summary["outputs"] = {
        p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
        for p in sorted(args.output.iterdir())
        if p.is_file() and p.name != "summary.json"
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "words": summary["word_accounting"],
                "readings": summary["readings"],
                "cell_classifications": summary["cells"]["classifications"],
                "settled_review_rows": len(cell_review),
                "source_pins": summary["source_pins"],
                "model_calls": summary["model_calls"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
