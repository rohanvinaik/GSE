"""Versioned lexical laws and content-addressed empirical discovery records."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.core import compile_law as compile_law
from gse.lexicon_builder.core import law_admission_status, rule_admission_reason, rule_contract_digest
from gse.lexicon_builder.families import family_contract

RULEBOOK = Path(__file__).with_name("bank_laws.json")
RULE_FAMILIES = ("laws", "source_rules", "native_predicate_rules", "native_residual_rules")


def admission_report(book: dict) -> dict:
    """Expose lifecycle and admission reasons used by the production split."""
    records = []
    for family in RULE_FAMILIES:
        for record in book.get(family, []):
            reason = rule_admission_reason(record)
            try:
                digest = rule_contract_digest(record) if isinstance(record, dict) else None
            except TypeError, ValueError:
                digest = None
            records.append(
                {
                    "family": family,
                    "rule_id": record.get("rule_id") if isinstance(record, dict) else None,
                    "status": law_admission_status(record),
                    "reason": reason,
                    "tier": record.get("tier") if isinstance(record, dict) else None,
                    "contract_sha256": digest,
                }
            )
    return {
        "schema": "GSE_RULE_ADMISSION_V2",
        "reason_counts": dict(Counter(r["reason"] for r in records)),
        "records": records,
    }


def split_by_admission(book: dict) -> tuple[dict, dict]:
    """One admission policy for every rule family that can write a cell (F129).

    The admitted view is what the builder may construct with. The unadmitted view holds the
    rules still awaiting review; the builder records what they would write, never applies it.
    """
    admitted, withheld = dict(book), dict(book)
    for family in RULE_FAMILIES:
        rules = book.get(family, [])
        admitted[family] = [r for r in rules if law_admission_status(r) == "ADMITTED"]
        withheld[family] = [r for r in rules if law_admission_status(r) != "ADMITTED"]
    # A native predicate's join conditions (an emotion tag, a class scope) refuse a wrong-sense join
    # whatever the rule's admission state; withholding a rule must never widen another rule's reach.
    admitted["native_predicate_contracts"] = withheld["native_predicate_contracts"] = book.get(
        "native_predicate_rules", []
    )
    return admitted, withheld


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
    for rule in data["source_rules"]:
        family_contract(rule)
    return data
