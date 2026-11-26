# Active lexicon: senses6 (sub-kind inheritance) (2026-11-26)

`data/lexicon_active.json` names `lexicon_builder/2026-11-12/sparse-release-022-senses6.db`, the only lexicon copy
on disk (Rohan: keep the live one, the most complete one and the one being built; senses5 was deleted once senses6
was strictly better).

senses6 = senses5 plus the sub-kind inheritance layer (`word_sense_subkinds.py`, e4c8e7a) in the derived table the
word senses read below every stated value, and every word sense rebuilt.

| | senses5 | senses6 |
|---|---|---|
| nonzero sense values | 142,113 | 149,883 (7,770 inherited) |
| NSM agree / contradict / missing (`-lexicon-vs-nsm-senses6.json`) | 47 / 7 / 308 | 50 / 7 / 305 |
| warrant, acceptance and no-new-model guards | pass | 27 passed |
| `build_word_senses.py --verify 300` | 300/300 | 300/300 |
| the 66 encoder test files | 1,691 passed, 1 failed (sparse-wiki data) | the same |
| example sentences | cut unread | cut HAPPEN+1; others unchanged |

Inheritance (`2026-11-26-subkind-inheritance.json`): 63,638 definition cells on 29,858 definitions (54,062 inherited
and 9,576 strict consequences of them under the release's rules); 0 defaults suspended by the constraint closure; 0
exceptions; 19,093 hub values not promoted (one source, no kind confirms). Channels: WordNet kind-of, synonymy,
adjective satellite to head, verb entailment, Wiktionary form_of/alt_of. Gate: significance weighting's admissibility
(spine value or a kind that independently states it). Defeaters: substance -> part.n.01, move.v.02.
