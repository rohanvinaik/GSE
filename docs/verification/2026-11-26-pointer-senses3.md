# Active lexicon pointer moved to senses3 (2026-11-26)

`data/lexicon_active.json` (untracked) now names
`lexicon_builder/2026-11-12/sparse-release-022-senses3.db`. The previous target,
`sparse-release-022-verbnet-do.db`, is unchanged and is the rollback (pointer backup at
`/tmp/gse-senses/lexicon_active.backup.json`).

senses3 is the live release with its `word_senses` table rebuilt under the equal-encoding sense rule
(Rohan, 2026-11-25 03:28: same sense iff same encoding on the load-bearing banks; commit 0795753);
`build_word_senses.py --verify 300` replayed with 0 mismatches. Runtime changes read with it: an
out-of-variance exception must rule an agreed value out (b102cc0), and the bearer of a person-typed
predicate keeps its someone or creature senses (c091430). Rohan, 2026-11-25 21:28: set the pointer,
no publish cycle.

## Tests

Every test file that builds a `GSEEncoder` (66 files), real pytest exit codes:

| Run | Result |
|---|---|
| HEAD encoder, old pointer | 53 failed, 1639 passed, 12 xfailed |
| parent encoder (no bearer selection), old pointer | 53 failed, 1639 passed, 12 xfailed |
| HEAD encoder, senses3 | 53 failed, 1639 passed, 12 xfailed |

The failing IDs are identical in all three runs, all in `tests/test_runtime_native_identity_controls.py`;
they already fail on main against the old pointer.

## Witness readings

`2026-11-26-witness-readings-live.txt` vs `2026-11-26-witness-readings-senses3.txt`: nail loses QUANTITY+
and PART+ (unit of length and fingernail were merged into the fastener); room loses PEOPLE+ (its "people
in a room" sense). mother, man, delight and grief read only what their genuinely distinct senses share
when no context selects (mother the yeast substance vs the person; man the Isle of Man and the chess
piece vs the person; grief the feeling vs its cause). No verb or adjective reading changed.
