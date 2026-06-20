#!/usr/bin/env python3
"""WS1 Phase 0 — characterize the spaCy surface the test suite actually exercises.

Instruments ``GSEEncoder.encode`` to capture every input text the encoder-touching
tests feed it, then snapshots spaCy's ``(token, lemma, pos, morph)`` per sentence —
the GOLDEN TARGET the GSE-native front-end must reproduce, and the true regression
denominator for the yank. Pure measurement: no core change.

Usage:  python scripts/ws1_characterize.py
Output: data/ws1_golden_corpus.json  (gitignored scratch — regenerable)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORPUS: set[str] = set()

# Encoder test files (constructed GSEEncoder()) — the corpus sources.
ENC_TESTS = [
    "tests/test_gse_demiword.py", "tests/test_lemma_invariants.py",
    "tests/test_symbolic_serialization.py", "tests/test_symbolic_expression.py",
    "tests/test_l1_ladder.py", "tests/test_symbolic_resolution.py",
    "tests/test_symbolic_templating.py", "tests/test_basis_theory_invariants.py",
    "tests/test_symbolic_copula.py", "tests/test_gse_event.py",
    "tests/test_symbolic_proof_suite.py", "tests/test_gse_emit_contract.py",
    "tests/test_comp_operator_trace.py", "tests/test_gse_api_encoder.py",
    "tests/test_gse_document.py", "tests/test_symbolic_operators.py",
    "tests/test_gse_genealogy_store.py", "tests/test_gse_inference.py",
    "tests/test_symbolic_queries.py", "tests/test_gse_entity_refs.py",
    "tests/test_gse_abstention.py",
]


def main() -> int:
    import gse.api.encoder as enc_mod

    orig_encode = enc_mod.GSEEncoder.encode

    def capturing_encode(self, text):
        CORPUS.add(text)
        return orig_encode(self, text)

    enc_mod.GSEEncoder.encode = capturing_encode

    import pytest
    # Run the encoder-touching tests for real so every encode() input is captured.
    pytest.main(["-q", "-p", "no:cacheprovider", "--no-header"] + ENC_TESTS)

    enc_mod.GSEEncoder.encode = orig_encode

    print(f"\n[capture] {len(CORPUS)} unique sentences fed to encode()")

    # Snapshot spaCy golden per sentence.
    import spacy
    nlp = spacy.load("en_core_web_sm")
    golden = {}
    for text in sorted(CORPUS):
        doc = nlp(text)
        golden[text] = [
            {"i": t.i, "text": t.text, "lemma": t.lemma_.lower(),
             "pos": t.pos_, "tag": t.tag_, "dep": t.dep_,
             "head": t.head.i, "morph": str(t.morph)}
            for t in doc
        ]

    out = ROOT / "data" / "ws1_golden_corpus.json"
    out.write_text(json.dumps(golden, indent=2))
    print(f"[golden] wrote {out} ({len(golden)} sentences)")

    # Quick register stats.
    upos = {}
    for toks in golden.values():
        for t in toks:
            upos[t["pos"]] = upos.get(t["pos"], 0) + 1
    print("[register] UPOS distribution:",
          dict(sorted(upos.items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
