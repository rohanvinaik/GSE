"""Channels that extend a round beyond WordNet: nodes, edges, identity classes, obligations and facts (design E8).

The round runner (`scripts/rebuild_lexicon.py`) composes its WordNet graph with extensions. The Wiktionary binding
(`wiktionary_binding.py`) is one:

- its edges join the graph in the families `inheritance` declares for them (`aligned`, `form_of`, `alt_of`,
  `sense_synonym`, `wiktionary_hypernym`), each at the standing of its warrant. A binding that marks its links'
  standing is followed. For one that does not: the binding writes a `form_of` or `alt_of` edge only when its target
  has a single reading, so the edge is Wiktionary's own statement and is stated (TrialLedger: "Known is a source
  fact"); an anchor alignment is always proposed; every other family keeps the graph's default. An edge in a family
  the graph does not declare is left out and counted;
- its identity classes go to `inheritance.settle`'s `classes`, where the readings of one meaning are one candidate
  of an obligation. The classes the stated identities join act in both layers (`known_classes`: the binding's own
  when it gives them, else `Graph.stated_identities`); every class acts in the interpolated layer;
- its topic facts (`wiktionary_topic=<t>`) join the scopes, where they type discovery's candidates;
- its identity obligations ("this sense is one of these readings", F073 over meanings) are resolved between rounds,
  never inside one: the graph is fixed within a round's fixed point. The resolver (`resolve_identities`, over the
  inheritance implementer's `identities.resolve`) reads the settled round's known layer and returns the links that
  now have one target, proposed, with the obligations still open.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from . import identities, inheritance

STATED_FAMILIES = frozenset({"form_of", "alt_of"})  # single-target by the binding's construction


@dataclass
class Extension:
    """What a channel adds to the round. `groups`: node key -> reading rows; `links`: edges as the graph builder
    takes them; `obligations`: reading obligations (`obligations.Obligation`); `facts`: guard name -> boolean mask over
    readings; `classes`: an identity class per reading, or None; `known_classes`: the classes stated identities join,
    or None to take them from the graph; `identity_obligations`: what the resolver reads; `receipt`: its counts."""

    name: str
    groups: dict[str, list[int]] = field(default_factory=dict)
    links: list[tuple] = field(default_factory=list)
    obligations: list = field(default_factory=list)
    facts: dict[str, np.ndarray] = field(default_factory=dict)
    classes: np.ndarray | None = None
    known_classes: np.ndarray | None = None
    identity_obligations: list = field(default_factory=list)
    receipt: dict = field(default_factory=dict)


@dataclass
class Resolved:
    """A resolver's answer between two rounds: links to add, the identity obligations still open, how many have no
    target left, and the reading pairs a resolved identity joins into one class."""

    links: list[tuple] = field(default_factory=list)
    pending: list = field(default_factory=list)
    conflicts: int = 0
    joins: list[tuple[int, int]] = field(default_factory=list)


# (settlement, readings, pending identity obligations) -> Resolved
Resolver = Callable[[inheritance.Settlement, tuple, list], Resolved]


def _mask(rows, n: int) -> np.ndarray:
    rows = np.asarray(rows)
    if rows.dtype == bool:
        return rows.copy()
    out = np.zeros(n, dtype=bool)
    out[rows.astype(np.int64)] = True
    return out


def declared_families() -> frozenset[str]:
    return frozenset(f.name for f in inheritance.FAMILIES)


def from_binding(binding, readings, families: frozenset[str] | None = None) -> Extension:
    """The Wiktionary binding as an extension: its edges in declared families, its classes, its topic facts as
    masks, and its identity obligations for the resolver."""
    families = declared_families() if families is None else families
    links = [_with_standing(link) for link in binding.links if link[0] in families]
    left_out = Counter(link[0] for link in binding.links if link[0] not in families)
    n = len(readings)
    receipt = binding.census(readings)
    receipt["links_in_declared_families"] = dict(sorted(Counter(link[0] for link in links).items()))
    receipt["links_by_standing"] = dict(sorted(Counter(f"{link[0]}:{_standing(link)}" for link in links).items()))
    receipt["links_left_out_undeclared_family"] = dict(sorted(left_out.items()))
    receipt["identity_obligations"] = len(binding.obligations)
    return Extension(
        name="wiktionary",
        groups=dict(binding.groups),
        links=links,
        facts={name: _mask(rows, n) for name, rows in binding.facts.items()},
        classes=np.asarray(binding.classes, dtype=np.int64),
        known_classes=_optional(getattr(binding, "known_classes", None)),
        identity_obligations=list(binding.obligations),
        receipt=receipt,
    )


def _with_standing(link: tuple) -> tuple:
    if len(link) > 3:
        return link
    family, giver, receiver = link
    if family in STATED_FAMILIES:
        return (family, giver, receiver, inheritance.STATED)
    if family == "aligned":
        return (family, giver, receiver, inheritance.PROPOSED)
    return link


def _optional(classes) -> np.ndarray | None:
    return None if classes is None else np.asarray(classes, dtype=np.int64)


def _standing(link: tuple) -> str:
    return link[3] if len(link) > 3 else "graph default"


def resolve_identities(settlement, readings, pending) -> Resolved:
    """`identities.resolve` on the settled round's known layer (a link resolved from interpolated values would rest on
    the defaults it then carries). Located and conflicting obligations leave the pending list; the others stay."""
    resolution = identities.resolve(settlement.known.masks, readings, pending)
    ids = [r if isinstance(r, str) else r.reading_id for r in readings]
    row_of = {rid: i for i, rid in enumerate(ids)}

    def key(kind, reading, premises):
        return (kind, reading, tuple(premises))

    done = {key(e["kind"], e["reading"], e["premises"]) for e in resolution.located + resolution.conflicts}
    left = [o for o in pending if key(o.kind, ids[o.row], o.premises) not in done]
    identity = {f.name for f in inheritance.FAMILIES if f.identity}
    joins = [(row_of[e["reading"]], row_of[e["target"]]) for e in resolution.located if e["kind"] in identity]
    return Resolved(list(resolution.links), left, len(resolution.conflicts), joins)


def wiktionary(readings) -> Extension:
    """The real binding over the cohort (the pinned Wiktionary dump and WordNet 3.0)."""
    from . import wiktionary_binding

    senses = wiktionary_binding.load_senses(readings)
    return from_binding(wiktionary_binding.bind(readings, senses, wiktionary_binding.wordnet_taxonomy()), readings)


def join_classes(n: int, arrays, pairs=()) -> np.ndarray | None:
    """One identity class per reading (the least row of the class), joining every class array given and every pair:
    two readings share a class when any array or pair puts them in one. None when nothing joins two readings."""
    arrays = [np.asarray(a, dtype=np.int64) for a in arrays if a is not None]
    pairs = list(pairs)
    if not arrays and not pairs:
        return None
    parent = np.arange(n, dtype=np.int64)

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = int(parent[x])
        return x

    for classes in arrays:
        order = np.argsort(classes, kind="stable")
        same = classes[order][1:] == classes[order][:-1]
        for a_row, b_row in zip(order[:-1][same].tolist(), order[1:][same].tolist()):
            a, b = find(a_row), find(b_row)
            if a != b:
                parent[max(a, b)] = min(a, b)
    for a_row, b_row in pairs:
        a, b = find(int(a_row)), find(int(b_row))
        if a != b:
            parent[max(a, b)] = min(a, b)
    out = np.array([find(i) for i in range(n)], dtype=np.int64)
    return out if (out != np.arange(n)).any() else None
