"""Reading-level restrictions as relations, so they close with the laws (design E2, E4).

A source that states a value of one reading writes a restriction: cell (rows[i], cols[i]) keeps only the states in
allowed[i], by the source rule rules[i]. The source lenses (`projection.Restrictions`) and the NSM content
(`nsm.Compiled`) both produce them. Closure takes relations, so each (rule, bank, states) becomes a one-bank
relation over exactly the readings it restricts: closure then names the source rule as the cause of each removal and
wakes the laws that read the bank.
"""

from __future__ import annotations

import numpy as np

from .cells import BANKS, BIT_NAMES, NEG, POS, SILENT, ZERO
from .relations import Relation

_STATES = (POS, NEG, ZERO, SILENT)


def label(mask: int) -> str:
    """A mask as its state names, e.g. "+1|-1"."""
    return "|".join(BIT_NAMES[s] for s in _STATES if int(mask) & s)


def restriction_relations(restrictions, n: int, prefix: str = "") -> tuple[tuple[Relation, ...], dict[str, np.ndarray]]:
    """Each (rule, bank, mask) of `restrictions` as a one-bank relation over the readings it restricts.

    `restrictions` has `rows`, `cols`, `allowed`, `rules`, `rule_ids` and `warrants`. The relation is named
    `prefix + rule_id` and its scope `prefix + rule_id:bank:states`, a boolean mask over the `n` readings.
    """
    relations, scopes = [], {}
    keys = np.stack(
        [
            np.asarray(restrictions.rules, dtype=np.int64),
            np.asarray(restrictions.cols, dtype=np.int64),
            np.asarray(restrictions.allowed, dtype=np.int64),
        ]
    )
    for rule, col, mask in np.unique(keys, axis=1).T if keys.size else ():
        rule_id, bank = restrictions.rule_ids[rule], BANKS[col]
        scope = f"{prefix}{rule_id}:{bank}:{label(int(mask))}"
        chosen = (keys[0] == rule) & (keys[1] == col) & (keys[2] == mask)
        scopes[scope] = np.zeros(n, dtype=bool)
        scopes[scope][np.asarray(restrictions.rows)[chosen]] = True
        allowed = tuple((s,) for s in _STATES if int(mask) & s)
        relations.append(Relation(f"{prefix}{rule_id}", (bank,), allowed, restrictions.warrants[rule], scope))
    return tuple(relations), scopes
