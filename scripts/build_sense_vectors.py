"""Offline batch-build the HDC sense-vector store for grounding's WSD re-ranker.

The spike (Antigone `men`) proved that GLOSS-driven HDC decomposition discriminates
word senses by context (person +0.50 vs work_force +0.27) and is non-neural — but
live decomposition is ~182ms/word, far too slow for the emit hot path. So we
precompute ONCE, here, and persist:

  word_vec(word)        -> SparseVector   (for building the sentence context at runtime)
  sense_vec(synset.name) -> SparseVector  (the candidate-sense vector to resonate)

A synset's vector is the bundle of its gloss content-words' decompositions (the form
the spike validated). Runtime (gse/symbolic/grounding.py) loads this store and does
cheap cosine re-ranking, margin-gated over the WordNet frequency-primary.

Scope: the Genesis run corpus (stories/*.story.txt) — every content lemma + the
gloss vocabulary of its ambiguous nouns. Re-runnable; widen with --all-wordnet later.
Deterministic: the HDC basis is structured (not random), decompose is repeatable.

Usage:
    .venv/bin/python scripts/build_sense_vectors.py [--corpus GLOB] [--out PATH]
"""

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nltk.corpus import wordnet as wn  # noqa: E402

from gse.pipeline_v2 import GSEPipeline  # noqa: E402
from gse.vectors_v2 import bundle  # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STOP = set(
    "a an the of to and or in on for is are be as that this it its with by at from who whom "
    "which not no any all so very each one two who's also more most such may can will would".split()
)


def content_words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2]


def collect_corpus_lemmas(corpus_glob):
    vocab = set()
    files = glob.glob(corpus_glob)
    for f in files:
        try:
            vocab |= set(content_words(open(f, encoding="utf-8", errors="ignore").read()))
        except OSError:
            pass
    return vocab, len(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/Users/rohanvinaik/Genesis/stories/*.story.txt")
    ap.add_argument("--lexicon", default=os.path.join(_REPO, "data", "lexicon_clean.db"))
    ap.add_argument("--out", default=os.path.join(_REPO, "data", "sense_vectors.db"))
    args = ap.parse_args()

    print(f"[1/5] collecting corpus vocab from {args.corpus}")
    corpus, nfiles = collect_corpus_lemmas(args.corpus)
    print(f"      {nfiles} files -> {len(corpus)} content lemmas")

    # ambiguous nouns + the union of words we must decompose (corpus lemmas + their gloss words)
    print("[2/5] resolving ambiguous nouns + gloss vocabulary")
    ambig_lemmas, union = [], set(corpus)
    for w in corpus:
        syns = wn.synsets(w, pos="n")
        if len(syns) >= 2:
            ambig_lemmas.append(w)
        for s in syns:
            union |= set(content_words(s.definition()))
    print(f"      {len(ambig_lemmas)} ambiguous nouns | {len(union)} unique words to decompose")

    print(f"[3/5] loading decomposer ({args.lexicon})")
    p = GSEPipeline(lexicon_path=args.lexicon)
    if p.decomposer is None:
        sys.exit("decomposer not active — lexicon failed to load")

    def nnz(v):
        return int(v.positive_indices.size + v.negative_indices.size) if v is not None else 0

    print(f"[4/5] decomposing {len(union)} words (one-time; ~182ms each)")
    word_vec = {}
    t0 = time.time()
    for i, w in enumerate(sorted(union)):
        try:
            v = p.decompose_word(w, "n").vector
            if v is not None and nnz(v) > 0:
                word_vec[w] = v
        except Exception:
            pass
        if (i + 1) % 500 == 0:
            el = time.time() - t0
            print(f"      {i + 1}/{len(union)}  {el:.0f}s  eta {el / (i + 1) * (len(union) - i - 1):.0f}s", flush=True)
    print(f"      {len(word_vec)} non-empty word vectors in {time.time() - t0:.0f}s")

    # compose per-synset vectors for the ambiguous nouns (bundle of gloss-word vectors)
    print("[5/5] composing synset vectors + persisting")
    sense_vec = {}
    for w in ambig_lemmas:
        for s in wn.synsets(w, pos="n"):
            vs = [word_vec[g] for g in content_words(s.definition()) if g in word_vec]
            if not vs:
                continue
            sense_vec[s.name()] = bundle(vs) if len(vs) > 1 else vs[0]

    if os.path.exists(args.out):
        os.remove(args.out)
    conn = sqlite3.connect(args.out)
    conn.executescript(
        "CREATE TABLE word_vec (word TEXT PRIMARY KEY, pos TEXT, neg TEXT);"
        "CREATE TABLE sense_vec (synset TEXT PRIMARY KEY, pos TEXT, neg TEXT);"
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);"
    )

    def dump(v):
        return (json.dumps(v.positive_indices.tolist()), json.dumps(v.negative_indices.tolist()))

    conn.executemany(
        "INSERT INTO word_vec VALUES (?,?,?)",
        [(w, *dump(v)) for w, v in word_vec.items()],
    )
    conn.executemany(
        "INSERT INTO sense_vec VALUES (?,?,?)",
        [(s, *dump(v)) for s, v in sense_vec.items()],
    )
    conn.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [
            ("n_word_vec", str(len(word_vec))),
            ("n_sense_vec", str(len(sense_vec))),
            ("corpus", args.corpus),
            ("dim", "8192"),
        ],
    )
    conn.commit()
    conn.close()
    print(f"      wrote {len(word_vec)} word + {len(sense_vec)} sense vectors -> {args.out}")

    # ---- self-test: from the STORED vectors, does men->person beat men->work_force? ----
    print("\n[self-test] men sense discrimination from the persisted store")
    import numpy as np

    from gse.vectors_v2 import SparseVector

    def load(tbl, key, conn):
        r = conn.execute(
            f"SELECT pos,neg FROM {tbl} WHERE {'word' if tbl == 'word_vec' else 'synset'}=?", (key,)
        ).fetchone()
        if not r:
            return None
        return SparseVector(
            8192, np.array(json.loads(r[0]), dtype=np.uint16), np.array(json.loads(r[1]), dtype=np.uint16)
        )

    conn = sqlite3.connect(f"file:{args.out}?mode=ro", uri=True)
    ctx_words = content_words("discussion deteriorates two men bitterly insulting father persuade son quarrel argument")
    cvs = [v for w in ctx_words if (v := load("word_vec", w, conn)) is not None]
    ctx = bundle(cvs) if len(cvs) > 1 else (cvs[0] if cvs else None)
    if ctx is None:
        print("      context empty — cannot self-test")
        return
    rows = []
    for s in wn.synsets("men", pos="n"):
        sv = load("sense_vec", s.name(), conn)
        if sv is not None:
            rows.append((ctx.cosine(sv), s.name(), s.lexname()))
    for sc, name, lex in sorted(rows, reverse=True):
        print(f"      cos={sc:+.4f}  {name:16s} [{lex}]")
    mp = next((sc for sc, n, _ in rows if n == "man.n.01"), None)
    wf = next((sc for sc, n, _ in rows if n == "work_force.n.01"), None)
    if mp is not None and wf is not None:
        verdict = "PASS" if mp > wf else "FAIL"
        print(f"      -> person {mp:+.4f} vs work_force {wf:+.4f}  [{verdict}]")
    conn.close()


if __name__ == "__main__":
    main()
