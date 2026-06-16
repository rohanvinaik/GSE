"""
DB-backed two-strand GenealogyProvider — M2.2a of RESOLVED_STRUCTURE_DESIGN.md.

Reads only ``data/genealogy.db`` (built by ``scripts/build_genealogy_db.py``):

  word strand  — WordNet hypernym lineage (definitional / word-grounding)
  world strand — sparse-wiki DBpedia lineage (referent / world-grounding)

The two strands are orthogonal: a word's *definitional* type (``dog`` → animal)
and a referent's *world* type (``Paris`` → City) answer different questions, and
a proper noun can draw both.

:meth:`thread` returns the primary, context-free choice (so the store satisfies
:class:`gse.symbolic.grounding.GenealogyProvider` today). :meth:`candidates`
exposes the full ranked list — every WordNet sense + both strands — which the
coherence-scored selector (M2.2b) consumes to pick the sense/source that coheres
with the rest of the sentence.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Sequence, Tuple

_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "genealogy.db"


class GenealogyStore:
    """Two-strand genealogy provider backed by the local ``genealogy.db``."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        # Read-only; one connection per store (single-threaded use).
        self._conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    # -- strands ------------------------------------------------------------
    def _world(self, label: str) -> List[Tuple[str, ...]]:
        rows = self._conn.execute(
            "SELECT thread FROM world_thread WHERE label=? ORDER BY depth DESC",
            (label.lower(),),
        ).fetchall()
        return [tuple(json.loads(r[0])) for r in rows]

    def _word(self, lemma: str) -> List[Tuple[str, ...]]:
        rows = self._conn.execute(
            "SELECT thread FROM word_thread WHERE lemma=? AND pos='NOUN' ORDER BY sense",
            (lemma.lower(),),
        ).fetchall()
        return [tuple(json.loads(r[0])) for r in rows]

    # -- provider API -------------------------------------------------------
    def candidates(self, lemma: str, pos: str, is_proper: bool) -> List[Tuple[str, ...]]:
        """All candidate threads, best-first. Proper noun → world strand first
        (its own world identity), then WordNet as fallback/cross-check; common
        noun → word strand only."""
        if is_proper:
            return self._world(lemma) + self._word(lemma)
        return self._word(lemma)

    def thread(self, lemma: str, pos: str, is_proper: bool) -> Sequence[str]:
        """Primary (context-free) thread — first candidate, or ``()``."""
        cands = self.candidates(lemma, pos, is_proper)
        return cands[0] if cands else ()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "GenealogyStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
