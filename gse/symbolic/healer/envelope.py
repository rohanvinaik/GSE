"""The statement healer's metadata ENVELOPE — the per-statement *tertiary-structure* annotation.

Off-site context bundled to travel WITH a statement so a post-collapse repair specialist (a lens at
the ``narrative.from_document(repair=)`` seam) is premise-COMPLETE without re-reading the parse.
Biology homology (``docs/SPINE_SOCIETY_DESIGN.md``): an epigenetic / cis-regulatory mark, laid down
at the regulatory event — PARSE/INTAKE time, the one place the full ``OperationTrace`` still exists —
and PROPAGATED to the trace-less repair seam. The lens binds on the mark, not the linear sequence.

DESIGNED WHOLE (the broad pass): the tag set anticipates the needs of ALL eight Tier-2 laws up front
(each tag traces to a signed-off law signature — see the roster), so a per-law carve is a REFINEMENT
(its claim/repair logic) rather than re-extending the envelope each time. Tags, and who needs them:

  per-statement
    has_copula    linking-be present                          → L1 copula_predicate
    has_coord     and/or/nor/but present                       → L2 matrix_collapse, L7 vp_coord
    subordinators that/what/how/who/which/when… present        → L5 embedded_clause
    speech_verbs  GSE _SAY_VERBS present                       → L6 attribution_say
    deictics      GSE _DEICTIC_PERSON present (I/you/narrator)  → L8 deictic_bind
  per-token (position-keyed; an Atom node carries .position)
    surface       token surface form                           → L7 (morphology), L3 participial
    pos           trace POS tag                                 → L2, L3, L4
    senses        WordNet {v,a,n}  (v3: now FALLBACK)           → L1, general POS-ambiguity
    inflected     unambiguous verb inflection (is_verb_inflected) → L7 vp_coord, L2 matrix_collapse
    prev          (prev_lemma, prev_pos)                        → L3 (comma adjunct), L4 (to-infinitive)
    prev_func     preceding token is det/prep (gerund-noun)     → L7, L1
  per-token SEMANTIC layer (v3 — GSE's NATIVE NSM banks, the register-INVARIANT signal, carried from the
  TokenTrace's `word_primitives` at PARSE TIME, where prims are solid — NOT the noisy resolved-entity seam
  where `classify` mis-reads he/horse→object and 35% of agents have empty prims. A law reads the role by the
  operand's `.position`, not by re-running classify on the degraded seam entity. WordNet `senses` → fallback.)
    prims         raw word_primitives (NSM bank activations)    → experiencer_typing, affect_stance
    banks         active NSM banks (frozenset)                  → the semantic family (bank profile = evidence)
    role          classify role∈{agent,experiencer,object,evaluation,?} (thread-free) → role_coherence
    eligible      classify eligibility (entity bank present, parse-time) → eligibility_defer
  word-level
    lex           word(surface|lemma) → {v,a,n, pos-tags}       → L1 (premise-complete from a verb STRING)

The envelope holds NO repair logic and makes NO firing decision; it is pure annotation. Built once at
intake; carried forward verbatim. Laws not yet carved read tags DESIGNED from their signature — each
per-law carve still VALIDATES its tag against that law's real near-misses (validate-on-real-input).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Tuple

from nltk.corpus import wordnet as wn

# Determiner/preposition before an -ing token = gerund-noun signal (not a progressive verb).
DET_PREP = frozenset({"the", "a", "an", "any", "some", "no", "this", "that",
                      "of", "by", "with", "for", "in", "without", "from"})
# Coordinators (L2/L7) and embedded-clause subordinators/complementizers (L5).
COORD = frozenset({"and", "or", "nor", "but"})
SUBORDINATORS = frozenset({"that", "what", "which", "who", "whom", "whose",
                           "how", "when", "where", "why", "whether", "if"})


# ---- WordNet sense facts (dictionary lookups, NOT word lists) -----------------------------------
def _has_verb_sense(word: str) -> bool:
    return bool(wn.synsets(word, pos="v"))


def _has_adj_sense(word: str) -> bool:
    return bool(wn.synsets(word, pos="a")) or bool(wn.synsets(word, pos="s"))


def _has_noun_sense(word: str) -> bool:
    return bool(wn.synsets(word, pos="n"))


def is_verb_inflected(surface: str, lemma: str) -> bool:
    """Unambiguous verb inflection: -ed/-en/-ing or an irregular past (surface≠lemma, not -s).
    The morphology gate L7/L2 use to fire only on a real finite/participial verb — excludes -s
    plural-noun homographs (signs/locks) and bare-ambiguous forms."""
    s = (surface or "").lower()
    if s.endswith(("ing", "ed", "en")):
        return True
    if s != (lemma or "").lower() and not s.endswith("s"):
        return True
    return False


@dataclass
class StatementMeta:
    """The envelope — off-site context per statement (see module docstring for the tag map)."""
    genre: Optional[str]
    super_register: Optional[str]
    # per-position views (Atom nodes carry .position)
    senses: Dict[int, Dict[str, bool]] = field(default_factory=dict)
    prev_func: Dict[int, bool] = field(default_factory=dict)
    surface: Dict[int, str] = field(default_factory=dict)
    lemma: Dict[int, str] = field(default_factory=dict)
    pos: Dict[int, str] = field(default_factory=dict)
    inflected: Dict[int, bool] = field(default_factory=dict)
    prev: Dict[int, Tuple[str, str]] = field(default_factory=dict)
    next: Dict[int, Tuple[str, str]] = field(default_factory=dict)
    # per-token SEMANTIC layer (v3 — GSE NSM banks from word_primitives, laid at parse time)
    prims: Dict[int, Dict[str, int]] = field(default_factory=dict)
    banks: Dict[int, FrozenSet[str]] = field(default_factory=dict)
    role: Dict[int, str] = field(default_factory=dict)
    eligible: Dict[int, bool] = field(default_factory=dict)
    # word-level (for a node that carries only a bare string, e.g. Event.verb)
    lex: Dict[str, Dict[str, object]] = field(default_factory=dict)
    # per-statement flags (the regime + the law triggers)
    has_copula: bool = False
    has_coord: bool = False
    subordinators: FrozenSet[str] = frozenset()
    speech_verbs: FrozenSet[str] = frozenset()
    deictics: FrozenSet[str] = frozenset()

    def is_predicate_adjective(self, word: str) -> bool:
        """L1: was ``word`` an ADJECTIVE in this sentence (ADJ-tagged, adj sense, NO verb reading)?
        Premise-complete from a bare verb string — no trace, no position. False for verb-capable
        homographs (``clean``) and parser noise WordNet doesn't back (``matt`` from ``matter``)."""
        e = self.lex.get((word or "").lower())
        if not e:
            return False
        p = e.get("pos") or frozenset()
        return bool(e.get("a")) and ("ADJ" in p) and ("VERB" not in p)

    def is_inflected_verb(self, position: int) -> bool:
        """L7/L2: did the token at ``position`` carry unambiguous verb inflection?"""
        return bool(self.inflected.get(position))

    def role_at(self, position: int) -> str:
        """v3: the PARSE-TIME NSM role of the token at ``position`` (GSE's ``classify`` over its
        ``word_primitives``, thread-free) — agent / experiencer / object / evaluation / '?'. The
        semantic family's first-class signal, read from the clean parse-time mark rather than by
        re-running ``classify`` on the degraded resolved entity at the seam. '?' when the token had
        no primitives (the honest absence — a law abstains on it, per clean-or-hole)."""
        return self.role.get(position, "?")

    def banks_at(self, position: int) -> FrozenSet[str]:
        """v3: the active NSM banks of the token at ``position`` (the bank profile IS the evidence
        for experiencer_typing / affect_stance / role_coherence)."""
        return self.banks.get(position, frozenset())

    def is_eligible(self, position: int) -> bool:
        """v3: parse-time eligibility (the token fires an entity/SUBSTANTIVES bank) — eligibility_defer's
        signal. Parse-time only (no thread); grounding/sparse-wiki is layered later in ``_finalize``."""
        return bool(self.eligible.get(position, False))

    def participial_adjuncts(self):
        """L3: the comma-bounded / fronted present-participle (-ing) VERB tokens — secondary-predicate
        participles (`, throwing stones` / `, staggering,` / fronted `Trying doors,`). Returns
        ``[(position, lemma)]``. The caller still gates out -ing adjectives/gerund-nouns (senses)."""
        if not self.surface:
            return []
        first = min(self.surface)
        out = []
        for pos, surf in self.surface.items():
            if self.pos.get(pos) != "VERB" or not (surf or "").lower().endswith("ing"):
                continue
            prev_comma = self.prev.get(pos, ("", ""))[0] == ","
            next_comma = self.next.get(pos, ("", ""))[0] == ","
            if prev_comma or next_comma or pos == first:
                out.append((pos, self.lemma.get(pos, (surf or "").lower())))
        return out

    def infinitival_complements(self):
        """L4: present-infinitival VERB tokens — a ``to <verb>`` control/purpose complement
        (`to start`, `to make my fortune`). Returns ``[(position, lemma)]``. The caller gates out
        already-emitted verbs / noun-homographs and binds the controller (the matrix subject)."""
        out = []
        for pos, surf in self.surface.items():
            if self.pos.get(pos) != "VERB":
                continue
            if self.prev.get(pos, ("", ""))[0] == "to":
                out.append((pos, self.lemma.get(pos, (surf or "").lower())))
        return out


def build_envelope(trace, genre: Optional[str] = None) -> StatementMeta:
    """Lay down the full envelope for one utterance from its ``OperationTrace`` (parse-time).

    Pure annotation: reads only the token stream. ``genre`` from the recognizer when available
    (else None). Reuses GSE's own ``_SAY_VERBS`` / ``_DEICTIC_PERSON`` sets (lazy import — the
    discourse/grounding modules import gse.symbolic, so importing them here at top level would cycle).
    """
    super_reg: Optional[str] = genre
    say_verbs: FrozenSet[str] = frozenset()
    deictic_set: FrozenSet[str] = frozenset()
    try:
        if genre is not None:
            from gse.discourse import super_register_of
            super_reg = super_register_of(genre)
    except Exception:
        super_reg = genre
    try:
        from gse.discourse.speech import _SAY_VERBS
        say_verbs = _SAY_VERBS
    except Exception:
        pass
    try:
        from gse.symbolic.grounding import _DEICTIC_PERSON
        deictic_set = _DEICTIC_PERSON
    except Exception:
        pass
    try:                                          # v3 semantic layer: GSE's OWN native role fn
        from gse.symbolic.narrative import classify as _classify
    except Exception:
        _classify = None

    senses: Dict[int, Dict[str, bool]] = {}
    prev_func: Dict[int, bool] = {}
    surface: Dict[int, str] = {}
    lemma_map: Dict[int, str] = {}
    pos_map: Dict[int, str] = {}
    inflected: Dict[int, bool] = {}
    prev: Dict[int, Tuple[str, str]] = {}
    nxt: Dict[int, Tuple[str, str]] = {}
    prims_map: Dict[int, Dict[str, int]] = {}
    banks_map: Dict[int, FrozenSet[str]] = {}
    role_map: Dict[int, str] = {}
    elig_map: Dict[int, bool] = {}
    lex: Dict[str, Dict[str, object]] = {}
    has_copula = has_coord = False
    subs, speech, deic = set(), set(), set()

    toks = trace.tokens
    for i, t in enumerate(toks):
        surf = (t.token or "").lower()
        lem = (t.lemma or "").lower()
        p = t.position
        senses[p] = {"v": _has_verb_sense(lem) or _has_verb_sense(surf),
                     "a": _has_adj_sense(surf) or _has_adj_sense(lem),
                     "n": _has_noun_sense(surf) or _has_noun_sense(lem)}
        surface[p] = t.token
        lemma_map[p] = lem
        pos_map[p] = t.pos
        inflected[p] = is_verb_inflected(t.token, t.lemma)
        prev_lemma = (toks[i - 1].lemma or "").lower() if i > 0 else ""
        prev_pos = toks[i - 1].pos if i > 0 else ""
        prev[p] = (prev_lemma, prev_pos)
        nxt[p] = (((toks[i + 1].lemma or "").lower(), toks[i + 1].pos) if i + 1 < len(toks) else ("", ""))
        prev_func[p] = prev_lemma in DET_PREP
        # v3 semantic layer — the parse-time NSM decomposition (thread-free; grounding is layered in _finalize)
        wp = getattr(t, "word_primitives", None) or {}
        prims_map[p] = wp
        if _classify is not None and wp:
            r, el, bk = _classify(wp, ())
            role_map[p] = r
            elig_map[p] = bool(el)
            banks_map[p] = frozenset(bk) if bk else frozenset()
        # per-statement flags
        if lem == "be":
            has_copula = True
        if lem in COORD:
            has_coord = True
        if lem in SUBORDINATORS:
            subs.add(lem)
        if surf in say_verbs or lem in say_verbs:
            speech.add(lem)
        if lem in deictic_set:
            deic.add(lem)
        # word-keyed view
        for key in {surf, lem}:
            if not key:
                continue
            e = lex.get(key)
            if e is None:
                e = {"v": _has_verb_sense(key), "a": _has_adj_sense(key),
                     "n": _has_noun_sense(key), "pos": set()}
                lex[key] = e
            e["pos"].add(t.pos)  # type: ignore[union-attr]
    for e in lex.values():
        e["pos"] = frozenset(e["pos"])  # type: ignore[arg-type]

    return StatementMeta(
        genre=genre, super_register=super_reg,
        senses=senses, prev_func=prev_func, surface=surface, lemma=lemma_map, pos=pos_map,
        inflected=inflected, prev=prev, next=nxt, lex=lex,
        prims=prims_map, banks=banks_map, role=role_map, eligible=elig_map,
        has_copula=has_copula, has_coord=has_coord,
        subordinators=frozenset(subs), speech_verbs=frozenset(speech), deictics=frozenset(deic),
    )
