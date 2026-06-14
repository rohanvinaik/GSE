"""
Phase B5: argument resolution.

Walks a symbolic Expression tree (built by :func:`gse.symbolic.from_trace`)
and refines unresolved :class:`Phrase` nodes into structured
:class:`Entity` nodes. Three responsibilities:

1. **Entity grouping** — collapses multi-token entity spans (e.g.,
   "the cat" → one Entity with head=cat) by filtering out function words
   (DET, AUX, PART, ADP, etc.) and keeping the entity head (rightmost
   NOUN/PROPN/PRON).
2. **Possessive structuring** — recognizes "Mike's dog" pattern (PROPN
   PART NOUN) and produces ``Entity(head=dog, possessor=Entity(head=Mike))``.
3. **Pronoun binding** — within a single sentence, substitutes pronouns
   with the most-recent entity referent. v1: nearest preceding PROPN
   or NOUN. No gender/number agreement.

Per the scope doc, this is single-sentence only — cross-sentence
coreference is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from gse.symbolic.expression import Atom, Expression, Negation, Op, Phrase


# spaCy POS classes used by the resolver.
_ENTITY_POS = frozenset({"PROPN", "NOUN", "PRON"})
_FUNCTION_POS = frozenset({"DET", "AUX", "PART", "ADP", "SCONJ", "CCONJ", "PUNCT"})
_POSSESSIVE_PART_LEMMAS = frozenset({"'s", "’s", "'"})
_PRONOUN_LEMMAS = frozenset({
    "he", "she", "it", "they", "him", "her", "them",
    "his", "hers", "its", "their", "theirs",
})


@dataclass(frozen=True)
class Entity:
    """A structured entity reference.

    Args:
        head: the entity's head atom (e.g., ``dog`` in "Mike's dog").
        possessor: optional possessor entity for nested constructions
            ("Mike's dog" → ``Entity(head=dog, possessor=Entity(head=Mike))``).
        role: optional grammatical role inherited from the source atoms.
        modifier: optional ADJ/ADV atom from the source Phrase (the
            comparison axis in "the tall dog" or "the dog is taller").
            Preserved through resolution so :func:`queries.axis_of_comparison`
            can recover it from a resolved Predicate.
    """
    head: Atom
    possessor: Optional["Entity"] = None
    role: Optional[str] = None
    modifier: Optional[Atom] = None


# ---------------------------------------------------------------------------
# Phrase → Entity collapse helpers
# ---------------------------------------------------------------------------


def _is_entity_atom(atom: Atom) -> bool:
    return atom.pos in _ENTITY_POS


def _is_possessive_marker(atom: Atom) -> bool:
    return atom.pos == "PART" and atom.lemma in _POSSESSIVE_PART_LEMMAS


def _first_adj_or_adv(atoms) -> Optional[Atom]:
    """Return the first ADJ/ADV atom in a sequence, or None."""
    for a in atoms:
        if a.pos in ("ADJ", "ADV"):
            return a
    return None


def _collapse_phrase_to_entity(phrase: Phrase) -> Expression:
    """Turn a Phrase of atoms into the best-fitting structured Expression.

    Strategy:

    * Filter out function-word atoms.
    * Scan for possessive pattern: PROPN/NOUN + possessive PART + ... + NOUN.
      The trailing NOUN becomes the head; the leading entity is the
      possessor.
    * If exactly one entity atom remains, return ``Entity(head=...)``,
      attaching any ADJ/ADV in the phrase as ``modifier`` (the
      comparison axis).
    * If no entity atoms remain but there are content atoms (e.g., a
      Phrase of only predicates), return the Phrase unchanged.
    * If multiple distinct entities remain without possessive structure,
      pick the rightmost as the head; B5 v1 doesn't model compound
      entities.
    """
    atoms = phrase.atoms
    if not atoms:
        return phrase

    # The phrase's modifier (ADJ/ADV) is the comparison axis — preserve it
    # so axis_of_comparison can recover it post-resolution.
    modifier = _first_adj_or_adv(atoms)

    # Find any possessive marker positions
    possessive_indices = [
        i for i, a in enumerate(atoms) if _is_possessive_marker(a)
    ]
    if possessive_indices:
        # Take the first possessive split: everything left is the
        # possessor span; everything right (after dropping the 's) is
        # the head span.
        split_idx = possessive_indices[0]
        left = atoms[:split_idx]
        right = atoms[split_idx + 1:]
        possessor_entity = _collapse_phrase_to_entity(Phrase(atoms=left))
        head_entity = _collapse_phrase_to_entity(Phrase(atoms=right))
        if isinstance(head_entity, Entity) and isinstance(possessor_entity, Entity):
            return Entity(
                head=head_entity.head,
                possessor=possessor_entity,
                modifier=modifier or head_entity.modifier,
            )
        if isinstance(head_entity, Entity):
            return head_entity  # possessor couldn't be resolved; drop it
        # Head couldn't be resolved either — fall through to default
        # phrase return
        return phrase

    # No possessive — pick the entity head (rightmost entity atom).
    entity_atoms = [a for a in atoms if _is_entity_atom(a)]
    if len(entity_atoms) == 1:
        return Entity(
            head=entity_atoms[0],
            role=entity_atoms[0].role,
            modifier=modifier,
        )
    if len(entity_atoms) > 1:
        # Multiple entities without possessive — pick the last as head;
        # B5 v1 doesn't model coordination ("Mike and Rex"). Surface as
        # the rightmost head; the others are dropped from this entity.
        return Entity(
            head=entity_atoms[-1],
            role=entity_atoms[-1].role,
            modifier=modifier,
        )

    # No entity atoms at all — return atoms without function words,
    # preserving the Phrase shape.
    content_atoms = [a for a in atoms if a.pos not in _FUNCTION_POS]
    if not content_atoms:
        return phrase
    if len(content_atoms) == 1:
        return content_atoms[0]
    return Phrase(atoms=content_atoms)


# ---------------------------------------------------------------------------
# Pronoun binding
# ---------------------------------------------------------------------------


def _is_pronoun_atom(atom: Atom) -> bool:
    return atom.pos == "PRON" or atom.lemma in _PRONOUN_LEMMAS


def _bind_pronouns(expr: Expression) -> Expression:
    """Substitute pronouns with most-recent matching entity in document order.

    v1 strategy: walk the tree left-to-right. When a pronoun atom is
    encountered (Entity whose head is a pronoun), replace it with the
    most-recently-seen non-pronoun Entity. If no antecedent exists yet,
    leave the pronoun in place.
    """
    seen_entities: List[Entity] = []

    def _walk(e: Expression) -> Expression:
        if isinstance(e, Entity):
            if _is_pronoun_atom(e.head) and seen_entities:
                # Bind to the most-recent non-pronoun entity
                for prior in reversed(seen_entities):
                    if not _is_pronoun_atom(prior.head):
                        # Substitute, preserve role from the pronoun's slot
                        return Entity(
                            head=prior.head,
                            possessor=prior.possessor,
                            role=e.role,
                        )
                # All prior were pronouns too — leave as-is
                seen_entities.append(e)
                return e
            seen_entities.append(e)
            return e
        if isinstance(e, Op):
            new_args = [_walk(a) for a in e.args]
            return Op(
                primitive=e.primitive,
                operation=e.operation,
                arity=e.arity,
                args=new_args,
            )
        if isinstance(e, Negation):
            inner = _walk(e.operand)
            return Negation(operand=inner)
        if isinstance(e, Phrase):
            new_atoms = list(e.atoms)
            return Phrase(atoms=new_atoms)
        return e

    return _walk(expr)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve(expr: Expression) -> Expression:
    """Refine Phrases into Entities and bind pronouns.

    Returns a new Expression tree where:

    * Each former :class:`Phrase` is collapsed into an :class:`Entity` (or
      stays as a Phrase if no entity head was identified).
    * Possessive constructions become nested :class:`Entity` nodes with
      ``possessor`` populated.
    * Pronouns are bound to the most-recent same-sentence entity where
      possible.

    Idempotent: ``resolve(resolve(x))`` produces the same shape as
    ``resolve(x)`` since Entity nodes are passed through unchanged.
    """
    refined = _refine(expr)
    return _bind_pronouns(refined)


def _refine(expr: Expression) -> Expression:
    """Inner walker — collapse Phrases into Entities, leave other nodes."""
    if isinstance(expr, Phrase):
        return _collapse_phrase_to_entity(expr)
    if isinstance(expr, Op):
        return Op(
            primitive=expr.primitive,
            operation=expr.operation,
            arity=expr.arity,
            args=[_refine(a) for a in expr.args],
        )
    if isinstance(expr, Negation):
        return Negation(operand=_refine(expr.operand))
    if isinstance(expr, Atom):
        # Lone atoms — if entity-bearing, wrap as Entity
        if _is_entity_atom(expr):
            return Entity(head=expr, role=expr.role)
        return expr
    return expr
