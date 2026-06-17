"""
Genesis-facing emit contract — Stage 1 of ``docs/RESOLVED_STRUCTURE_DESIGN.md``.

Walks an *evaluated* predicate tree (the output of
:func:`gse.symbolic.operators.evaluate_tree`) into the op-keyed envelope of
``Genesis/docs/gse_innerese_adapter_spec.md`` §5::

    {"op": <OP>, "args": [...], "features": {...}}

This is deliberately **flatter** than the ``_kind``-rich internal
:mod:`gse.symbolic.serialization` round-trip. The emit surface mirrors the
*consumer's* gold shape (Genesis's bridge deserializes it 1:1 over Winston's
``RoleFrames`` constructors), not GSE's richer internal ontology — the
output-contract-mirrors-gold discipline.

Versioning. ``v1`` emits ``args`` as bare entity **strings** (the surface
lemma form) or nested predicate envelopes, exactly as §5 specifies. Stage 2
(global resolution) upgrades leaf args to entity-refs
``{entity_id, lemma, type_thread[]}`` — that is contract ``v2``. The
``contract_version`` on :func:`emit_contract` makes the step explicit rather
than silent.
"""

from __future__ import annotations

import json
from typing import Any, Dict

# Contract versions. v1 = bare-string args; v2 = entity-ref args
# ({entity_id, lemma, type_thread}) once references are resolved. emit_contract
# infers the version from whether any entity-ref is present, so a tree that
# never ran resolve_references stays a clean v1 emit.
CONTRACT_VERSION = "1.0"
CONTRACT_VERSION_V2 = "2.0"

# Predicate type name → (op token, ordered arg fields, feature fields).
# The op vocabulary is the GSE→Genesis gold contract: the bridge's walker is
# built to match these tokens. Aligned with adapter-spec §4/§5.
_PRED_SPEC: Dict[str, tuple] = {
    "Event": ("EVENT", ("agent", "patient"), ("verb",)),
    "Comparison": ("COMPARISON", ("lhs", "rhs"), ("sign", "axis")),
    "Equality": ("EQUALITY", ("lhs", "rhs"), ("axis",)),
    "TypeAssertion": ("TYPE_ASSERT", ("entity", "kind"), ()),
    "TypeQuery": ("TYPE_QUERY", ("entity",), ()),
    "DegreeQuery": ("DEGREE_QUERY", ("entity",), ("axis",)),
    "MinimalSufficiency": ("MIN_SUFFICIENCY", ("threshold", "purpose"), ()),
    "SetRestriction": ("SET_RESTRICT", ("member", "predicate"), ()),
    "BoundaryCase": ("BOUNDARY_CASE", ("entity", "predicate"), ("note",)),
    "Contrast": ("CONTRAST", ("left", "right"), ()),
    "Causation": ("CAUSATION", ("cause", "effect"), ("conjunction",)),
    "RelativeRestriction": ("REL_RESTRICT", ("head", "restriction"), ()),
    "Control": ("CONTROL", ("subject", "controller", "inner"), ("verb",)),
}


def _leaf_str(node: Any) -> str:
    """Render an entity-like leaf to its surface lemma string (contract v1).

    Lossless over possessor + modifier so "Macduff's friend" / "the barking
    dog" survive as strings rather than collapsing to the bare head.
    """
    name = type(node).__name__
    if name == "Atom":
        return node.lemma
    if name == "Phrase":
        return " ".join(a.lemma for a in node.atoms)
    if name == "Entity":
        s = node.head.lemma
        if getattr(node, "modifier", None) is not None:
            s = f"{_leaf_str(node.modifier)} {s}"
        if getattr(node, "possessor", None) is not None:
            s = f"{_leaf_str(node.possessor)}'s {s}"
        return s
    # Fallback: a primitive value already (str/int) or an unknown leaf.
    return node if isinstance(node, str) else str(node)


def emit(node: Any) -> Any:
    """Walk an evaluated node into its §5 envelope (or a leaf string).

    Predicates become ``{op, args, features}``; entity-like leaves become
    surface strings; ``Negation`` and ``Coordination`` get their own op
    envelopes. Total over the node set so a partially-evaluated tree never
    raises — an un-reduced ``Op`` falls through to its operation token.
    """
    name = type(node).__name__

    spec = _PRED_SPEC.get(name)
    if spec is not None:
        op, fields, feats = spec
        return {
            "op": op,
            # Skip optional operand fields that are None (e.g. an Event's patient
            # for an intransitive verb).
            "args": [emit(getattr(node, f)) for f in fields if getattr(node, f) is not None],
            "features": {k: getattr(node, k) for k in feats},
        }

    if name == "Negation":
        return {"op": "NOT", "args": [emit(node.operand)], "features": {}}

    if name == "Coordination":
        features: Dict[str, Any] = {"conjunction": node.conjunction}
        if getattr(node, "modifier", None) is not None:
            features["modifier"] = _leaf_str(node.modifier)
        return {
            "op": "COORD",
            "args": [emit(m) for m in node.members],
            "features": features,
        }

    if name == "Op":
        # Un-reduced operator (shouldn't appear post-evaluate_tree; stay total).
        return {
            "op": node.operation,
            "args": [emit(a) for a in node.args],
            "features": {},
        }

    # A reference-resolved Entity → v2 entity-ref. (Possessor folds into the
    # surface lemma string; the ref's identity is the head's entity_id.)
    if name == "Entity" and getattr(node, "entity_id", None) is not None:
        return {
            "entity_id": node.entity_id,
            "lemma": _leaf_str(node),
            "type_thread": list(node.type_thread),
        }

    # Entity (unresolved) / Atom / Phrase / bare value → leaf string (v1).
    return _leaf_str(node)


def _has_entity_ref(payload: Any) -> bool:
    """True if the emitted payload contains any v2 entity-ref."""
    if isinstance(payload, dict):
        if "entity_id" in payload:
            return True
        return any(_has_entity_ref(v) for v in payload.values())
    if isinstance(payload, list):
        return any(_has_entity_ref(v) for v in payload)
    return False


def emit_contract(node: Any, version: str | None = None) -> Dict[str, Any]:
    """Wrap :func:`emit` with the contract version envelope.

    One sentence → one predicate tree → one contract dict. The version is
    inferred from the payload (``v2`` if any entity-ref is present, else
    ``v1``), so the Genesis bridge knows whether ``args`` leaves are strings or
    ``{entity_id, lemma, type_thread}``. Pass ``version`` to override."""
    payload = emit(node)
    if version is None:
        version = CONTRACT_VERSION_V2 if _has_entity_ref(payload) else CONTRACT_VERSION
    return {"contract_version": version, "predicate": payload}


def emit_json(node: Any, indent: int = 2) -> str:
    """Serialize the contract envelope to JSON."""
    return json.dumps(emit_contract(node), indent=indent)
