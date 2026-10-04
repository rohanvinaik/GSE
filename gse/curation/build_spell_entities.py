"""Build ``data/spell_entities.db`` — the ALIAS-FREE entity-name dictionary for the
proper-noun leg of the spell-corrector.

The derivation is pure structure, from ``data/genealogy.db``:

  * **canonical labels** (``world_thread`` rows with ``src='label'`` ONLY — never a
    redirect/alias row), single-token labels kept as names directly;
  * **name-part tokens** of multi-token labels, under the same orthographic law the
    genealogy build uses (>=4 alphabetic chars; not a common lowercase WordNet word;
    a token shared by many entities keeps only the top-K by pagerank).

Wikipedia's redirect table — including its thousands of collated misspelling
redirects — is deliberately NOT consulted. The correction path must run on the
dictionary of what exists + the closed edit model + the pagerank prior alone; the
redirects serve as a held-out EVAL corpus instead (``scripts/eval_entity_leg.py``).
That split (structure corrects, collated data only measures) is the project's thesis
applied to the entity axis.

Common-word single-token labels ("war", "china" as porcelain) are skipped by the same
WordNet law: the WORD substrate already owns them, and letting them into the entity
space would make a common word a proper-noun correction target.

Schema:  entity_names(name TEXT, canon TEXT, pagerank REAL)  + idx on name,
         meta(key TEXT, value TEXT)  with n_entities for the percentile->rank prior.

Rebuild:  python -m gse.curation.build_spell_entities
Absent file => the entity leg degrades to a no-op (same contract as the marisa/HDC
caches).
"""
from __future__ import annotations

import os
import sqlite3
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GENEALOGY = os.path.join(_REPO_ROOT, "data", "genealogy.db")
_OUT = os.path.join(_REPO_ROOT, "data", "spell_entities.db")

# Same caps as scripts/build_genealogy_db.py's token-alias pass: a token shared by
# thousands of titles is a meaningless prior beyond its head.
_TOKEN_CAP = 8
_MIN_TOKEN_LEN = 4


def _common_word(tok: str) -> bool:
    """The orthographic-collision law (grounding._orthographic_collision / the
    genealogy token build): a token that exists in WordNet as a LOWERCASE lemma is a
    common English word and belongs to the word substrate, not the entity space."""
    from nltk.corpus import wordnet as wn

    for pos in ("n", "v", "a", "r", "s"):
        for syn in wn.synsets(tok, pos):
            for lem in syn.lemmas():
                if lem.name().lower() == tok and not lem.name()[0].isupper():
                    return True
    return False


def build(genealogy_db: str = _GENEALOGY, out_db: str = _OUT) -> int:
    src = sqlite3.connect(f"file:{genealogy_db}?mode=ro", uri=True)
    rows = src.execute(
        "SELECT label, MAX(pagerank) FROM world_thread WHERE src='label' GROUP BY label"
    ).fetchall()
    src.close()

    names: dict = {}          # name -> [(pagerank, canon), ...]
    n_labels = 0
    for label, pagerank in rows:
        if not label:
            continue
        pagerank = pagerank or 0.0
        n_labels += 1
        if " " not in label:
            if label.isalpha() and len(label) >= _MIN_TOKEN_LEN and not _common_word(label):
                names.setdefault(label, []).append((pagerank, label))
            continue
        for tok in label.split():
            if len(tok) < _MIN_TOKEN_LEN or not tok.isalpha() or _common_word(tok):
                continue
            names.setdefault(tok, []).append((pagerank, label))

    if os.path.exists(out_db):
        os.remove(out_db)
    conn = sqlite3.connect(out_db)
    conn.executescript(
        "CREATE TABLE entity_names(name TEXT, canon TEXT, pagerank REAL);"
        "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);"
    )
    n_rows = 0
    batch = []
    for name, cands in names.items():
        cands.sort(key=lambda c: -c[0])
        seen_canon = set()
        for pagerank, canon in cands:
            if canon in seen_canon:
                continue                      # one row per (name, entity)
            seen_canon.add(canon)
            batch.append((name, canon, pagerank))
            n_rows += 1
            if len(seen_canon) >= _TOKEN_CAP:
                break
        if len(batch) >= 20000:
            conn.executemany("INSERT INTO entity_names VALUES(?,?,?)", batch)
            batch = []
    if batch:
        conn.executemany("INSERT INTO entity_names VALUES(?,?,?)", batch)
    conn.execute("CREATE INDEX idx_entity_name ON entity_names(name)")
    conn.execute("INSERT INTO meta VALUES('n_entities', ?)", (str(n_labels),))
    conn.commit()
    conn.close()
    print(f"spell_entities.db: {n_rows:,} name rows / {len(names):,} distinct names "
          f"(from {n_labels:,} canonical labels; aliases never read)")
    return n_rows


if __name__ == "__main__":
    build(*sys.argv[1:])
