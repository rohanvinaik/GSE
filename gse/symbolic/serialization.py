"""
Phase B4: JSON serialization round-trip.

Per ``sentence_architecture.md`` line 152: "decoded set of mathematical
operations in a JSON (or something else) that can be processed and
reconstructed into any arbitrary output". This module is the JSON
layer for both :class:`Expression` (AST nodes) and :class:`Predicate`
(semantic outputs from B2).

Format: every node serializes to a dict with a ``"_kind"`` discriminator
plus its fields. Recursive types serialize their children the same way.
``to_dict`` is symmetric with ``from_dict``; ``to_json`` / ``from_json``
just wrap (de)serialization in ``json.dumps`` / ``json.loads``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Union

from gse.symbolic.expression import Atom, Expression, Negation, Op, Phrase
from gse.symbolic.predicates import (
    BoundaryCase,
    Causation,
    Comparison,
    Contrast,
    Control,
    DegreeQuery,
    Equality,
    Event,
    MinimalSufficiency,
    Predicate,
    RelativeRestriction,
    SetRestriction,
    TypeAssertion,
    TypeQuery,
)
from gse.symbolic.resolution import Coordination, Entity

# All node types that can appear in a serialized tree. The
# ``_kind`` field on the dict maps back to one of these.
Node = Union[Expression, Entity, Predicate]


class SerializationError(ValueError):
    """Raised when a dict's ``_kind`` is missing or unknown."""


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def to_dict(node: Node) -> Dict[str, Any]:
    """Serialize an Expression / Entity / Predicate tree to a JSON-safe dict.

    Every node carries a ``_kind`` discriminator so ``from_dict`` can
    reconstruct without external type information.
    """
    if isinstance(node, Atom):
        return {
            "_kind": "Atom",
            "lemma": node.lemma,
            "word_primitives": dict(node.word_primitives),
            "role": node.role,
            "position": node.position,
            "pos": node.pos,
        }
    if isinstance(node, Phrase):
        return {
            "_kind": "Phrase",
            "atoms": [to_dict(a) for a in node.atoms],
        }
    if isinstance(node, Negation):
        return {
            "_kind": "Negation",
            "operand": to_dict(node.operand),
        }
    if isinstance(node, Op):
        return {
            "_kind": "Op",
            "primitive": node.primitive,
            "operation": node.operation,
            "arity": node.arity,
            "args": [to_dict(a) for a in node.args],
        }
    if isinstance(node, Entity):
        d = {
            "_kind": "Entity",
            "head": to_dict(node.head),
            "possessor": to_dict(node.possessor) if node.possessor else None,
            "role": node.role,
            "modifier": to_dict(node.modifier) if node.modifier else None,
        }
        # Reference-resolution fields (M2): emit only when set, so pre-resolution
        # Entity payloads stay byte-identical to before.
        if node.entity_id is not None:
            d["entity_id"] = node.entity_id
        if node.type_thread:
            d["type_thread"] = list(node.type_thread)
        if node.span:
            d["span"] = list(node.span)
        return d
    if isinstance(node, Comparison):
        return {
            "_kind": "Comparison",
            "lhs": to_dict(node.lhs),
            "rhs": to_dict(node.rhs),
            "sign": node.sign,
            "axis": node.axis,
        }
    if isinstance(node, Equality):
        return {
            "_kind": "Equality",
            "lhs": to_dict(node.lhs),
            "rhs": to_dict(node.rhs),
            "axis": node.axis,
        }
    if isinstance(node, TypeQuery):
        return {"_kind": "TypeQuery", "entity": to_dict(node.entity)}
    if isinstance(node, DegreeQuery):
        return {
            "_kind": "DegreeQuery",
            "entity": to_dict(node.entity),
            "axis": node.axis,
        }
    if isinstance(node, MinimalSufficiency):
        return {
            "_kind": "MinimalSufficiency",
            "threshold": to_dict(node.threshold),
            "purpose": to_dict(node.purpose),
        }
    if isinstance(node, SetRestriction):
        return {
            "_kind": "SetRestriction",
            "member": to_dict(node.member),
            "predicate": to_dict(node.predicate),
        }
    if isinstance(node, BoundaryCase):
        return {
            "_kind": "BoundaryCase",
            "entity": to_dict(node.entity),
            "predicate": to_dict(node.predicate),
            "note": node.note,
        }
    if isinstance(node, Event):
        return {
            "_kind": "Event",
            "verb": node.verb,
            "agent": to_dict(node.agent),
            "patient": to_dict(node.patient) if node.patient is not None else None,
        }
    if isinstance(node, Contrast):
        return {
            "_kind": "Contrast",
            "left": to_dict(node.left),
            "right": to_dict(node.right),
        }
    if isinstance(node, Causation):
        return {
            "_kind": "Causation",
            "cause": to_dict(node.cause),
            "effect": to_dict(node.effect),
            "conjunction": node.conjunction,
        }
    if isinstance(node, TypeAssertion):
        return {
            "_kind": "TypeAssertion",
            "entity": to_dict(node.entity),
            "kind": to_dict(node.kind),
        }
    if isinstance(node, RelativeRestriction):
        return {
            "_kind": "RelativeRestriction",
            "head": to_dict(node.head),
            "restriction": to_dict(node.restriction),
        }
    if isinstance(node, Control):
        return {
            "_kind": "Control",
            "controller": to_dict(node.controller),
            "inner": to_dict(node.inner),
            "verb": node.verb,
            "subject": to_dict(node.subject) if node.subject is not None else None,
        }
    if isinstance(node, Coordination):
        return {
            "_kind": "Coordination",
            "members": [to_dict(m) for m in node.members],
            "conjunction": node.conjunction,
            "modifier": to_dict(node.modifier) if node.modifier else None,
        }
    raise SerializationError(f"Unknown node type: {type(node).__name__}")


def to_json(node: Node, indent: int = 2) -> str:
    """Serialize a node tree to a JSON string."""
    return json.dumps(to_dict(node), indent=indent)


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------


def _require_kind(d: Dict[str, Any]) -> str:
    kind = d.get("_kind")
    if kind is None:
        raise SerializationError("Dict missing '_kind' discriminator")
    return kind


def from_dict(d: Dict[str, Any]) -> Node:
    """Reconstruct a node tree from a ``to_dict`` result."""
    kind = _require_kind(d)
    if kind == "Atom":
        return Atom(
            lemma=d["lemma"],
            word_primitives=dict(d.get("word_primitives") or {}),
            role=d.get("role"),
            position=d.get("position", 0),
            pos=d.get("pos"),
        )
    if kind == "Phrase":
        return Phrase(atoms=[from_dict(x) for x in d["atoms"]])
    if kind == "Negation":
        return Negation(operand=from_dict(d["operand"]))
    if kind == "Op":
        return Op(
            primitive=d["primitive"],
            operation=d["operation"],
            arity=d["arity"],
            args=[from_dict(x) for x in d["args"]],
        )
    if kind == "Entity":
        return Entity(
            head=from_dict(d["head"]),
            possessor=from_dict(d["possessor"]) if d.get("possessor") else None,
            role=d.get("role"),
            modifier=from_dict(d["modifier"]) if d.get("modifier") else None,
            entity_id=d.get("entity_id"),
            type_thread=tuple(d.get("type_thread") or ()),
            span=tuple(d.get("span") or ()),
        )
    if kind == "Comparison":
        return Comparison(
            lhs=from_dict(d["lhs"]),
            rhs=from_dict(d["rhs"]),
            sign=d.get("sign", +1),
            axis=d.get("axis"),
        )
    if kind == "Equality":
        return Equality(
            lhs=from_dict(d["lhs"]),
            rhs=from_dict(d["rhs"]),
            axis=d.get("axis"),
        )
    if kind == "TypeQuery":
        return TypeQuery(entity=from_dict(d["entity"]))
    if kind == "DegreeQuery":
        return DegreeQuery(entity=from_dict(d["entity"]), axis=d.get("axis"))
    if kind == "MinimalSufficiency":
        return MinimalSufficiency(
            threshold=from_dict(d["threshold"]),
            purpose=from_dict(d["purpose"]),
        )
    if kind == "SetRestriction":
        return SetRestriction(
            member=from_dict(d["member"]),
            predicate=from_dict(d["predicate"]),
        )
    if kind == "BoundaryCase":
        # ``note`` has a default so deserializing older payloads stays safe.
        return BoundaryCase(
            entity=from_dict(d["entity"]),
            predicate=from_dict(d["predicate"]),
            note=d.get("note", "deferred"),
        )
    if kind == "Event":
        return Event(
            verb=d["verb"],
            agent=from_dict(d["agent"]),
            patient=from_dict(d["patient"]) if d.get("patient") else None,
        )
    if kind == "Contrast":
        return Contrast(left=from_dict(d["left"]), right=from_dict(d["right"]))
    if kind == "Causation":
        return Causation(
            cause=from_dict(d["cause"]),
            effect=from_dict(d["effect"]),
            conjunction=d.get("conjunction", "so"),
        )
    if kind == "TypeAssertion":
        return TypeAssertion(
            entity=from_dict(d["entity"]),
            kind=from_dict(d["kind"]),
        )
    if kind == "RelativeRestriction":
        return RelativeRestriction(
            head=from_dict(d["head"]),
            restriction=from_dict(d["restriction"]),
        )
    if kind == "Control":
        return Control(
            controller=from_dict(d["controller"]),
            inner=from_dict(d["inner"]),
            verb=d.get("verb", ""),
            subject=from_dict(d["subject"]) if d.get("subject") else None,
        )
    if kind == "Coordination":
        return Coordination(
            members=tuple(from_dict(m) for m in d["members"]),
            conjunction=d.get("conjunction", "and"),
            modifier=from_dict(d["modifier"]) if d.get("modifier") else None,
        )
    raise SerializationError(f"Unknown _kind: {kind!r}")


def from_json(s: str) -> Node:
    """Deserialize a JSON string back into a node tree."""
    return from_dict(json.loads(s))
