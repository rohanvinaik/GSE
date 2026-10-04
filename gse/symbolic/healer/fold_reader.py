"""LAYER 2 — the fold-reader: multi-strand SEMANTIC ISOLATION over the whole resolved document.

A document-scale phase-0 pre-pass at the heal seam. Where the per-statement lenses (Layer 1) repair
PRIMARY/SECONDARY structure, this resolves the TERTIARY/QUATERNARY fold: each entity's role, type,
significance, and affect — by COMBINING four independent strands, never one. (See
``~/Genesis/docs/SPINE_SOCIETY_DESIGN.md`` §4/§6 and the Law-as-Architecture coherent-replicate move.)

The replicate field is the COREF CLUSTER: ``resolve_document`` threads every mention of one referent
under a stable ``entity_id``. A statement whose local signal is silent — a name with empty NSM banks
in *this* clause (della) — has its role recovered from her OTHER mentions: **shape from the field,
level from the self.** No single strand is the oracle:

  word     — NSM banks (``classify`` over ``word_primitives``)   clean for content words; empty for names/pronouns
  world    — sparse-wiki type-genealogy (optional, needs store)  clean for named referents; empty for fictional
  document — recurrence × timeline-span across the coref cluster  clean for protagonists (della); empty for one-shots
  local    — the coref binding itself (the entity_id grouping)    clean when the antecedent threads

Computed at the REPAIR SEAM (before ``_finalize``), so recurrence comes from the wide ``timed``
predicate set directly (count agent-participation per ``entity_id``), the same shape ``_backbone``
uses downstream. ALL SYMBOLIC: deterministic strand lookups + a set-theoretic vote. No gradient descent.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from gse.symbolic.predicates import Event

from .treewalk import walk

# Personal pronouns are animate referents the word strand mis-reads as object (he/horse→object); the
# LOCAL/lexical strand carries them. (Mirrors treewalk._ANIMATE_PRON.)
_ANIMATE_PRON = frozenset({"i", "we", "you", "he", "she", "they", "me", "us", "him", "her", "them"})


@dataclass
class EntityFold:
    """The resolved fold of one referent — the multi-strand semantic isolation of an entity_id."""

    eid: str
    lemma: str = ""
    pos: Optional[str] = None
    role: str = "?"  # voted role: agent / experiencer / object / '?'
    significance: int = 0  # agent-participation × timeline-span (the tertiary fold)
    agent_count: int = 0
    tspan: int = 1
    recurs: bool = False  # a recurring agent (document strand) — the protagonist signal
    eligible: bool = False  # real referent: grounds at SOME scale (multi-strand OR)
    type_thread: Tuple[str, ...] = ()  # world strand (sparse-wiki) genealogy, if grounded
    valence: int = 0  # affect substrate: EVALUATORS GOOD(+)/BAD(−) from the word strand;
    # for a named referent (empty NSM banks) the world EPA evaluation
    potency: int = 0  # world-salience EPA P — the intensity/gravity leg (word ⟂ world)
    activity: int = 0  # world-salience EPA A
    strands: Tuple[str, ...] = ()  # which strands voted the entity REAL (provenance/audit)


# World types that CANNOT be story agents (mirrors narrative.py's world-leg gate):
# a war or a creative work is not a protagonist, however often it recurs.
_NONAGENT_WORLD = frozenset({"Event", "SocietalEvent", "MilitaryConflict", "Work"})
# World types that are not ANIMATE by default: a Place loses the bare PROPN→animate
# vote, but the DOCUMENT strand can still make it an agent (a recurring "France"
# acting across the story is a collective agent) — only the default is removed,
# never a positive signal.
_PLACE_WORLD = frozenset({"Place", "PopulatedPlace", "Location"})


def _operands(pred):
    """The (role_slot, operand) pairs of every Event under a predicate — the agent/patient fillers."""
    for n in walk(pred):
        if isinstance(n, Event):
            if getattr(n, "agent", None) is not None:
                yield "agent", n.agent
            if getattr(n, "patient", None) is not None:
                yield "patient", n.patient


def _eid(operand) -> Optional[str]:
    return getattr(operand, "entity_id", None)


def _head(operand):
    return getattr(operand, "head", None) or operand


def read_fold(
    timed: List[tuple], envelopes: Optional[List[Any]] = None, genealogy: Any = None
) -> Dict[str, EntityFold]:
    """Build the per-entity fold map from the WIDE statement set. ``genealogy`` (the GenealogyStore)
    is OPTIONAL — when absent the world strand is simply not consulted (graceful degradation; the
    other three strands still resolve). Returns ``{entity_id: EntityFold}``."""
    from gse.symbolic.narrative import classify  # lazy: avoid import cycle

    agent_t: Dict[str, Set[int]] = defaultdict(set)  # entity_id → timesteps it is an Event AGENT
    part_t: Dict[str, Set[int]] = defaultdict(set)  # entity_id → timesteps it participates at all
    info: Dict[str, Tuple[str, Optional[str], Dict[str, int]]] = {}  # eid → (lemma, pos, prims)

    for t, pred in timed:
        for slot, op in _operands(pred):
            eid = _eid(op)
            if eid is None:
                continue
            head = _head(op)
            if eid not in info:
                info[eid] = (
                    (getattr(head, "lemma", "") or "").lower(),
                    getattr(head, "pos", None),
                    getattr(head, "word_primitives", None) or {},
                )
            part_t[eid].add(t)
            if slot == "agent":
                agent_t[eid].add(t)

    folds: Dict[str, EntityFold] = {}
    for eid, (lemma, pos, prims) in info.items():
        # --- document strand: recurrence × span (the tertiary fold) ---
        agent_count = len(agent_t.get(eid, ()))
        ts = part_t.get(eid, set())
        tspan = (max(ts) - min(ts) + 1) if ts else 1
        significance = agent_count * tspan
        recurs = agent_count >= 2
        # --- word strand: NSM role + eligibility from the decomposition ---
        wrole, welig, banks = classify(prims, ()) if prims else ("?", False, set())
        # --- world strand: sparse-wiki genealogy for a named referent (optional) ---
        type_thread: Tuple[str, ...] = ()
        if pos == "PROPN" and lemma and genealogy is not None and hasattr(genealogy, "candidates"):
            try:
                cands = genealogy.candidates(lemma, "PROPN", True)
                if cands:
                    type_thread = tuple(cands[0])
            except Exception:
                type_thread = ()
        grounded_world = bool(type_thread)
        tset = set(type_thread)
        # --- world-leg role gates (the thread's CONTENT, not just its truthiness;
        #     mirrors narrative.py's world-leg agent gate) ---
        nonagent_world = bool(tset & _NONAGENT_WORLD)  # a war/work is never a protagonist
        place_world = bool(tset & _PLACE_WORLD)  # a place is not animate BY DEFAULT
        # --- local/lexical strand: a threaded pronoun / proper name is an animate referent —
        #     UNLESS the world strand positively types it a place/event (Bosnia is not an
        #     animate agent for being spelled with a capital letter). Shallow/absent world
        #     grounding leaves the default intact (a fictional name stays animate). ---
        lexical_animate = (pos == "PROPN" and not (place_world or nonagent_world)) or (
            pos == "PRON" and lemma in _ANIMATE_PRON
        )

        # --- the multi-strand VOTE (set-theoretic; real if it grounds at ANY scale) ---
        voted: List[str] = []
        if welig:
            voted.append("word")
        if grounded_world:
            voted.append("world")
        if recurs:
            voted.append("document")
        if lexical_animate:
            voted.append("local")
        eligible = bool(voted)
        # role: the document strand (recurring agent) and the local strand (animate name/pron) are
        # authoritative for AGENT exactly where the word strand is blind (names/pronouns); else the
        # word-strand role stands. Never let the noisy word 'object' override an animate name.
        # A world-typed NON-AGENT (Event/Work) is excluded from the agent path outright — however
        # often it recurs (narrative.py's discipline); a world-typed PLACE can still earn agent-hood
        # through document-strand recurrence (a nation acting), just not by default.
        if nonagent_world:
            role = wrole if wrole not in ("?", "agent") else "object"
        elif recurs or lexical_animate or wrole in ("agent", "experiencer"):
            role = "agent" if (recurs or lexical_animate or wrole == "agent") else "experiencer"
        else:
            role = wrole
        # affect substrate: EVALUATORS valence from the word strand; a NAMED referent
        # (empty NSM banks) takes the world-salience EPA instead — the word-affect ⟂
        # world-salience split (GSE_vision §IV½), each strand supplying what the other
        # cannot. Potency/activity are world-only (intensity is a world quantity).
        valence = int(prims.get("GOOD", 0)) - int(prims.get("BAD", 0)) if prims else 0
        potency = activity = 0
        if grounded_world and genealogy is not None and hasattr(genealogy, "epa"):
            try:
                epa = genealogy.epa(lemma) or {}
            except Exception:
                epa = {}
            if epa:
                if not prims:
                    valence = int(epa.get("evaluation", 0))
                potency = int(epa.get("potency", 0))
                activity = int(epa.get("activity", 0))

        folds[eid] = EntityFold(
            eid=eid,
            lemma=lemma,
            pos=pos,
            role=role,
            significance=significance,
            agent_count=agent_count,
            tspan=tspan,
            recurs=recurs,
            eligible=eligible,
            type_thread=type_thread,
            valence=valence,
            potency=potency,
            activity=activity,
            strands=tuple(voted),
        )
    return folds


def best_subject(operands, folds: Dict[str, EntityFold], min_significance: int = 2):
    """Pick the most plausible subject among candidate operands — 'shape from the field': prefer the
    highest-significance RECURRING agent (the protagonist over a one-shot nearby noun). The
    disambiguator that un-buckets the L3/L7 subject-attachment wall.

    CONFIDENCE GATE (clean-or-hole): anchor ONLY on a recurring agent (or a clearly-significant one) —
    if the best local candidate is a one-shot nearby noun (flight/change/hedge), return None so the
    lens ABSTAINS rather than fire wrong. We do NOT fall back to the global protagonist: binding a
    stray participle to the discourse topic is exactly the move that manufactures false spine
    (compaction paper §4.1). Returns the operand or None."""
    best, best_sig = None, -1
    for op in operands:
        fold = folds.get(_eid(op))
        if fold is None or not fold.eligible:
            continue
        if not (fold.recurs or fold.significance >= min_significance):
            continue  # one-shot nearby noun → not a confident anchor
        if fold.significance > best_sig:
            best, best_sig = op, fold.significance
    return best
