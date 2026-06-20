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

    checks = {"verbs_to_promote": (verbs_to_promote, _verbs_to_promote_arcs)}

    overall_ok = True
    for name, (new_fn, ref_fn) in checks.items():
        diverged = []
        for text in corpus:
            doc = nlp(text)
            new, ref = new_fn(doc), ref_fn(doc)
            if new != ref:
                diverged.append((text, sorted(ref), sorted(new)))
        status = "OK" if not diverged else f"{len(diverged)} DIVERGENCES"
        print(f"[{name}] {len(corpus)} sentences — {status}")
        for text, ref, new in diverged:
            print(f"    {text!r}\n        arc-ref={ref}  arc-free={new}")
        overall_ok = overall_ok and not diverged

    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
