"""Admission: the Significance Weighting gate over coherence candidates (design E6; task 8.2).

Written from Significance Weighting sections 14 and 16.

- Section 14, admissibility: "Promote r only if (i) its confirmation is spine-sourced ... and (ii)
  sigma_sem(D | P u {r}) > 0 -- the corpus still admits plural lawful readings after promotion." A rule confirmed
  by the engine's own output "reduces H by construction while carrying zero information".
- Section 16.7: "A candidate is promoted iff, all MEASURED: (i) spine-CONFIRMED, (ii) RETAINS PLURALITY, and (iii)
  kappa > 0 -- it adds real coverage ... No number is picked."
- Section 16.6: an oscillating candidate is specialized to each type separating its confirmations from its
  contradictions; "if not, the oscillation IS the finding, logged with the exact fillers."
- Negative Specification section 9: censors pass the same gate, carved from stated near-misses; "An LLM- or
  a-priori-authored constraint is an unverified assertion and must not gate."

The verdicts, checked in this order:

- UNCONFIRMED: no stated witness from a root other than the antecedent's. Derived values never appear in the
  postings, and one record's two encodings are agreement, not confirmation.
- NARROWED: witnesses and counterexamples both, and some type holds every witness and no counterexample. Each such
  type yields a child candidate, which is judged in full. None is preferred.
- FINDING: witnesses and counterexamples, and no type separates them. The exact readings are the finding. Also
  FINDING: two or more candidates, each admissible alone, that together empty a cell. All of them are withheld,
  none preferred, with their partners and the cells.
- UNEXPOSED: within the scope, no reading has the consequent's bank stated outside the consequent's states. The
  population could not have broken the rule, so its confirmation carries no information: SSL 4.3's falsifiability
  pivot (mutual information > 0 iff the answer channel is non-degenerate; `self_confirming_cannot_certify`) and
  SW 14 (ii). Measured on the old artifact: GOOD=0 => SOMETHING=+1 had 78,002 "supports" and no counterexample
  only because the opposite states were never stated. Exposure is the non-emptiness of an exact set.
- NO_REACH: kappa = 0. Against the current closure the rule removes no state anywhere, or a stronger admitted
  candidate in the same round removes everything it removes.
- DEGENERATE: retained plurality fails. After the rule the scope admits one lawful configuration of the rule's
  banks, or none, because the rule empties a cell the current closure holds. This verdict is added here: the
  gate needs a name for a candidate that fails (ii). An exposed candidate always keeps two configurations (a
  witness has B in b, an exposing reading has B outside b), so after exposure it fails only by emptying a cell.
- ADMITTED: stated confirmation, exposure, retained plurality and kappa > 0 all hold. The rule becomes a `relations.Relation` whose warrant names its witness
  count. The count is reported, never compared with anything.

Every candidate in a round is measured against the same closed state, so no verdict depends on order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .cells import BANK_INDEX, BANKS, State
from .closure import Derivations, close
from .coherence import (
    Candidate,
    Evidence,
    Settlement,
    Types,
    evidence,
    near_miss_conjunctions,
    pair_candidates,
    render,
)
from .relations import Relation
from .relations import apply as apply_relation

ADMITTED = "ADMITTED"
NARROWED = "NARROWED"
FINDING = "FINDING"
UNCONFIRMED = "UNCONFIRMED"
UNEXPOSED = "UNEXPOSED"
NO_REACH = "NO_REACH"
DEGENERATE = "DEGENERATE"
VERDICTS = (ADMITTED, NARROWED, FINDING, UNCONFIRMED, UNEXPOSED, NO_REACH, DEGENERATE)


@dataclass
class Reach:
    """What a candidate does when staged over its whole scope against the current closure (kappa, measured)."""

    rows: np.ndarray  # readings whose masks change
    removed: dict[tuple[int, int], int]  # (row, col) -> states removed
    decided: int  # cells newly decided
    bits: float  # H removed
    emptied: tuple[tuple[str, str], ...]  # (reading, bank) left with no lawful state
    configurations: int  # distinct lawful joint states of the rule's banks across the scope, after the rule
    plural: bool

    @property
    def cells(self) -> int:
        return len(self.removed)

    def covered_by(self, other: Reach) -> bool:
        return all(not (bits & ~other.removed.get(cell, 0)) for cell, bits in self.removed.items())


@dataclass
class Verdict:
    candidate: Candidate
    verdict: str
    evidence: Evidence
    reach: Reach | None = None
    guards: tuple[str, ...] = ()
    children: tuple[Candidate, ...] = ()
    relation: Relation | None = None
    note: str = ""
    collided: tuple[tuple[str, str], ...] = ()  # (reading, bank) cells it empties jointly with other admitted rules


def _decided(masks: np.ndarray) -> np.ndarray:
    """Exactly one state left: nonzero with no second bit."""
    return masks.astype(bool) & np.logical_not(masks & (masks - np.uint8(1)))


def stage(candidate: Candidate, state: State, relations, scopes: dict, types: Types) -> Reach:
    """Apply the candidate over its whole scope, then close the readings it changed under every current relation.

    Relations act within one reading, so closing only the changed readings is exact. `state` is not modified.
    """
    rows = types.rows(candidate.scope)
    rel = candidate.relation("staged for measurement")
    probe = state.masks[rows].copy()
    changed, _, _ = apply_relation(rel, probe, np.arange(rows.size))
    cols = np.array([BANK_INDEX[b] for b in rel.banks])
    before_scope = state.masks[np.ix_(rows, cols)]
    if not changed.size:
        configs, plural = _plurality(rel, before_scope)
        return Reach(rows[changed], {}, 0, 0.0, (), configs, plural)
    touched = rows[changed]
    sub = State(tuple(state.readings[i] for i in touched.tolist()), state.masks[touched].copy())
    sub_scopes = {name: np.asarray(mask)[touched] for name, mask in scopes.items()}
    sub_scopes[candidate.scope_name] = np.ones(touched.size, dtype=bool)
    close(sub, list(relations) + [rel], sub_scopes)
    before, after = state.masks[touched], sub.masks
    gone = before & ~after
    r, c = np.nonzero(gone)
    removed = {(int(touched[i]), int(j)): int(gone[i, j]) for i, j in zip(r.tolist(), c.tolist())}
    emptied_r, emptied_c = np.nonzero(before.astype(bool) & np.logical_not(after))
    emptied = tuple((sub.readings[i], BANKS[j]) for i, j in zip(emptied_r.tolist(), emptied_c.tolist()))
    decided = int((_decided(after) & np.logical_not(_decided(before))).sum())
    bits = State(sub.readings, before.copy()).bits() - sub.bits()
    after_scope = before_scope.copy()
    after_scope[changed] = after[:, cols]
    configs, plural = _plurality(rel, after_scope)
    return Reach(touched, removed, decided, bits, emptied, configs, plural)


def _plurality(rel: Relation, masks: np.ndarray) -> tuple[int, bool]:
    """The rule's permitted joint states that some reading in scope can still take; plural if two differ."""
    live = masks.astype(bool).all(axis=1)
    configs = np.unique(masks[live], axis=0)
    allowed = np.array(rel.allowed, dtype=np.uint8)
    if not configs.size or not allowed.size:
        return 0, False
    fits = (configs[:, None, :] & allowed[None, :, :]).astype(bool).all(axis=2)
    lawful = np.flatnonzero(fits.any(axis=0))
    plural = bool(lawful.size) and bool((lawful != lawful[0]).any())
    return int(lawful.size), plural


def _entails(stronger: Candidate, weaker: Candidate, rows: dict) -> bool:
    """`stronger` logically implies `weaker`: a weaker or equal antecedent, a narrower consequent, a wider scope."""
    if stronger.then_bank != weaker.then_bank or stronger.then_states & ~weaker.then_states:
        return False
    theirs = dict(weaker.if_terms)
    for bank, states in stronger.if_terms:
        if bank not in theirs or theirs[bank] & ~states:
            return False
    return bool(np.isin(rows[weaker.key()], rows[stronger.key()], assume_unique=True).all())


def warrant(candidate: Candidate, ev: Evidence, reach: Reach) -> str:
    terms = " and ".join(f"{b} in {render(s)}" for b, s in candidate.if_terms) or "membership"
    return (
        f"Coherence among independent sources (SW 14, 16.7; F101, F108): within {' & '.join(candidate.scope)}, "
        f"{terms} implies {candidate.then_bank} in {render(candidate.then_states)}. Confirmed by "
        f"{ev.witnesses.size} stated witness readings from {len(ev.witness_roots)} roots; no counterexample; "
        f"{ev.unknown.size} unknown; exposed by {ev.exposure.size} readings. Reach {reach.cells} cells, {reach.bits:.1f} bits. "
        f"Origin {candidate.origin}."
    )


def judge(candidates, settlement: Settlement, types: Types, state: State, relations, scopes: dict) -> list[Verdict]:
    """A verdict for every candidate, and for every child that narrowing and near-misses produce."""
    queue = list(candidates)
    seen: dict = {}
    kids: dict = {}
    order: list = []
    while queue:
        c = queue.pop(0)
        if c.key() in seen:
            continue
        ev = evidence(c, settlement, types)
        seen[c.key()] = (c, ev)
        order.append(c.key())
        if ev.witnesses.size and ev.counterexamples.size:
            kids[c.key()] = tuple(_children(c, ev, settlement, types))
            queue.extend(kids[c.key()])
    verdicts: dict = {}
    staged = []
    for k in order:
        c, ev = seen[k]
        if not ev.witnesses.size:
            verdicts[k] = Verdict(c, UNCONFIRMED, ev, note=_unconfirmed_note(ev))
        elif ev.counterexamples.size:
            guards = types.separating(ev.witnesses, ev.counterexamples)
            if guards:
                verdicts[k] = Verdict(c, NARROWED, ev, guards=guards, children=kids[k])
            else:
                verdicts[k] = Verdict(c, FINDING, ev, children=kids[k], note=_finding_note(ev, settlement))
        elif not ev.exposed:
            verdicts[k] = Verdict(c, UNEXPOSED, ev, note="no reading in scope states the bank outside the consequent")
        else:
            staged.append(k)
    reaches = {k: stage(seen[k][0], state, relations, scopes, types) for k in staged}
    for k in staged:
        c, ev = seen[k]
        reach = reaches[k]
        if not reach.removed:
            verdicts[k] = Verdict(c, NO_REACH, ev, reach, note="the current closure already holds every consequence")
        elif reach.emptied or not reach.plural:
            note = f"empties {len(reach.emptied)} cells" if reach.emptied else "one lawful configuration remains"
            verdicts[k] = Verdict(c, DEGENERATE, ev, reach, note=note)
        else:
            verdicts[k] = Verdict(c, ADMITTED, ev, reach, relation=c.relation(warrant(c, ev, reach)))
    _jointly(verdicts, order, seen, state, relations, scopes, types)
    _redundant(verdicts, seen, types)
    return [verdicts[k] for k in order]


def _children(c: Candidate, ev: Evidence, settlement: Settlement, types: Types) -> list[Candidate]:
    out = []
    scope_rows = types.rows(c.scope)
    for g in types.separating(ev.witnesses, ev.counterexamples):
        inside = np.isin(types.rows((g,)), scope_rows, assume_unique=True).all()
        scope = (g,) if inside else tuple(sorted(set(c.scope) | {g}))
        out.append(Candidate(c.if_terms, c.then_bank, c.then_states, scope, f"narrowed:{c.rule_id}", c.kind))
    out.extend(near_miss_conjunctions(c, ev, settlement))
    return out


def _jointly(verdicts: dict, order: list, seen: dict, state: State, relations, scopes: dict, types: Types) -> None:
    """Rules that pass alone can contradict each other together. Close the admitted batch jointly on the readings
    they touch. Every admitted rule that removed a state from a cell the batch empties is withheld, all of them
    and none preferred, as a FINDING naming its partners and the cells. Repeat until nothing empties."""
    while True:
        admitted = [k for k in order if verdicts[k].verdict == ADMITTED]
        if not admitted:
            return
        touched = np.unique(np.concatenate([verdicts[k].reach.rows for k in admitted]))
        sub = State(tuple(state.readings[i] for i in touched.tolist()), state.masks[touched].copy())
        sub_scopes = {name: np.asarray(mask)[touched] for name, mask in scopes.items()}
        for k in admitted:
            sub_scopes[seen[k][0].scope_name] = types.mask(seen[k][0].scope)[touched]
        record = Derivations()
        close(sub, list(relations) + [verdicts[k].relation for k in admitted], sub_scopes, record)
        er, ec = np.nonzero(state.masks[touched].astype(bool) & np.logical_not(sub.masks))
        if not er.size:
            return
        a = record.arrays()
        ids = [str(a["rule_ids"][i]) for i in a["rules"].tolist()]
        emptied = set(zip(er.tolist(), ec.tolist()))
        rows = set(er.tolist())
        cells = list(zip(a["rows"].tolist(), a["cols"].tolist()))
        by_id = {verdicts[k].relation.rule_id: k for k in admitted}
        culprits = {by_id[i] for i, cell in zip(ids, cells) if i in by_id and cell in emptied}
        culprits = culprits or {by_id[i] for i, (r, _) in zip(ids, cells) if i in by_id and r in rows}
        culprits = culprits or set(admitted)  # progress: the batch empties a cell, so something must be withheld
        collided = tuple(sorted((sub.readings[r], BANKS[c]) for r, c in emptied))
        names = sorted(seen[k][0].rule_id for k in culprits)
        for k in culprits:
            v = verdicts[k]
            partners = ", ".join(n for n in names if n != v.candidate.rule_id)
            note = f"confirmed, but contradicts {partners} jointly on {len(collided)} cells"
            verdicts[k] = Verdict(v.candidate, FINDING, v.evidence, v.reach, note=note, collided=collided)


def _redundant(verdicts: dict, seen: dict, types: Types) -> None:
    """An admitted candidate strictly implied by another admitted one, which also removes everything it removes,
    adds nothing: NO_REACH. Judged against the round's admitted set as found, so the outcome is order-free."""
    admitted = [k for k, v in verdicts.items() if v.verdict == ADMITTED]
    rows = {k: types.rows(seen[k][0].scope) for k in admitted}
    demoted = {}
    for k in admitted:
        c = seen[k][0]
        by = sorted(
            seen[other][0].rule_id
            for other in admitted
            if other != k
            and _entails(seen[other][0], c, rows)
            and not _entails(c, seen[other][0], rows)
            and verdicts[k].reach.covered_by(verdicts[other].reach)
        )
        if by:
            demoted[k] = by
    for k, by in demoted.items():
        v = verdicts[k]
        verdicts[k] = Verdict(v.candidate, NO_REACH, v.evidence, v.reach, note="implied by " + ", ".join(by))


def _unconfirmed_note(ev: Evidence) -> str:
    if ev.co_encoded.size:
        return f"{ev.co_encoded.size} agreements, each stated by one record only"
    return "no stated witness"


def _finding_note(ev: Evidence, settlement: Settlement) -> str:
    w = ", ".join(settlement.readings[i] for i in ev.witnesses.tolist())
    k = ", ".join(settlement.readings[i] for i in ev.counterexamples.tolist())
    return f"no type separates witnesses [{w}] from counterexamples [{k}]"


@dataclass
class Round:
    verdicts: list[Verdict]
    admitted: list[Relation]
    scopes: dict[str, np.ndarray]
    receipt: dict
    census: dict = field(default_factory=dict)


def admission_round(state: State, relations, scopes: dict, settlement, types, supplied=()) -> Round:
    """Discover, judge against the current closure, admit, and close again (one turn of task 8.3's loop)."""
    candidates = pair_candidates(settlement, types) + list(supplied)
    verdicts = judge(candidates, settlement, types, state, relations, scopes)
    admitted = [v for v in verdicts if v.verdict == ADMITTED]
    new_scopes = {v.candidate.scope_name: types.mask(v.candidate.scope) for v in admitted}
    rels = [v.relation for v in admitted]
    receipt = close(state, list(relations) + rels, {**scopes, **new_scopes})
    return Round(verdicts, rels, new_scopes, receipt, state.census())


def discover(state: State, relations, scopes: dict, settlement, types, supplied=()) -> list[Round]:
    """Rounds until one admits nothing. Each admission removes states, so the loop ends."""
    rounds, relations, scopes = [], list(relations), dict(scopes)
    while True:
        r = admission_round(state, relations, scopes, settlement, types, supplied)
        rounds.append(r)
        if not r.admitted:
            return rounds
        relations += r.admitted
        scopes.update(r.scopes)
