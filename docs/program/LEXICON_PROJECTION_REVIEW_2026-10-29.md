> Historical pre-decision record. Rohan has since accepted and refined the conventions. The current formal design and implementation status are in [LEXICON_CONSTRUCTION_DESIGN.md](LEXICON_CONSTRUCTION_DESIGN.md); the original unapproved proposal JSON and its audit remain historical evidence.

# Proposed GSE conventions for review

These are explicit proposals requested by Rohan, not admitted laws and not claims that the NSM chart supplies complete GSE vectors. The executable builder, stored evidence, exception handling and review interfaces are implemented. The remaining semantic foundation is not concealed by that software completion.

The machine-readable companion, `LEXICON_PROJECTION_PROPOSALS_2026-10-29.json`, preserves all 65 primary chart units, the proposed coordinate correspondences, their complete combinatorial frames, and explicit unknown cells. It also contains the 20 relational tables below, all with `approved: false`. A proposal cannot be passed to `build --rules` as an approved manifest.

## Proposed relational closure

| Proposed convention | Scope and reason | Necessary caution |
| --- | --- | --- |
| I → SOMEONE; YOU → SOMEONE | Personal reference retains its distinct deictic coordinate and person-category content. | This is an additional component, not replacement of I/YOU by SOMEONE. |
| BODY → SOMETHING | Body-denoting nouns are independently denoting objects. | A body mentioned as an action's participant does not qualify. |
| ONE → QUANTITY; TWO → QUANTITY | Cardinality is quantity-bearing. | This types a component; it does not set a magnitude or assign NUMBER as a flat prime. |
| MOVE → HAPPEN; DO → HAPPEN; CAUSE → HAPPEN | An actual lexical event component implies occurrence. | Do not flatten negated, hypothetical or embedded events, or infer an agent. |
| GOOD ≠ 0 → BIG = 0, for adjectives | Proposed conditional separation of pure evaluation from size, following F067. | Explicitly joint meanings defeat the default locally. |
| BIG ≠ 0 → GOOD = 0, for adjectives | Proposed conditional separation of pure size from evaluation. | Conventional affect and literal evaluation must remain separate. |
| THEN, BEFORE, LONG_TIME ≠ 0 → WHEN; MOMENT → WHEN | Temporal subtypes retain temporal content and their signed distinctions. | A time occurring only in an example is not a lexical warrant. |
| ABOVE, FAR, OUTSIDE, TOWARD ≠ 0 → WHERE; HERE, SIDE → WHERE | Literal spatial subtypes retain spatial content. | Separately identified metaphorical meanings can be exceptions. |

The two GOOD/BIG rows are the same exclusion table with the columns reversed: twenty proposal records contain nineteen distinct tables. They represent one review decision. The current executable guards restrict that exclusion only to adjectives; “pure evaluation” and “pure size” are explanatory intent, not implemented guard distinctions. Approval as written would therefore assert absence whenever only one component is known. A narrower typed guard or explicit per-definition absence evidence would avoid that unwarranted generalization.

All consequent positive values above mean `+1`; arrows preserve existing assignments and pass through the conditional-exception resolver. The relations are proposals about GSE representation, not new assertions about the scientific truth of NSM.

## Representation choices that need a ruling

1. **Negative volition.** Proposed convention: the specifically identified DON'T WANT unit uses WANT = −1; zero remains absence. The alternative is structured NOT over WANT. Those geometries differ, and the existing code does not establish their equivalence.
2. **THIS.** Proposed convention: use the existing deictic/reference structure at sentence scale and keep the current closed word basis. This leaves the standalone word-scale signature incomplete; adding a new coordinate instead requires an explicit versioned basis decision.
3. **FOR SOME TIME.** Proposed convention: temporal content plus a duration component whose relative level remains unknown. WHEN alone cannot distinguish duration from reference, and neither LONG_TIME sign should be invented merely to fill the gap.
4. **Ordinal baseline.** Proposed convention: use `primitives_v2` as the construction baseline, then explicitly migrate alternative modifier encodings. Existing code gives VERY both +1 and +2, and NONE both −3 and −5. Relative comparisons need one declared convention; this is not a demand to preserve every old table.
5. **Prime signatures.** Bind actual dictionary definitions explicitly, then populate only warranted cells and propagate the reviewed relations. A chart name is not a complete vector, and an unfilled cell is not an explicit zero. Do not label a one-bank seed a completed prime definition.

I do not propose GOOD → WANT, GOOD → FEEL, or SEE → KNOW: the current evidence does not establish those as universal own-word implications. Nor do I propose converting frame participants into objects, source silence into zeros, or recurrence counts into causal proof.

## What the corpus audit establishes

The read-only proposal audit at `docs/readings/2026-10-29-lexicon-coherence/proposed-rule-audit.json` evaluates all 155,111 stored definitions, separately and jointly, with proposed relations active only in memory. The final snapshot (3,208,354 observations and 2,930,872 unresolved source records) produced 796 new HAPPEN assignments from MOVE and 1,439 from CAUSE; overlap leaves 1,939 joint additions. It changed no previously known value and recorded no exceptions. The other eighteen proposals made no changes under current evidence coverage.

That is not twenty validated semantic laws. Current admitted native assertions cover only seven coordinates: ALIVE, CAUSE, FEEL, MOVE, PART, SOMEONE and SOMETHING. Many proposed antecedents are therefore untested by this corpus projection, despite the breadth of raw source coverage. The audit carries its input fingerprint and complete representative definitions so this limitation is inspectable.

## Full-corpus replay result

The production CLI validator checked all 155,111 definitions and returned `REPLAY_VALIDATED`: 155,111 validated, zero mismatches, all outcomes PARTIAL. The build records 213,913 assigned cells (including 106,606 explicit zeros), 8,472,303 unresolved cells, and zero model calls. The saved reports are `docs/readings/2026-10-29-lexicon-coherence/build-report.json` and `validation-report.json`.

Replay verifies stored evidence, provenance and local rule closure. It is not semantic gold validation or exhaustive global satisfiability. The report explicitly excludes original discovery populations/weights and unpersisted definition source-ID metadata from full reconstruction; it does not independently validate the build summary.

## What remains after reviewing these proposals

Admission should produce an explicit versioned manifest of accepted scoped relations and definition anchors. Rebuild and replay it; evaluate against independent, reviewed labels; inspect every conditional exception; specialize a rule only when a real typed distinction explains its counterexamples. The current implementation supports guarded rules and local exceptions, but does not claim to have completed the entire significance-guided induction, guard-specialization and corpus-promotion loop.

The full default corpus is a sparse, source-backed construction result with unresolved domains. It is not ready to replace the active lexicon, and the large unresolved population should not be sent wholesale to a model. The founder's intended small tail has not yet been established. Its reduction requires the reviewed foundational signatures and additional justified source-to-bank relationships above.
