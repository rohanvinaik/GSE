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
from typing import Dict, List, Sequence, Tuple

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

    def facets(self, label: str) -> Dict[str, Tuple[str, ...]]:
        """The ORTHOGONAL world facets (SCALE / DOMAIN) for a named referent — additive evidence
        beyond the TAXONOMIC thread. A nation grounds SCALE=('Regional','National') +
        DOMAIN=('Knowledge','Geography') even when its TAXONOMIC genealogy is a shallow ['Thing']
        (honest abstention, never filled): that facet is the signal it is a NATIONAL collective.
        Returns ``{dimension: deepest-path}`` (deepest candidate per dimension); ``{}`` if unknown.

        Absent from ``world_facets`` (an older genealogy.db build) → ``{}``, degrading gracefully to
        the TAXONOMIC-only behaviour (no facet evidence, no crash)."""
        try:
            rows = self._conn.execute(
                "SELECT dimension, path FROM world_facets WHERE label=? ORDER BY depth DESC",
                (label.lower(),),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        out: Dict[str, Tuple[str, ...]] = {}
        for dim, path in rows:
            if dim not in out:        # ORDER BY depth DESC → keep the most-typed path per dimension
                out[dim] = tuple(json.loads(path))
        return out

    # -- provider API -------------------------------------------------------
    def candidates(self, lemma: str, pos: str, is_proper: bool) -> List[Tuple[str, ...]]:
        """All candidate threads, best-first.

        Proper noun → **world strand only** (its world identity). We do *not*
        fall back to WordNet, because a proper name lemma collides with
        common-noun homographs (Rex→king, Spot→topographic_point, Duncan→dancer)
        — a silent common-noun thread is a wrong identity, worse than none. A
        proper noun absent from the world strand gets an empty thread and
        ``grounding_flags`` flags it (honest abstention). Common noun → word
        strand."""
        if pos == "PRON":
            return []   # a pronoun's identity is its antecedent, not "I"→iodine
        if is_proper:
            # A narrative proper-noun AGENT is a person / place / organization — never a creative WORK.
            # A world match rooted in `Work` (its DBpedia children: Software, Film, Album, Book, …) is the
            # spurious-homograph class — a product NAMED AFTER the character ("Antigone" → a software
            # product, mislabeling the protagonist "Software"). Abstain rather than assert a wrong
            # identity — the same discipline as the common-noun-homograph abstention above (Rex→king).
            return [c for c in self._world(lemma) if "Work" not in c]
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
