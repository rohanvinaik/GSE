# Scoped lexicon-builder MVP — 2026-10-25

The real builder emitted 11 complete candidate definition vectors across quality, size and happy/sad feeling properties. Exact checks of all 58 states matched the authored expectations for those scoped readings. One reading remained partial and two unsupported controls abstained. These are MVP acceptance checks, not an independent linguistic gold corpus or evidence of general lexicon coverage.

## Run it

From the GSE repository:

```sh
uv run python -m gse.lexicon_builder build \
  --words excellent terrible enormous tiny superb immense delighted miserable ecstatic sorrowful happy awful furious quuxlexiconcontrol \
  --output /tmp/gse-mvp

uv run python -m gse.lexicon_builder number-order \
  --input /tmp/gse-mvp/vectors.jsonl --left happy --right delighted \
  --output /tmp/gse-mvp/number-happy-delighted.json
```

The constructor loads native records and shared rules. The acceptance cases are separate fixtures; they are not inputs to construction. No word-specific override, gloss parser or source-voting path is used.

The frozen evidence is [manifest.json](manifest.json), [words.jsonl](words.jsonl), [vectors.jsonl](vectors.jsonl), [rulebook.json](rulebook.json), and the `implementation/` snapshot. The snapshot records the build that produced these vectors; it is not an alternate active implementation. The later NUMBER command records its own implementation hashes and the vector-file digest in [number-happy-delighted.json](number-happy-delighted.json).

Consume the artifact with `gse.lexicon_builder.artifact.read_vectors(path)`. Each reading has canonical states, mask, numeric coefficients, 72 signed prime views, NUMBER metadata and provenance. Written zero and silence remain different.

## What was resolved

| Scoped reading | Nonzero content | Explicit zeros | Silent coordinates |
|---|---|---|---:|
| excellent, superb | GOOD:+1, INTENSITY:+1 | SOMETHING:0 | 55 |
| terrible, awful | GOOD:−1, INTENSITY:+1 | SOMETHING:0 | 55 |
| enormous | BIG:+1, INTENSITY:+1 | SOMETHING:0 | 55 |
| tiny | BIG:−1, INTENSITY:+1 | SOMETHING:0 | 55 |
| happy, delighted, ecstatic | FEEL:+1, GOOD:+1, INTENSITY:+1 | SOMETHING:0, KIND:0 | 53 |
| miserable, sorrowful | FEEL:+1, GOOD:−1, INTENSITY:+1 | SOMETHING:0, KIND:0 | 53 |

These 11 vectors account for every canonical coordinate. The remaining silent masks are explicitly **provisional**, following the scoped template and local omission challenge; they are not relabeled as symbolically certified silence. Every artifact remains `production_eligible:false`.

The source conditions establish the own property and its signed pole. In the feeling reading, FEEL presence triggers the guarded KIND:0 consequence. The shared `OWN_DEGREE_BEARING_CONTENT` rule establishes INTENSITY relevance; it does not threshold words by strength. This directly implements founder F125–F126. The local model was not asked to choose any of these established states. It made one constrained omission check for each of the 12 applicable readings.

`immense` retained BIG:+1, SOMETHING:0 and INTENSITY:+1, but its omission challenge proposed QUANTITY. It therefore remained partial and was not exported as complete. `furious` has source records but lacks an applicable completed MVP profile; its disgust association was not converted into lexical content. `quuxlexiconcontrol` has no matching source records and received no invented vector. Other native alternatives, including the other uses of `awful`, remain in the native record.

## NUMBER is value, not another presence bit

The [real NUMBER run](number-happy-delighted.json) compared identical happy/delighted signed patterns. Its two schema-constrained model outputs were LESS and MORE. Symbolic inversion accepted the pair and recorded happy at ordinal 0 and delighted at 1 within the named pair scale. Those ordinals are **not** multiplication coefficients or a claim of equal spacing. Every mask and sign stayed unchanged; numerical gain remains unset.

The live [self-comparison](number-self-control.json) resolved equality without a model call. The [incompatible-pattern control](number-incompatible-control.json), tiny versus happy, returned `INCOMPATIBLE_PATTERN` and no NUMBER value or model call. Ordinary tests additionally enforce that repeated same-direction answers are a contradiction, not a value to average.

This is a functional pair-relative operator. Global scale construction, cross-pair transitivity, equality-class reconciliation and numerical gain calibration remain unfinished. Bidirectional consistency alone does not establish lexical truth; the happy/delighted order is also an explicit common-sense acceptance case.

## Reproduce the checks

```sh
uv run python docs/verification/lexicon-rebuild/mvp-rule-first-live-2026-10-25/verify.py
```

[cases.json](cases.json) declares the expected scoped vectors and controls. [semantic-check.json](semantic-check.json) records the computed comparison and file digests. Word outcomes are reported separately: 11 identified, 0 mismatches, 1 partial, 2 abstained, 0 unavailable. NUMBER checks are separate from those word counts. A zero checker exit means no checked mismatch; it does not turn partial readings into completed definitions.

Intent/MUST-NOT tests cover source-premise ablation, association leakage, scoped KIND propagation, omission refusal, written zero versus silence, alias polarity, malformed vectors, scale compatibility, inverse order consistency and input immutability. Detective generated additional tests for the artifact validator and order-consistency decision. Its bounded-search limitations are retained in its reports; the generated tests do not certify linguistic truth.

The earlier degree-ablation/BASE-versus-AMPLIFIED trials used an incorrect interpretation of INTENSITY. They are superseded by F125–F126 and are not semantic labels or a basis for fitting exceptions.

## Remaining boundary

This MVP constructs the demonstrated scoped property readings. It has not completed the general rulebook, atomic combinatorial-profile review, random 2K–10K cohort, 1,000-word run, global NUMBER calibration or production lexicon import. The [active design](../../../program/LEXICON_CONSTRUCTION_DESIGN.md) remains the construction contract.
