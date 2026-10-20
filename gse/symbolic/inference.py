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

from gse.symbolic.claims import claim_key, commitment, identity, polarity, scope_signature
from gse.symbolic.modality import assertion_mode
from gse.symbolic.propositions import Proposition, propositions
from gse.symbolic.queries import entities


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
    source_ids: Tuple[str, ...] = ()

    @property
    def state(self) -> str:
        """Named decision; ``holds`` remains the compatibility projection."""
        return "entailed" if self.holds else "not_entailed"

    def __str__(self) -> str:
        q = f"{self.relation}({self.query[0]}, {self.query[1]})"
        if self.holds:
            return f"{q}  =  TRUE     ⊢  {' → '.join(self.chain)}"
        return f"{q}  =  not entailed"


@dataclass(frozen=True)
class Admission:
    source_id: str
    kind: str
    state: str
    commitment: str
    reason: str = ""


@dataclass(frozen=True)
class ClaimDerivation:
    state: str
    key: tuple | None
    sign: int | None
    source_ids: Tuple[str, ...] = ()
    reason: str = ""
    rule_chain: Tuple[str, ...] = ()


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
        self._neg_types: Set[Tuple[str, str]] = set()
        self._neg_comparisons: Set[Tuple[Any, ...]] = set()
        self.admissions: List[Admission] = []
        self._active_source = ""
        self._fact_sources: Dict[tuple, Set[str]] = defaultdict(set)
        self._isa_sources: Dict[tuple, Set[str]] = defaultdict(set)
        self._gt_sources: Dict[tuple, Set[str]] = defaultdict(set)
        self._rule_sources: Dict[int, str] = {}
        self._chain_sources: Dict[tuple, Tuple[str, ...]] = {}
        self._claim_facts: Dict[tuple, Set[str]] = defaultdict(set)
        self._relation_primitives = None
        self._resolved_names: Dict[str, Set[str]] = defaultdict(set)
        self._resolved_aliases: Dict[str, Set[str]] = defaultdict(set)
        self._unresolved_names: Set[str] = set()

    @staticmethod
    def _event_key(p: Any) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        if type(p).__name__ != "Event":
            return None
        if getattr(p, "themes", ()):
            return None  # lexical event() cannot express secondary argument roles
        patient = _lemma(p.patient) if p.patient is not None else None
        if (
            p.patient is not None
            and patient is None
            and assertion_mode("Event", p.verb, type(p.patient).__name__) not in {"belief", "epistemic"}
        ):
            return None
        if not p.verb or _lemma(p.agent) is None:
            return None
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
                self._isa_sources[(child, parent)].add(f"world:{lemma}")

    def _harvest_threads(self, p: Any) -> None:
        for field in ("agent", "patient", "entity", "kind", "lhs", "rhs"):
            operand = getattr(p, field, None)
            if operand is not None:
                self._harvest_thread(operand)

    def _ingest(self, p: Any, negated: bool = False, base_kind: str | None = None) -> str:
        name = type(p).__name__
        if name == "Negation":
            return "unsupported_direct_negation"  # shared propositions owns sign composition
        if name == "Conditional":
            if negated:
                return "unsupported_negated_rule"
            ant, cons = p.antecedent, p.consequent
            if type(ant).__name__ not in {"Event", "TypeAssertion", "Comparison"} or type(cons).__name__ != "Event":
                return "unsupported_rule_structure"
            # Validate the WHOLE arms, never their first flattened predicates.
            for arm in (ant, cons):
                readings = propositions(arm)
                if len(readings) != 1 or commitment(readings[0]) != "committed":
                    return "unsupported_rule_scope"
                signed = polarity(readings[0])
                if signed.state != "read" or signed.sign != 1:
                    return "unsupported_rule_polarity"
                if type(arm).__name__ == "Event" and self._event_key(arm) is None:
                    return "unsupported_rule_arguments"
                if type(arm).__name__ == "TypeAssertion" and not (_lemma(arm.entity) and _lemma(arm.kind)):
                    return "unsupported_rule_arguments"
                if type(arm).__name__ == "Comparison" and not (_lemma(arm.lhs) and _lemma(arm.rhs)):
                    return "unsupported_rule_arguments"
            self._rules.append((ant, cons))
            self._rule_sources[len(self._rules) - 1] = self._active_source
            return "admitted_rule"
        if name == "Event":
            key = self._event_key(p)
            if key:
                (self._neg_facts if negated else self._facts).add(key)
                self._fact_sources[(negated, key)].add(self._active_source)
            self._harvest_threads(p)
            return (
                "admitted_negative" if negated and key else ("admitted_fact" if key else "unsupported_event_arguments")
            )
        if negated:
            if name == "TypeAssertion":
                x, y = _lemma(p.entity), base_kind or _lemma(p.kind)
                if x and y:
                    self._neg_types.add((x, y))
            elif name == "Comparison":
                self._neg_comparisons.add((_lemma(p.lhs), _lemma(p.rhs), p.sign, p.axis))
            return "admitted_negative"  # retained separately, never inverted
        if name == "TypeAssertion":
            x, y = _lemma(p.entity), base_kind or _lemma(p.kind)
            if x and y:
                self._isa[x].add(y)
                self._isa_sources[(x, y)].add(self._active_source)
            self._harvest_threads(p)
            return "admitted_fact" if x and y else "unsupported_type_arguments"
        elif name == "Comparison":
            x, y = _lemma(p.lhs), _lemma(p.rhs)
            if x and y:
                axis = getattr(p, "axis", None)
                hi, lo = (x, y) if p.sign >= 0 else (y, x)
                self._gt[(axis, hi)].add(lo)
                self._axes.add(axis)
                self._gt_sources[(axis, hi, lo)].add(self._active_source)
                return "admitted_fact"
            return "unsupported_comparison_arguments"
        return "structural_only"

    def _ingest_tree(
        self,
        node: Any,
        *,
        source_text: str | None = None,
        source_claim_ids: Sequence[str] | None = None,
    ) -> None:
        """Admit only the shared authority's committed signed propositions."""
        extracted = propositions(node, source_text=source_text)
        if source_claim_ids is not None:
            if (
                not isinstance(source_claim_ids, Sequence)
                or isinstance(source_claim_ids, (str, bytes))
                or len(source_claim_ids) != len(extracted)
            ):
                raise ValueError("source_claim_ids must align one-to-one with extracted propositions")
            if any(not isinstance(item, str) or not item.strip() for item in source_claim_ids):
                raise ValueError("source_claim_ids must be nonempty claim identities")
        for index, proposition in enumerate(extracted):
            if source_claim_ids is not None:
                self._active_source = source_claim_ids[index]
            mode = commitment(proposition)
            if mode != "committed":
                self.admissions.append(Admission(self._active_source, proposition.kind, "withheld", mode, mode))
                continue
            signed = polarity(proposition)
            if signed.state != "read":
                self.admissions.append(
                    Admission(self._active_source, proposition.kind, "withheld", mode, signed.reason)
                )
                continue
            result = self._ingest(proposition.node, negated=signed.sign == -1, base_kind=signed.base)
            self.admissions.append(Admission(self._active_source, proposition.kind, result, mode))
            key = claim_key(proposition, self._relation_primitives)
            if key.state == "supported":
                self._claim_facts[(key.key, signed.sign)].add(self._active_source)

    @classmethod
    def from_trees(
        cls,
        trees: Sequence[Any],
        *,
        source_texts: Sequence[str] | None = None,
        source_ids: Sequence[str] | None = None,
        source_claim_ids: Sequence[Sequence[str]] | None = None,
        relation_primitives=None,
    ) -> "KnowledgeBase":
        """Build the bounded KB, retaining admission and source evidence.

        The legacy ``event/is_a/greater`` methods are lexical projections for
        the documented type/order/single-antecedent fragment. ``claim`` uses
        certified referent-aware keys and refuses unresolved comparisons.
        """
        if source_texts is not None and len(source_texts) != len(trees):
            raise ValueError("source_texts must align one-to-one with trees")
        if source_ids is not None and len(source_ids) != len(trees):
            raise ValueError("source_ids must align one-to-one with trees")
        if source_claim_ids is not None:
            if (
                not isinstance(source_claim_ids, Sequence)
                or isinstance(source_claim_ids, (str, bytes))
                or len(source_claim_ids) != len(trees)
            ):
                raise ValueError("source_claim_ids must align one-to-one with trees")
            if any(item is None for item in source_claim_ids):
                raise ValueError("source_claim_ids needs an explicit claim sequence for each tree")
        kb = cls()
        kb._relation_primitives = relation_primitives
        for index, tree in enumerate(trees):
            for entity in entities(tree):
                evidence = identity(entity)
                eid = entity.entity_id
                if evidence.state == "resolved" and evidence.lemma and isinstance(eid, str):
                    kb._resolved_names[evidence.lemma].add(eid)
                    kb._resolved_aliases[eid].add(evidence.lemma)
                elif evidence.lemma:
                    kb._unresolved_names.add(evidence.lemma)
            kb._active_source = str(source_ids[index]) if source_ids is not None else str(index)
            kb._ingest_tree(
                tree,
                source_text=source_texts[index] if source_texts is not None else None,
                source_claim_ids=source_claim_ids[index] if source_claim_ids is not None else None,
            )
        return kb

    def claim(self, proposition: Proposition) -> ClaimDerivation:
        """Certified lookup or bounded derivation, never a coarse referent match.

        The legacy fragment may derive a new claim only when every query
        referent has an unambiguous alias in this resolution domain. Rich
        context and secondary roles are never erased to make a rule fire.
        """
        key = claim_key(proposition, self._relation_primitives)
        if key.state != "supported" or key.key is None:
            return ClaimDerivation(key.state, None, key.polarity.sign, reason=key.reason)
        if commitment(proposition) != "committed":
            return ClaimDerivation("unsupported", key.key, key.polarity.sign, reason="non_committed_query")
        sources = self._claim_facts.get((key.key, key.polarity.sign), ())
        if sources:
            return ClaimDerivation(
                "entailed",
                key.key,
                key.polarity.sign,
                tuple(sorted(sources)),
                rule_chain=("exact admitted signed claim",),
            )
        if key.polarity.sign != 1:
            return ClaimDerivation("not_entailed", key.key, key.polarity.sign)
        if scope_signature(proposition):
            return ClaimDerivation(
                "unsupported", key.key, key.polarity.sign, reason="contextual_derivation_unsupported"
            )

        def aliases(operand):
            evidence = identity(operand)
            if evidence.state != "resolved":
                return ()
            return tuple(
                sorted(
                    name
                    for name in self._resolved_aliases.get(operand.entity_id, ())
                    if self._resolved_names[name] == {operand.entity_id} and name not in self._unresolved_names
                )
            )

        node, kind = proposition.node, proposition.kind
        derivations = []
        if kind == "Event":
            if getattr(node, "themes", ()):
                return ClaimDerivation("unsupported", key.key, 1, reason="secondary_role_derivation_unsupported")
            agents, patients = aliases(node.agent), aliases(node.patient) if node.patient is not None else (None,)
            if not agents or not patients:
                return ClaimDerivation("not_entailed", key.key, 1, reason="no_unambiguous_prior_referent")
            derivations = [self.event(node.verb, agent, patient) for agent in agents for patient in patients]
        elif kind == "TypeAssertion":
            names = aliases(node.entity)
            if not names:
                return ClaimDerivation("not_entailed", key.key, 1, reason="no_unambiguous_prior_referent")
            base = key.polarity.base
            if base is None:
                return ClaimDerivation("unresolved", key.key, 1, reason="missing_type_base")
            derivations = [self.is_a(name, base) for name in names]
        elif kind == "Comparison":
            left, right = aliases(node.lhs), aliases(node.rhs)
            if not left or not right:
                return ClaimDerivation("not_entailed", key.key, 1, reason="no_unambiguous_prior_referent")
            axis = key.key[1][1]
            derivations = [
                self.greater(a, b, axis) if node.sign == 1 else self.greater(b, a, axis) for a in left for b in right
            ]
        for result in derivations:
            if result.holds:
                return ClaimDerivation("entailed", key.key, 1, result.source_ids, rule_chain=result.chain)
        return ClaimDerivation("not_entailed", key.key, key.polarity.sign)

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
        sources = tuple(
            sorted({source for a, b in zip(chain, chain[1:]) for source in self._isa_sources.get((a, b), ())})
        )
        self._chain_sources[chain] = sources
        return Derivation(bool(chain), "is_a", (x, y), chain, source_ids=sources)

    def greater(self, x: str, y: str, axis: Optional[str] = None) -> Derivation:
        axes: List[Optional[str]] = (
            [axis] if axis is not None else sorted(self._axes, key=lambda a: (a is None, a or ""))
        )
        for ax in axes:
            chain = self._bfs(lambda n: self._gt.get((ax, n), ()), x, y)
            if chain:
                sources = tuple(
                    sorted(
                        {source for a, b in zip(chain, chain[1:]) for source in self._gt_sources.get((ax, a, b), ())}
                    )
                )
                self._chain_sources[chain] = sources
                return Derivation(True, "greater", (x, y), chain, ax, sources)
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
            key = self._event_key(ant)
            if key is None:
                return None
            verb, a, patient = key
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
                        chain = (f"fact: {self._fmt(fv, fa, fp)}", " → ".join(bind.chain))
                        self._chain_sources[chain] = tuple(
                            sorted(set(self._fact_sources[(False, (fv, fa, fp))]) | set(bind.source_ids))
                        )
                        return chain
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
                d = self.greater(hi, lo, axis=getattr(ant, "axis", None))
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
            chain = (f"fact: {pretty}",)
            sources = tuple(sorted(self._fact_sources[(False, query)]))
            self._chain_sources[chain] = sources
            return Derivation(True, "event", (agent, pretty), chain, source_ids=sources)
        seen = _seen | {query}
        for rule_index, (ant, cons) in enumerate(self._rules):
            key = self._event_key(cons)
            if key is None:
                continue
            c_verb, c_agent, c_patient = key
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
            sources = tuple(
                sorted(
                    set(self._chain_sources.get(ant_chain, ()))
                    | set(self._chain_sources.get(bridge, ()))
                    | {self._rule_sources[rule_index]}
                )
            )
            self._chain_sources[chain] = sources
            return Derivation(True, "event", (agent, pretty), chain, source_ids=sources)
        return Derivation(False, "event", (agent, pretty), ())
