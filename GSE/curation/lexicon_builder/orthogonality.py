"""Orthogonal cells: explicit absence where no valid encoding has content (Rohan, 2026-11-25 17:56).

"There IS a way to fill default zeros that isn't slop ... the part informed by the TrialLedger project and
constraint proprogation ideas ... The one that classifies all the dimensions that are plausibly sane and potentially
valid encodings, and which are definitionally not valid or useful and propogating the correct constraints. For the
ones that are completely orthogonal to a valid definition of the word should be zeros. Others should NOT be
automatically filled in with zeros." TrialLedger: "Explicit premises can eliminate incompatible alternatives."

The lead's reading of it (2026-11-27). A cell is orthogonal when the constraints have eliminated every content state
(+1 and -1), so no valid encoding of the reading has content there: its mask is exactly {0, SILENT}. Such a cell is 0,
explicit absence (F118: "0 is explicit absence; empty is silence"), unless a silence warrant covers it (NSM
completeness, an authored SILENT). A cell whose content states are still legal is not touched, which includes an
unpaired bank at its starting mask {+1, 0, SILENT}: "Others should NOT be automatically filled in with zeros." A
decided cell is not touched either.

Standing. Applied to the known layer, the zero is a strict conclusion from known premises and is known; applied to
the interpolated layer, a cell whose content only interpolation eliminated is interpolated. A known zero stands over
an interpolated SILENT on the same cell: that default contradicts a known value, and is reported as suspended.

Writing a zero can wake a law, so `apply` closes again under the relations and repeats until no new orthogonal cell
appears. Every zero is a recorded derivation under the rule id `orthogonal`.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from .cells import BANKS, NEG, POS, SILENT, ZERO, State
from .closure import Derivations, close

RULE_ID = "orthogonal"
WARRANT = (
    "Rohan 2026-11-25 17:56: the ones completely orthogonal to a valid definition of the word should be zeros; "
    "every content state eliminated, no silence warrant"
)
CONTENT = POS | NEG
ORTHOGONAL_MASK = ZERO | SILENT


def orthogonal(state: State, silence_warranted: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """The cells whose mask holds no content state but still both 0 and SILENT, and that no silence warrant covers."""
    cells = state.masks == ORTHOGONAL_MASK
    if silence_warranted is not None:
        cells &= ~silence_warranted
    return np.nonzero(cells)


def write(state: State, rows: np.ndarray, cols: np.ndarray, derivations: Derivations | None = None) -> int:
    """Narrow the given cells to 0 in place, recording each removal under `orthogonal`."""
    if not rows.size:
        return 0
    touched = np.unique(rows)
    old = state.masks[touched].copy()
    state.masks[rows, cols] = ZERO
    if derivations is not None:
        rule = len(derivations.rule_ids)
        derivations.rule_ids.append(RULE_ID)
        derivations.add(rule, touched, np.arange(len(BANKS)), old, state.masks[touched])
    return int(rows.size)


def apply(
    state: State, relations=(), scopes=None, silence_warranted=None, derivations: Derivations | None = None
) -> dict:
    """Write every orthogonal cell of `state` as 0, close under `relations`, and repeat until none is left."""
    rows_all, cols_all, sweeps = [], [], 0
    while True:
        rows, cols = orthogonal(state, silence_warranted)
        if not rows.size:
            break
        write(state, rows, cols, derivations)
        rows_all.append(rows)
        cols_all.append(cols)
        sweeps += 1
        if relations:
            close(state, relations, scopes, derivations)
    rows = np.concatenate(rows_all) if rows_all else np.zeros(0, dtype=np.int64)
    cols = np.concatenate(cols_all) if cols_all else np.zeros(0, dtype=np.int64)
    return {"rows": rows, "cols": cols, "cells": int(rows.size), "sweeps": sweeps}


def apply_settlement(settlement, relations=(), silence_warranted=None, record: Derivations | None = None) -> dict:
    """Both layers of a settled round, in place, each with its own standing: the known layer under its known scopes,
    then the interpolated layer, which stays inside the known one. Where the known layer changed, the interpolated
    layer takes the intersection; an interpolated state the known one now excludes (an interpolated SILENT on a cell
    the known layer makes 0) is suspended, the known value stands, and the cell is reported."""
    known, state = settlement.known, settlement.state
    before = known.masks.copy()
    k = apply(known, relations, settlement.known_scopes, silence_warranted, record)
    rows, cols = np.nonzero(known.masks != before)
    inside = state.masks[rows, cols] & known.masks[rows, cols]
    excluded = inside == 0
    state.masks[rows, cols] = np.where(excluded, known.masks[rows, cols], inside)
    m = apply(state, relations, settlement.scopes, silence_warranted)
    return {
        "known": k,
        "interpolated": m,
        "interpolated_suspended": (rows[excluded], cols[excluded]),
    }


def silence_warrants(n: int, relations=(), scopes=None, batch=None) -> np.ndarray:
    """Cells a silence warrant covers: the scope of every one-bank relation that eliminates content but keeps SILENT
    (an authored domain that permits silence), and the candidate readings of every obligation whose states are
    SILENT alone (an NSM explication's silence on its sense, not yet located on one reading)."""
    out = np.zeros((n, len(BANKS)), dtype=bool)
    scopes = dict(scopes or {})
    every = np.ones(n, dtype=bool)
    for rel in relations:
        if len(rel.banks) != 1:
            continue
        states = 0
        for (s,) in rel.allowed:
            states |= s
        if states & SILENT and not states & CONTENT:
            col = BANKS.index(rel.banks[0])
            out[:, col] |= every if rel.scope == "all" else scopes[rel.scope]
    if batch is not None and len(batch):
        silent = batch.allowed[batch.owner] == SILENT
        out[batch.rows[silent], batch.cols[batch.owner][silent]] = True
    return out


def summary(result: dict, readings) -> dict:
    """Counts of the cells written, by bank and by part of speech."""
    rows, cols = result["rows"], result["cols"]
    return {
        "cells": int(rows.size),
        "by_bank": dict(Counter(BANKS[c] for c in cols.tolist()).most_common()),
        "by_pos": dict(Counter(readings[r].pos for r in rows.tolist()).most_common()),
    }
