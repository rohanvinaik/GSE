"""Versioned lexical laws and content-addressed empirical discovery records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.core import Cell, Law

RULEBOOK = Path(__file__).with_name("bank_laws.json")


def candidate_id(record: dict) -> str:
    """Identity describes a relation; repeated measurements retain that identity."""
    claim = {"antecedents": sorted(record["antecedents"]), "consequent": record["consequent"]}
    return "COH_" + hashlib.sha256(json.dumps(claim, sort_keys=True).encode()).hexdigest()[:16]


def export_candidates(results: Path, output: Path) -> dict:
    """Save ALL measured candidates, their evidence, exceptions and exact lineage."""
    report = json.loads(results.read_text())
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for family in ("pair_relations", "conjunction_relations"):
        for relation in report[family]:
            records.append(
                {
                    "rule_id": candidate_id(relation),
                    "kind": "NATIVE_ASSOCIATION",
                    "review_state": "DISCOVERED_NOT_ADMITTED",
                    "may_write_lexical_cells": False,
                    "discovery_file": str(results.resolve()),
                    "discovery_sha256": hashlib.sha256(results.read_bytes()).hexdigest(),
                    "discovery_script_sha256": report["script_sha256"],
                    "population_policy": report["candidate_policy"],
                    "source_snapshots": report["sources"],
                    "relation": relation,
                }
            )
    path = output / "coherence_candidates.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True, allow_nan=False) + "\n" for r in records))
    manifest = {
        "schema_version": 1,
        "basis_id": BASIS_ID,
        "candidates": len(records),
        "catalog": str(path),
        "catalog_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "active_laws": str(RULEBOOK),
        "active_laws_sha256": hashlib.sha256(RULEBOOK.read_bytes()).hexdigest(),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_rulebook(path: Path = RULEBOOK) -> dict:
    data = json.loads(path.read_text())
    if data["basis_id"] != BASIS_ID:
        raise ValueError("rulebook basis mismatch")
    ids = [
        r["rule_id"]
        for r in data["laws"]
        + data["source_rules"]
        + data.get("native_predicate_rules", [])
        + data.get("native_residual_rules", [])
    ]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ID")
    for rule in data["laws"]:
        compile_law(rule)
    return data


def compile_law(record: dict) -> Law:
    return Law(
        record["rule_id"],
        tuple(record["coordinates"]),
        tuple(tuple(Cell(v) for v in row) for row in record["allowed"]),
        tuple(tuple(pair) for pair in record["guard"]),
        record["warrant"],
    )
