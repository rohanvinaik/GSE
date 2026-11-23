"""The Lens protocol — one law-grounded specialist of the statement-healer Society of Mind.

Each lens encodes ONE piece of the law of clean-statement formation as a structural ``must``/
``must-not`` constraint plus its thin repair. A lens is BLIND to the others (no cross-talk =
inverse-brittleness, DNA-repair-pathway style: each enzyme one lesion class). Three outcomes:

  * ``claims(node, env)`` is False  → not my territory; I never touch it.
  * ``apply`` returns ``Repair``    → my law applied cleanly; here is the corrected node.
  * ``apply`` returns ``Hole``      → my law's territory but I cannot cleanly repair → an HONEST
                                      hole (abstention is first-class; fabrication is the one
                                      forbidden thing — the clean-or-hole contract).

A lens NEVER fabricates a fill it is unsure of. Repairs are structural re-reads under the law and
K-line/HDC recall by resemblance — NOT frequency stats, NOT gradient descent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Repair:
    """A clean repair: the law fired and produced a corrected predicate node."""

    node: Any
    lens: str
    note: str = ""


@dataclass
class Hole:
    """An honest abstention: this lens owns the territory but cannot cleanly repair it."""

    lens: str
    reason: str


class Lens:
    """Base NODE specialist — a node-local transform. Subclasses set ``name``/``law`` and implement
    ``claims`` + ``apply``. The defect is a WRONG node in the tree (e.g. an Event whose verb is a
    predicate adjective); the lens rewrites it 1:1."""

    name: str = "lens"
    law: str = ""

    def claims(self, node: Any, env, folds=None) -> bool:
        """Does this node fall under my law's territory? Must be cheap and mutually exclusive with
        the other lenses' territories (the no-cross-talk invariant). ``folds`` is the optional
        Layer-2 fold map (``{entity_id: EntityFold}``) — the document-scale semantic resolution a
        structural law may consult (e.g. subject disambiguation); structural-only lenses ignore it."""
        raise NotImplementedError

    def apply(self, node: Any, env, folds=None):  # -> Repair | Hole
        """Apply my law. Return a ``Repair`` (clean fix) or a ``Hole`` (honest abstention).
        Only called when ``claims`` returned True. ``folds`` = the optional Layer-2 fold map."""
        raise NotImplementedError


class AdditiveLens:
    """An UTTERANCE-level additive specialist — for a defect that is a MISSING predication, not a
    wrong node (e.g. a participial adjunct whose event was dropped entirely, so there is no node to
    claim). Given the utterance's predicates + its envelope, it EMITS the recovered predicates.
    Same clean-or-hole discipline: emit only what it can recover cleanly; abstain (emit nothing)
    on anything doubtful — never fabricate."""

    name: str = "additive_lens"
    law: str = ""

    def emit(self, predicates, env, folds=None):  # -> List[Repair]
        """Return a list of ``Repair`` (each wrapping a newly recovered predicate), or [] to abstain.
        ``predicates`` are this utterance's (possibly already node-repaired) predicates; ``env`` is
        its envelope; ``folds`` the optional Layer-2 fold map (subject disambiguation by significance)."""
        raise NotImplementedError
