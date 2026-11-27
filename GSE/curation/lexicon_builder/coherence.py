"""Coherence among independent sources, per reading and across the population (design E5; task 8.1).

TrialLedger: "Meaning is settled by constraints and the constructive or destructive combination of independent
evidence. Each source measures its own thing. Encodings of the same evidence are not independent corroboration.
Agreement alone does not assign a value; supported constraints eliminate alternatives."

Per reading. A root is one native record: a catalog row, a synset, an authored profile. Everything one record
yields is one observation, so two restrictions with the same root are one witness. The restrictions on a cell
are intersected. Agreement settles the intersection. An empty intersection is a conflict: it is recorded with its
reading, bank, roots and rules, and the cell is left as it was. Neither side is preferred over the other.

Across the population. F101: "if one bank, one dimension, has one value vs another value, or if a bank being
filled with SOME non-empty value means another is definitionally silent every time, then we can impute a rule ...
Not 'statistical similarity', but dynamic mechanism impute." Postings hold the exact set of readings where a
stated source, never a derivation, puts a bank in a state. A candidate "within S, A in a implies B in b" is judged
on exact sets:

- witnesses: A stated in a and B stated in b, by two source families that share no dataset (`verbnet+usas` and
  `verbnet` share VerbNet; `usas+framenet` and `verbnet` share none). Only stated
  observations confirm (SW 14). F108 asks for "relations between banks in single words, stable across the tens of
  thousands of words that exist in multiple datasets": the relation is seen where one dataset states A and another
  dataset states B of the same word. One dataset stating both, whether in one record (the `cannot` portmanteau row
  states CAN and NOT) or in two of its records (two VerbNet classes, or a class and its subclass, on one sense key),
  is that dataset's own composition, not a witness of a relation between banks. Roots still deduplicate within a
  family: two restrictions from one record are one observation;
- counterexamples: A known in a and B known outside b. A single record refutes even though it cannot confirm;
- unknowns: A known in a and B neither known in b nor known outside b. They are neither confirmations nor
  counterexamples. A reading where B is known in b only as a consequence is a known agreement: it neither
  confirms nor refutes;
- exposure: the near-misses, readings of S where B is known outside b and every antecedent bank is known outside
  its states. F101 establishes a relation by "one value vs another value": variation in A that goes with variation
  in B. Winston's near-miss and Negative Specification section 9 ("carved from observed near-misses") locate the
  information in that contrast case. Without one the population could not have broken the rule (SSL 4.3), and its
  "every time" carries no information. A candidate with no antecedent bank has no near-miss.

A statement its source confines to its own reading (`Observation.generalizes` False) neither confirms nor exposes;
it can still refute. Known is TrialLedger's: "Known is a source fact or a strict conclusion from known premises." It
is the stated observations closed under the authored laws (`Settlement.knowing`), so a law's consequence on a stated
premise, such as the substantive zeros of a verb head, can supply either side of a near-miss and can contradict,
though it never confirms. Near-misses read the known state built without reading-confined statements. Inherited and
other derived-only values are interpolated and count for nothing.

"Every time" means the counterexample set is empty. Typed scopes are guard facts and strict WordNet ancestor types.
No probability, rate, ratio, support count, threshold or similarity enters any of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from urllib.parse import unquote

import numpy as np

from .cells import ALL, BANK_INDEX, BANKS, BIPOLAR, BIT_NAMES, NEG, POS, START, State
from .relations import Relation, from_predicate

NON_EMPTY = POS | NEG  # "presence of any non-zero and non-empty input" (F088)
_EMPTY = np.zeros(0, dtype=np.int64)
_WIDTH = np.int64(len(BANKS))
_FAMILY_BITS = np.iinfo(np.int64).bits - 1  # family codes are bits of an int64


def render(states: int) -> str:
    """A mask as its states, e.g. "{0|SILENT}"."""
    return "{" + "|".join(name for b, name in BIT_NAMES.items() if states & b) + "}"


def identity_root(reading_id: str) -> str:
    """The native record a reading's own type facts come from: its synset for WordNet, else the reading itself."""
    if reading_id.startswith("wordnet:"):
        return "wordnet:" + unquote(reading_id.split(":")[2])
    return reading_id


def datasets(family: str) -> frozenset[str]:
    """The datasets a source family states through: `usas+framenet` is USAS with FrameNet."""
    return frozenset(family.split("+"))


def disjoint_masks(families) -> tuple[int, ...]:
    """For each family code, the bitmask of the families sharing no dataset with it."""
    return tuple(sum(1 << j for j, g in enumerate(families) if not datasets(f) & datasets(g)) for f in families)


def identity_family(reading_id: str) -> str:
    """The dataset a reading's own type facts come from: its source (wordnet, wiktionary, gse_closed_class ...)."""
    return reading_id.split(":", 1)[0]


def _starts(key: np.ndarray) -> np.ndarray:
    """First index of each run of equal values in a sorted key."""
    return np.flatnonzero(np.concatenate(([True], np.diff(key).astype(bool))))


# ---------------------------------------------------------------------------------------------------- records


@dataclass(frozen=True)
class Observation:
    """What one native record states about one cell: a stated fact, the only material coherence judges.

    `generalizes` is False when the source confines the statement to its own reading. The authored prime
    boundary is the case in point: "It applies only to this prime reading, never to ordinary words." Such a
    statement narrows its own cell and can refute a population relation, but it never confirms one.
    """

    reading: str
    bank: str
    states: int
    family: str
    root: str
    generalizes: bool = True

    def __post_init__(self):
        if self.bank not in BANK_INDEX:
            raise ValueError(f"OBSERVATION_BANK {self.bank}")
        if not self.family or not self.root or not self.reading:
            raise ValueError("OBSERVATION_NEEDS_READING_FAMILY_AND_ROOT")
        if not self.states or self.states & ~ALL:
            raise ValueError("OBSERVATION_STATES")
        if self.states & ~int(START[BANK_INDEX[self.bank]]):
            raise ValueError(f"OBSERVATION_STATE_ILLEGAL {self.bank} {render(self.states)}")


@dataclass(frozen=True)
class Derivation:
    """A builder consequence on one cell: a rule applied to premises. It narrows a cell and never confirms."""

    reading: str
    bank: str
    states: int
    rule: str
    premises: tuple[str, ...] = ()

    def __post_init__(self):
        if self.bank not in BANK_INDEX or not self.rule:
            raise ValueError("DERIVATION_NEEDS_BANK_AND_RULE")


@dataclass(frozen=True)
class Conflict:
    """An empty intersection on one cell. The cell keeps the state it had."""

    reading: str
    bank: str
    roots: tuple[str, ...]
    rules: tuple[str, ...]
    restrictions: tuple[tuple[str, str], ...]  # (root or rule, rendered states)


# ---------------------------------------------------------------------------------------------------- postings


@dataclass
class Column:
    """One bank's stated cells: sorted rows, the intersected mask, and the families stating each (a bitmask over
    the settlement's family codes)."""

    rows: np.ndarray
    masks: np.ndarray
    fams: np.ndarray

    def at(self, rows: np.ndarray):
        """The stated cells among `rows` (sorted, unique): (rows, masks, family bitmasks)."""
        common, _, mine = np.intersect1d(rows, self.rows, assume_unique=True, return_indices=True)
        return common, self.masks[mine], self.fams[mine]


@dataclass
class Postings:
    """Exact sets of readings where stated sources put a bank in a state. Built only from `Observation`s."""

    n: int
    columns: dict[int, Column]
    families: tuple[str, ...]

    def column(self, bank: str) -> Column | None:
        return self.columns.get(BANK_INDEX[bank])

    def within(self, bank: str, states: int) -> np.ndarray:
        """Readings whose stated mask for `bank` lies inside `states`."""
        col = self.column(bank)
        if col is None:
            return _EMPTY
        return col.rows[np.logical_not(col.masks & (ALL & ~states))]

    def outside(self, bank: str, states: int) -> np.ndarray:
        """Readings whose stated mask for `bank` shares nothing with `states`."""
        col = self.column(bank)
        if col is None:
            return _EMPTY
        return col.rows[np.logical_not(col.masks & states)]

    def stated(self, bank: str) -> np.ndarray:
        col = self.column(bank)
        return _EMPTY if col is None else col.rows

    def postings(self) -> dict[tuple[str, str], np.ndarray]:
        """Every (bank, stated mask) posting as its exact set of rows."""
        out = {}
        for c, col in self.columns.items():
            for m in np.unique(col.masks).tolist():
                out[(BANKS[c], render(m))] = col.rows[col.masks == m]
        return out


def _columns(rows, cols, masks, codes) -> dict[int, Column]:
    """Group observations by cell: intersect their masks, unite the bits of the families stating them."""
    out = {}
    if not rows.size:
        return out
    key = rows * _WIDTH + cols
    order = np.argsort(key, kind="stable")
    key, rows, cols, masks, codes = key[order], rows[order], cols[order], masks[order], codes[order]
    starts = _starts(key)
    inter = np.bitwise_and.reduceat(masks, starts).astype(np.uint8)
    fams = np.bitwise_or.reduceat(np.left_shift(np.int64(1), codes), starts)
    cell_rows, cell_cols = rows[starts], cols[starts]
    for c in np.unique(cell_cols).tolist():
        pick = cell_cols == c
        out[c] = Column(cell_rows[pick], inter[pick], fams[pick])
    return out


@dataclass
class Settlement:
    """Per-reading coherence of the stated observations, and the population postings built from it.

    `stated` holds every coherent stated cell; it narrows the state and refutes. `confirming` holds only the
    observations that may confirm a population relation (`generalizes`). A conflicted cell is in neither: a
    conflict among stated roots, or one between a stated cell and a derivation (`excluding`), leaves the cell
    unresolved, and an unresolved cell neither confirms nor refutes.
    """

    readings: tuple[str, ...]
    stated: Postings
    confirming: Postings
    identity: np.ndarray  # family code of each reading's own source, in `stated.families`
    informative: tuple[Observation, ...]  # every observation that restricts something, conflicted or not
    confirming_roots: dict[int, tuple[str, ...]]  # cell key -> the generalizing roots stating it
    conflicts: list[Conflict] = field(default_factory=list)
    uninformative: int = 0  # observations that restricted nothing: the bank's whole starting mask
    excluded: tuple[Conflict, ...] = ()
    known: Postings | None = None  # stated cells closed under the authored laws; refutes, never confirms
    known_general: Postings | None = None  # the same without reading-confined statements; supplies near-misses
    root_family: dict[str, str] = field(default_factory=dict)

    def restrictions_of(self, row: int, col: int) -> tuple[Observation, ...]:
        reading, bank = self.readings[row], BANKS[col]
        return tuple(o for o in self.informative if o.reading == reading and o.bank == bank)

    def roots_of(self, row: int, col: int) -> tuple[str, ...]:
        return tuple(sorted({o.root for o in self.restrictions_of(row, col)}))

    def excluding(self, conflicts) -> Settlement:
        """The same settlement with the cells of `conflicts` (stated against derived) removed from the postings."""
        return _build(self.readings, self.informative, self.excluded + tuple(conflicts), self.uninformative)

    @staticmethod
    def located(reading: str, bank: str, allowed: int, family: str, root: str, layer: str) -> Observation:
        """A word-level obligation located on one reading in the KNOWN layer, as a stated observation of its source.

        The lead's ruling (2026-11-27): an obligation located in the known layer is the source's own statement,
        placed on a reading by strict structure (a word-level fact plus known exclusions of every other reading).
        TrialLedger: "Known is ... a strict conclusion from known premises". So it is a stated observation of its
        SOURCE FAMILY: it can confirm under the family rule, expose and contradict. Its root is the source record the
        obligation rests on. An obligation located only in the interpolated layer, through an aligned class, counts
        for nothing, so any other `layer` is refused.
        """
        if layer != "known":
            raise ValueError(f"LOCATED_OUTSIDE_THE_KNOWN_LAYER {layer}")
        return Observation(reading, bank, allowed, family, root)

    @staticmethod
    def located_groups(batch, located_rows, located_by, readings, source, layer: str) -> list[Observation]:
        """Every obligation of every located group, on each reading the group is located on, as `located`.

        `batch` is the `obligations.Batch` the known layer forced; `located_rows` and `located_by` are a known-layer
        `obligations.Forcing`'s (one obligation of the group per located reading). `source(i)` gives obligation i's
        `(family, root)`: the dataset that stated it and the record it rests on, which the batch does not carry.
        """
        out = []
        for row, by in zip(np.asarray(located_rows).tolist(), np.asarray(located_by).tolist()):
            for i in np.flatnonzero(batch.group == batch.group[by]).tolist():
                family, root = source(i)
                bank = BANKS[int(batch.cols[i])]
                out.append(Settlement.located(readings[row], bank, int(batch.allowed[i]), family, root, layer))
        return out

    def generalizing(self) -> Settlement:
        """The settlement of the observations that may generalize, to close into the state near-misses read."""
        kept = tuple(o for o in self.informative if o.generalizes)
        return _build(self.readings, kept, self.excluded, self.uninformative)

    def knowing(self, state: State, general: State) -> Settlement:
        """The same settlement with `known` set from `state`: the stated observations closed under the authored laws
        and nothing else (no inheritance, no obligation). `general` is the same closure of `generalizing()`, without
        the reading-confined statements; near-misses read it. It is required: passing the full state would let a
        confined statement expose. Every cell narrower than its starting mask is known, except a cell left empty and
        a cell in conflict, which stay unresolved."""
        if state.readings != self.readings or general.readings != self.readings:
            raise ValueError("SETTLEMENT_READINGS")
        known = self._known(state)
        known_general = self._known(general)
        return Settlement(
            self.readings,
            self.stated,
            self.confirming,
            self.identity,
            self.informative,
            self.confirming_roots,
            self.conflicts,
            self.uninformative,
            self.excluded,
            known,
            known_general,
            self.root_family,
        )

    def _known(self, state: State) -> Postings:
        index = {r: i for i, r in enumerate(self.readings)}
        unresolved = np.array(
            sorted({index[c.reading] * int(_WIDTH) + BANK_INDEX[c.bank] for c in self.conflicts}), dtype=np.int64
        )
        columns = {}
        for c in range(len(BANKS)):
            m = state.masks[:, c]
            rows = np.flatnonzero(m.astype(bool) & (m != START[c]))
            rows = rows[np.logical_not(np.isin(rows * _WIDTH + c, unresolved))]
            if rows.size:
                columns[c] = Column(rows, m[rows].copy(), np.zeros(rows.size, dtype=np.int64))
        return Postings(len(self.readings), columns, self.stated.families)


def settle(observations, readings) -> Settlement:
    """Intersect each cell's stated observations; an empty intersection is a conflict and enters no posting."""
    readings = tuple(readings)
    index = {r: i for i, r in enumerate(readings)}
    obs = []
    uninformative = 0
    for o in observations:
        if type(o) is not Observation:
            raise TypeError("POSTINGS_TAKE_STATED_OBSERVATIONS_ONLY")
        if o.reading not in index:
            raise ValueError(f"OBSERVATION_READING_UNKNOWN {o.reading}")
        if o.states == int(START[BANK_INDEX[o.bank]]):
            uninformative += 1
            continue
        obs.append(o)
    return _build(readings, tuple(obs), (), uninformative)


def _build(readings, obs, excluded, uninformative) -> Settlement:
    index = {r: i for i, r in enumerate(readings)}
    families = tuple(sorted({o.family for o in obs} | {identity_family(r) for r in readings}))
    if families[_FAMILY_BITS:]:
        raise ValueError("TOO_MANY_SOURCE_FAMILIES")
    code = {f: i for i, f in enumerate(families)}
    identity = np.array([code[identity_family(r)] for r in readings], dtype=np.int64)
    rows = np.array([index[o.reading] for o in obs], dtype=np.int64)
    cols = np.array([BANK_INDEX[o.bank] for o in obs], dtype=np.int64)
    masks = np.array([o.states for o in obs], dtype=np.uint8)
    codes = np.array([code[o.family] for o in obs], dtype=np.int64)
    general = np.array([o.generalizes for o in obs], dtype=bool)
    keys = rows * _WIDTH + cols
    bad_keys = []
    for c, col in _columns(rows, cols, masks, codes).items():
        bad_keys.extend((col.rows[np.logical_not(col.masks)] * _WIDTH + c).tolist())
    among = np.array(sorted(bad_keys), dtype=np.int64)
    outside = [index[x.reading] * int(_WIDTH) + BANK_INDEX[x.bank] for x in excluded]
    keep = np.logical_not(np.isin(keys, np.union1d(among, np.array(outside, dtype=np.int64))))
    conflicts = []
    if among.size:
        here: dict[int, list[Observation]] = {}
        for o, k in zip(obs, keys.tolist()):
            here.setdefault(k, []).append(o)
        for k in among.tolist():
            group = here[k]
            conflicts.append(
                Conflict(
                    group[0].reading,
                    group[0].bank,
                    tuple(sorted({o.root for o in group})),
                    (),
                    tuple(sorted((o.root, render(o.states)) for o in group)),
                )
            )
    stated = Postings(len(readings), _columns(rows[keep], cols[keep], masks[keep], codes[keep]), families)
    sel = keep & general
    confirming = Postings(len(readings), _columns(rows[sel], cols[sel], masks[sel], codes[sel]), families)
    confirming_roots: dict[int, set[str]] = {}
    for o, k, chosen in zip(obs, keys.tolist(), sel.tolist()):
        if chosen:
            confirming_roots.setdefault(k, set()).add(o.root)
    frozen = {k: tuple(sorted(v)) for k, v in confirming_roots.items()}
    return Settlement(
        readings,
        stated,
        confirming,
        identity,
        obs,
        frozen,
        conflicts + list(excluded),
        uninformative,
        excluded,
        root_family={o.root: o.family for o in obs},
    )


def apply(state: State, settlement: Settlement, derivations=()) -> list[Conflict]:
    """Narrow `state` by the settled stated cells and by `derivations`; a cell they would empty is left alone.

    Returns the conflicts: the stated roots and the derivation rules whose intersection with the cell is empty.
    """
    if state.readings != settlement.readings:
        raise ValueError("SETTLEMENT_READINGS")
    narrowing: dict[tuple[int, int], int] = {}
    for c, col in settlement.stated.columns.items():
        for r, m in zip(col.rows.tolist(), col.masks.tolist()):
            narrowing[(r, c)] = m
    rules: dict[tuple[int, int], list[Derivation]] = {}
    for d in derivations:
        if type(d) is not Derivation:
            raise TypeError("NOT_A_DERIVATION")
        key = (state.index[d.reading], BANK_INDEX[d.bank])
        narrowing[key] = narrowing.get(key, ALL) & d.states
        rules.setdefault(key, []).append(d)
    conflicts = []
    for (r, c), m in sorted(narrowing.items()):
        new = int(state.masks[r, c]) & m
        if new:
            state.masks[r, c] = new
            continue
        derived = rules.get((r, c), ())
        roots = tuple(sorted(set(settlement.roots_of(r, c)) | {p for d in derived for p in d.premises}))
        restrictions = tuple((o.root, render(o.states)) for o in settlement.restrictions_of(r, c))
        restrictions += tuple((d.rule, render(d.states)) for d in rules.get((r, c), ()))
        restrictions += (("current", render(int(state.masks[r, c]))),)
        conflicts.append(
            Conflict(
                state.readings[r],
                BANKS[c],
                roots,
                tuple(sorted({d.rule for d in rules.get((r, c), ())})),
                restrictions,
            )
        )
    return conflicts


def closure_conflicts(state: State, settlement: Settlement, derivations) -> list[Conflict]:
    """Cells a closure left empty, with the stated roots on them and the relations that removed their states."""
    a = derivations.arrays()
    empty_r, empty_c = np.nonzero(np.logical_not(state.masks))
    out = []
    for r, c in zip(empty_r.tolist(), empty_c.tolist()):
        pick = (a["rows"] == r) & (a["cols"] == c)
        rule_ids = tuple(sorted({str(a["rule_ids"][i]) for i in a["rules"][pick].tolist()}))
        stated = tuple((o.root, render(o.states)) for o in settlement.restrictions_of(r, c))
        out.append(Conflict(state.readings[r], BANKS[c], tuple(sorted({x for x, _ in stated})), rule_ids, stated))
    return out


# ---------------------------------------------------------------------------------------------------- types


@dataclass
class Types:
    """Typed facts about readings, each the exact set of readings holding it: guard facts and WordNet ancestors."""

    n: int
    names: tuple[str, ...]
    members: tuple[np.ndarray, ...]
    indptr: np.ndarray
    ids: np.ndarray

    @classmethod
    def build(cls, n: int, facts: dict[str, np.ndarray]) -> Types:
        """`facts` maps a type name to the readings holding it (row indices or a boolean mask)."""
        names, members = [], []
        for name in sorted(facts):
            rows = np.asarray(facts[name])
            rows = np.flatnonzero(rows) if rows.dtype == bool else np.unique(rows.astype(np.int64))
            if rows.size:
                names.append(name)
                members.append(rows)
        if names:
            owner = np.concatenate(members)
            tid = np.concatenate([np.full(m.size, i, dtype=np.int64) for i, m in enumerate(members)])
            order = np.lexsort((tid, owner))
            owner, tid = owner[order], tid[order]
            indptr = np.searchsorted(owner, np.arange(n + 1))
        else:
            tid, indptr = _EMPTY, np.zeros(n + 1, dtype=np.int64)
        return cls(n, tuple(names), tuple(members), indptr, tid)

    def index(self, name: str) -> int:
        return self.names.index(name)

    def of(self, row: int) -> np.ndarray:
        return self.ids[self.indptr[row] : self.indptr[row + 1]]

    def rows(self, scope: tuple[str, ...]) -> np.ndarray:
        """The readings holding every type of `scope`, as sorted rows."""
        out = None
        for name in scope:
            m = self.members[self.index(name)]
            out = m if out is None else np.intersect1d(out, m, assume_unique=True)
        return _EMPTY if out is None else out

    def mask(self, scope: tuple[str, ...]) -> np.ndarray:
        out = np.zeros(self.n, dtype=bool)
        out[self.rows(scope)] = True
        return out

    def held_by_any(self, rows: np.ndarray) -> np.ndarray:
        if not rows.size:
            return _EMPTY
        return np.unique(np.concatenate([self.of(int(r)) for r in rows.tolist()]))

    def held_by_all(self, rows: np.ndarray) -> np.ndarray:
        if not rows.size:
            return _EMPTY
        first = self.of(int(rows[0])).tolist()
        keep = [t for t in first if np.isin(rows, self.members[t], assume_unique=True).all()]
        return np.array(keep, dtype=np.int64)

    def separating(self, witnesses: np.ndarray, counterexamples: np.ndarray) -> tuple[str, ...]:
        """Every type held by each witness and by no counterexample (SW 16.6; all of them, none preferred)."""
        sep = np.setdiff1d(self.held_by_all(witnesses), self.held_by_any(counterexamples))
        return tuple(self.names[t] for t in sep.tolist())


@cache
def _wordnet():
    from nltk.corpus import wordnet as wn

    wn.synsets("test")
    return wn


@cache
def _ancestors(synset_name: str) -> frozenset[str]:
    """Strict IS-A ancestors of a synset (hypernyms and instance hypernyms); the synset itself is excluded."""
    s = _wordnet().synset(synset_name)
    out: set[str] = set()
    for parent in s.hypernyms() + s.instance_hypernyms():
        out.add(parent.name())
        out |= _ancestors(parent.name())
    return frozenset(out)


def wordnet_types(readings) -> dict[str, np.ndarray]:
    """`wordnet_isa:<synset>` for every strict ancestor of each WordNet reading's own synset."""
    from nltk.corpus.reader.wordnet import WordNetError

    rows: dict[str, list[int]] = {}
    for i, r in enumerate(readings):
        rid = r if isinstance(r, str) else r.reading_id
        if not rid.startswith("wordnet:"):
            continue
        try:
            names = _ancestors(unquote(rid.split(":")[2]))
        except WordNetError:
            continue
        for a in names:
            rows.setdefault("wordnet_isa:" + a, []).append(i)
    return {k: np.array(v, dtype=np.int64) for k, v in rows.items()}


# ---------------------------------------------------------------------------------------------------- candidates


@dataclass(frozen=True)
class Candidate:
    """Within the readings holding every type of `scope`, if every `if_terms` bank is in its states, then
    `then_bank` is in `then_states`. With no `if_terms` the scope alone is the condition.

    A censor is the same object with `kind="censor"`. It forbids the states outside `then_states`, and its witness
    is a stated near-miss: a reading in scope whose bank a source states outside the forbidden states. A censor
    needs an antecedent bank to be admissible: with the scope alone as its condition, every reading in scope that
    states a forbidden state is a counterexample, so the censor is never exposed without being contradicted.
    """

    if_terms: tuple[tuple[str, int], ...]
    then_bank: str
    then_states: int
    scope: tuple[str, ...]
    origin: str = "supplied"
    kind: str = "implication"

    def __post_init__(self):
        banks = [b for b, _ in self.if_terms] + [self.then_bank]
        if len(set(banks)) != len(banks) or any(b not in BANK_INDEX for b in banks):
            raise ValueError("CANDIDATE_BANKS")
        if not self.scope:
            raise ValueError("CANDIDATE_NEEDS_A_TYPED_SCOPE")
        if not self.then_states & int(START[BANK_INDEX[self.then_bank]]):
            raise ValueError("CANDIDATE_CONSEQUENT_EMPTY")

    @property
    def banks(self) -> tuple[str, ...]:
        return tuple(b for b, _ in self.if_terms) + (self.then_bank,)

    @property
    def scope_name(self) -> str:
        return "coherence:" + "&".join(sorted(self.scope))

    @property
    def rule_id(self) -> str:
        terms = "&".join(f"{b}{render(s)}" for b, s in self.if_terms) or "scope"
        then = f"{self.then_bank}{render(self.then_states)}"
        return f"coherence:{self.kind}:[{'&'.join(sorted(self.scope))}]:{terms}=>{then}"

    def key(self):
        return (tuple(sorted(self.if_terms)), self.then_bank, self.then_states, tuple(sorted(self.scope)), self.kind)

    def relation(self, warrant: str) -> Relation:
        terms = tuple(s for _, s in self.if_terms)
        then = self.then_states

        def permitted(*t):
            return not all(t[i] & s for i, s in enumerate(terms)) or bool(t[-1] & then)

        return from_predicate(self.rule_id, self.banks, permitted, warrant, self.scope_name)


def censor(scope, bank: str, forbidden: int, if_terms=(), origin="supplied") -> Candidate:
    """A negative constraint (Negative Specification section 9): within `scope`, `bank` is never in `forbidden`."""
    legal = int(START[BANK_INDEX[bank]])
    return Candidate(tuple(if_terms), bank, legal & ~forbidden, tuple(scope), origin, "censor")


@dataclass
class Evidence:
    """The exact sets a candidate is judged on, within its scope."""

    antecedent: np.ndarray  # A known in a (the whole scope when there is no antecedent)
    witnesses: np.ndarray  # A and B stated in a and b, B by a source family other than an antecedent's
    co_encoded: np.ndarray  # stated in a and b, but every term by one family: agreement, not confirmation
    counterexamples: np.ndarray  # A known in a, B known outside b
    unknown: np.ndarray  # A known in a, B neither known in b nor known outside b
    exposure: np.ndarray  # the near-misses: B and every antecedent bank known outside their states
    witness_roots: tuple[str, ...]
    known_agreement: np.ndarray = field(default_factory=lambda: _EMPTY)  # B known in b only as a consequence
    witness_families: tuple[str, ...] = ()

    @property
    def exposed(self) -> bool:
        return bool(self.exposure.size)


def _independent(a_fams: np.ndarray, b_fams: np.ndarray, disjoint: tuple[int, ...]) -> np.ndarray:
    """Some family stating A and some family stating B share no dataset (F108: the relation is seen where one
    dataset states A and another states B). `verbnet+usas` and `verbnet` share VerbNet, so they are one."""
    out = np.zeros(a_fams.shape, dtype=bool)
    for f, others in enumerate(disjoint):
        holds_f = np.bitwise_and(np.right_shift(a_fams, f), 1).astype(bool)
        out |= holds_f & np.bitwise_and(b_fams, np.int64(others)).astype(bool)
    return out


def _confirming_witnesses(candidate: Candidate, settlement: Settlement, agree: np.ndarray) -> np.ndarray:
    """The rows of `agree` whose terms the confirming postings state, with an antecedent family sharing no dataset
    with a family that states B."""
    confirming = settlement.confirming
    col_b = confirming.column(candidate.then_bank)
    if col_b is None or not agree.size:
        return _EMPTY
    disjoint = disjoint_masks(confirming.families)
    rows, b_masks, b_fams = col_b.at(agree)
    inside = np.logical_not(b_masks & (ALL & ~candidate.then_states))
    rows, b_fams = rows[inside], b_fams[inside]
    if not candidate.if_terms:
        ident = np.left_shift(np.int64(1), settlement.identity[rows])
        return rows[_independent(ident, b_fams, disjoint)]
    eligible = np.ones(rows.size, dtype=bool)
    distinct = np.zeros(rows.size, dtype=bool)
    for bank, states in candidate.if_terms:
        col_a = confirming.column(bank)
        if col_a is None:
            return _EMPTY
        a_rows, a_masks, a_fams = col_a.at(rows)
        pos = np.searchsorted(rows, a_rows)
        here = np.zeros(rows.size, dtype=bool)
        here[pos] = np.logical_not(a_masks & (ALL & ~states))
        apart = np.zeros(rows.size, dtype=bool)
        apart[pos] = _independent(a_fams, b_fams[pos], disjoint)
        eligible &= here
        distinct |= here & apart
    return rows[eligible & distinct]


def evidence_on(candidate: Candidate, settlement: Settlement, scope_rows: np.ndarray) -> Evidence:
    """Witnesses, co-encoded agreements, counterexamples and unknowns of `candidate` among `scope_rows`.

    Confirmation reads the stated postings; refutation, unknowns and exposure read the known postings when the
    settlement has them (`Settlement.knowing`), the stated ones otherwise.
    """
    stated = settlement.stated
    known = stated if settlement.known is None else settlement.known
    b, bs = candidate.then_bank, candidate.then_states
    ante, ante_stated = scope_rows, scope_rows
    for bank, states in candidate.if_terms:
        ante = np.intersect1d(ante, known.within(bank, states), assume_unique=True)
        ante_stated = np.intersect1d(ante_stated, stated.within(bank, states), assume_unique=True)
    agree_known = np.intersect1d(ante, known.within(b, bs), assume_unique=True)
    agree = np.intersect1d(ante_stated, stated.within(b, bs), assume_unique=True)
    counter = np.intersect1d(ante, known.outside(b, bs), assume_unique=True)
    unknown = np.setdiff1d(ante, np.union1d(agree_known, counter), assume_unique=True)
    exposure = _near_misses(candidate, settlement, scope_rows)
    known_agreement = np.setdiff1d(agree_known, agree, assume_unique=True)
    witnesses = _confirming_witnesses(candidate, settlement, agree)
    co_encoded = np.setdiff1d(agree, witnesses, assume_unique=True)
    roots = set()
    for col in [BANK_INDEX[x] for x in candidate.banks]:
        for r in witnesses.tolist():
            roots.update(settlement.confirming_roots.get(r * int(_WIDTH) + col, ()))
    families = {settlement.root_family[r] for r in roots}
    if not candidate.if_terms:
        families.update(identity_family(settlement.readings[r]) for r in witnesses.tolist())
    return Evidence(
        ante,
        witnesses,
        co_encoded,
        counter,
        unknown,
        exposure,
        tuple(sorted(roots)),
        known_agreement,
        tuple(sorted(families)),
    )


def _near_misses(candidate: Candidate, settlement: Settlement, scope_rows: np.ndarray) -> np.ndarray:
    """Readings in scope with B and every antecedent bank known outside their states, read from the known state
    without reading-confined statements (the confirming postings when the settlement has no known state)."""
    if not candidate.if_terms:
        return _EMPTY
    general = settlement.confirming if settlement.known_general is None else settlement.known_general
    out = np.intersect1d(scope_rows, general.outside(candidate.then_bank, candidate.then_states), assume_unique=True)
    for bank, states in candidate.if_terms:
        out = np.intersect1d(out, general.outside(bank, states), assume_unique=True)
    return out


def evidence(candidate: Candidate, settlement: Settlement, types: Types) -> Evidence:
    return evidence_on(candidate, settlement, types.rows(candidate.scope))


def _antecedent_values(col: Column, bank: str) -> list[int]:
    values = sorted(set(np.unique(col.masks).tolist()))
    content = NON_EMPTY & int(START[BANK_INDEX[bank]])
    if bank in BIPOLAR and any(not (m & ~content) for m in values) and content not in values:
        values.append(content)
    return values


def _consequent_values(observed: np.ndarray, bank: str) -> list[int]:
    values = sorted(set(np.unique(observed).tolist()))
    union = int(np.bitwise_or.reduce(observed))
    if union not in values and union != int(START[BANK_INDEX[bank]]):
        values.append(union)
    return values


def pair_candidates(settlement: Settlement, types: Types) -> list[Candidate]:
    """Candidate source (i): every pair of stated bank states, in every typed scope holding a confirming witness.

    For each stated state of A, and each bank B stated on those readings, every stated state of B and their
    union is a consequent. The candidate is posed in each type held by at least one of its confirming witnesses.
    All of it is set algebra over the postings.
    """
    stated = settlement.stated
    out, seen = [], set()
    for a_id, a_col in sorted(stated.columns.items()):
        a_bank = BANKS[a_id]
        for a in _antecedent_values(a_col, a_bank):
            rows_a = stated.within(a_bank, a)
            for b_id, b_col in sorted(stated.columns.items()):
                if b_id == a_id:
                    continue
                b_bank = BANKS[b_id]
                _, observed, _ = b_col.at(rows_a)
                if not observed.size:
                    continue
                for b in _consequent_values(observed, b_bank):
                    probe = Candidate(((a_bank, a),), b_bank, b, ("population",), "pair")
                    w = evidence_on(probe, settlement, rows_a).witnesses
                    for t in types.held_by_any(w).tolist():
                        c = Candidate(((a_bank, a),), b_bank, b, (types.names[t],), "pair")
                        if c.key() not in seen:
                            seen.add(c.key())
                            out.append(c)
    return out


def near_miss_conjunctions(candidate: Candidate, ev: Evidence, settlement: Settlement) -> list[Candidate]:
    """Candidate source (ii): add a second antecedent that every witness holds and every near-miss lacks.

    A counterexample is a near-miss: the antecedent held and the consequent fell outside. A bank C known on every
    witness inside c and on every counterexample outside c is the condition the witnesses share and the
    near-misses lack (F073: constraints are conjunctive). Its verdict is computed in full like any candidate's, so
    it is confirmed only where C is also stated.
    """
    known = settlement.stated if settlement.known is None else settlement.known
    if not ev.witnesses.size or not ev.counterexamples.size:
        return []
    used = set(candidate.banks)
    out = []
    for c_id, col in sorted(known.columns.items()):
        bank = BANKS[c_id]
        if bank in used:
            continue
        if not np.isin(ev.witnesses, col.rows).all() or not np.isin(ev.counterexamples, col.rows).all():
            continue
        _, w_masks, _ = col.at(ev.witnesses)
        _, k_masks, _ = col.at(ev.counterexamples)
        on_w = int(np.bitwise_or.reduce(w_masks))
        if on_w & int(np.bitwise_or.reduce(k_masks)):
            continue
        out.append(
            Candidate(
                candidate.if_terms + ((bank, on_w),),
                candidate.then_bank,
                candidate.then_states,
                candidate.scope,
                f"near_miss:{candidate.rule_id}",
                candidate.kind,
            )
        )
    return out
