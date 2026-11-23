# Separate evaluation of the second Fear-family development trial

V2 emits six coordinate-complete candidates for five surfaces. The old-reference comparison still exposes a wrong pole and unresolved addition/mask challenges, so coordinate completeness is not a semantic-accuracy clearance.

`reveal-receipt-v2.json` pins the V2 results. The original evaluation manifest and all V1 result files remain byte-identical to their recorded digests. V2 follows inspection of the first development trial; it carries no new held-out accuracy claim.

## Identity and execution

The run directory is `/private/tmp/gse-family-live-v2-20261025`. The manifest's recorded rulebook and implementation digests match construction freeze V2, SHA-256 `da0968fdf51e13568221bd46583349f7534ba4bbf51b8fd3630af803208447e4`.

The working library `build.py` changed after the run imported its source, as the root reported. Evaluation therefore checks the run manifest against the freeze rather than pretending that present working bytes identify the earlier run. The evaluation reader's `artifact.py` matches the run manifest. These are source-identity receipts, not instrumented bytecode-execution proof.

All six Fear readings received their seven tasks. There are 42 recorded requests and 42 selections, with no abstentions. Selected states comprise 33 `+1`, four `-1`, and five written zeros. No optional-coordinate selection changed an additional optional coordinate's domain.

## Outcomes by construction layer

The complete per-reading 58-cell matrix is `live-v2-cell-matrix.json`; the independent old-reference ledger is `live-v2-reference-results.json`.

| Family account | Agrees | Wrong pole | Addition challenge | Zero/silence disagreement | No reference state |
|---|---:|---:|---:|---:|---:|
| Required, independently derived | 108 | 0 | 0 | 0 | 6 |
| Authored silent | 186 | 0 | 0 | 0 | 6 |
| Optional, model selected | 24 | 1 | 12 | 5 | 0 |

This split matters: the 318 agreements include 294 already established required/silence positions and 24 selected positions. It must not be presented as held-out model accuracy. Missing reference components generate addition challenges rather than proof of lexical absence.

The wrong pole is `THEN:+1` on *afraid* against `THEN:-1` in the frozen old projection. Addition challenges include MAYBE and MUST on *afraid/frightened*, THEN on *nervous*, KNOW and IF on both *scared* alternatives, and KNOW/MAYBE on *terrified*. Written-zero versus silence differences affect MAYBE/MUST on both *scared* alternatives and MUST on *terrified*.

The *nervous* MUST difference retains the explicit GSE practical-necessity projection qualification. The *frightened* THINK position retains the old source's suspected-misprint qualification. The five INTENSITY no-reference positions remain separate GSE degree-domain conventions. No frozen reference was changed to agree with V2.

No false omission or unresolved coordinate remains in V2. The scope/ablation/omission mechanics evidence remains in the separately pinned V1 contract-results packet, using the unchanged family semantics. It is not relabeled as a new V2 held-out positive test.

## Remaining evidence limit

There is still no untouched positive published Fear-family evaluation set. The separate primary neighboring-class checks establish scope only. This trial demonstrates complete candidate construction through a bounded live selector and preserves concrete residual semantic disagreements for diagnosis.
