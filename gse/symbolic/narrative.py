"""
Narrative skeleton — document-level semantic compression over the clause graph.

Sibling of :mod:`gse.symbolic.inference` (which collects is-a + ordering edges and
does LSAT-style transitive reasoning). Where that answers logic queries, this builds
the **narrative spine**: from a document's globally-resolved clause trees
(:func:`gse.symbolic.grounding.resolve_document`) it collects

  * **entities** keyed on their global ``entity_id`` (one referent → one node),
  * each entity's **role-timeline** — its ordered ``be``/``become``/type facts
    (Macbeth: soldier → thane → king → deposed),
  * **event** edges (agent —verb→ patient), **causal** edges (``Causation``),
    and **temporal/precedence** edges (``Temporal``).

**Significance = participation.** A clause earns a place in the skeleton only if it
contributes an edge or a role between *resolved* entities. A degenerate triple
(``girl —is→ girl``) or a collapsed wide-coordination contributes no connective
edge, so it drops out *by construction* — the noise-vs-signal split is a property
of the graph, not an imposed score.

Stage A: build + inspect (this module). The public emit + bridge consumer come next.
This is GSE-native document analysis — it never imports Genesis.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# queries.predicates() is intentionally NOT used — the skeleton needs a more complete walk
# (see _collect_predicates below) that descends into coordination/conditional containers.

_STATE_VERBS = {"be", "become", "is", "are", "was", "were", "remain", "turn"}

# --- HDC role + eligibility: OTP informational-zero elimination over the NSM banks ----
# GSE already partitions the NSM primitives into 8 semantic banks (primitives_v2). An
# entity's word_primitives give a bank-activity profile; ROLE falls out of the signature
# (which banks fire) and ELIGIBILITY out of the informational ZEROS (which don't). A node
# that fires no SUBSTANTIVES (entity) bank and carries no resolved thread is, by the
# noise-floor, not a narrative citizen — eliminated with confidence, not by a stopword list.
try:
    from gse.primitives_v2 import PRIMITIVE_FAMILIES, SemanticBank
    _PRIME_BANK = {p: spec["bank"] for spec in PRIMITIVE_FAMILIES.values() for p in spec["primitives"]}
    _SUBSTANTIVES = SemanticBank.SUBSTANTIVES
except Exception:                       # degrade to thread-only eligibility if unavailable
    _PRIME_BANK, _SUBSTANTIVES = {}, None

_ANIMATE = {"I", "YOU", "SOMEONE", "PEOPLE", "BODY"}
_INANIMATE = {"SOMETHING", "KIND", "PART"}
_MENTAL = {"THINK", "KNOW", "INFER", "WANT", "FEEL", "SEE", "HEAR"}
_EVAL = {"GOOD", "BAD", "BIG", "SMALL"}


def _role_from_thread(thread: Tuple[str, ...]) -> str:
    t = set(thread)
    if {"person", "organism", "causal_agent"} & t:
        return "agent"
    if {"abstraction", "attribute", "feeling", "state", "psychological_feature"} & t:
        return "state"
    if "physical_entity" in t:
        return "object"
    return "?"


def classify(prims: Dict[str, int], thread: Tuple[str, ...]):
    """(role, eligible, active_banks) for an entity, from primitive profile + thread."""
    active = {p for p, v in (prims or {}).items() if v != 0}
    banks = {_PRIME_BANK[p] for p in active if p in _PRIME_BANK}
    has_entity = (_SUBSTANTIVES in banks) if _SUBSTANTIVES is not None else False
    grounded = bool(thread)
    eligible = has_entity or grounded
    if active & _ANIMATE:
        role = "agent"
    elif active & _MENTAL:
        role = "experiencer"
    elif active & _INANIMATE:
        role = "object"
    elif active & _EVAL:
        role = "evaluation"
    elif grounded:
        role = _role_from_thread(thread)
    else:
        role = "?"
    return role, eligible, banks


def _is_entity(node: Any) -> bool:
    return type(node).__name__ == "Entity"


def _eid(node: Any) -> Optional[str]:
    """The global entity id of an operand, or None if it isn't a resolved entity."""
    return getattr(node, "entity_id", None) if _is_entity(node) else None


def _label(node: Any, _depth: int = 0) -> str:
    """A compact, bounded surface rendering of any operand or sub-predicate."""
    name = type(node).__name__
    if _depth > 4:
        return name.lower()
    d = _depth + 1
    if name == "Entity":
        if getattr(node, "span", ()):
            return " ".join(node.span)
        return getattr(node.head, "lemma", "?")
    if name == "Atom":
        return node.lemma
    if name == "Phrase":
        return " ".join(a.lemma for a in node.atoms)
    if name == "Event":
        p = f"→{_label(node.patient, d)}" if node.patient is not None else ""
        return f"{node.verb}({_label(node.agent, d)}{p})"
    if name == "Causation":
        return f"[{_label(node.cause, d)} ⇒ {_label(node.effect, d)}]"
    if name == "Temporal":
        return f"[{_label(node.setting, d)} ; {_label(node.event, d)}]"
    if name == "TypeAssertion":
        return f"{_label(node.entity, d)}:{_label(node.kind, d)}"
    if name == "Coordination":
        conj = getattr(node, "conjunction", "and")
        return "(" + f" {conj} ".join(_label(m, d) for m in node.members) + ")"
    if name == "Control":
        return _label(node.inner, d) if getattr(node, "inner", None) is not None else (node.verb or "control")
    if name == "RelativeRestriction":
        return _label(node.head, d)
    if name in ("ClauseCoordination", "Contrast"):
        return f"{_label(node.left, d)} / {_label(node.right, d)}"
    if name == "Conditional":
        return f"[{_label(node.antecedent, d)} → {_label(node.consequent, d)}]"
    if name == "Negation":
        return f"¬{_label(node.operand, d)}"
    s = str(getattr(node, "lemma", name.lower()))
    return s if len(s) < 50 else name.lower()


@dataclass
class _Node:
    eid: str
    surface: Set[str] = field(default_factory=set)
    thread: Tuple[str, ...] = ()
    roles: List[Tuple[int, str]] = field(default_factory=list)   # (time, role/state)
    degree: int = 0                                              # edges touching this node
    prims: Dict[str, int] = field(default_factory=dict)         # bundled NSM primitive profile
    pos: str = ""                                               # grammatical POS of the head (NOUN/PROPN/…)
    lemma: str = ""                                             # head lemma (for the world-strand heal)
    role: str = "?"                                            # inferred semantic role
    eligible: bool = False                                      # admitted citizen vs eliminated noise
    provenance: List[str] = field(default_factory=list)         # heals applied (audit trail)


@dataclass
class Edge:
    t: int
    kind: str            # "event" | "cause" | "temporal"
    src: str             # entity id, or a rendered label for a non-entity endpoint
    rel: str             # verb / "causes" / "then"
    dst: str
    src_resolved: bool
    dst_resolved: bool
    provenance: List[str] = field(default_factory=list)         # heals applied (audit trail)


_YIELD_PREDS = {"Event", "Causation", "Temporal", "TypeAssertion", "Comparison",
                "Conditional", "Control", "RelativeRestriction", "Contrast", "ClauseCoordination"}
_CONTAINER_FIELDS = {
    "ClauseCoordination": ("left", "right"),
    "Contrast": ("left", "right"),
    "Causation": ("cause", "effect"),
    "Temporal": ("setting", "event"),
    "Conditional": ("antecedent", "consequent"),
    "RelativeRestriction": ("head", "restriction"),
    "Control": ("subject", "controller", "inner"),
    "Event": ("agent", "patient"),
    "Negation": ("operand",),
}


def _collect_predicates(tree: Any) -> List[Any]:
    """A COMPLETE predicate walk for the skeleton. Like ``queries.predicates()`` but it ALSO
    descends into ClauseCoordination / Coordination / Conditional / Temporal, so events nested
    under a top-level coordination ("betrayed Aldric and murdered him") are not lost. Kept
    LOCAL here so the shared ``queries.predicates()`` (relied on by inference.py) is untouched."""
    out: List[Any] = []
    seen: set = set()

    def walk(n: Any) -> None:
        if n is None or id(n) in seen:
            return
        seen.add(id(n))
        nm = type(n).__name__
        if nm in _YIELD_PREDS:
            out.append(n)
        if nm == "Coordination":
            for m in getattr(n, "members", []) or []:
                walk(m)
        elif nm == "Op":
            for a in getattr(n, "args", []) or []:
                walk(a)
        else:
            for f in _CONTAINER_FIELDS.get(nm, ()):
                walk(getattr(n, f, None))

    walk(tree)
    return out


class NarrativeGraph:
    """Entities (+ role-timelines) and event/causal/temporal edges of a document."""

    def __init__(self) -> None:
        self.nodes: Dict[str, _Node] = {}
        self.edges: List[Edge] = []
        self.excluded = 0          # predicates that anchored no resolved entity

    # -- construction -------------------------------------------------------
    def _node(self, ent: Any) -> Optional[_Node]:
        eid = _eid(ent)
        if eid is None:
            return None
        n = self.nodes.get(eid)
        if n is None:
            n = _Node(eid=eid, thread=tuple(getattr(ent, "type_thread", ()) or ()))
            self.nodes[eid] = n
        n.surface.add(_label(ent))
        if not n.thread and getattr(ent, "type_thread", ()):
            n.thread = tuple(ent.type_thread)
        head = getattr(ent, "head", None)                      # bundle the primitive profile
        for p, v in (getattr(head, "word_primitives", {}) or {}).items():
            n.prims[p] = n.prims.get(p, 0) + v
        hpos = getattr(head, "pos", "") or ""
        if hpos and (not n.pos or n.pos not in ("NOUN", "PROPN")):   # prefer a nominal POS
            n.pos = hpos
        if not n.lemma:
            n.lemma = getattr(head, "lemma", "") or ""
        return n

    def _state(self, ent: Any, kind: Any, t: int) -> bool:
        n = self._node(ent)
        if n is None:
            return False
        n.roles.append((t, _label(kind)))
        return True

    def _edge(self, kind: str, a: Any, rel: str, b: Any, t: int) -> bool:
        na, nb = self._node(a), self._node(b) if b is not None else None
        src = na.eid if na else _label(a)
        dst = (nb.eid if nb else _label(b)) if b is not None else ""
        if na is None and nb is None:
            return False                      # neither endpoint resolved → not in the spine
        self.edges.append(Edge(t, kind, src, rel, dst, na is not None, nb is not None))
        if na:
            na.degree += 1
        if nb:
            nb.degree += 1
        return True

    @classmethod
    def from_document(cls, trees: List[Any], genealogy: Any = None) -> "NarrativeGraph":
        g = cls()
        for t, tree in enumerate(trees):
            for p in _collect_predicates(tree):
                nm = type(p).__name__
                ok = False
                if nm == "TypeAssertion":
                    ok = g._state(p.entity, p.kind, t)
                elif nm == "Event":
                    if p.verb in _STATE_VERBS and p.patient is not None:
                        ok = g._state(p.agent, p.patient, t)          # "became king" → role
                    else:
                        ok = g._edge("event", p.agent, p.verb, p.patient, t)
                elif nm == "Causation":
                    ok = g._edge("cause", p.cause, "causes", p.effect, t)
                elif nm == "Temporal":
                    ok = g._edge("temporal", p.setting, "then", p.event, t)
                else:
                    ok = True       # other predicates (Comparison etc.) aren't spine edges; not "excluded noise"
                if not ok:
                    g.excluded += 1
        g._finalize(genealogy)
        g._heal()
        return g

    def _finalize(self, genealogy: Any = None) -> None:
        """Fold grammatical POS + semantic-bank role + graph position (+ a role-biased
        world-strand heal) into per-node role and eligibility. Citizenship propagates by
        traversal from grounded neighbours; collapsed blobs and non-nominals drop out."""
        subj_of: Dict[str, int] = defaultdict(int)
        obj_of: Dict[str, int] = defaultdict(int)
        adj: Dict[str, Set[str]] = defaultdict(set)
        for e in self.edges:
            if e.kind == "event":
                if e.src_resolved:
                    subj_of[e.src] += 1
                if e.dst_resolved:
                    obj_of[e.dst] += 1
            if e.src in self.nodes and e.dst in self.nodes:
                adj[e.src].add(e.dst)
                adj[e.dst].add(e.src)

        def animate(n: _Node) -> bool:
            return bool({p for p, v in n.prims.items() if v} & _ANIMATE)

        def grounded(n: _Node) -> bool:
            return bool(n.thread) or animate(n)

        def nominal(n: _Node) -> bool:
            if n.pos in ("NOUN", "PROPN", "PRON"):
                return True
            return (_SUBSTANTIVES is not None
                    and _SUBSTANTIVES in {_PRIME_BANK.get(p) for p, v in n.prims.items() if v})

        def blob(n: _Node) -> bool:
            toks = max((len(s.split()) for s in n.surface), default=1)
            return toks > 2 and not n.thread

        for n in self.nodes.values():
            role, _e, _b = classify(n.prims, n.thread)
            # Role-biased grounding heal: an ungrounded PROPER NOUN in a referent slot is a
            # proper-noun person/thing → bias a sparse-wiki world-strand lookup. Real referents
            # ground; fictional names stay world-ungrounded (honest), admitted by role instead.
            if (not grounded(n) and n.pos == "PROPN" and n.lemma
                    and genealogy is not None and hasattr(genealogy, "candidates")):
                try:
                    cands = genealogy.candidates(n.lemma, "PROPN", True)
                    if cands:
                        n.thread = tuple(cands[0])
                        n.provenance.append("world-strand: grounded '%s' → %s"
                                            % (n.lemma, n.thread[-1] if n.thread else "?"))
                except Exception:
                    pass
            nbr_grounded = any(grounded(self.nodes[m]) for m in adj.get(n.eid, ()))
            # Admit-by-exclusion: a truly OOV referent — a proper noun, or a jargon NOUN with no
            # lexical decomposition — that fills a RESOLVED event role-slot is a name/term, not
            # noise. Admit it by its surface bytes even when world-ungrounded: the validation is
            # the exclusion itself (absent from the lexicon) plus the defensible structural home
            # (the role-slot it occupies). The resolved-participation guard holds the noise floor —
            # a free-floating OOV token with no event role stays eliminated. (The world-strand
            # positive path above grounds the real referents first; this catches the fictional/
            # jargon tail the comment there always promised but the gate never delivered.)
            participates = bool(subj_of.get(n.eid) or obj_of.get(n.eid))
            oov_referent = (n.pos == "PROPN"
                            or (n.pos == "NOUN" and not any(n.prims.values())))
            admit_by_exclusion = (not grounded(n) and not nbr_grounded
                                  and oov_referent and participates)
            n.eligible = nominal(n) and (not blob(n)) and (
                grounded(n) or nbr_grounded or admit_by_exclusion)
            if n.eligible and admit_by_exclusion:
                n.provenance.append("admitted by exclusion: OOV %s in role-slot"
                                    % ("name" if n.pos == "PROPN" else "term"))
            if role == "?":
                role = "agent" if subj_of.get(n.eid) else ("object" if obj_of.get(n.eid) else "?")
            n.role = role

    def _heal(self) -> None:
        """Discourse-strand correction: an EVENT whose subject was dropped/garbled (its agent
        slot is an ineligible non-entity) is zero-anaphora — bind it to the current discourse
        topic (the most-recent eligible agent-subject). Full-blast + provenance-stamped, so the
        back end stays auditable and re-runnable; aggressiveness calibrates from the audit."""
        topic = None
        for e in sorted(self.edges, key=lambda e: e.t):
            if e.kind != "event":
                continue
            src = self.nodes.get(e.src)
            if src is not None and src.eligible and src.role == "agent":
                topic = e.src                                    # the running discourse topic
            elif (src is None or not src.eligible) and topic is not None:
                old, e.src, e.src_resolved = e.src, topic, True
                e.provenance.append("discourse: dropped-subject [%s] → topic [%s]" % (old, topic))
                self.nodes[topic].degree += 1

    # -- inspection ---------------------------------------------------------
    def significant_nodes(self) -> List[_Node]:
        """Entities that participate — have a role-timeline or touch an edge."""
        return [n for n in self.nodes.values() if n.roles or n.degree > 0]

    def render(self) -> str:
        out: List[str] = []
        nodes = [n for n in self.nodes.values() if n.roles or n.degree > 0]
        # Signal unification: rank by the SAME semantic-informativeness the compaction uses
        # (op class of incident edges + role-states), not raw degree — one significance notion.
        _kind_op = {"event": "EVENT", "cause": "CAUSATION", "temporal": "TEMPORAL"}
        node_sig: Dict[str, float] = defaultdict(float)
        for e in self.edges:
            w = _OP_BASE.get(_kind_op.get(e.kind, ""), 1.0)
            if e.src in self.nodes:
                node_sig[e.src] += w
            if e.dst in self.nodes:
                node_sig[e.dst] += w
        elig = sorted((n for n in nodes if n.eligible),
                      key=lambda n: (-(node_sig.get(n.eid, 0.0) + len(n.roles)), n.eid))
        elim = [n for n in nodes if not n.eligible]
        elig_ids = {n.eid for n in elig}

        out.append(f"NARRATIVE ENTITIES (eligible {len(elig)} / eliminated-as-noise {len(elim)} "
                   f"/ {len(self.nodes)} resolved)")
        for n in elig:
            surf = "/".join(sorted(n.surface))
            inv = n.thread[-1] if n.thread else "·"
            line = f"  {n.eid:>4}  [{n.role:<11}] {surf:<22} ⟨{inv}⟩ deg={n.degree}"
            if n.roles:
                line += "   roles: " + " → ".join(r for _, r in n.roles)
            out.append(line)

        spine = [e for e in sorted(self.edges, key=lambda e: (e.t, e.kind))
                 if e.src in elig_ids or e.dst in elig_ids]
        out.append(f"\nSPINE edges (touch an eligible entity): {len(spine)} of {len(self.edges)}")
        for e in spine:
            arrow = f"{e.src} —{e.rel}→ {e.dst}".rstrip(" —→")
            out.append(f"  t{e.t:<3} [{e.kind}] {arrow}")

        if elim:
            names = sorted({"/".join(sorted(n.surface)) for n in elim})
            out.append(f"\nELIMINATED (informational zero — no entity bank, no thread): {len(elim)}")
            out.append("  " + ", ".join(names[:30]) + (" …" if len(names) > 30 else ""))
        out.append(f"\nunanchored clause-predicates: {self.excluded}")
        return "\n".join(out)

    def emit(self) -> List[Dict[str, Any]]:
        """Serialize the eligible spine as a TIME-ORDERED list of v2 contract envelopes
        (TYPE_ASSERT for role-states, EVENT/CAUSATION/TEMPORAL for edges). This is the
        compressed narrative skeleton the Genesis bridge walks IN PLACE OF the N raw
        per-sentence contracts — the customs office handing the engine the spine, not the
        noise. Envelopes are standard §5 shape, so the existing walker consumes them 1:1."""
        elig = {n.eid for n in self.nodes.values() if n.eligible}

        def ref(eid: str):
            n = self.nodes.get(eid)
            if n is None:
                return None
            lemma = min(n.surface, key=len) if n.surface else (n.lemma or eid)
            return {"entity_id": n.eid, "lemma": lemma, "type_thread": list(n.thread)}

        items: List[Tuple[int, Dict[str, Any]]] = []
        for n in self.nodes.values():
            if not n.eligible:
                continue
            r = ref(n.eid)
            for (t, state) in n.roles:
                if r is not None:
                    feats = {"_prov": list(n.provenance)} if n.provenance else {}
                    items.append((t, {"op": "TYPE_ASSERT", "args": [r, state], "features": feats}))
        for e in self.edges:
            if e.src not in elig and e.dst not in elig:
                continue
            src = ref(e.src) if (e.src_resolved and e.src in self.nodes) else None
            dst = ref(e.dst) if (e.dst_resolved and e.dst in self.nodes) else None
            prov = {"_prov": list(e.provenance)} if e.provenance else {}
            if e.kind == "event" and src is not None:
                args = [src] + ([dst] if dst is not None else [])
                items.append((e.t, {"op": "EVENT", "args": args, "features": {"verb": e.rel, **prov}}))
            elif e.kind == "cause" and src is not None and dst is not None:
                items.append((e.t, {"op": "CAUSATION", "args": [src, dst], "features": {"conjunction": "so", **prov}}))
            elif e.kind == "temporal" and src is not None and dst is not None:
                items.append((e.t, {"op": "TEMPORAL", "args": [src, dst], "features": {"conjunction": "when", **prov}}))
        items.sort(key=lambda it: it[0])
        return [{"contract_version": "2.0", "predicate": env} for _, env in items]


# ============================================================================
# ADAPTIVE COMPACTION — the granularity controller (a "compact system for text").
#   (B) semantic S/N : a trace's informativeness is its position on the
#       flat(naming) → relational(event) → nested(causal/logical) spectrum.
#   (A) complexity budget : GSE's TextProfile sets the trace ceiling, the target
#       S/N (the text's intrinsic relational share), and the prune floor.
#   (C) compact-cycling : iteratively merge-redundant + prune-low-info + cap-to-
#       budget until the document S/N plateaus or budget+target are met; track a
#       per-trace iteration count and a global counter (the efficiency profile).
# Narrative TIME ORDER is preserved — Genesis reasons over the sequence.
# ============================================================================

_FLAT_OPS = {"TYPE_ASSERT"}
_RELATIONAL_OPS = {"EVENT", "COMPARISON", "REL_RESTRICT"}
_LOGICAL_OPS = {"CAUSATION", "TEMPORAL", "IMPLIES", "CONTROL", "CONTRAST", "CLAUSE_COORD", "NOT"}
_STRUCTURE_OPS = _RELATIONAL_OPS | _LOGICAL_OPS
_OP_BASE = {**{o: 1.0 for o in _FLAT_OPS},
            **{o: 2.0 for o in _RELATIONAL_OPS},
            **{o: 3.0 for o in _LOGICAL_OPS}}


def _is_ref(a: Any) -> bool:
    return isinstance(a, dict) and "entity_id" in a


def _is_op(a: Any) -> bool:
    return isinstance(a, dict) and "op" in a


def _op_of(contract: Dict[str, Any]) -> str:
    p = contract.get("predicate", contract)
    return p.get("op", "") if isinstance(p, dict) else ""


def trace_info(contract: Dict[str, Any]) -> float:
    """(B) Semantic informativeness on the flat→relational→nested spectrum: op class
    (naming < event < causal/logical) + grounded-referent arity + nesting depth."""
    p = contract.get("predicate", contract)
    if not isinstance(p, dict):
        return 0.5
    score = _OP_BASE.get(p.get("op", ""), 0.5)
    for a in p.get("args", []) or []:
        if _is_ref(a):
            score += 0.6 if a.get("type_thread") else 0.3   # grounded vs bare referent
        elif _is_op(a):
            score += 1.0                                     # a nested predicate = logical depth
    return score


def _trace_key(contract: Dict[str, Any]):
    """Identity for redundancy-merge: op + verb + the sorted referents it relates."""
    p = contract.get("predicate", contract)
    if not isinstance(p, dict):
        return ("?",)
    verb = (p.get("features", {}) or {}).get("verb", "")
    ids = tuple(sorted(a.get("entity_id") if _is_ref(a) else str(a)
                       for a in (p.get("args", []) or []) if _is_ref(a) or isinstance(a, str)))
    return (p.get("op", ""), verb, ids)


def document_sn(contracts: List[Dict[str, Any]]) -> float:
    """Semantic S/N of a trace SET: the share of total informativeness carried by
    RELATIONAL+LOGICAL structure vs the flat naming baseline. Rises as flat noise is pruned."""
    tot = sig = 0.0
    for c in contracts:
        i = trace_info(c)
        tot += i
        if _op_of(c) in _STRUCTURE_OPS:
            sig += i
    return sig / tot if tot else 0.0


def budget_from_profile(profile: Any, n_traces: int) -> Dict[str, float]:
    """(A) The complexity controller. GSE's TextProfile sets the trace budget (denser text
    earns a higher ceiling), the target S/N (the text's intrinsic relational share), and the
    prune floor (noisier parses cut harder). Degrades to a length default with no profile."""
    if profile is not None and getattr(profile, "complexity", None):
        cx = profile.complexity or {}
        mix = getattr(profile, "operator_mix", {}) or {}
        coh = getattr(profile, "coherence", {}) or {}
        n_sents = max(getattr(profile, "n_sentences", 1), 1)
        density = (cx.get("tokens_per_sent", 12) / 12.0
                   + cx.get("embed_rate", 0.0)
                   + cx.get("ops_per_sent", 1.0) / 3.0)
        budget = int(min(80, max(8, round(n_sents * (1.0 + density)))))
        struct = sum(mix.get(o, 0.0) for o in _STRUCTURE_OPS)
        target_sn = min(0.85, struct / sum(mix.values())) if sum(mix.values()) else 0.5
        prune_floor = 1.2 + 1.0 * min(coh.get("degraded_rate", 0.0), 1.0)
    else:
        budget = int(min(80, max(8, round(n_traces * 0.5))))
        target_sn, prune_floor = 0.5, 1.2
    return {"budget": budget, "target_sn": target_sn, "prune_floor": prune_floor}


@dataclass
class Trace:
    contract: Dict[str, Any]
    info: float
    order: int                 # original time index — the narrative sequence
    key: Any
    iters: int = 0             # (C) per-trace survival counter; reset when re-formed


def compress(graph: "NarrativeGraph", profile: Any = None, max_cycles: int = 8):
    """Parts A+B+C composed. Returns (compacted_contracts, report). The report's S/N
    trajectory + global iteration count IS the efficiency profile / plateau monitor."""
    raw = graph.emit()
    traces = [Trace(c, trace_info(c), i, _trace_key(c)) for i, c in enumerate(raw)]
    ctrl = budget_from_profile(profile, len(traces))
    budget, target_sn, prune_floor = ctrl["budget"], ctrl["target_sn"], ctrl["prune_floor"]

    def sn(ts):
        return document_sn([t.contract for t in ts])

    trajectory = [round(sn(traces), 3)]
    sizes = [len(traces)]
    global_iters = 0
    plateau = "max-cycles"
    for _cycle in range(max_cycles):
        before_n, before_sn = len(traces), sn(traces)

        # (C-i) redundancy-merge — the same edge stated twice collapses to one; the survivor
        #       inherits the iteration credit (re-seen → it has earned its place).
        by_key: Dict[Any, Trace] = {}
        for t in sorted(traces, key=lambda t: t.order):
            if t.key in by_key:
                by_key[t.key].iters += t.iters + 1
            else:
                by_key[t.key] = t
        cur = list(by_key.values())

        # (C-ii) low-info prune — flat naming below the complexity-set floor; relational and
        #        logical structure is always spared (it IS the signal we're concentrating).
        cur = [t for t in cur if _op_of(t.contract) in _STRUCTURE_OPS or t.info >= prune_floor]

        # (C-iii) budget ceiling — keep the most informative when over the complexity cap.
        if len(cur) > budget:
            cur = sorted(cur, key=lambda t: -t.info)[:budget]

        for t in cur:
            t.iters += 1
        traces = cur
        global_iters += 1
        cur_sn = sn(traces)
        trajectory.append(round(cur_sn, 3))
        sizes.append(len(traces))

        if len(traces) == before_n and abs(cur_sn - before_sn) < 1e-3:
            plateau = "converged (no change)"
            break
        if cur_sn >= target_sn and len(traces) <= budget:
            plateau = "target S/N + budget met"
            break

    contracts = [t.contract for t in sorted(traces, key=lambda t: t.order)]   # restore narrative order
    report = {
        "raw_traces": len(raw), "final_traces": len(traces), "budget": budget,
        "target_sn": round(target_sn, 3), "final_sn": trajectory[-1],
        "sn_trajectory": trajectory, "size_trajectory": sizes,
        "global_iters": global_iters, "plateau": plateau,
        "prune_floor": round(prune_floor, 2),
        "max_iters_single_trace": max((t.iters for t in traces), default=0),
    }
    return contracts, report
