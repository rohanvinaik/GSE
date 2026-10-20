# Design

## Context

See proposal.md for motivation and evidence.md for authority and inspected paths. This is a proposed repair design, not a claim that its APIs already exist or that every definition was authored by Rohan. The scope is the GSE substrate used by the complete voice instrument. General generation, a new parser, a new ontology and unrelated repository cleanup are outside this change.

GSE currently has useful public typed and geometric surfaces, a shared proposition extractor, document resolution, a multiscale cassette substrate and spelling components. Failures occur at their joins. The canonical consumer contract is [contracts/gse-voice-boundary.md](contracts/gse-voice-boundary.md); the linked SquishOS change owns its metric catalog and source-file representation.

## Goals / Non-Goals

Goals: faithful typed reading, consistent commitment authority, complete source accounting, explicit unavailable channels and a reusable healing operation. Preserve the existing working symbolic constructions and resource ownership. No new runtime dependency is assumed.

Non-goals: replace typed structures with dense similarity; tune to an author's desired score; pretend the proof packet certifies arbitrary prose; modify unrelated Genesis or SparseWiki reasoning; install a framework; make the coding harness a prerequisite for specifying this work.

## Decisions

### D1. Repair existing producers and route their consumers

| Work unit | Existing path to inspect/change | Consumer and closure test |
|---|---|---|
| Lexical integrity | `gse/nlp/native.py`, `morphology.py`, `api/encoder.py` | token readings, spell core and operator attachment; false-prefix and lemma/capital/noun-verb minimal pairs through encode |
| Operator preservation | `_build_clause_expr`, `_build_operator_op`, tier/segmentation dispatch and evaluator | all public trees, proposition and graph walkers; clause contrast, head operators and unary restrictions preserve content |
| Scope authority | `symbolic/propositions.py`, `modality.py`, negative sign ownership | KB, narrative/emit adapters, proof packet and voice; modal/negation/conditional/attitude decisions agree |
| Identity and keying | `resolution.py`, `inference.py`, `scripts/proof_packet.py` | resolved entity IDs and signed relation keys; pronoun/antecedent join, same-lemma distinction, role-swap guard |
| Loss accounting | `coherence.py`, `discourse/speech.py`, `cassettes/multiscale.py`, `discourse/profile.py` | speech triples, cassettes, classifier and voice; no swallowed missing observations |
| Raw channels | `prime_projection.py`, `frequency.py`, external-source readers | word adapter; local-resource state and raw scale preserved |
| Healing/dictionary | `nlp/spellcheck*.py`, `mcp/spell_server.py`, `curation/personal_dictionary.py` | MCP, standalone spell and voice prepass; same ledger/text at each door |

The alternative, parallel voice-only parsing or a second proposition walk, would repeat the same consumer drift. Each change includes a reference inventory, its old/new public behavior, a negative guard and an end-to-end consumer test. Internal helper names are not acceptance criteria.

### D2. One claim authority, with a bounded fragment

Extend the existing `propositions` contract with the public operations in the boundary document. Keep `Proposition.node` and ordered `Scope` records. `status` is a lossy convenience; no consumer may infer commitment from it alone. `commitment`, `polarity`, `scope_signature`, `identity` and `claim_key` are individually testable. KB ingestion uses their result and preserves positive/negative facts separately. Rule ingestion must validate the supported whole rule, not take the first flattened antecedent/consequent and silently drop the rest.

Retain source operators and canonical lexical form separately: a negative lexical signature does not automatically mean a syntactically denied statement. Restrict equivalence/mining to supported keys and name coarse/generic or unresolved evidence. Include represented time/context and relevant argument roles in comparability; when unsupported, abstain rather than broaden the inference claim.

### D3. Preserve the clause core before adding operators

Build the supported clause predicate with its arguments, then attach a qualifying operator or combine clause predicates at their declared tier. `CONTRAST` remains the external operation label; occurrence tier distinguishes phrase and clause use. Unary operators must take the licensed operand side. Preserve G6 head-only readings: however/yet/still/instead → contrast; thus/therefore/hence/consequently → consequence; and → coordination; then → temporal. Mid-sentence readings remain context-specific. A head linker with no preceding clause retains an open discourse relation rather than an invented operand.

The existing soft-operator exception is evidence that absolute precedence is the wrong composition boundary. Do not add a new exception per word. Surface cases remain fixtures; tier, arity, attachment and recoverable core are the decisions.

### D4. Complete intake and multiscale failures

The speech iterator owns segmentation/attribution once and includes source sentence IDs. Its try boundary covers encode, tree construction and deixis. Existing triple/trees APIs wrap it; new consumers retain every outcome. Document resolution, fold and graph phases retain their own failure state. Fix `MultiScaleDoc.is_person` to return grounded eligibility/negative/unknown evidence; update its consumers so an unknown cannot become an unconditional true.

`text_profile` must return its failed populations and avoid zero-imputing failed valence. Preserve legacy classifier layout by explicitly projecting a complete operation catalog onto its existing keys where necessary. Do not silently change a serialized classifier vector without a version/migration. A coherence report is diagnostic evidence, never a certificate of semantic correctness; add verb/operand-preservation witnesses at the construction boundary rather than asserting complete detection from the current collapse heuristic.

### D5. Publish facts, retain resource boundaries

Source words expose lexical state independently of token prime maps. Existing lexical DB metadata can provide source/validation evidence; do not present `lemma LIMIT 1` as sense resolution. Preserve deterministic record choice and report ambiguity within the supported lookup policy. Do not redesign the full lexicon here.

Frequency uses the source-specific rank and an explicit database-open result. VAD/concreteness use their parsers' raw data from local paths with auto-download bypassed; neither arousal nor dominance becomes CAN/MUST or generic intensity. Structural EPA uses `gse.prime_projection.epa_projection`. Missing raw resources produce unread channels; their acquisition is a separate explicit task with no fake ratings or estimated metadata presented as measured.

### D6. Extract one healing core and one protected store

Move composition out of `gse.mcp.spell_server` into `gse.nlp.heal`, keeping MCP wrappers. Dictionary store includes `kind=term|name`, display surface, aliases, definition when supplied, review status and `source=confirmed|draft|learned`. Known confirmed definitions win merge conflicts; validate entries, write atomically and invalidate caches. Preserve the existing curation checks and validate the agreed intersection as well as each independent decomposition. Draft protection does not certify a definition. No absent historical draft is recreated from memory.

Use located edits rather than token rejoining. Policy guards first: protect dictionary entries and aliases; keep valid words, non-ASCII/unit/digit/markup forms. Uncertain names and edits remain offers. Preserve historical clear-typo recoveries through guard fixtures. Boundary repair only edits where the declared structural evidence warrants it; ambiguous capitals are offered.

### D7. Optimize only behind evidence equivalence

The old plan identified eager primitive activations and sparse-index sorting as candidates; those are historical leads, not current speed claims. First profile the actual end-to-end path. Lazy activations must preserve serialization and restore values on deserialization; `assume_unique` requires an audited invariant for every index constructor. Cache only context-free stages by text, code/data/policy hashes. Speech attribution, document resolution and passage inference run in document order. Parallel healing is permitted only with byte-identical ordered outcomes and failure accounting. No JIT or dependency addition without a measured need.

## Migration Plan

1. Freeze the cross-project fixture/schema and map every public consumer before edits.
2. Land local intent tests with each repair; flip the corresponding expected failures only when the full consumer path passes. Keep independent guards.
3. Add new APIs compatibly where possible. Version changed records and classifier layouts where unavoidable. Record intended deltas beside preserved behavior.
4. Migrate KB/proof demonstrations/multiscale/profile consumers to the shared semantics. Do not treat a demonstration-only reducer as a production API.
5. Wire the SquishOS adapter against the contract; only then rebuild private references and recognizer artifacts.
6. Retire `scripts/voice_profile.py` after locating all consumers; point documented users at the SquishOS commands. `rohan_voice.py` is a separate consumer and must be migrated/refit, not assumed to depend on that retired script.
7. Reconcile README/architecture/theory status at their sources. `THEORY.md`'s invalid/reconciled conflict needs an explicit source-backed correction, not automatic promotion.

Rollback is per admitted repair and artifact version; keep source manifests and old artifact identities. Never relabel stale references as new-version data. All work remains local; no push or data upload.

## Risks / Trade-offs

- Coarse NSM forms can erase distinctions → retain original predicates and abstraction boundary; unsupported key construction abstains.
- A morphology repair can damage valid lexical readings → use positive and false-prefix pairs plus lexicon evidence, not more prefix overrides.
- Silent fallback looks robust → preserve failure records and independent channel states through every adapter.
- Classifier feature consumers assume an exact layout → keep an explicit legacy projection and version any changed layout.
- Optional rating data may be unavailable → report the channel's state and acquisition prerequisite; do not block unrelated measurements.
- Old golden transcripts encode bugs → require predicted deltas and negative guards; byte equality only for behavior intended to stay the same.

## Acceptance boundary

Automated checks establish the specified typed results, source preservation, bounded derivations and complete accounting. The linked voice change must additionally demonstrate real passage traces. A passing small proof suite or a zero collapse rate alone establishes neither full English correctness nor successful Winston-style communication.
