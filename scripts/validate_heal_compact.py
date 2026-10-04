#!/usr/bin/env python3
"""Validate the heal → compact flow on REAL stories: does the trained K-line library actually apply
fixes to the raw GSE output, and do those fixes land in the contracts the compactor consumes?

(Persisted to the repo, not /tmp — the prior copies were lost to a reboot.)

For each eval story: raw GSE → resolve → HEAL (the lens society + trained K-line recall on abstain) →
graph.emit() = the compact INPUT → compress() = the compact OUTPUT. Reports: how many fixes each
specialist applied, how many came from the trained K-line (vs the fold), and shows the K-line-healed
events that reach the compactor.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

GSE_ROOT = Path("/Users/rohanvinaik/Projects/gse")
sys.path.insert(0, str(GSE_ROOT))
from gse.api import GSEEncoder
from gse.discourse.speech import encode_document_utterances_traced
from gse.symbolic import GenealogyStore, resolve_document
from gse.symbolic.healer import build_envelope, make_repair_hook
from gse.symbolic.healer.recollect import default_memory, default_memory_path
from gse.symbolic.narrative import NarrativeGraph, compress

EVAL = GSE_ROOT / "data" / "eval_corpus"


def ev_str(c):
    p = c.get("predicate", c); a = p.get("args", []); f = p.get("features", {})
    if p.get("op") != "EVENT":
        return None
    ag = a[0].get("lemma") if a and isinstance(a[0], dict) else "?"
    return f"{ag} —{f.get('verb','?')}→"


def _docs(brown):
    if brown:
        sys.path.insert(0, str(GSE_ROOT / "data" / "healer_training"))
        from harvest_taxonomy import complete_docs
        for genre, _src, doc_id, sents in complete_docs(brown):
            yield f"{genre}/{doc_id}", sents
    else:
        for story in sorted(EVAL.glob("*.txt")):
            yield name, [l.strip() for l in open(story) if l.strip()]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--brown", type=int, default=0, help="docs/genre from Brown (0 = the 5 eval stories)")
    args = ap.parse_args()
    mem = default_memory(name="baseline")
    print(f"  trained library: {default_memory_path('baseline')} -> {'LOADED %d cases' % len(mem) if mem else 'ABSENT'}\n")
    enc = GSEEncoder()
    fires, kline = Counter(), Counter()
    per_story = []
    kline_events = []
    for name, sents in _docs(args.brown):
        traced = encode_document_utterances_traced(enc, sents)
        if not traced:
            continue
        trees = [t for _a, t, _b in traced]
        envelopes = [build_envelope(tr, None) for tr, _t, _u in traced]
        store = GenealogyStore()
        resolved = resolve_document(trees, store)
        hook = make_repair_hook(envelopes, genealogy=store)
        graph = NarrativeGraph.from_document(resolved, store, repair=hook)
        raw = graph.emit()
        out, _rep = compress(graph, None)
        rep = hook.society.report
        nk = 0
        for _t, lens, note in rep.repairs:
            fires[lens] += 1
            if "k-line recall" in (note or ""):
                kline[lens] += 1; nk += 1
                if len(kline_events) < 30:
                    kline_events.append((name, note))
        per_story.append((name, rep.seen, len(rep.repairs), nk, len(raw), len(out)))
    enc.close()
    print("  per story:  seen / heal-fixes / of-which-K-LINE / compact-IN / compact-OUT")
    for name, seen, reps, nk, nin, nout in per_story:
        print(f"    {name:26s} {seen:3d} / {reps:3d} / {nk:2d} / {nin:3d} / {nout:3d}")
    print(f"\n  TOTAL heal-fixes by specialist: {dict(fires)}")
    print(f"  of which from the TRAINED K-LINE: {dict(kline)}")
    print("\n  K-LINE-healed events that reached the compactor (the trained fixes feeding compact):")
    for name, note in kline_events:
        print(f"    [{name}] {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
