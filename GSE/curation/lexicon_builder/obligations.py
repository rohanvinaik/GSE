"""Word-level obligations: a value that must go somewhere among a lemma's readings (design E4, F073).

A source often states a fact about a lemma and part of speech without naming the sense: "one of these readings has
this bank in these states". F073: "you know that one of the numbers can't fit in the other two squares, so even if
the square *techncially* can't be narrowed down further, the fact that one of the numbers can't fit in the other two
spaces but HAS to fit SOMEWHERE in those three boxes". An obligation is that fact: a rule id, a bank, the allowed
states, and the readings it ranges over. It is produced by the source lenses (`LensOutput.obligations`).

Obligations that share a `witness` come from one source observation, so one and the same reading satisfies all of
them (a coordinate and its companions). They are propagated as one group; an obligation without a witness is a group
by itself.

Applying a batch of obligations reads only the current masks:

- a reading is *excluded* from a group when, for some obligation of the group, none of the allowed states is still
  legal on its cell (or the reading is not among that obligation's readings);
- when every reading but one is excluded, the last one is restricted, on every bank of the group, to that
  obligation's allowed states (forced);
- when every reading is excluded, every obligation of the group is a conflict, and no mask changes;
- obligations forcing one cell to disjoint states are all conflicts, and that cell does not change;
- a group over a reading whose cell is already a conflict (an empty mask) is left alone, as closure leaves a
  conflicted reading alone.

One application is one sweep. A forced cell can exclude a reading from another obligation, so the runner repeats
the sweep, interleaved with closure, until nothing changes (`inheritance.settle` does).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cells import BANK_INDEX, BANKS, State

ALL_EXCLUDED = 1
DISJOINT_FORCINGS = 2
REASONS = {ALL_EXCLUDED: "every reading excluded", DISJOINT_FORCINGS: "forced to disjoint states on one cell"}


@dataclass(frozen=True, eq=False)
class Obligation:
    """At least one of `rows` (reading rows of the State) has `bank` in `allowed` (a mask of state bits).

    Obligations that share a `witness` are satisfied by one and the same reading. `premises` name the source
    observations the obligation rests on.
    """

    rule_id: str
    bank: str
    allowed: int
    rows: np.ndarray
    witness: int | None = None
    premises: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.rule_id or self.bank not in BANK_INDEX or not 0 < self.allowed < 16:
            raise ValueError("OBLIGATION_FIELDS")


@dataclass(frozen=True)
class Batch:
    """Many obligations as flat arrays: one entry per (obligation, reading) membership."""

    rule_ids: tuple[str, ...]
    cols: np.ndarray  # (m,) bank column of each obligation
    allowed: np.ndarray  # (m,) allowed states of each obligation
    group: np.ndarray  # (m,) the witness group of each obligation, dense from 0
    rows: np.ndarray  # (k,) member reading rows
    owner: np.ndarray  # (k,) the obligation each member belongs to

    @classmethod
    def of(cls, obligations) -> Batch:
        """Any objects with `rule_id`, `bank`, `allowed`, `rows` and optionally `witness`."""
        obligations = tuple(obligations)
        members = [np.unique(np.asarray(o.rows, dtype=np.int64)) for o in obligations]
        groups: dict = {}
        group = [
            groups.setdefault(
                ("witness", w) if (w := getattr(o, "witness", None)) is not None else ("own", i), len(groups)
            )
            for i, o in enumerate(obligations)
        ]
        return cls(
            rule_ids=tuple(o.rule_id for o in obligations),
            cols=np.array([BANK_INDEX[o.bank] for o in obligations], dtype=np.int64),
            allowed=np.array([o.allowed for o in obligations], dtype=np.uint8),
            group=np.array(group, dtype=np.int64),
            rows=np.concatenate(members) if members else np.zeros(0, dtype=np.int64),
            owner=np.repeat(np.arange(len(obligations), dtype=np.int64), [m.size for m in members]),
        )

    def __len__(self) -> int:
        return len(self.rule_ids)

    def members(self, i: int) -> np.ndarray:
        return self.rows[self.owner == i]


@dataclass(frozen=True)
class Forcing:
    """What one sweep did: the cells it narrowed and the obligation that forced each, its conflicts, and the
    obligations it left alone because a member cell is already a conflict."""

    rows: np.ndarray
    cols: np.ndarray
    old: np.ndarray
    new: np.ndarray
    by: np.ndarray  # for each narrowed cell, one obligation that forced it
    conflicts: np.ndarray  # obligation indices
    reasons: np.ndarray  # ALL_EXCLUDED or DISJOINT_FORCINGS, parallel to `conflicts`
    blocked: np.ndarray  # obligation indices

    @property
    def changed(self) -> int:
        return int(self.rows.size)

    def described(self, batch: Batch, state: State) -> list[dict]:
        """The conflicts named by rule, bank, reason and readings."""
        return [
            {
                "rule_id": batch.rule_ids[i],
                "bank": BANKS[int(batch.cols[i])],
                "reason": REASONS[int(r)],
                "readings": [state.readings[j] for j in batch.members(int(i))],
            }
            for i, r in zip(self.conflicts.tolist(), self.reasons.tolist())
        ]


def _open_readings(state: State, batch: Batch):
    """Per witness group: whether a member cell is a conflict, and its readings that satisfy every obligation."""
    n_groups = int(batch.group.max()) + 1 if len(batch) else 0
    member_group = batch.group[batch.owner]
    cells = state.masks[batch.rows, batch.cols[batch.owner]]
    blocked = np.zeros(n_groups, dtype=bool)
    blocked[member_group[cells == 0]] = True
    misfits = (cells & batch.allowed[batch.owner]) == 0
    span = max(len(state.readings), 1)
    pairs, inverse, counts = np.unique(member_group * span + batch.rows, return_inverse=True, return_counts=True)
    pair_group = pairs // span
    size = np.bincount(batch.group, minlength=n_groups)
    fits_all = np.bincount(inverse, weights=misfits, minlength=pairs.size) == 0
    open_pair = fits_all & (counts == size[pair_group])
    return n_groups, blocked, pair_group[open_pair], pairs[open_pair] % span


def force(state: State, batch: Batch) -> Forcing:
    """One sweep of every obligation in `batch` over `state`, narrowing it in place."""
    n_groups, blocked, open_group, open_row = _open_readings(state, batch)
    open_count = np.bincount(open_group, minlength=n_groups)
    excluded = (open_count == 0) & ~blocked
    forcing = (open_count == 1) & ~blocked
    forced_row = np.full(n_groups, -1, dtype=np.int64)
    one = forcing[open_group]
    forced_row[open_group[one]] = open_row[one]
    owners = np.flatnonzero(forcing[batch.group])
    rows, cols = forced_row[batch.group[owners]], batch.cols[owners]
    keys = rows * len(BANKS) + cols
    order = np.argsort(keys, kind="stable")
    keys, owners = keys[order], owners[order]
    unique, starts = np.unique(keys, return_index=True)
    combined = np.bitwise_and.reduceat(batch.allowed[owners], starts) if unique.size else np.zeros(0, np.uint8)
    cell_rows, cell_cols = unique // len(BANKS), unique % len(BANKS)
    masks = state.masks
    old = masks[cell_rows, cell_cols]
    new = old & combined
    disjoint = new == 0
    clash = np.unique(owners[disjoint[np.searchsorted(unique, keys)]])
    changed = ~disjoint & (new != old)
    masks[cell_rows[changed], cell_cols[changed]] = new[changed]
    excluded_obligations = np.flatnonzero(excluded[batch.group])
    return Forcing(
        rows=cell_rows[changed],
        cols=cell_cols[changed],
        old=old[changed],
        new=new[changed],
        by=owners[starts][changed],
        conflicts=np.concatenate([excluded_obligations, clash]),
        reasons=np.concatenate(
            [
                np.full(excluded_obligations.size, ALL_EXCLUDED, np.uint8),
                np.full(clash.size, DISJOINT_FORCINGS, np.uint8),
            ]
        ),
        blocked=np.flatnonzero(blocked[batch.group]),
    )
