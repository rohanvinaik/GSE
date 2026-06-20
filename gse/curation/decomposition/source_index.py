"""Index the RAW Wiktionary source into a queryable SQLite — Phase 1 table-stakes.

The source `kaikki-english.jsonl` is a 2.7 GB flat JSONL; grepping it per build is
a linear scan of a giant file (the reason every build stalled). This streams it
ONCE into `data/definitions.db` (word, pos, sense_idx, gloss), indexed on word, so
every lookup is milliseconds thereafter.

Faithful to the source: just the raw Wiktionary glosses, indexed. NO derivation,
NO reuse of the old broken derived DBs (`wiktionary_primitives.db`, the degenerate
`lexicon.db`) — those are the outputs we're replacing.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import List, Optional, Tuple

KAIKKI = "data/external/wiktionary/kaikki-english.jsonl"
OUT_DB = "data/definitions.db"


def build_index(kaikki: str = KAIKKI, out_db: str = OUT_DB) -> dict:
    """One-time pass: kaikki-english.jsonl → indexed (word, pos, sense_idx, gloss)."""
    if os.path.exists(out_db):
        os.remove(out_db)
    con = sqlite3.connect(out_db)
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA journal_mode=MEMORY")
    con.execute("CREATE TABLE definitions "
                "(word TEXT, pos TEXT, sense_idx INTEGER, gloss TEXT)")

    n_rec = n_rows = 0
    t0 = time.time()
    batch: List[Tuple[str, str, int, str]] = []
    with open(kaikki) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            w, p = r.get("word"), r.get("pos")
            if not w or not p:
                continue
            n_rec += 1
            for i, s in enumerate(r.get("senses", [])):
                g = s.get("glosses") or s.get("raw_glosses")
                if g:
                    batch.append((w, p, i, g[0]))
                    n_rows += 1
            if len(batch) >= 20000:
                con.executemany("INSERT INTO definitions VALUES (?,?,?,?)", batch)
                batch.clear()
            if n_rec % 100000 == 0:
                con.commit()
                print(f"  {n_rec:>8} records · {n_rows:>9} glosses · "
                      f"{time.time() - t0:5.0f}s", flush=True)
    if batch:
        con.executemany("INSERT INTO definitions VALUES (?,?,?,?)", batch)
    con.commit()
    print("  building word index…", flush=True)
    con.execute("CREATE INDEX idx_word ON definitions(word)")
    con.commit()
    con.close()
    dt = time.time() - t0
    print(f"DONE · {n_rec} records · {n_rows} glosses · {dt:.0f}s → {out_db}",
          flush=True)
    return {"records": n_rec, "glosses": n_rows, "seconds": round(dt, 1),
            "out_db": out_db}


def senses(word: str, pos: Optional[str] = None, db: str = OUT_DB
           ) -> List[Tuple[str, int, str]]:
    """Indexed lookup → [(pos, sense_idx, gloss), …] for a word. Milliseconds."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    if pos:
        rows = con.execute(
            "SELECT pos, sense_idx, gloss FROM definitions WHERE word=? AND pos=? "
            "ORDER BY sense_idx", (word, pos)).fetchall()
    else:
        rows = con.execute(
            "SELECT pos, sense_idx, gloss FROM definitions WHERE word=? "
            "ORDER BY pos, sense_idx", (word,)).fetchall()
    con.close()
    return rows


def primary_gloss(word: str, pos: Optional[str] = None, db: str = OUT_DB
                  ) -> Optional[Tuple[str, str]]:
    """First sense (the primary definition) for a word, POS-matched when given."""
    rows = senses(word, pos, db)
    if not rows and pos:
        rows = senses(word, None, db)
    return (rows[0][0], rows[0][2]) if rows else None


if __name__ == "__main__":
    build_index()
