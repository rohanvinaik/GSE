"""The rebuild's round runner: every channel on main in full-population rounds, to the kappa -> 0 stop (task 8.3).

Design E9: "Each round reports how much H fell, split into direct premises, structural consequences and admitted
population laws." Significance Weighting 16.7: the loop stops when a round admits nothing (kappa -> 0).

1. Load. The pinned cohort and its opening state. The stated premises: closed-class rows, the examined prime
   profiles with their law-derived decisions, and the approved anchors, read by `lexicon_rebuild_discovery` and
   applied through `coherence.apply`, which leaves a cell they would empty alone. The source lenses (`projection`)
   and the NSM content (`nsm`) as restriction relations (`restrictions`), so closure names their rules. The authored
   laws (`laws.compile_laws`) over the guard scopes (`guards.scopes`, with the lens facts). Every obligation, lens
   and NSM, as one `obligations.Batch`: a joint NSM obligation is its single-bank obligations sharing a witness, and
   the witnesses are renumbered so two sources never share one. The WordNet graph (`inheritance`). Extensions add
   nodes, edges, obligations and facts; the Wiktionary binding (`wiktionary_binding.py`, the lenses implementer's)
   arrives through `wiktionary_extension` and is left out of this runner until it lands.
2. Settle. `inheritance.settle`: closure, forcing and woken facts to the known layer, then inheritance to the
   interpolated layer.
3. Discover and admit. `admission.discover` on every stated observation (premises, lens and NSM restrictions),
   with the conflicted cells excluded and the known layer as what is known. The admitted relations join the round's
   relations and the round settles again. A round that admits nothing ends the run.
4. Measure, for the known and the interpolated layer apart: H, the census, the decided cells by warrant, the cells
   by bank, the obligation groups forced, open and in conflict, the suspensions, and wall time and memory.
5. Persist the final state and its provenance under `data/lexicon_builder/rebuild/` (gitignored), and the receipt.

Provenance. Every narrowed cell names the warrant class and the rule of its last narrowing: a stated premise (its
root), a profile derivation, a law, a lens rule, an NSM record, a forced obligation, an admitted rule, an inherited
default (its origin) or a consequence of defaults. `inheritance.settle` keeps no per-cell record, so the known
layer is replayed with the same operators (`closure.close` with a `Derivations` record, `obligations.force`,
`obligations.wake`) and must reach exactly the layer `settle` reached; the run stops if it does not. A cell the
interpolated layer holds narrower than the known layer rests on a default: it is inherited where a default landed
on it, and a consequence of defaults otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import resource
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder import (  # noqa: E402
    admission,
    coherence,
    guards,
    inheritance,
    inventory,
    laws,
    nsm,
    projection,
    restrictions,
)
from GSE.curation.lexicon_builder import obligations as ob  # noqa: E402
from GSE.curation.lexicon_builder.cells import BANKS, BIT_NAMES, START, State  # noqa: E402
from GSE.curation.lexicon_builder.closure import Derivations, close  # noqa: E402

COHORT = ROOT / "data/lexicon_builder/rebuild/cohort.jsonl"
STATE_OUT = ROOT / "data/lexicon_builder/rebuild/round-final.npz"
RECEIPT = ROOT / "docs/verification/2026-11-27-rebuild-round.json"
MAX_ROUNDS = 64  # a guard only: every admission removes states, so the loop ends well before

UNTOUCHED, STATED, PROFILE_DERIVATION, LAW, LENS, NSM, FORCED, ADMITTED, INHERITED, CONSEQUENCE = range(10)
CLASSES = (
    "untouched",
    "stated",
    "profile_derivation",
    "law",
    "lens",
    "nsm",
    "forced_obligation",
    "admitted",
    "inherited",
    "inherited_consequence",
)
_PREFIX_CLASS = {
    "stated": STATED,
    "derived": PROFILE_DERIVATION,
    "lens": LENS,
    "nsm": NSM,
    "forced": FORCED,
    "coherence": ADMITTED,
    "inherit": INHERITED,
}
_STATE_BITS = tuple(BIT_NAMES)


def _discovery():
    """The stated-premise loaders of `scripts/lexicon_rebuild_discovery.py` (the coherence implementer's), loaded by
    path: `scripts` is not a package."""
    path = ROOT / "scripts/lexicon_rebuild_discovery.py"
    spec = importlib.util.spec_from_file_location("lexicon_rebuild_discovery", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- Inputs -----------------------------------------------------------------------------------------------------


@dataclass
class Extension:
    """A channel that adds to the round: graph nodes (`groups`, node key -> reading rows), edges (`links`, (family,
    giver, receiver), in families `inheritance` declares), obligations, and guard facts. The Wiktionary binding
    arrives as one."""

    name: str
    groups: dict[str, list[int]] = field(default_factory=dict)
    links: list[tuple[str, str, str]] = field(default_factory=list)
    obligations: list = field(default_factory=list)
    facts: dict[str, np.ndarray] = field(default_factory=dict)


def wiktionary_extension(readings) -> Extension | None:
    """The hook for the Wiktionary binding (`wiktionary_binding.py`, the lenses implementer's, task 6.2).

    Left out of this runner until it lands. When it does, it returns its binding here: a node per bound reading
    outside WordNet (`Binding.groups`), its identity edges (`Binding.links`, with their families added to the
    graph's), its identity and alignment obligations, and its `wiktionary_topic=<t>` facts.
    """
    return None


class RuleTable:
    """Rule ids as dense codes, for the per-cell provenance arrays."""

    def __init__(self):
        self.ids: list[str] = []
        self.code: dict[str, int] = {}

    def __call__(self, rule_id: str) -> int:
        if rule_id not in self.code:
            self.code[rule_id] = len(self.ids)
            self.ids.append(rule_id)
        return self.code[rule_id]

    def classes(self) -> np.ndarray:
        """The warrant class of every rule code, by its prefix; an authored law has none of the others."""
        return np.array([_PREFIX_CLASS.get(r.split(":", 1)[0], LAW) for r in self.ids], dtype=np.uint8)


@dataclass
class Inputs:
    """Everything a round reads, composed once."""

    readings: tuple
    ids: tuple[str, ...]
    premises: State
    premise_rule: np.ndarray  # readings x banks: the rule code of each premise narrowing, -1 elsewhere
    premise_conflicts: list
    relations: tuple
    scopes: dict[str, np.ndarray]
    batch: ob.Batch
    graph: inheritance.Graph
    stated: coherence.Settlement
    types_facts: dict[str, np.ndarray]
    checks: tuple
    table: RuleTable
    counts: dict


def _obligations(lens, compiled, extensions) -> list[ob.Obligation]:
    """Lens, NSM and extension obligations, with witnesses renumbered so no two sources share one."""
    out, base = [], 0

    def take(items, source):
        nonlocal base
        top = base
        for o in items:
            w = getattr(o, "witness", None)
            witness = None if w is None else base + int(w)
            top = max(top, (witness or 0) + 1)
            premises = tuple(getattr(o, "premises", ())) or (f"{source}:{o.rule_id}",)
            facts = tuple(getattr(o, "facts", ()))
            out.append(ob.Obligation(o.rule_id, o.bank, o.allowed, o.rows, witness, premises, facts))
        base = top

    take(lens.obligations, "lens")
    take([o for o in compiled.obligations if not o.joint], "nsm")
    for ext in extensions:
        take(ext.obligations, ext.name)
    return out


def _premise_rules(stated, derivations, ids, before, after, table) -> np.ndarray:
    """The rule code of each cell the premises narrowed: a stated root, or the profile derivation that narrowed it."""
    rule = np.full(after.shape, -1, dtype=np.int32)
    index = {r: i for i, r in enumerate(ids)}
    bank = {b: i for i, b in enumerate(BANKS)}
    alone: dict[tuple[int, int], tuple[int, str]] = {}
    for o in stated:
        key = (index[o.reading], bank[o.bank])
        mask, root = alone.get(key, (int(START[key[1]]), o.root))
        alone[key] = (mask & o.states, root)
    derived = {(index[d.reading], bank[d.bank]): d.rule for d in derivations}
    for r, c in zip(*np.nonzero(before != after)):
        key = (int(r), int(c))
        if key in alone and alone[key][0] == int(after[r, c]):
            rule[r, c] = table(f"stated:{alone[key][1]}")
        elif key in derived:
            rule[r, c] = table(f"derived:{derived[key]}")
        else:
            rule[r, c] = table(f"stated:{alone[key][1]}" if key in alone else "derived:unattributed")
    return rule


def compose(
    readings, lens, compiled, stated, derivations, links, extensions=(), types_facts=None, discovery=None
) -> Inputs:
    """The round's inputs from loaded parts. Tests pass synthetic parts; `load` passes the real ones."""
    discovery = discovery or _discovery()
    ids = tuple(r.reading_id for r in readings)
    n = len(ids)
    extensions = tuple(e for e in extensions if e is not None)
    skipped: Counter = Counter()
    observations = list(stated)
    observations += discovery.lens_observations(lens, ids, skipped) + discovery.nsm_observations(compiled, ids, skipped)
    table = RuleTable()
    premises = State.opening(ids)
    before = premises.masks.copy()
    premise_conflicts = coherence.apply(premises, coherence.settle(stated, ids), derivations)
    premise_rule = _premise_rules(stated, derivations, ids, before, premises.masks, table)
    law_relations = laws.compile_laws()
    checks = laws.required_checks()
    wanted = {r.scope for r in law_relations} | {c.scope for c in checks}
    facts = {name: mask.copy() for name, mask in lens.facts.items()}
    for ext in extensions:
        for name, mask in ext.facts.items():
            facts[name] = facts[name] | mask if name in facts else mask.copy()
    scopes = guards.scopes(readings, wanted, facts)
    lens_relations, lens_scopes = projection.restriction_relations(lens.restrictions, n)
    nsm_relations, nsm_scopes = restrictions.restriction_relations(compiled, n)
    scopes |= lens_scopes | nsm_scopes
    batch = ob.Batch.of(_obligations(lens, compiled, extensions))
    groups = inheritance.wordnet_groups(readings)
    all_links = list(links)
    for ext in extensions:
        groups |= ext.groups
        all_links += ext.links
    graph = inheritance.build(groups, all_links)
    if types_facts is None:
        types_facts = coherence.wordnet_types(readings)
    counts = {
        "readings": n,
        "stated_premises": len(stated),
        "profile_derivations": len(derivations),
        "premise_conflicts": len(premise_conflicts),
        "stated_observations": len(observations),
        "observation_refusals": dict(sorted(skipped.items())),
        "relations": {
            "law": len(law_relations),
            "lens": len(lens_relations),
            "nsm": len(nsm_relations),
        },
        "lens_restrictions": len(lens.restrictions),
        "nsm_restrictions": len(compiled),
        "obligations": {"single": len(batch), "groups": batch.groups},
        "graph": {"nodes": len(graph.keys), "edges": int(graph.src.size)},
        "extensions": [e.name for e in extensions],
    }
    return Inputs(
        readings=tuple(readings),
        ids=ids,
        premises=premises,
        premise_rule=premise_rule,
        premise_conflicts=premise_conflicts,
        relations=tuple(lens_relations) + tuple(nsm_relations) + tuple(law_relations),
        scopes=scopes,
        batch=batch,
        graph=graph,
        stated=coherence.settle(observations, ids),
        types_facts=types_facts,
        checks=checks,
        table=table,
        counts=counts,
    )


def load(cohort: Path = COHORT) -> tuple[Inputs, dict]:
    """The real inputs: the pinned cohort and every source on main."""
    seconds = {}
    started = time.perf_counter()
    readings = inventory.load(cohort)
    discovery = _discovery()
    sources, seconds["sources"] = projection.load_sources()
    lens = projection.project(readings, sources)
    compiled = nsm.compile_records(nsm.load_records(ROOT / nsm.RECORDS), readings)
    ids = tuple(r.reading_id for r in readings)
    index = {r: i for i, r in enumerate(ids)}
    skipped: Counter = Counter()
    bindings: dict[str, str] = {}
    stated = discovery.closed_class(index, skipped)
    profile_stated, profile_derived = discovery.prime_profiles(index, skipped, bindings)
    stated += profile_stated + discovery.approved_anchors(index, bindings, skipped)
    seconds["load"] = round(time.perf_counter() - started, 2)
    started = time.perf_counter()
    links = list(inheritance.wordnet_links())
    types_facts = coherence.wordnet_types(readings)
    seconds["wordnet"] = round(time.perf_counter() - started, 2)
    started = time.perf_counter()
    inputs = compose(
        readings,
        lens,
        compiled,
        stated,
        profile_derived,
        links,
        (wiktionary_extension(readings),),
        types_facts,
        discovery,
    )
    seconds["compose"] = round(time.perf_counter() - started, 2)
    inputs.counts["premise_skips"] = dict(sorted(skipped.items()))
    inputs.counts["profile_bindings"] = len(bindings)
    return inputs, seconds


# --- One round --------------------------------------------------------------------------------------------------


@dataclass
class Provenance:
    """Per cell, the rule code of its last narrowing in each layer (-1: never narrowed), and the known layer's
    derivation record (for `coherence.closure_conflicts`)."""

    known_rule: np.ndarray
    interpolated_rule: np.ndarray
    derivations: Derivations


def _last(rows, cols, codes, shape) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The last entry for each cell of a chronological record."""
    if not rows.size:
        return rows, cols, codes
    key = rows * shape[1] + cols
    rev = key[::-1]
    _, first_rev = np.unique(rev, return_index=True)
    pick = key.size - 1 - first_rev
    return rows[pick], cols[pick], codes[pick]


def provenance(inputs: Inputs, relations, scopes, settled) -> Provenance:
    """Replay the known layer with a record of every removal, and check it reaches `settled.known` exactly."""
    table, batch = inputs.table, inputs.batch
    state = inputs.premises.copy()
    scopes = {name: mask.copy() for name, mask in scopes.items()}
    record = Derivations()
    chunks: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    while True:
        k = len(record.rows)
        close(state, relations, scopes, record)
        if len(record.rows) > k:
            rules = np.concatenate(record.rules[k:])
            codes = np.array([table(record.rule_ids[i]) for i in np.unique(rules)], dtype=np.int32)
            chunks.append(
                (
                    np.concatenate(record.rows[k:]),
                    np.concatenate(record.cols[k:]),
                    codes[np.searchsorted(np.unique(rules), rules)],
                )
            )
        if not len(batch):
            break
        forcing = ob.force(state, batch)
        if forcing.changed:
            codes = np.array([table(f"forced:{batch.rule_ids[i]}") for i in forcing.by.tolist()], dtype=np.int32)
            chunks.append((forcing.rows.astype(np.int64), forcing.cols.astype(np.int64), codes))
        added = ob.wake(scopes, forcing.facts)
        if forcing.changed == 0 and added == 0:
            break
    if not np.array_equal(state.masks, settled.known.masks):
        raise RuntimeError("PROVENANCE_REPLAY_DIFFERS_FROM_SETTLE")
    known_rule = inputs.premise_rule.copy()
    if chunks:
        rows, cols, codes = (np.concatenate(x) for x in zip(*chunks))
        rows, cols, codes = _last(rows, cols, codes, state.masks.shape)
        known_rule[rows, cols] = codes
    interpolated_rule = known_rule.copy()
    moved = settled.interpolated
    interpolated_rule[moved] = table("inherit:consequence")
    origins = getattr(settled, "origins", None)
    if origins is None:  # the lineage arrives with the inheritance implementer's change
        interpolated_rule[moved & settled.inherited] = table("inherit:default")
    else:
        o = origins()
        names = [f.name for f in settled.graph.families] + ["synonymy"]
        keys = settled.graph.keys
        codes = np.array(
            [table(f"inherit:{names[f]}:{keys[g]}") for f, g in zip(o["family"].tolist(), o["origin"].tolist())],
            dtype=np.int32,
        )
        rows, cols, codes = _last(o["rows"], o["cols"], codes, state.masks.shape)
        interpolated_rule[rows, cols] = codes
    return Provenance(known_rule, interpolated_rule, record)


def warrant_classes(rule: np.ndarray, table: RuleTable) -> np.ndarray:
    """The warrant class of every cell from its rule code; a consequence of defaults is its own class."""
    by_code = table.classes()
    if not by_code.size:
        return np.zeros(rule.shape, dtype=np.uint8)
    consequence = table.code.get("inherit:consequence", -2)
    out = np.where(rule >= 0, by_code[np.maximum(rule, 0)], UNTOUCHED).astype(np.uint8)
    out[rule == consequence] = CONSEQUENCE
    return out


def obligation_status(state: State, batch: ob.Batch) -> dict:
    """Obligation groups at a fixed point: located (forced on one reading), open (two or more fit), in conflict
    (none fits) or blocked (a member cell is already a conflict). Read by one sweep over a copy."""
    if not len(batch):
        return {"groups": 0, "located": 0, "open": 0, "conflict": 0, "blocked": 0}
    sweep = ob.force(state.copy(), batch)
    conflict = int(np.unique(batch.group[sweep.conflicts]).size)
    blocked = int(np.unique(batch.group[sweep.blocked]).size)
    located = int(sweep.located_rows.size)
    return {
        "groups": batch.groups,
        "located": located,
        "open": batch.groups - located - conflict - blocked,
        "conflict": conflict,
        "blocked": blocked,
        "changed_by_a_further_sweep": sweep.changed,
    }


def measure(state: State, classes: np.ndarray, batch: ob.Batch) -> dict:
    """One layer: H, the census, decided cells by warrant, every cell by warrant, cells by bank, obligations."""
    counts = state.counts()
    decided = counts == 1
    by_class = np.bincount(classes.ravel(), minlength=len(CLASSES))
    decided_by_class = np.bincount(classes[decided], minlength=len(CLASSES))
    by_class_state = Counter()
    for c, m in zip(classes[decided].tolist(), state.masks[decided].tolist()):
        by_class_state[f"{CLASSES[c]}:{BIT_NAMES[m]}"] += 1
    banks = {}
    for col, bank in enumerate(BANKS):
        m, k = state.masks[:, col], counts[:, col]
        one = k == 1
        banks[bank] = {BIT_NAMES[b]: int((one & (m == b)).sum()) for b in _STATE_BITS}
        banks[bank] |= {"residual": int((k > 1).sum()), "conflict": int((k == 0).sum())}
    return {
        "bits": state.bits(),
        "census": state.census(),
        "decided_by_warrant": {CLASSES[i]: int(v) for i, v in enumerate(decided_by_class) if v},
        "decided_by_warrant_state": dict(sorted(by_class_state.items())),
        "cells_by_warrant": {CLASSES[i]: int(v) for i, v in enumerate(by_class) if v},
        "cells_by_bank": banks,
        "obligations": obligation_status(state, batch),
    }


@dataclass
class Settled:
    settlement: inheritance.Settlement
    provenance: Provenance
    relations: tuple
    scopes: dict
    seconds: float


def settle_round(inputs: Inputs, admitted=(), admitted_scopes=None) -> Settled:
    relations = inputs.relations + tuple(admitted)
    scopes = inputs.scopes | dict(admitted_scopes or {})
    started = time.perf_counter()
    settlement = inheritance.settle(inputs.premises, inputs.graph, relations, scopes, inputs.batch)
    prov = provenance(inputs, relations, scopes, settlement)
    return Settled(settlement, prov, relations, scopes, round(time.perf_counter() - started, 2))


def discover_round(inputs: Inputs, settled: Settled) -> tuple[list, dict, dict]:
    """Admission over every stated observation, conflicted cells excluded, the known layer as what is known."""
    started = time.perf_counter()
    s = settled.settlement
    conflicts = coherence.closure_conflicts(s.known, inputs.stated, settled.provenance.derivations)
    stated = inputs.stated.excluding(inputs.premise_conflicts + conflicts).knowing(s.known)
    facts = {f"guard:{k}": v for k, v in s.known_scopes.items() if v.any()} | inputs.types_facts
    types = coherence.Types.build(len(inputs.ids), facts)
    rounds = admission.discover(s.known.copy(), settled.relations, s.known_scopes, stated, types, ())
    admitted, scopes = [], {}
    inner, evidence = [], []
    for r in rounds:
        admitted += r.admitted
        scopes |= r.scopes
        verdicts = Counter(v.verdict for v in r.verdicts)
        inner.append(
            {
                "candidates": len(r.verdicts),
                "verdicts": {k: verdicts.get(k, 0) for k in admission.VERDICTS},
                "admitted": [rel.rule_id for rel in r.admitted],
            }
        )
        evidence += [_admitted_evidence(v, stated) for v in r.verdicts if v.verdict == admission.ADMITTED]
    summary = {
        "stated_cells_excluded_as_conflicts": len(inputs.premise_conflicts) + len(conflicts),
        "types": len(types.names),
        "inner_rounds": inner,
        "admitted": [rel.rule_id for rel in admitted],
        "admitted_evidence": evidence,
        "seconds": round(time.perf_counter() - started, 2),
    }
    return admitted, scopes, summary


def _admitted_evidence(verdict, stated) -> dict:
    """What an admitted rule rests on: its witnesses and their roots by source family, its exposure and reach."""
    ev, reach = verdict.evidence, verdict.reach
    return {
        "rule": verdict.candidate.rule_id,
        "witnesses": int(ev.witnesses.size),
        "witness_examples": [stated.readings[i] for i in ev.witnesses[:5].tolist()],
        "witness_roots": len(ev.witness_roots),
        "witness_root_families": dict(sorted(Counter(r.split(":", 1)[0] for r in ev.witness_roots).items())),
        "exposure": int(ev.exposure.size),
        "unknown": int(ev.unknown.size),
        "reach_cells": reach.cells,
        "reach_decided": reach.decided,
        "reach_bits": round(reach.bits, 1),
    }


def _memory_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (1 << 20) if sys.platform == "darwin" else peak / (1 << 10), 1)


def layer_receipts(inputs: Inputs, settled: Settled) -> dict:
    s, p = settled.settlement, settled.provenance
    known = measure(s.known, warrant_classes(p.known_rule, inputs.table), inputs.batch)
    interpolated = measure(s.state, warrant_classes(p.interpolated_rule, inputs.table), inputs.batch)
    known["required_checks"] = _checks(s.known, s.known_scopes, inputs.checks)
    interpolated["required_checks"] = _checks(s.state, s.scopes, inputs.checks)
    known["obligation_conflicts"] = len(s.known_conflicts)
    interpolated["obligation_conflicts"] = len(s.interpolated_conflicts)
    interpolated["suspensions"] = {
        "cells_by_reason": s.receipt.get("suspended_cells", {}),
        "held_defaults": s.receipt.get("held", 0),
        "held_synonym_equalities": s.receipt.get("held_equal", 0),
        "unattributed_conflict": s.receipt.get("unattributed_conflict", False),
    }
    interpolated["interpolated_cells"] = int(s.interpolated.sum())
    return {"known": known, "interpolated": interpolated}


def _checks(state, scopes, checks) -> dict:
    out = laws.check(state.masks, scopes, checks)
    return {k: v for k, v in out.items() if any(v.values())}


def run(inputs: Inputs, max_rounds: int = MAX_ROUNDS) -> tuple[list[dict], Settled]:
    """Settle, discover, admit, and again, until a round admits nothing."""
    admitted, admitted_scopes, rounds = [], {}, []
    for number in range(1, max_rounds + 1):
        started = time.perf_counter()
        settled = settle_round(inputs, admitted, admitted_scopes)
        receipt = {"round": number, "settle_seconds": settled.seconds}
        receipt |= layer_receipts(inputs, settled)
        new, scopes, receipt["discovery"] = discover_round(inputs, settled)
        receipt["admitted_relations_in_force"] = len(admitted)
        receipt["seconds"] = round(time.perf_counter() - started, 2)
        receipt["peak_memory_mb"] = _memory_mb()
        rounds.append(receipt)
        if not new:
            return rounds, settled
        admitted += new
        admitted_scopes |= scopes
    raise RuntimeError("ROUNDS_DID_NOT_REACH_A_ROUND_ADMITTING_NOTHING")


# --- Persist and report -----------------------------------------------------------------------------------------


def persist(path: Path, inputs: Inputs, settled: Settled) -> dict:
    """The final state and its provenance: both layers' masks, the reading ids, and each cell's warrant class and
    rule (codes into `rule_ids`, -1 for a cell never narrowed)."""
    s, p = settled.settlement, settled.provenance
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        readings=np.array(inputs.ids, dtype=object),
        banks=np.array(BANKS, dtype=object),
        known_masks=s.known.masks,
        interpolated_masks=s.state.masks,
        known_class=warrant_classes(p.known_rule, inputs.table),
        known_rule=p.known_rule,
        interpolated_class=warrant_classes(p.interpolated_rule, inputs.table),
        interpolated_rule=p.interpolated_rule,
        rule_ids=np.array(inputs.table.ids, dtype=object),
        classes=np.array(CLASSES, dtype=object),
    )
    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "rules": len(inputs.table.ids),
    }


_MODULES = (
    "cells",
    "relations",
    "closure",
    "laws",
    "guards",
    "restrictions",
    "projection",
    "nsm",
    "nsm_frames",
    "nsm_text",
    "nsm_typing",
    "obligations",
    "inheritance",
    "coherence",
    "admission",
)


def provenance_of_code() -> dict:
    """Digests of every module and data file the round read, and whether git has them as committed."""
    files = [
        COHORT,
        ROOT / "GSE/curation/lexicon_builder/bank_laws.json",
        ROOT / "scripts/lexicon_rebuild_discovery.py",
    ]
    files += [ROOT / f"GSE/curation/lexicon_builder/{m}.py" for m in _MODULES]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *[str(f.relative_to(ROOT)) for f in files]],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split("\n")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {
        "head": head,
        "uncommitted": sorted(line[3:] for line in status if line.strip()),
        "sha256": {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    }


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cohort", type=Path, default=COHORT)
    parser.add_argument("--state", type=Path, default=STATE_OUT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    inputs, load_seconds = load(args.cohort)
    rounds, final = run(inputs)
    out = {
        "format": "GSE.rebuild-round/1",
        "code": provenance_of_code(),
        "inputs": inputs.counts,
        "graph": final.settlement.graph.counts(),
        "opening_bits": State.opening(inputs.ids).bits(),
        "premise_bits": inputs.premises.bits(),
        "rounds": rounds,
        "final_state": persist(args.state, inputs, final),
        "seconds": {"load": load_seconds, "total": round(time.perf_counter() - started, 2)},
        "peak_memory_mb": _memory_mb(),
    }
    args.receipt.write_text(json.dumps(out, indent=1, default=int) + "\n")
    return out


if __name__ == "__main__":
    result = main()
    for r in result["rounds"]:
        print(
            f"round {r['round']}: known H {r['known']['bits']:.1f}, interpolated H {r['interpolated']['bits']:.1f}, "
            f"admitted {len(r['discovery']['admitted'])}, {r['seconds']} s"
        )
    print(json.dumps(result["seconds"]), result["peak_memory_mb"], "MB")
