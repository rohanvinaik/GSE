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
# M4-3a — document scope (cross-sentence coreference + global ids + threads)
# ---------------------------------------------------------------------------
#
# Completion is recursion, not addition: the within-sentence resolver lifts to a
# document by minting ids over *all* the sentences' entities at once (so one
# referent shares an id across sentences) and binding pronouns left unbound by
# their own sentence to an antecedent in a prior one.


def _is_pronoun(ent: Entity) -> bool:
    # resolve() already rebinds *within-sentence* pronouns to their antecedent's
    # head, so a head still tagged PRON here is one that found no local antecedent.
    return getattr(ent.head, "pos", None) == "PRON"


def _bind_document_pronouns(trees: Sequence[Any]) -> List[Any]:
    """Bind cross-sentence pronouns to the most-recent prior non-pronoun entity.

    v1, matching the within-sentence binder: nearest antecedent in document
    order, no gender/number agreement."""
    antecedents: List[Entity] = []
    out: List[Any] = []
    for tree in trees:
        def bind(ent: Entity) -> Entity:
            if _is_pronoun(ent) and antecedents:
                ante = antecedents[-1]
                return replace(ent, head=ante.head, possessor=ante.possessor)
            return ent

        bound = _map_entities(tree, bind)
        post: List[Entity] = []
        _collect_entities(bound, post)
        for ent in post:
            if not _is_pronoun(ent):
                antecedents.append(ent)
        out.append(bound)
    return out


def resolve_document(
    trees: Sequence[Any], genealogy: GenealogyProvider | None = None
) -> List[Any]:
    """Resolve a *document* — an ordered list of evaluated clause trees.

    Lifts resolve_references to document scope: cross-sentence pronouns are
    bound to a prior antecedent, ``entity_id`` is minted globally (one referent
    → one id across all sentences), and coherence-scored thread selection runs
    over the **whole document's** entities. Returns the trees, each annotated.
    """
    if genealogy is None:
        genealogy = NullGenealogy()

    trees = _bind_document_pronouns(trees)

    # All entities in document order: (sentence index, token position).
    indexed: List[Tuple[int, Entity]] = []
    flat: List[Entity] = []
    for s_idx, tree in enumerate(trees):
        ents: List[Entity] = []
        _collect_entities(tree, ents)
        for ent in ents:
            indexed.append((s_idx, ent))
            flat.append(ent)

    sig_to_id: Dict[Tuple, str] = {}
    for _, ent in sorted(indexed, key=lambda se: (se[0], _position(se[1]))):
        sig = _signature(ent)
        if sig not in sig_to_id:
            sig_to_id[sig] = f"e{len(sig_to_id)}"

    if hasattr(genealogy, "candidates"):
        sig_thread = _select_by_coherence(flat, genealogy)
    else:
        sig_thread = {}
        for ent in flat:
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

    return [_map_entities(tree, annotate) for tree in trees]


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
    pos: str = ""      # spaCy POS of the flagged token — the triage covariate


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
            flags.append(GroundingFlag(ent.entity_id or "", ent.head.lemma, 2,
                                       "ungrounded", 0.0, getattr(ent.head, "pos", "") or ""))

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
            head_a = getattr(a, "head", None)
            lemma_a = getattr(head_a, "lemma", "?")
            pos_a = getattr(head_a, "pos", "") or ""
            flags.append(GroundingFlag(getattr(a, "entity_id", "") or "",
                                       lemma_a, 1, "incomparable", j, pos_a))

    return flags


# ---------------------------------------------------------------------------
# M3b — persist / Tier-3 triage (the "errors coherent with each other" level)
# ---------------------------------------------------------------------------
#
# One level up from M3a: run the flags over a *corpus* and ask whether a flag
# correlates with a covariate (the flagged token's spaCy tag-class). Correlated
# ⇒ a *systematic* mechanism fault — distrust that class. Uncorrelated ⇒ a SNP,
# catalogue it and move on. (DNA: a recurring lesion at one locus is a hotspot;
# a one-off is a SNP.) The covariate is the spaCy POS — exactly "that label
# class" in the propose→veto framing.


def _spearman(x: List[float], y: List[float]) -> float:
    """Spearman rank correlation (no-scipy, lifted from destash coherence.py)."""
    n = len(x)
    if n < 3:
        return 0.0

    def _rank(values: List[float]) -> List[float]:
        indexed = sorted(enumerate(values), key=lambda t: t[1])
        ranks = [0.0] * n
        for rank_val, (orig_idx, _) in enumerate(indexed):
            ranks[orig_idx] = float(rank_val + 1)
        return ranks

    rx, ry = _rank(x), _rank(y)
    d_sq = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - (6 * d_sq) / (n * (n**2 - 1))


@dataclass(frozen=True)
class TriageResult:
    """The systematic-vs-SNP split over a flag corpus.

    ``systematic`` — tag-classes whose flag rate runs well above baseline (a
    mechanism fault: distrust the class). Each entry is
    ``(pos, rate, n_flagged, n_total)``. ``snps`` — the residual flags, each
    idiosyncratic to its site. ``concentration`` — Spearman ρ between per-class
    occurrence and flag counts: high ρ ⇒ flags spread proportionally (no
    systematic locus); lower ρ ⇒ flags concentrate (a hotspot exists)."""
    systematic: tuple
    snps: tuple
    concentration: float


def triage_flags(
    trees: Sequence[Any], min_support: int = 3, systematic_multiplier: float = 2.0
) -> TriageResult:
    """Split a corpus of flagged trees into systematic faults vs SNPs.

    ``trees`` are *resolved* trees (post resolve_references). For each, the
    entity population gives the denominators (by spaCy POS) and grounding_flags
    gives the numerators. A POS class with support ≥ ``min_support`` and a flag
    rate above ``systematic_multiplier`` × baseline is systematic; its flags are
    a mechanism fault. All other flags are SNPs.
    """
    total_by_pos: Dict[str, int] = {}
    flagged_by_pos: Dict[str, int] = {}
    all_flags: List[GroundingFlag] = []

    for tree in trees:
        ents: List[Entity] = []
        _collect_entities(tree, ents)
        seen: set = set()
        for ent in ents:
            eid = ent.entity_id or f"@{_signature(ent)}"
            if eid in seen:
                continue
            seen.add(eid)
            p = getattr(ent.head, "pos", "") or "?"
            total_by_pos[p] = total_by_pos.get(p, 0) + 1
        for flag in grounding_flags(tree):
            all_flags.append(flag)
            key = flag.pos or "?"
            flagged_by_pos[key] = flagged_by_pos.get(key, 0) + 1

    total_sites = sum(total_by_pos.values()) or 1
    baseline = sum(flagged_by_pos.values()) / total_sites

    systematic = []
    for pos, n_total in total_by_pos.items():
        n_flagged = flagged_by_pos.get(pos, 0)
        if n_total < min_support or n_flagged == 0:
            continue
        rate = n_flagged / n_total
        if rate > baseline * systematic_multiplier:
            systematic.append((pos, rate, n_flagged, n_total))

    sys_pos = {p for p, _, _, _ in systematic}
    snps = tuple(f for f in all_flags if (f.pos or "?") not in sys_pos)

    poses = list(total_by_pos)
    concentration = _spearman(
        [float(total_by_pos[p]) for p in poses],
        [float(flagged_by_pos.get(p, 0)) for p in poses],
    )
    return TriageResult(tuple(systematic), snps, concentration)
