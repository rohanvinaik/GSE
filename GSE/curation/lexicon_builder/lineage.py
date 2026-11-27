"""Where each inherited value came from (design E8; the lead's ruling of 2026-11-27: landed cells record their origin).

Every carried value records its origin, the node where it was decided without a carried default (a stated value, a
synonym's, or a consequence of the laws), with the parent and edge family of its last hop and the first node and
family after the origin, on a shortest carrying path. A retraction (TrialLedger: "Every conclusion retains premises,
source and rule versions") and the audit against NSM (`nsm_audit.py`) walk it back. The arrays are compact: one entry
per (node, bank, origin), parallel arrays, computed level by level from the origins.

`inheritance.settle` builds the lineage of its final round (`Settlement.lineage`); `Settlement.origins` gives it per
inherited reading cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np

from .cells import _POPCOUNT, BANKS

SYNONYM_HOP = -1  # the family code of a value a reading takes from its own synset
_WIDTH = len(BANKS)


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


def trace(graph, node_masks: np.ndarray, given: np.ndarray, landed: np.ndarray) -> Lineage:
    """Walk every decided value forward along the edges that carry it, level by level from its origin.

    `node_masks` are the graph's node masks, `given` what each node gives its receivers (`inheritance.emissions`),
    and `landed` the node cells a carried default narrowed in the round.
    """
    n = len(graph.keys)
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


def origins(graph, lin: Lineage, cells: np.ndarray, landed: np.ndarray, n_readings: int) -> dict[str, np.ndarray]:
    """Arrays parallel to the reading cells flagged in `cells` (readings x banks), one entry per origin: the reading
    row and bank, the origin node, the parent node and family of the last hop (`SYNONYM_HOP` and the reading's own
    node when the value comes from its own synset), the first node and family after the origin, and the lineage
    entry (-1 for a synonym's)."""
    node_of_row = np.full(n_readings, -1, dtype=np.int64)
    node_of_row[graph.rows] = graph.node_of
    rows, cols = np.nonzero(cells)
    nodes = node_of_row[rows]
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
