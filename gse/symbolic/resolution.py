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
_COORDINATOR_LEMMAS = frozenset({"and", "or"})
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
        entity_id: stable within-sentence referent id (e.g. ``"e0"``),
            assigned by :func:`gse.symbolic.grounding.resolve_references`. Two
            mentions of one referent share an id (coreference by id); ``None``
            until references are resolved.
        type_thread: root-first type genealogy
            (e.g. ``("thing", "person", "thane")``), populated by a
            ``GenealogyProvider`` during reference resolution. Empty until then.
        span: the **demi-word** — the contiguous undifferentiated nominal lemmas
            when the slot names one multi-token unit ("Lady Macbeth" →
            ``("lady", "macbeth")``). Empty for a single-token referent. The
            *structure* (one slot) decides it is one unit; identity keys off the
            span, so "Lady Macbeth" ≠ "Macbeth" even before either grounds.
    """
    head: Atom
    possessor: Optional["Entity"] = None
    role: Optional[str] = None
    modifier: Optional[Atom] = None
    entity_id: Optional[str] = None
    type_thread: tuple = ()
    span: tuple = ()


@dataclass(frozen=True)
class Coordination:
    """A set-union of coordinated entities sharing one predicate.

    NP-level coordination: "Spot and Rex are dogs" → the subject is
    ``Coordination((Entity(Spot), Entity(Rex)), conjunction="and")``, which the
    clause's predicate (here a TypeAssertion) takes as a single operand. The
    members are a tuple so the node stays hashable like :class:`Entity`.

    ``modifier`` carries any ADJ/ADV comparison axis from the source Phrase
    (e.g. "Spot and Rex are *cuter* than the cat") so ``axis_of_comparison``
    can still recover it after resolution.
    """
    members: tuple
    conjunction: str = "and"
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

    # Coordination: a CCONJ ("and"/"or") joining multiple entity heads is a
    # set-union of entities ("Spot and Rex"), not a single entity. Build a
    # Coordination over each entity atom rather than dropping all but one.
    coordinator = next(
        (a for a in atoms
         if a.pos == "CCONJ" and a.lemma in _COORDINATOR_LEMMAS),
        None,
    )
    entity_atoms = [a for a in atoms if _is_entity_atom(a)]
    if coordinator is not None and len(entity_atoms) > 1:
        members = tuple(
            Entity(head=a, role=a.role) for a in entity_atoms
        )
        return Coordination(
            members=members, conjunction=coordinator.lemma, modifier=modifier
        )

    # No possessive — pick the entity head (rightmost entity atom).
    if len(entity_atoms) == 1:
        return Entity(
            head=entity_atoms[0],
            role=entity_atoms[0].role,
            modifier=modifier,
        )
    if len(entity_atoms) > 1:
        # Multiple contiguous undifferentiated nominals with no coordinator and
        # no possessive — a **demi-word** ("Lady Macbeth"). The structure (one
        # slot, no coordination) says it is one unit; keep the whole span as the
        # referent's identity (rightmost as the syntactic head), so it no longer
        # collapses to its head token and unify with a bare "Macbeth".
        return Entity(
            head=entity_atoms[-1],
            role=entity_atoms[-1].role,
            modifier=modifier,
            span=tuple(a.lemma for a in entity_atoms),
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
    """Substitute pronouns with the most-recent COMPATIBLE prior entity.

    Walks left-to-right in document order, binding each pronoun to the most-recent
    non-pronoun entity — but with two binding-theory refinements over the bare
    most-recent rule (which mis-bound a clausemate subject and collapsed two pronouns
    onto one entity):

    * **Anti-reflexive (Principle B):** a (non-reflexive) pronoun argument of a clause
      does not bind to a *co-argument* of that same clause. So "The brother betrayed
      him" → ``him`` ≠ brother (stays unresolved rather than reflexive); "...it feared
      him" → ``him`` ≠ the fearer.
    * **Distinctness:** two pronoun arguments of one clause bind to *different*
      entities, so "the wolf chased the fox and it feared him" → ``it`` = fox, ``him``
      = wolf (not both fox).

    A pronoun with no compatible antecedent is left unresolved — better than a wrong
    bind. (Cross-sentence antecedents are out of scope here: emit is per-sentence.)
    """
    seen_entities: List[Entity] = []

    def _bind_one(e: Entity, excluded: set) -> Expression:
        """Bind pronoun ``e`` to the most-recent prior non-pronoun entity whose head is
        not in ``excluded`` (its clause's co-arguments + entities already taken by a
        sibling pronoun). Returns the pronoun unchanged if none qualifies."""
        for prior in reversed(seen_entities):
            if _is_pronoun_atom(prior.head):
                continue
            if prior.head.lemma in excluded:       # by referent (lemma), not atom id:
                continue                            # the co-arg may recur as a distinct atom
            return Entity(head=prior.head, possessor=prior.possessor, role=e.role)
        return e

    def _walk(e: Expression) -> Expression:
        if isinstance(e, Entity):
            # Default binding (a pronoun NOT inside an EVENT's arg list — e.g. a direct
            # operand of a clause-linker): plain most-recent, no co-argument exclusion.
            if _is_pronoun_atom(e.head):
                bound = _bind_one(e, set())
                if bound is e:
                    seen_entities.append(e)        # unresolved → still a referent slot
                return bound
            seen_entities.append(e)
            return e
        if isinstance(e, Op):
            # Anti-reflexive + distinctness apply only to EVENT, whose args are genuine
            # co-arguments (agent/patient) — they cannot corefer. A clause-linking op
            # (CAUSAL_SOURCE / TEMPORAL / IMPLIES / CLAUSE_COORD) takes whole CLAUSES, so
            # a pronoun in one clause MAY bind into the sibling clause ("Mike left
            # because he was tired" → he = Mike); bind those by plain recency.
            if e.operation != "EVENT":
                return Op(
                    primitive=e.primitive, operation=e.operation, arity=e.arity,
                    args=[_walk(a) for a in e.args],
                )
            new_args: List[Expression] = [None] * len(e.args)  # type: ignore[list-item]
            # Pass 1: resolve the non-pronoun args first — they are this clause's
            # co-arguments, which its pronoun args must avoid (anti-reflexive).
            excluded: set = set()
            for i, a in enumerate(e.args):
                if isinstance(a, Entity) and _is_pronoun_atom(a.head):
                    continue
                new_args[i] = _walk(a)
                if isinstance(new_args[i], Entity):
                    excluded.add(new_args[i].head.lemma)
            # Pass 2: bind pronoun args, avoiding co-arguments AND each other (distinct).
            for i, a in enumerate(e.args):
                if new_args[i] is not None:
                    continue
                bound = _bind_one(a, excluded)
                new_args[i] = bound
                if bound is a:                      # unresolved → still a referent slot
                    seen_entities.append(a)
                else:                               # bound: next sibling pronoun avoids it
                    excluded.add(bound.head.lemma)
            return Op(
                primitive=e.primitive,
                operation=e.operation,
                arity=e.arity,
                args=new_args,
            )
        if isinstance(e, Negation):
            return Negation(operand=_walk(e.operand))
        if isinstance(e, Phrase):
            return Phrase(atoms=list(e.atoms))
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
