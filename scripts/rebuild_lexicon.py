"""The rebuild's round runner: every channel on main in full-population rounds, to the kappa -> 0 stop (task 8.3).

Design E9: "Each round reports how much H fell, split into direct premises, structural consequences and admitted
population laws." Significance Weighting 16.7: the loop stops when a round admits nothing (kappa -> 0).

1. Load. The pinned cohort and its opening state. The stated premises: closed-class rows, the examined prime
   profiles with their law-derived decisions, and the approved anchors, read by `lexicon_rebuild_discovery` and
   applied through `coherence.apply`, which leaves a cell they would empty alone. The source lenses (`projection`)
   and the NSM content (`nsm`) as restriction relations (`restrictions`), so closure names their rules. The authored
   laws (`laws.compile_laws`) over the guard scopes (`guards.scopes`, with the lens facts). Every obligation, lens
   and NSM, as one `obligations.Batch`: a joint NSM obligation is its single-bank obligations sharing a witness, and
   the witnesses are renumbered so two sources never share one. The WordNet graph (`inheritance`). Extensions
   (`extensions`) add nodes, edges, identity classes, obligations and facts. The Wiktionary binding
   (`wiktionary_binding.py`) is one: its edges in the graph's declared families, its classes to `settle`'s
   `classes`, its topic facts to the scopes, and its identity obligations to the resolver between rounds.
2. Settle. `inheritance.settle`: closure, forcing and woken facts to the known layer, then inheritance to the
   interpolated layer.
3. Discover and admit. `admission.discover` on every stated observation (premises, lens and NSM restrictions),
   with the conflicted cells excluded and the known layer, forced obligations included, as what is known.
4. Between rounds, never inside one (the graph is fixed within a round's fixed point), the identity obligations go
   to the resolver (`extensions.resolve_identities`, over `identities.resolve`, on the known layer). Each one left
   with a single target becomes a link for the next round, proposed, and an identity link also joins its readings'
   class. The classes the stated identities join (`Graph.stated_identities`) act in both layers, every class in the
   interpolated one. The admitted relations and the added links join the next round, which settles again. A round
   that admits no rule and adds no link ends the run.
5. Measure, for the known and the interpolated layer apart: H, the census, the decided cells by warrant, the cells
   by bank, the obligation groups forced, open and in conflict, the suspensions, and wall time and memory.
6. Persist the final state and its provenance under `data/lexicon_builder/rebuild/` (gitignored), and the receipt.

Provenance. Every narrowed cell names the warrant class and the rule of its last narrowing: a stated premise (its
root), a profile derivation, a law, a lens rule, an NSM record, a forced obligation, a stated identity, an admitted
rule, an inherited default (its origin) or a consequence of defaults. The known layer's come from `settle` itself:
its removal record and its ordered steps (`Settlement.known_steps`). A cell the interpolated layer holds narrower
than the known layer rests on a default: it is inherited where a default landed on it, and a consequence of defaults
otherwise.
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
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder import (  # noqa: E402
    admission,
    coherence,
    extensions,
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
from GSE.curation.lexicon_builder.closure import Derivations  # noqa: E402

COHORT = ROOT / "data/lexicon_builder/rebuild/cohort.jsonl"
STATE_OUT = ROOT / "data/lexicon_builder/rebuild/round-final.npz"
RECEIPT = ROOT / "docs/verification/2026-11-27-rebuild-round.json"
MAX_ROUNDS = 64  # a guard only: every admission removes states, so the loop ends well before

UNTOUCHED, STATED, PROFILE_DERIVATION, LAW, LENS, NSM, FORCED, ADMITTED, INHERITED, CONSEQUENCE, IDENTITY = range(11)
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
    "stated_identity",
)
_PREFIX_CLASS = {
    "stated": STATED,
    "derived": PROFILE_DERIVATION,
    "lens": LENS,
    "nsm": NSM,
    "forced": FORCED,
    "coherence": ADMITTED,
    "inherit": INHERITED,
    "identity": IDENTITY,
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


Extension = extensions.Extension


def wiktionary_extension(readings) -> Extension:
    """The Wiktionary binding (`wiktionary_binding.py`, the lenses implementer's, task 6.2) as an extension."""
    return extensions.wiktionary(readings)


def identity_resolver() -> extensions.Resolver:
    """The resolver of identity obligations, between rounds (`identities.resolve`, the inheritance implementer's)."""
    return extensions.resolve_identities


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
    general_premises: State  # the premises without the reading-confined statements, which near-misses read
    premise_rule: np.ndarray  # readings x banks: the rule code of each premise narrowing, -1 elsewhere
    premise_conflicts: list
    relations: tuple
    scopes: dict[str, np.ndarray]
    batch: ob.Batch
    groups: dict[str, list[int]]
    links: list
    graph: inheritance.Graph
    classes: np.ndarray | None
    known_classes: np.ndarray | None
    identity_obligations: list
    resolver: extensions.Resolver | None
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
    readings,
    lens,
    compiled,
    stated,
    derivations,
    links,
    channels=(),
    types_facts=None,
    discovery=None,
    resolver=None,
) -> Inputs:
    """The round's inputs from loaded parts. Tests pass synthetic parts; `load` passes the real ones. `channels` are
    `extensions.Extension`s; `resolver` resolves their identity obligations between rounds."""
    discovery = discovery or _discovery()
    ids = tuple(r.reading_id for r in readings)
    n = len(ids)
    channels = tuple(e for e in channels if e is not None)
    skipped: Counter = Counter()
    observations = list(stated)
    observations += discovery.lens_observations(lens, ids, skipped) + discovery.nsm_observations(compiled, ids, skipped)
    table = RuleTable()
    premises = State.opening(ids)
    before = premises.masks.copy()
    premise_settlement = coherence.settle(stated, ids)
    premise_conflicts = coherence.apply(premises, premise_settlement, derivations)
    premise_rule = _premise_rules(stated, derivations, ids, before, premises.masks, table)
    general_premises = State.opening(ids)
    coherence.apply(general_premises, premise_settlement.generalizing(), derivations)
    law_relations = laws.compile_laws()
    checks = laws.required_checks()
    wanted = {r.scope for r in law_relations} | {c.scope for c in checks}
    facts = {name: mask.copy() for name, mask in lens.facts.items()}
    channel_facts: dict[str, np.ndarray] = {}
    for ext in channels:
        for name, mask in ext.facts.items():
            channel_facts[name] = channel_facts[name] | mask if name in channel_facts else mask.copy()
    for name, mask in channel_facts.items():
        facts[name] = facts[name] | mask if name in facts else mask.copy()
    scopes = guards.scopes(readings, wanted, facts)
    scopes |= {name: mask for name, mask in channel_facts.items() if name not in scopes}
    lens_relations, lens_scopes = projection.restriction_relations(lens.restrictions, n)
    nsm_relations, nsm_scopes = restrictions.restriction_relations(compiled, n)
    scopes |= lens_scopes | nsm_scopes
    batch = ob.Batch.of(_obligations(lens, compiled, channels))
    groups = inheritance.wordnet_groups(readings)
    all_links = list(links)
    for ext in channels:
        groups |= ext.groups
        all_links += ext.links
    graph = inheritance.build(groups, all_links)
    given = [ext.known_classes for ext in channels if ext.known_classes is not None]
    known_classes = extensions.join_classes(n, given) if given else known_classes_of(graph, n)
    classes = extensions.join_classes(n, [ext.classes for ext in channels] + [known_classes])
    identity_obligations = [o for ext in channels for o in ext.identity_obligations]
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
        "extensions": {e.name: e.receipt for e in channels},
        "identity_classes_with_several_readings": int((np.bincount(classes) > 1).sum()) if classes is not None else 0,
        "known_classes_with_several_readings": int((np.bincount(known_classes) > 1).sum())
        if known_classes is not None
        else 0,
        "identity_obligations": len(identity_obligations),
        "resolver": getattr(resolver, "__name__", None) if resolver is not None else None,
    }
    return Inputs(
        readings=tuple(readings),
        ids=ids,
        premises=premises,
        general_premises=general_premises,
        premise_rule=premise_rule,
        premise_conflicts=premise_conflicts,
        relations=tuple(lens_relations) + tuple(nsm_relations) + tuple(law_relations),
        scopes=scopes,
        batch=batch,
        groups=groups,
        links=all_links,
        graph=graph,
        classes=classes,
        known_classes=known_classes,
        identity_obligations=identity_obligations,
        resolver=resolver,
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
        identity_resolver(),
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


def provenance(inputs: Inputs, settled, record: Derivations) -> Provenance:
    """Each cell's last narrowing in each layer: the premises, then the known layer's steps in `settle`'s order (its
    closure removals from `record`, stated identities, forcings), then the interpolated layer's defaults."""
    table = inputs.table
    shape = settled.known.masks.shape
    removed = record.arrays()
    codes_of_rule = np.array([table(r) for r in removed["rule_ids"].tolist()], dtype=np.int32)
    chunks: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for step in settled.known_steps:
        if step[0] == "close":
            _, first, end = step
            if end > first:
                rules = removed["rules"][first:end]
                chunks.append((removed["rows"][first:end], removed["cols"][first:end], codes_of_rule[rules]))
        elif step[0] == "identity":
            rows, cols = step[1], step[2]
            if rows.size:
                chunks.append((rows, cols, np.full(rows.size, table("identity:stated"), dtype=np.int32)))
        elif step[0] == "force":
            rows, cols, by = step[1], step[2], step[3]
            if rows.size:
                codes = np.array([table(f"forced:{inputs.batch.rule_ids[i]}") for i in by.tolist()], dtype=np.int32)
                chunks.append((rows, cols, codes))
    known_rule = inputs.premise_rule.copy()
    if chunks:
        rows, cols, codes = (np.concatenate([np.asarray(x, dtype=np.int64) for x in part]) for part in zip(*chunks))
        rows, cols, codes = _last(rows, cols, codes, shape)
        known_rule[rows, cols] = codes
    interpolated_rule = known_rule.copy()
    moved = settled.interpolated
    interpolated_rule[moved] = table("inherit:consequence")
    o = settled.origins()
    names = [f.name for f in settled.graph.families] + ["synonymy"]
    keys = settled.graph.keys
    codes = np.array(
        [table(f"inherit:{names[f]}:{keys[g]}") for f, g in zip(o["family"].tolist(), o["origin"].tolist())],
        dtype=np.int32,
    )
    rows, cols, codes = _last(o["rows"], o["cols"], codes, shape)
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


def obligation_status(state: State, batch: ob.Batch, classes=None) -> dict:
    """Obligation groups at a fixed point: located (forced on one reading, or one identity class), open (two or more
    fit), in conflict (none fits) or blocked (a member cell is already a conflict). Read by one sweep over a copy."""
    if not len(batch):
        return {"groups": 0, "located": 0, "open": 0, "conflict": 0, "blocked": 0}
    sweep = ob.force(state.copy(), batch, classes)
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


def measure(state: State, classes: np.ndarray, batch: ob.Batch, identity_classes=None) -> dict:
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
        "obligations": obligation_status(state, batch, identity_classes),
    }


@dataclass
class Settled:
    settlement: inheritance.Settlement
    provenance: Provenance
    relations: tuple
    scopes: dict
    seconds: float
    classes: np.ndarray | None = None
    known_classes: np.ndarray | None = None


def known_classes_of(graph: inheritance.Graph, n: int) -> np.ndarray | None:
    """The classes the stated identity links join, or None when they join no two readings."""
    known = graph.stated_identities(n)
    return known if (known != np.arange(n)).any() else None


def settle_round(inputs: Inputs, admitted=(), admitted_scopes=None, graph=None, classes=None) -> Settled:
    """One round to its fixed point, over the round's graph and identity classes (the inputs' when not given)."""
    relations = inputs.relations + tuple(admitted)
    scopes = inputs.scopes | dict(admitted_scopes or {})
    graph = inputs.graph if graph is None else graph
    classes = inputs.classes if classes is None else classes
    known = inputs.known_classes  # stated identities only; a link resolved between rounds is proposed
    started = time.perf_counter()
    record = Derivations()
    settlement = inheritance.settle(
        inputs.premises, graph, relations, scopes, inputs.batch, classes=classes, known_classes=known, record=record
    )
    prov = provenance(inputs, settlement, record)
    return Settled(settlement, prov, relations, scopes, round(time.perf_counter() - started, 2), classes, known)


def discover_round(inputs: Inputs, settled: Settled) -> tuple[list, dict, dict]:
    """Admission over every stated observation, conflicted cells excluded, the known layer as what is known, and the
    same layer without the reading-confined statements as what near-misses read."""
    started = time.perf_counter()
    s = settled.settlement
    conflicts = coherence.closure_conflicts(s.known, inputs.stated, settled.provenance.derivations)
    # Near-misses read the same known layer closed from the premises that may generalize (coherence.knowing): the same
    # graph, relations, scopes, obligations and identity classes, so its stated identities act as in `s.known`.
    general = inheritance.settle(
        inputs.general_premises,
        s.graph,
        settled.relations,
        settled.scopes,
        inputs.batch,
        classes=settled.classes,
        known_classes=settled.known_classes,
    )
    stated = inputs.stated.excluding(inputs.premise_conflicts + conflicts).knowing(s.known, general.known)
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
    """Both layers measured, each with the identity classes `settle` gave it."""
    s, p = settled.settlement, settled.provenance
    known = measure(s.known, warrant_classes(p.known_rule, inputs.table), inputs.batch, settled.known_classes)
    interpolated = measure(s.state, warrant_classes(p.interpolated_rule, inputs.table), inputs.batch, settled.classes)
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


def resolve_between_rounds(inputs: Inputs, settled: Settled, pending: list) -> tuple[extensions.Resolved, dict]:
    """The identity obligations against the settled round: the links that now have one target, and what is left."""
    if inputs.resolver is None or not pending:
        resolved = extensions.Resolved([], list(pending), 0, [])
    else:
        resolved = inputs.resolver(settled.settlement, inputs.readings, list(pending))
    receipt = {
        "resolver": inputs.resolver is not None,
        "pending_before": len(pending),
        "pending_after": len(resolved.pending),
        "conflicts": resolved.conflicts,
        "identity_joins": len(resolved.joins),
        "links_added": len(resolved.links),
        "links_added_by_family": dict(sorted(Counter(link[0] for link in resolved.links).items())),
        "links_added_by_standing": dict(
            sorted(Counter(str(link[3]) if len(link) > 3 else "unstated" for link in resolved.links).items())
        ),
    }
    return resolved, receipt


def run(inputs: Inputs, max_rounds: int = MAX_ROUNDS) -> tuple[list[dict], Settled]:
    """Settle, discover and admit, resolve identities between rounds, and again, until a round admits no rule and
    adds no link."""
    admitted, admitted_scopes, rounds = [], {}, []
    added, pending, joins = [], list(inputs.identity_obligations), []
    graph, classes = inputs.graph, inputs.classes
    for number in range(1, max_rounds + 1):
        started = time.perf_counter()
        settled = settle_round(inputs, admitted, admitted_scopes, graph, classes)
        receipt = {"round": number, "settle_seconds": settled.seconds, "links_in_force": len(added)}
        receipt |= layer_receipts(inputs, settled)
        new, scopes, receipt["discovery"] = discover_round(inputs, settled)
        resolved, receipt["identities"] = resolve_between_rounds(inputs, settled, pending)
        receipt["admitted_relations_in_force"] = len(admitted)
        receipt["seconds"] = round(time.perf_counter() - started, 2)
        receipt["peak_memory_mb"] = _memory_mb()
        rounds.append(receipt)
        fresh = [link for link in resolved.links if link not in set(added)]
        if not new and not fresh:
            return rounds, settled
        admitted += new
        admitted_scopes |= scopes
        pending = resolved.pending
        if resolved.joins:
            joins += resolved.joins
            classes = extensions.join_classes(len(inputs.ids), [inputs.classes, inputs.known_classes], joins)
        if fresh:
            added += fresh
            graph = inheritance.build(inputs.groups, inputs.links + added)
    raise RuntimeError("ROUNDS_DID_NOT_REACH_A_ROUND_ADDING_NOTHING")


# --- Persist and report -----------------------------------------------------------------------------------------


def persist(path: Path, inputs: Inputs, settled: Settled) -> dict:
    """The final state and its provenance: both layers' masks, the reading ids, each cell's warrant class and rule
    (codes into `rule_ids`, -1 for a cell never narrowed), and the known layer's guard facts (`fact_names` x readings,
    the scopes the laws select on, located facts included), which the senses read."""
    s, p = settled.settlement, settled.provenance
    path.parent.mkdir(parents=True, exist_ok=True)
    wanted = sorted({r.scope for r in laws.compile_laws()} | {c.scope for c in inputs.checks})
    wanted += sorted(name for name in s.known_scopes if name.startswith("wiktionary_topic=") and name not in wanted)
    facts = np.stack([s.known_scopes[name] for name in wanted]) if wanted else np.zeros((0, len(inputs.ids)), bool)
    np.savez_compressed(
        path,
        fact_names=np.array(wanted, dtype=object),
        known_facts=np.packbits(facts, axis=1),
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
    "extensions",
    "identities",
    "wiktionary_binding",
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
