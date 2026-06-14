"""
Phase B3: query interface over evaluated symbolic trees.

Per ``sentence_architecture.md`` line 154, the symbolic layer should
support queries like:

* "Recover what animals we're talking about" (entities)
* "Recover the cuteness > 0 assertion about the dog" (predicates)
* "Distinguish 'dog cuter than cat' from 'cat cuter than dog' symbolically"
  (is_argument_swap_of, is_logically_equal_to)
* "The axis of comparison" (axis_of_comparison)

These functions consume any mix of :class:`Expression`, :class:`Entity`,
and :class:`Predicate` nodes (i.e., the output of ``evaluate_tree`` over
a ``resolve``'d AST). They never call back into HDC; pure Python set
operations and tree walks.
"""

from __future__ import annotations

from typing import List, Optional, Set, Union

from gse.symbolic.expression import Atom, Expression, Negation, Op, Phrase
from gse.symbolic.predicates import (
    BoundaryCase,
    Causation,
    Comparison,
    Contrast,
    DegreeQuery,
    Equality,
    MinimalSufficiency,
    Predicate,
    SetRestriction,
    TypeQuery,
)
from gse.symbolic.resolution import Entity


# Anything that can show up in an evaluated symbolic tree.
TreeNode = Union[Expression, Entity, Predicate]


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def entities(tree: TreeNode) -> List[Entity]:
    """Return every Entity in the tree, in document order.

    "The dog is cuter than the cat" → [Entity(dog), Entity(cat)].
    """
    seen_lemmas: Set[tuple] = set()
    out: List[Entity] = []

    def _walk(n: TreeNode) -> None:
        if isinstance(n, Entity):
            key = (n.head.lemma, n.head.position)
            if key not in seen_lemmas:
                seen_lemmas.add(key)
                out.append(n)
            if n.possessor is not None:
                _walk(n.possessor)
            return
        if isinstance(n, Op):
            for a in n.args:
                _walk(a)
            return
        if isinstance(n, Negation):
            _walk(n.operand)
            return
        if isinstance(n, Phrase):
            for a in n.atoms:
                _walk(a)
            return
        # Predicate types — walk their content fields
        if isinstance(n, Comparison):
            _walk(n.lhs); _walk(n.rhs); return
        if isinstance(n, Equality):
            _walk(n.lhs); _walk(n.rhs); return
        if isinstance(n, TypeQuery):
            _walk(n.entity); return
        if isinstance(n, DegreeQuery):
            _walk(n.entity); return
        if isinstance(n, MinimalSufficiency):
            _walk(n.threshold); _walk(n.purpose); return
        if isinstance(n, SetRestriction):
            _walk(n.member); _walk(n.predicate); return
        if isinstance(n, BoundaryCase):
            _walk(n.entity); _walk(n.predicate); return
        if isinstance(n, Contrast):
            _walk(n.left); _walk(n.right); return
        if isinstance(n, Causation):
            _walk(n.cause); _walk(n.effect); return
        # Atom — leaf, nothing to traverse further

    _walk(tree)
    return out


def entity_lemmas(tree: TreeNode) -> List[str]:
    """Convenience: the lemmas of every entity in document order."""
    return [e.head.lemma for e in entities(tree)]


# ---------------------------------------------------------------------------
# Predicate extraction
# ---------------------------------------------------------------------------


def predicates(tree: TreeNode) -> List[Predicate]:
    """Return every Predicate in the tree (nested traversal)."""
    out: List[Predicate] = []
    _predicate_classes = (
        Comparison, Equality, TypeQuery, DegreeQuery, MinimalSufficiency,
        SetRestriction, BoundaryCase, Contrast, Causation,
    )

    def _walk(n: TreeNode) -> None:
        if isinstance(n, _predicate_classes):
            out.append(n)
        # Predicates can wrap Expression children — walk them too in case
        # of nested operators.
        if isinstance(n, Op):
            for a in n.args:
                _walk(a)
        elif isinstance(n, Negation):
            _walk(n.operand)
        elif isinstance(n, Phrase):
            for a in n.atoms:
                _walk(a)
        elif isinstance(n, Entity):
            if n.possessor is not None:
                _walk(n.possessor)
        # Walk Predicate children (in case of nesting)
        if isinstance(n, Comparison):
            _walk(n.lhs); _walk(n.rhs)
        elif isinstance(n, Equality):
            _walk(n.lhs); _walk(n.rhs)
        elif isinstance(n, TypeQuery):
            _walk(n.entity)
        elif isinstance(n, DegreeQuery):
            _walk(n.entity)
        elif isinstance(n, MinimalSufficiency):
            _walk(n.threshold); _walk(n.purpose)
        elif isinstance(n, SetRestriction):
            _walk(n.member); _walk(n.predicate)
        elif isinstance(n, BoundaryCase):
            _walk(n.entity); _walk(n.predicate)
        elif isinstance(n, Contrast):
            _walk(n.left); _walk(n.right)
        elif isinstance(n, Causation):
            _walk(n.cause); _walk(n.effect)

    _walk(tree)
    return out


# ---------------------------------------------------------------------------
# Axis of comparison
# ---------------------------------------------------------------------------


def axis_of_comparison(node: TreeNode) -> Optional[str]:
    """Best-guess axis for a Comparison / Equality / DegreeQuery.

    Walks the relevant content fields looking for the first adjective/
    adverb atom (POS == ``ADJ`` or ``ADV``) and returns its lemma. For
    "Mike is taller than Rex" the lhs span typically includes "tall"
    as ADJ (post-lemmatization).

    Returns the predicate's stored ``axis`` field if set; otherwise
    infers from the args' POS. Returns ``None`` if no candidate found.
    """
    if isinstance(node, (Comparison, Equality, DegreeQuery)):
        if getattr(node, "axis", None):
            return node.axis
        # Walk the lhs / rhs / entity content looking for ADJ/ADV
        targets: List[TreeNode] = []
        if isinstance(node, Comparison):
            targets = [node.lhs, node.rhs]
        elif isinstance(node, Equality):
            targets = [node.lhs, node.rhs]
        else:  # DegreeQuery
            targets = [node.entity]
        for t in targets:
            axis = _first_adj_adv(t)
            if axis is not None:
                return axis
    return None


def _first_adj_adv(node: TreeNode) -> Optional[str]:
    """Find the leftmost ADJ/ADV atom (or Entity.modifier) in a subtree."""
    if isinstance(node, Atom):
        if node.pos in ("ADJ", "ADV"):
            return node.lemma
        return None
    if isinstance(node, Entity):
        # Resolution preserves the source Phrase's ADJ/ADV as Entity.modifier.
        # This is the canonical recovery path after resolve().
        if node.modifier is not None:
            return node.modifier.lemma
        # Entity head shouldn't be an adjective, but check as a fallback
        if node.head.pos in ("ADJ", "ADV"):
            return node.head.lemma
        return None
    if isinstance(node, Phrase):
        for a in node.atoms:
            if a.pos in ("ADJ", "ADV"):
                return a.lemma
        return None
    if isinstance(node, Negation):
        return _first_adj_adv(node.operand)
    if isinstance(node, Op):
        for a in node.args:
            found = _first_adj_adv(a)
            if found is not None:
                return found
    return None


# ---------------------------------------------------------------------------
# Logical equality and argument swap
# ---------------------------------------------------------------------------


def is_logically_equal_to(a: TreeNode, b: TreeNode) -> bool:
    """True if two trees have the same logical structure + entity content.

    Stricter than ``==`` because it ignores positions, roles, and
    word_primitives — just looks at structural shape and lemma identity.
    "Dog is taller than cat" should logically equal itself even if the
    two trees were built from different traces.
    """
    return _structural_signature(a) == _structural_signature(b)


def is_argument_swap_of(a: TreeNode, b: TreeNode) -> bool:
    """True if ``a`` is ``b`` with the args of some top-level operator swapped.

    "Dog cuter than cat" and "Cat cuter than dog" → True. The operation
    and entity set are the same; only the directional argument
    assignment differs.
    """
    if not isinstance(a, (Op, Comparison, Equality, Contrast, Causation, MinimalSufficiency)):
        return False
    if type(a) is not type(b):
        return False
    # Swap b's args and compare structurally
    swapped = _swap_args(b)
    return is_logically_equal_to(a, swapped)


def _swap_args(node: TreeNode) -> TreeNode:
    if isinstance(node, Op):
        if node.arity == 2 and len(node.args) == 2:
            return Op(
                primitive=node.primitive,
                operation=node.operation,
                arity=node.arity,
                args=[node.args[1], node.args[0]],
            )
        return node
    if isinstance(node, Comparison):
        return Comparison(lhs=node.rhs, rhs=node.lhs, sign=node.sign, axis=node.axis)
    if isinstance(node, Equality):
        return Equality(lhs=node.rhs, rhs=node.lhs, axis=node.axis)
    if isinstance(node, Contrast):
        return Contrast(left=node.right, right=node.left)
    if isinstance(node, Causation):
        return Causation(cause=node.effect, effect=node.cause, conjunction=node.conjunction)
    if isinstance(node, MinimalSufficiency):
        return MinimalSufficiency(threshold=node.purpose, purpose=node.threshold)
    return node


def _structural_signature(node: TreeNode):
    """A canonical tuple representation for structural comparison."""
    if isinstance(node, Atom):
        return ("Atom", node.lemma)
    if isinstance(node, Phrase):
        return ("Phrase", tuple(_structural_signature(a) for a in node.atoms))
    if isinstance(node, Negation):
        return ("Negation", _structural_signature(node.operand))
    if isinstance(node, Op):
        return (
            "Op", node.operation, node.arity,
            tuple(_structural_signature(a) for a in node.args),
        )
    if isinstance(node, Entity):
        return (
            "Entity",
            node.head.lemma,
            _structural_signature(node.possessor) if node.possessor else None,
        )
    if isinstance(node, Comparison):
        return ("Comparison", node.sign, _structural_signature(node.lhs),
                _structural_signature(node.rhs))
    if isinstance(node, Equality):
        return ("Equality", _structural_signature(node.lhs),
                _structural_signature(node.rhs))
    if isinstance(node, TypeQuery):
        return ("TypeQuery", _structural_signature(node.entity))
    if isinstance(node, DegreeQuery):
        return ("DegreeQuery", _structural_signature(node.entity))
    if isinstance(node, MinimalSufficiency):
        return ("MinimalSufficiency", _structural_signature(node.threshold),
                _structural_signature(node.purpose))
    if isinstance(node, SetRestriction):
        return ("SetRestriction", _structural_signature(node.member),
                _structural_signature(node.predicate))
    if isinstance(node, BoundaryCase):
        return ("BoundaryCase", _structural_signature(node.entity),
                _structural_signature(node.predicate))
    if isinstance(node, Contrast):
        return ("Contrast", _structural_signature(node.left),
                _structural_signature(node.right))
    if isinstance(node, Causation):
        return ("Causation", node.conjunction, _structural_signature(node.cause),
                _structural_signature(node.effect))
    return ("Unknown", repr(node))
