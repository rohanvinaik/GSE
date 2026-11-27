"""Population discovery over the pinned cohort with every stated observation on main (rebuild task 8).

Stated facts, each from its native record (root):
- the source lenses (`projection.project`: VerbNet, and USAS with FrameNet where the lemma and part of speech have a
  single reading); root = the lens's premise record (a VerbNet class and sense key, a USAS tag with its FrameNet
  units). Lens obligations are not observations about a known reading and do not enter the postings; lens reading
  facts select the guards;
- the NSM explications, templates and molecules (`nsm.compile_records`), restrictions only; root = the record, and a
  record that republishes another's observation (`same_as`) shares that record's root. Obligations do not enter;
- closed-class catalog rows (`GSEClosedClassParser.to_primitives_for_entry`; root = the catalog row);
- the examined prime profiles (`prime_profiles.json`; root = the profile), bound to a cohort reading only through
  the chart box the profile examined and the chart data's own alignment of that unit to the same signed pole
  (`foundation_prime_links`). Units the chart data calls candidate alignments (die, live, mine) are not bound.
  The profile's identity and asserted components are stated. Its authored silence boundary is stated but confined
  to its reading ("never to ordinary words"). Its law-derived decisions are derivations.
- the approved anchors `_APPROVED_CORRESPONDENCES` for readings no profile binds (this, dont-want, very).

The authored laws' consequences on the stated premises are known: they narrow cells, expose and contradict, and never
confirm (TrialLedger: "Known is a source fact or a strict conclusion from known premises"; SW 14). WordNet enters only
as types:
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

from GSE.curation.lexicon_builder import guards, inventory, laws, nsm, projection
from GSE.curation.lexicon_builder import obligations as ob
from GSE.curation.lexicon_builder.admission import VERDICTS, discover
from GSE.curation.lexicon_builder.cells import BANK_INDEX, BANKS, NEG, NEGATIVE_POLES, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.closure import Derivations, close
from GSE.curation.lexicon_builder.coherence import (
    Candidate,
    Derivation,
    Observation,
    Settlement,
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


def lens_observations(lens, ids, skipped):
    r = lens.restrictions
    out = []
    for row, col, allowed, rule, premise in zip(
        r.rows.tolist(), r.cols.tolist(), r.allowed.tolist(), r.rules.tolist(), r.premises.tolist()
    ):
        try:
            out.append(Observation(ids[row], BANKS[col], allowed, r.rule_sources[rule], r.premise_ids[premise]))
        except ValueError as e:
            skipped[f"lens_refused:{r.rule_ids[rule]}:{e}"] += 1
    return out


def nsm_roots(compiled):
    """rule id -> the record it rests on: a template's members share their template's record, and a republished
    observation (`same_as`) keeps the root of the record that first published it."""
    record_of, same_as = {}, {}
    for e in compiled.receipt:
        record = f"nsm:{e['source']}:{e['start_line']}-{e['end_line']}"
        for b in [e, *[m for m in e.get("members", []) if isinstance(m, dict)]]:
            if "rule_id" in b:
                record_of[b["rule_id"]] = record
                if "same_as" in b:
                    same_as[b["rule_id"]] = b["same_as"]
    return lambda rule_id: record_of[same_as.get(rule_id, rule_id)]


def nsm_observations(compiled, ids, skipped):
    """Restrictions only; each rooted at its record (`nsm_roots`)."""
    root = nsm_roots(compiled)
    out = []
    for row, col, allowed, rule in zip(
        compiled.rows.tolist(), compiled.cols.tolist(), compiled.allowed.tolist(), compiled.rules.tolist()
    ):
        rule_id = compiled.rule_ids[rule]
        try:
            out.append(Observation(ids[row], BANKS[col], allowed, "nsm", root(rule_id)))
        except ValueError as e:
            skipped[f"nsm_refused:{rule_id}:{e}"] += 1
    return out


def obligation_batch(lens, compiled):
    """Lens and NSM obligations as one batch, witnesses renumbered so no two sources share one, with each
    obligation's (family, root): the dataset that stated it and the record it rests on."""
    source_of = dict(zip(lens.restrictions.rule_ids, lens.restrictions.rule_sources))
    root = nsm_roots(compiled)
    items, sources, base = [], [], 0

    def take(objs, origin):
        nonlocal base
        top = base
        for o in objs:
            w = getattr(o, "witness", None)
            witness = None if w is None else base + int(w)
            top = max(top, (witness or 0) + 1)
            premises = tuple(getattr(o, "premises", ()))
            items.append(ob.Obligation(o.rule_id, o.bank, o.allowed, np.asarray(o.rows), witness, premises))
            sources.append(origin(o))
        base = top

    take(lens.obligations, lambda o: (source_of[o.rule_id], ";".join(o.premises) or o.rule_id))
    take([o for o in compiled.obligations if not o.joint], lambda o: ("nsm", root(o.rule_id)))
    return ob.Batch.of(items), sources


def close_known(state, relations, scopes, batch, derivations=None) -> dict:
    """The known layer: the laws close, the obligations force and wake the facts they locate, until nothing changes
    (no identity classes: each reading is its own candidate)."""
    sweeps = forced = 0
    while True:
        close(state, relations, scopes, derivations)
        f = ob.force(state, batch)
        woken = ob.wake(scopes, f.facts)
        sweeps += 1
        forced += f.changed
        if not (f.changed or woken):
            return {"sweeps": sweeps, "forced_cells": forced, "obligation_conflicts": int(f.conflicts.size)}


def _digests() -> dict:
    files = [COHORT, PROFILES, ROOT / "GSE/curation/lexicon_builder/bank_laws.json"]
    files += [
        ROOT / f"GSE/curation/lexicon_builder/{m}.py"
        for m in (
            "laws",
            "guards",
            "projection",
            "nsm",
            "nsm_frames",
            "nsm_text",
            "nsm_typing",
            "coherence",
            "admission",
        )
    ]
    out = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    return out | {f"nsm_records/{k}": v for k, v in nsm.records_digest(ROOT / nsm.RECORDS).items()}


def _examples(settlement, rows, k=10):
    return {"count": int(rows.size), "examples": [settlement.readings[i] for i in rows[:k].tolist()]}


def _by_kind(settlement, v, rows) -> dict:
    """What puts the consequent's bank outside its states on `rows`: a statement that may generalize, a statement
    its source confines to its own reading (the authored prime boundary; it can refute but never expose), or only a
    known consequence of the laws."""
    b, bs = v.candidate.then_bank, v.candidate.then_states
    general = np.intersect1d(rows, settlement.confirming.outside(b, bs))
    stated = np.intersect1d(rows, settlement.stated.outside(b, bs))
    return {
        "by_generalizing_statement": _examples(settlement, general),
        "by_confined_statement": _examples(settlement, np.setdiff1d(stated, general)),
        "by_known_consequence_only": _examples(settlement, np.setdiff1d(rows, stated)),
    }


def _verdict_record(settlement, v) -> dict:
    ev = v.evidence
    item = {
        "rule": v.candidate.rule_id,
        "origin": v.candidate.origin,
        "verdict": v.verdict,
        "witnesses": _examples(settlement, ev.witnesses),
        "witness_families": list(ev.witness_families),
        "witness_roots": {"count": len(ev.witness_roots), "examples": list(ev.witness_roots[:10])},
        "counterexamples": _examples(settlement, ev.counterexamples),
        "exposure": _examples(settlement, ev.exposure),
        "exposure_by_kind": _by_kind(settlement, v, ev.exposure),
        "counterexamples_by_kind": _by_kind(settlement, v, ev.counterexamples),
        "unknown": int(ev.unknown.size),
        "co_encoded": int(ev.co_encoded.size),
        "known_agreement": int(ev.known_agreement.size),
        "note": v.note,
    }
    if v.guards:
        item["guards"] = list(v.guards)
        item["children"] = [c.rule_id for c in v.children]
    if v.collided:
        item["collided"] = [list(x) for x in v.collided[:10]]
    if v.reach is not None:
        item["reach"] = {
            "readings": _examples(settlement, v.reach.rows),
            "cells": v.reach.cells,
            "decided": v.reach.decided,
            "bits": round(v.reach.bits, 3),
            "emptied": [list(x) for x in v.reach.emptied[:10]],
            "configurations": v.reach.configurations,
        }
    return item


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
                _, observed, _ = b_col.at(rows_a)
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


def run() -> dict:
    t0 = time.perf_counter()
    readings = inventory.load(COHORT)
    ids = tuple(r.reading_id for r in readings)
    index = {r: i for i, r in enumerate(ids)}
    skipped: Counter = Counter()
    bindings: dict[str, str] = {}
    sources, load_seconds = projection.load_sources()
    lens = projection.project(readings, sources)
    compiled = nsm.compile_records(nsm.load_records(ROOT / nsm.RECORDS), readings)
    observations = lens_observations(lens, ids, skipped) + nsm_observations(compiled, ids, skipped)
    observations += closed_class(index, skipped)
    prof_stated, prof_derived = prime_profiles(index, skipped, bindings)
    observations += prof_stated + approved_anchors(index, bindings, skipped)
    t_sources = time.perf_counter() - t0
    premises = settle(observations, ids)
    state = State.opening(ids)
    h_open = state.bits()
    premise_conflicts = apply(state, premises, prof_derived)
    h_premises = state.bits()
    rels = laws.compile_laws()
    base_scopes = guards.scopes(readings, {r.scope for r in rels}, lens.facts)
    scopes = {k: v.copy() for k, v in base_scopes.items()}
    batch, obligation_sources = obligation_batch(lens, compiled)
    derivations = Derivations()
    known_receipt = close_known(state, rels, scopes, batch, derivations)
    # An obligation located in the known layer is a stated observation of its source (the lead's ruling, 2026-11-27).
    at_fixed_point = ob.force(state.copy(), batch)
    located = Settlement.located_groups(
        batch, at_fixed_point.located_rows, at_fixed_point.located_by, ids, lambda i: obligation_sources[i], "known"
    )
    settlement = settle(observations + located, ids)
    after_laws = closure_conflicts(state, settlement, derivations)
    # Near-misses read the same known layer without the reading-confined statements.
    general = State.opening(ids)
    apply(general, premises.generalizing(), prof_derived)
    close_known(general, rels, {k: v.copy() for k, v in base_scopes.items()}, batch)
    # A conflicted cell is unresolved: it neither confirms nor refutes.
    settlement = settlement.excluding(premise_conflicts + after_laws).knowing(state, general)
    law_receipt = {"bits_after": state.bits()} | known_receipt
    facts = {f"guard:{k}": v for k, v in scopes.items() if v.any()}
    facts |= wordnet_types(readings)
    types = Types.build(len(ids), facts)
    t_inputs = time.perf_counter() - t0
    rounds = discover(state, rels, scopes, settlement, types, DEMONSTRATIONS)
    t_discover = time.perf_counter() - t0 - t_inputs
    by_family = Counter(o.family for o in settlement.informative)
    cells_by_family = {
        fam: len({(o.reading, o.bank) for o in settlement.informative if o.family == fam}) for fam in by_family
    }
    readings_by_family = {fam: len({o.reading for o in settlement.informative if o.family == fam}) for fam in by_family}
    roots_by_family = {fam: len({o.root for o in settlement.informative if o.family == fam}) for fam in by_family}
    states_by_family = Counter(f"{o.family}:{o.bank}{render(o.states)}" for o in settlement.informative)
    known_cells = int(sum(c.rows.size for c in settlement.known.columns.values()))
    out_rounds = []
    for i, r in enumerate(rounds):
        counts = Counter(v.verdict for v in r.verdicts)
        full = [_verdict_record(settlement, v) for v in r.verdicts if v.verdict in ("ADMITTED", "NARROWED", "FINDING")]
        compact = [
            {
                "rule": v.candidate.rule_id,
                "verdict": v.verdict,
                "witnesses": int(v.evidence.witnesses.size),
                "counterexamples": int(v.evidence.counterexamples.size),
                "exposure": int(v.evidence.exposure.size),
                "unknown": int(v.evidence.unknown.size),
                "note": v.note,
            }
            for v in r.verdicts
            if v.verdict not in ("ADMITTED", "NARROWED", "FINDING")
        ]
        out_rounds.append(
            {
                "round": i + 1,
                "candidates": len(r.verdicts),
                "verdicts": {k: counts.get(k, 0) for k in VERDICTS},
                "admitted": [rel.rule_id for rel in r.admitted],
                "closure": r.receipt,
                "census": r.census,
                "admitted_narrowed_findings": full,
                "others": compact,
            }
        )
    return {
        "format": "GSE.rebuild-coherence-discovery/2",
        "inputs": _digests(),
        "law_relations": len(rels),
        "readings": len(ids),
        "stated_observations": {
            "total": len(settlement.informative),
            "by_source": dict(sorted(by_family.items())),
            "cells_by_source": dict(sorted(cells_by_family.items())),
            "readings_by_source": dict(sorted(readings_by_family.items())),
            "roots_by_source": dict(sorted(roots_by_family.items())),
            "by_source_bank_state": dict(sorted(states_by_family.items())),
            "uninformative": settlement.uninformative,
        },
        "lens_restrictions_by_source": dict(
            sorted(Counter(lens.restrictions.rule_sources[i] for i in lens.restrictions.rules.tolist()).items())
        ),
        "located_in_the_known_layer": dict(sorted(Counter(o.family for o in located).items())),
        "known_layer": known_receipt,
        "not_observations": {
            "lens_obligations": len(lens.obligations),
            "nsm_obligations": len(compiled.obligations),
            "profile_derivations_applied_as_known": len(prof_derived),
        },
        "stated_cells": int(sum(c.rows.size for c in settlement.stated.columns.values())),
        "confirming_cells": int(sum(c.rows.size for c in settlement.confirming.columns.values())),
        "known_cells": known_cells,
        "known_general_cells": int(sum(c.rows.size for c in settlement.known_general.columns.values())),
        "profile_bindings": dict(sorted(bindings.items())),
        "skipped": dict(sorted(skipped.items())),
        "conflicts": {
            "among_stated_sources": [c.__dict__ for c in settlement.conflicts if c not in settlement.excluded],
            "stated_against_derived": [c.__dict__ for c in premise_conflicts],
            "left_empty_by_the_laws": [c.__dict__ for c in after_laws],
        },
        "pair_census": pair_census(settlement),
        "types": {"count": len(types.names), "guard": sorted(k for k in facts if k.startswith("guard:"))},
        "bits": {"opening": h_open, "after_premises": h_premises, "after_known_layer": law_receipt["bits_after"]},
        "rounds": out_rounds,
        "seconds": {
            "load": load_seconds,
            "sources": round(t_sources, 2),
            "inputs": round(t_inputs, 2),
            "discover": round(t_discover, 2),
            "total": round(time.perf_counter() - t0, 2),
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    receipt = run()
    text = json.dumps(receipt, indent=1, default=str)
    if args.out:
        args.out.write_text(text + "\n")
    print(json.dumps({k: receipt[k] for k in ("stated_observations", "seconds")}, default=str)[:1500])
    for rd in receipt["rounds"]:
        print("  round", rd["round"], rd["candidates"], rd["verdicts"], "admitted", len(rd["admitted"]))


if __name__ == "__main__":
    main()
