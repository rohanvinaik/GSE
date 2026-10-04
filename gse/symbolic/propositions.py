"""
Signed propositions: every predicate a clause tree states, with the scopes it is stated under (#15).

Five walkers turned a tree into signed propositions under three policies: the story skeleton, the knowledge base,
the SquishOS voice probe, personal-wiki and a proof script. This is the one extraction. It walks the operand-field map
(:data:`gse.symbolic.predicates.OPERAND_FIELDS`), applies the shared modality decision
(:func:`gse.symbolic.modality.assertion_mode`), and records, for each predicate, the ORDERED scopes it sits under,
outermost first: each Negation over it, each Conditional arm, attitude complement and irrealis inner act it is in.
Each consumer maps that record to its own action (a fact, a rule, a skipped belief, a count).

:attr:`Proposition.status` is the one code the voice probe reads: the outermost scope's mode, or ``"asserted"``. It
is lossy on purpose, because it reproduces the probe's walk exactly and so changes no measure when the probe moves
onto this. Under "He doesn't believe X" it calls X negated, and under not-(P and Q) it calls P and Q negated, though X
is believed content and P, Q are asserted neither way. The scopes keep what the code loses; a consumer that needs
the difference reads them.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, List, Tuple

from gse.symbolic.modality import assertion_mode
from gse.symbolic.predicates import OPERAND_FIELDS

# The operand fields each mode governs on the node that imposes it.
_GOVERNED = {
    "conditional": ("antecedent", "consequent"),
    "belief": ("patient",),
    "irrealis": ("inner",),
}
# Deeper than any parsed sentence; a guard against a malformed, self-referencing tree.
_MAX_DEPTH = 64


@dataclass(frozen=True)
class Scope:
    """One governing scope on a proposition's path: the mode, the node imposing it, and the field it governs.

    The owner is kept whole so a consumer can read what the mode flattens: the attitude verb behind a ``belief``
    (factive "know" or "realize" against "believe"), the matrix verb behind ``irrealis``, the arm of a ``conditional``.
    """

    mode: str
    owner: Any
    field: str

    @property
    def owner_kind(self) -> str:
        return type(self.owner).__name__


@dataclass(frozen=True)
class Proposition:
    """One predicate a tree states, with its scopes, outermost first; none means it is stated outright."""

    node: Any
    scopes: Tuple[Scope, ...] = ()

    @property
    def kind(self) -> str:
        return type(self.node).__name__

    @property
    def status(self) -> str:
        return proposition_status([scope.mode for scope in self.scopes])


def proposition_status(modes: List[str]) -> str:
    """The one code a proposition's scope modes, outermost first, project to (pure, pinned).

    The outermost mode that is not ``"asserted"`` (``negated``, ``conditional``, ``belief`` or ``irrealis``), or
    ``"asserted"`` when there is none. Lossy by design; see the module docstring.
    """
    for mode in modes:
        if mode != "asserted":
            return mode
    return "asserted"


def propositions(tree: Any) -> List[Proposition]:
    """Every predicate in ``tree``, depth-first in tree order, each with the scopes it sits under."""
    out: List[Proposition] = []

    def walk(node: Any, scopes: Tuple[Scope, ...], depth: int) -> None:
        if node is None or depth > _MAX_DEPTH or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item, scopes, depth + 1)
            return
        kind = type(node).__name__
        if kind == "Negation":
            walk(getattr(node, "operand", None), (*scopes, Scope("negated", node, "operand")), depth + 1)
            return
        fields = OPERAND_FIELDS.get(kind)
        if fields is not None:
            out.append(Proposition(node, scopes))
            patient_kind = type(getattr(node, "patient", None)).__name__
            mode = assertion_mode(kind, getattr(node, "verb", "") or "", patient_kind)
            governed = _GOVERNED.get(mode, ())
            for field in fields:
                inner = (*scopes, Scope(mode, node, field)) if field in governed else scopes
                walk(getattr(node, field, None), inner, depth + 1)
            return
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            for field in dataclasses.fields(node):
                walk(getattr(node, field.name, None), scopes, depth + 1)

    walk(tree, (), 0)
    return out
