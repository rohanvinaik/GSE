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

from dataclasses import replace
from typing import Mapping, Union

from gse.symbolic.expression import Atom, Expression, Negation, Op, Phrase
from gse.symbolic.predicates import OPERAND_FIELDS, Event, Predicate
from gse.symbolic.resolution import Coordination, Entity

TreeNode = Union[Expression, Entity, Predicate]


def substitute(tree: TreeNode, mapping: Mapping[str, Union[str, Entity, Atom]]) -> TreeNode:
    """Walk a tree and substitute entities per ``mapping``.

    Each key in ``mapping`` is a lemma to match against ``Entity.head.lemma``.
    Each value is either:

    * a string — the substitute lemma. The entity keeps its SLOT: possessor,
      role, modifier and ``entity_id`` (coreference by id) survive, and the
      head keeps its grammatical attributes (position, POS, number, …). Its
      GROUNDING — ``type_thread``, ``span`` and ``apposition_thread``, computed
      for the old head — is cleared: it does not describe the new word. Re-run
      reference resolution to ground the new head (the textual evidence, e.g.
      the head's ``apposition``, is still there for it).
    * an :class:`Atom` — used as the new ``Entity.head`` directly; the same
      slot-kept / grounding-cleared rule applies.
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
    """Build the new Entity for a matched substitution: the slot is kept, the old head's grounding
    is cleared (see :func:`substitute`). Before, a head substitution also dropped ``entity_id``,
    and a string substitution dropped the head's number / graded / apposition."""
    if isinstance(replacement, Entity):
        # Wholesale replacement
        return replacement
    if isinstance(replacement, Atom):
        new_head = replacement
    elif isinstance(replacement, str):
        new_head = replace(
            original_entity.head, lemma=replacement, word_primitives=dict(original_entity.head.word_primitives)
        )
    else:
        raise TypeError(f"substitute mapping value must be str, Atom, or Entity; got {type(replacement).__name__}")
    return replace(original_entity, head=new_head, type_thread=(), span=(), apposition_thread=())


def _walk(node: TreeNode, mapping: Mapping[str, Union[str, Entity, Atom]]) -> TreeNode:
    # A rebuilt node keeps every field the substitution does not touch: dataclasses.replace over the
    # one operand map, predicates.OPERAND_FIELDS — the form grounding._map_entities uses. The
    # hand-listed constructors this replaces dropped fields as the dataclasses grew: a possessed
    # entity lost its modifier and grounding, an Event its themes, a substituted Atom its number /
    # graded / apposition (#5).
    if isinstance(node, Entity):
        if node.head.lemma in mapping:
            return _make_replacement(node, mapping[node.head.lemma])
        if node.possessor is not None:
            new_possessor = _walk(node.possessor, mapping)
            if new_possessor is not node.possessor:
                return replace(node, possessor=new_possessor)
        return node

    if isinstance(node, Atom):
        if node.lemma in mapping:
            replacement = mapping[node.lemma]
            if isinstance(replacement, Atom):
                return replacement
            if isinstance(replacement, str):
                return replace(node, lemma=replacement, word_primitives=dict(node.word_primitives))
            if isinstance(replacement, Entity):
                return replacement.head
        return node

    if isinstance(node, Phrase):
        return Phrase(atoms=[_walk(a, mapping) for a in node.atoms])

    if isinstance(node, Negation):
        return Negation(operand=_walk(node.operand, mapping))

    if isinstance(node, Op):
        return replace(node, args=[_walk(a, mapping) for a in node.args])

    if isinstance(node, Coordination):
        return replace(node, members=tuple(_walk(m, mapping) for m in node.members))

    fields = OPERAND_FIELDS.get(type(node).__name__)
    if fields is not None:
        changes: dict[str, object] = {f: _walk(getattr(node, f), mapping) for f in fields}
        if isinstance(node, Event) and node.themes:
            # The latent secondary args are entities in the sentence too: walked, never dropped.
            changes["themes"] = tuple(_walk(t, mapping) for t in node.themes)
        return replace(node, **changes)

    return node
