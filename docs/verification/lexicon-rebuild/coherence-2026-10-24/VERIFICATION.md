# Verification of the native-source coherence analysis

The production lexicon and its old generated prime values are not inputs to this run. The real analysis entry point is:

```sh
uv run python scripts/lexicon_coherence.py --output docs/verification/lexicon-rebuild/coherence-2026-10-24
```

It completed with 41,597 single words observed in at least two of seven sources, 197 cross-source numeric relations, 458 directional candidates and 190 conjunction candidates. `results.json` records exact source snapshots, the analysis script digest, contingency tables, discovery/held-out partitions, native-state entropy changes and all counterexamples. `REPORT.md` is generated from those results.

The authored arithmetic and intent tests completed: **16 passed**. They include perfect opposition, independence, absent antecedents, undefined lift, invalid counts, source-missing observations, the single-word boundary, held-out disagreement and a complementary parity relation with zero singleton information gain. That parity case checks the search mechanism; it is not a claim that a corresponding lexical relation was observed. Ruff and ty passed on the new analysis scope. The program reference/dependency checker passed.

Detective was invoked through the local Detective/Wesker checkouts in GSE's interpreter, after its regime resolved cleanly. Its `converge scripts/lexicon_coherence.py::relation_status` run returned:

> FINAL scripts/lexicon_coherence.py::relation_status: ⚠ UNGATEABLE — one or more mutants could not be BUILT, so they say nothing about any test — this measures the engine, not your suite; it is a defect to report, not a gap to close; the required verification measurement was invalid; resolve its reported reasons; diagnostic counts; no certified bound or verdict established

Its full report is `.detective/reports/converge_relation_status.txt`. It also reported that its generated test could not be collected; the generated import was `from lexicon_coherence import relation_status`, while the authored tests import `scripts.lexicon_coherence`. The unusable generated test was removed. No mutant equivalence was asserted and no Detective certificate is claimed. The analysis target was not rewritten to obtain a passing verdict.

These checks validate the calculation and its stated boundaries. Semantic review and promotion of candidate bank laws have not been performed by this analysis. Related-word leakage across hash partitions, source coverage bias and correlated annotation lineages remain limitations of the exploratory stability check.
