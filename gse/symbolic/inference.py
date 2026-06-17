"""
Deterministic logical inference over the clause graph — transitive closure.

Solves the transitivity / ordering class of logical-reasoning problems — the
"zorble/florp" / LSAT linear-ordering & type-hierarchy class. From a document's
resolved clause graphs it collects **is-a** edges (from ``TypeAssertion``) and
**ordering** edges (from ``Comparison``), then answers queries by breadth-first
search over the transitive closure — returning the **derivation chain**, and
refusing the unentailed direction (no false positives).

Everything here is integer/set graph work — deterministic by construction.

**Boundary (honest):** transitive/subset reasoning only. "all X are Y" and "a X
is a Y" collapse to the same is-a edge — sound for the syllogism, but there is
no quantifier scope, no conditionals, no grouping. This is the linear-ordering /
type-chain fragment of logical reasoning, not all of it.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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
    relation: str               # "is_a" | "greater"
    query: Tuple[str, str]      # (x, y)
    chain: Tuple[str, ...]      # the derivation path; () when not entailed
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

    @classmethod
    def from_trees(cls, trees: Sequence[Any]) -> "KnowledgeBase":
        kb = cls()
        for tree in trees:
            for p in predicates(tree):
                name = type(p).__name__
                if name == "TypeAssertion":
                    x, y = _lemma(p.entity), _lemma(p.kind)
                    if x and y:
                        kb._isa[x].add(y)
                elif name == "Comparison":
                    x, y = _lemma(p.lhs), _lemma(p.rhs)
                    if x and y:
                        axis = getattr(p, "axis", None)
                        hi, lo = (x, y) if p.sign >= 0 else (y, x)
                        kb._gt[(axis, hi)].add(lo)
                        kb._axes.add(axis)
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
            [axis] if axis is not None
            else sorted(self._axes, key=lambda a: (a is None, a or ""))
        )
        for ax in axes:
            chain = self._bfs(lambda n: self._gt.get((ax, n), ()), x, y)
            if chain:
                return Derivation(True, "greater", (x, y), chain, ax)
        return Derivation(False, "greater", (x, y), (), axis)
