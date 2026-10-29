"""Versioned representation conventions, separate from corpus-discovered rules.

These are the founder-approved projection laws, not a claim that NSM's full
prime explications have already been compiled. Additional justified relations
and hand-reviewed definition anchors enter through the build manifest.
"""

import hashlib
import json
from itertools import product
from pathlib import Path

from gse.curation.schema import ALL_PRIMITIVES, BIPOLAR_PAIRS

from .engine import Assertion, Relation
from .interchange import read_json

FOUNDER_SOURCE = "docs/program/LEXICON_FOUNDER_WORDS_2026-10-24.md"
DESIGN_SOURCE = "docs/program/LEXICON_CONSTRUCTION_DESIGN.md"
CONVENTION_VERSION = "gse.lexicon-conventions/2026-10-29"
WANT_POLARITY = {-1: "NOT_WANT", 0: "ORTHOGONAL_TO_WANTING", 1: "WANT"}
ORDINAL_INTENSITY = {"VERY": 1, "EXTREMELY": 2}
NEGATIVE_POLES = {negative: positive for positive, negative in BIPOLAR_PAIRS}
BANKS = tuple(p for p in ALL_PRIMITIVES if p not in NEGATIVE_POLES and p not in {"NUMBER", "HIER_PLUS", "HIER_MINUS"})
POS_NAMES = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",
    "r": "adverb",
    "adj": "adjective",
    "adv": "adverb",
}


def representation_contract() -> dict:
    """Pin supported ordinal laws and fingerprint the lexical basis explicitly.

    Other historical ordinal tables are not silently promoted to authority.
    A conflicting runtime mapping requires an explicit representation migration.
    """
    from gse.primitives_v2 import get_hierarchy_encoding

    for modifier, level in ORDINAL_INTENSITY.items():
        if get_hierarchy_encoding(modifier) != ("INTENSITY", level, abs(level)):
            raise ValueError("ORDINAL_REPRESENTATION_DRIFT")
    return {
        "version": CONVENTION_VERSION,
        "basis": list(BANKS),
        "basis_sha256": hashlib.sha256(json.dumps(BANKS, separators=(",", ":")).encode()).hexdigest(),
        "want_polarity": {str(k): v for k, v in WANT_POLARITY.items()},
        "ordinal_intensity": dict(ORDINAL_INTENSITY),
        "ordinal_source": DESIGN_SOURCE + "#ordinal-stability",
        "other_ordinal_levels": "EXPLICIT_JUSTIFIED_MANIFEST_ONLY",
    }


def definition_context(pos: str) -> dict[str, str]:
    """Keep unknown POS unknown; only explicit lexical types activate a law."""
    normalized = pos.lower()
    return {"pos": POS_NAMES.get(normalized, normalized)}


def projection_relations() -> tuple[Relation, ...]:
    """Compile the approved own-word projection rules, with their scope guards."""
    foundational = (
        Relation(
            "founder:noun-own-evaluation",
            ("GOOD",),
            ((0,),),
            (FOUNDER_SOURCE + "#F057",),
            "foundational",
            True,
            (("pos", "noun"),),
        ),
        Relation(
            "founder:adjective-not-object",
            ("SOMETHING",),
            ((0,),),
            (FOUNDER_SOURCE + "#F057",),
            "foundational",
            True,
            (("pos", "adjective"),),
        ),
        Relation(
            "founder:adverb-not-object",
            ("SOMETHING",),
            ((0,),),
            (FOUNDER_SOURCE + "#F057",),
            "foundational",
            True,
            (("pos", "adverb"),),
        ),
    )
    categories = (
        ("I", "SOMEONE", (1,), ()),
        ("YOU", "SOMEONE", (1,), ()),
        ("BODY", "SOMETHING", (1,), (("pos", "noun"),)),
        ("ONE", "QUANTITY", (1,), ()),
        ("TWO", "QUANTITY", (1,), ()),
        ("MOVE", "HAPPEN", (1,), ()),
        ("DO", "HAPPEN", (1,), ()),
        ("CAUSE", "HAPPEN", (1,), ()),
        ("THEN", "WHEN", (-1, 1), ()),
        ("BEFORE", "WHEN", (-1, 1), ()),
        ("LONG_TIME", "WHEN", (-1, 1), ()),
        ("MOMENT", "WHEN", (1,), ()),
        ("ABOVE", "WHERE", (-1, 1), ()),
        ("FAR", "WHERE", (-1, 1), ()),
        ("OUTSIDE", "WHERE", (-1, 1), ()),
        ("TOWARD", "WHERE", (-1, 1), ()),
        ("HERE", "WHERE", (1,), ()),
        ("SIDE", "WHERE", (1,), ()),
    )
    category_relations = tuple(
        Relation(
            f"founder:category:{specific.lower()}-{general.lower()}",
            (specific, general),
            tuple((a, b) for a, b in product((-1, 0, 1), repeat=2) if a not in active or b == 1),
            (DESIGN_SOURCE + "#category-content",),
            "conditional",
            True,
            guards,
        )
        for specific, general, active, guards in categories
    )
    absence_relations = tuple(
        Relation(
            f"founder:absence:{source.lower()}-{target.lower()}",
            (source, target),
            tuple((a, b) for a, b in product((-1, 0, 1), repeat=2) if a == 0 or b == 0),
            (DESIGN_SOURCE + "#evidence-conditioned-absence",),
            "conditional",
            True,
            (("pos", "adjective"),),
            absent_evidence=(target,),
        )
        for source, target in (("GOOD", "BIG"), ("BIG", "GOOD"))
    )
    return foundational + category_relations + absence_relations


def load_manifest(path: str | Path | None) -> tuple[tuple[Relation, ...], dict[str, tuple[Assertion, ...]], dict]:
    """Load explicit approved rules/anchors and NUMBER metadata, never infer approval.

    Anchors are keyed by dictionary entry ID, not spelling. Each assertion must
    name its source and record. A manifest cannot mint additional coordinates.
    """
    if path is None:
        return (), {}, {}
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("format") != "gse.lexicon-rules/1":
        raise ValueError("INVALID_RULE_MANIFEST")
    if set(raw) - {"format", "relations", "anchors", "hierarchy", "definitions", "prime_entries"}:
        raise ValueError("UNKNOWN_MANIFEST_FIELD")
    if not isinstance(raw.get("relations", []), list) or not isinstance(raw.get("anchors", {}), dict):
        raise ValueError("INVALID_RULE_MANIFEST")
    for entry_id, records in raw.get("anchors", {}).items():
        if not isinstance(entry_id, str) or not entry_id.strip() or not isinstance(records, list):
            raise ValueError("INVALID_ANCHORS")
    relations = []
    for record in raw.get("relations", []):
        required = {"rule_id", "banks", "allowed_rows", "provenance"}
        if (
            not isinstance(record, dict)
            or not required <= record.keys()
            or set(record) - required - {"authority", "approved", "guards", "absent_evidence"}
        ):
            raise ValueError("INVALID_RELATION_RECORD")
        for key in ("banks", "provenance", "allowed_rows", "guards", "absent_evidence"):
            if not isinstance(record.get(key, []), list):
                raise ValueError("INVALID_RELATION_SEQUENCE")
        if any(not isinstance(row, list) for row in record["allowed_rows"] + record.get("guards", [])):
            raise ValueError("INVALID_RELATION_ROWS")
        record = dict(record)
        for key in ("banks", "provenance"):
            record[key] = tuple(record[key])
        record["allowed_rows"] = tuple(tuple(row) for row in record["allowed_rows"])
        record["guards"] = tuple(tuple(pair) for pair in record.get("guards", []))
        record["absent_evidence"] = tuple(record.get("absent_evidence", []))
        relations.append(Relation(**record))
    try:
        anchors = {
            entry_id: tuple(Assertion(**record) for record in records)
            for entry_id, records in raw.get("anchors", {}).items()
        }
    except TypeError as exc:
        raise ValueError("INVALID_ANCHOR_RECORD") from exc
    hierarchy = raw.get("hierarchy", {})
    if not isinstance(hierarchy, dict):
        raise ValueError("INVALID_HIERARCHY")
    for entry_id, targets in hierarchy.items():
        if not isinstance(entry_id, str) or not isinstance(targets, dict):
            raise ValueError("INVALID_HIERARCHY")
        for bank, level in targets.items():
            if bank not in BANKS or type(level) is not int:
                raise ValueError("INVALID_HIERARCHY_TARGET")
    return tuple(relations), anchors, hierarchy


def load_manifest_extensions(path: str | Path | None):
    """Explicit hand-authored definitions and prime-unit identity bindings.

    Existing source identities must be reused when they denote the same definition;
    neither this boundary nor catalog coverage merges meanings by spelling.
    """
    from .evidence import Definition

    if path is None:
        return (), {}
    raw = read_json(path)
    records = raw.get("definitions", [])
    links = raw.get("prime_entries", {})
    if not isinstance(records, list) or not isinstance(links, dict):
        raise ValueError("INVALID_MANIFEST_DEFINITIONS")
    definitions = []
    for record in records:
        required = {"entry_id", "lemma", "pos", "definition"}
        if not isinstance(record, dict) or not required <= record.keys() or set(record) - required - {"source_ids"}:
            raise ValueError("INVALID_MANIFEST_DEFINITION")
        if not isinstance(record.get("source_ids", []), list):
            raise ValueError("INVALID_MANIFEST_SOURCE_IDS")
        definitions.append(
            Definition(
                record["entry_id"],
                record["lemma"],
                record["pos"],
                record["definition"],
                tuple(record.get("source_ids", [])),
            )
        )
    for unit, entries in links.items():
        if (
            not isinstance(unit, str)
            or not isinstance(entries, list)
            or any(not isinstance(entry, str) or not entry.strip() for entry in entries)
        ):
            raise ValueError("INVALID_PRIME_ENTRIES")
    return tuple(definitions), {unit: tuple(entries) for unit, entries in links.items()}
