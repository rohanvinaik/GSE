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
        CREATE TABLE world_thread (label TEXT, thread TEXT, depth INTEGER);
        CREATE INDEX idx_world ON world_thread(label);
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
            conn.executemany(
                "INSERT INTO word_thread(lemma,pos,sense,thread) VALUES(?,?,?,?)", rows)
            rows = []
    if rows:
        conn.executemany(
            "INSERT INTO word_thread(lemma,pos,sense,thread) VALUES(?,?,?,?)", rows)
    return n


def ingest_sparse_wiki(conn: sqlite3.Connection) -> int:
    if not SPARSE_WIKI.exists():
        print(f"  WARNING: {SPARSE_WIKI} missing — world strand skipped.")
        return 0
    src = sqlite3.connect(f"file:{SPARSE_WIKI}?mode=ro", uri=True)
    cur = src.execute(
        """SELECT e.label, dp.path_nodes, dp.path_depth
           FROM dimension_positions dp JOIN entities e ON dp.entity_id=e.id
           WHERE dp.dimension='TAXONOMIC' AND dp.path_depth>0"""
    )
    rows, n = [], 0
    for label, path_nodes, depth in cur:
        if not label:
            continue
        rows.append((label.lower(), path_nodes, depth))
        n += 1
        if len(rows) >= 5000:
            conn.executemany(
                "INSERT INTO world_thread(label,thread,depth) VALUES(?,?,?)", rows)
            rows = []
    if rows:
        conn.executemany(
            "INSERT INTO world_thread(label,thread,depth) VALUES(?,?,?)", rows)
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
