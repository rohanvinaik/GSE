# Frozen paragraph performance evidence

Four actual entry-point cProfile captures completed with exit 0: raw/healed complete CLI reads, and the same raw/healed GSE worker entrypoints in separate processes. The measured paragraph has 1,290 characters, 7 source sentences, and 211 source words. No source was edited; no long source was reparsed.

| Mode/domain | Wall seconds | User seconds | System seconds | OS max RSS bytes |
|---|---:|---:|---:|---:|
| read-raw-cli-complete | 5.205387 | 3.77 | 0.78 | 535511040 |
| read-healed-cli-complete | 8.355701 | 5.61 | 1.31 | 590757888 |
| read-raw-worker-complete | 9.548883 | 7.45 | 0.91 | 553402368 |
| read-healed-worker-complete | 11.209567 | 9.24 | 1.27 | 597573632 |

All four complete semantic records are SAME against their saved final CLI baseline before normalization: zero field differences. Both CLI output files are also byte-identical to the baseline files. All 59 whole-document metric rows, the paragraph view, complete passage evidence, source/measurement identities, code identities and named partial/unsupported states participate in comparison.

The declared normalization removes only operational cache fields on recognized healing-resource receipts and the mirrored WordNet receipt. It preserves stale/unverified states, identity scope, source/resource hashes and paths, code, and every semantic field. No timing fields were removed. Normalization was unnecessary for these captures.

The parent profile spends 5.034s raw / 8.134s healed in kqueue waiting for the GSE process. The separate worker profile measures resource provenance at 4.604s raw / 4.357s healed, dominated by WordNet lazy loading (4.357s raw). The healed worker also measures suggest at 2.605s. These cumulative intervals overlap their callers and must not be added. The resource receipt reads wn.root/get_version; even raw mode captures those dependencies.

Resource-independent path counts are read_source/read_document/run_probe once, profile twice (whole plus paragraph), and 118 metric-row constructions (59 in each view). Observed semantic populations are 11 utterances, 34 claims, 43 mentions, 8 nodes and 4 edges. Raw has 3 flags and no applied edits; healed has 2 flags and 2 applied edits. Both retain 56 measured, 2 partial and 1 not_applicable whole-document metric rows.

This is one observed run per mode/domain, with cProfile overhead and uncontrolled machine/OS caches. Parent cProfile does not inspect child internals; the worker profile is a separate replay of the exact public payload. macOS rusage memory/counters are not function-level memory attribution. No speedup, tuning or comparative benchmark is claimed.

GSE source SHA256: `b4510b6b8ec1b3b0c3ac173d7a954e6968cf59a93785fd84027a63ea15366b2a`. All nine consumer hashes and the selected source hash are in performance-public-receipt.json. Each producer initial/final identity is frozen and read; the final healed worker additionally has independent launcher before/after GSE and all-nine-consumer hash proofs. All source/consumer identities are checked again after analysis.

Public artifacts: performance-public-receipt.json and storage-public-receipt.json contain numeric/hash/code-name evidence without source passages or lexical snippets. Private artifacts: exact resolved commands/environments in runs.private.json; full stdout/stderr, payloads, pstats, full stats/callers, assembled worker Readings and complete comparison data remain beside this report with private filenames. The public receipt gives exact parameterized commands; private runs.private.json preserves their literal resolved argv.
