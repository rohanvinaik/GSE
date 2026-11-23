Reading of the incremental constructor against Rohan's contract, from the sealed packet only. Rohan's words are the instrument, the code and receipts are the specimen, and the design prose is treated as unverified.

## Claim ledger

| # | Claim | Kind | Scope | Falsifier | Test available in packet |
|---|---|---|---|---|---|
| 1 | A model ruling cannot alter known cells or widen the question | Operational | `complete_bank` | an ASSIGNED result with nonempty `changed_known`, or a schema admitting a second field | `complete_bank` returns CONTRADICTION on `changed_known` or `new_exceptions`; schema has `additionalProperties: false`; protocol `known_values: IMMUTABLE` |
| 2 | Unknown stays distinct from zero | Operational | residual, reconsideration | a null stored as 0, or withdrawn cells becoming 0 | `_read_value` None yields ABSTAINED with no assertion; reconsideration left seven cells at `[-1, 0, 1]`; `coverage_delta_since_reconsideration` shows explicit_zero 32 equals assigned 32 |
| 3 | Frequency chooses work only | Operational | `_select_entries` | frequencies reaching `build_request` | frequencies appear only in the heap key `(-frequencies.get(lemma.casefold(), 0), residual_size)` |
| 4 | The 32 zeros are justified orthogonality | Semantic | 16 definitions | one cell whose definition carries own content in that bank | none: `semantic_gold: NOT_CHECKED`; every record `review: NOT_INDEPENDENTLY_REVIEWED` |
| 5 | The BE convention is enforced at admission | Semantic validation | `model_scope_admission` | BE=+1 admitted for a reference-only definition | enforced only when every exact lexical record is the curated catalog; a Wiktionary `pron` leaf returns `ADDITIONAL_EXACT_LEXICAL_SOURCE`, hence NOT_APPLICABLE |
| 6 | The pattern-to-broad-fill loop is operational | Integration | `reviewed_patterns` | a production write from an admitted pattern | `lexicon_writes: False`, `admission: UNAPPROVED_CANDIDATE`, `unsupported` lists `AUTOMATIC_RULE_PROMOTION` and `PRODUCTION_RULE_REPLAY_MIGRATION` |
| 7 | Replay establishes correctness | Semantic | full corpus | category error | `full_replay.gold: NOT_CHECKED`; replay is arc consistency over stored evidence |

## Q1 through Q3

**Q1, handoff fidelity. Operation is preserved.** `_scaffold` snapshots every approved relation with an ACTIVE, BLOCKED or EXCEPTED disposition and raises `missing_request_rule_proof` if one lacks a proof. `compact_scaffold` keeps the requested bank's connected component and hashes the omissions. After the answer, `complete_bank` rebuilds the request, compares hashes, re-resolves, and refuses CONFLICT, new conditional exceptions, or any changed known cell. That is Rohan's "bounded, constrained task" in structure.

**The gap is degree, not violation.** For 14 of the 16 definitions, `prior_known` was empty at the first question. The symbolic side contributed no assignment to any Wiktionary leaf of "you". Rohan's handoff says "only the REMAINDER, the SPECIFIC banks that aren't FULLY encoded". Here the remainder was the whole vector, and the "cross-channel information" was one gloss plus 56 open domains. The design's own section "Audited source-integration deficits" names the cause: Wiktionary's assertion scope is empty and the other adapters' projections are not connected to inference. This is a missing-integration gap. The scaffold is faithful and also nearly empty for this cohort.

**Semantic validation of zeros does not exist, by design.** The `model_scope_admission` docstring states "Zero, negative signs and null receive no new value here." The publication field `model_scope_code: NO_SCOPE_REJECTION` over 43 active receipts is therefore vacuous. The check can reject only BE=+1, and every active receipt visible in the review is a 0.

**Two operational points.** First, `batching.py` is hashed in the verification receipt but not supplied. Whether `run_batched_cohort` routes each slot through the same freshness, scope and contradiction checks as `complete_bank`: cannot determine. Batch 002 used batch size 4, so that path produced most of the 32 zeros. Second, in the single path `remaining = sorted((len(domain), bank))` is alphabetical when all domains have size 3. So every definition's first questions are ABOVE and ALIVE regardless of type. That is why the batch asked ABOVE of "Your." and ALIVE of a Chinese prefecture.

**Q2, what the 32 zeros establish.** They establish that the pinned transport returned `{bank: 0}` for 32 exact request hashes, that each passed freshness, closure and storage, that the assignment audit matched saved values to receipts, and that replay found no structural inconsistency. Nothing more.

They do not establish correctness, since there is no review and no gold. They do not establish discrimination. With no nonzero and no null among 32 answers, the sample cannot separate "these banks are orthogonal to these definitions" from "this model says 0". They do not establish independence from context. By `prior_known`, 18 of 32 requests already carried earlier model zeros in `known`; the letter-noun CAN question carried eight. Whether an all-zero `known` list primes 0: cannot determine, no counterfactual run exists.

Lexical-own-content risks visible in the records:
- **Curated "you" has native `animacy: ANIMATE`**, yet ALIVE=0 stands from batch 001. Whether animacy is lexical ALIVE content or grammatical metadata is Rohan's call. No receipt addresses it.
- **Six zeros went to three proper-name leaves** (Youzhou, prefecture, surname). Whether names carry word coordinates or belong to the world leg is unsettled. Budget spent there is the spelling-frequency artifact the design already admits.
- **The dummy-pronoun leaf** glosses as "stating the existence or typicality of something". Its BE cell is the first real test of "the definition's own stative content" and should not fall to alphabetical order.
- **"Your."** is a possessive cross-reference. Its informative cell is HAVE, not ABOVE or ALIVE.

Zero bias is real in the sample and confounded in cause: A-initial banks on function words and names, possible model tendency, possible priming. The protocol examples contain one 0 and two nonzero answers and give no leverage. The remedy is a discriminating probe, not a new zero convention.

**Q3, is the loop operational.** No, and the module says so. Reusable pieces exist: `reviewed_rulings` pins review to `receipt_sha256`; `propose_patterns` records `OBSERVED_AGREEMENT` and `OBSERVED_COUNTEREXAMPLE`; `stage_pattern` resolves in memory with `replace(pattern.relation, approved=True)`; `audit_pattern` asks the withheld target via `build_request` against baseline closure on disjoint audit IDs; `Relation.guards` and `absent_evidence` express typed scope; the approved-relations manifest is a promotion seam; `scripts/reconsider_lexicon_model.py` can archive receipts a new rule would invalidate.

Missing contracts:
1. **Export.** `run_workflow` never opens a database. Something must emit `gse.reviewed-pattern-input/1` from the candidate. Not in packet.
2. **Review.** `RULING_REQUIRES_EXPLICIT_REVIEW` needs a reviewer. All 32 are `NOT_INDEPENDENTLY_REVIEWED`.
3. **Antecedent eligibility.** `_antecedent_state` returns `UNSUPPORTED_PRIOR_MODEL_DEPENDENCY` or `ANTECEDENT_BASELINE_MISMATCH` for any receipt whose request already held model values. By `prior_known`, 18 of 32 receipts fail this. Only the 14 first-questions can serve as antecedents.
4. **Rule class.** `propose_patterns` emits bank-pair relations with no guards. From an all-zero batch it can only propose relations like ABOVE=0 implies ALIVE=0, which carry no causal content. The broad fill Rohan describes ("go wide with reasonable pattern-based fills") is more naturally a type-guarded rule, such as pos equals pron implies a bank value. The engine represents guards. The proposal generator cannot propose them.
5. **Promotion.** The section "Construction and inference" states receipt replay pins the full relation set, so adding a rule needs historical-ruleset migration. No code supplied.
6. **Causal warrant.** No machinery supplies it. `MODEL_AGREEMENT` is labelled `UNAPPROVED_PATTERN_NOT_GOLD`, correctly.

## Q4 and Q5

**Q4, prerequisites and acceptance tests.** Residual batches should keep running. These are additive.
1. **Discrimination probe.** Reuse the `gse.direct-model-transport-audit/1` path with the target withheld on anchored cells: WANT on `wordnet:want:desire.v.01`, WANT on NOT WANT, SOMETHING on THIS, INTENSITY on the approved VERY definition. Acceptance: returned signs match the anchors with `database_writes: 0`. A 0 on an anchored +1 is a recorded calibration finding before further batches.
2. **Bank selection.** `complete_dictionary` already accepts `banks` and `entry_ids`. Run the next cohort with banks fitted to the definitions' types, or an explicit scope over curated and WordNet content words. Acceptance: `new_assignment_values` is not solely `{"0": N}`, or the probe in step 1 has shown the model returns nonzero when warranted.
3. **Export and review.** Build the input exporter; Rohan reviews the 14 baseline-replayable receipts. Acceptance: `run_workflow` with zero budget yields `STAGED_ONLY` with no antecedent refusals, then a budgeted run yields agreement or counterexample codes on disjoint audit IDs.
4. **Promotion seam.** A versioned manifest entry plus a migration that re-replays or archives earlier receipts under the new relation set. Acceptance: `validate` reports REPLAY_VALIDATED with `components_solver_limited: 0`, no receipt lost silently, no known value changed except through recorded closure.
5. **BE admission coverage.** Decide whether `_catalog_reference_record`'s narrow class should extend to Wiktionary `pron` leaves whose gloss is pure reference. Test: a synthetic BE=+1 receipt for the leaf "The person spoken to or written to, as a subject" currently returns NOT_APPLICABLE. Rohan decides whether that is acceptable before BE is asked of those eleven leaves.
6. **Batched path review.** Supply `batching.py` or a test showing each slot passes `complete_bank`-equivalent checks.
7. **Account for GOOD=0 on the letter noun.** Batch 001 reports 16 rulings over two definitions. The curated entry received nine. The letter noun's `prior_known` shows eight values. The eighth's origin: cannot determine.

**Q5, settled versus open.** Settled by Rohan: scaffold then one-bank bounded residual; batching; Zipf-ordered increments; justification per bank; unknown distinct from zero; BE requires own stative content; identity distinct from geometry; replace only when complete and valid; WANT polarity; THIS anchor; VERY and EXTREMELY ordinals.

Genuinely open semantic questions:
- Is grammatical animacy lexical ALIVE content? This bears on the retained ALIVE=0 for curated "you".
- Do proper-name leaves carry word coordinates, or belong to the world leg?
- Is a lexical-type-guarded zero rule an admissible pattern class? "This adds no blanket pronoun-zero rule" and "go wide with reasonable pattern-based fills" coexist only if each such rule is individually approved with scope and receipts. Rohan should say whether that is his intent.
- Dummy "you" and BE; "Your." and HAVE.

Implementation details needing no ruling: within-entry bank order, cohort and batch sizes, the byte bound, the codebook, the schedule policy, reviewer tooling.

Cannot determine from this packet: the protocol version batch 002 used, since its two batch digests differ from the protocol-8 probe's; batched-path fidelity; the origin of the eighth letter-noun zero; whether 32 of 32 zeros reflect bank choice or model bias.
