"""Word-level obligations: a value that must go somewhere among a lemma's readings (design E4, F073).

A source often states a fact about a lemma and part of speech without naming the sense: "one of these readings has
this bank in these states". F073: "you know that one of the numbers can't fit in the other two squares, so even if
the square *techncially* can't be narrowed down further, the fact that one of the numbers can't fit in the other two
spaces but HAS to fit SOMEWHERE in those three boxes". An obligation is that fact: a rule id, a bank, the allowed
states, and the readings it ranges over. The source lenses produce them (`projection.LensOutput.obligations`), and so
does NSM content. A word-level fact is never copied onto every reading of the lemma.

A joint obligation. Obligations that share a `witness` come from one source observation (USAS's "happy (adj) is
GOOD +1 and FEEL +1", or one NSM explication), so all of their (bank, states) hold together on one and the same
reading. They are one group; an obligation without a witness is a group by itself. A group may carry `facts`, guard
names (`own_semantic_kind=evaluator`, `source_frame_family=Fear`), which hold of the reading the group is located on.

Applying a batch of obligations reads only the current masks:

- a reading is *excluded* from a group when it cannot satisfy all of the group's (bank, states) together: on some
  bank none of the states the group requires there is still legal, or the reading is outside one obligation's rows;
- when exactly one reading is left, the group is *located* on it: that reading is restricted to every (bank,
  states) of the group (forced), and the group's facts become true for it, returned so the runner can add them to
  the guard scopes and wake the laws;
- when no reading is left, every obligation of the group is a conflict, and no mask changes;
- located groups that force one cell to disjoint states are all conflicts: none of their cells is written and none
  of their facts is returned;
- a group over a reading whose cell is already a conflict (an empty mask) is left alone, as closure leaves a
  conflicted reading alone.

Identity classes. When readings are joined by proposed identities of meaning (a Wiktionary sense aligned to a
WordNet reading, a form or alternative spelling of its target), they are one candidate, not several: `classes` gives
each reading its class, and a group counts classes. A class is open when every reading of it among the group's
candidates can satisfy the group (the same meaning cannot satisfy it in one reading and not in another); when one
class is left, every one of those readings is forced. A class rests on proposals, so the runner applies classes only
in the interpolated layer, and `held` groups fall back to single readings when a conflict suspends their class.

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
_WIDTH = len(BANKS)


@dataclass(frozen=True, eq=False)
class Obligation:
    """At least one of `rows` (reading rows of the State) has `bank` in `allowed` (a mask of state bits).

    Obligations that share a `witness` hold together on one and the same reading. `premises` name the source records
    the obligation rests on. `facts` are guard names that hold of the reading the obligation is located on.
    """

    rule_id: str
    bank: str
    allowed: int
    rows: np.ndarray
    witness: int | None = None
    premises: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()

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
    facts: tuple[tuple[str, ...], ...] = ()  # (m,) guard names of each obligation

    @classmethod
    def of(cls, obligations) -> Batch:
        """From `Obligation`s, or any objects with `rule_id`, `bank`, `allowed`, `rows` and optionally `witness`
        and `facts` (the source lenses' `LensOutput.obligations` are `Obligation`s)."""
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
            facts=tuple(tuple(getattr(o, "facts", ())) for o in obligations),
        )

    def __len__(self) -> int:
        return len(self.rule_ids)

    @property
    def groups(self) -> int:
        return int(self.group.max()) + 1 if len(self) else 0

    def members(self, i: int) -> np.ndarray:
        return self.rows[self.owner == i]

    def joint_allowed(self) -> np.ndarray:
        """(m,) the states each obligation's group requires on its bank: the intersection over the group's
        obligations on that bank."""
        if not len(self):
            return self.allowed.copy()
        keys = self.group * _WIDTH + self.cols
        unique, inverse = np.unique(keys, return_inverse=True)
        order = np.argsort(inverse, kind="stable")
        starts = np.searchsorted(inverse[order], np.arange(unique.size))
        return np.bitwise_and.reduceat(self.allowed[order], starts)[inverse]


@dataclass(frozen=True)
class Forcing:
    """What one sweep did: the cells it narrowed and the obligation that forced each, the groups it located with
    their facts, its conflicts, and the obligations it left alone because a member cell is already a conflict."""

    rows: np.ndarray
    cols: np.ndarray
    old: np.ndarray
    new: np.ndarray
    by: np.ndarray  # for each narrowed cell, one obligation that forced it
    located_rows: np.ndarray  # the readings each located group is on (several when located on a class)
    located_by: np.ndarray  # one obligation of the group, parallel to `located_rows`
    through_class: np.ndarray  # the groups located on a class of more than one reading
    facts: dict[str, np.ndarray]  # guard name -> the readings a located group makes it true for
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


def _pairs(state: State, batch: Batch):
    """Every (group, reading) candidate pair, whether it satisfies all of the group together, and the groups that
    touch a conflicted cell."""
    n_groups = batch.groups
    member_group = batch.group[batch.owner]
    cells = state.masks[batch.rows, batch.cols[batch.owner]]
    blocked = np.zeros(n_groups, dtype=bool)
    blocked[member_group[cells == 0]] = True
    misfits = (cells & batch.joint_allowed()[batch.owner]) == 0
    span = max(len(state.readings), 1)
    pairs, inverse, counts = np.unique(member_group * span + batch.rows, return_inverse=True, return_counts=True)
    pair_group = pairs // span
    size = np.bincount(batch.group, minlength=n_groups)
    fits_all = np.bincount(inverse, weights=misfits, minlength=pairs.size) == 0
    return blocked, pair_group, pairs % span, fits_all & (counts == size[pair_group])


def _combine(rows, cols, allowed, owners):
    """Per cell: the intersection of the states forced on it, with the cell's first forcing entry."""
    keys = rows * _WIDTH + cols
    order = np.argsort(keys, kind="stable")
    unique, starts = np.unique(keys[order], return_index=True)
    combined = np.bitwise_and.reduceat(allowed[order], starts) if unique.size else np.zeros(0, np.uint8)
    cell_of_entry = np.empty(keys.size, dtype=np.int64)
    cell_of_entry[order] = np.searchsorted(unique, keys[order])
    return unique // _WIDTH, unique % _WIDTH, combined, owners[order][starts], cell_of_entry


def force(
    state: State,
    batch: Batch,
    classes: np.ndarray | None = None,
    held: np.ndarray | None = None,
    held_classes: np.ndarray | None = None,
) -> Forcing:
    """One sweep of every obligation in `batch` over `state`, narrowing it in place.

    `classes` (an id per reading) makes readings of one identity class one candidate; `held` (a flag per group)
    keeps a group on `held_classes` instead (single readings when that is omitted).
    """
    n_groups = batch.groups
    blocked, pair_group, pair_row, pair_open = _pairs(state, batch)
    if classes is None:
        pair_class = pair_row
    else:
        pair_class = np.asarray(classes, dtype=np.int64)[pair_row]
        if held is not None:
            fallback = pair_row if held_classes is None else np.asarray(held_classes, dtype=np.int64)[pair_row]
            pair_class = np.where(held[pair_group], int(classes.max()) + 1 + fallback, pair_class)
    span = int(pair_class.max()) + 1 if pair_class.size else 1
    keys = pair_group * span + pair_class
    class_keys, class_of_pair = np.unique(keys, return_inverse=True)
    class_open = np.bincount(class_of_pair, weights=~pair_open, minlength=class_keys.size) == 0
    class_group = class_keys // span
    open_count = np.bincount(class_group[class_open], minlength=n_groups)
    excluded = (open_count == 0) & ~blocked
    located = (open_count == 1) & ~blocked
    chosen = np.full(n_groups, -1, dtype=np.int64)
    sel = class_open & located[class_group]
    chosen[class_group[sel]] = class_keys[sel]
    on = located[pair_group] & (keys == chosen[pair_group])
    located_pair_row, located_pair_group = pair_row[on], pair_group[on]
    # Every obligation of a located group forces its bank on each reading the group is located on.
    ob_order = np.argsort(batch.group, kind="stable")
    ob_start = np.searchsorted(batch.group[ob_order], np.arange(n_groups + 1))
    count = ob_start[located_pair_group + 1] - ob_start[located_pair_group]
    rep = np.repeat(np.arange(located_pair_row.size), count)
    offset = np.arange(rep.size) - np.repeat(np.cumsum(count) - count, count)
    owners = ob_order[ob_start[located_pair_group][rep] + offset]
    entry_rows = located_pair_row[rep]
    # A group with any cell forced to disjoint states writes nothing.
    rows, cols, combined, _, cell_of = _combine(entry_rows, batch.cols[owners], batch.allowed[owners], owners)
    masks = state.masks
    disjoint = (masks[rows, cols] & combined) == 0
    clash_groups = np.unique(batch.group[owners[disjoint[cell_of]]])
    located[clash_groups] = False
    keep = located[batch.group[owners]]
    owners, entry_rows = owners[keep], entry_rows[keep]
    rows, cols, combined, by, _ = _combine(entry_rows, batch.cols[owners], batch.allowed[owners], owners)
    old = masks[rows, cols]
    new = old & combined
    changed = new != old
    masks[rows[changed], cols[changed]] = new[changed]
    on_located = located[located_pair_group]
    located_pair_row, located_pair_group = located_pair_row[on_located], located_pair_group[on_located]
    first = np.unique(batch.group, return_index=True)[1]  # groups are dense, so this is indexed by group
    facts: dict[str, set[int]] = {}
    group_rows: dict[int, list[int]] = {}
    for g, r in zip(located_pair_group.tolist(), located_pair_row.tolist()):
        group_rows.setdefault(g, []).append(r)
    for i in np.flatnonzero(located[batch.group]).tolist():
        for name in batch.facts[i] if batch.facts else ():
            facts.setdefault(name, set()).update(group_rows[int(batch.group[i])])
    excluded_obligations = np.flatnonzero(excluded[batch.group])
    clash = np.flatnonzero(np.isin(batch.group, clash_groups))
    per_group = np.bincount(located_pair_group, minlength=n_groups)
    return Forcing(
        rows=rows[changed],
        cols=cols[changed],
        old=old[changed],
        new=new[changed],
        by=by[changed],
        located_rows=located_pair_row,
        located_by=first[located_pair_group] if located_pair_group.size else np.zeros(0, dtype=np.int64),
        through_class=np.flatnonzero(per_group > 1),
        facts={name: np.array(sorted(r), dtype=np.int64) for name, r in sorted(facts.items())},
        conflicts=np.concatenate([excluded_obligations, clash]),
        reasons=np.concatenate(
            [
                np.full(excluded_obligations.size, ALL_EXCLUDED, np.uint8),
                np.full(clash.size, DISJOINT_FORCINGS, np.uint8),
            ]
        ),
        blocked=np.flatnonzero(blocked[batch.group]),
    )


def wake(scopes: dict[str, np.ndarray], facts: dict[str, np.ndarray]) -> int:
    """Add located facts to the guard scopes in place, and return how many (scope, reading) memberships are new.

    A scope named by one guard gains the readings that guard is located on. A conjunctive scope (`a&b`) gains a
    reading when each of its guards is located on that reading or is itself a scope that already holds for it. The
    scopes are boolean masks over readings, as `guards.scopes` returns them.
    """
    added = 0
    for name, mask in scopes.items():
        parts = name.split("&")
        located = [facts[p] for p in parts if p in facts]
        if not located:
            continue
        rows = np.unique(np.concatenate(located))
        holds = np.ones(rows.size, dtype=bool)
        for part in parts:
            here = np.isin(rows, facts[part]) if part in facts else np.zeros(rows.size, dtype=bool)
            if part != name and part in scopes:
                here |= scopes[part][rows]
            holds &= here
        new = rows[holds & ~mask[rows]]
        mask[new] = True
        added += int(new.size)
    return added
