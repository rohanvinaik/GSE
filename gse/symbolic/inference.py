"""
Deterministic logical inference over the clause graph — transitive closure.

Solves the transitivity / ordering class of logical-reasoning problems — the
"zorble/florp" / LSAT linear-ordering & type-hierarchy class. From a document's
resolved clause graphs it collects **is-a** edges (from ``TypeAssertion``) and
**ordering** edges (from ``Comparison``), then answers queries by breadth-first
search over the transitive closure — returning the **derivation chain**, and
refusing the unentailed direction (no false positives).

Everything here is integer/set graph work — deterministic by construction.

Conditionals (2026-07-01): parsed ``Conditional`` clauses ("If a member misses
the payment then the member loses the vote") are stored as rules, and
:meth:`KnowledgeBase.event` answers event queries by **modus ponens** — a rule
fires when its antecedent is derivable (an event fact, an is-a chain, or an
ordering chain), with the rule's generic subject ("a member") bound to the
queried individual through the is-a hierarchy ("alice → member"). Negated
clauses (``Negation``) are stored as negative facts, never asserted positively —
at any depth. Ingestion walks each tree by its assertion modality
(:mod:`gse.symbolic.modality`, shared with the narrative skeleton): an attitude
verb's complement ("believes that X") and an irrealis control verb's inner act
("refused to bow") are never asserted, and a conditional asserts neither clause.

**Boundary (honest):** the transitive/subset fragment plus single-antecedent
modus ponens. "all X are Y" and "a X is a Y" collapse to the same is-a edge —
sound for the syllogism — and a rule binds ONE generic subject through the
type hierarchy; there is no quantifier scope, no conjunction of antecedents,
no negation-as-failure (a negative fact refuses assertion; it does not license
inference). This is the linear-ordering / type-chain / conditional-chain
fragment of logical reasoning, not all of it.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from gse.symbolic.modality import assertion_mode
from gse.symbolic.predicates import OPERAND_FIELDS
from gse.symbolic.queries import predicates


def _lemma(node: Any) -> Optional[str]:
    name = type(node).__name__
    if name == "Entity":
        return node.head.lemma
    if name == "Atom":
        return node.lemma
    if name == "Phrase":
        return " ".join(a.lemma for a in node.atoms)
    return None


@dataclass(frozen=True)
class Derivation:
    """The verdict of a query, with its proof chain."""

    holds: bool
    relation: str  # "is_a" | "greater"
    query: Tuple[str, str]  # (x, y)
    chain: Tuple[str, ...]  # the derivation path; () when not entailed
    axis: Optional[str] = None

    def __str__(self) -> str:
        q = f"{self.relation}({self.query[0]}, {self.query[1]})"
        if self.holds:
            return f"{q}  =  TRUE     ⊢  {' → '.join(self.chain)}"
        return f"{q}  =  not entailed"


class KnowledgeBase:
    """Is-a and ordering edges collected from a document's clause graphs."""

    def __init__(self) -> None:
        self._isa: Dict[str, Set[str]] = defaultdict(set)
        self._gt: Dict[Tuple[Optional[str], str], Set[str]] = defaultdict(set)
        self._axes: Set[Optional[str]] = set()
        # (verb, agent, patient) event facts; negative facts kept apart so a
        # negated clause is never asserted positively.
        self._facts: Set[Tuple[str, Optional[str], Optional[str]]] = set()
        self._neg_facts: Set[Tuple[str, Optional[str], Optional[str]]] = set()
        self._rules: List[Tuple[Any, Any]] = []  # (antecedent pred, consequent Event)

    @staticmethod
    def _event_key(p: Any) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        if type(p).__name__ != "Event":
            return None
        patient = _lemma(p.patient) if p.patient is not None else None
        return (p.verb, _lemma(p.agent), patient)

    def _harvest_thread(self, operand: Any) -> None:
        """A RESOLVED entity carries its two-strand type genealogy
        (``Entity.type_thread``, WordNet or sparse-wiki world lineage). Ingest it
        as is-a edges — Napoleon's ``Thing → Agent → Person → Royalty`` makes
        ``is_a(napoleon, person)`` derivable with the thread as the chain, so a
        rule about "a person" can bind a referent the TEXT never types. This is
        the world-grounding leg feeding the reasoner: the premise comes from the
        encyclopedia, deterministically, with provenance."""
        thread = getattr(operand, "type_thread", None) or ()
        lemma = _lemma(operand)
        if not thread or not lemma:
            return
        nodes = [lemma] + [t.lower() for t in reversed(thread)]  # specific → root
        for child, parent in zip(nodes, nodes[1:]):
            if child != parent:
                self._isa[child].add(parent)

    def _harvest_threads(self, p: Any) -> None:
        for field in ("agent", "patient", "entity", "kind", "lhs", "rhs"):
            operand = getattr(p, field, None)
            if operand is not None:
                self._harvest_thread(operand)

    def _ingest(self, p: Any, negated: bool = False) -> None:
        name = type(p).__name__
        if name == "Negation":
            self._ingest(p.operand, negated=not negated)
            return
        if name == "Conditional":
            # A rule needs both sides as stated: the reasoner has no negated antecedent or
            # consequent (no negation-as-failure), so a negated side ABSTAINS rather than
            # flattening to its positive clause — "if X does not bark" is not "if X barks" (#7).
            if "negated" in (assertion_mode(type(p.antecedent).__name__), assertion_mode(type(p.consequent).__name__)):
                return
            ant = predicates(p.antecedent)
            cons = predicates(p.consequent)
            if ant and cons and type(cons[0]).__name__ == "Event":
                self._rules.append((ant[0], cons[0]))
            return
        if name == "Event":
            key = self._event_key(p)
            if key:
                (self._neg_facts if negated else self._facts).add(key)
            self._harvest_threads(p)
            return
        if negated:
            return  # a negated comparison/type is withheld, not inverted
        if name == "TypeAssertion":
            x, y = _lemma(p.entity), _lemma(p.kind)
            if x and y:
                self._isa[x].add(y)
            self._harvest_threads(p)
        elif name == "Comparison":
            x, y = _lemma(p.lhs), _lemma(p.rhs)
            if x and y:
                axis = getattr(p, "axis", None)
                hi, lo = (x, y) if p.sign >= 0 else (y, x)
                self._gt[(axis, hi)].add(lo)
                self._axes.add(axis)

    def _ingest_tree(self, node: Any) -> None:
        """Ingest what a clause tree ASSERTS — a structural walk, not a flatten (#7).

        Flattening through ``queries.predicates()`` asserted everything it reached: the operand of
        a nested ``Negation`` as a positive fact, an irrealis control verb's inner act ("refused to
        bow" → bow), an attitude verb's complement ("believes that X is a traitor" → is-a), and,
        once ``predicates()`` descends into a ``Conditional``, both of its clauses. Each node's
        :func:`~gse.symbolic.modality.assertion_mode` decides instead — the same decision the
        narrative skeleton applies — and the walk descends only into content that holds as stated.
        """
        if node is None:
            return
        name = type(node).__name__
        mode = assertion_mode(name, getattr(node, "verb", "") or "", type(getattr(node, "patient", None)).__name__)
        self._ingest(node)  # a fact, a negative fact or a rule; a no-op for a container
        if mode in ("negated", "conditional"):
            return  # nothing beneath holds as stated
        if name == "Op":
            children = list(node.args)
        elif name == "Coordination":
            children = list(node.members)
        else:
            unasserted = {"belief": "patient", "irrealis": "inner"}.get(mode)
            children = [getattr(node, f, None) for f in OPERAND_FIELDS.get(name, ()) if f != unasserted]
        for child in children:
            self._ingest_tree(child)

    @classmethod
    def from_trees(cls, trees: Sequence[Any]) -> "KnowledgeBase":
        kb = cls()
        for tree in trees:
            kb._ingest_tree(tree)
        return kb

    @staticmethod
    def _bfs(neighbors, x: str, y: str) -> Tuple[str, ...]:
        """Shortest path x→y over ``neighbors(node)`` (sorted → deterministic)."""
        if x == y:
            return ()
        prev: Dict[str, Optional[str]] = {x: None}
        queue = deque([x])
        while queue:
            cur = queue.popleft()
            for nxt in sorted(neighbors(cur)):
                if nxt in prev:
                    continue
                prev[nxt] = cur
                if nxt == y:
                    path = [y]
                    c: Optional[str] = cur
                    while c is not None:
                        path.append(c)
                        c = prev[c]
                    return tuple(reversed(path))
                queue.append(nxt)
        return ()

    def is_a(self, x: str, y: str) -> Derivation:
        chain = self._bfs(lambda n: self._isa.get(n, ()), x, y)
        return Derivation(bool(chain), "is_a", (x, y), chain)

    def greater(self, x: str, y: str, axis: Optional[str] = None) -> Derivation:
        axes: List[Optional[str]] = (
            [axis] if axis is not None else sorted(self._axes, key=lambda a: (a is None, a or ""))
        )
        for ax in axes:
            chain = self._bfs(lambda n: self._gt.get((ax, n), ()), x, y)
            if chain:
                return Derivation(True, "greater", (x, y), chain, ax)
        return Derivation(False, "greater", (x, y), (), axis)

    # -- modus ponens over parsed Conditional rules --------------------------
    @staticmethod
    def _fmt(verb: str, agent: Optional[str], patient: Optional[str]) -> str:
        return " ".join(w for w in (agent, verb, patient) if w)

    def _fmt_pred(self, p: Any) -> str:
        """Compact rendering of a rule antecedent for the derivation chain."""
        name = type(p).__name__
        if name == "Event":
            return self._fmt(*(self._event_key(p) or ("?", None, None)))
        if name == "TypeAssertion":
            return f"{_lemma(p.entity)} is-a {_lemma(p.kind)}"
        if name == "Comparison":
            x, y = _lemma(p.lhs), _lemma(p.rhs)
            return f"{x} > {y}" if p.sign >= 0 else f"{y} > {x}"
        return "…"

    def _bind(self, agent: str, generic: Optional[str]) -> Optional[Tuple[str, ...]]:
        """Bind the queried individual to a rule's generic subject: identity, or
        an is-a chain ("alice → member"). None = no binding."""
        if generic is None or agent == generic:
            return ()
        d = self.is_a(agent, generic)
        return d.chain if d.holds else None

    def _antecedent_holds(
        self, ant: Any, agent: str, generic: Optional[str], seen: frozenset
    ) -> Optional[Tuple[str, ...]]:
        """Derivation chain for a rule's antecedent with the generic subject
        bound to ``agent``; None when not derivable."""
        name = type(ant).__name__
        if name == "Event":
            verb, a, patient = self._event_key(ant)  # type: ignore[misc]
            a = agent if a == generic else a
            if a is None:
                return None
            d = self.event(verb, a, patient, _seen=seen)
            if d.holds:
                return d.chain
            # the rule's patient may be GENERIC too ("… leads a country"): a fact
            # whose patient is-a the generic satisfies it — the same is-a binding
            # as the subject, on the object slot (france → country).
            if patient is not None:
                for fv, fa, fp in sorted(self._facts, key=repr):
                    if fv != verb or fa != a or fp is None or fp == patient:
                        continue
                    bind = self.is_a(fp, patient)
                    if bind.holds:
                        return (f"fact: {self._fmt(fv, fa, fp)}", " → ".join(bind.chain))
            return None
        if name == "TypeAssertion":
            x, y = _lemma(ant.entity), _lemma(ant.kind)
            x = agent if x == generic else x
            if x and y:
                d = self.is_a(x, y)
                return d.chain if d.holds else None
        elif name == "Comparison":
            x, y = _lemma(ant.lhs), _lemma(ant.rhs)
            x = agent if x == generic else x
            y = agent if y == generic else y
            if x and y:
                hi, lo = (x, y) if ant.sign >= 0 else (y, x)
                d = self.greater(hi, lo)
                return d.chain if d.holds else None
        return None

    def event(self, verb: str, agent: str, patient: Optional[str] = None, _seen: frozenset = frozenset()) -> Derivation:
        """Does ``agent verb patient`` hold — as a stated fact, or by modus
        ponens through the Conditional rules (the generic rule subject bound to
        ``agent`` via the is-a hierarchy)? Refuses (``not entailed``) rather
        than fabricates; a negated fact never satisfies a query."""
        query = (verb, agent, patient)
        pretty = self._fmt(verb, agent, patient)
        if query in _seen:  # cycle guard for rule chains
            return Derivation(False, "event", (agent, pretty), ())
        if query in self._facts:
            return Derivation(True, "event", (agent, pretty), (f"fact: {pretty}",))
        seen = _seen | {query}
        for ant, cons in self._rules:
            c_verb, c_agent, c_patient = self._event_key(cons)  # type: ignore[misc]
            if c_verb != verb or c_patient != patient:
                continue
            bridge = self._bind(agent, c_agent)
            if bridge is None:
                continue
            ant_chain = self._antecedent_holds(ant, agent, c_agent, seen)
            if ant_chain is None:
                continue
            rule_str = f"rule: {self._fmt_pred(ant)} ⇒ {self._fmt(c_verb, c_agent, c_patient)}"
            chain = tuple(ant_chain) + ((" → ".join(bridge),) if bridge else ()) + (rule_str, f"∴ {pretty}")
            return Derivation(True, "event", (agent, pretty), chain)
        return Derivation(False, "event", (agent, pretty), ())
