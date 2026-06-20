#!/usr/bin/env python3
"""Build the L2 register corpus — Brown genre docs → GSE feature profiles → labeled JSONL.

The training set for the Society-of-Mind register router (and, per-genre, the
dogfooding failure-list: coherence/OOV stats tell us which registers need which
voice-mode scripts). Each output line:

    {"genre", "source", "fileid", "n_sentences", "vector": [...], "banks": {...}}

Genre labels come from the Brown Corpus (NLTK) — genre-balanced, curated,
public-domain. Crash-safe: appends one line per document and resumes by skipping
fileids already present in the output, so a kill loses at most one document.

Usage:
    python scripts/build_l2_corpus.py [--docs-per-genre N] [--max-sents M]
                                      [--out data/l2_corpus.jsonl] [--genres a,b,...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_FIX_SPACING = re.compile(r"\s+([.,;:!?'])")


def _doc_text(sents) -> str:
    """Join Brown's word-tokenized sentences into raw text, undoing the corpus's
    space-before-punctuation tokenization."""
    return " ".join(_FIX_SPACING.sub(r"\1", " ".join(words)) for words in sents)


def _already_done(out: Path) -> set:
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                done.add(json.loads(line)["fileid"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-per-genre", type=int, default=5)
    ap.add_argument("--max-sents", type=int, default=40)
    ap.add_argument("--out", default=str(ROOT / "data" / "l2_corpus.jsonl"))
    ap.add_argument("--genres", default="", help="comma list; default = all Brown genres")
    args = ap.parse_args()

    import nltk
    try:
        nltk.data.find("corpora/brown")
    except LookupError:
        nltk.download("brown", quiet=True)
    from nltk.corpus import brown

    from gse.api import GSEEncoder
    from gse.discourse import text_profile

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _already_done(out)
    genres = [g.strip() for g in args.genres.split(",") if g.strip()] or brown.categories()

    enc = GSEEncoder()
    n_written = 0
    with out.open("a") as fh:
        for cat in genres:
            fids = brown.fileids(categories=cat)[: args.docs_per_genre]
            for fid in fids:
                if fid in done:
                    continue
                text = _doc_text(brown.sents(fid)[: args.max_sents])
                p = text_profile(enc, text)
                rec = {
                    "genre": cat, "source": "brown", "fileid": fid,
                    "n_sentences": p.n_sentences,
                    "vector": p.vector(), "banks": p.to_dict(),
                }
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n_written += 1
                print(f"  [{cat:16s}] {fid}  ({p.n_sentences} sents)")
    enc.close()
    print(f"\n[done] wrote {n_written} new records → {out} "
          f"({len(done) + n_written} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
