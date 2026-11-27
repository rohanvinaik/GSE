"""Measurement over the population: H both ways, the census, frequency cohorts and per-rule reach (design E9).

Every claim about progress is a measurement. 2026-11-26 20:44: "There are several dozen million combinations of bank
encodings and associations ... you're still stuck on the scale of hundreds or thousands"; SSL 2.5: H and the
completeness equation.

H, both kinds. The marginal bits are the sum over cells of log2 |mask| (`State.bits`). The joint specification bits
count, for each reading, the complete legal configurations of its 56 banks under the relations that apply to it (the
relations whose scope holds the reading). The SSL contract: "Disconnected solved components contribute their
exhaustive witness counts and free coordinates contribute their remaining domain sizes. The marginal domain-log sum
remains an upper bound, not a substitute for the joint count. Solver limits and missing certificates leave exact
counts unavailable; conflicts earn no completion credit." So the banks a reading's multi-bank relations couple are
factored into connected components; each component's legal joint states are the natural join of its relations'
permitted tuples, counted exactly within the reading's masks; every other bank gives its mask size. A one-bank
relation couples nothing, and closure has already applied it to the mask. Readings are grouped by the relations that
apply to them and, per component, by their mask tuple, so each distinct case is counted once. A component whose join
would exceed `EXACT_JOIN_ROWS` (a solver limit, named, never a decision) gives its marginal bits and is reported as a
bound, never as an estimate. A reading with no legal configuration (an empty mask, or masks no joint state fits)
earns no bits and is counted apart.

The census counts every cell in one class (decided +1, -1, 0 or SILENT, residual, conflict) by bank, part of speech
and source family, for any population of rows: definitions now, senses when `senses.py` gives their masks.

Frequency cohorts, as the SSL contract measured release 021: the cohort's spellings ranked by SUBTLEX count
(`data/external/concreteness.csv`), buckets 1-500, 501-1500, 1501-5000, 5001+ and absent, every definition kept,
with the mean unresolved banks per definition. They are measurement cohorts, never a value decision.

Per-rule reach and kappa. Closure is local to a reading (a relation reads one reading's banks), so a rule's
contribution is measured on its own scope, leave-one-out: the closure of the premises under every relation, against
the closure without that rule. What it alone narrows or decides, and the marginal and joint bits it alone removes
(kappa, SIGNIFICANCE_WEIGHTING section 5: marginal coverage), are its reach. Where rules overlap, the overlap is
credited to none of them and reported as such: no first-credit order.
"""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .cells import _POPCOUNT, BANK_INDEX, BANKS, BIT_NAMES, NEG, POS, SILENT, ZERO, State
from .closure import close

EXACT_JOIN_ROWS = 1 << 20  # the largest component table counted exactly; a larger one is reported as a bound
CONCRETENESS = Path("data/external/concreteness.csv")
BUCKETS = ("1-500", "501-1500", "1501-5000", "5001+", "absent")
_LOG2 = np.array([0.0] + [math.log2(k) for k in range(1, 5)])
_STATES = (POS, NEG, ZERO, SILENT)


# ------------------------------------------------------------------------------------------------------ joint H


def _components(relations) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Connected components of the banks the given relations couple: (bank columns, relation indices)."""
    parent = list(range(len(BANKS)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, rel in relations:
        cols = [BANK_INDEX[b] for b in rel.banks]
        for c in cols[1:]:
            parent[find(c)] = find(cols[0])
    groups: dict[int, tuple[set, list]] = {}
    for i, rel in relations:
        root = find(BANK_INDEX[rel.banks[0]])
        banks, rels = groups.setdefault(root, (set(), []))
        banks.update(BANK_INDEX[b] for b in rel.banks)
        rels.append(i)
    return [(tuple(sorted(banks)), tuple(rels)) for banks, rels in groups.values()]


def _join(component: tuple[int, ...], relations) -> np.ndarray | None:
    """The legal joint states of a component's banks: the natural join of its relations' permitted tuples, as state
    bits in the component's column order; None when the table would exceed EXACT_JOIN_ROWS."""
    table, cols = None, []
    for rel in sorted(relations, key=lambda r: len(r.allowed)):
        rcols = [BANK_INDEX[b] for b in rel.banks]
        allowed = np.array(rel.allowed, dtype=np.uint8).reshape(-1, len(rcols))
        if table is None:
            table, cols = allowed, rcols
            continue
        shared = [c for c in rcols if c in cols]
        new = [c for c in rcols if c not in cols]
        left = [cols.index(c) for c in shared]
        right = [rcols.index(c) for c in shared]
        extra = [rcols.index(c) for c in new]
        index: dict[bytes, list[int]] = defaultdict(list)
        for j, row in enumerate(allowed):
            index[row[right].tobytes()].append(j)
        pairs = [(i, j) for i, row in enumerate(table) for j in index.get(row[left].tobytes(), ())]
        if len(pairs) > EXACT_JOIN_ROWS:
            return None
        if not pairs:
            return np.zeros((0, len(component)), dtype=np.uint8)
        li, rj = np.array(pairs).T
        table = np.concatenate([table[li], allowed[rj][:, extra]], axis=1)
        cols = cols + new
        if table.shape[0] > EXACT_JOIN_ROWS:
            return None
    order = [cols.index(c) for c in component]
    return table[:, order]


def _count(valid: np.ndarray, masks: np.ndarray) -> np.ndarray:
    """For each mask tuple (rows of `masks`), how many legal joint states fit inside it."""
    out = np.zeros(masks.shape[0], dtype=np.int64)
    if not valid.shape[0]:
        return out
    step = max(1, (1 << 24) // max(1, valid.size))
    for start in range(0, masks.shape[0], step):
        chunk = masks[start : start + step]
        out[start : start + step] = ((chunk[:, None, :] & valid[None, :, :]) != 0).all(axis=2).sum(axis=1)
    return out


def row_bits(state: State, relations, scopes=None):
    """Per reading: joint specification bits, whether it has a legal configuration, and whether a component of it
    was too large to count (its bits are then that component's marginal bound); and the components counted."""
    masks = state.masks
    n = masks.shape[0]
    scopes = dict(scopes or {})
    coupled = [(i, r) for i, r in enumerate(relations) if len(r.banks) >= 2]
    per_bank = _LOG2[_POPCOUNT[masks]]
    bits = per_bank.sum(axis=1)
    satisfiable = (masks != 0).all(axis=1)
    bounded = np.zeros(n, dtype=bool)
    report = []
    if not coupled or not n:
        return bits, satisfiable, bounded, report
    member = np.stack([np.ones(n, dtype=bool) if r.scope == "all" else scopes[r.scope] for _, r in coupled])
    signatures, inverse = np.unique(np.packbits(member.T, axis=1), axis=0, return_inverse=True)
    inverse = inverse.ravel()
    order = np.argsort(inverse, kind="stable")
    starts = np.searchsorted(inverse[order], np.arange(signatures.shape[0] + 1))
    cache: dict[tuple, np.ndarray | None] = {}
    for s in range(signatures.shape[0]):
        rows = order[starts[s] : starts[s + 1]]
        active = [coupled[k] for k in np.flatnonzero(member[:, rows[0]])]
        for banks, rels in _components(active):
            key = (banks, rels)
            if key not in cache:
                cache[key] = _join(banks, [relations[i] for i in rels])
            valid = cache[key]
            if valid is None:
                bounded[rows] = True
                report.append(_component_entry(banks, rels, relations, rows.size, None, True))
                continue
            unique, back = np.unique(masks[np.ix_(rows, banks)], axis=0, return_inverse=True)
            counted = _count(valid, unique)[back.ravel()]
            satisfiable[rows[counted == 0]] = False
            exact = np.log2(np.maximum(counted, 1))
            bits[rows] += exact - per_bank[np.ix_(rows, banks)].sum(axis=1)
            report.append(_component_entry(banks, rels, relations, rows.size, valid, False))
    return bits, satisfiable, bounded, report


def joint(state: State, relations, scopes=None) -> dict:
    """Marginal and joint specification bits of `state` under `relations` (scoped by `scopes`)."""
    bits, satisfiable, bounded, report = row_bits(state, relations, scopes)
    per_bank = _LOG2[_POPCOUNT[state.masks]]
    return {
        "marginal_bits": float(per_bank.sum()),
        "joint_bits": float(bits[satisfiable].sum()),
        "marginal_bits_of_satisfiable": float(per_bank[satisfiable].sum()),
        "exact": not bounded.any(),
        "readings": int(state.masks.shape[0]),
        "readings_without_configuration": int((~satisfiable).sum()),
        "readings_with_a_bound": int(bounded.sum()),
        "components": _merge_components(report),
    }


def _component_entry(banks, rels, relations, readings, valid, bounded) -> dict:
    return {
        "banks": [BANKS[c] for c in banks],
        "relations": [relations[i].rule_id for i in rels],
        "readings": int(readings),
        "legal_joint_states": None if valid is None else int(valid.shape[0]),
        "bounded": bounded,
    }


def _merge_components(entries) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for e in entries:
        key = (tuple(e["banks"]), tuple(e["relations"]))
        if key in merged:
            merged[key]["readings"] += e["readings"]
        else:
            merged[key] = dict(e)
    return sorted(merged.values(), key=lambda e: -e["readings"])


# ------------------------------------------------------------------------------------------------------ census


def _classes(masks: np.ndarray) -> dict[str, np.ndarray]:
    counts = _POPCOUNT[masks]
    one = counts == 1
    out = {BIT_NAMES[b]: one & (masks == b) for b in _STATES}
    out["residual"] = counts > 1
    out["conflict"] = counts == 0
    return out


def census(masks: np.ndarray, pos=None, source=None, kind=None) -> dict:
    """Every cell in one class, overall, by bank, by part of speech, by source family and by kind (one label per row;
    for senses, kind is "sense" or "exception")."""
    classes = _classes(masks)
    out = {
        "rows": int(masks.shape[0]),
        "cells": int(masks.size),
        "by_state": {k: int(v.sum()) for k, v in classes.items()},
        "by_bank": {bank: {k: int(v[:, c].sum()) for k, v in classes.items()} for c, bank in enumerate(BANKS)},
    }
    for name, labels in (("by_pos", pos), ("by_source", source), ("by_kind", kind)):
        if labels is None:
            continue
        labels = np.asarray(labels)
        groups = {}
        for label in sorted(set(labels.tolist())):
            rows = labels == label
            groups[label] = {"rows": int(rows.sum())} | {k: int(v[rows].sum()) for k, v in classes.items()}
        out[name] = groups
    return out


# ------------------------------------------------------------------------------------------- frequency cohorts


def spelling(word: str) -> str:
    return " ".join(word.lower().replace("_", " ").split())


def subtlex_counts(path: Path = CONCRETENESS) -> dict[str, int]:
    """SUBTLEX counts by spelling, read from the concreteness norms' SUBTLEX column."""
    out: dict[str, int] = {}
    with Path(path).open(encoding="utf-8") as src:
        for row in csv.DictReader(src):
            try:
                count = int(float(row["SUBTLEX"]))
            except TypeError, ValueError:
                continue
            key = spelling(row["Word"])
            out[key] = max(out.get(key, 0), count)
    return out


def bucket_of(lemmas, counts: dict[str, int]) -> np.ndarray:
    """Each row's cohort: the rank of its spelling among the cohort's counted spellings, or absent."""
    spellings = [spelling(lemma) for lemma in lemmas]
    ranked = sorted({s for s in spellings if counts.get(s, 0) > 0}, key=lambda s: (-counts[s], s))
    rank = {s: i for i, s in enumerate(ranked, 1)}

    def name(s):
        r = rank.get(s)
        if r is None:
            return "absent"
        return "1-500" if r <= 500 else "501-1500" if r <= 1500 else "1501-5000" if r <= 5000 else "5001+"

    return np.array([name(s) for s in spellings])


def frequency_buckets(masks: np.ndarray, lemmas, counts: dict[str, int]) -> dict:
    """Per frequency cohort: spellings, definitions, and the mean unresolved banks, decided cells and marginal bits
    per definition. Every definition is kept."""
    buckets = bucket_of(lemmas, counts)
    spellings = np.array([spelling(lemma) for lemma in lemmas])
    k = _POPCOUNT[masks]
    unresolved, decided = (k > 1).sum(axis=1), (k == 1).sum(axis=1)
    bits = _LOG2[k].sum(axis=1)
    out = {}
    for name in BUCKETS:
        rows = buckets == name
        n = int(rows.sum())
        out[name] = {
            "spellings": int(np.unique(spellings[rows]).size),
            "definitions": n,
            "mean_unresolved_banks": float(unresolved[rows].mean()) if n else 0.0,
            "mean_decided_banks": float(decided[rows].mean()) if n else 0.0,
            "mean_marginal_bits": float(bits[rows].mean()) if n else 0.0,
        }
    return out


# ----------------------------------------------------------------------------------------------- per-rule reach


def _sub(state: State, rows: np.ndarray, scopes: dict) -> tuple[State, dict]:
    return (
        State(tuple(state.readings[i] for i in rows.tolist()), state.masks[rows].copy()),
        {k: v[rows] for k, v in scopes.items()},
    )


def rule_reach(premises: State, relations, scopes=None, rules=None) -> dict:
    """Each rule's leave-one-out reach on its own scope: the closure of `premises` under every relation against the
    closure without that rule. `rules` (rule ids) limits which rules are measured."""
    relations = tuple(relations)
    scopes = dict(scopes or {})
    n = len(premises.readings)
    full = premises.copy()
    close(full, relations, scopes)
    every = np.ones(n, dtype=bool)
    wanted = None if rules is None else set(rules)
    out = []
    for i, rel in enumerate(relations):
        if wanted is not None and rel.rule_id not in wanted:
            continue
        rows = np.flatnonzero(every if rel.scope == "all" else scopes[rel.scope])
        if not rows.size:
            out.append(_reach_entry(rel, 0, 0, 0, 0.0, 0.0, Counter()))
            continue
        base, sub_scopes = _sub(premises, rows, scopes)
        # Only the relations whose scope meets these readings can act on them.
        meets = [r.scope == "all" or bool(sub_scopes[r.scope].any()) for r in relations]
        others = tuple(r for j, r in enumerate(relations) if j != i and meets[j])
        present = tuple(r for j, r in enumerate(relations) if meets[j])
        without = base.copy()
        close(without, others, sub_scopes)
        within = full.masks[rows]
        narrowed = within != without.masks
        decided = (_POPCOUNT[within] == 1) & (_POPCOUNT[without.masks] > 1)
        marginal = float(_LOG2[_POPCOUNT[without.masks]].sum() - _LOG2[_POPCOUNT[within]].sum())
        bits_without, ok_without, _, _ = row_bits(without, others, sub_scopes)
        bits_with, ok_with, _, _ = row_bits(State(base.readings, within.copy()), present, sub_scopes)
        both = ok_without & ok_with
        kappa = float((bits_without[both] - bits_with[both]).sum())
        states = Counter(BIT_NAMES[int(m)] for m in within[decided].tolist())
        entry = _reach_entry(rel, rows.size, int(narrowed.sum()), int(decided.sum()), marginal, kappa, states)
        entry["readings_it_leaves_without_configuration"] = int((ok_without & ~ok_with).sum())
        out.append(entry)
    total_marginal = float(premises.bits() - full.bits())
    credited = sum(e["marginal_bits"] for e in out)
    return {
        "rules": out,
        "bits_removed_by_all": total_marginal,
        "bits_credited_to_single_rules": credited,
        "bits_in_overlap": total_marginal - credited if wanted is None else None,
    }


def _reach_entry(rel, scope, narrowed, decided, marginal, kappa, states) -> dict:
    return {
        "rule": rel.rule_id,
        "banks": list(rel.banks),
        "scope_readings": int(scope),
        "cells_narrowed": narrowed,
        "cells_decided": decided,
        "decided_states": dict(sorted(states.items())),
        "marginal_bits": marginal,
        "kappa_joint_bits": kappa,
    }


# ------------------------------------------------------------------------------------------------------ receipt


def receipt(
    settlement, readings, relations, premises: State | None = None, counts=None, senses=None, sense_scopes=None
) -> dict:
    """Both layers of a settled round: joint and marginal H, the census by state, bank, part of speech and source
    family, and the frequency cohorts; with `premises`, each rule's leave-one-out reach on the known layer's scopes.

    `senses` is `senses.Senses.columns(readings)`: per-layer sense masks (`known`, `interpolated`) with each sense's
    `lemma`, `pos`, `kind` and `source`. The senses get the same census (with their kind) and frequency cohorts, and,
    with `sense_scopes` (layer name -> the guard scopes over the senses), their joint and marginal H."""
    relations = tuple(relations)
    pos = [r.pos for r in readings]
    source = [r.source for r in readings]
    lemmas = [r.lemma for r in readings]
    counts = subtlex_counts() if counts is None else counts
    layers = {}
    for name, state, scopes in (
        ("known", settlement.known, settlement.known_scopes),
        ("interpolated", settlement.state, settlement.scopes),
    ):
        layers[name] = {
            "H": joint(state, relations, scopes),
            "census": census(state.masks, pos, source),
            "frequency": frequency_buckets(state.masks, lemmas, counts),
        }
        if senses is not None:
            masks = np.asarray(senses[name], dtype=np.uint8)
            entry = {
                "census": census(masks, senses["pos"], senses["source"], senses.get("kind")),
                "frequency": frequency_buckets(masks, senses["lemma"], counts),
            }
            if sense_scopes is not None and name in sense_scopes:
                sense_state = State(tuple(str(i) for i in range(masks.shape[0])), masks.copy())
                entry["H"] = joint(sense_state, relations, sense_scopes[name])
            layers[name]["senses"] = entry
    out = {"layers": layers}
    if premises is not None:
        out["rules"] = rule_reach(premises, relations, settlement.known_scopes)
    return out
