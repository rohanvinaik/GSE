"""Source-typed checks on model rulings; these checks never supply bank values."""

from __future__ import annotations

import json
from dataclasses import asdict

REFERENCE_COMPONENTS = frozenset({"I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "SAME"})
BE_SCOPE_SOURCE = "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#be-stative-content-scope"
BODY_SCOPE_SOURCE = "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#body-reference-content-scope"


def _catalog_reference_record(entry_id: str, record: dict) -> str:
    """Recognize a complete existing native row, not a label or a spelling."""
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

    if record.get("source") != "gse_closed_class" or record.get("family") != "gse_curated_grammar":
        return "ADDITIONAL_EXACT_LEXICAL_SOURCE"
    features = record.get("features")
    if type(features) is not dict:
        return "UNRECOGNIZED_NATIVE_CATALOG_RECORD"
    if features.get("catalog") != "pronoun" or features.get("grammar_roles") != ["PRON"]:
        return "NOT_NATIVE_PRONOUN_REFERENCE_ROLE"
    components = features.get("primitives")
    if type(components) is not dict or not components:
        return "NO_DECLARED_REFERENCE_COMPONENT"
    if any(type(name) is not str or name not in REFERENCE_COMPONENTS for name in components):
        return "NONREFERENCE_LEXICAL_COMPONENT"
    lemma = features.get("lemma")
    if type(lemma) is not str or not lemma:
        return "UNRECOGNIZED_NATIVE_CATALOG_RECORD"
    # Lookup identifies a source record for equality verification, never a
    # spelling-based semantic assignment. Every native field must match.
    for entry in GSEClosedClassParser().get_entries(lemma):
        if entry.entry_id != entry_id:
            continue
        native = json.loads(json.dumps(asdict(entry), allow_nan=False))
        try:
            actual = json.dumps(features, sort_keys=True, allow_nan=False)
            expected = json.dumps(native, sort_keys=True, allow_nan=False)
        except TypeError, ValueError:
            return "UNRECOGNIZED_NATIVE_CATALOG_RECORD"
        if actual == expected:
            return "EXACT_NATIVE_REFERENCE_ONLY_CATALOG"
    return "UNRECOGNIZED_NATIVE_CATALOG_RECORD"


def model_scope_admission(
    entry_id: str, bank: str, value: int | None, observations: tuple[dict, ...] | list[dict]
) -> dict:
    """Refuse positive BE/BODY supported only by the exact native reference catalog.

    Association/world records cannot supply own-word stative or bodily content. An
    additional exact lexical source or a different native catalog component
    prevents the narrow reference-only classification. NOT_APPLICABLE is not
    approval: the ordinary freshness, domain and contradiction checks still
    govern the ruling. Zero, negative signs and null receive no new value here.
    """
    if bank not in {"BE", "BODY"} or type(value) is not int or value != 1:
        return {
            "code": "NOT_APPLICABLE",
            "reason": "OUTSIDE_POSITIVE_BODY_SCOPE_CHECK" if bank == "BODY" else "OUTSIDE_POSITIVE_BE_SCOPE_CHECK",
        }
    if type(entry_id) is not str or not entry_id or type(observations) not in (tuple, list):
        return {"code": "NOT_APPLICABLE", "reason": "UNCLASSIFIED_SOURCE_INPUT"}
    if any(type(record) is not dict for record in observations):
        return {"code": "NOT_APPLICABLE", "reason": "UNCLASSIFIED_SOURCE_INPUT"}
    exact = [
        record for record in observations if record.get("entry_id") == entry_id and record.get("scope") == "lexical"
    ]
    if not exact:
        return {"code": "NOT_APPLICABLE", "reason": "NO_EXACT_LEXICAL_SOURCE"}
    witnesses = []
    for record in exact:
        code = _catalog_reference_record(entry_id, record)
        if code != "EXACT_NATIVE_REFERENCE_ONLY_CATALOG":
            return {"code": "NOT_APPLICABLE", "reason": code}
        record_id = record.get("record_id")
        if type(record_id) is not str or not record_id:
            return {"code": "NOT_APPLICABLE", "reason": "UNRECOGNIZED_NATIVE_CATALOG_RECORD"}
        witnesses.append(record_id)
    return {
        "code": "SCOPE_UNJUSTIFIED",
        "reason": f"ENTITY_REFERENCE_ALONE_DOES_NOT_JUSTIFY_POSITIVE_{bank}",
        "entry_id": entry_id,
        "bank": bank,
        "proposed_value": value,
        "source": BE_SCOPE_SOURCE if bank == "BE" else BODY_SCOPE_SOURCE,
        "exact_native_record_ids": sorted(set(witnesses)),
        "classification": "EXCLUSIVELY_EXACT_NATIVE_REFERENCE_ONLY_CATALOG",
        "disposition": "NO_ASSERTION_CURRENT_DOMAINS_UNCHANGED",
    }
