#!/usr/bin/env python3
"""
Build the GSE-local genealogy store — two orthogonal type-genealogy strands.

  word strand  (WordNet)     : a lemma's hypernym lineage   (definitional / word-grounding)
  world strand (sparse-wiki) : a referent's DBpedia lineage (world-grounding)

Option B: nltk and the relational-ai sparse_wiki.db are read **once, here, at
ingest time**. The runtime GenealogyStore (gse/symbolic/genealogy_store.py) reads
only data/genealogy.db — no nltk at runtime, no coupling to relational-ai.

Senses are stored in WordNet frequency order (sense 0 = most common), so a
context-free lookup defaults to the primary sense; the coherence-scored selector
(M2.2b) consumes the full candidate list instead.

Run:  python scripts/build_genealogy_db.py
Out:  data/genealogy.db
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

GSE_ROOT = Path(__file__).resolve().parent.parent
OUT = GSE_ROOT / "data" / "genealogy.db"
SPARSE_WIKI = Path("/Users/rohanvinaik/Projects/relational-ai/data/sparse_wiki.db")


def build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS word_thread;
        DROP TABLE IF EXISTS world_thread;
        CREATE TABLE word_thread (lemma TEXT, pos TEXT, sense INTEGER, thread TEXT);
        CREATE INDEX idx_word ON word_thread(lemma, pos);
        -- world_thread rows carry the entity's PAGERANK PERCENTILE (the real
        -- link-graph score, scripts/compute_pagerank.py in relational-ai) as the
        -- candidate-ranking prior, and a src marker: 'label' = the entity's own
        -- label; 'alias' = a redirect-derived alternate name ("bosnia" →
        -- Bosnia and Herzegovina's thread) — partial-label resolution for free.
        -- canon = the entity's own label (for an alias row, the redirect TARGET's
        -- label), so anchor/facet/EPA lookups reach the canonical entry from any
        -- alias mention.
        CREATE TABLE world_thread (label TEXT, thread TEXT, depth INTEGER,
                                   pagerank REAL DEFAULT 0, src TEXT DEFAULT 'label',
                                   canon TEXT);
        CREATE INDEX idx_world ON world_thread(label);
        DROP TABLE IF EXISTS world_facets;
        -- The ORTHOGONAL facets (SCALE / DOMAIN / TEMPORAL / SPATIAL) beyond the
        -- TAXONOMIC genealogy. A name whose TAXONOMIC is a shallow ["Thing"] (honest
        -- abstention — never to be "filled") can still carry SCALE=["Regional","National"]
        -- + DOMAIN=["Knowledge","Geography"], the signal that it is a NATIONAL/geographic
        -- collective; TEMPORAL/SPATIAL joined once the infobox backfill made them real
        -- (2026-07-01). Additive evidence consumed by GenealogyStore.facets().
        CREATE TABLE world_facets (label TEXT, dimension TEXT, path TEXT, depth INTEGER);
        CREATE INDEX idx_facets ON world_facets(label);
        DROP TABLE IF EXISTS world_epa;
        -- World-salience EPA (Osgood Evaluation/Potency/Activity, ternary) — the
        -- INTENSITY leg of the word-affect ⟂ world-salience split (GSE_vision §IV½):
        -- the word `die` is affect-neutral by definition; the GRAVITY of death is a
        -- fact about the referent, supplied here. Derived upstream by
        -- relational-ai/scripts/backfill_epa.py (primitives_to_epa over entity
        -- descriptions; confidence marks derivation: 1.0 description / 0.3 type-default).
        CREATE TABLE world_epa (label TEXT, e INTEGER, p INTEGER, a INTEGER,
                                confidence REAL);
        CREATE INDEX idx_epa ON world_epa(label);
        DROP TABLE IF EXISTS world_anchors;
        -- Semantic-anchor property bags (the entity's most significant Wikipedia-link
        -- targets, weighted by target pagerank). The CONTEXT-COHERENCE substrate for
        -- the world leg: a mention's world reading is corroborated when its anchors
        -- overlap the document's other referents ("Paris" the city anchors
        -- {france, seine, europe}) — and abstainable when they don't (a fictional
        -- "Paris" in a Verona story). Anchors are keyed by the entity's OWN label
        -- (aliases resolve identity via world_thread, then anchor via the canon label).
        CREATE TABLE world_anchors (label TEXT, anchor TEXT, weight REAL);
        CREATE INDEX idx_anchors ON world_anchors(label);
        """
    )


def ingest_wordnet(conn: sqlite3.Connection) -> int:
    from nltk.corpus import wordnet as wn

    lemmas = set()
    for syn in wn.all_synsets(pos="n"):
        lemmas.update(syn.lemma_names())

    rows, n = [], 0
    for name in lemmas:
        lem = name.replace("_", " ").lower()
        for i, syn in enumerate(wn.synsets(name, pos=wn.NOUN)):
            paths = syn.hypernym_paths()
            if not paths:
                continue
            thread = [s.name().split(".")[0] for s in paths[0]]  # root-first
            rows.append((lem, "NOUN", i, json.dumps(thread)))
            n += 1
        if len(rows) >= 5000:
            conn.executemany("INSERT INTO word_thread(lemma,pos,sense,thread) VALUES(?,?,?,?)", rows)
            rows = []
    if rows:
        conn.executemany("INSERT INTO word_thread(lemma,pos,sense,thread) VALUES(?,?,?,?)", rows)
    return n


def ingest_sparse_wiki(conn: sqlite3.Connection) -> int:
    if not SPARSE_WIKI.exists():
        print(f"  WARNING: {SPARSE_WIKI} missing — world strand skipped.")
        return 0
    src = sqlite3.connect(f"file:{SPARSE_WIKI}?mode=ro", uri=True)
    # Include depth-0 (untyped) entities too: a known Wikipedia entity that lacks
    # a DBpedia type still grounds to ["Thing"] — "known world entity, type
    # unspecified" — which distinguishes it from a genuinely unknown name (flagged).
    cur = src.execute(
        """SELECT e.label, e.pagerank, dp.dimension, dp.path_nodes, dp.path_depth
           FROM dimension_positions dp JOIN entities e ON dp.entity_id=e.id
           WHERE dp.dimension IN ('TAXONOMIC','SCALE','DOMAIN','TEMPORAL','SPATIAL')"""
    )
    threads, facets, n = [], [], 0

    def flush():
        nonlocal threads, facets
        if threads:
            conn.executemany(
                "INSERT INTO world_thread(label,thread,depth,pagerank,src,canon) VALUES(?,?,?,?,?,?)", threads
            )
            threads = []
        if facets:
            conn.executemany("INSERT INTO world_facets(label,dimension,path,depth) VALUES(?,?,?,?)", facets)
            facets = []

    typed_labels = []  # (label, path_nodes, depth, pagerank) of REAL-typed entities → token aliases
    for label, pagerank, dimension, path_nodes, depth in cur:
        if not label:
            continue
        if dimension == "TAXONOMIC":
            threads.append((label.lower(), path_nodes, depth, pagerank or 0, "label", label.lower()))
            if depth and depth > 1 and " " in label:  # typed, multi-token → token-alias candidate
                typed_labels.append((label.lower(), path_nodes, depth, pagerank or 0))
            n += 1
        else:  # SCALE / DOMAIN / TEMPORAL / SPATIAL — the orthogonal facets
            facets.append((label.lower(), dimension, path_nodes, depth))
        if len(threads) >= 5000 or len(facets) >= 5000:
            flush()
    flush()

    # World-salience EPA (the intensity leg) — one row per canon label.
    epa_rows = src.execute(
        """SELECT e.label, v.evaluation, v.potency, v.activity, v.confidence
           FROM epa_values v JOIN entities e ON e.id=v.entity_id
           WHERE v.evaluation!=0 OR v.potency!=0 OR v.activity!=0"""
    ).fetchall()
    conn.executemany(
        "INSERT INTO world_epa(label,e,p,a,confidence) VALUES(?,?,?,?,?)",
        [(lb.lower(), ev, pv, av, cf) for lb, ev, pv, av, cf in epa_rows if lb],
    )
    print(f"  +{len(epa_rows):,} world_epa rows")

    # Semantic anchors (the context-coherence substrate), keyed by canon label.
    anchor_rows = 0
    batch = []
    for lb, anchor, weight in src.execute(
        """SELECT e.label, ad.label, ea.weight
               FROM entity_anchors ea
               JOIN anchor_dictionary ad ON ad.anchor_id=ea.anchor_id
               JOIN entities e ON e.id=ea.entity_id"""
    ):
        if not lb or not anchor:
            continue
        batch.append((lb.lower(), anchor.lower(), weight or 0))
        anchor_rows += 1
        if len(batch) >= 20000:
            conn.executemany("INSERT INTO world_anchors(label,anchor,weight) VALUES(?,?,?)", batch)
            batch = []
    if batch:
        conn.executemany("INSERT INTO world_anchors(label,anchor,weight) VALUES(?,?,?)", batch)
    print(f"  +{anchor_rows:,} world_anchors rows")

    # Redirect-derived aliases (relational-ai scripts/build_aliases.py): each
    # alias carries its target's TAXONOMIC thread(s), so a partial/alternate
    # mention ("bosnia", "napoleon bonaparte") grounds to the canonical entity
    # with no store-side change. TAXONOMIC only — identity is the load-bearing
    # signal; facet lookups go through the canonical label.
    try:
        cur = src.execute(
            """SELECT a.alias, e.label, e.pagerank, dp.path_nodes, dp.path_depth
               FROM aliases a JOIN entities e ON e.id=a.entity_id
               JOIN dimension_positions dp ON dp.entity_id=e.id
               WHERE dp.dimension='TAXONOMIC'"""
        )
        seen_labels = {r[0] for r in conn.execute("SELECT DISTINCT label FROM world_thread")}
        n_alias = 0
        for alias, canon, pagerank, path_nodes, depth in cur:
            if not alias or alias in seen_labels:
                continue  # an alias never shadows a real label
            threads.append((alias, path_nodes, depth, pagerank or 0, "alias", (canon or "").lower()))
            n_alias += 1
            if len(threads) >= 5000:
                flush()
        flush()
        print(f"  +{n_alias:,} alias world_thread rows")
    except sqlite3.OperationalError:
        print("  (no aliases table in sparse_wiki.db — aliases skipped)")

    # TOKEN aliases (2026-07-01): the redirect table misses forename/sub-token mentions —
    # "alexander" (→ Alexander the Great), "herzegovina" (→ Bosnia and Herzegovina),
    # "antony" (→ Mark Antony) all returned empty, the mention→entity residual of the
    # taxonomic backfill. For every REAL-typed multi-token entity, each content token
    # becomes an alias row, guarded by the ORTHOGRAPHIC discipline (the same law as
    # grounding._orthographic_collision): a token that exists in WordNet as a LOWERCASE
    # lemma is a common English word ("mark", "war", "great") and is never aliased — a
    # capitalized-only WordNet entry (Alexander, Antony, Herzegovina) or an OOV token is
    # a name-like mention and may stand for its entity. Rows are capped per token to the
    # top-K by pagerank (candidates() reads best-first; a token shared by thousands of
    # titles is a meaningless prior beyond its head). An alias never shadows a real label.
    _TOKEN_CAP = 8
    try:
        from nltk.corpus import wordnet as wn

        def _common_word(tok: str) -> bool:
            for pos in ("n", "v", "a", "r", "s"):
                for syn in wn.synsets(tok, pos):
                    for lem in syn.lemmas():
                        if lem.name().lower() == tok and not lem.name()[0].isupper():
                            return True
            return False

        seen_labels = {r[0] for r in conn.execute("SELECT DISTINCT label FROM world_thread")}
        by_token: dict = {}
        for label, path_nodes, depth, pagerank in typed_labels:
            for tok in label.split():
                if len(tok) < 4 or not tok.isalpha() or tok in seen_labels:
                    continue
                by_token.setdefault(tok, []).append((pagerank, label, path_nodes, depth))
        n_token = 0
        for tok, cands in by_token.items():
            if _common_word(tok):
                continue
            cands.sort(key=lambda c: -c[0])
            for pagerank, canon, path_nodes, depth in cands[:_TOKEN_CAP]:
                threads.append((tok, path_nodes, depth, pagerank, "token", canon))
                n_token += 1
                if len(threads) >= 5000:
                    flush()
        flush()
        print(f"  +{n_token:,} token-alias world_thread rows ({len(by_token):,} tokens considered)")
    except Exception as e:
        print(f"  (token aliases skipped: {e!r})")

    src.close()
    return n


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(OUT))
    build_schema(conn)
    print("Ingesting WordNet word-threads ...")
    w = ingest_wordnet(conn)
    print(f"  {w:,} word_thread rows")
    print("Ingesting sparse-wiki world-threads ...")
    s = ingest_sparse_wiki(conn)
    print(f"  {s:,} world_thread rows")
    conn.commit()
    conn.close()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
