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
    "Event": ("agent", "patient"),
    "Comparison": ("lhs", "rhs"),
    "Equality": ("lhs", "rhs"),
    "TypeAssertion": ("entity", "kind"),
    "TypeQuery": ("entity",),
    "DegreeQuery": ("entity",),
    "MinimalSufficiency": ("threshold", "purpose"),
    "SetRestriction": ("member", "predicate"),
    "BoundaryCase": ("entity", "predicate"),
    "Contrast": ("left", "right"),
    "ClauseCoordination": ("left", "right"),
    "Causation": ("cause", "effect"),
    "Conditional": ("antecedent", "consequent"),
    "RelativeRestriction": ("head", "restriction"),
    "Control": ("subject", "controller", "inner"),
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
    # A demi-word ("Lady Macbeth") is keyed by its whole span, so it stays a
    # distinct referent from a bare head token ("Macbeth").
    key = tuple(entity.span) if getattr(entity, "span", ()) else (entity.head.lemma,)
    return (key, poss)


def _position(entity: Entity) -> int:
    return getattr(entity.head, "position", 0)


def _lookup_key(entity: Entity) -> str:
    """The genealogy key for an entity — its whole demi-word span ("ice cream",
    "lady macbeth") when it has one, else the head lemma. The store's
    ``candidates`` already accepts multi-token keys (WordNet MWEs + sparse-wiki
    labels), so a matched span grounds confidently to its own entry."""
    span = getattr(entity, "span", ())
    return " ".join(span) if span else entity.head.lemma


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
                _lookup_key(ent), getattr(ent.head, "pos", "") or "", _is_proper(ent)
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


def _promote_demiwords(node: Any, genealogy: Any) -> Any:
    """Promote a modifier+head slot to a demi-word when the joined span is a
    lexicalized dictionary entry.

    The structure reads "hot dog" as ADJ-modifier + NOUN ("a warm dog"), peeling
    "hot" off. But "hot dog" is a *lexicalized* WordNet entry and "red car" is
    not — so WordNet's own lexicalization is the commonness gate (your gradation,
    pre-decided by lexicographers). When the compound is a dictionary key, promote
    it to a single demi-word span (clearing the now-absorbed modifier); the
    existing coherence selector then picks among the MWE's senses. "red car" / "big
    dog" stay compositional. Only runs when a real dictionary is present.
    """
    def promote(ent: Entity) -> Entity:
        if ent.span:                                  # already a demi-word
            return ent
        mod = getattr(ent, "modifier", None)
        if mod is None or getattr(mod, "pos", None) != "ADJ":
            return ent
        # A comparative/superlative adjective is gradable-descriptive, never part of a
        # fixed lexicalized compound: "the fattest hen" is a superlative chicken, NOT the
        # plant "fat hen". Keep it compositional (head stays the bird).
        if getattr(mod, "graded", False):
            return ent
        compound = f"{mod.lemma} {ent.head.lemma}"
        pos = getattr(ent.head, "pos", "") or ""
        if genealogy.candidates(compound, pos, _is_proper(ent)):
            return replace(ent, span=(mod.lemma, ent.head.lemma), modifier=None)
        return ent

    return _map_entities(node, promote)


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

    # Promote lexicalized ADJ+NOUN compounds to demi-words before id minting, so
    # "hot dog" gets one identity (not head "dog" + modifier "hot").
    if hasattr(genealogy, "candidates"):
        node = _promote_demiwords(node, genealogy)

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
                        _lookup_key(ent), getattr(ent.head, "pos", "") or "", _is_proper(ent)
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


# Pronoun grammatical number / person, for cross-sentence agreement. they/them are
# number=plur, person-agnostic (a group of people OR things); it/its are non-person.
_PRON_NUMBER = {
    "they": "plur", "them": "plur", "their": "plur", "theirs": "plur", "themselves": "plur",
    "he": "sing", "she": "sing", "it": "sing", "him": "sing", "her": "sing",
    "his": "sing", "hers": "sing", "its": "sing",
    "himself": "sing", "herself": "sing", "itself": "sing",
}
_PRON_PERSON = {  # True = requires a person antecedent; False = requires non-person
    "he": True, "she": True, "him": True, "her": True, "his": True, "hers": True,
    "himself": True, "herself": True, "it": False, "its": False, "itself": False,
}
# First/second-person (DEICTIC) pronoun lemmas — the speaker, the addressee, or the
# narrator; never anaphoric to a prior third-person noun. They are excluded from recency
# binding because binding them by recency corrupts dialogue and first-person narration
# ("I ran" rebound to the last-named entity → "jim ran"). Resolving quoted "I" → speaker /
# "you" → addressee is a separate parse-time concern (dialogue-deixis), not recency coref.
# "narrator" is the same deictic class: the speech pass re-lemmatizes a narration "I"/"we"
# to this tag (speech.NARRATOR_TAG) BEFORE document binding, so without it here the binder
# would no longer recognize the narrator as first-person and would rebind it to a recency
# antecedent — clobbering the narrating voice across the document (the first-person
# protagonist would dissolve into the last-named third person).
_DEICTIC_PERSON = frozenset({
    "i", "me", "my", "mine", "myself",
    "we", "us", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "narrator",   # the re-lemmatized narration first-person (speech.NARRATOR_TAG)
})
# INDEFINITE / universal pronouns are quantifiers, not anaphors — "Alonso forgives everyone"
# does NOT corefer "everyone" with a prior named entity (binding it to the most-recent noun is
# exactly the duke-capture bug). Like the deictics, they are left UNBOUND (kept as their own
# indefinite referent) rather than rebound by recency.
_INDEFINITE_PRONOUN = frozenset({
    "everyone", "everybody", "everything",
    "someone", "somebody", "something",
    "anyone", "anybody", "anything",
    "no one", "nobody", "nothing", "none",
})
_PERSON_CACHE: Dict[str, Any] = {}


def _is_person(lemma: str) -> Any:
    """True/False if ``lemma`` is/ isn't a person (WordNet hypernymy); None if unknown."""
    if lemma in _PERSON_CACHE:
        return _PERSON_CACHE[lemma]
    res: Any = None
    try:
        from nltk.corpus import wordnet as wn
        person = wn.synset("person.n.01")
        syns = wn.synsets(lemma, pos="n")
        if syns:
            res = any(person in path for s in syns for path in s.hypernym_paths())
    except Exception:
        res = None
    _PERSON_CACHE[lemma] = res
    return res


# Pronoun GENDER + a small gendered-noun lexicon. The "royal title → gender" signal: the world
# strand (sparse-wiki) has the entities but no gender field, so the cheap dependency-free source is
# the title/role WORD itself. The lexicon covers the titles WordNet hypernymy misses (king/queen/
# lord carry gender in the gloss, not the tree); WordNet (male.n.02 / female.n.02) is the fallback.
_PRON_GENDER = {
    "he": "m", "him": "m", "his": "m", "himself": "m",
    "she": "f", "her": "f", "hers": "f", "herself": "f",
}
_GENDERED_NOUNS = {
    "king": "m", "lord": "m", "prince": "m", "duke": "m", "emperor": "m", "sir": "m", "mister": "m",
    "father": "m", "husband": "m", "son": "m", "brother": "m", "uncle": "m", "nephew": "m",
    "grandfather": "m", "boy": "m", "gentleman": "m", "knight": "m", "monk": "m", "priest": "m",
    "master": "m", "widower": "m", "groom": "m", "bachelor": "m",
    "queen": "f", "lady": "f", "princess": "f", "duchess": "f", "empress": "f", "madam": "f",
    "mother": "f", "wife": "f", "daughter": "f", "sister": "f", "aunt": "f", "niece": "f",
    "grandmother": "f", "girl": "f", "gentlewoman": "f", "nun": "f", "mistress": "f",
    "maid": "f", "widow": "f", "bride": "f", "witch": "f",
}
_GENDER_CACHE: Dict[str, Any] = {}


def _word_gender(lemma: str) -> Any:
    """'m'/'f' if the noun is gendered, else None. Lexicon first (the royal titles WordNet's
    hypernymy misses), then WordNet hypernymy (male.n.02 / female.n.02)."""
    if not lemma:
        return None
    key = lemma.lower()
    if key in _GENDER_CACHE:
        return _GENDER_CACHE[key]
    res: Any = _GENDERED_NOUNS.get(key)
    if res is None:
        try:
            from nltk.corpus import wordnet as wn
            male, female = wn.synset("male.n.02"), wn.synset("female.n.02")
            m = f = False
            for s in wn.synsets(key, pos="n"):
                for path in s.hypernym_paths():
                    if male in path:
                        m = True
                    if female in path:
                        f = True
            res = "m" if (m and not f) else "f" if (f and not m) else None
        except Exception:
            res = None
    _GENDER_CACHE[key] = res
    return res


def _entity_gender(ante: Entity) -> Any:
    """Gender of a candidate antecedent — from any gendered word it carries: the head lemma, its
    span tokens (so 'Lady Macbeth' → female via the 'lady' in the span), or its modifier."""
    words = []
    h = getattr(ante, "head", None)
    if h is not None and getattr(h, "lemma", None):
        words.append(h.lemma)
    words.extend(getattr(ante, "span", ()) or ())
    m = getattr(ante, "modifier", None)
    if m is not None and getattr(m, "lemma", None):
        words.append(m.lemma)
    for w in words:
        g = _word_gender(w)
        if g:
            return g
    return None


def _pron_agrees(pron_lemma: str, ante: Entity) -> bool:
    """Number + person + GENDER agreement between a pronoun and a candidate antecedent. A check
    is skipped when either side's feature is unknown (permissive — never rules out on a gap)."""
    pn = _PRON_NUMBER.get(pron_lemma)
    an = getattr(ante.head, "number", None)
    if pn and an and pn != an:
        return False
    pp = _PRON_PERSON.get(pron_lemma)
    if pp is not None:
        ap = _is_person(getattr(ante.head, "lemma", "") or "")
        if ap is not None and ap != pp:
            return False
    pg = _PRON_GENDER.get(pron_lemma)
    if pg is not None:
        ag = _entity_gender(ante)
        if ag is not None and ag != pg:
            return False
    return True


def _bind_document_pronouns(trees: Sequence[Any]) -> List[Any]:
    """Bind cross-sentence pronouns to the most-recent AGREEING prior entity.

    Strictly improves the v1 most-recent rule with two refinements (the cross-sentence
    twin of the within-sentence binder's agreement):
      * **agreement** — prefer the most-recent antecedent that matches the pronoun's
        number ("they" → a plural noun like ``nobles``) and person ("it" → non-person);
      * **distinctness** — two pronouns in one sentence take different antecedents
        ("They harmed him" → they=nobles, him=tyrant, not both the same).
    Falls back to plain most-recent when no antecedent agrees (so it is never worse than
    v1), and leaves a pronoun unbound only when there is no available antecedent at all.
    """
    antecedents: List[Entity] = []
    out: List[Any] = []
    for tree in trees:
        used: set = set()   # antecedent lemmas already taken by a sibling pronoun (distinct)

        def bind(ent: Entity) -> Entity:
            if not _is_pronoun(ent):
                return ent
            pron = getattr(ent.head, "lemma", "") or ""
            # First/second-person pronouns are deictic, not anaphoric: leave them unbound
            # rather than grabbing the most-recent third-person noun (which corrupts
            # first-person narration). Speaker/addressee attribution is handled upstream.
            if pron in _DEICTIC_PERSON or pron in _INDEFINITE_PRONOUN:
                return ent
            cands = [a for a in reversed(antecedents)
                     if (getattr(a.head, "lemma", None) not in used)]
            if not cands:
                return ent
            # Prefer a candidate whose gender is KNOWN and matches the pronoun (so "she" picks the
            # titled/role female over a more-recent gender-unknown name), then most-recent agreeing.
            pg = _PRON_GENDER.get(pron)
            # CENTERING — topic salience over recency+gender-known. The discourse TOPIC (the entity
            # that recurs far above the rest) holds a pronoun that AGREES with it, instead of yielding
            # to a just-named incidental of matching gender. This is what keeps a long-running
            # protagonist ("Alonso … him / his") on Alonso rather than the duke named one clause
            # earlier (whose KNOWN gender would otherwise outrank gender-unknown Alonso). A topic must
            # clearly persist (>= 3 mentions and >= 2x the runner-up); with no dominant topic this is
            # skipped and the gender-known → recency logic below is unchanged (so "she" still prefers a
            # titled female over a more-recent gender-unknown name).
            topic = None
            counts: Dict[Any, int] = {}
            for a in antecedents:
                lm = getattr(a.head, "lemma", None)
                counts[lm] = counts.get(lm, 0) + 1
            if counts:
                ranked = sorted(counts.values(), reverse=True)
                top_n = ranked[0]
                runner = ranked[1] if len(ranked) > 1 else 0
                top_lemma = max(counts, key=lambda k: counts[k])
                if top_lemma is not None and top_n >= 3 and top_n >= 2 * runner:
                    topic = next(
                        (a for a in cands
                         if getattr(a.head, "lemma", None) == top_lemma
                         and _pron_agrees(pron, a)
                         and (pg is None or _entity_gender(a) in (pg, None))),
                        None,
                    )
            pick = topic
            if pick is None and pg is not None:
                pick = next((a for a in cands if _entity_gender(a) == pg), None)
            if pick is None:
                pick = next((a for a in cands if _pron_agrees(pron, a)), cands[0])
            used.add(getattr(pick.head, "lemma", None))
            return replace(ent, head=pick.head, possessor=pick.possessor)

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
    if hasattr(genealogy, "candidates"):
        trees = [_promote_demiwords(t, genealogy) for t in trees]

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
                        _lookup_key(ent), getattr(ent.head, "pos", "") or "", _is_proper(ent)
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
        # A proper noun is grounded only by a *world* thread (its identity); its
        # lexicon decomposition is a common-noun homograph, not who it is. A
        # common noun is grounded by either the lexicon or a word thread.
        if getattr(ent.head, "pos", None) == "PROPN":
            grounded = bool(ent.type_thread)
        else:
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
