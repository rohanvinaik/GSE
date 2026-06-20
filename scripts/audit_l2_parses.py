#!/usr/bin/env python3
"""Audit GSE's parse of the L2 corpus — characterize the failure SHAPES (the worklist).

The dogfooding instrument: re-parse the corpus texts (via the same providers the
corpus builder uses) with failure + degradation capture, and bucket the issues by
*shape* so each becomes a structural/logical parser fix:

  * EXCEPTIONS  — a sentence GSE can't evaluate (e.g. the SCALAR_EXTREME arity bug):
    grouped by exception type+message, with an example. These are sentence-scale
    bugs to fix.
  * DEGRADED    — clauses the coherence gate flags (by reason): the partial-parse
    failure modes.
  * OOV         — unknown content words per super-register: the spell-check / slang /
    archaic lexical-repair worklist.

Usage: python scripts/audit_l2_parses.py [--docs-per-genre 8] [--max-sents 30]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_CONTENT = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-per-genre", type=int, default=8)
    ap.add_argument("--max-sents", type=int, default=30)
    args = ap.parse_args()

    import nltk
    for name, path in [("brown", "corpora/brown"), ("gutenberg", "corpora/gutenberg"),
                       ("nps_chat", "corpora/nps_chat"), ("reuters", "corpora/reuters")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(name, quiet=True)

    from gse.api import GSEEncoder
    from gse.discourse import split_sentences, super_register_of
    from gse.symbolic import evaluate_tree, from_trace, resolve
    from gse.symbolic.coherence import coherence_report
    from scripts.build_l2_corpus import _providers

    enc = GSEEncoder()
    exc_shapes: Counter = Counter()
    exc_example: dict = {}
    degraded_reasons: Counter = Counter()
    oov_by_super: dict = defaultdict(Counter)
    n_sents = 0
    n_exc = n_degraded = 0

    for reg_class, genre, source, doc_id, text in _providers(
            args.docs_per_genre, args.max_sents):
        sr = super_register_of(genre)
        for s in split_sentences(text):
            n_sents += 1
            try:
                tr = enc.encode(s)
                resolved = resolve(from_trace(tr))
                tree = evaluate_tree(resolved)
                for d in coherence_report(tree, tr):
                    degraded_reasons[d.get("reason", "?")] += 1
                    n_degraded += 1
                for t in tr.tokens:
                    if t.pos in _CONTENT and not enc._lookup_lexeme(t.lemma)[0]:
                        oov_by_super[sr][t.lemma] += 1
            except Exception as e:
                key = f"{type(e).__name__}: {str(e)[:55]}"
                exc_shapes[key] += 1
                exc_example.setdefault(key, (genre, s[:90]))
                n_exc += 1
    enc.close()

    print(f"\naudited {n_sents} sentences | {n_exc} exceptions, {n_degraded} degraded clauses\n")
    print("=== EXCEPTION SHAPES (sentence-scale bugs to fix) ===")
    for k, n in exc_shapes.most_common():
        g, ex = exc_example[k]
        print(f"  {n:4d}×  {k}\n          e.g. [{g}] {ex!r}")
    print("\n=== DEGRADED-CLAUSE REASONS (partial-parse modes) ===")
    for r, n in degraded_reasons.most_common():
        print(f"  {n:4d}×  {r}")
    print("\n=== TOP OOV CONTENT WORDS per super-register (lexical-repair worklist) ===")
    for sr in sorted(oov_by_super):
        top = ", ".join(f"{w}({n})" for w, n in oov_by_super[sr].most_common(8))
        total = sum(oov_by_super[sr].values())
        print(f"  {sr:18s} ({total} OOV)  {top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
