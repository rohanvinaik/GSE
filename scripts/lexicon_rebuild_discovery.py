"""Population discovery over the pinned cohort with the stated facts available now (rebuild task 8).

Stated facts, each from its native record (root):
- closed-class catalog rows (`GSEClosedClassParser.to_primitives_for_entry`; root = the catalog row);
- the examined prime profiles (`prime_profiles.json`; root = the profile), bound to a cohort reading only through
  the chart box the profile examined and the chart data's own alignment of that unit to the same signed pole
  (`foundation_prime_links`). Units the chart data calls candidate alignments (die, live, mine) are not bound.
  The profile's identity and asserted components are stated. Its authored silence boundary is stated but confined
  to its reading ("never to ordinary words"). Its law-derived decisions are derivations.
- the approved anchors `_APPROVED_CORRESPONDENCES` for readings no profile binds (this, dont-want, very).

The authored laws' consequences are derivations: they narrow cells and never confirm. WordNet enters only as types:
the warranted guard facts and the strict hypernym ancestors of each WordNet reading are the typed scopes. The
reviewed-root values `WordNetHierarchyParser.to_primitives_for_definition` projects (SOMEONE from person.n.01, ALIVE
from organism.n.01) are not stated facts: each is an authored hub value carried down kind-of, E8 inheritance, an
interpolated derivation, and "the engine cannot confirm from its own output" (SW 14).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from GSE.curation.lexicon_builder import guards, inventory, laws
from GSE.curation.lexicon_builder.admission import VERDICTS, discover
from GSE.curation.lexicon_builder.cells import BANK_INDEX, BANKS, NEG, NEGATIVE_POLES, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.closure import Derivations, close
from GSE.curation.lexicon_builder.coherence import (
    Candidate,
    Derivation,
    Observation,
    Types,
    apply,
    censor,
    closure_conflicts,
    evidence_on,
    render,
    settle,
    wordnet_types,
)

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "data/lexicon_builder/rebuild/cohort.jsonl"
PROFILES = ROOT / "GSE/curation/lexicon_builder/prime_profiles.json"
_SIGN = {1: POS, -1: NEG, 0: ZERO}
_STATE = {"+1": POS, "-1": NEG, "0": ZERO, "empty": SILENT}


def _canonical(bank: str, value: int):
    """A source's (bank, value) on the registry's banks: a negative pole name becomes its bank's -1."""
    if bank in NEGATIVE_POLES:
        return NEGATIVE_POLES[bank], {1: NEG, -1: POS, 0: ZERO}[value]
    if bank not in BANK_INDEX:
        return None
    return bank, _SIGN[value]


def closed_class(index, skipped):
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

    p = GSEClosedClassParser()
    p.load()
    out = []
    for entries in p.entries.values():
        for e in entries:
            if e.entry_id not in index:
                skipped["closed_class_not_in_cohort"] += 1
                continue
            for bank, value in sorted(p.to_primitives_for_entry(e).items()):
                cv = _canonical(bank, value)
                if cv is None:
                    skipped[f"closed_class_bank_outside_registry:{bank}"] += 1
                    continue
                out.append(Observation(e.entry_id, cv[0], cv[1], "gse_closed_class", e.entry_id))
    return out


def _norm(heading: str) -> str:
    return heading.replace("\n", "").replace("’", "'").strip()


def prime_profiles(index, skipped, bindings):
    from GSE.curation.external_sources import nsm_chart_data as chart

    key_of = {_norm(h): k for k, h, _, _ in chart._CHART_BOXES}
    links = chart.foundation_prime_links()
    align = {k: (bank, 1) for k, bank in chart._EXACT.items()}
    align |= {k: (b, s) for k, (b, s, note) in chart._ADAPTED.items() if not note.startswith("Candidate")}
    stated, derived = [], []
    for prof in json.loads(PROFILES.read_text())["profiles"]:
        axiom = prof["definition_axiom"]
        ident = [
            (d["coordinates"][0], d["state"])
            for d in axiom["decisions"]
            if any(x.endswith(":IDENTIFIES_PRIME") for x in d["derived_by"])
        ]
        bank, sign = ident[0][0], int(ident[0][1])
        boxes = {_norm(e["box"]) for e in axiom["examination"]}
        keys = sorted(key_of[b] for b in boxes if b in key_of and align.get(key_of[b]) == (bank, sign))
        if len(keys) != 1:
            skipped[f"profile_unbound:{prof['prime']}:{len(keys)}_aligned_boxes"] += 1
            continue
        reading = links[f"nsm:v20:{keys[0]}"][0]
        if reading not in index:
            skipped[f"profile_reading_not_in_cohort:{prof['prime']}"] += 1
            continue
        bindings[prof["prime"]] = reading
        root = f"prime_profile:{prof['prime']}"
        for d in axiom["decisions"]:
            states = _STATE[d["state"]]
            for coord in d["coordinates"]:
                if coord not in BANK_INDEX:
                    skipped[f"profile_coordinate_outside_registry:{coord}"] += 1
                    continue
                by = d["derived_by"]
                if not by:
                    stated.append(Observation(reading, coord, states, "prime_profile", root, generalizes=False))
                elif all(x.startswith("PROFILE:") for x in by):
                    stated.append(Observation(reading, coord, states, "prime_profile", root))
                else:
                    derived.append(Derivation(reading, coord, states, "law:" + "+".join(by), (root,)))
    return stated, derived


def approved_anchors(index, bindings, skipped):
    from GSE.curation.external_sources import nsm_chart_data as chart

    bound = set(bindings.values())
    out = []
    for key, (bank, sign, reading, _family, _ordinal) in sorted(chart._APPROVED_CORRESPONDENCES.items()):
        if reading in bound:
            skipped[f"anchor_already_bound_by_profile:{key}"] += 1
            continue
        if reading not in index:
            skipped[f"anchor_reading_not_in_cohort:{key}"] += 1
            continue
        try:
            out.append(Observation(reading, bank, _SIGN[sign], "approved_anchor", f"nsm_chart_data:approved:{key}"))
        except ValueError as e:  # the anchor states a value the bank registry forbids
            skipped[f"anchor_refused:{key}:{e}"] += 1
    return out


# Candidate source (iii), supplied: two proposals put to the gate on the real cohort to show its verdicts there.
# They are candidates, not stated facts.
DEMONSTRATIONS = (
    Candidate((("SOMEONE", POS),), "ALIVE", POS, ("wordnet_isa:person.n.01",), "supplied:demonstration"),
    censor(("wordnet_isa:artifact.n.01",), "THINK", POS, if_terms=(("ALIVE", ZERO),), origin="supplied:demonstration"),
)


def _digests() -> dict:
    files = [COHORT, PROFILES, ROOT / "GSE/curation/lexicon_builder/bank_laws.json"]
    files += [ROOT / f"GSE/curation/lexicon_builder/{m}.py" for m in ("laws", "guards", "coherence", "admission")]
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def _rows(settlement, rows):
    return [settlement.readings[i] for i in rows.tolist()]


def pair_census(settlement) -> dict:
    """Every stated pair pattern over the whole population (no scope): how much of its agreement is independent.

    The same loops as `coherence.pair_candidates`, without scopes, reported rather than judged.
    """
    stated = settlement.stated
    patterns = []
    for a_id, a_col in sorted(stated.columns.items()):
        a_bank = BANKS[a_id]
        for a in sorted(set(np.unique(a_col.masks).tolist())):
            rows_a = stated.within(a_bank, a)
            for b_id, b_col in sorted(stated.columns.items()):
                if b_id == a_id:
                    continue
                _, observed, _, _ = b_col.at(rows_a)
                for b in sorted(set(np.unique(observed).tolist())):
                    c = Candidate(((a_bank, a),), BANKS[b_id], b, ("population",), "census")
                    ev = evidence_on(c, settlement, rows_a)
                    patterns.append(
                        {
                            "pattern": f"{a_bank}{render(a)}=>{BANKS[b_id]}{render(b)}",
                            "witnesses": int(ev.witnesses.size),
                            "co_encoded": int(ev.co_encoded.size),
                            "counterexamples": int(ev.counterexamples.size),
                            "unknown": int(ev.unknown.size),
                        }
                    )
    agreeing = [x for x in patterns if x["witnesses"] or x["co_encoded"]]
    return {
        "patterns": len(patterns),
        "with_any_stated_agreement": len(agreeing),
        "with_an_independent_witness": sum(1 for x in patterns if x["witnesses"]),
        "with_a_counterexample": sum(1 for x in patterns if x["counterexamples"]),
        "largest_agreements": sorted(agreeing, key=lambda x: (-x["co_encoded"] - x["witnesses"], x["pattern"]))[:25],
    }


def run(exclude_conflicts: bool = True) -> dict:
    t0 = time.perf_counter()
    readings = inventory.load(COHORT)
    ids = tuple(r.reading_id for r in readings)
    index = {r: i for i, r in enumerate(ids)}
    skipped: Counter = Counter()
    bindings: dict[str, str] = {}
    observations = closed_class(index, skipped)
    prof_stated, prof_derived = prime_profiles(index, skipped, bindings)
    observations += prof_stated + approved_anchors(index, bindings, skipped)
    settlement = settle(observations, ids)
    state = State.opening(ids)
    h_open = state.bits()
    premise_conflicts = apply(state, settlement, prof_derived)
    h_premises = state.bits()
    rels = laws.compile_laws()
    scopes = guards.scopes(readings, {r.scope for r in rels})
    derivations = Derivations()
    law_receipt = close(state, rels, scopes, derivations)
    after_laws = closure_conflicts(state, settlement, derivations)
    # A conflicted cell is unresolved: it neither confirms nor refutes.
    if exclude_conflicts:
        settlement = settlement.excluding(premise_conflicts + after_laws)
    facts = {f"guard:{k}": v for k, v in scopes.items() if v.any()}
    facts |= wordnet_types(readings)
    types = Types.build(len(ids), facts)
    t_inputs = time.perf_counter() - t0
    rounds = discover(state, rels, scopes, settlement, types, DEMONSTRATIONS)
    by_family = Counter(o.family for o in settlement.informative)
    stated_cells = {
        "cells": int(sum(c.rows.size for c in settlement.stated.columns.values())),
        "readings": int(np.unique(np.concatenate([c.rows for c in settlement.stated.columns.values()])).size),
        "by_bank_state": {f"{b}{s}": int(rows.size) for (b, s), rows in sorted(settlement.stated.postings().items())},
        "confirming_cells": int(sum(c.rows.size for c in settlement.confirming.columns.values())),
    }
    out_rounds = []
    for i, r in enumerate(rounds):
        counts = Counter(v.verdict for v in r.verdicts)
        detail = []
        for v in r.verdicts:
            ev = v.evidence
            item = {
                "rule": v.candidate.rule_id,
                "origin": v.candidate.origin,
                "verdict": v.verdict,
                "witnesses": _rows(settlement, ev.witnesses),
                "witness_roots": list(ev.witness_roots),
                "co_encoded": int(ev.co_encoded.size),
                "counterexamples": _rows(settlement, ev.counterexamples),
                "unknown": int(ev.unknown.size),
                "exposed": ev.exposed,
                "note": v.note,
            }
            if v.guards:
                item["guards"] = list(v.guards)
            if v.reach is not None:
                item["reach"] = {
                    "rows": int(v.reach.rows.size),
                    "cells": v.reach.cells,
                    "decided": v.reach.decided,
                    "bits": round(v.reach.bits, 3),
                    "emptied": [list(x) for x in v.reach.emptied[:20]],
                    "configurations": v.reach.configurations,
                }
            detail.append(item)
        out_rounds.append(
            {
                "round": i + 1,
                "candidates": len(r.verdicts),
                "verdicts": {k: counts.get(k, 0) for k in VERDICTS},
                "admitted": [rel.rule_id for rel in r.admitted],
                "closure": r.receipt,
                "census": r.census,
                "detail": detail,
            }
        )
    return {
        "format": "GSE.rebuild-coherence-discovery/1",
        "inputs": _digests(),
        "law_relations": len(rels),
        "variant": "stated facts, WordNet as types only"
        + ("" if exclude_conflicts else "; COUNTERFACTUAL: stated cells in conflict with a law left in the postings"),
        "readings": len(ids),
        "observations": len(settlement.informative),
        "observations_by_family": dict(sorted(by_family.items())),
        "uninformative_observations": settlement.uninformative,
        "derivations_from_profiles": len(prof_derived),
        "profile_bindings": dict(sorted(bindings.items())),
        "skipped": dict(sorted(skipped.items())),
        "stated": stated_cells,
        "conflicts": {
            "among_stated_sources": [c.__dict__ for c in settlement.conflicts if c not in settlement.excluded],
            "stated_against_derived": [c.__dict__ for c in premise_conflicts],
            "left_empty_by_the_laws": [c.__dict__ for c in after_laws],
        },
        "pair_census": pair_census(settlement),
        "types": {"count": len(types.names), "guard": sorted(k for k in facts if k.startswith("guard:"))},
        "bits": {"opening": h_open, "after_premises": h_premises, "after_laws": law_receipt["bits_after"]},
        "rounds": out_rounds,
        "seconds": {"inputs": round(t_inputs, 2), "total": round(time.perf_counter() - t0, 2)},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    receipt = {"types_only": run(), "types_only_conflicts_kept": run(exclude_conflicts=False)}
    text = json.dumps(receipt, indent=1, default=str)
    if args.out:
        args.out.write_text(text + "\n")
    for name, r in receipt.items():
        print(name, json.dumps({k: r[k] for k in ("observations_by_family", "stated", "seconds")}, default=str)[:600])
        for rd in r["rounds"]:
            print("  round", rd["round"], rd["candidates"], rd["verdicts"], "admitted", len(rd["admitted"]))


if __name__ == "__main__":
    main()
