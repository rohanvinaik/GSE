"""Where each inherited value came from (`lineage.py`). The nodes and links are written for the test."""

from __future__ import annotations

import numpy as np

from GSE.curation.lexicon_builder import cells, lineage
from GSE.curation.lexicon_builder import inheritance as inh
from GSE.curation.lexicon_builder.cells import POS, State
from GSE.curation.lexicon_builder.relations import implies

B = cells.BANK_INDEX


def _state(n):
    return State.opening([f"r{i}" for i in range(n)])


def _set(state, row, bank, value):
    state.masks[row, B[bank]] = cells.bit(value)


def _get(state, row, bank):
    return int(state.masks[row, B[bank]])


def _settle(state, groups, links, **kw):
    return inh.settle(state, inh.build(groups, links), **kw)


def test_every_carried_value_records_its_origin_and_last_hop():
    s = _state(6)
    _set(s, 0, "MOVE", +1)
    _set(s, 5, "MOVE", +1)
    _set(s, 4, "FEEL", +1)
    groups = {"hub": [0, 1], "kind": [2], "kk": [3, 4], "other": [5]}
    links = [
        ("hypernym", "hub", "transit"),
        ("hypernym", "transit", "kind"),
        ("hypernym", "kind", "kk"),
        ("entails", "other", "kk"),
    ]
    # A law written for the test, scoped to r4 alone: its consequence on r4 reaches r3 by synonymy, interpolated.
    law = implies("t:moves-alive", "MOVE", POS, "ALIVE", POS, "test", scope="only_r4")
    only_r4 = np.array([False, False, False, False, True, False])
    out = _settle(s, groups, links, relations=[law], scopes={"only_r4": only_r4})
    keys, o = out.graph.keys, out.origins()
    found = {
        (out.state.readings[r], cells.BANKS[c], keys[g], keys[p], int(f), keys[first])
        for r, c, g, p, f, first in zip(o["rows"], o["cols"], o["origin"], o["parent"], o["family"], o["first"])
    }
    hypernym, entails = 0, 3
    assert ("r2", "MOVE", "hub", "transit", hypernym, "transit") in found
    assert ("r3", "MOVE", "hub", "kind", hypernym, "transit") in found
    assert ("r3", "MOVE", "other", "other", entails, "kk") in found  # a second origin, by entailment
    assert ("r3", "ALIVE", "kk", "kk", lineage.SYNONYM_HOP, "kk") in found  # a consequence, across synonymy
    assert not any(r == "r1" for r, *_ in found)  # a synonym's statement is known, not carried
    assert _get(out.known, 3, "FEEL") == POS
    entry = next(
        int(e) for r, c, g, e in zip(o["rows"], o["cols"], o["origin"], o["entry"]) if (r, keys[g]) == (3, "hub")
    )
    assert [keys[out.lineage.node[j]] for j in out.lineage.path(entry)] == ["transit", "kind", "kk"]
