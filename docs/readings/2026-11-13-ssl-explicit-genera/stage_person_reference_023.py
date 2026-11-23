"""Measure a source-witnessed person-reference exclusion hypothesis without writes."""

from math import log2
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import Family, census, fingerprint, forecast, read, record, scope_rows
from GSE.lexicon_resource import ACTIVE_POINTER

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
BASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-021.db"


def run():
    approval = read(NOTES / "023-approved-person-reference-boundary.json")
    if approval["code"] != "FOUNDER_APPROVED_PERSON_REFERENCE_BOUNDARY":
        raise ValueError("PERSON_REFERENCE_BOUNDARY_NOT_APPROVED")
    base_hash, pointer_hash = fingerprint(BASE), fingerprint(ACTIVE_POINTER)
    guards = (("pos", "noun"), ("wordnet_native_lemma", "true"),
              ("wordnet_ancestor:physical_entity.n.01", "true"), ("wordnet_outside_ancestor:person.n.01", "true"))
    warrant = {
        "kind": "DEFINITIONAL_DERIVATION", "warrant_id": "023:nonperson-physical-noun-reference",
        "review_id": "023:proposed-boundary-requires-fresh-audit", "reviewer": "UNADMITTED_SOURCE_REVIEW",
        "source_refs": [str(NOTES / "023-approved-person-reference-boundary.json"),
                        str(ROOT / "GSE/primitives_v2.py"), str(ROOT / "docs/program/LEXICON_CONSTRUCTION_DESIGN.md")],
        "statement": "Conditional hypothesis: exact native physical non-person noun definitions denote their own "
        "object/kind rather than the current speaker or addressee. Under the approved person-reference-only "
        "coordinates, these defining contents are orthogonal to I and YOU. Sentence reference binding is separate. "
        "Person ancestry is excluded to reserve personal, address and pronominal readings. This scope is not "
        "yet independently audited, and other native ambiguities or counterexamples may require refinement.",
    }
    families = tuple(Family("nonperson-physical-noun-" + bank.lower(), None, (bank, 0), guards, (), warrant)
                     for bank in ("I", "YOU"))
    inventory = census(BASE, {families[0].id: families[0]})[families[0].id]
    record(NOTES / "023-person-reference-scope.json", {
        "code": "UNADMITTED_SHARED_SCOPE_NO_BANK_WRITES", "baseline": str(BASE), "baseline_sha256": base_hash,
        "active_pointer_sha256": pointer_hash, "definitions": inventory,
        "families": [{"id": family.id, **family.proposal()} for family in families],
        "approval_sha256": fingerprint(NOTES / "023-approved-person-reference-boundary.json"),
    })
    print("PERSON_REFERENCE_SCOPE", {"definitions": len(inventory),
                                     "native_sense_groups": len({row['synset'] for row in inventory})}, flush=True)
    rules, rows = scope_rows(BASE, inventory)
    stage = forecast(rows, rules, tuple(family.relation() for family in families))
    if fingerprint(BASE) != base_hash or fingerprint(ACTIVE_POINTER) != pointer_hash:
        raise ValueError("PERSON_REFERENCE_STAGE_FROZEN_INPUT_CHANGED")
    changes = stage["changes"]
    report = {
        "code": "UNADMITTED_READ_ONLY_PERSON_REFERENCE_STAGE", "baseline": str(BASE),
        "baseline_sha256": base_hash, "active_pointer_sha256": pointer_hash,
        "scope_definitions": len(rows), "native_sense_groups": len({row['synset'] for row in inventory}),
        "bank_assignments_written": 0, "model_questions": 0,
        "new_singletons": sum(len(row["before"]) > 1 and len(row["after"]) == 1 for row in changes),
        "changed_known_cells": sum(len(row["before"]) == 1 for row in changes),
        "marginal_potential_reduction_bits": sum(log2(len(row["before"]) / len(row["after"])) for row in changes),
        "semantic_admission": "REQUIRES_SHARED_CONTRACT_UPDATE_AND_FRESH_TEACHING_AUDITS",
        **stage,
    }
    record(NOTES / "023-person-reference-population-stage.json", report)
    print("PERSON_REFERENCE_PROVISIONAL_REACH", {key: report[key] for key in (
        "scope_definitions", "new_singletons", "changed_known_cells", "bank_assignments_written", "model_questions"
    )}, "formal_contradictions", len(stage["contradictions"]), flush=True)


if __name__ == "__main__":
    run()
