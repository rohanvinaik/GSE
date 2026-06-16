"""
Phase B6: structural templating.

Per ``sentence_architecture.md`` line 154, the symbolic layer should be
able to substitute arbitrary entities while preserving structure:
"the <animal in lexicon> is cuter than the <second animal in lexicon>".

This module provides :func:`substitute` — a pure-Python tree rewriter
that walks an Expression / Predicate tree and swaps matching Entity
nodes per a lemma-keyed mapping. Preserves operation labels, arity,
direction (e.g., Causation's cause/effect), and all non-substituted
content.
"""

from __future__ import annotations

from typing import Mapping, Union

from gse.symbolic.expression import Atom, Expression, Negation, Op, Phrase
from gse.symbolic.predicates import (
    BoundaryCase,
    Causation,
    Comparison,
    Contrast,
    Control,
    DegreeQuery,
    Equality,
    MinimalSufficiency,
    Predicate,
    RelativeRestriction,
    SetRestriction,
    TypeAssertion,
    TypeQuery,
)
from gse.symbolic.resolution import Coordination, Entity

TreeNode = Union[Expression, Entity, Predicate]


def substitute(tree: TreeNode, mapping: Mapping[str, Union[str, Entity, Atom]]) -> TreeNode:
    """Walk a tree and substitute entities per ``mapping``.

    Each key in ``mapping`` is a lemma to match against ``Entity.head.lemma``.
    Each value is either:

    * a string — the substitute lemma (other Entity fields preserved).
    * an :class:`Atom` — used as the new ``Entity.head`` directly.
    * an :class:`Entity` — replaces the matching node wholesale.

    Atoms outside of Entity wrappers are also substituted when their
    lemma matches a key (useful for raw Phrase-mode trees).

    Returns a new tree; the input is not mutated. Possessor entities
    are walked recursively. Structural operators (Op, Predicate types)
    pass through with their args/fields substituted.

    Examples
    --------
    >>> tree = evaluate_tree(resolve(from_trace(encoder.encode(
    ...     "The dog is cuter than the cat"))))
    >>> templated = substitute(tree, {"dog": "rabbit", "cat": "mouse"})
    >>> # The Comparison now references rabbit and mouse instead.
    """
    return _walk(tree, mapping)


def _make_replacement(
    original_entity: Entity,
    replacement: Union[str, Atom, Entity],
) -> Entity:
    """Build the new Entity for a matched substitution."""
    if isinstance(replacement, Entity):
        # Wholesale replacement
        return replacement
    if isinstance(replacement, Atom):
        return Entity(
            head=replacement,
            possessor=original_entity.possessor,
            role=original_entity.role,
            modifier=original_entity.modifier,
        )
    if isinstance(replacement, str):
        new_head = Atom(
            lemma=replacement,
            word_primitives=dict(original_entity.head.word_primitives),
            role=original_entity.head.role,
            position=original_entity.head.position,
            pos=original_entity.head.pos,
        )
        return Entity(
            head=new_head,
            possessor=original_entity.possessor,
            role=original_entity.role,
            modifier=original_entity.modifier,
        )
    raise TypeError(
        f"substitute mapping value must be str, Atom, or Entity; "
        f"got {type(replacement).__name__}"
    )


def _walk(node: TreeNode, mapping: Mapping[str, Union[str, Entity, Atom]]) -> TreeNode:
    if isinstance(node, Entity):
        if node.head.lemma in mapping:
            return _make_replacement(node, mapping[node.head.lemma])
        if node.possessor is not None:
            new_possessor = _walk(node.possessor, mapping)
            if new_possessor is not node.possessor:
                return Entity(
                    head=node.head,
                    possessor=new_possessor,
                    role=node.role,
                )
        return node

    if isinstance(node, Atom):
        if node.lemma in mapping:
            replacement = mapping[node.lemma]
            if isinstance(replacement, Atom):
                return replacement
            if isinstance(replacement, str):
                return Atom(
                    lemma=replacement,
                    word_primitives=dict(node.word_primitives),
                    role=node.role,
                    position=node.position,
                    pos=node.pos,
                )
            if isinstance(replacement, Entity):
                return replacement.head
        return node

    if isinstance(node, Phrase):
        new_atoms = [_walk(a, mapping) for a in node.atoms]
        return Phrase(atoms=new_atoms)

    if isinstance(node, Negation):
        return Negation(operand=_walk(node.operand, mapping))

    if isinstance(node, Op):
        return Op(
            primitive=node.primitive,
            operation=node.operation,
            arity=node.arity,
            args=[_walk(a, mapping) for a in node.args],
        )

    if isinstance(node, Comparison):
        return Comparison(
            lhs=_walk(node.lhs, mapping),
            rhs=_walk(node.rhs, mapping),
            sign=node.sign,
            axis=node.axis,
        )
    if isinstance(node, Equality):
        return Equality(
            lhs=_walk(node.lhs, mapping),
            rhs=_walk(node.rhs, mapping),
            axis=node.axis,
        )
    if isinstance(node, TypeQuery):
        return TypeQuery(entity=_walk(node.entity, mapping))
    if isinstance(node, DegreeQuery):
        return DegreeQuery(entity=_walk(node.entity, mapping), axis=node.axis)
    if isinstance(node, MinimalSufficiency):
        return MinimalSufficiency(
            threshold=_walk(node.threshold, mapping),
            purpose=_walk(node.purpose, mapping),
        )
    if isinstance(node, SetRestriction):
        return SetRestriction(
            member=_walk(node.member, mapping),
            predicate=_walk(node.predicate, mapping),
        )
    if isinstance(node, BoundaryCase):
        return BoundaryCase(
            entity=_walk(node.entity, mapping),
            predicate=_walk(node.predicate, mapping),
            note=node.note,
        )
    if isinstance(node, Contrast):
        return Contrast(
            left=_walk(node.left, mapping),
            right=_walk(node.right, mapping),
        )
    if isinstance(node, Causation):
        return Causation(
            cause=_walk(node.cause, mapping),
            effect=_walk(node.effect, mapping),
            conjunction=node.conjunction,
        )
    if isinstance(node, TypeAssertion):
        return TypeAssertion(
            entity=_walk(node.entity, mapping),
            kind=_walk(node.kind, mapping),
        )
    if isinstance(node, RelativeRestriction):
        return RelativeRestriction(
            head=_walk(node.head, mapping),
            restriction=_walk(node.restriction, mapping),
        )
    if isinstance(node, Control):
        return Control(
            controller=_walk(node.controller, mapping),
            inner=_walk(node.inner, mapping),
        )
    if isinstance(node, Coordination):
        return Coordination(
            members=tuple(_walk(m, mapping) for m in node.members),
            conjunction=node.conjunction,
            modifier=node.modifier,
        )

    return node
