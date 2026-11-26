"""Relations between banks: the computational atoms (design E4).

F088: "the true atomic is a *sub*-prime symbolic rule of relation between banks ... 'presence of any non-zero and
non-empty input in <bank A> forces <bank b> to be [typed 0/empty/also filled/etc]'". A relation is a table of the
joint states its banks may take, over a typed scope, with its warrant. Applying it keeps, for every cell, only the
states that still belong to some permitted tuple (generalized arc consistency), so two premises can together remove
a state neither removes alone (F073), and a value that has to go somewhere is forced where it alone fits.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np

from .cells import ALL, BANK_INDEX, NEG, POS, SILENT, ZERO

_STATES = (POS, NEG, ZERO, SILENT)


@dataclass(frozen=True)
class Relation:
    """Permitted joint states of `banks`, applied to the readings of `scope`."""

    rule_id: str
    banks: tuple[str, ...]
    allowed: tuple[tuple[int, ...], ...]
    warrant: str
    scope: str = "all"

    def __post_init__(self):
        if not self.rule_id or not self.warrant:
            raise ValueError("RELATION_NEEDS_ID_AND_WARRANT")
        if len(set(self.banks)) != len(self.banks) or any(b not in BANK_INDEX for b in self.banks):
            raise ValueError("RELATION_BANKS")
        if any(len(t) != len(self.banks) or any(s not in _STATES for s in t) for t in self.allowed):
            raise ValueError("RELATION_TUPLES")


def from_predicate(rule_id, banks, permitted, warrant, scope="all") -> Relation:
    """Build a relation from a predicate over one state bit per bank."""
    allowed = tuple(t for t in product(_STATES, repeat=len(banks)) if permitted(*t))
    return Relation(rule_id, tuple(banks), allowed, warrant, scope)


def implies(rule_id, if_bank, if_states, then_bank, then_states, warrant, scope="all") -> Relation:
    """When `if_bank` is in `if_states`, `then_bank` must be in `then_states` (masks of state bits)."""
    return from_predicate(
        rule_id, (if_bank, then_bank), lambda a, b: not (a & if_states) or bool(b & then_states), warrant, scope
    )


def excludes(rule_id, a_bank, a_states, b_bank, b_states, warrant, scope="all") -> Relation:
    """`a_bank` in `a_states` and `b_bank` in `b_states` never hold together."""
    return from_predicate(rule_id, (a_bank, b_bank), lambda a, b: not (a & a_states and b & b_states), warrant, scope)


def at_least_one(rule_id, banks, states, warrant, scope="all") -> Relation:
    """At least one of `banks` is in `states`: the value must go somewhere."""
    return from_predicate(rule_id, banks, lambda *t: any(s & states for s in t), warrant, scope)


def apply(relation: Relation, masks: np.ndarray, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Narrow the relation's banks on `rows` to the states that keep a permitted tuple.

    Readings whose masks already hold a conflict on these banks are left alone. Returns the rows, the columns and
    the old masks of every cell that changed, so the caller can record each removal and wake dependents.
    """
    cols = np.array([BANK_INDEX[b] for b in relation.banks])
    if rows.size == 0:
        return rows, cols, np.zeros((0, cols.size), dtype=np.uint8)
    sub = masks[np.ix_(rows, cols)]
    live = (sub != 0).all(axis=1)
    rows, sub = rows[live], sub[live]
    if rows.size == 0:
        return rows, cols, sub
    shifts = np.arange(cols.size, dtype=np.int64) * 4
    keys = (sub.astype(np.int64) << shifts).sum(axis=1)
    unique, inverse = np.unique(keys, return_inverse=True)
    configs = ((unique[:, None] >> shifts) & 15).astype(np.uint8)
    support = np.zeros_like(configs)
    for t in relation.allowed:
        t = np.array(t, dtype=np.uint8)
        fits = ((configs & t) != 0).all(axis=1)
        support[fits] |= t
    new = sub & support[inverse]
    changed = (new != sub).any(axis=1)
    if changed.any():
        masks[np.ix_(rows[changed], cols)] = new[changed]
    return rows[changed], cols, sub[changed]


def states(*values) -> int:
    """A mask from values: +1, -1, 0, "SILENT"."""
    out = 0
    for v in values:
        out |= {+1: POS, -1: NEG, 0: ZERO, "SILENT": SILENT}[v]
    return out


NON_EMPTY_CONTENT = POS | NEG  # "presence of any non-zero and non-empty input" (F088)
ANY = ALL
