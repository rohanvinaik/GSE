"""Inheritance across readings: typed edges, defaults, suspensions and the joint round (design E8).

Rohan, 2026-11-26 19:38: sub-kinds are "the *easiest* tier"; the build propagates "rules that define how banks are
implicitly decided and filled by other sources of information, like other banks"; WordNet is not the gold standard,
only a jump-start ("I've told you repeatedly not to focus on WordNet as if its the gold standard"). 19:42:
"TrialLedger's constraint propogation ideas are how we allow sub-kind inheritcance without introducing spurious and
incorrect additions". TrialLedger: "Interpolated is a declared default or a conclusion resting on interpolation";
"Defaults have declared applicability and defeaters; conflicting defaults are suspended and reported, not selected by
order."

Nodes. A node is one unit of meaning, here a WordNet synset; its members are the cohort's readings of it, one per
lemma. A synset with no cohort reading is still a node, a transit node holding no value of its own, so a chain
through it is not cut (`animal.n.01` reaches 4,016 synsets, of which 1,881 have cohort readings).

Families and what they carry. Every edge runs from the node whose value is carried to the node that receives it, and
belongs to a family that declares the states it carries.

- `hypernym`, `instance_hypernym` (kind-of), from the hypernym to the hyponym or instance. Carries +1, -1 and 0.
  Warrant: NSM's molecules, "X [m] of one kind": a kind of X is an X, so a component X's definition has (+1 or -1)
  the kind has, and what X's definition explicitly excludes (0, F118: "0 is explicit absence") the kind excludes.
  The lead's ruling of 2026-11-27 accepts the zeros: a hub's orthogonality is definitional for its kinds (it
  supersedes the earlier build's "zeros are not inherited", commit 559bfe6). X's SILENT is never carried: a kind may
  use a prime its hub never mentions. NSM's own subkind explications refute silence inheritance: 10 of 11 subkinds
  use primes their hub never uses (`docs/verification/2026-11-26-hub-silence-vs-nsm-subkinds.json`).
- `similar_to`, from an adjective head (pos `a`) to its satellite (pos `s`), never the reverse (nltk lists the link
  from both ends). Carries +1, -1 and 0. Warrant: WordNet's adjective cluster, in which a satellite is similar in
  meaning to its head and refines it (`wet.a.01` -> `damp.s.01`), the adjective analogue of kind-of; the head's
  silence is not carried, for the same reason as a hub's.
- `entails`, from the entailed verb to the entailing one (`sleep.v.01` -> `snore.v.01`). Carries +1 and -1.
  Warrant: WordNet's entailment, in which X cannot be done unless Y is or has been done, by the same subject, so Y's
  components are part of X's own meaning. Y's zeros are not carried, since X adds to Y and can add what Y excludes,
  and Y's silence is not either.
- `causes`, from the effect to the causing verb (`die.v.01` -> `kill.v.01`). Carries the effect's +1 and -1, on
  every bank but CAUSE. Warrant: `native_predicate_policy.lexical_component` (`bank_laws.json`, founder-approved)
  counts an event's effect on another participant as part of the word's content ("A negative state for another
  participant or stage does not assert that the word definition lacks the relation"), which is how kill has ALIVE
  -1 from VerbNet (the lead's ruling of 2026-11-27, superseding this family's earlier empty carry). No authored
  contract lets WordNet write CAUSE, so the link itself writes none. The effect's zeros and silence are not
  carried: the causer adds its own action to the effect.
- synonymy: the same synset under different lemmas is one definition, equality of meaning, so it carries every
  state, SILENT included. It is the node itself: its members' masks are intersected.

Defaults. A node emits its own value where its mask is decided (the kind's own value is what its kinds inherit);
elsewhere it passes on the proposals reaching it that are still legal for it. Proposals are ORed over every incoming
edge to a fixed point. This is monotone, so it terminates on cycles (`breathe.v.01` entails `inhale.v.02`, which is a
kind of it) and involves no order. A proposal applies to a node's readings only when exactly one state reaches the
cell, it is legal under the known state, and it fits the current state. Otherwise it is suspended and reported:

- `defaults disagree`: two states reach one cell, at any depth; nothing is chosen;
- `contradicts known`: the one state reaching the cell is not legal under the known state, which stands;
- `joint conflict`: defaults that are each legal under the known state are not legal together: a state that fits
  the known state but not what interpolation already made of the node, an empty cell the known layer does not have,
  an obligation the known layer satisfies and the interpolated layer does not, or a consequence of other defaults
  that removes one of two disagreeing states. Every default that landed on the nodes involved is suspended and the
  round is replayed from the known state;
- `synonyms disagree`: the known states of one synset's readings have no state in common; they are not equalized.

Known and interpolated. The known state is the closure of the premises under the laws and the obligations. The
interpolated state is the known state plus defaults, closed again. Removal is monotone, so every cell the
interpolated state holds narrower than the known state rests on at least one default: those cells are the
interpolated ones (`Settlement.interpolated`), and the cells a default or a synonym narrowed directly are
`Settlement.inherited`.

Defeaters. A declared source misfiling carries nothing: a link (child, parent) in any family, or an origin from which
nothing carries (its own values and what would pass through it). The list starts empty; candidates come from the
NSM audit and are decided by review.

Lineage. Every carried value records its origin, the node where it was decided without a carried default (a
stated value, a synonym's, or a consequence of the laws), with the parent and edge family of its last hop
(`Settlement.lineage`), so a retraction or the audit can walk it back.

The audit (`audit_against_nsm`). The verb hierarchy's cells stay interpolated and are audited against NSM (F148:
the tail is the disagreement with NSM by word, bank and rule). An explication is the complete meaning of its sense,
so a carried +1 or -1 on a bank the explication neither mentions nor reaches through its molecules disagrees with
it. Each disagreement names the link through which the value entered the chain of kinds leading to the explicated
sense, as a candidate defeater with the NSM record (source key and line range) as its warrant. Nothing is defeated
automatically.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cached_property
from urllib.parse import unquote

import numpy as np

from . import obligations as ob
from .cells import ALL, BANKS, BIT_NAMES, NEG, POS, SILENT, ZERO, State
from .closure import close

KIND_OF = POS | NEG | ZERO
CONTENT = POS | NEG
_POPCOUNT = np.array([bin(i).count("1") for i in range(16)], dtype=np.uint8)
_WIDTH = len(BANKS)


@dataclass(frozen=True)
class Family:
    """An edge family: the states it carries from the giving node to the receiving one, the banks it never writes,
    and its warrant."""

    name: str
    carries: int
    warrant: str
    never_writes: frozenset[str] = frozenset()

    def carry_row(self) -> np.ndarray:
        """The states it carries on each bank."""
        return np.array([0 if bank in self.never_writes else self.carries for bank in BANKS], dtype=np.uint8)


FAMILIES: tuple[Family, ...] = (
    Family("hypernym", KIND_OF, "kind-of: NSM 'X [m] of one kind'; a hub's silence is refuted (module docstring)"),
    Family("instance_hypernym", KIND_OF, "kind-of: an instance of X is an X (module docstring)"),
    Family("similar_to", KIND_OF, "WordNet adjective cluster: a satellite refines its head (module docstring)"),
    Family("entails", CONTENT, "WordNet entailment: same subject, the entailed event is part (module docstring)"),
    Family(
        "causes",
        CONTENT,
        "native_predicate_policy.lexical_component: the effect on another participant is content (module docstring)",
        frozenset({"CAUSE"}),
    ),
)
SYNONYMY = Family("synonymy", ALL, "one synset, one definition: equality of meaning (module docstring)")


@dataclass(frozen=True)
class Defeater:
    """A declared source misfiling and its reason.

    With `child`, the link from `parent` to `child` carries nothing, in any family. Without it, `parent` is an origin
    that is no genus for its kinds: nothing carries out of it, neither its own values nor what would pass through it.
    """

    parent: str
    reason: str
    child: str | None = None


DEFEATERS: tuple[Defeater, ...] = ()

DISAGREE, KNOWN, JOINT, SYNONYMS = 1, 2, 4, 8
REASONS = {
    DISAGREE: "defaults disagree",
    KNOWN: "contradicts known",
    JOINT: "joint conflict",
    SYNONYMS: "synonyms disagree",
}


def reason_names(code: int) -> list[str]:
    return [name for bit, name in REASONS.items() if code & bit]


def state_names(mask: int) -> list[str]:
    return [name for bit, name in BIT_NAMES.items() if mask & bit]


# ---------------------------------------------------------------------------------------------------- the graph


def _span(keys: np.ndarray, starts: np.ndarray, total: int, key: int) -> slice:
    """The slice of a sorted, grouped array that belongs to `key` (empty when the key has no group)."""
    i = int(np.searchsorted(keys, key))
    if i == keys.size or keys[i] != key:
        return slice(0, 0)
    return slice(int(starts[i]), int(starts[i + 1]) if i + 1 < keys.size else total)


@dataclass(frozen=True)
class Graph:
    """Nodes with their member readings, and typed edges between nodes, as arrays."""

    keys: tuple[str, ...]
    rows: np.ndarray  # member reading rows, grouped by node
    node_of: np.ndarray  # the node of each member, non-decreasing
    owned: np.ndarray  # the nodes with at least one member
    starts: np.ndarray  # the first member of each owned node
    src: np.ndarray  # edges, sorted by receiving node
    dst: np.ndarray
    family: np.ndarray
    targets: np.ndarray  # the nodes with incoming edges
    edge_starts: np.ndarray  # the first edge of each target
    carries: np.ndarray  # (edges, banks) the states each edge carries on each bank
    families: tuple[Family, ...]
    defeated: tuple[tuple[str, str, str, str], ...] = field(default=())  # (family, parent, child, reason)

    def node_masks(self, masks: np.ndarray) -> np.ndarray:
        """Each node's mask: the intersection of its members' masks; ALL for a transit node."""
        out = np.full((len(self.keys), _WIDTH), ALL, dtype=np.uint8)
        if self.rows.size:
            out[self.owned] = np.bitwise_and.reduceat(masks[self.rows], self.starts, axis=0)
        return out

    def node_any(self, flags: np.ndarray) -> np.ndarray:
        """Per node and bank: whether any member reading's flag is set (`flags` is readings x banks)."""
        return self.member_any(flags[self.rows])

    def member_any(self, flags: np.ndarray) -> np.ndarray:
        """Per node and bank: whether any member's flag is set (`flags` is members x banks, in member order)."""
        out = np.zeros((len(self.keys), _WIDTH), dtype=bool)
        if self.rows.size:
            out[self.owned] = np.bitwise_or.reduceat(flags.astype(np.uint8), self.starts, axis=0) > 0
        return out

    def members(self, node: int) -> np.ndarray:
        """The member reading rows of `node` (none for a transit node)."""
        return self.rows[_span(self.owned, self.starts, self.rows.size, node)]

    def incoming(self, node: int) -> np.ndarray:
        """The edges into `node`."""
        return np.arange(*_span(self.targets, self.edge_starts, self.dst.size, node).indices(self.dst.size))

    def counts(self) -> dict:
        """Links per family (all, and with both ends owning readings), reading pairs, nodes and synonym groups."""
        owned = np.zeros(len(self.keys), dtype=bool)
        owned[self.owned] = True
        size = np.zeros(len(self.keys), dtype=np.int64)
        np.add.at(size, self.node_of, 1)
        out = {}
        for i, fam in enumerate(self.families):
            sel = self.family == i
            both = sel & owned[self.src] & owned[self.dst]
            out[fam.name] = {
                "links": int(sel.sum()),
                "links_between_readings": int(both.sum()),
                "reading_pairs": int((size[self.src[both]] * size[self.dst[both]]).sum()),
                "carries": state_names(fam.carries),
                "never_writes": sorted(fam.never_writes),
            }
        groups = size[size >= 2]
        out[SYNONYMY.name] = {
            "synsets_with_two_or_more_readings": int(groups.size),
            "reading_pairs": int((groups * (groups - 1) // 2).sum()),
            "carries": state_names(SYNONYMY.carries),
        }
        out["nodes"] = {"all": len(self.keys), "owning_readings": int(owned.sum()), "transit": int((~owned).sum())}
        out["defeated_links"] = len(self.defeated)
        return out


def _defeat(links, defeaters):
    pairs = {(d.parent, d.child): d for d in defeaters if d.child is not None}
    origins = {d.parent: d for d in defeaters if d.child is None}
    kept, gone, used = [], [], set()
    for link in links:
        family, parent, child = link
        d = pairs.get((parent, child)) or origins.get(parent)
        if d is None:
            kept.append(link)
        else:
            used.add(d)
            gone.append((family, parent, child, d.reason))
    unused = [d for d in defeaters if d not in used]
    if unused:
        raise ValueError(f"DEFEATER_MATCHES_NO_LINK {unused}")
    return kept, gone


def build(groups: dict[str, list[int]], links, defeaters=DEFEATERS, families=FAMILIES) -> Graph:
    """The graph over `groups` (node key -> member reading rows) and `links` ((family, parent, child) node keys).

    Nodes named only by links are transit nodes. A defeater that matches no link is refused.
    """
    index = {f.name: i for i, f in enumerate(families)}
    links = list(dict.fromkeys(tuple(link) for link in links))
    unknown = {family for family, _, _ in links} - set(index)
    if unknown:
        raise ValueError(f"UNKNOWN_FAMILIES {sorted(unknown)}")
    kept, gone = _defeat(links, defeaters)
    keys = tuple(sorted(set(groups) | {p for _, p, _ in kept} | {c for _, _, c in kept}))
    node = {k: i for i, k in enumerate(keys)}
    owned = sorted(node[k] for k, rows in groups.items() if len(rows))
    member_rows = [np.unique(np.asarray(groups[keys[v]], dtype=np.int64)) for v in owned]
    sizes = np.array([m.size for m in member_rows], dtype=np.int64)
    rows = np.concatenate(member_rows) if member_rows else np.zeros(0, dtype=np.int64)
    if np.unique(rows).size != rows.size:
        raise ValueError("READING_IN_TWO_NODES")
    src = np.array([node[p] for _, p, _ in kept], dtype=np.int64)
    dst = np.array([node[c] for _, _, c in kept], dtype=np.int64)
    fam = np.array([index[f] for f, _, _ in kept], dtype=np.int8)
    order = np.argsort(dst, kind="stable")
    src, dst, fam = src[order], dst[order], fam[order]
    targets, edge_starts = np.unique(dst, return_index=True)
    rules = np.stack([f.carry_row() for f in families]) if families else np.zeros((0, _WIDTH), np.uint8)
    carries = rules[fam] if fam.size else np.zeros((0, _WIDTH), np.uint8)
    return Graph(
        keys=keys,
        rows=rows,
        node_of=np.repeat(np.array(owned, dtype=np.int64), sizes),
        owned=np.array(owned, dtype=np.int64),
        starts=np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64) if sizes.size else sizes,
        src=src,
        dst=dst,
        family=fam,
        targets=targets,
        edge_starts=edge_starts,
        carries=carries,
        families=tuple(families),
        defeated=tuple(gone),
    )


def wordnet_groups(readings) -> dict[str, list[int]]:
    """Synset -> rows of the cohort's WordNet readings (`wordnet:<quote(lemma)>:<quote(synset)>`)."""
    out: dict[str, list[int]] = defaultdict(list)
    for row, reading in enumerate(readings):
        rid = reading if isinstance(reading, str) else reading.reading_id
        if rid.startswith("wordnet:"):
            out[unquote(rid.rsplit(":", 1)[1])].append(row)
    return dict(out)


def wordnet_links(wn=None):
    """WordNet's own links, as (family, giving synset, receiving synset), over every synset (nltk, WordNet 3.0)."""
    if wn is None:
        from nltk.corpus import wordnet as wn
    for synset in wn.all_synsets():
        name = synset.name()
        for h in synset.hypernyms():
            yield ("hypernym", h.name(), name)
        for h in synset.instance_hypernyms():
            yield ("instance_hypernym", h.name(), name)
        if synset.pos() == "s":
            for head in synset.similar_tos():
                if head.pos() == "a":
                    yield ("similar_to", head.name(), name)
        for entailed in synset.entailments():
            yield ("entails", entailed.name(), name)
        for effect in synset.causes():
            yield ("causes", effect.name(), name)


# ------------------------------------------------------------------------------------------------ one pass


@dataclass(frozen=True)
class Carry:
    """One inheritance pass: the reading cells it narrowed, and per node and bank what landed and what was
    suspended."""

    rows: np.ndarray
    cols: np.ndarray
    old: np.ndarray
    new: np.ndarray
    landed: np.ndarray  # (nodes, banks) a default narrowed the node's readings
    equalized: np.ndarray  # (nodes, banks) synonymy narrowed one of the node's readings
    suspended: np.ndarray  # (nodes, banks) reason bits
    proposals: np.ndarray  # (nodes, banks) the states that reached each node

    @property
    def changed(self) -> int:
        return int(self.rows.size)


def emissions(node_masks: np.ndarray, proposals: np.ndarray) -> np.ndarray:
    """What each node gives its receivers: its own value where decided, else the proposals still legal for it."""
    return np.where(_POPCOUNT[node_masks] == 1, node_masks, proposals & node_masks)


def proposals(graph: Graph, node_masks: np.ndarray) -> np.ndarray:
    """The OR, over every incoming edge, of the states carried to each node, to a fixed point."""
    p = np.zeros_like(node_masks)
    if graph.src.size == 0:
        return p
    carries = graph.carries
    while True:
        given = emissions(node_masks, p)[graph.src] & carries
        incoming = np.bitwise_or.reduceat(given, graph.edge_starts, axis=0)
        if (incoming == p[graph.targets]).all():
            return p
        p[graph.targets] = incoming


def carry(state: State, graph: Graph, known: State | None = None, held=None, held_equal=None) -> Carry:
    """Run one inheritance pass on `state` in place and return what changed.

    `known` is the known layer the defaults are checked against (the state itself when omitted). `held` and
    `held_equal` (nodes x banks) are cells where defaults, or synonym equality, are suspended.
    """
    known = state if known is None else known
    shape = (len(graph.keys), _WIDTH)
    held = np.zeros(shape, dtype=bool) if held is None else held
    held_equal = np.zeros(shape, dtype=bool) if held_equal is None else held_equal
    current = graph.node_masks(state.masks)
    known_nodes = graph.node_masks(known.masks)
    known_broken = graph.node_any(known.masks == 0)
    p = proposals(graph, current)
    owned = np.zeros(shape[0], dtype=bool)
    owned[graph.owned] = True
    reaching = owned[:, None] & (p != 0) & ~known_broken
    count = _POPCOUNT[p]
    disagree = reaching & (count >= 2)
    single = reaching & (count == 1)
    against_known = single & ((p & known_nodes) == 0)
    joint = single & ~against_known & ((p & current) == 0)
    applies = single & ~against_known & ~joint & ~held
    synonyms = owned[:, None] & (known_nodes == 0) & ~known_broken
    suspended = (
        np.where(disagree, DISAGREE, 0)
        | np.where(against_known & ~synonyms, KNOWN, 0)
        | np.where(joint, JOINT, 0)
        | np.where(synonyms, SYNONYMS, 0)
    ).astype(np.uint8)
    target = np.where(applies, current & p, current)
    equal_ok = ~held_equal & (target != 0)

    of = graph.node_of
    before = state.masks[graph.rows]
    by_default = np.where(applies[of], p[of], ALL)
    by_synonym = np.where(equal_ok[of], target[of], ALL)
    after = before & by_default & by_synonym
    r, c = np.nonzero(after != before)
    rows = graph.rows[r]
    state.masks[rows, c] = after[r, c]
    return Carry(
        rows=rows,
        cols=c,
        old=before[r, c],
        new=after[r, c],
        landed=applies & ((current & p) != current),
        equalized=graph.member_any((before & by_synonym) != before),
        suspended=suspended,
        proposals=p,
    )


# ------------------------------------------------------------------------------------------------- lineage

SYNONYM_HOP = -1  # the family code of a value a reading takes from its own synset


@dataclass(frozen=True)
class Lineage:
    """Where each carried value came from: one entry per (node, bank, origin) on a carrying path, with the parent and
    edge family of its last hop, and the first node and family after the origin, on a shortest path.

    An origin is a node cell decided without a carried default landing on it: a stated value, a synonym's, or a
    consequence of the laws. Entries also cover transit and suspended nodes a value passes through, so every path
    can be walked back to its origin.
    """

    node: np.ndarray
    bank: np.ndarray
    origin: np.ndarray
    parent: np.ndarray
    family: np.ndarray
    first: np.ndarray
    first_family: np.ndarray
    value: np.ndarray
    width: int  # the number of nodes, for the entry keys

    def keys(self, node, bank, origin) -> np.ndarray:
        return (np.asarray(node, dtype=np.int64) * _WIDTH + bank) * self.width + origin

    @cached_property
    def _index(self) -> dict[int, int]:
        return {int(k): j for j, k in enumerate(self.keys(self.node, self.bank, self.origin))}

    def path(self, i: int) -> list[int]:
        """The entries from the origin's first hop down to entry `i`."""
        out = [i]
        while self.parent[out[-1]] != self.origin[out[-1]]:
            j = out[-1]
            out.append(self._index[int(self.keys(self.parent[j], self.bank[j], self.origin[j]))])
        return out[::-1]


def _lineage(graph: Graph, node_masks: np.ndarray, proposals_: np.ndarray, landed: np.ndarray) -> Lineage:
    """Walk every decided value forward along the edges that carry it, level by level from its origin."""
    n = len(graph.keys)
    given = emissions(node_masks, proposals_)
    origin_cell = (_POPCOUNT[node_masks] == 1) & ~landed
    order = np.argsort(graph.src, kind="stable")
    start = np.searchsorted(graph.src[order], np.arange(n + 1))
    u, b = np.nonzero(origin_cell)
    o, value = u.copy(), node_masks[u, b]
    first = np.full(u.size, -1, dtype=np.int64)
    first_family = np.full(u.size, -1, dtype=np.int64)
    parts, seen = [], np.zeros(0, dtype=np.int64)
    while u.size:
        degree = start[u + 1] - start[u]
        rep = np.repeat(np.arange(u.size), degree)
        offset = np.arange(rep.size) - np.repeat(np.cumsum(degree) - degree, degree)
        e = order[start[u][rep] + offset]
        w, bb, vv = graph.dst[e], b[rep], value[rep]
        ok = ((graph.carries[e, bb] & vv) != 0) & ((given[w, bb] & vv) != 0) & ~origin_cell[w, bb]
        keys = (w * _WIDTH + bb) * n + o[rep]
        idx = np.flatnonzero(ok)
        _, firsts = np.unique(keys[idx], return_index=True)
        idx = idx[firsts]
        idx = idx[~np.isin(keys[idx], seen)]
        seen = np.concatenate([seen, keys[idx]])
        fam = graph.family[e[idx]].astype(np.int64)
        f0 = first[rep[idx]]
        new_first = np.where(f0 < 0, w[idx], f0)
        new_first_family = np.where(f0 < 0, fam, first_family[rep[idx]])
        parts.append((w[idx], bb[idx], o[rep[idx]], u[rep[idx]], fam, new_first, new_first_family, vv[idx]))
        u, b, o, value = w[idx], bb[idx], o[rep[idx]], vv[idx]
        first, first_family = new_first, new_first_family
    cols = [np.concatenate(c) if parts else np.zeros(0, dtype=np.int64) for c in zip(*parts)] if parts else []
    if not cols:
        cols = [np.zeros(0, dtype=np.int64)] * 8
    return Lineage(*cols, width=n)


# ------------------------------------------------------------------------------------------- the joint round


@dataclass
class Settlement:
    """The joint round's result: the known layer, the interpolated layer, and every suspension with its reason."""

    known: State
    state: State
    graph: Graph
    inherited: np.ndarray  # readings x banks: a default or a synonym narrowed the cell directly
    reasons: np.ndarray  # nodes x banks: reason bits of every suspension reported in any round
    held: np.ndarray  # nodes x banks: defaults suspended
    held_equal: np.ndarray  # nodes x banks: synonym equality suspended
    proposals: np.ndarray  # nodes x banks: the states reaching each node in the final round
    known_conflicts: list[dict]  # obligation conflicts in the known layer
    interpolated_conflicts: list[dict]  # obligation conflicts in the final interpolated layer
    known_scopes: dict  # guard scopes with the facts located in the known layer
    scopes: dict  # guard scopes with the facts located in the interpolated layer too
    landed: np.ndarray  # nodes x banks: a default landed on the node in the final round
    lineage: Lineage  # where every carried value came from
    receipt: dict

    @property
    def interpolated(self) -> np.ndarray:
        """Readings x banks: cells narrower than the known layer, which therefore rest on a default."""
        return self.state.masks != self.known.masks

    def origins(self) -> dict[str, np.ndarray]:
        """Arrays parallel to the inherited reading cells, one entry per origin: the reading row and bank, the origin
        node, the parent node and family of the last hop (`SYNONYM_HOP` and the reading's own node when the value
        comes from its own synset), and the first node and family after the origin."""
        g, lin = self.graph, self.lineage
        node_of_row = np.full(len(self.state.readings), -1, dtype=np.int64)
        node_of_row[g.rows] = g.node_of
        rows, cols = np.nonzero(self.inherited & self.interpolated)
        nodes = node_of_row[rows]
        landed = self.landed
        own = ~landed[nodes, cols]
        cell_keys = nodes * _WIDTH + cols
        entry_cells = lin.node * _WIDTH + lin.bank
        order = np.argsort(entry_cells, kind="stable")
        lo = np.searchsorted(entry_cells[order], cell_keys[~own])
        hi = np.searchsorted(entry_cells[order], cell_keys[~own], side="right")
        count = hi - lo
        cell = np.repeat(np.flatnonzero(~own), count)
        entry = order[np.repeat(lo, count) + (np.arange(count.sum()) - np.repeat(np.cumsum(count) - count, count))]
        syn = np.flatnonzero(own)
        idx = np.concatenate([cell, syn])
        return {
            "rows": rows[idx],
            "cols": cols[idx],
            "origin": np.concatenate([lin.origin[entry], nodes[syn]]),
            "parent": np.concatenate([lin.parent[entry], nodes[syn]]),
            "family": np.concatenate([lin.family[entry], np.full(syn.size, SYNONYM_HOP)]),
            "first": np.concatenate([lin.first[entry], nodes[syn]]),
            "first_family": np.concatenate([lin.first_family[entry], np.full(syn.size, SYNONYM_HOP)]),
            "entry": np.concatenate([entry, np.full(syn.size, -1)]),
        }

    def suspensions(self) -> list[dict]:
        """Every suspended node cell: its reasons, the states reaching it, its known states, its readings, and the
        edges that gave each state."""
        g = self.graph
        given = emissions(g.node_masks(self.state.masks), self.proposals)
        known_nodes = g.node_masks(self.known.masks)
        names = [f.name for f in g.families]
        out = []
        for v, b in zip(*np.nonzero(self.reasons)):
            incoming = g.incoming(v)
            givers = [
                {"family": names[g.family[e]], "from": g.keys[g.src[e]], "states": state_names(int(s))}
                for e in incoming
                if (s := int(given[g.src[e], b] & g.carries[e, b]))
            ]
            out.append(
                {
                    "node": g.keys[v],
                    "bank": BANKS[b],
                    "reasons": reason_names(int(self.reasons[v, b])),
                    "reaching": state_names(int(self.proposals[v, b])),
                    "known": state_names(int(known_nodes[v, b])),
                    "readings": [self.state.readings[r] for r in g.members(v)],
                    "givers": givers,
                }
            )
        return out


def _close_known(state: State, relations, scopes: dict, batch: ob.Batch):
    """Close the known layer in place: laws, then obligations, waking the laws on the facts they locate."""
    closures = sweeps = forced = woken = 0
    last = None
    while True:
        close(state, relations, scopes)
        closures += 1
        if not len(batch):
            break
        last = ob.force(state, batch)
        sweeps += 1
        forced += last.changed
        added = ob.wake(scopes, last.facts)
        woken += added
        if last.changed == 0 and added == 0:
            break
    return {"closures": closures, "sweeps": sweeps, "forced": forced, "facts_woken": woken}, last


def _culprits(graph, batch, current, known, found, forced, new_conflicts, node_of_row) -> np.ndarray:
    """The nodes whose landed defaults a joint conflict rests on.

    A joint conflict is a carried state that fits the known layer but not what interpolation already made of the
    node, an empty cell the known layer does not have, or an obligation the known layer satisfies and the
    interpolated layer does not. Interpolation reaches a reading only by a default landing on its node, or by an
    obligation forcing it from interpolated exclusions, so the culprits are the nodes of those readings and,
    through each forcing or located fact, the nodes of the readings of the forcing group.
    """
    nodes = set(np.flatnonzero((found & JOINT).any(axis=1)).tolist())
    rows = set(np.flatnonzero(((current.masks == 0) & (known.masks != 0)).any(axis=1)).tolist())
    for i in new_conflicts:
        rows.update(batch.members(i).tolist())
    f_rows = np.concatenate([r for r, _ in forced]) if forced else np.zeros(0, dtype=np.int64)
    f_by = np.concatenate([b for _, b in forced]) if forced else np.zeros(0, dtype=np.int64)
    frontier, seen_groups = rows, set()
    while frontier and f_rows.size:
        groups = set(batch.group[np.unique(f_by[np.isin(f_rows, list(frontier))])].tolist()) - seen_groups
        seen_groups |= groups
        members = np.isin(batch.owner, np.flatnonzero(np.isin(batch.group, list(groups))))
        reached = set(batch.rows[members].tolist()) - rows
        rows |= reached
        frontier = reached
    row_nodes = node_of_row[list(rows)] if rows else np.zeros(0, dtype=np.int64)
    nodes.update(row_nodes[row_nodes >= 0].tolist())
    return np.array(sorted(nodes), dtype=np.int64)


def settle(state: State, graph: Graph, relations=(), scopes=None, obligations: ob.Batch | None = None) -> Settlement:
    """The joint round, leaving `state` untouched.

    The known layer is `state` closed under `relations` and forced by `obligations`, repeated until neither
    changes; the facts a located obligation makes true join the guard `scopes` (`obligations.wake`), which wakes the
    laws they select. The interpolated layer starts from it: defaults carry (`carry`), the laws narrow
    (`closure.close`), the obligations force and wake, and defaults carry again, until nothing changes. Facts located
    in the interpolated layer join only its own copy of the scopes. `scopes` itself is not modified. A suspension that
    retracts something already landed (two states now reach a cell a default narrowed, or a joint conflict) holds
    the defaults it names and the interpolated layer is replayed from the known layer. Holds only grow, so the
    replay ends; the final replay has no new conflict, and its result is the fixed point of monotone operators,
    which no order of edges or relations changes.
    """
    started = time.perf_counter()
    relations = tuple(relations)
    batch = obligations if obligations is not None else ob.Batch.of(())
    known = state.copy()
    known_scopes = {name: mask.copy() for name, mask in (scopes or {}).items()}
    known_receipt, known_forcing = _close_known(known, relations, known_scopes, batch)
    known_conflicts = set(known_forcing.conflicts.tolist()) if known_forcing is not None else set()
    shape = (len(graph.keys), _WIDTH)
    held = np.zeros(shape, dtype=bool)
    held_equal = np.zeros(shape, dtype=bool)
    reasons = np.zeros(shape, dtype=np.uint8)
    node_of_row = np.full(len(state.readings), -1, dtype=np.int64)
    node_of_row[graph.rows] = graph.node_of
    rounds = []
    unattributed = False
    while True:
        current = known.copy()
        round_scopes = {name: mask.copy() for name, mask in known_scopes.items()}
        landed = np.zeros(shape, dtype=bool)
        equalized = np.zeros(shape, dtype=bool)
        found = np.zeros(shape, dtype=np.uint8)
        inherited = np.zeros(current.masks.shape, dtype=bool)
        forced, last, passes = [], None, 0
        while True:
            step = carry(current, graph, known=known, held=held, held_equal=held_equal)
            passes += 1
            landed |= step.landed
            equalized |= step.equalized
            found |= step.suspended
            inherited[step.rows, step.cols] = True
            changed = step.changed + close(current, relations, round_scopes)["removals"]
            if len(batch):
                last = ob.force(current, batch)
                forced.append(
                    (np.concatenate([last.rows, last.located_rows]), np.concatenate([last.by, last.located_by]))
                )
                changed += last.changed + ob.wake(round_scopes, last.facts)
            if changed == 0:
                break
        # Interpolation must not choose between defaults that disagree: where a consequence of other defaults has
        # removed one of them although the known layer allows it, those defaults are suspended too. (A disagreeing
        # cell that a default had already narrowed is retracted by its own hold and the replay.)
        p = step.proposals
        removed = (p & graph.node_masks(known.masks)) != (p & graph.node_masks(current.masks))
        found[removed & (_POPCOUNT[p] >= 2) & ~landed] |= JOINT
        new_conflicts = sorted(set(last.conflicts.tolist()) - known_conflicts) if last is not None else []
        culprit = np.zeros(shape[0], dtype=bool)
        culprit[_culprits(graph, batch, current, known, found, forced, new_conflicts, node_of_row)] = True
        disagree = ((found & DISAGREE) != 0) & ~held
        grow = (disagree | ((found & JOINT) != 0) | (landed & culprit[:, None])) & ~held
        grow_equal = equalized & culprit[:, None] & ~held_equal
        reasons |= found
        reasons[landed & culprit[:, None]] |= JOINT
        held |= grow
        held_equal |= grow_equal
        replay = bool((disagree & landed).any() or culprit.any())
        rounds.append(
            {
                "passes": passes,
                "landed": int(landed.sum()),
                "held_added": int(grow.sum()),
                "held_equal_added": int(grow_equal.sum()),
                "culprit_nodes": int(culprit.sum()),
                "replay": replay,
            }
        )
        if not replay:
            break
        if not (grow.any() or grow_equal.any()):
            unattributed = True
            break
    settlement = Settlement(
        known=known,
        state=current,
        graph=graph,
        inherited=inherited,
        reasons=reasons,
        held=held,
        held_equal=held_equal,
        proposals=step.proposals,
        landed=landed,
        lineage=_lineage(graph, graph.node_masks(current.masks), step.proposals, landed),
        known_conflicts=known_forcing.described(batch, known) if known_forcing is not None else [],
        interpolated_conflicts=last.described(batch, current) if last is not None else [],
        known_scopes=known_scopes,
        scopes=round_scopes,
        receipt={},
    )
    interpolated = settlement.interpolated
    settlement.receipt.update(
        {
            "rounds": rounds,
            "known": known_receipt,
            "interpolated_cells": int(interpolated.sum()),
            "inherited_cells": int((inherited & interpolated).sum()),
            "consequence_cells": int((interpolated & ~inherited).sum()),
            "suspended_cells": {name: int(((reasons & bit) != 0).sum()) for bit, name in REASONS.items()},
            "facts_located": {
                "known": sum(int((known_scopes[k] & ~(scopes or {})[k]).sum()) for k in known_scopes),
                "interpolated": sum(int((round_scopes[k] & ~known_scopes[k]).sum()) for k in known_scopes),
            },
            "held": int(held.sum()),
            "held_equal": int(held_equal.sum()),
            "unattributed_conflict": unattributed,
            "bits": {"known": known.bits(), "interpolated": current.bits()},
            "seconds": round(time.perf_counter() - started, 3),
        }
    )
    return settlement


# ----------------------------------------------------------------------------------------- the audit against NSM

DISAGREE_UNMENTIONED = "carried content on a bank the explication does not mention"
DISAGREE_OPPOSITE = "carried state the explication's own states exclude"


@dataclass(frozen=True)
class Explication:
    """One NSM explication as the audit reads it: its record key (source and line range), the lemma and part of
    speech it explicates, the readings it binds to (one, or the typed candidates of which one is its sense), and the
    states it gives each bank it mentions or reaches through its molecules."""

    key: str
    lemma: str
    pos: str
    rows: np.ndarray
    states: dict[str, int]


_LABEL_BITS = {"+1": POS, "-1": NEG, "0": ZERO, "SILENT": SILENT}


def explications_from_nsm(compiled, kinds=("explication", "molecule"), pos=("verb", "noun")) -> list[Explication]:
    """The audited explications from `nsm.compile_records` output: records of `kinds` for `pos`, bound to a reading
    (a restriction) or to typed candidates (an obligation); templates and unbound records are not explications of
    one sense. The banks are the record's content with its molecules'."""
    by_rule = {}
    for o in compiled.obligations:
        by_rule.setdefault(o.rule_id, np.asarray(o.rows, dtype=np.int64))
    out = []
    for entry in compiled.receipt:
        if entry.get("kind") not in kinds or entry.get("pos") not in pos or "rule_id" not in entry:
            continue
        disposition = entry.get("disposition")
        if disposition == "RESTRICTION":
            rows = np.array([entry["reading"]], dtype=np.int64)
        elif disposition in {"OBLIGATION", "UNTYPED"} and entry["rule_id"] in by_rule:
            rows = by_rule[entry["rule_id"]]
        else:
            continue
        states = {bank: sum(_LABEL_BITS[x] for x in label.split("|")) for bank, label in entry.get("banks", {}).items()}
        key = f"{entry['source']}:{entry['start_line']}-{entry['end_line']}"
        out.append(Explication(key, entry["lemma"], entry["pos"], rows, states))
    return out


def audit_against_nsm(settlement: Settlement, explications, expressible=None) -> dict:
    """Every carried value on an explicated sense, judged against the explication as its complete meaning.

    For each explication and bank, each candidate reading's carried state (a single +1, -1 or 0 that inheritance
    landed on it) agrees with the explication, disagrees with it, or says nothing. A carried +1 or -1 on a bank the
    explication neither mentions nor reaches through its molecules disagrees; so does a carried state the
    explication's own states on that bank exclude; a carried 0 on a bank it does not mention says nothing. When the
    explication binds to several candidate readings, one of which is its sense, it disagrees (or agrees) only if
    every candidate does; a mixed bank is undetermined.

    Each disagreeing reading names its origins, their paths, and the candidate defeater: the link through which the
    value entered the chain of kinds leading to the explicated sense, from its origin to the first node after it
    (`synonymy` when the value is stated on the reading's own synset, which no link carries). Candidates are
    aggregated with what else rests on them: the explications that agree through the same link, and every inherited
    cell whose path starts with it. Nothing is defeated here.

    An explication is complete only over what NSM content can say: a bank no NSM record ever writes (`expressible`,
    by default every bank some given explication writes) is not judged, and its carried cells are counted apart.

    While a binding still has several candidates, a candidate that disagrees does so only if it is the sense: such
    readings are reported apart, as conditional disagreements with their own aggregated candidate links, never
    mixed with the definite ones.
    """
    explications = tuple(explications)
    if expressible is None:
        expressible = {bank for ex in explications for bank in ex.states}
    expressible = frozenset(expressible)
    not_judged: Counter = Counter()
    g, st, lin = settlement.graph, settlement.state, settlement.lineage
    masks = st.masks
    known_nodes = g.node_masks(settlement.known.masks)
    inherited = settlement.inherited & settlement.interpolated
    org = settlement.origins()
    cell_key = org["rows"] * _WIDTH + org["cols"]
    order = np.argsort(cell_key, kind="stable")
    sorted_keys = cell_key[order]
    names = [f.name for f in g.families]

    def family_name(code: int) -> str:
        return SYNONYMY.name if code == SYNONYM_HOP else names[code]

    def link_of(i: int) -> tuple[str, str, str]:
        origin = g.keys[int(org["origin"][i])]
        if org["entry"][i] < 0:
            return (SYNONYMY.name, origin, origin)
        return (family_name(int(org["first_family"][i])), origin, g.keys[int(org["first"][i])])

    def origins_of(row: int, col: int) -> list[tuple[int, dict]]:
        key = row * _WIDTH + col
        out = []
        for i in order[np.searchsorted(sorted_keys, key) : np.searchsorted(sorted_keys, key, "right")].tolist():
            e = int(org["entry"][i])
            hops = [] if e < 0 else [(family_name(int(lin.family[j])), g.keys[int(lin.node[j])]) for j in lin.path(e)]
            origin = int(org["origin"][i])
            fam, frm, to = link_of(i)
            out.append(
                (
                    i,
                    {
                        "origin": g.keys[origin],
                        "origin_stated": bool(_POPCOUNT[known_nodes[origin, col]] == 1),
                        "path": hops,
                        "candidate": {"family": fam, "from": frm, "to": to},
                        "last_hop": {
                            "family": family_name(int(org["family"][i])),
                            "from": g.keys[int(org["parent"][i])],
                        },
                    },
                )
            )
        return out

    def verdict(row: int, col: int, told) -> str | None:
        v = int(masks[row, col])
        if not inherited[row, col] or _POPCOUNT[v] != 1:
            return None
        if told is None:
            return DISAGREE_UNMENTIONED if v & CONTENT else None
        return "agrees" if v & told else DISAGREE_OPPOSITE

    disagreements, undetermined, conditional = [], [], []
    confirmations = 0
    link_disagree: dict = defaultdict(set)
    link_conditional: dict = defaultdict(set)
    link_agree: Counter = Counter()
    for ex in explications:
        rows = np.unique(np.asarray(ex.rows, dtype=np.int64))
        if not rows.size:
            continue
        for col in np.flatnonzero(inherited[rows].any(axis=0)).tolist():
            bank = BANKS[col]
            if bank not in expressible:
                not_judged[bank] += int(inherited[rows, col].sum())
                continue
            told = ex.states.get(bank)
            verdicts = [verdict(r, col, told) for r in rows.tolist()]
            if all(x == "agrees" for x in verdicts):
                confirmations += 1
                for r in rows.tolist():
                    for i, _ in origins_of(r, col):
                        link_agree[(*link_of(i), bank)] += 1
            elif all(x in (DISAGREE_UNMENTIONED, DISAGREE_OPPOSITE) for x in verdicts):
                readings = []
                for r, x in zip(rows.tolist(), verdicts):
                    carried = BIT_NAMES[int(masks[r, col])]
                    found = origins_of(r, col)
                    readings.append(
                        {"reading": st.readings[r], "carried": carried, "kind": x, "origins": [o for _, o in found]}
                    )
                    for i, _ in found:
                        link_disagree[(*link_of(i), bank, carried)].add(ex.key)
                disagreements.append(
                    {
                        "explication": ex.key,
                        "lemma": ex.lemma,
                        "pos": ex.pos,
                        "bank": bank,
                        "explication_states": state_names(told) if told is not None else [],
                        "readings": readings,
                    }
                )
            elif any(x in (DISAGREE_UNMENTIONED, DISAGREE_OPPOSITE) for x in verdicts):
                undetermined.append({"explication": ex.key, "lemma": ex.lemma, "pos": ex.pos, "bank": bank})
                for r, x in zip(rows.tolist(), verdicts):
                    if x not in (DISAGREE_UNMENTIONED, DISAGREE_OPPOSITE):
                        continue
                    carried = BIT_NAMES[int(masks[r, col])]
                    found = origins_of(r, col)
                    conditional.append(
                        {
                            "explication": ex.key,
                            "lemma": ex.lemma,
                            "pos": ex.pos,
                            "bank": bank,
                            "candidates": int(rows.size),
                            "reading": st.readings[r],
                            "carried": carried,
                            "kind": x,
                            "origins": [o for _, o in found],
                        }
                    )
                    for i, _ in found:
                        link_conditional[(*link_of(i), bank, carried)].add((ex.key, st.readings[r]))
    reach = Counter((*link_of(i), BANKS[int(org["cols"][i])]) for i in range(org["rows"].size))
    candidates = [
        {
            "link": {"family": fam, "from": frm, "to": to},
            "bank": bank,
            "carried": carried,
            "disagreeing_explications": sorted(keys),
            "agreeing_through_it": link_agree[(fam, frm, to, bank)],
            "inherited_cells_resting_on_it": reach[(fam, frm, to, bank)],
            "warrant": "NSM " + ", ".join(sorted(keys)),
        }
        for (fam, frm, to, bank, carried), keys in sorted(link_disagree.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]
    conditional_candidates = [
        {
            "link": {"family": fam, "from": frm, "to": to},
            "bank": bank,
            "carried": carried,
            "explications": sorted({k for k, _ in pairs}),
            "readings": len(pairs),
            "inherited_cells_resting_on_it": reach[(fam, frm, to, bank)],
        }
        for (fam, frm, to, bank, carried), pairs in sorted(
            link_conditional.items(), key=lambda kv: (-len(kv[1]), kv[0])
        )
    ]
    by_word_bank = Counter((d["lemma"], d["pos"], d["bank"]) for d in disagreements)
    conditional_by_word_bank = Counter((d["lemma"], d["pos"], d["bank"]) for d in conditional)
    return {
        "explications": len(explications),
        "disagreements": len(disagreements),
        "confirmations": confirmations,
        "undetermined": len(undetermined),
        "by_word_and_bank": {f"{w} ({p}) {b}": n for (w, p, b), n in sorted(by_word_bank.items())},
        "by_bank": dict(Counter(d["bank"] for d in disagreements).most_common()),
        "candidates": candidates,
        "details": disagreements,
        "undetermined_cells": undetermined,
        "not_judged": {"banks": sorted(set(BANKS) - expressible), "carried_cells": dict(not_judged.most_common())},
        "conditional": {
            "readings": len(conditional),
            "by_word_and_bank": {f"{w} ({p}) {b}": n for (w, p, b), n in sorted(conditional_by_word_bank.items())},
            "candidates": conditional_candidates,
            "details": conditional,
        },
    }
