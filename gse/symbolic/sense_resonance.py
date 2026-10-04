"""HDC sense-resonance re-ranker for grounding's word-sense disambiguation.

Loads the offline-built sense-vector store (``data/sense_vectors.db``; see
``scripts/build_sense_vectors.py``) and picks, for an ambiguous common noun, the
WordNet sense whose precomputed gloss-vector best resonates with the sentence
context. The expensive HDC decomposition is precomputed offline (it is ~182ms/word
live, far too slow for the hot path); at runtime this is a cheap cosine.

It overrides the WordNet frequency-primary sense ONLY when a non-primary sense
beats the primary's resonance by ``_RESONANCE_MARGIN`` — a margin gate, because the
gloss decomposition carries a mild person/human bias (validated on the Antigone
``men`` case: person +0.50 vs work_force +0.27, but person never *loses* even under
a labour-themed context). The gate lets resonance fix ``men → work_force`` without
stealing a genuinely collective/group reading.

Non-neural, deterministic. Falls back silently (``available`` False / ``None``
returns) when the store is absent or a word is OOV — grounding then keeps its
existing frequency + Jaccard behaviour, so there is no regression.
"""
from __future__ import annotations

import json
import os
import sqlite3
from functools import lru_cache
from typing import List, Optional

import numpy as np

from ..vectors_v2 import SparseVector, bundle

_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "sense_vectors.db",
)
_DIM = 8192
# A non-primary sense must beat the frequency-primary's resonance by this much to win.
_RESONANCE_MARGIN = 0.05


class SenseResonance:
    """Read-only accessor over the persisted sense-vector store."""

    def __init__(self, db_path: str = _DB):
        self._conn: Optional[sqlite3.Connection] = None
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            try:
                self._conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            except sqlite3.Error:
                self._conn = None
        self._wcache: dict = {}
        self._scache: dict = {}

    @property
    def available(self) -> bool:
        return self._conn is not None

    def _vec(self, table: str, col: str, key: str, cache: dict) -> Optional[SparseVector]:
        if key in cache:
            return cache[key]
        v: Optional[SparseVector] = None
        if self._conn is not None:
            row = self._conn.execute(
                f"SELECT pos, neg FROM {table} WHERE {col}=?", (key,)
            ).fetchone()
            if row:
                v = SparseVector(
                    _DIM,
                    np.array(json.loads(row[0]), dtype=np.uint16),
                    np.array(json.loads(row[1]), dtype=np.uint16),
                )
        cache[key] = v
        return v

    def word_vec(self, word: str) -> Optional[SparseVector]:
        return self._vec("word_vec", "word", word.lower(), self._wcache)

    def sense_vec(self, synset_name: str) -> Optional[SparseVector]:
        return self._vec("sense_vec", "synset", synset_name, self._scache)

    def context_vector(self, lemmas: List[str]) -> Optional[SparseVector]:
        """Bundle the known word-vectors of the context lemmas (OOV silently skipped)."""
        vs = [v for w in lemmas if (v := self.word_vec(w)) is not None]
        if not vs:
            return None
        return bundle(vs) if len(vs) > 1 else vs[0]

    def best_sense_index(
        self, synset_names: List[str], context: Optional[SparseVector]
    ) -> Optional[int]:
        """Index of the sense to PROMOTE over the frequency-primary (index 0), or
        None for "no confident override" (keep the primary).

        A non-primary sense wins only if it (a) resonates and (b) beats the
        primary's resonance by ``_RESONANCE_MARGIN``; ties and sub-margin wins
        leave the frequency-primary in place.
        """
        if context is None or len(synset_names) < 2:
            return None
        scores = [
            (context.cosine(sv) if (sv := self.sense_vec(n)) is not None else None)
            for n in synset_names
        ]
        prim = scores[0]
        if prim is None:
            ranked = [(s, i) for i, s in enumerate(scores) if s is not None]
            return max(ranked)[1] if ranked else None
        over = [
            (s, i)
            for i, s in enumerate(scores)
            if i != 0 and s is not None and s > prim + _RESONANCE_MARGIN
        ]
        return max(over)[1] if over else None


@lru_cache(maxsize=1)
def get_resonance() -> SenseResonance:
    """Process-wide singleton — opens the store once (warm in the resident encoder)."""
    return SenseResonance()
