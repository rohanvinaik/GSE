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

from dataclasses import dataclass, replace
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


# ---------------------------------------------------------------------------
# M3a — the abstention signal (grounding confidence, fidelity-tiered)
# ---------------------------------------------------------------------------
#
# The deterministic core does not drive flags to zero (Eigen's error threshold):
# the residual *is* the signal. grounding_flags() emits the catalogued residual
# of low-confidence sites alongside the (still-derived) structure — closing the
# abstention-under-ambiguity proof COMPLEX_SENTENCE_DESIGN.md M3 deferred.


@dataclass(frozen=True)
class GroundingFlag:
    """A flagged grounding site — the abstention signal.

    ``tier`` follows the DNA fidelity-tier model: 1 = self-contradiction (the
    tree disagrees with itself, no cross-reference needed), 2 = cross-strand
    (a read and its grounding disagree). ``confidence`` is the residual coherence
    at the site (lower = weaker)."""
    entity_id: str
    lemma: str
    tier: int
    kind: str          # "ungrounded" | "incomparable"
    confidence: float


def _strand_root(thread: Tuple[str, ...]) -> str:
    """The strand a thread belongs to, by its root node — so coherence is only
    ever compared *within* a vocabulary (WordNet 'entity' ⟂ DBpedia 'Thing')."""
    return thread[0] if thread else ""


def _walk_predicates(node: Any):
    """Yield every predicate node in the evaluated tree (pre-order)."""
    name = type(node).__name__
    if name in _OPERAND_FIELDS:
        yield node
        for f in _OPERAND_FIELDS[name]:
            yield from _walk_predicates(getattr(node, f))
    elif name == "Negation":
        yield from _walk_predicates(node.operand)
    elif name == "Op":
        for a in node.args:
            yield from _walk_predicates(a)
    elif name == "Coordination":
        for m in node.members:
            yield from _walk_predicates(m)


def grounding_flags(node: Any, incomparable_threshold: float = 0.2) -> List[GroundingFlag]:
    """Catalogue the low-confidence grounding sites in a *resolved* tree.

    Two fidelity-tiered checks, computable from the threads alone:

    * **Tier 2 — ungrounded**: an entity neither the lexicon (word_primitives)
      nor the genealogy (type_thread) can ground. GSE abstains *honestly* on
      out-of-vocabulary words — and still derives the structure around them.
    * **Tier 1 — incomparable**: a comparison/equality whose two operands are
      grounded in the *same strand* yet share only the root (Jaccard below
      threshold) — "you can't compare an animal to an abstraction." A
      self-contradiction in the tree, no external reference needed.

    Returns the residual; an empty list means a clean, confidently-grounded tree.
    """
    flags: List[GroundingFlag] = []

    # Tier 2 — ungrounded entities (deduped by id).
    collected: List[Entity] = []
    _collect_entities(node, collected)
    seen: set = set()
    for ent in collected:
        eid = ent.entity_id or f"@{_signature(ent)}"
        if eid in seen:
            continue
        seen.add(eid)
        grounded = bool(getattr(ent.head, "word_primitives", None)) or bool(ent.type_thread)
        if not grounded:
            flags.append(GroundingFlag(ent.entity_id or "", ent.head.lemma, 2, "ungrounded", 0.0))

    # Tier 1 — incomparable operands (same strand, share ~only the root).
    for pred in _walk_predicates(node):
        if type(pred).__name__ not in ("Comparison", "Equality"):
            continue
        a, b = pred.lhs, pred.rhs
        ta = tuple(getattr(a, "type_thread", ()) or ())
        tb = tuple(getattr(b, "type_thread", ()) or ())
        if not (ta and tb) or _strand_root(ta) != _strand_root(tb):
            continue  # ungrounded (caught above) or cross-vocabulary (uncomparable by us)
        j = _jaccard(set(ta), set(tb))
        if j < incomparable_threshold:
            lemma_a = getattr(getattr(a, "head", None), "lemma", "?")
            flags.append(GroundingFlag(getattr(a, "entity_id", "") or "",
                                       lemma_a, 1, "incomparable", j))

    return flags
