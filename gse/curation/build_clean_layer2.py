"""Layer-2: genus-differentia decomposition for words the sources didn't ground.

ADDITIVE to the clean DB — writes only `source='layer2'` rows, never touches
Layer-0 (tier_0) or Layer-1. Fully reversible (`DELETE WHERE source='layer2'`).

Mechanism is the EXISTING `definition_linker` (genus chain over the grounded
floor + differentia) — no new decomposition logic. Common-register first per the
plan: the frequency-ranked words Layer-1 missed, restricted to content POS
(closed-class words are informational-zero and skipped, not written).

The representative sense for a POS-free entry is the word's dominant content POS
(most senses) — a flagged choice; the genus chain itself uses POS-from-role.
"""

from __future__ import annotations

import sqlite3
import time
from collections import Counter

from gse.curation.decomposition.definition_linker import Linker
from gse.curation.decomposition.definitional_decomposer import _CLOSED_CLASS
from gse.curation.decomposition.source_index import senses

CLEAN_DB = "data/lexicon_clean.db"
FREQ_DB = "data/frequency.db"


def _dom_pos(word: str):
    rows = senses(word)
    if not rows:
        return None
    return Counter(p for p, _, _ in rows).most_common(1)[0][0]


def main(clean_db: str = CLEAN_DB, freq_db: str = FREQ_DB) -> dict:
    con = sqlite3.connect(clean_db)
    # The decomposition FLOOR is tier-0 + Layer-1 ONLY, but the candidate pool
    # excludes EVERY lemma that already has a row: operators / quantifiers are
    # grammatical homes (never content-decomposed), and a layer1 lemma is
    # already grounded. Excluding only the floor collided with the operator/
    # quantifier rows once those layers existed (UNIQUE lemma,pos,sense_id).
    grounded = {r[0] for r in
                con.execute("SELECT lemma FROM lexemes WHERE source != 'layer2'")}
    fc = sqlite3.connect(f"file:{freq_db}?mode=ro", uri=True)
    freq = [(r[0].lower(), r[1]) for r in
            fc.execute("SELECT word, combined_rank FROM frequency ORDER BY combined_rank")]
    fc.close()

    # Candidate pool: frequency-ranked common register + WordNet's single-word
    # lemmas (the authoritative "real English word" filter — excludes the exotic
    # junk in the raw 1.34M definitions dump). Ungrounded, deduped, content only.
    seen = set(grounded)
    candidates = []
    for w, rank in freq:
        if w not in seen and w.isalpha():
            candidates.append((w, rank)); seen.add(w)
    from gse.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser
    wn = WordNetHierarchyParser(); wn.load()
    for w in wn.get_all_words():
        w = w.lower()
        if " " in w or not w.isalpha() or w in seen:
            continue
        candidates.append((w, None)); seen.add(w)
    print(f"  candidate pool: {len(candidates)} words (frequency + WordNet real-words)", flush=True)

    # Clear any prior Layer-2 and COMMIT *before* the Linker opens — otherwise the
    # Linker's read-only connection still sees the old Layer-2 rows and reads them
    # back via grounded(), re-emitting stale values (non-deterministic counts).
    # After this commit the DB is floor-only (tier-0+layer1), so decomposition is
    # fresh against the floor.
    old = [r[0] for r in con.execute("SELECT id FROM lexemes WHERE source='layer2'")]
    con.executemany("DELETE FROM primitive_values WHERE lexeme_id=?", [(i,) for i in old])
    con.execute("DELETE FROM lexemes WHERE source='layer2'")
    con.commit()

    # PHASE 1 — decompose all candidates into memory (reads only). The Linker
    # reads the floor-only DB; nothing writes concurrently, so no lock contention
    # (the cause of the earlier "database is locked" on the long WordNet build).
    lk = Linker()
    t0 = time.time()
    built = []
    for i, (w, rank) in enumerate(candidates):
        pos = _dom_pos(w)
        if not pos or pos in _CLOSED_CLASS:
            continue   # informational zero — not a stored entry
        d = lk.evaluate(w, pos)
        if d:
            built.append((w, rank, d))
        if (i + 1) % 5000 == 0:
            print(f"  decomposed {i+1}/{len(candidates)}  kept={len(built)}  {time.time()-t0:.0f}s", flush=True)
    lk.close()

    # PHASE 2 — bulk-write (the Linker connection is closed; single writer).
    for w, rank, d in built:
        cur = con.execute(
            "INSERT INTO lexemes(lemma,pos,sense_id,source,frequency_rank,confidence,validation_status)"
            " VALUES(?,?,?,?,?,?,?)",
            (w, "x", "0", "layer2", rank, 0.8, "decomposed"),
        )
        con.executemany(
            "INSERT INTO primitive_values(lexeme_id,primitive,value,confidence,source) VALUES(?,?,?,?,?)",
            [(cur.lastrowid, p, v, 0.8, "layer2") for p, v in d.items()],
        )
    con.commit()
    written = len(built)

    counts = {s: n for s, n in con.execute("SELECT source,count(*) FROM lexemes GROUP BY source")}
    con.close()
    stats = {"written": written, "counts": counts, "seconds": round(time.time() - t0, 1)}
    print(f"Layer-2 written: {written}  | DB now: {counts}  ({stats['seconds']}s)")
    return stats


if __name__ == "__main__":
    main()
