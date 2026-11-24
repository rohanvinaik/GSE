**ASSIGNMENT C — READ-ONLY FACT CENSUS complete; editing stopped.**

Saved under `docs/readings/2026-11-13-ssl-explicit-genera/`:
- `ssl-api-coverage-native-equivalence.json`
- `ssl-api-coverage-native-equivalence.md`

### Findings
- **2,508 candidate unknown→singleton cells** across **982 separate definition IDs**, **837 spellings**, and **546 exact native synsets**.
- **2,489 source-backed:** 1,701 direct VerbNet components plus 788 existing founder-rule consequences.
- **19 accepted-model-only**, separately identified.
- **483 candidates in frequency bands 1–1500**, including 481 source-backed.
- **Zero contradictory existing singleton-sign groups**.
- Six INTENSITY candidates excluded; no hierarchy/ordinal transfer.

The concrete reach gap is in `_verbnet_links`: exact native links reach `(word, synset)`, not every native synonym definition. Existing guards can isolate exact synsets using ancestry plus exhaustive immediate-child exclusions; the recorded scopes showed **zero leaked or missed eligible IDs**.

### Verification
- Independently checked all **155,111 original WordNet observations** against local WordNet 3.0.
- Reprojected **772 native VerbNet packets**: zero projection differences.
- **22 census checks passed**; corrected audit-assertion failure retained and explained.
- Foundation byte hash unchanged; all eight inspected source pins stable.

**No assignments transferred, rules admitted, database/source edits, activation, or measured H gain.** Active pointer remains `sparse-release-021.db`. These are candidate opportunities—not jointly validated gains or new transfer warrants.