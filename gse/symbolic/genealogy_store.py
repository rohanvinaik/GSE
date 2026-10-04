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
        """Candidates best-first: by PAGERANK percentile (the world-importance
        prior — 'paris' → the city before the plant genus), then depth. Falls
        back to depth-only ordering on a pre-pagerank genealogy.db build."""
        try:
            rows = self._conn.execute(
                "SELECT thread FROM world_thread WHERE label=? ORDER BY pagerank DESC, depth DESC",
                (label.lower(),),
            ).fetchall()
        except sqlite3.OperationalError:
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
        the TAXONOMIC-only behaviour (no facet evidence, no crash).

        Facet rows are keyed by the CANONICAL entity label, so an alias mention must resolve
        through :meth:`_canon` first (the same hop :meth:`epa`/:meth:`anchors` take) — otherwise
        every partial-label mention (``bosnia`` → "bosnia and herzegovina") silently loses its
        facet evidence, starving the demonym/Geography strands downstream."""
        try:
            rows = self._conn.execute(
                "SELECT dimension, path FROM world_facets WHERE label=? ORDER BY depth DESC",
                (self._canon(label),),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        out: Dict[str, Tuple[str, ...]] = {}
        for dim, path in rows:
            if dim not in out:  # ORDER BY depth DESC → keep the most-typed path per dimension
                out[dim] = tuple(json.loads(path))
        return out

    def _canon(self, label: str) -> str:
        """The canonical entity label behind a mention — for an alias row, the
        redirect target's label; else the label itself. Anchor/EPA/facet data is
        keyed by canon, so an alias mention reaches its entity's records."""
        try:
            row = self._conn.execute(
                "SELECT canon FROM world_thread WHERE label=? AND canon IS NOT NULL ORDER BY pagerank DESC LIMIT 1",
                (label.lower(),),
            ).fetchone()
        except sqlite3.OperationalError:
            return label.lower()
        return row[0] if row and row[0] else label.lower()

    def epa(self, label: str) -> Dict[str, float]:
        """World-salience EPA for a named referent — the INTENSITY leg of the
        word-affect ⟂ world-salience split (the word carries valence; the
        referent's gravity lives here). ``{}`` when unknown or on an older
        genealogy.db build (graceful degradation, like :meth:`facets`)."""
        try:
            row = self._conn.execute(
                "SELECT e, p, a, confidence FROM world_epa WHERE label=? ORDER BY confidence DESC LIMIT 1",
                (self._canon(label),),
            ).fetchone()
        except sqlite3.OperationalError:
            return {}
        if row is None:
            return {}
        return {"evaluation": row[0], "potency": row[1], "activity": row[2], "confidence": row[3]}

    def anchors(self, label: str) -> Dict[str, float]:
        """The referent's semantic-anchor property bag (its most significant
        Wikipedia-link targets, weight = target pagerank) — the context-coherence
        substrate for the world leg. ``{anchor_label: weight}``; ``{}`` when
        unknown or on an older build."""
        try:
            rows = self._conn.execute(
                "SELECT anchor, weight FROM world_anchors WHERE label=?",
                (self._canon(label),),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        return {a: w for a, w in rows}

    def world_candidates(self, label: str) -> List[Dict]:
        """Full world-candidate records, best-first — thread + the ranking prior
        + provenance. The richer sibling of :meth:`candidates` for consumers that
        score candidates (anchor coherence) rather than just take the primary.
        ``[]`` on an older build without the pagerank/canon columns."""
        try:
            rows = self._conn.execute(
                "SELECT thread, depth, pagerank, src, canon FROM world_thread"
                " WHERE label=? ORDER BY pagerank DESC, depth DESC",
                (label.lower(),),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            {"thread": tuple(json.loads(t)), "depth": d, "pagerank": pr, "src": s, "canon": c}
            for t, d, pr, s, c in rows
        ]

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
            return []  # a pronoun's identity is its antecedent, not "I"→iodine
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
