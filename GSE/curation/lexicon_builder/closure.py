"""Closure over the whole population to an order-independent fixed point (design E9).

TrialLedger: "Finite coordinate closure removes values with recorded causes and reaches an order-independent fixed
point." Every relation is applied to its whole scope at once. When a relation narrows a bank anywhere, only the
relations that read that bank are woken again, and only on the readings that changed. Every removal is recorded
with the relation that made it. Removal only ever narrows a mask, so the fixed point does not depend on the order
in which relations run.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np

from .cells import BANK_INDEX, State
from .relations import Relation, apply


@dataclass
class Derivations:
    """Every removal: the reading row, the bank column, the states removed, and the relation that removed them."""

    rows: list = field(default_factory=list)
    cols: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    rule_ids: list = field(default_factory=list)

    def add(self, rule: int, rows, cols, old, new) -> None:
        gone = old & ~new
        r, c = np.nonzero(gone)
        if r.size:
            self.rows.append(rows[r])
            self.cols.append(cols[c])
            self.removed.append(gone[r, c])
            self.rules.append(np.full(r.size, rule, dtype=np.int32))

    def count(self) -> int:
        return int(sum(a.size for a in self.rows))

    def arrays(self) -> dict:
        def cat(parts, dtype):
            return np.concatenate(parts) if parts else np.zeros(0, dtype=dtype)

        return {
            "rows": cat(self.rows, np.int64),
            "cols": cat(self.cols, np.int64),
            "removed": cat(self.removed, np.uint8),
            "rules": cat(self.rules, np.int32),
            "rule_ids": np.array(self.rule_ids, dtype=object),
        }


def close(state: State, relations, scopes: dict[str, np.ndarray] | None = None, derivations=None) -> dict:
    """Narrow `state` in place under `relations` until nothing changes; return the round's receipt.

    `scopes` maps a scope name to a boolean mask over readings; "all" is every reading.
    """
    started = time.perf_counter()
    relations = tuple(relations)
    n = len(state.readings)
    scopes = dict(scopes or {})
    scopes.setdefault("all", np.ones(n, dtype=bool))
    missing = {r.scope for r in relations} - set(scopes)
    if missing:
        raise ValueError(f"UNKNOWN_SCOPES {sorted(missing)}")
    derivations = derivations if derivations is not None else Derivations()
    offset = len(derivations.rule_ids)
    derivations.rule_ids.extend(r.rule_id for r in relations)
    readers: dict[int, list[int]] = defaultdict(list)
    for i, r in enumerate(relations):
        for b in r.banks:
            readers[BANK_INDEX[b]].append(i)
    scope_rows = {name: np.flatnonzero(mask) for name, mask in scopes.items()}
    pending: dict[int, np.ndarray | None] = {i: None for i in range(len(relations))}
    queue = deque(range(len(relations)))
    bits_before = state.bits()
    applications = 0
    while queue:
        i = queue.popleft()
        rows_hint = pending.pop(i)
        relation = relations[i]
        rows = scope_rows[relation.scope]
        if rows_hint is not None:
            rows = rows[np.isin(rows, rows_hint, assume_unique=False)]
        applications += 1
        changed_rows, cols, old = apply(relation, state.masks, rows)
        if changed_rows.size == 0:
            continue
        new = state.masks[np.ix_(changed_rows, cols)]
        derivations.add(offset + i, changed_rows, cols, old, new)
        touched = cols[(old != new).any(axis=0)]
        for col in touched:
            for j in readers[int(col)]:
                if j == i:
                    continue
                if j in pending:
                    prev = pending[j]
                    pending[j] = None if prev is None else np.union1d(prev, changed_rows)
                else:
                    pending[j] = changed_rows
                    queue.append(j)
    return {
        "relations": len(relations),
        "applications": applications,
        "removals": derivations.count(),
        "bits_before": bits_before,
        "bits_after": state.bits(),
        "seconds": round(time.perf_counter() - started, 3),
    }


def check_relation(relation: Relation) -> None:
    if not isinstance(relation, Relation):
        raise TypeError("NOT_A_RELATION")
