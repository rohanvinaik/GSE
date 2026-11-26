# Active lexicon pointer moved to senses5 (2026-11-26)

`data/lexicon_active.json` (untracked) now names `lexicon_builder/2026-11-12/sparse-release-022-senses5.db`. Rollback:
`sparse-release-022-senses3.db` (pointer copy at `/tmp/gse-senses/pointer-senses3.json`).

senses5 is senses3 with every word sense rebuilt at 4319632: the equal-encoding sense rule plus NSM molecule
inheritance (`word_sense_nsm_molecules.py`). NSM's "creatures" explication ("something like this can move / something
like this can feel something") binds to animal.n.01 through the common hypernym of its explicated subkinds, and every
noun sense whose WordNet members lie under it takes MOVE+1 and FEEL+1 where no member value or agreed source sign
speaks to those banks: 2,232 senses, FEEL and MOVE each.

| Check | Result |
|---|---|
| `build_word_senses.py --verify 300` | 300/300, 0 mismatches |
| warrant guard (recomputes every `nsm-molecule` value), acceptance, no new model values | 26 passed |
| the 66 encoder test files | 1,691 passed, 12 xfailed, 1 failed (`test_GSE_genealogy_store`: sparse-wiki's data, as before) |
| NSM measurement (`2026-11-26-lexicon-vs-nsm-senses5.json` vs `-v2.json`) | agree 43 -> 47, contradict 7 -> 7, missing 312 -> 308 |
| example sentences | unchanged readings |
