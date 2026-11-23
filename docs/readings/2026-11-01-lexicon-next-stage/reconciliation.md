# Fable consultation: reconciliation and next implementation increment

## Request, authority and scope

Rohan's current request, verbatim:

> Yes, continue. Collect Fable’s answer, reconcile it with the existing implementation and my intent, and tell me what we should do next.

Instrument: Rohan's stated lexicon-construction contract. Specimen: the implementation and saved execution evidence. Fable supplies an independent reading, not authority to change the design. Planning prose remains unverified where it is not supported by code or Rohan's decisions.

The consultation completed successfully through the Claude Code CLI with `claude-fable-5-1`, no tools or MCP servers, `apiKeySource: none`, and `stop_reason: end_turn`. The CLI's list-price cost estimate is not evidence of an API-credit charge. See `fable-cli-metadata.json` and `fable-answer.md`. My `independent-reading.md` was saved before dispatch and excluded from the packet.

This reconciliation made no production-code, candidate-value or active-pointer changes. Checks below are code inspection, offline digest reconstruction and exact read-only database queries. They are not a new full-corpus validation or a new semantic audit. Corpus totals in the consultation remain the dated October 30 checkpoint.

## Claim ledger

| ID | Claim and kind | Scope / falsifier | Test and disposition |
|---|---|---|---|
| R1 | Symbolic scaffolding followed by exact unresolved-bank model questions is the intended division of labor — user instruction | Requiring complete symbolic coverage before model work, or unrestricted vector generation, would violate it | Existing bounded writer follows this structure; no design reversal is needed |
| R2 | Batch answers pass the same cell-admission boundary — implementation claim | A production batch slot bypassing `complete_bank` falsifies it | `batching.run_batched_cohort.commit` explicitly calls `complete_bank`, then commits assertion and receipt atomically; Fable's packet uncertainty is resolved by inspection |
| R3 | Accepted zeros have independent semantic validation — semantic claim | A missing adjudication leaves correctness unestablished | Saved review marks the 32 assignments unreviewed; replay is not gold. This claim is not established |
| R4 | The reviewed-pattern loop reaches production rule admission — integration claim | A real versioned admission/migration caller would establish it | Inspected `run_workflow` explicitly reports no lexicon writes and unsupported production migration; the known production caller is the audit script. This integration remains unfinished |
| R5 | Different transport hashes imply different semantic protocols — inference | Exact reconstruction under one protocol falsifies it | Both single-transport digests reconstruct under protocol 8 with different context/output budgets; inference rejected |
| R6 | The letter-name GOOD=0 has unexplained authority — provenance question | An explicit stored derivation resolves it | Live trace identifies `founder:noun-own-evaluation`, provenance F057; no extra model assertion is needed |
| R7 | All source adapters are disconnected from symbolic inference — implementation claim | Existing assertion-producing paths falsify the broad claim | `collect_evidence` includes WordNet, closed-class and linked VerbNet assertion paths. Other projection candidates remain context-only. Broad claim narrowed |
| R8 | Adding an approved rule can preserve historical replay without migration — implementation claim | Reconstructed request identity depending on the supplied relation set falsifies it | `validation._provenance` rebuilds historical requests with that relation set. Versioned historical replay and candidate reclosure are needed |

## Reconciliation

### Retain the intended construction design

The scaffold may leave many cells unresolved. That is the intended model handoff, not a failed symbolic stage. Each model question remains tied to one definition and one missing bank, with source evidence, known banks and applicable constraints. Batching is already authorized. Unknown, explicit zero and abstention remain distinct. Lexical identity is not inferred from geometric equality; grammatical binding and world facts keep their separate roles.

Fable's statement that the batch cannot establish semantic correctness is supported by the saved review qualifications. Its phrase “zero bias is real” is too strong if read as a model diagnosis: an all-zero sample is observed, but bank selection, definition selection and model behavior are confounded. Earlier saved rulings include WANT=+1 for eager and WANT=-1 for reluctant, so an “always zero” account of all historical operation is already contradicted. Those older rulings do not validate the current protocol or the new zeros.

Do not use a mixed output-sign distribution as a pass condition. A correctly chosen cohort may legitimately contain only zeros. Use independently justified expected outcomes and explicit abstention cases instead.

### Resolve packet limitations rather than implement duplicate safeguards

* Batch execution already routes each item through `complete_bank`; the wrapper does not replace freshness, domain, scope or contradiction checks. External database changes also trigger `STALE_SNAPSHOT`. `OllamaBatchTransport` validates slot cardinality, exact bank schemas and domains and rejects dependent questions for one definition in a batch.
* Offline reconstruction produced the recorded main digest `6c6cdffea1ee2388581efb0ecd41564ed17195aaa529af4c87fe61ee250f4a64` with protocol 8, thinking false, context 32768 and output 1024; the retry digest `31030ef1d07e335abf049743e15a567abb1a7d0febbbae91351421b6b6682271` uses protocol 8, thinking false, context 36864 and output 256. All source hashes in the saved verification receipt still matched at this check.
* The letter-name entry's stored assertions contain seven original model cells before batch 002. GOOD=0 is separately derived by `founder:noun-own-evaluation`; it is not an eighth unexplained model receipt. This accounts for provenance without independently re-proving that rule's semantics.
* Replay checks provenance and request identity as well as constraint closure; the saved full replay also includes bounded joint-support checks. Calling it only arc consistency understates its structural coverage. None of those checks supplies semantic gold.

### Keep the confirmed gaps precise

`reviewed_patterns.propose_patterns` currently proposes unguarded bank-pair implications. It can count agreement and counterexamples, but cannot manufacture a causal warrant. Repeated ABOVE=0 / ALIVE=0 is not sufficient grounds for a production implication. The engine's typed guard capability must be used with an explicit derivation and exception conditions.

`_antecedent_state` refuses unsupported prior-model dependency chains and target leakage. This is an explicit limitation, not permission to strip earlier context. Fable's exact claim that 18 receipts are unusable was not independently established: `prior_known` alone does not distinguish native, rule-derived and model-derived values, and eligibility depends on the proposed antecedent and baseline. Preserve this as a per-pattern admission test.

The source path already imports justified assertions from several adapters. In contrast, `projection_candidates` are explicitly context-only, and unresolved definition links are recorded rather than guessed. Wiktionary's empty direct-assertion scope does not mean its definitions are absent from model evidence. Improve exact linking and justified projections; do not copy spelling-level ratings into every sense or turn candidate scores into facts.

The BE rejection rule recognizes the exact curated reference-only catalog. Additional exact lexical sources return NOT_APPLICABLE. That is narrower than the general approved BE convention, but NOT_APPLICABLE is not approval. Extend deterministic recognition where a complete source-backed classification is available; ambiguous cases continue through constrained adjudication. No new convention is needed to enforce the already-approved own-stative-content rule.

## Next implementation increment

1. **Build and run a finite semantic contrast audit.** Reuse the current typed transport/audit path, with database writes disabled and the target answer withheld. Cover justified +1, -1, 0, abstention, own-content/argument/world distinctions, and the YOU/BE discrepancy. Compare singleton and batch presentations of the same evidence, including batch companions/order. Source or approved-definition expectations must be independent of the model being checked. Report identified, abstained and wrong by class, not just schema success or one accuracy figure. Reconsider a failing cell and its dependent receipts through the existing archive path.

2. **Improve scheduling while bounded construction continues.** Retain Zipf priority, durable visits and all definitions. Add a recorded breadth policy so one spelling's many senses do not consume each small learning cohort. Prioritize unresolved banks using available source relevance and constraint connectivity, with deterministic tie-breaking and eventual coverage of the remainder. These priorities select questions; they never assign signs. Include basis definitions and common content words without making a complete prime matrix a prerequisite to model work.

3. **Connect evidence to the existing reviewed-pattern workflow.** Export exact candidate definitions, native/anchor baselines, complete model receipts and hash-pinned reviews into its typed input format. Distinguish supported antecedents, dependency-bearing antecedents and unresolved ones. Extend the review path to retain/replay dependency chains and prevent target leakage. Review tooling should support source-backed adjudication; the user need not manually approve every routine cell.

4. **Implement guarded proposal admission.** Reuse the resolver and relation representation. Each proposed rule needs its definitional warrant, typed applicability, explicit exception conditions, source/receipt lineage, disjoint audit population and recorded counterexamples. Direct model audits test the proposal; agreement counts do not establish its cause. The next useful demonstration is one justified rule carried through the entire path, not a large set of automatically promoted correlations. New semantic conventions alone return to Rohan for a decision.

5. **Implement versioned rule migration before broad fills.** Keep original receipts and the original rule/context version needed to verify them. Reclose a candidate under the new approved version, account for changed domains and affected dependent model contexts, and archive/reconsider invalidated rulings explicitly. Test an affected dependency chain, an unaffected entry, an explicit zero, an unknown and a contradictory proposal. No old receipt should silently become evidence for a question it was never asked.

6. **Repeat the coupled cycle and validate publication separately.** Execute bounded residual cohorts; review and audit their useful patterns; apply admitted rules broadly; reclose; ask only the new remainder. Full replay, independent semantic audit, declared population completeness and prime-foundation completeness govern eventual publication. Passing a batch or a structural replay never marks the full lexicon complete. The active pointer changes only after the complete candidate satisfies those gates.

The immediate deliverable should be a contrast-audited, breadth-aware cohort plus one end-to-end reviewed-rule admission/migration demonstration. These can advance alongside bounded construction; there is no requirement to wait for perfect symbolic coverage or a different inference host.

## What needs Rohan's decision

No new foundational decision is established as necessary to begin this increment. Existing instructions already settle batching, justified zeros, BE scope, word/grammar/world separation, identity versus geometry and publication conditions.

Fable's animacy/ALIVE, proper-name, dummy-pronoun/BE and possessive/HAVE cases belong in the evidence audit. They are not grounds to invent blanket mappings or to reopen the entire architecture. The exact cell may remain unresolved if its evidence cannot decide it. If the audit exposes a genuinely unspecified convention, present that exact definition, bank, evidence and competing outcomes to Rohan. Lexical-type-guarded zero rules likewise require individual justification; “pronoun” alone is not a warrant.

## Evidence locations

* `gse/curation/lexicon_builder/batching.py`: `run_batched_cohort`, nested `next_item` and `commit`.
* `gse/curation/lexicon_builder/model_batch.py`: `OllamaBatchTransport`.
* `gse/curation/lexicon_builder/residual.py`: `OllamaTransport.__init__`, `complete_bank`.
* `gse/curation/lexicon_builder/validation.py:329`: `_provenance`.
* `gse/curation/lexicon_builder/reviewed_patterns.py:135`: `propose_patterns`; `:323`: `_antecedent_state`; `run_workflow`.
* `gse/curation/lexicon_builder/evidence.py:631`: `collect_evidence`.
* `gse/curation/external_sources/source_scope.py`: full source-scope map and filtering functions.
* `gse/curation/lexicon_builder/scope_admission.py`: full module.
* `docs/readings/2026-10-29-lexicon-coherence/zipf-batch-002-verification-receipt.json`, ruling review, input-budget audit and retry-input preflight.
* Read-only `constructed-corpus.db` queries for the complete assertion sequence and GOOD trace of `wiktionary:en-you-en-noun-2YsMsj8i:1a8439a0a38c9ceda0caa33ff6c2362469673c22b330b24292e5176d7be33894`.
