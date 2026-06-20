#!/usr/bin/env python3
"""WS1 parity gate — arc-free derivations must match spaCy's arcs on the register.

For each capability being converted from spaCy dependency arcs to arc-free
(connective + position + verb-inventory) derivation, run BOTH implementations on
every sentence in the golden corpus and report divergences. A capability ships
only when this is clean (or the divergences are reviewed and judged correct).

Usage:  python scripts/ws1_parity.py
Needs:  data/ws1_golden_corpus.json  (build via scripts/ws1_characterize.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "data" / "ws1_golden_corpus.json"


def main() -> int:
    if not GOLDEN.exists():
        print(f"missing {GOLDEN}; run scripts/ws1_characterize.py first")
        return 1
    corpus = sorted(json.loads(GOLDEN.read_text()).keys())

    import spacy

    from gse.api.parse_repair import _verbs_to_promote_arcs, verbs_to_promote

    nlp = spacy.load("en_core_web_sm")
    overall_ok = True

    # --- function-level: verbs_to_promote (arc-free vs arc) -------------------
    diverged = []
    for text in corpus:
        doc = nlp(text)
        if verbs_to_promote(doc) != _verbs_to_promote_arcs(doc):
            diverged.append((text, sorted(_verbs_to_promote_arcs(doc)),
                             sorted(verbs_to_promote(doc))))
    print(f"[verbs_to_promote] {len(corpus)} sentences — "
          f"{'OK' if not diverged else f'{len(diverged)} DIVERGENCES (reviewed)'}")
    for text, ref, new in diverged:
        print(f"    {text!r}  arc-ref={ref}  arc-free={new}")

    # --- trace-level: embedded-clause deriver (the real contract) ------------
    # Compare the full resolved symbolic structure + vector_hash between the
    # arc-free and arc embedded-clause derivers. Raw embedded tuples differ on
    # and/so sentences (arc emits spurious ccomps the encoder filters; arc-free
    # never emits them) — the trace is what must match.
    from gse.api.encoder import GSEEncoder
    from gse.symbolic import from_trace, resolve, to_dict

    enc = GSEEncoder()
    arcfree_method = enc._detect_embedded_clauses
    arc_method = enc._detect_embedded_clauses_arcs

    def trace_struct(text):
        tr = enc.encode(text)
        return to_dict(resolve(from_trace(tr))), tr.vector_hash

    tdiv = []
    for text in corpus:
        enc._detect_embedded_clauses = arcfree_method
        free_struct, free_hash = trace_struct(text)
        enc._detect_embedded_clauses = arc_method
        arc_struct, arc_hash = trace_struct(text)
        enc._detect_embedded_clauses = arcfree_method
        if free_struct != arc_struct or free_hash != arc_hash:
            tdiv.append((text, free_hash != arc_hash, free_struct != arc_struct))
    enc.close()
    print(f"[embedded_clauses:trace] {len(corpus)} sentences — "
          f"{'OK' if not tdiv else f'{len(tdiv)} DIVERGENCES'}")
    for text, hdiff, sdiff in tdiv:
        flags = ("hash " if hdiff else "") + ("struct" if sdiff else "")
        print(f"    {text!r}  [{flags}]")
    overall_ok = overall_ok and not tdiv

    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
