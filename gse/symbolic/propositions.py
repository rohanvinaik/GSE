"""
Signed propositions: every predicate a clause tree states, with the scopes it is stated under (#15).

Five walkers turned a tree into signed propositions under three policies: the story skeleton, the knowledge base,
the SquishOS voice probe, personal-wiki and a proof script. This is the one extraction. It walks the operand-field map
(:data:`gse.symbolic.predicates.OPERAND_FIELDS`), applies the shared modality decision
(:func:`gse.symbolic.modality.assertion_mode`), and records, for each predicate, the ORDERED scopes it sits under,
outermost first: each Negation over it, each Conditional arm, attitude complement and irrealis inner act it is in.
Each consumer maps that record to its own action (a fact, a rule, a skipped belief, a count).

:attr:`Proposition.status` is the one code the voice probe reads: the outermost scope's mode, or ``"asserted"``, with
one rule from the knowability rulings. A negation over a believing or knowing verb is that verb's, and the content
it governs abstains: "I don't think X" and "She doesn't know that X" leave X's truth unknown, never negated (Rohan,
2026-10-05 00:28:45 and 01:37:36: "The "not" applies to thinking … It's not about the truth value of the actual "X",
which is unkown"). An unnegated knowing commits its complement (00:21:44). The code stays lossy elsewhere: under
not-(P and Q) it calls P and Q negated, though they are asserted neither way. The scopes keep what the code loses; a
consumer that needs the difference reads them.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, List, Tuple

from gse.symbolic.claims import (  # noqa: F401 — public claim authority
    CLAIM_KEY_VERSION,
    ClaimKey,
    Identity,
    Polarity,
    claim_key,
    commitment,
    commitment_modes,
    identity,
    polarity,
    scope_signature,
)
from gse.symbolic.modality import assertion_mode, modal_force
from gse.symbolic.predicates import OPERAND_FIELDS

# The operand fields each mode governs on the node that imposes it.
_GOVERNED = {
    "conditional": ("antecedent", "consequent"),
    "belief": ("patient",),
    "epistemic": ("patient",),
    "irrealis": ("inner",),
}
# The modes of a verb whose clausal content a negation over it leaves unknown (the knowability rulings).
_ATTITUDE_MODES = frozenset({"belief", "epistemic"})
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
    state: str = "read"
    reason: str = ""

    @property
    def kind(self) -> str:
        return type(self.node).__name__

    @property
    def status(self) -> str:
        return proposition_status([scope.mode for scope in self.scopes])


def proposition_status(modes: List[str]) -> str:
    """The one code a proposition's scope modes, outermost first, project to (pure, pinned).

    The outermost mode that is not ``"asserted"`` (``negated``, ``conditional``, ``belief`` or ``irrealis``), or
    ``"asserted"`` when there is none. ``"epistemic"`` is transparent: a knowing commits its complement. A
    ``"negated"`` with a believing or knowing scope inside it projects to ``"abstained"``: the negation is the verb's,
    and the content's truth is unknown ("I don't think X", "She doesn't know that X"). A negation inside the content
    is the content's own ("He knows that she did not leave": negated). Lossy by design; see the module docstring.
    """
    for i, mode in enumerate(modes):
        if mode in ("asserted", "epistemic"):
            continue
        if mode == "negated" and any(inner in _ATTITUDE_MODES for inner in modes[i + 1 :]):
            return "abstained"
        return mode
    return "asserted"


def propositions(tree: Any, *, interrogative: bool = False, source_text: str | None = None) -> List[Proposition]:
    """Every predicate, with ordered scopes and explicit source question evidence.

    ``source_text`` is the original utterance; its terminal question mark is
    retained even where the current tree has no interrogative node. Callers
    with independent interrogative evidence may pass ``interrogative=True``.
    """
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
            # A modal event ("He might leave") is stated as possible or necessary, never as a fact (#66); the mode
            # covers the event itself and everything under it.
            force = modal_force(",".join(getattr(node, "modal", ()) or ()))
            if force != "asserted":
                scopes = (*scopes, Scope(force, node, "modal"))
            if kind in {"TypeQuery", "DegreeQuery"}:
                scopes = (*scopes, Scope("question", node, "source"))
            out.append(Proposition(node, scopes))
            patient_kind = type(getattr(node, "patient", None)).__name__
            mode = assertion_mode(kind, getattr(node, "verb", "") or "", patient_kind)
            governed = _GOVERNED.get(mode, ())
            for field in fields:
                inner = (*scopes, Scope(mode, node, field)) if field in governed else scopes
                if kind == "Temporal":
                    # Both clauses remain committed, while their represented
                    # temporal qualification participates in comparison.
                    inner = (*inner, Scope("asserted", node, field))
                walk(getattr(node, field, None), inner, depth + 1)
            return
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            for field in dataclasses.fields(node):
                walk(getattr(node, field.name, None), scopes, depth + 1)

    question = interrogative or (isinstance(source_text, str) and source_text.rstrip().endswith("?"))
    scopes = (Scope("question", tree, "source"),) if question else ()
    walk(tree, scopes, 0)
    return out
