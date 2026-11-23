# Historical replay of the corrected cohort

The manifest worklist is identical in both builds: 1,040 words. All 470 historical readings survive. The corrected build contains 2,342 readings, including 1,872 additions and 0 removals. These are measured differences, not semantic approval.

Every changed shared cell is OPEN_TO_SETTLED: 4,082. Settled-value changes: 0; reopened settled cells: 0; settled-to-conflict transitions: 0. The empty `settled-cell-review.jsonl` and `removed-readings.jsonl` files record that no such cases were found.

| Recorded restricting writer | Changed shared cells |
|---|---:|
| EVALUATOR_EXCLUDES_SIZE | 8 |
| FEAR_AVERSION | 2 |
| NATIVE:VN_CAUSATION | 440 |
| SIZE_DESCRIPTOR_EXCLUDES_EVALUATION | 8 |
| VERB_HEADS_NO_SUBSTANTIVE | 3,624 |

A restricting trace records domain reduction. It does not establish the semantic validity of its rule. `reading-ledger.jsonl.gz` retains full source premise IDs, recorded applications, bindings, unmapped predicates and decisions for both sides. Old records lack application IDs; that absence is labeled as missing schema evidence.

The complete `cell-ledger.jsonl.gz` contains 135,836 unique rows: all 58 coordinates for every reading in the union, including unchanged cells and all cells in new readings. Its counts were independently decompressed and checked against the summary.

Source pins: 1,158 additions, 0 removals, 0 changed hashes, 5 path-only changes and 238 unchanged pins. FrameNet detail files account for the added source coverage; adapter metadata and native records differ across the cohort. Exact file records are in `source-pins.json`.

Recorded model calls: old 0, new 0. No model or gold source is imported by the comparison script. Both inputs were hashed before and after comparison and remained unchanged.

The packet also contains exact writer counts, construction additions and a standalone reproducible `compare.py`. No baseline was refreshed. The 63 complete prime readings belong to this cohort; this comparison does not claim that the cohort includes every prime.

## Final metadata refresh

The final comparison input is `/private/tmp/gse-lexicon-final-gate-build-current-20261025`. Direct comparison with the previous corrected cohort checks 135,836 cells across 2,342 matching readings: 0 cell/reading changes and 0 domain-order changes. The recorded field changes are listed in `cohort-metadata-refresh.json`; no model calls occurred.

Local-byte validation checked every original pinned path: 243 historical and 1401 current file pins. Their exact results and hashes are in `source-pin-validation.json`. Both sets match their pinned hashes. No baseline was changed.
