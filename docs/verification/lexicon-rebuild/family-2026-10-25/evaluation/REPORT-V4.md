# Independent evaluation of V4 typed quantification

**CURRENT_RESULT: SEMANTIC_FAMILY_ACCEPTANCE_NOT_ESTABLISHED.** V4 demonstrates the shared symbolic quantification correction, complete candidate construction, and explicit abstention. The original-reference comparison retains semantic disagreements. This remains post-challenge development evidence.

The original evaluation manifest and every pinned V1/V2/V3 result were checked and remain unchanged. `reveal-receipt-v4.json` pins the V4 output files. The source freeze is `c103abac8a6c74f435bf0799fb970a20d676944c4a2a65144e2460a426f54c40`; the run manifest matches its implementation/rulebook digests. Artifact identities stayed stable during evaluation. No source or repository test file was edited by this evaluator.

## Typed quantification

All six Fear readings have QUANTITY +1 without a QUANTITY model task. The real public-builder ablation shows that removing either the `QUANTIFIED_TIME_PORTMANTEAU` law or the typed SOMETIMES claim reopens QUANTITY, preserves independently supported WHEN +1, and blocks complete export. The family expectation does not supply the deleted content. Exact records are in `quantification-ablation-v4.json` and `quantification-ablation-records-v4.json`.

## Settlement and execution

There were 36 requests, 35 selections and 1 abstention. No selection caused another optional coordinate's domain to change.

| Located reading | Status | Unresolved cells |
|---|---|---|
| afraid:ADJ:E5-:fear | CANDIDATE_COMPLETE | none |
| frightened:ADJ:E5-:fear | PARTIAL | MAYBE |
| nervous:ADJ:E6-:fear | CANDIDATE_COMPLETE | none |
| scared:ADJ:E5-:fear | CANDIDATE_COMPLETE | none |
| scared:ADJ:E6-:fear | CANDIDATE_COMPLETE | none |
| terrified:ADJ:E5-:fear | CANDIDATE_COMPLETE | none |

## Reference outcomes by construction layer

| Account | Agrees | Omission | Addition challenge | Zero/silence disagreement | Unresolved state | No reference state |
|---|---:|---:|---:|---:|---:|---:|
| REQUIRED | 114 | 0 | 0 | 0 | 0 | 6 |
| SILENT | 186 | 0 | 0 | 0 | 0 | 6 |
| OPTIONAL | 18 | 1 | 13 | 3 | 1 | 0 |

No wrong-pole or unresolved-reference-component outcome remains. The all-58-cell matrix is `live-v4-cell-matrix.json`; the raw ledger and source qualifications are in `live-v4-reference-results.json`. A reference's unexpressed component yields an addition challenge, not proof of lexical silence.

## Remaining semantic challenges

The remaining omission is *afraid* THEN: the candidate writes 0 where the old reference projects NOW as THEN -1. *Frightened* MAYBE remains unresolved.

Addition challenges remain for MAYBE/MUST on *afraid*, MUST on *frightened*, NOW/MUST on *nervous*, KNOW/MUST/IF on both *scared* alternatives, and KNOW/MUST on *terrified*. Written-zero/silence disagreements affect MAYBE on both *scared* alternatives and on *terrified*.

The *nervous* MUST position retains its GSE practical-necessity projection qualification; *frightened* THINK retains the old source's suspected-misprint qualification. INTENSITY applicability remains separately identified where the old reference did not assign a state. No reference was edited to agree with this trial. Exact residuals are grouped by coordinate in `CURRENT_RESULT-V4.json`.

## Vocabulary and evidence limits

Every actual request's signed-name vocabulary agrees with `canonical_pole`. THEN -1 is NOW. No offered, intermediate or serialized Fear temporal domain contains positive THEN. These checks establish execution of the declared domain restriction; they do not prove its wider semantic completeness.

No untouched positive published Fear reference set has been established. The earlier neighboring-primary and native-scope checks retain their separate scope. Coordinate-complete candidates remain distinct from semantic acceptance; residuals require shared source/scope/projection diagnosis rather than per-word fitting or automatic promotion.
