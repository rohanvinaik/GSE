"""Inheritance across readings: typed edges, defaults, suspensions and the joint round (design E8).

Rohan, 2026-11-26 19:38: sub-kinds are "the *easiest* tier"; the build propagates "rules that define how banks are
implicitly decided and filled by other sources of information, like other banks"; WordNet is not the gold standard,
only a jump-start ("I've told you repeatedly not to focus on WordNet as if its the gold standard"). 19:42:
"TrialLedger's constraint propogation ideas are how we allow sub-kind inheritcance without introducing spurious and
incorrect additions". TrialLedger: "Interpolated is a declared default or a conclusion resting on interpolation";
"Defaults have declared applicability and defeaters; conflicting defaults are suspended and reported, not selected by
order."

Nodes. A node is one unit of meaning, here a WordNet synset; its members are the cohort's readings of it, one per
lemma. A synset with no cohort reading is still a node, a transit node holding no value of its own, so a chain
through it is not cut (`animal.n.01` reaches 4,016 synsets, of which 1,881 have cohort readings).

Families and what they carry. Every edge runs from the node whose value is carried to the node that receives it, and
belongs to a family that declares the states it carries.

- `hypernym`, `instance_hypernym` (kind-of), from the hypernym to the hyponym or instance. Carries +1, -1 and 0.
  Warrant: NSM's molecules, "X [m] of one kind": a kind of X is an X, so a component X's definition has (+1 or -1)
  the kind has, and what X's definition explicitly excludes (0, F118: "0 is explicit absence") the kind excludes.
  The lead's ruling of 2026-11-27 accepts the zeros: a hub's orthogonality is definitional for its kinds (it
  supersedes the earlier build's "zeros are not inherited", commit 559bfe6). X's SILENT is never carried: a kind may
  use a prime its hub never mentions. NSM's own subkind explications refute silence inheritance: 10 of 11 subkinds
  use primes their hub never uses (`docs/verification/2026-11-26-hub-silence-vs-nsm-subkinds.json`).
- `similar_to`, from an adjective head (pos `a`) to its satellite (pos `s`), never the reverse (nltk lists the link
  from both ends). Carries +1, -1 and 0. Warrant: WordNet's adjective cluster, in which a satellite is similar in
  meaning to its head and refines it (`wet.a.01` -> `damp.s.01`), the adjective analogue of kind-of; the head's
  silence is not carried, for the same reason as a hub's.
- `entails`, from the entailed verb to the entailing one (`sleep.v.01` -> `snore.v.01`). Carries +1 and -1.
  Warrant: WordNet's entailment, in which X cannot be done unless Y is or has been done, by the same subject, so Y's
  components are part of X's own meaning. Y's zeros are not carried, since X adds to Y and can add what Y excludes,
  and Y's silence is not either.
- `causes`, from the effect to the causing verb (`die.v.01` -> `kill.v.01`). Carries the effect's +1 and -1, on
  every bank but CAUSE. Warrant: `native_predicate_policy.lexical_component` (`bank_laws.json`, founder-approved)
  counts an event's effect on another participant as part of the word's content ("A negative state for another
  participant or stage does not assert that the word definition lacks the relation"), which is how kill has ALIVE
  -1 from VerbNet (the lead's ruling of 2026-11-27, superseding this family's earlier empty carry). No authored
  contract lets WordNet write CAUSE, so the link itself writes none. The effect's zeros and silence are not
  carried: the causer adds its own action to the effect.
- synonymy: the same synset under different lemmas is one definition, equality of meaning, so it carries every
  state, SILENT included. It is the node itself: its members' masks are intersected.

The Wiktionary binding (task 6.2, `wiktionary_binding.py`) adds proposed identities of meaning between a Wiktionary
sense (a node of its own) and a WordNet or Wiktionary reading, emitted in both directions. Design E8: "An alignment is
a proposed identity: content crosses it as an interpolated default, suspended on any conflict", which is what every
edge here is.

- `aligned`: the Wiktionary sense and the one WordNet reading of the same lemma and part of speech that has a
  linked word's synset among its kind-of ancestors (the exact anchor alignment). Carries every state, SILENT
  included: it claims one meaning, as synonymy does.
- `form_of`, `alt_of`: Wiktionary's own statement that the sense is an inflected form or an alternative spelling
  of its target, bound only when the target lemma and part of speech has one reading. Carries every state: a form
  or a spelling of a word has that word's meaning.
- `sense_synonym`: a Wiktionary sense-level synonym, bound to a single reading. Carries +1 and -1 only. A listed
  synonym is a near-synonym, not an identity (the binding leaves it out of the identity classes for that reason):
  the two share their components, but what each excludes and what each leaves unsaid can differ, so zeros and
  silence stay with their own word. Degree is the open risk (a listed synonym can be stronger or weaker), to be
  audited against NSM.
- `wiktionary_hypernym`: a Wiktionary sense-level `hypernyms` entry, from the hypernym word's single reading of the
  same part of speech to the sense. Carries +1, -1 and 0, as kind-of does, never SILENT. Warrant: the lead's decision
  of 2026-11-27, "Sense-level `hypernyms` are a kind-of source the Wiktionary editors state ... It carries what kind-of
  carries." Not mirrored, and it joins no identity class. A hypernym word with several readings is a link
  obligation, resolved between rounds (`identities.resolve`).

Standing (the lead's ruling of 2026-11-27). A link may carry a standing, `stated` or `proposed`, as a fourth element.
`form_of` or `alt_of` with a single target reading is stated: Wiktionary's own structured field names it, and
TrialLedger's "Known is a source fact or a strict conclusion from known premises" holds of it. `aligned`, and a
`form_of` or `alt_of` resolved among several targets (`identities.resolve`), is proposed; an `aligned` link is never
stated. An identity link without a standing is proposed, so nothing is promoted by omission. Standing decides the
identity classes `settle` counts obligations by: classes joined by stated identities (`known_classes`) act in both
layers, and every other class only in the interpolated layer. Content crossing any link is still an interpolated
default.

Defaults. A node emits its own value where its mask is decided (the kind's own value is what its kinds inherit);
elsewhere it passes on the proposals reaching it that are still legal for it. Proposals are ORed over every incoming
edge to a fixed point. This is monotone, so it terminates on cycles (`breathe.v.01` entails `inhale.v.02`, which is a
kind of it) and involves no order. A proposal applies to a node's readings only when exactly one state reaches the
cell, it is legal under the known state, and it fits the current state. Otherwise it is suspended and reported:

- `defaults disagree`: two states reach one cell, at any depth; nothing is chosen;
- `contradicts known`: the one state reaching the cell is not legal under the known state, which stands;
- `joint conflict`: defaults that are each legal under the known state are not legal together: a state that fits
  the known state but not what interpolation already made of the node, an empty cell the known layer does not have,
  an obligation the known layer satisfies and the interpolated layer does not, or a consequence of other defaults
  that removes one of two disagreeing states. Every default that landed on the nodes involved is suspended and the
  round is replayed from the known state;
- `synonyms disagree`: the known states of one synset's readings have no state in common; they are not equalized.

Known and interpolated. The known state is the closure of the premises under the laws and the obligations. The
interpolated state is the known state plus defaults, closed again. Removal is monotone, so every cell the
interpolated state holds narrower than the known state rests on at least one default: those cells are the
interpolated ones (`Settlement.interpolated`), and the cells a default or a synonym narrowed directly are
`Settlement.inherited`.

Defeaters. A declared source misfiling carries nothing: a link (child, parent) in any family, or an origin from which
nothing carries (its own values and what would pass through it). The list starts empty; candidates come from the
NSM audit and are decided by review.

Lineage (`lineage.py`): every carried value records its origin, so a retraction or the audit can walk it back. The
audit against NSM (`nsm_audit.py`) judges carried values against the explications as complete meanings.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import unquote

import numpy as np

from . import obligations as ob
from .cells import _POPCOUNT, ALL, BANKS, BIT_NAMES, NEG, POS, ZERO, State
from .closure import close
from .lineage import Lineage, trace
from .lineage import origins as lineage_origins

KIND_OF = POS | NEG | ZERO
CONTENT = POS | NEG
STATED, PROPOSED = "stated", "proposed"
_WIDTH = len(BANKS)


@dataclass(frozen=True)
class Family:
    """An edge family: the states it carries from the giving node to the receiving one, the banks it never writes,
    and its warrant."""

    name: str
    carries: int
    warrant: str
    never_writes: frozenset[str] = frozenset()
    identity: bool = False  # a claim that the two nodes have one meaning; its links carry a standing
    mirrored: bool = False  # its links are emitted in both directions (a symmetric relation)

    def carry_row(self) -> np.ndarray:
        """The states it carries on each bank."""
        return np.array([0 if bank in self.never_writes else self.carries for bank in BANKS], dtype=np.uint8)


FAMILIES: tuple[Family, ...] = (
    Family("hypernym", KIND_OF, "kind-of: NSM 'X [m] of one kind'; a hub's silence is refuted (module docstring)"),
    Family("instance_hypernym", KIND_OF, "kind-of: an instance of X is an X (module docstring)"),
    Family("similar_to", KIND_OF, "WordNet adjective cluster: a satellite refines its head (module docstring)"),
    Family("entails", CONTENT, "WordNet entailment: same subject, the entailed event is part (module docstring)"),
    Family(
        "aligned",
        ALL,
        "Wiktionary sense aligned to one WordNet reading: a proposed identity",
        identity=True,
        mirrored=True,
    ),
    Family("form_of", ALL, "Wiktionary form_of: a form of a word has its meaning", identity=True, mirrored=True),
    Family("alt_of", ALL, "Wiktionary alt_of: a spelling of a word has its meaning", identity=True, mirrored=True),
    Family(
        "sense_synonym",
        CONTENT,
        "Wiktionary sense synonym: near-synonymy shares content only (module docstring)",
        mirrored=True,
    ),
    Family(
        "wiktionary_hypernym",
        KIND_OF,
        "Wiktionary sense-level hypernyms: a kind-of the editors state (the lead's decision, 2026-11-27)",
    ),
    Family(
        "causes",
        CONTENT,
        "native_predicate_policy.lexical_component: the effect on another participant is content (module docstring)",
        frozenset({"CAUSE"}),
    ),
)
SYNONYMY = Family("synonymy", ALL, "one synset, one definition: equality of meaning (module docstring)")


@dataclass(frozen=True)
class Defeater:
    """A declared source misfiling and its reason.

    With `child`, the link from `parent` to `child` carries nothing, in any family. Without it, `parent` is an origin
    that is no genus for its kinds: nothing carries out of it, neither its own values nor what would pass through it.
    """

    parent: str
    reason: str
    child: str | None = None


DEFEATERS: tuple[Defeater, ...] = ()

DISAGREE, KNOWN, JOINT, SYNONYMS = 1, 2, 4, 8
REASONS = {
    DISAGREE: "defaults disagree",
    KNOWN: "contradicts known",
    JOINT: "joint conflict",
    SYNONYMS: "synonyms disagree",
}


def reason_names(code: int) -> list[str]:
    return [name for bit, name in REASONS.items() if code & bit]


def state_names(mask: int) -> list[str]:
    return [name for bit, name in BIT_NAMES.items() if mask & bit]


# ---------------------------------------------------------------------------------------------------- the graph


def _span(keys: np.ndarray, starts: np.ndarray, total: int, key: int) -> slice:
    """The slice of a sorted, grouped array that belongs to `key` (empty when the key has no group)."""
    i = int(np.searchsorted(keys, key))
    if i == keys.size or keys[i] != key:
        return slice(0, 0)
    return slice(int(starts[i]), int(starts[i + 1]) if i + 1 < keys.size else total)


@dataclass(frozen=True)
class Graph:
    """Nodes with their member readings, and typed edges between nodes, as arrays."""

    keys: tuple[str, ...]
    rows: np.ndarray  # member reading rows, grouped by node
    node_of: np.ndarray  # the node of each member, non-decreasing
    owned: np.ndarray  # the nodes with at least one member
    starts: np.ndarray  # the first member of each owned node
    src: np.ndarray  # edges, sorted by receiving node
    dst: np.ndarray
    family: np.ndarray
    targets: np.ndarray  # the nodes with incoming edges
    edge_starts: np.ndarray  # the first edge of each target
    carries: np.ndarray  # (edges, banks) the states each edge carries on each bank
    families: tuple[Family, ...]
    stated: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))  # each edge's standing
    defeated: tuple[tuple[str, str, str, str], ...] = field(default=())  # (family, parent, child, reason)

    def node_masks(self, masks: np.ndarray) -> np.ndarray:
        """Each node's mask: the intersection of its members' masks; ALL for a transit node."""
        out = np.full((len(self.keys), _WIDTH), ALL, dtype=np.uint8)
        if self.rows.size:
            out[self.owned] = np.bitwise_and.reduceat(masks[self.rows], self.starts, axis=0)
        return out

    def node_any(self, flags: np.ndarray) -> np.ndarray:
        """Per node and bank: whether any member reading's flag is set (`flags` is readings x banks)."""
        return self.member_any(flags[self.rows])

    def member_any(self, flags: np.ndarray) -> np.ndarray:
        """Per node and bank: whether any member's flag is set (`flags` is members x banks, in member order)."""
        out = np.zeros((len(self.keys), _WIDTH), dtype=bool)
        if self.rows.size:
            out[self.owned] = np.bitwise_or.reduceat(flags.astype(np.uint8), self.starts, axis=0) > 0
        return out

    def stated_identities(self, n_readings: int) -> np.ndarray:
        """A component id per reading: readings whose nodes are joined by stated identity links share one; every
        other reading is its own (its row)."""
        identity = np.array([f.identity for f in self.families], dtype=bool)
        sel = identity[self.family] & self.stated if self.family.size else np.zeros(0, dtype=bool)
        label = np.arange(len(self.keys), dtype=np.int64)
        a, b = self.src[sel], self.dst[sel]
        while a.size:
            low = np.minimum(label[a], label[b])
            if (low == label[a]).all() and (low == label[b]).all():
                break
            np.minimum.at(label, a, low)
            np.minimum.at(label, b, low)
        out = np.arange(n_readings, dtype=np.int64)
        joined = np.bincount(label, minlength=len(self.keys)) > 1
        node_label = label[self.node_of]
        on = joined[node_label]
        out[self.rows[on]] = n_readings + node_label[on]
        return out

    def members(self, node: int) -> np.ndarray:
        """The member reading rows of `node` (none for a transit node)."""
        return self.rows[_span(self.owned, self.starts, self.rows.size, node)]

    def incoming(self, node: int) -> np.ndarray:
        """The edges into `node`."""
        return np.arange(*_span(self.targets, self.edge_starts, self.dst.size, node).indices(self.dst.size))

    def counts(self) -> dict:
        """Links per family (all, and with both ends owning readings), reading pairs, nodes and synonym groups."""
        owned = np.zeros(len(self.keys), dtype=bool)
        owned[self.owned] = True
        size = np.zeros(len(self.keys), dtype=np.int64)
        np.add.at(size, self.node_of, 1)
        out = {}
        for i, fam in enumerate(self.families):
            sel = self.family == i
            both = sel & owned[self.src] & owned[self.dst]
            out[fam.name] = {
                "links": int(sel.sum()),
                "links_between_readings": int(both.sum()),
                "reading_pairs": int((size[self.src[both]] * size[self.dst[both]]).sum()),
                "carries": state_names(fam.carries),
                "never_writes": sorted(fam.never_writes),
                "stated": int((sel & self.stated).sum()) if self.stated.size else 0,
            }
        groups = size[size >= 2]
        out[SYNONYMY.name] = {
            "synsets_with_two_or_more_readings": int(groups.size),
            "reading_pairs": int((groups * (groups - 1) // 2).sum()),
            "carries": state_names(SYNONYMY.carries),
        }
        out["nodes"] = {"all": len(self.keys), "owning_readings": int(owned.sum()), "transit": int((~owned).sum())}
        out["defeated_links"] = len(self.defeated)
        return out


def _defeat(links, defeaters):
    pairs = {(d.parent, d.child): d for d in defeaters if d.child is not None}
    origins = {d.parent: d for d in defeaters if d.child is None}
    kept, gone, used = [], [], set()
    for link in links:
        family, parent, child = link
        d = pairs.get((parent, child)) or origins.get(parent)
        if d is None:
            kept.append(link)
        else:
            used.add(d)
            gone.append((family, parent, child, d.reason))
    unused = [d for d in defeaters if d not in used]
    if unused:
        raise ValueError(f"DEFEATER_MATCHES_NO_LINK {unused}")
    return kept, gone


def build(groups: dict[str, list[int]], links, defeaters=DEFEATERS, families=FAMILIES) -> Graph:
    """The graph over `groups` (node key -> member reading rows) and `links` ((family, parent, child) node keys).

    Nodes named only by links are transit nodes. A defeater that matches no link is refused.
    """
    index = {f.name: i for i, f in enumerate(families)}
    standing: dict[tuple[str, str, str], bool] = {}
    for link in links:
        family, parent, child, *rest = tuple(link)
        if family not in index:
            raise ValueError(f"UNKNOWN_FAMILIES {[family]}")
        given = rest[0] if rest else (PROPOSED if families[index[family]].identity else STATED)
        if given not in (STATED, PROPOSED):
            raise ValueError(f"UNKNOWN_STANDING {given}")
        if family == "aligned" and given == STATED:
            raise ValueError("ALIGNMENT_IS_PROPOSED")
        key = (family, parent, child)
        standing[key] = standing.get(key, False) or given == STATED
    links = list(standing)
    kept, gone = _defeat(links, defeaters)
    keys = tuple(sorted(set(groups) | {p for _, p, _ in kept} | {c for _, _, c in kept}))
    node = {k: i for i, k in enumerate(keys)}
    owned = sorted(node[k] for k, rows in groups.items() if len(rows))
    member_rows = [np.unique(np.asarray(groups[keys[v]], dtype=np.int64)) for v in owned]
    sizes = np.array([m.size for m in member_rows], dtype=np.int64)
    rows = np.concatenate(member_rows) if member_rows else np.zeros(0, dtype=np.int64)
    if np.unique(rows).size != rows.size:
        raise ValueError("READING_IN_TWO_NODES")
    src = np.array([node[p] for _, p, _ in kept], dtype=np.int64)
    dst = np.array([node[c] for _, _, c in kept], dtype=np.int64)
    fam = np.array([index[f] for f, _, _ in kept], dtype=np.int8)
    stated = np.array([standing[link] for link in kept], dtype=bool)
    order = np.argsort(dst, kind="stable")
    src, dst, fam, stated = src[order], dst[order], fam[order], stated[order]
    targets, edge_starts = np.unique(dst, return_index=True)
    rules = np.stack([f.carry_row() for f in families]) if families else np.zeros((0, _WIDTH), np.uint8)
    carries = rules[fam] if fam.size else np.zeros((0, _WIDTH), np.uint8)
    return Graph(
        keys=keys,
        rows=rows,
        node_of=np.repeat(np.array(owned, dtype=np.int64), sizes),
        owned=np.array(owned, dtype=np.int64),
        starts=np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64) if sizes.size else sizes,
        src=src,
        dst=dst,
        family=fam,
        targets=targets,
        edge_starts=edge_starts,
        carries=carries,
        families=tuple(families),
        stated=stated,
        defeated=tuple(gone),
    )


def wordnet_groups(readings) -> dict[str, list[int]]:
    """Synset -> rows of the cohort's WordNet readings (`wordnet:<quote(lemma)>:<quote(synset)>`)."""
    out: dict[str, list[int]] = defaultdict(list)
    for row, reading in enumerate(readings):
        rid = reading if isinstance(reading, str) else reading.reading_id
        if rid.startswith("wordnet:"):
            out[unquote(rid.rsplit(":", 1)[1])].append(row)
    return dict(out)


def wordnet_links(wn=None):
    """WordNet's own links, as (family, giving synset, receiving synset), over every synset (nltk, WordNet 3.0)."""
    if wn is None:
        from nltk.corpus import wordnet as wn
    for synset in wn.all_synsets():
        name = synset.name()
        for h in synset.hypernyms():
            yield ("hypernym", h.name(), name)
        for h in synset.instance_hypernyms():
            yield ("instance_hypernym", h.name(), name)
        if synset.pos() == "s":
            for head in synset.similar_tos():
                if head.pos() == "a":
                    yield ("similar_to", head.name(), name)
        for entailed in synset.entailments():
            yield ("entails", entailed.name(), name)
        for effect in synset.causes():
            yield ("causes", effect.name(), name)


# ------------------------------------------------------------------------------------------------ one pass


@dataclass(frozen=True)
class Carry:
    """One inheritance pass: the reading cells it narrowed, and per node and bank what landed and what was
    suspended."""

    rows: np.ndarray
    cols: np.ndarray
    old: np.ndarray
    new: np.ndarray
    landed: np.ndarray  # (nodes, banks) a default narrowed the node's readings
    equalized: np.ndarray  # (nodes, banks) synonymy narrowed one of the node's readings
    suspended: np.ndarray  # (nodes, banks) reason bits
    proposals: np.ndarray  # (nodes, banks) the states that reached each node

    @property
    def changed(self) -> int:
        return int(self.rows.size)


def emissions(node_masks: np.ndarray, proposals: np.ndarray) -> np.ndarray:
    """What each node gives its receivers: its own value where decided, else the proposals still legal for it."""
    return np.where(_POPCOUNT[node_masks] == 1, node_masks, proposals & node_masks)


def proposals(graph: Graph, node_masks: np.ndarray) -> np.ndarray:
    """The OR, over every incoming edge, of the states carried to each node, to a fixed point."""
    p = np.zeros_like(node_masks)
    if graph.src.size == 0:
        return p
    carries = graph.carries
    while True:
        given = emissions(node_masks, p)[graph.src] & carries
        incoming = np.bitwise_or.reduceat(given, graph.edge_starts, axis=0)
        if (incoming == p[graph.targets]).all():
            return p
        p[graph.targets] = incoming


def carry(state: State, graph: Graph, known: State | None = None, held=None, held_equal=None) -> Carry:
    """Run one inheritance pass on `state` in place and return what changed.

    `known` is the known layer the defaults are checked against (the state itself when omitted). `held` and
    `held_equal` (nodes x banks) are cells where defaults, or synonym equality, are suspended.
    """
    known = state if known is None else known
    shape = (len(graph.keys), _WIDTH)
    held = np.zeros(shape, dtype=bool) if held is None else held
    held_equal = np.zeros(shape, dtype=bool) if held_equal is None else held_equal
    current = graph.node_masks(state.masks)
    known_nodes = graph.node_masks(known.masks)
    known_broken = graph.node_any(known.masks == 0)
    p = proposals(graph, current)
    owned = np.zeros(shape[0], dtype=bool)
    owned[graph.owned] = True
    reaching = owned[:, None] & (p != 0) & ~known_broken
    count = _POPCOUNT[p]
    disagree = reaching & (count >= 2)
    single = reaching & (count == 1)
    against_known = single & ((p & known_nodes) == 0)
    joint = single & ~against_known & ((p & current) == 0)
    applies = single & ~against_known & ~joint & ~held
    synonyms = owned[:, None] & (known_nodes == 0) & ~known_broken
    suspended = (
        np.where(disagree, DISAGREE, 0)
        | np.where(against_known & ~synonyms, KNOWN, 0)
        | np.where(joint, JOINT, 0)
        | np.where(synonyms, SYNONYMS, 0)
    ).astype(np.uint8)
    target = np.where(applies, current & p, current)
    equal_ok = ~held_equal & (target != 0)

    of = graph.node_of
    before = state.masks[graph.rows]
    by_default = np.where(applies[of], p[of], ALL)
    by_synonym = np.where(equal_ok[of], target[of], ALL)
    after = before & by_default & by_synonym
    r, c = np.nonzero(after != before)
    rows = graph.rows[r]
    state.masks[rows, c] = after[r, c]
    return Carry(
        rows=rows,
        cols=c,
        old=before[r, c],
        new=after[r, c],
        landed=applies & ((current & p) != current),
        equalized=graph.member_any((before & by_synonym) != before),
        suspended=suspended,
        proposals=p,
    )


# ------------------------------------------------------------------------------------------- the joint round


@dataclass
class Settlement:
    """The joint round's result: the known layer, the interpolated layer, and every suspension with its reason."""

    known: State
    state: State
    graph: Graph
    inherited: np.ndarray  # readings x banks: a default or a synonym narrowed the cell directly
    reasons: np.ndarray  # nodes x banks: reason bits of every suspension reported in any round
    held: np.ndarray  # nodes x banks: defaults suspended
    held_equal: np.ndarray  # nodes x banks: synonym equality suspended
    proposals: np.ndarray  # nodes x banks: the states reaching each node in the final round
    known_conflicts: list[dict]  # obligation conflicts in the known layer
    identity_conflicts: list[
        dict
    ]  # (reading, bank) where a stated identity class's known states have nothing in common
    known_steps: list  # the known layer's steps in order (see `settle`)
    interpolated_conflicts: list[dict]  # obligation conflicts in the final interpolated layer
    known_scopes: dict  # guard scopes with the facts located in the known layer
    scopes: dict  # guard scopes with the facts located in the interpolated layer too
    landed: np.ndarray  # nodes x banks: a default landed on the node in the final round
    lineage: Lineage  # where every carried value came from
    receipt: dict

    @property
    def interpolated(self) -> np.ndarray:
        """Readings x banks: cells narrower than the known layer, which therefore rest on a default."""
        return self.state.masks != self.known.masks

    def origins(self) -> dict[str, np.ndarray]:
        """Arrays parallel to the inherited reading cells, one entry per origin (`lineage.origins`)."""
        return lineage_origins(
            self.graph, self.lineage, self.inherited & self.interpolated, self.landed, len(self.state.readings)
        )

    def suspensions(self) -> list[dict]:
        """Every suspended node cell: its reasons, the states reaching it, its known states, its readings, and the
        edges that gave each state."""
        g = self.graph
        given = emissions(g.node_masks(self.state.masks), self.proposals)
        known_nodes = g.node_masks(self.known.masks)
        names = [f.name for f in g.families]
        out = []
        for v, b in zip(*np.nonzero(self.reasons)):
            incoming = g.incoming(v)
            givers = [
                {"family": names[g.family[e]], "from": g.keys[g.src[e]], "states": state_names(int(s))}
                for e in incoming
                if (s := int(given[g.src[e], b] & g.carries[e, b]))
            ]
            out.append(
                {
                    "node": g.keys[v],
                    "bank": BANKS[b],
                    "reasons": reason_names(int(self.reasons[v, b])),
                    "reaching": state_names(int(self.proposals[v, b])),
                    "known": state_names(int(known_nodes[v, b])),
                    "readings": [self.state.readings[r] for r in g.members(v)],
                    "givers": givers,
                }
            )
        return out


def _check_classes(graph: Graph, n: int, classes, known_classes):
    """Known classes must rest on stated identities, and every class joining readings must keep their known joins."""
    if known_classes is not None:
        known_classes = np.asarray(known_classes, dtype=np.int64)
        pairs = np.unique(np.stack([known_classes, graph.stated_identities(n)]), axis=1)
        if np.unique(pairs[0]).size != pairs.shape[1]:
            raise ValueError("KNOWN_CLASS_WITHOUT_STATED_IDENTITY")
    if classes is not None and known_classes is not None:
        pairs = np.unique(np.stack([known_classes, np.asarray(classes, dtype=np.int64)]), axis=1)
        if np.unique(pairs[0]).size != pairs.shape[1]:
            raise ValueError("CLASSES_SPLIT_A_KNOWN_CLASS")
    return classes, known_classes


def _equalize(state: State, known_classes: np.ndarray):
    """Readings of one stated identity class have one meaning: intersect their masks in place. A bank where their
    states have nothing in common is not written; it is returned as a conflict between known premises."""
    size = np.bincount(known_classes)
    rows = np.flatnonzero(size[known_classes] > 1)
    empty = np.zeros(0, dtype=np.int64)
    if not rows.size:
        return empty, empty, empty, empty, (empty, empty)
    rows = rows[np.argsort(known_classes[rows], kind="stable")]
    cls = known_classes[rows]
    _, starts, inverse = np.unique(cls, return_index=True, return_inverse=True)
    common = np.bitwise_and.reduceat(state.masks[rows], starts, axis=0)
    before = state.masks[rows]
    after = np.where(common[inverse] != 0, before & common[inverse], before)
    r, c = np.nonzero(after != before)
    state.masks[rows[r], c] = after[r, c]
    bad_class, bad_bank = np.nonzero(common == 0)
    return rows[r], c, before[r, c], after[r, c], (rows[starts[bad_class]], bad_bank)


def _close_known(state: State, relations, scopes: dict, batch: ob.Batch, known_classes=None, record=None):
    """Close the known layer in place: laws, stated identities, then obligations, waking the laws on the facts they
    locate, until nothing changes. Returns the receipt, the last forcing, the ordered steps, and the identity
    conflicts."""
    closures = sweeps = forced = woken = carried = 0
    last, steps, conflicts = None, [], ([], [])
    while True:
        first = record.count() if record is not None else 0
        close(state, relations, scopes, record)
        closures += 1
        steps.append(("close", first, record.count() if record is not None else 0))
        changed = 0
        if known_classes is not None:
            rows, cols, old, new, bad = _equalize(state, known_classes)
            steps.append(("identity", rows, cols, old, new))
            carried += rows.size
            changed += rows.size
            conflicts = bad
        if len(batch):
            last = ob.force(state, batch, known_classes)
            steps.append(("force", last.rows, last.cols, last.by, last.facts))
            sweeps += 1
            forced += last.changed
            added = ob.wake(scopes, last.facts)
            woken += added
            changed += last.changed + added
        if changed == 0:
            break
    receipt = {
        "closures": closures,
        "sweeps": sweeps,
        "forced": forced,
        "facts_woken": woken,
        "identity_cells": carried,
    }
    return receipt, last, steps, conflicts


def _culprits(graph, batch, current, known, found, forced, new_conflicts, node_of_row):
    """The nodes whose landed defaults a joint conflict rests on, and the obligation groups it passes through.

    A joint conflict is a carried state that fits the known layer but not what interpolation already made of the
    node, an empty cell the known layer does not have, or an obligation the known layer satisfies and the
    interpolated layer does not. Interpolation reaches a reading only by a default landing on its node, or by an
    obligation forcing it from interpolated exclusions, so the culprits are the nodes of those readings and,
    through each forcing or located fact, the nodes of the readings of the forcing group. A group it passes
    through that was counted by identity class is a culprit too: its class rests on proposed identities.
    """
    nodes = set(np.flatnonzero((found & JOINT).any(axis=1)).tolist())
    rows = set(np.flatnonzero(((current.masks == 0) & (known.masks != 0)).any(axis=1)).tolist())
    seen_groups = set(batch.group[list(new_conflicts)].tolist()) if new_conflicts else set()
    for i in new_conflicts:
        rows.update(batch.members(i).tolist())
    f_rows = np.concatenate([r for r, _ in forced]) if forced else np.zeros(0, dtype=np.int64)
    f_by = np.concatenate([b for _, b in forced]) if forced else np.zeros(0, dtype=np.int64)
    frontier = set(rows)
    while frontier and f_rows.size:
        groups = set(batch.group[np.unique(f_by[np.isin(f_rows, list(frontier))])].tolist()) - seen_groups
        seen_groups |= groups
        members = np.isin(batch.owner, np.flatnonzero(np.isin(batch.group, list(groups))))
        reached = set(batch.rows[members].tolist()) - rows
        rows |= reached
        frontier = reached
    row_nodes = node_of_row[list(rows)] if rows else np.zeros(0, dtype=np.int64)
    nodes.update(row_nodes[row_nodes >= 0].tolist())
    return np.array(sorted(nodes), dtype=np.int64), np.array(sorted(seen_groups), dtype=np.int64)


def settle(
    state: State,
    graph: Graph,
    relations=(),
    scopes=None,
    obligations: ob.Batch | None = None,
    classes=None,
    known_classes=None,
    record=None,
) -> Settlement:
    """The joint round, leaving `state` untouched.

    The known layer is `state` closed under `relations` and forced by `obligations`, repeated until neither
    changes; the facts a located obligation makes true join the guard `scopes` (`obligations.wake`), which wakes the
    laws they select. The interpolated layer starts from it: defaults carry (`carry`), the laws narrow
    (`closure.close`), the obligations force and wake, and defaults carry again, until nothing changes. Facts located
    in the interpolated layer join only its own copy of the scopes. `scopes` itself is not modified. A suspension that
    retracts something already landed (two states now reach a cell a default narrowed, or a joint conflict) holds
    the defaults it names and the interpolated layer is replayed from the known layer. Holds only grow, so the
    replay ends; the final replay has no new conflict, and its result is the fixed point of monotone operators,
    which no order of edges or relations changes.

    Identity classes (an id per reading) make the readings of one meaning one candidate of an obligation.
    `known_classes` are joined by stated identities only (checked against the graph's stated links) and act in both
    layers; `classes` are joined by every identity and act only in the interpolated layer, where a conflict that rests
    on one sends its group back to the known classes.

    A stated identity also runs in the known layer (the lead's ruling of 2026-11-27): the readings of one known class
    have one meaning, so their known masks are intersected, and a known value crosses as known (TrialLedger: "Known
    is a source fact or a strict conclusion from known premises"). It carries only known values: what is
    interpolated on one side stays interpolated on the other, since the interpolated layer carries it as any default.
    A proposed link never acts in the known layer. Readings of one class whose known states have nothing in common on
    a bank are not equalized there (`Settlement.identity_conflicts`).

    `record`, a `closure.Derivations`, receives every removal the known layer's closure makes; the known layer's steps
    come back in order (`Settlement.known_steps`): ("close", first, end) spans of `record`, ("identity", rows, cols,
    old, new) and ("force", rows, cols, obligation, facts).
    """
    started = time.perf_counter()
    relations = tuple(relations)
    batch = obligations if obligations is not None else ob.Batch.of(())
    known = state.copy()
    known_scopes = {name: mask.copy() for name, mask in (scopes or {}).items()}
    classes, known_classes = _check_classes(graph, len(state.readings), classes, known_classes)
    interpolated_classes = classes if classes is not None else known_classes
    known_receipt, known_forcing, known_steps, identity_conflicts = _close_known(
        known, relations, known_scopes, batch, known_classes, record
    )
    known_conflicts = set(known_forcing.conflicts.tolist()) if known_forcing is not None else set()
    shape = (len(graph.keys), _WIDTH)
    held = np.zeros(shape, dtype=bool)
    held_equal = np.zeros(shape, dtype=bool)
    held_groups = np.zeros(batch.groups, dtype=bool)  # groups kept on single readings in the interpolated layer
    reasons = np.zeros(shape, dtype=np.uint8)
    node_of_row = np.full(len(state.readings), -1, dtype=np.int64)
    node_of_row[graph.rows] = graph.node_of
    rounds = []
    unattributed = False
    while True:
        current = known.copy()
        round_scopes = {name: mask.copy() for name, mask in known_scopes.items()}
        landed = np.zeros(shape, dtype=bool)
        equalized = np.zeros(shape, dtype=bool)
        found = np.zeros(shape, dtype=np.uint8)
        inherited = np.zeros(current.masks.shape, dtype=bool)
        forced, last, passes = [], None, 0
        while True:
            step = carry(current, graph, known=known, held=held, held_equal=held_equal)
            passes += 1
            landed |= step.landed
            equalized |= step.equalized
            found |= step.suspended
            inherited[step.rows, step.cols] = True
            changed = step.changed + close(current, relations, round_scopes)["removals"]
            if len(batch):
                last = ob.force(
                    current,
                    batch,
                    interpolated_classes,
                    held_groups if classes is not None else None,
                    held_classes=known_classes,
                )
                forced.append(
                    (np.concatenate([last.rows, last.located_rows]), np.concatenate([last.by, last.located_by]))
                )
                changed += last.changed + ob.wake(round_scopes, last.facts)
            if changed == 0:
                break
        # Interpolation must not choose between defaults that disagree: where a consequence of other defaults has
        # removed one of them although the known layer allows it, those defaults are suspended too. (A disagreeing
        # cell that a default had already narrowed is retracted by its own hold and the replay.)
        p = step.proposals
        removed = (p & graph.node_masks(known.masks)) != (p & graph.node_masks(current.masks))
        found[removed & (_POPCOUNT[p] >= 2) & ~landed] |= JOINT
        new_conflicts = sorted(set(last.conflicts.tolist()) - known_conflicts) if last is not None else []
        culprit = np.zeros(shape[0], dtype=bool)
        culprit_nodes, culprit_groups = _culprits(
            graph, batch, current, known, found, forced, new_conflicts, node_of_row
        )
        culprit[culprit_nodes] = True
        grow_groups = np.zeros(batch.groups, dtype=bool)
        if classes is not None:
            grow_groups[culprit_groups] = True
            grow_groups &= ~held_groups
            held_groups |= grow_groups
        disagree = ((found & DISAGREE) != 0) & ~held
        grow = (disagree | ((found & JOINT) != 0) | (landed & culprit[:, None])) & ~held
        grow_equal = equalized & culprit[:, None] & ~held_equal
        reasons |= found
        reasons[landed & culprit[:, None]] |= JOINT
        held |= grow
        held_equal |= grow_equal
        replay = bool((disagree & landed).any() or culprit.any() or grow_groups.any())
        rounds.append(
            {
                "passes": passes,
                "landed": int(landed.sum()),
                "held_added": int(grow.sum()),
                "held_equal_added": int(grow_equal.sum()),
                "held_groups_added": int(grow_groups.sum()),
                "culprit_nodes": int(culprit.sum()),
                "replay": replay,
            }
        )
        if not replay:
            break
        if not (grow.any() or grow_equal.any() or grow_groups.any()):
            unattributed = True
            break
    final_nodes = graph.node_masks(current.masks)
    settlement = Settlement(
        known=known,
        state=current,
        graph=graph,
        inherited=inherited,
        reasons=reasons,
        held=held,
        held_equal=held_equal,
        proposals=step.proposals,
        landed=landed,
        lineage=trace(graph, final_nodes, emissions(final_nodes, step.proposals), landed),
        known_conflicts=known_forcing.described(batch, known) if known_forcing is not None else [],
        identity_conflicts=[
            {"reading": state.readings[int(r)], "bank": BANKS[int(c)]}
            for r, c in zip(*(np.asarray(x) for x in identity_conflicts))
        ],
        known_steps=known_steps,
        interpolated_conflicts=last.described(batch, current) if last is not None else [],
        known_scopes=known_scopes,
        scopes=round_scopes,
        receipt={},
    )
    interpolated = settlement.interpolated
    settlement.receipt.update(
        {
            "rounds": rounds,
            "known": known_receipt,
            "interpolated_cells": int(interpolated.sum()),
            "inherited_cells": int((inherited & interpolated).sum()),
            "consequence_cells": int((interpolated & ~inherited).sum()),
            "suspended_cells": {name: int(((reasons & bit) != 0).sum()) for bit, name in REASONS.items()},
            "facts_located": {
                "known": sum(int((known_scopes[k] & ~(scopes or {})[k]).sum()) for k in known_scopes),
                "interpolated": sum(int((round_scopes[k] & ~known_scopes[k]).sum()) for k in known_scopes),
            },
            "held": int(held.sum()),
            "held_equal": int(held_equal.sum()),
            "held_groups": int(held_groups.sum()),
            "unattributed_conflict": unattributed,
            "bits": {"known": known.bits(), "interpolated": current.bits()},
            "seconds": round(time.perf_counter() - started, 3),
        }
    )
    return settlement
