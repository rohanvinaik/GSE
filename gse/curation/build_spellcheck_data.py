"""One-command setup for SymbolicSpellCheck's data files.

A fresh clone has the committed package data (the CC-BY-SA misspellings table and the
project allowlist) but NOT the large rebuildable validity wordlist (gitignored). Run
this once to populate it:

    python -m gse.curation.build_spellcheck_data [--date YYYY-MM-DD] [local_titles.gz]

Builds:
  - gse/nlp/data/misspellings_wikipedia.tsv   (confusion table; committed, refresh only)
  - data/wordlist_wiktionary.txt + .bloom      (validity list; gitignored, REQUIRED for
                                                full jargon coverage — without it the
                                                corrector still runs on lexicon+WordNet)
  - data/spell_entities.db                     (alias-free entity-name dictionary for the
                                                proper-noun leg; needs data/genealogy.db,
                                                skipped gracefully when absent)
"""

from __future__ import annotations

import os
import sys

from gse.curation import build_misspellings, build_wordlist


def main(argv: list[str]) -> None:
    date = "unknown"
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == "--date" and i + 1 < len(argv):
            date = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    local_gz = rest[0] if rest else None

    print("[1/3] confusion table (Wikipedia common misspellings)…")
    build_misspellings.main([date])
    print("[2/3] validity wordlist + bloom (Wiktionary English titles)…")
    n = build_wordlist.build(local_gz)
    print("[3/3] entity-name dictionary (from genealogy.db canonical labels; alias-free)…")
    from gse.curation import build_spell_entities

    if os.path.exists(build_spell_entities._GENEALOGY):
        build_spell_entities.build()
    else:
        print("  data/genealogy.db absent — skipped (the entity leg degrades to a no-op)")
    print(f"done — validity list: {n} words (+ bloom). SymbolicSpellCheck data is ready.")


if __name__ == "__main__":
    main(sys.argv[1:])
