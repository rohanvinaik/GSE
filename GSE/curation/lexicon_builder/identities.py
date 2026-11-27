"""Link obligations, resolved between rounds (design E8, F073; the lead's ruling of 2026-11-27).

A Wiktionary sense whose `form_of`, `alt_of`, synonym or hypernym target word has several readings in its part of
speech says "it is linked to one of these": F073's form over meanings rather than over one bank. The graph is fixed
inside a round's fixed point, so the resolution runs between rounds. The runner calls `resolve` on a closed state;
when one target remains, it adds the link for the next round's graph, at the standing of its warrant: proposed, since
it was resolved among several targets (a stated identity names a single target).

A target is excluded when the link could not hold on the closed state:

- for an identity family (`aligned`, `form_of`, `alt_of`, which carry every state), when some bank has no state legal
  for both: one meaning has one state per bank;
- for any other family, when a decided state the link would carry is not legal where it lands: from the target to
  the sense (a hypernym's +1, -1 or 0 onto its kind), and from the sense to the target too when the family is
  mirrored (`sense_synonym`, +1 and -1 each way).

No target left is a conflict, recorded and resolved to nothing; two or more stay open. The known layer is the state
to resolve on: a link resolved from interpolated values would rest on the defaults it then carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

import numpy as np

from .cells import _POPCOUNT
from .inheritance import FAMILIES, PROPOSED


@dataclass(frozen=True, eq=False)
class IdentityObligation:
    """The sense `row` is linked, by a link of family `kind`, to one of `targets`: an identity (it has the meaning of
    one of them) or a kind-of (it is a kind of one of them)."""

    kind: str
    row: int
    targets: np.ndarray
    premises: tuple[str, ...] = ()


@dataclass(frozen=True)
class Resolution:
    """The links to add for the next round (both directions), what each located obligation resolved to, its
    conflicts, and how many stay open."""

    links: tuple[tuple[str, str, str, str], ...]  # (family, giver, receiver, standing)
    located: tuple[dict, ...]
    conflicts: tuple[dict, ...]
    open: int


def _rid(reading) -> str:
    return reading if isinstance(reading, str) else reading.reading_id


def node_key(reading) -> str:
    """The inheritance graph's node for a reading: its synset for a WordNet reading, else its own reading id."""
    rid = _rid(reading)
    return unquote(rid.rsplit(":", 1)[1]) if rid.startswith("wordnet:") else rid


def _compatible(sense: np.ndarray, target: np.ndarray, family) -> np.ndarray:
    """Per (sense, target) pair of mask rows: whether the link could hold under the family's carry rule."""
    if family.identity:
        return ((target & sense) != 0).all(axis=1)
    carry = family.carry_row()
    given = np.where(_POPCOUNT[target] == 1, target & carry, 0)
    ok = ((given & ~sense) == 0).all(axis=1)
    if family.mirrored:
        back = np.where(_POPCOUNT[sense] == 1, sense & carry, 0)
        ok &= ((back & ~target) == 0).all(axis=1)
    return ok


def resolve(masks: np.ndarray, readings, obligations, families=FAMILIES) -> Resolution:
    """Each link obligation against `masks` (readings x banks): the one remaining target becomes a proposed link
    (both directions for a mirrored family, else from the target to the sense); none is a conflict; several stay
    open. Vectorised over every (obligation, target) pair."""
    obligations = tuple(obligations)
    by_name = {f.name: i for i, f in enumerate(families)}
    unknown = sorted({o.kind for o in obligations} - set(by_name))
    if unknown:
        raise ValueError(f"UNKNOWN_FAMILIES {unknown}")
    targets = [np.unique(np.asarray(o.targets, dtype=np.int64)) for o in obligations]
    sizes = np.array([t.size for t in targets], dtype=np.int64)
    pair_ob = np.repeat(np.arange(len(obligations), dtype=np.int64), sizes)
    pair_target = np.concatenate(targets) if targets else np.zeros(0, dtype=np.int64)
    sense_rows = np.array([o.row for o in obligations], dtype=np.int64)
    ob_family = np.array([by_name[o.kind] for o in obligations], dtype=np.int64)
    fits = np.zeros(pair_ob.size, dtype=bool)
    for i in np.unique(ob_family).tolist():
        sel = ob_family[pair_ob] == i
        fits[sel] = _compatible(masks[sense_rows[pair_ob[sel]]], masks[pair_target[sel]], families[i])
    count = np.bincount(pair_ob[fits], minlength=len(obligations))
    chosen = np.full(len(obligations), -1, dtype=np.int64)
    one = fits & (count[pair_ob] == 1)
    chosen[pair_ob[one]] = pair_target[one]
    links, located, conflicts = [], [], []
    for k in np.flatnonzero(count <= 1).tolist():
        o = obligations[k]
        entry = {"kind": o.kind, "reading": _rid(readings[o.row]), "premises": list(o.premises)}
        if count[k] == 0:
            conflicts.append(entry | {"targets": [_rid(readings[t]) for t in targets[k].tolist()]})
            continue
        sense, target = node_key(readings[o.row]), node_key(readings[int(chosen[k])])
        links.append((o.kind, target, sense, PROPOSED))
        if families[ob_family[k]].mirrored:
            links.append((o.kind, sense, target, PROPOSED))
        located.append(entry | {"target": _rid(readings[int(chosen[k])])})
    return Resolution(tuple(dict.fromkeys(links)), tuple(located), tuple(conflicts), int((count >= 2).sum()))
