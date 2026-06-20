#!/usr/bin/env python3
"""Build the L2 register corpus — multi-source text → GSE feature profiles → labeled JSONL.

The training set for the Society-of-Mind register router (and, per register, the
dogfooding failure-list). Each output line:

    {"register_class", "genre", "source", "doc_id", "n_sentences",
     "vector": [...], "banks": {...}}

A top-line ``register_class`` splits SPEECH-derived prose (the Brown corpus —
genre-balanced, curated, public-domain) from NON-SPEECH structured text (words
meant to communicate but not represent literal speech: poetry/verse, reference/
dictionary entries, lists). That axis is the one Brown alone cannot cover.

Crash-safe: appends one line per document, resumes by skipping ``doc_id``s already
present, so a kill loses at most one document.

Usage:
    python scripts/build_l2_corpus.py [--docs-per-genre N] [--max-sents M]
                                      [--out data/l2_corpus.jsonl]
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


def _join(sent_words) -> str:
    return " ".join(_FIX_SPACING.sub(r"\1", " ".join(w)) for w in sent_words)


# --- NON-SPEECH: hand-curated list/catalog samples (no dataset exists) ----------
_LISTS = [
    "Milk. Eggs. Bread. Two pounds of apples. Coffee. Paper towels. Chicken. Spinach.",
    "Passport. Phone charger. Three shirts. Toothbrush. Sunscreen. Hiking boots. Rain jacket.",
    "Two cups flour. One teaspoon salt. Three eggs. A cup of sugar. Half a stick of butter.",
    "Call the dentist. Pay the electric bill. Pick up the dry cleaning. Email the landlord.",
    "Model X200. Sixteen gigabytes of memory. A five hundred gigabyte drive. Two USB ports.",
    "Nine o'clock standup. Ten o'clock design review. Noon lunch. Two o'clock client call.",
]
_VERSE_FILES = ["blake-poems.txt", "whitman-leaves.txt", "milton-paradise.txt"]


def _providers(docs_per_genre: int, max_sents: int):
    """Yield ``(register_class, genre, source, doc_id, text)`` across all sources."""
    from nltk.corpus import brown, gutenberg

    # SPEECH-derived prose — Brown's genre-balanced documents.
    for cat in brown.categories():
        for fid in brown.fileids(categories=cat)[:docs_per_genre]:
            yield ("speech", cat, "brown", f"brown/{fid}",
                   _join(brown.sents(fid)[:max_sents]))

    # NON-SPEECH · poetry/verse — gutenberg verse, chunked.
    for vf in _VERSE_FILES:
        sents = gutenberg.sents(vf)
        for ci in range(2):  # two chunks per verse file
            chunk = sents[ci * max_sents:(ci + 1) * max_sents]
            if chunk:
                yield ("non_speech", "poetry", "gutenberg",
                       f"poetry/{vf}-{ci}", _join(chunk))

    # NON-SPEECH · reference/wiki — clusters of Wiktionary glosses (plain-text defs).
    kaikki = ROOT / "data" / "external" / "wiktionary" / "kaikki-english.jsonl"
    if kaikki.exists():
        glosses, doc_i = [], 0
        with kaikki.open() as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for s in e.get("senses", []):
                    g = (s.get("glosses") or [None])[0]
                    if g:
                        glosses.append(g)
                if len(glosses) >= 8:
                    yield ("non_speech", "reference", "wiktionary",
                           f"ref/{doc_i}", " ".join(glosses[:8]))
                    glosses, doc_i = [], doc_i + 1
                    if doc_i >= 8:
                        break

    # NON-SPEECH · lists — hand-curated (no clean dataset; classical-AI scale).
    for i, txt in enumerate(_LISTS):
        yield ("non_speech", "list", "curated", f"list/{i}", txt)


def _already_done(out: Path) -> set:
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                done.add(json.loads(line)["doc_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-per-genre", type=int, default=8)
    ap.add_argument("--max-sents", type=int, default=40)
    ap.add_argument("--out", default=str(ROOT / "data" / "l2_corpus.jsonl"))
    args = ap.parse_args()

    import nltk
    for name, path in [("brown", "corpora/brown"), ("gutenberg", "corpora/gutenberg")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(name, quiet=True)

    from gse.api import GSEEncoder
    from gse.discourse import text_profile

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _already_done(out)
    enc = GSEEncoder()
    n_written = 0
    with out.open("a") as fh:
        for reg_class, genre, source, doc_id, text in _providers(
                args.docs_per_genre, args.max_sents):
            if doc_id in done or not text.strip():
                continue
            p = text_profile(enc, text)
            fh.write(json.dumps({
                "register_class": reg_class, "genre": genre, "source": source,
                "doc_id": doc_id, "n_sentences": p.n_sentences,
                "vector": p.vector(), "banks": p.to_dict(),
            }) + "\n")
            fh.flush()
            n_written += 1
            print(f"  [{reg_class:10s}/{genre:14s}] {doc_id}  ({p.n_sentences} sents)")
    enc.close()
    print(f"\n[done] wrote {n_written} new records → {out} ({len(done) + n_written} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
