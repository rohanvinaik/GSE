"""CassetteDeck — the cross-cassette constraint cascade that assembles the cheat-sheet.

A single cassette resolves what it can confidently; the rest is ambiguous *until the field shrinks*.
So loaded cassettes do not each commit in isolation — their resolutions are arbitrated by a greedy
constraint cascade (the pattern of the archived ``ConstraintCascade``), composing GSE's existing
coherence machinery rather than re-inventing arbitration:

  1. PRIORITY — resolve the most CONVERGENT (``confidence`` = independent agreeing strands) and most
     LOCAL (tight, same-window) resolutions FIRST. (The user's "priority resolution for locality":
     lock the local anchors, then propagate. Mirrors the centering/salience priority the document
     pronoun binder already uses.)
  2. CONSTRAINT PROPAGATION — each commit updates a union-find of merged ids. A later, weaker, or
     ambiguous resolution is re-checked against that state: if the two names it could not separate are
     now the SAME referent (already merged), the ambiguity DISSOLVES and it commits; if its target was
     claimed incompatibly, it is dropped. "Greedy selection for ambiguous terms, leaving the rest
     easier to resolve."
  3. ABSTENTION is preserved end-to-end — a gap no cascade step can decide is left exactly as it was
     (the SSC never-destroy guarantee survives composition).

The committed set is the cheat-sheet: the resolutions that, with the literal GSE pipeline, produce
clean Innerese. Domain-portable: load a different deck of cassettes per domain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base import Cassette, Resolution
from .multiscale import MultiScaleDoc


class _UnionFind:
    """Merged-referent classes — the constraint state a commit grows and a re-check consults."""

    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb           # bias toward b (the NAME side in a merge)

    def same(self, a: str, b: str) -> bool:
        return self.find(a) == self.find(b)


@dataclass
class CheatEntry:
    """One committed cassette resolution — a line of the cheat-sheet, with its full provenance."""
    cassette: str
    kind: str                              # "merge" | "split"
    subject: str                           # the resolved element (description lemma / split id)
    answer: Any                            # name eid (merge) | partition keys (split)
    eid: Optional[str]
    confidence: float
    strands: Dict[str, float] = field(default_factory=dict)
    note: str = ""


@dataclass
class DeckResult:
    entries: List[CheatEntry]
    merges: Dict[str, str]                 # description-eid -> name-eid (the bound identities)
    abstained: List[Resolution]

    def cheat_sheet(self) -> List[dict]:
        return [{"cassette": e.cassette, "kind": e.kind, "subject": e.subject,
                 "answer": e.answer, "eid": e.eid, "confidence": e.confidence,
                 "strands": e.strands, "note": e.note} for e in self.entries]


class CassetteDeck:
    # Convergence floor: a resolution must have ≥ this many independent agreeing strands to commit.
    # A lone signal (one strand) — even the only candidate — is not convergence; the SSC discipline is
    # that ORTHOGONAL readings must agree. Floor = 2: predicative identity PLUS one external corroborator
    # (cross-sentence recency / gender agreement / document centering).
    min_confidence: float = 2.0

    def __init__(self, cassettes: List[Cassette], min_confidence: float = 2.0):
        self.cassettes = cassettes
        self.min_confidence = min_confidence

    def resolve(self, doc: MultiScaleDoc) -> DeckResult:
        # 1. every cassette resolves every gap it finds (committed + abstentions)
        committed: List[Tuple[Cassette, Resolution]] = []
        abstained: List[Resolution] = []
        for cas in self.cassettes:
            for r in cas.run(doc):
                (committed if not r.abstained else abstained).append((cas, r) if not r.abstained else r)

        # 2a. CROSS-CASSETTE CONSTRAINTS — a validator cassette's vetoes gate the resolver cassettes.
        #     A "veto" resolution (e.g. person_validation: this name is non-person) removes its target
        #     from every merge's candidate pool BEFORE arbitration. The composition the brief calls for:
        #     a validator constrains a resolver, so an edge case one cassette can't see another vetoes.
        #     A veto is NOT held to the convergence floor: it only ABSTAINS a merge (never asserts one),
        #     so it errs toward safety — one authoritative non-person signal (WordNet "germanic is a
        #     language") is enough. The cassette already commits a veto only on positive evidence.
        vetoed = {r.committed for cas, r in committed if getattr(r.gap, "kind", None) == "veto"}

        # 2b. PRIORITY order — most convergent, then most local, then strongest margin
        committed.sort(key=lambda cr: (cr[1].confidence, cr[1].locality, cr[1].ranked[0].total
                                       if cr[1].ranked else 0.0), reverse=True)

        uf = _UnionFind()
        merges: Dict[str, str] = {}
        entries: List[CheatEntry] = []

        def commit(cas: Cassette, r: Resolution) -> None:
            g = r.gap
            if getattr(g, "kind", None) == "split":
                entries.append(CheatEntry(cas.name, "split", f"{g.rep.lemma}[{g.eid}]",
                                          sorted(r.committed.keys()), g.eid, r.confidence,
                                          dict(r.ranked[0].strands) if r.ranked else {}, r.note))
                return
            d_eid, n_eid = g.eid, r.committed
            uf.union(d_eid, n_eid)
            merges[d_eid] = uf.find(n_eid)
            entries.append(CheatEntry(cas.name, "merge", f"{g.rep.lemma}[{d_eid}]", n_eid, d_eid,
                                      r.confidence, dict(r.ranked[0].strands) if r.ranked else {}, r.note))

        # 3. GREEDY CASCADE with constraint propagation
        for cas, r in committed:
            g = r.gap
            kind = getattr(g, "kind", None)
            if kind == "veto":
                continue                       # consumed as a constraint in 2a, not a cheat-sheet line
            if r.confidence < self.min_confidence:
                continue                       # below the convergence floor — a lone signal, defer/drop
            if kind == "merge":
                if r.committed in vetoed:
                    continue                   # target vetoed non-person by a validator cassette → drop
                # conflict check: this description already bound to a DIFFERENT referent class → skip
                if g.eid in merges and not uf.same(g.eid, r.committed):
                    continue
            commit(cas, r)

        # 4. RE-RESOLVE the abstained — ambiguity that the cascade has since DISSOLVED.
        #    A merge that abstained over candidates {A, B, ...} now commits IFF those candidates have
        #    become a SINGLE referent class (already merged) — the field shrank, the doubt is gone.
        still_abstained: List[Resolution] = []
        for r in abstained:
            g = getattr(r, "gap", None)
            if getattr(g, "kind", None) == "merge" and r.ranked:
                cands = [s.answer for s in r.ranked if isinstance(s.answer, str)]
                classes = {uf.find(c) for c in cands}
                if len(cands) >= 2 and len(classes) == 1:
                    target = next(iter(classes))
                    uf.union(g.eid, target)
                    merges[g.eid] = uf.find(target)
                    entries.append(CheatEntry(g.cassette if hasattr(g, "cassette") else "deck",
                                              "merge", f"{g.rep.lemma}[{g.eid}]", target, g.eid,
                                              r.confidence, {}, "dissolved: candidates already merged"))
                    continue
            still_abstained.append(r)

        return DeckResult(entries, merges, still_abstained)
