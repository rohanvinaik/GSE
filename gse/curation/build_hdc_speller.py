"""Build + cache the keyboard-HDC speller lexicon (gse.nlp.hdc_speller).

Encodes the top-N common words into sparse-ternary keyboard-HDC hypervectors and caches
the (L2-normalized dense ternary) matrix + words + frequency ranks to data/hdc_speller.npz,
so the speller loads instantly at runtime instead of re-encoding ~12k words per process.

Run once (and after any change to the encoder operating point):
    python -m gse.curation.build_hdc_speller
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np

from gse.nlp.hdc_speller import _CACHE_PATH, _REPO_ROOT, _encode_dense_unit

_FREQ_DB = os.path.join(_REPO_ROOT, "data", "frequency.db")
_LIMIT = 12000           # common-word lexicon size (>=4 letters, by combined_rank)
_MIN_LEN = 4


def build(limit: int = _LIMIT, out_path: str = _CACHE_PATH) -> int:
    conn = sqlite3.connect(_FREQ_DB)
    rows = [
        (w.lower(), rank)
        for (w, rank) in conn.execute(
            "SELECT word, combined_rank FROM frequency "
            "WHERE LENGTH(word) >= ? ORDER BY combined_rank LIMIT ?",
            (_MIN_LEN, limit),
        )
        if w.isalpha()
    ]
    conn.close()
    words = [w for w, _ in rows]
    rank = np.array([r for _, r in rows], dtype=np.float64)

    print(f"encoding {len(words)} words (sparse-ternary keyboard-HDC)...", flush=True)
    matrix = np.empty((len(words), _vec_len(words[0])), dtype=np.float32)
    for i, w in enumerate(words):
        matrix[i] = _encode_dense_unit(w)
        if (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{len(words)}", flush=True)

    np.savez_compressed(out_path, words=np.array(words), matrix=matrix, rank=rank)
    print(f"wrote {out_path}  ({matrix.shape[0]}x{matrix.shape[1]}, "
          f"{os.path.getsize(out_path) / 1e6:.1f} MB)")
    return len(words)


def _vec_len(sample_word: str) -> int:
    return _encode_dense_unit(sample_word).shape[0]


if __name__ == "__main__":
    n = build()
    sys.exit(0 if n else 1)
