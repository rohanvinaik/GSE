"""
Reference resolution — Stage 2 (M2.1) of ``docs/RESOLVED_STRUCTURE_DESIGN.md``.

Turns *parsed* structure into *resolved* structure: assigns each referent a
stable within-sentence ``entity_id`` (coreference by id) and populates each
entity's ``type_thread`` (type genealogy) from an injectable
:class:`GenealogyProvider`. The annotated tree drives the emit contract's v2
entity-refs (``{entity_id, lemma, type_thread}``).

This module is **DB-free and deterministic**: id assignment is a fixed
first-occurrence ordering by token position; the genealogy source is injected,
so the symbolic layer stays testable without the multi-GB lexical databases.
The real DB-backed provider (``genus_hierarchy`` for common nouns,
``sparse_wiki`` for proper nouns, coherence-scored sense selection) is M2.2 and
plugs in here without touching this contract.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Protocol, Sequence, Tuple, runtime_checkable

from gse.symbolic.resolution import Entity

# Operand-bearing fields per predicate type — the recursion map for the generic
# entity walker. Mirrors emit._PRED_SPEC's arg fields (single source would
# couple the modules; kept parallel and asserted by tests instead).
_OPERAND_FIELDS: Dict[str, Tuple[str, ...]] = {
    "Comparison": ("lhs", "rhs"),
    "Equality": ("lhs", "rhs"),
    "TypeAssertion": ("entity", "kind"),
    "TypeQuery": ("entity",),
    "DegreeQuery": ("entity",),
    "MinimalSufficiency": ("threshold", "purpose"),
    "SetRestriction": ("member", "predicate"),
    "BoundaryCase": ("entity", "predicate"),
    "Contrast": ("left", "right"),
    "Causation": ("cause", "effect"),
    "RelativeRestriction": ("head", "restriction"),
    "Control": ("controller", "inner"),
}


# ---------------------------------------------------------------------------
# Genealogy provider (injectable; M2.2 supplies the DB-backed implementation)
# ---------------------------------------------------------------------------


@runtime_checkable
class GenealogyProvider(Protocol):
    """Supplies a root-first type genealogy for an entity head.

    ``thread("thane", "NOUN", is_proper=False)`` → ``("thing", "person",
    "thane")``. Returns ``()`` when no thread is known. Implementations must be
    deterministic (same args → same thread) to preserve the determinism
    guarantee.
    """

    def thread(self, lemma: str, pos: str, is_proper: bool) -> Sequence[str]:
        ...


class NullGenealogy:
    """The empty provider — every thread is ``()``.

    The DB-free default: reference resolution still assigns ids and produces
    valid v2 entity-refs (with empty threads), so the contract shape is
    exercisable without any lexical database. M2.2 swaps in the real provider.
    """

    def thread(self, lemma: str, pos: str, is_proper: bool) -> Sequence[str]:
        return ()


# ---------------------------------------------------------------------------
# Generic entity walker (rebuilds the frozen tree via dataclasses.replace)
# ---------------------------------------------------------------------------


def _is_proper(entity: Entity) -> bool:
    return getattr(entity.head, "pos", None) == "PROPN"


def _signature(entity: Entity) -> Tuple:
    """Referent identity key. Same referent → same signature → same id.

    Within a sentence, a referent is keyed by its head lemma + its possessor's
    signature (so "Mike's dog" and a later "the dog" do NOT collide while
    "Macbeth" … "Macbeth" do). v1 identity is lexical; sense/world identity is
    M2.2 territory.
    """
    poss = _signature(entity.possessor) if entity.possessor is not None else None
    return (entity.head.lemma, poss)


def _position(entity: Entity) -> int:
    return getattr(entity.head, "position", 0)


def _map_entities(node: Any, fn) -> Any:
    """Rebuild ``node`` applying ``fn`` to every :class:`Entity` leaf.

    Total over the evaluated-tree node set (predicates, Coordination, Negation,
    Op, Entity, Atom/Phrase/values). Frozen dataclasses are rebuilt with
    :func:`dataclasses.replace`; non-entity leaves pass through unchanged.
    """
    name = type(node).__name__

    if name == "Entity":
        # Recurse into the possessor first, then apply fn to this entity.
        if node.possessor is not None:
            node = replace(node, possessor=_map_entities(node.possessor, fn))
        return fn(node)

    if name == "Coordination":
        return replace(node, members=tuple(_map_entities(m, fn) for m in node.members))

    if name == "Negation":
        return replace(node, operand=_map_entities(node.operand, fn))

    if name == "Op":
        return replace(node, args=[_map_entities(a, fn) for a in node.args])

    fields = _OPERAND_FIELDS.get(name)
    if fields is not None:
        return replace(node, **{f: _map_entities(getattr(node, f), fn) for f in fields})

    # Atom / Phrase / bare value — no entity to annotate.
    return node


def _collect_entities(node: Any, out: List[Entity]) -> None:
    """Gather every Entity leaf (possessors included) for id assignment."""

    def _grab(e: Entity) -> Entity:
        out.append(e)
        return e

    _map_entities(node, _grab)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _jaccard(a: set, b: set) -> float:
    """Node-set overlap — the coherence primitive (lifted from destash
    coherence.py). 1.0 when both empty (vacuously coherent)."""
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# Minimum coherence advantage required to override the frequency-primary sense.
# WordNet orders senses by frequency, a strong prior; a noisy context word must
# not flip a clear primary. king↔bishop clears this easily (~0.5); a stray
# overlap does not.
_COHERENCE_MARGIN = 0.15


def _select_by_coherence(
    collected: List[Entity], genealogy: Any, margin: float = _COHERENCE_MARGIN
) -> Dict[Tuple, Tuple[str, ...]]:
    """Pick each referent's thread by coherence with the rest of the sentence.

    Single deterministic pass. Each entity's candidate threads (all WordNet
    senses + both strands) are scored by node-overlap (Jaccard) with the union
    of the *other* entities' **primary** threads. The frequency-primary sense is
    kept unless a candidate beats it by ``margin`` — so coherence *re-ranks* a
    genuinely ambiguous word (king↔bishop) but never flips a clear primary on a
    noisy neighbour. Coherence can only re-rank existing candidates, never
    invent a thread.
    """
    cand: Dict[Tuple, List[Tuple[str, ...]]] = {}
    for ent in collected:
        sig = _signature(ent)
        if sig in cand:
            continue
        cand[sig] = [
            tuple(t)
            for t in genealogy.candidates(
                ent.head.lemma, getattr(ent.head, "pos", "") or "", _is_proper(ent)
            )
        ]

    primary: Dict[Tuple, Tuple[str, ...]] = {
        sig: (cs[0] if cs else ()) for sig, cs in cand.items()
    }

    chosen: Dict[Tuple, Tuple[str, ...]] = {}
    for sig, cs in cand.items():
        if len(cs) <= 1:
            chosen[sig] = primary[sig]
            continue
        context: set = set()
        for other_sig, thread in primary.items():
            if other_sig != sig:
                context |= set(thread)
        prim = cs[0]
        prim_score = _jaccard(set(prim), context)
        best, best_score = prim, prim_score
        for thread in cs[1:]:
            score = _jaccard(set(thread), context)
            if score > prim_score + margin and score > best_score:
                best, best_score = thread, score
        chosen[sig] = best

    return chosen


def resolve_references(node: Any, genealogy: GenealogyProvider | None = None) -> Any:
    """Annotate an evaluated tree with stable ids + type threads.

    1. Assign ``entity_id`` per distinct referent, in first-occurrence order by
       token position (deterministic; coreferent mentions share an id).
    2. Populate ``type_thread`` from ``genealogy``. If the provider exposes
       ``candidates()``, the thread is chosen by **global coherence**
       (sense/strand that coheres with the rest of the sentence); otherwise the
       provider's single ``thread()`` is used (default: empty threads).

    Returns a new tree; the input is unmodified (frozen rebuild).
    """
    if genealogy is None:
        genealogy = NullGenealogy()

    collected: List[Entity] = []
    _collect_entities(node, collected)

    # First-occurrence order by position → deterministic id minting.
    sig_to_id: Dict[Tuple, str] = {}
    for ent in sorted(collected, key=_position):
        sig = _signature(ent)
        if sig not in sig_to_id:
            sig_to_id[sig] = f"e{len(sig_to_id)}"

    # Coherence-scored thread selection when the provider supports candidates.
    if hasattr(genealogy, "candidates"):
        sig_thread = _select_by_coherence(collected, genealogy)
    else:
        sig_thread = {}
        for ent in collected:
            sig = _signature(ent)
            if sig not in sig_thread:
                sig_thread[sig] = tuple(
                    genealogy.thread(
                        ent.head.lemma, getattr(ent.head, "pos", "") or "", _is_proper(ent)
                    )
                )

    def annotate(ent: Entity) -> Entity:
        sig = _signature(ent)
        return replace(ent, entity_id=sig_to_id[sig], type_thread=sig_thread.get(sig, ()))

    return _map_entities(node, annotate)
