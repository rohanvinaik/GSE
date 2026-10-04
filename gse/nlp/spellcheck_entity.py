"""Proper-noun spell-correction — the ENTITY leg beside the word leg
(:mod:`gse.nlp.spellcheck`), same noisy-channel law on a different substrate.

The word leg cannot commit on a proper noun: its candidates come from the English
word space, and the shape gate rightly blocks a lone word-guess at a name. This leg
gives names their own instance of the exact same structural discipline:

  error model P(x|w)  — the SAME closed keyboard-weighted Damerau generators
                        (:func:`gse.nlp.spellcheck._edits1` / ``_edits2``);
  grounding gate      — the candidate must be a real NAME: it must exist in
                        ``data/spell_entities.db``, the ALIAS-FREE entity dictionary
                        (canonical labels + their name-part tokens, derived by
                        :mod:`gse.curation.build_spell_entities`; no redirect /
                        collated-misspelling data anywhere in this path);
  prior P(w)          — the entity's PageRank percentile, converted to an effective
                        rank and fed through the same ``edit_cost + λ·log10(rank)``
                        score law as the word leg's frequency prior;
  context tiebreak    — the referent's semantic-anchor bag ∩ the document's content
                        words, under grounding._anchor_overrides' parameter-free
                        promotion law: corroboration can CONFIRM a candidate inside
                        the commit margin, never override the grounding gate;
  abstention          — commit only on a decisive margin (the shared
                        ``WORD_COMMIT_MARGIN``) or a unique corroborated candidate;
                        otherwise surface the ranked options.

Trigger discipline (enforced by the caller, :mod:`gse.mcp.spell_server`): the leg
fires only on PROPN/title-case tokens that do not ground anywhere; a token that
grounds as an entity name — including rare-but-real names (``Shakespear`` →
Richmond Shakespear) — is NEVER touched. Absent ``spell_entities.db`` the leg
degrades to a no-op (same contract as the marisa/HDC caches).
"""

from __future__ import annotations

import math
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from gse.nlp.spellcheck import (
    _LAMBDA,
    WORD_COMMIT_MARGIN,
    Candidate,
    _edits1,
    _edits2,
)
from gse.nlp.spellcheck import (
    propose as _propose_words,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_DB = os.path.join(_REPO_ROOT, "data", "spell_entities.db")
_GENEALOGY_DB = os.path.join(_REPO_ROOT, "data", "genealogy.db")

_CHUNK = 500  # SQLite parameter-limit-safe IN() batching
_TOPK_ANCHOR = 5  # only the best few candidates are worth anchor lookups


class _Entities:
    """Lazy read-only view of the alias-free entity-name dictionary."""

    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._n_entities: Optional[int] = None
        self._missing = False

    @property
    def conn(self) -> Optional[sqlite3.Connection]:
        if self._conn is None and not self._missing:
            try:
                self._conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
                self._conn.execute("SELECT 1 FROM entity_names LIMIT 1")
            except sqlite3.Error:
                self._conn = None
                self._missing = True
        return self._conn

    @property
    def available(self) -> bool:
        return self.conn is not None

    @property
    def n_entities(self) -> int:
        if self._n_entities is None:
            conn = self.conn
            row = conn.execute("SELECT value FROM meta WHERE key='n_entities'").fetchone() if conn else None
            self._n_entities = int(row[0]) if row else 250_000
        return self._n_entities

    def lookup(self, name: str) -> List[Tuple[str, float]]:
        """``[(canon, pagerank), ...]`` best-first for one name; ``[]`` if unknown."""
        conn = self.conn
        if conn is None:
            return []
        return conn.execute(
            "SELECT canon, pagerank FROM entity_names WHERE name=? ORDER BY pagerank DESC",
            (name.lower(),),
        ).fetchall()

    def grounds(self, name: str) -> bool:
        conn = self.conn
        if conn is None:
            return False
        return conn.execute("SELECT 1 FROM entity_names WHERE name=? LIMIT 1", (name.lower(),)).fetchone() is not None

    def members(self, names: Sequence[str]) -> Dict[str, Tuple[str, float]]:
        """Filter ``names`` by dictionary membership: ``{name: (best_canon,
        best_pagerank)}``. Batched IN() queries — the grounding gate over an edit
        candidate set."""
        conn = self.conn
        if conn is None or not names:
            return {}
        out: Dict[str, Tuple[str, float]] = {}
        seq = list(names)
        for i in range(0, len(seq), _CHUNK):
            chunk = seq[i : i + _CHUNK]
            q = "SELECT name, canon, MAX(pagerank) FROM entity_names WHERE name IN (%s) GROUP BY name" % ",".join(
                "?" * len(chunk)
            )
            for name, canon, pagerank in conn.execute(q, chunk):
                out[name] = (canon, pagerank or 0.0)
        return out

    def rank_cost(self, pagerank: float) -> float:
        """PageRank percentile -> effective rank -> the word leg's log10 cost law."""
        rank = max(1, int(round((1.0 - pagerank) * self.n_entities)) + 1)
        return math.log10(rank)


_DEFAULT_ENTITIES = _Entities()


def _default_anchors(canon: str) -> Dict[str, float]:
    """Referent's semantic-anchor bag from genealogy.db (lazy, optional)."""
    global _ANCHOR_CONN
    if _ANCHOR_CONN is False:
        return {}
    if _ANCHOR_CONN is None:
        try:
            _ANCHOR_CONN = sqlite3.connect(f"file:{_GENEALOGY_DB}?mode=ro", uri=True)
            _ANCHOR_CONN.execute("SELECT 1 FROM world_anchors LIMIT 1")
        except sqlite3.Error:
            _ANCHOR_CONN = False
            return {}
    rows = _ANCHOR_CONN.execute("SELECT anchor, weight FROM world_anchors WHERE label=?", (canon,)).fetchall()
    return {a: w for a, w in rows}


_ANCHOR_CONN = None  # None = untried, False = unavailable, else the connection


@dataclass(frozen=True)
class EntityCandidate:
    name: str
    edit_cost: int
    pagerank: float
    canon: str
    corroboration: float = 0.0  # anchor-bag ∩ context weight (0 when no context)

    def score(self, entities: _Entities) -> float:
        return self.edit_cost + _LAMBDA * entities.rank_cost(self.pagerank)


@dataclass(frozen=True)
class EntityCorrection:
    surface: str
    fired: bool  # False = the surface IS a known entity name
    committed: Optional[str]
    canon: Optional[str] = None
    ranked: Tuple[EntityCandidate, ...] = field(default_factory=tuple)
    note: str = ""


def propose_entities(surface: str, entities: _Entities = _DEFAULT_ENTITIES) -> List[EntityCandidate]:
    """Grounded entity-name candidates for ``surface``, best-first — the same
    generate -> ground -> score shape as the word leg's :func:`propose`."""
    word = surface.lower()
    e1 = _edits1(word)
    hits = entities.members(list(e1))
    cost = {n: e1[n] for n in hits}
    if not cost:
        e2 = _edits2(word)
        hits = entities.members(list(e2))
        cost = {n: e2[n] for n in hits}
    out = [EntityCandidate(n, c, hits[n][1], hits[n][0]) for n, c in cost.items()]
    out.sort(key=lambda c: (c.score(entities), c.name))
    return out


def correct_entity(
    surface: str,
    context_words: Sequence[str] = (),
    entities: _Entities = _DEFAULT_ENTITIES,
    anchors_fn: Callable[[str], Dict[str, float]] = _default_anchors,
    word_pool: Optional[Sequence[Candidate]] = None,
) -> EntityCorrection:
    """Correct one PROPN/title-case token against the entity-name space.

    * surface grounds as a name -> ``fired=False``, never touched;
    * decisive noisy-channel margin -> commit;
    * indecisive margin -> anchor corroboration may CONFIRM a unique candidate
      (parameter-free: it must be the only within-margin candidate the document's
      context corroborates); otherwise abstain with the ranked set.

    ``word_pool`` is the surface's WORD-space candidate set (computed via
    :func:`gse.nlp.spellcheck.propose` when None; pass ``()`` to disable). The two
    substrates share one score law, so they COMPETE in one channel: an entity commit
    must either AGREE with the best word reading (the same string — the word
    grounding corroborates the name) or decisively beat it. This is the gate that
    stops a sole obscure entity name from out-committing a plausible ordinary-word
    reading ("Aadvark": the word space's `aardvark` wins; the leg abstains).
    """
    word = surface.lower()
    if not entities.available:
        return EntityCorrection(surface, fired=False, committed=None, note="entity dictionary absent: leg inert")
    if entities.grounds(word):
        return EntityCorrection(surface, fired=False, committed=word, note="surface is a known entity name")

    cands = propose_entities(surface, entities)
    if not cands:
        return EntityCorrection(surface, fired=True, committed=None, note="no grounded entity candidate")
    if word_pool is None:
        word_pool = _propose_words(surface)
    word_best = word_pool[0] if word_pool else None

    def _beats_word_reading(c: EntityCandidate) -> bool:
        if word_best is None or word_best.word == c.name:
            return True  # no competitor, or the readings agree
        return word_best.score - c.score(entities) >= WORD_COMMIT_MARGIN

    # anchor corroboration (context signal) for the cheapest few candidates
    ctx = {w.lower() for w in context_words if w}
    if ctx:
        scored = []
        for c in cands[:_TOPK_ANCHOR]:
            bag = anchors_fn(c.canon) or {}
            corr = sum(wt for a, wt in bag.items() if a in ctx)
            scored.append(EntityCandidate(c.name, c.edit_cost, c.pagerank, c.canon, corr))
        cands = scored + cands[_TOPK_ANCHOR:]

    best = cands[0]
    second = cands[1] if len(cands) > 1 else None
    margin_ok = second is None or (second.score(entities) - best.score(entities)) >= WORD_COMMIT_MARGIN
    if margin_ok:
        if not _beats_word_reading(best):
            return EntityCorrection(surface, True, None, None, tuple(cands), "word-space reading competes: abstained")
        return EntityCorrection(surface, True, best.name, best.canon, tuple(cands), "committed: decisive margin")
    # within-margin set: corroboration may confirm a UNIQUE candidate
    within = [c for c in cands if c.score(entities) - best.score(entities) < WORD_COMMIT_MARGIN]
    corroborated = [c for c in within if c.corroboration > 0]
    if len(corroborated) == 1 and _beats_word_reading(corroborated[0]):
        c = corroborated[0]
        return EntityCorrection(
            surface, True, c.name, c.canon, tuple(cands), "committed: unique anchor-corroborated candidate"
        )
    return EntityCorrection(surface, True, None, None, tuple(cands), "no decisive winner: abstained")
