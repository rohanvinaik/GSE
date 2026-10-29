# GSE lexicon construction design

Status: approved semantic decisions with an implementation status ledger. Version: `gse.lexicon-conventions/2026-10-29`. Owner of semantic decisions: Rohan. This document consolidates the lexicon construction contract; it does not make historical planning documents authoritative.

## Authority and purpose

The controlling sources are Rohan's current instructions and `LEXICON_FOUNDER_WORDS_2026-10-24.md`. His 2026-10-29 decisions admit the category relations below, specify evidence-conditioned absence, fix WANT's three values, clarify THIS through the word/sentence boundary, and require defensible stable ordinals. The primary NSM v20 chart supplies prime units and combinatorial frames; it does not itself supply complete GSE signatures. Existing code is evidence of implementation, not authority over those decisions. `docs/THEORY.md` is not used.

The sentence boundary is grounded in `/Users/rohanvinaik/Projects/rohan-vinaik.github.io/papers/Core Documents/GSE/sentence_architecture.md`, read in full. Its historical passages about unrestricted model decomposition are superseded by Rohan's present restriction to a typed single-bank residual. Its set-theoretic and grammatical framing informs the boundary described below, without treating exploratory arithmetic or complexity estimates as established theorems.

The deliverable is a definition-indexed, provenance-carrying geometric lexicon, built primarily by deterministic source projection and relational closure. It is not a word-association table or a collection of complete vectors guessed by a model.

## Identity and representation

A definition is `(entry_id, lemma, lexical_type, definition, source_ids)`. Native dictionary identities are reused where they identify the intended definition. A new frame, roleset, source record, or grammatical use does not automatically create a new definition. Distinct objects may share geometry: dog and cat need not be geometrically different to remain different lexical identities.

For each ordinary coordinate, the value domain is a nonempty subset of `{-1, 0, +1}`. A singleton is an assignment. Zero means explicitly warranted orthogonality/absence in that coordinate; an unassigned domain means unresolved. Contradiction produces an empty domain and a named CONFLICT outcome, never a vote or a zero. Conflicted entries publish no values.

The existing registries reconcile to 56 ordinary word coordinates, with NUMBER and hierarchy markers treated separately. The representation contract records the ordered basis and its SHA-256 fingerprint. Changes to coordinate meaning, ordering, polarity or hierarchy conventions require an explicit versioned migration and a rebuilt artifact; they must not silently reinterpret a saved artifact.

NUMBER describes the ordinal position of an explicitly named component. It is not a flat coordinate pasted onto every word, and it cannot erase or invert that component's base sign.

## Word and sentence boundary

Word geometry contains the minimal definitional content relevant at word scale. Sentence geometry carries grammatical capabilities, operator scope, argument binding, tense, reference, and the set-theoretic relationships among identified objects. Complete representation across these scales does not require putting every grammatical distinction in the word vector.

THIS has demonstrative object-reference content: the approved lexical anchor is SOMETHING=+1. It does not gain a new THIS coordinate or a HAVE assignment. WHICH object is designated is a grammatical/contextual binding, represented through structured identity. Ownership here must not be conflated with possession: an object's assignment to a grammatical referent is different from asserting that someone possesses it.

At the interface, grammar constrains the permitted roles and bindings. A present but uninstantiated grammatical dimension is distinct from a dimension outside the permitted set. This distinction does not require storing every possible role in the lexical artifact: the active encoder assigns roles dynamically. Set membership, argument ownership, and operator scope operate on structured identities, not vector equality. Two sentences can have similar lexical geometry and different comparison truth conditions.

GSE already implements this separation. `gse/lexicon/pronouns.py` supplies demonstrative reference metadata, `gse/lexicon/function_words.py` supplies determiner metadata, and the symbolic/document paths bind references and represent possession separately. The separate `SentenceParser` also implements possible-role constraints; its existence is not a reason to replace the active dynamic path. Empty `sentence_primitive_values` tables do not establish missing grammar. The earlier requirement to populate static role masks as a prerequisite to this build was unsupported and is withdrawn.

For versioned dictionaries, the encoder now obtains the established `COMP_METADATA` grammatical operations independently of lexical definition selection. BECAUSE, ONLY and THAN therefore retain their causal, restriction and comparison operations even when the word's lexical lookup is missing or ambiguous. No lexical definition or bank value is manufactured by this bridge. Conflicting selected-row operator metadata fails with `GRAMMATICAL_OPERATOR_METADATA_MISMATCH`; the legacy lookup path retains its existing behavior.

Audit probes distinguish actual behavior from intermediate tags: “This dog runs” retains its running event, and “A dog runs. This is a dog” binds THIS to the antecedent. “A dog runs. This runs” instead loses the second event without a structural-loss warning. That is a specific existing parsing defect, not evidence that a new demonstrative or reference subsystem is needed. The lexicon migration obligation is compatibility with these existing consumers, including their grammatical metadata needs; sentence-wide repairs are tracked separately from dictionary construction.

FOR SOME TIME likewise must not be forced into a positive or negative LONG_TIME value merely to close a vector. Temporal lexical content and a duration/interval operation belong at their appropriate scales; duration magnitude remains unspecified unless warranted. Its full construction-to-sentence integration remains open.

## Source evidence and competence

Sources enter through the existing parser/integrator architecture. A source exposes native records and justified `to_primitives` projections; its assertion scope is explicit. Native records retain full available content and exact identifiers. WordNet currently supplies the definition spine. Exact VerbNet sense links can support event assertions; unresolved ratings and frame links remain evidence.

Every projection must distinguish the definition's own content from participants, embedded evaluations, examples, world facts, and associations. A verb taking a body argument does not thereby denote a body. World facts remain on the separate sparse-wiki leg. DeepNSM remains silver material for anchors/evaluation only and is not baked into the shipped lexicon.

An assertion requires an exact definition link and source competence. An unresolved candidate link cannot assert a sign, but it can prevent an absence claim while its relevant evidence remains unresolved. Source disagreement is retained. A large, optionally Zipf-weighted population tests proposed causal structure; its frequency does not establish that structure's truth.

### Relevance is not a value

An observation may carry `features.bank_relevance = {code: CLASSIFIED, banks: [...], provenance: [...]}`. This annotation names canonical coordinates the record can inform, without assigning their values. Empty banks means an explicitly justified classification as irrelevant to word-coordinate assignment. Missing classification means UNCLASSIFIED, conservatively potentially relevant to all coordinates. Malformed annotations fail ingestion/replay.

Source competence is an upper bound on what may be asserted, not a complete relevance classification for an individual record. Existing `SOURCE_PRIMITIVE_SCOPE`, native parser fields and projections are the starting machinery for this interpretation. The new builder's relevance annotations are an integration boundary, not a demand for a separate grounding system or manual classification of every record. A projection that emits no BIG assertion does not prove that its full native definition contains no size information. Unclassified records therefore continue to block absence defaults until their typed interpretation justifies a narrower relevance set.

The native collector now accepts an explicit adapter-owned `bank_relevance_for_entry` classification. SentiWordNet's exact six-field sentiment record is classified as relevant to GOOD; its identity fields introduce no additional measurement. This does not assert a positive, negative or zero lexical sign. Extra fields, malformed ratings, and unrecognized record shapes remain unclassified, and existing explicit annotations are preserved. Native record identity is computed before adding derived relevance. WordNet's unrestricted definition text remains potentially relevant to every bank; the bridge does not remove that separate blocker.

## Category content

The following additional category content is approved. Specific coordinates remain present; no identity is replaced by a superclass.

| Antecedent | Consequent | Scope |
|---|---|---|
| I=+1, YOU=+1 | SOMEONE=+1 | Own lexical component |
| BODY=+1 | SOMETHING=+1 | Body-denoting noun |
| ONE=+1, TWO=+1 | QUANTITY=+1 | Cardinal component; no magnitude inferred |
| MOVE=+1, DO=+1, CAUSE=+1 | HAPPEN=+1 | Own event component; no agent inferred |
| THEN, BEFORE, LONG_TIME nonzero; MOMENT=+1 | WHEN=+1 | Own temporal content |
| ABOVE, FAR, OUTSIDE, TOWARD nonzero; HERE, SIDE=+1 | WHERE=+1 | Own literal spatial content |

These eighteen relations are approved GSE representational conventions, not a claim that the NSM chart independently proves every table. They are stored as conditional compatibility relations with provenance and explicit scope. Their relational tables support constraint propagation in either direction; an unresolved value is not an asserted inverse fact. Direct hard evidence survives a locally contradicted conditional, with a named exception receipt. New typed specialization requires an independently justified distinction.

## Evidence-conditioned absence

Rohan's decision: evaluatives are assumed BIG=0 only conditional on there being no encoding information relevant to size; this is an iff eligibility condition, not an inference followed by contradiction fallback.

For an adjectival definition `d`, let `R_b(d)` mean that any admitted or potentially applicable encoding information is relevant to bank `b`. The evaluation default is licensed exactly when `GOOD(d)` is nonzero and `not R_BIG(d)`. The reciprocal size default is licensed when `BIG(d)` is nonzero and `not R_GOOD(d)`. The respective licensed conclusions are BIG=0 and GOOD=0. This specifies when these defaults supply zero; an independently evidenced zero can of course exist while relevant evidence exists.

Relevance includes explicit assertions of any sign (including zero), unresolved source evidence, candidate-linked evidence, and ordinary rule deductions that narrow the bank's domain. Unclassified evidence blocks the default. No model ruling is required merely to decide that an unresolved signal exists.

Implementation order:

1. Resolve source/anchor assertions and ordinary relations to a local fixed point.
2. Form the relevance set from declared observation relevance, assertion banks and narrowed ordinary domains.
3. Evaluate every absence guard against this same baseline. Defaults cannot authorize one another.
4. Admit only eligible defaults to further closure. Record ELIGIBLE or BLOCKED with witnesses.

`Relation.absent_evidence` makes the condition explicit. Direct low-level propagation skips an unevaluated absence guard. Build, model completion and replay share `resolve_dictionary`. A blocked default never enters contradiction handling. Explicit size and evaluation can coexist; the broad defaults do not forbid that combination.

The earlier two unconditional GOOD/BIG tables were the same exclusion relation with columns reversed. Those proposals are superseded by two separately conditioned defaults; they must not be admitted as unconditional exclusions.

## WANT polarity

The approved coordinate is exactly: −1 = NOT WANT, 0 = orthogonal to wanting, +1 = WANT. Zero does not mean weak desire or lack of evidence. This polarity concerns the component; sentence negation still obeys grammatical scope.

`LEXICON_APPROVED_ANCHORS_2026-10-29.json` anchors NOT WANT as an explicit authored definition and anchors WANT=+1 only on `wordnet:want:desire.v.01`, whose full native gloss denotes desire. It does not modify the noun “want” meaning deprivation or other senses. The desire gloss includes “strongly”; no arbitrary intensity is inferred and it is not declared a complete exact NSM-prime signature. The explicit THIS and NOT WANT definitions are linked to their chart units, with remaining cells unresolved.

## Ordinal stability

The source of authority is a defensible law, not the filename `primitives_v2`. Rohan's sentence architecture explicitly gives VERY one positive step and repeated VERY two steps, with EXTREMELY corresponding to two steps. The construction contract pins VERY=+1 and EXTREMELY=+2 and checks that the runtime registry agrees; disagreement fails as ORDINAL_REPRESENTATION_DRIFT.

The approved manifest applies this convention to exact existing definitions: `wordnet:very:very.r.01` (the intensifier) and `wordnet:extremely:extremely.r.02` (“to an extreme degree”). Both carry INTENSITY=+1, with per-component hierarchy 1 and 2 respectively. The sign remains balanced ternary; degree is separate metadata. Other VERY and EXTREMELY definitions do not inherit these assignments by spelling. This fills the previously missing link between the approved ordinal convention and actual constructed entries; their remaining banks are not presumed zero.

Both historical competing tables already occur in the first repository commit, and both have antecedents in the supplied project documents: `GSE_V2.md` gives VERY=1 and EXTREMELY=2, whereas `pronouns_numbers.md` gives the larger alternative scale. Their provenance is therefore not wholly unknown. The approved sentence-scale law determines the canonical convention used here. Other ordinal positions require explicit, justified definition-specific manifest input and a versioned migration where a consumer uses a competing scale; they are not automatically imported from either old table.

The old `scripts/encode_modifiers.py` writer selects the first matching spelling and writes an unused competing hierarchy table. Writes through it are disabled; its dry-run inspection remains read-only. Historical constants remain readable for diagnosis, not authoritative construction inputs.

The full GSE path already represents modifier and negation scope: sign ownership distinguishes “not very good” from “very not good,” and the expression layer distinguishes hierarchy-direction evidence from syntactic negation. It is incorrect to describe composition architecture as absent. The narrower audit finding is that repeated VERY is not normalized to the approved composed degree, and the final structural comparison can treat “very good” and “not very good” as equal despite their distinct sign evidence. Versioned per-component hierarchy also needs to reach the existing sentence consumer. These are consumer integration and output-fidelity repairs, not missing lexical coordinates or reasons to import a second parser wholesale.

## Construction and inference

The production entry point is `python -m gse.curation.cli.commands`. Construction loads local sources or strict typed evidence; establishes definitions and source links; validates competence/relevance; loads approved anchors, relations and per-component hierarchy; resolves ordinary structure and guarded absence; optionally completes a bounded residual; stores one atomic snapshot; and reports coverage/conflicts.

Hard source assertions and foundational constraints are inviolate. Approved ordinary conditional constraints can be locally excepted with receipts. Jointly contradictory conditional components are withdrawn together rather than selecting an arbitrary winner. Current closure is generalized arc consistency, not exhaustive global satisfiability. Counts and weighting never turn a candidate into an approved law.

The intended induction loop uses independent source evidence to propose mechanisms, retain counterexamples, identify justified typed guards, test specialized rules against independent anchors and the whole eligible population, and version admitted rules. Significance orders investigations; it does not become a truth gate. GSE already has recursive genus/differentia construction, aggregation, lexical pattern networks, and `MerkleLearningBridge.train_from_tree`, called by the public `GSEPipeline.train_from_corpus` method. Document significance and coherence also already serve interpretation and repair. Their existence must be credited; their outputs and contracts must not be conflated with admission of a causal lexical rule.

The inspected legacy aggregation/decomposition paths drop explicit zeros, select or combine conflicting signs, or resolve by the first lemma row. They cannot be substituted unchanged for definition identity, retained conflict, and warranted-zero semantics. The remaining construction work is to adapt usable machinery and supply the causal justification, typed guards, counterexample receipts and versioned admission boundary. The inspected candidate-discovery and local-exception paths do not yet establish that full process. This is a specific contract gap, not a project-wide claim that lexical learning or significance machinery is missing.

## Bounded residual model

Only after symbolic closure may an explicitly selected local model receive one unresolved bank. Input is typed JSON containing the exact definition, source observations, known assignments and surviving values; output is constrained to that bank's surviving ternary values or null. There is no English task prompt, whole-vector fallback, automatic model selection or automatic unlimited budget.

The ruling cannot change known cells or introduce new contradiction exceptions. It is rechecked under the same evidence guards and propagated before acceptance. Abstention, transport failure, malformed data and contradictory output remain distinct outcomes. Model-generated values cannot independently validate their own generating rules. The large current residual must not be sent wholesale to a model merely because the boundary exists.

## Storage, runtime and verification

The versioned SQLite snapshot separates definitions, published assignments, unresolved domains, source observations, assertions, proof traces, hierarchy, normalized diagnostics, candidate evidence and representation metadata. Large evidence sets are stored as rows rather than one giant JSON value. Rebuilds are transactional; a failed rebuild preserves the earlier snapshot.

Runtime selects explicit definition identities or reports ambiguity. It does not select the first spelling match or merge equal vectors. Published encoding uses warranted values; explicit zero remains in evidence even though it adds no vector signal. Conflicted entries abstain. Exact definition encoding preserves per-component hierarchy signs.

Validation replays the snapshot read-only, checking source provenance, metadata, domains, assignments, guard decisions and model receipts. Semantic evaluation separately uses independently supplied labels and reports correct/abstained/conflicted/wrong/not-found by bank, lexical type and source cohort. Replay success is not semantic gold. Reports state metadata reconstruction limits.

The previous 155,111-definition baseline was replay-validated before these decisions. Its reports remain historical evidence; updated artifacts must be rebuilt and replayed under this convention version before reporting current measurements. The active runtime lexicon is not silently replaced by a sparse construction result.

## Implementation status and completion criteria

This ledger distinguishes a capability already present elsewhere in GSE from an unverified connection to the new dictionary. The 2026-10-29 whole-project audit corrects the earlier ledger, which incorrectly elevated several builder-local omissions into missing architecture. Historical documents supply design context; code and executable checks establish current implementation.

| Area | Status |
|---|---|
| Definition identity, strict evidence, domains, storage, runtime selection | Implemented |
| Eighteen approved category relations | Implemented in default construction |
| Evidence-conditioned evaluation/size defaults | Implemented with typed relevance and replay |
| WANT polarity; explicit NOT WANT and THIS lexical anchors | Implemented contract and manifest |
| Stable supported ordinal laws and competing writer prevention | Implemented; other existing scales require explicit reconciliation |
| Complete reviewed, definition-scoped prime signatures | Not established by the inspected one-hot Tier-0 catalog; partial anchors are not complete signatures |
| Native-record relevance | Existing source interpretation must feed the new guards; unrestricted or unresolved records remain conservative |
| Lexical discovery and significance machinery | Existing; adaptation and causal rule admission remain incomplete in the new construction path |
| Grammatical roles, THIS reference and possession | Existing in the active GSE path; no new static-mask prerequisite |
| Modifier and negation scope | Existing; composed-degree and final-output fidelity have specific unresolved defects |
| Existing evaluation resources | Present; their identity, scale and independence must match the claim being tested |
| Independent ternary labels and readiness to replace active lexicon | Not established for this new artifact by replay or existing similarity labels alone |

A complete full-corpus build means every requested definition and source record has been processed, every warranted assignment stored, and every unresolved/conflicted outcome explicitly accounted for. It does not mean every cell has become known. Replay verifies that artifact's construction contract. Readiness to replace the active lexicon additionally requires compatible behavior through current consumers and independent semantic evaluation appropriate to the new representation. Neither a populated registry nor passing unit tests substitutes for these distinct requirements.

The specific sentence parsing and modifier-output defects above are existing full-project issues. They must not be presented as missing lexicon construction subsystems or used to justify duplicating GSE's grammar, reference, or composition layers.

### Whole-project audit sources

The audit read `sentence_architecture.md`, `complex_sentence_architecture.md`, `pronouns_numbers.md`, `GSE_HDC_architecture.md`, `GSE_V2.md`, `geometric_frame_semantics_architecture_v2.md`, and the relevant complete method sections of `GSE_PAPER_EXPERIMENTS/GSE_PAPER_SKELETON.md` in the supplied Core Documents/GSE directory. The paper method explicitly separates vector similarity from logical structure and assigns roles dynamically. The learning summary and Wiktionary resolver document provide historical construction context, not proof that their old outputs satisfy the current contract.

Current implementation evidence includes the active encoder/document intake, symbolic expression/sign/reference machinery, source scope and native adapters, Tier-0 dispatch, the definition linker, constraint aggregation and its daemon consumer, and the Merkle learning bridge. In particular, old word/POS-keyed artifacts and association-driven outputs are reusable evidence; their size or presence does not establish definition-scoped correctness. `docs/THEORY.md` remains excluded.

## Historical verification receipt — accepted convention build

The production CLI rebuilt the 67,111-spelling source cohort into `data/lexicon_builder/2026-10-29/accepted.db`, retaining the preceding baseline separately. The accepted snapshot has 155,113 definitions (including the two authored definitions), 3,208,354 source observations, 23 approved relations, and three explicit anchor definitions. It has 215,855 assigned cells, including 106,606 explicit zeros, and 8,470,473 unresolved cells. All entries remain PARTIAL; no model calls were made.

The read-only CLI replay checked all 155,113 definitions: REPLAY_VALIDATED, zero mismatches, representation contract VERIFIED. Direct comparison against the baseline found zero changed or lost known values and 1,942 new assignments: HAPPEN=+1 on 1,939 definitions, SOMETHING=+1 on THIS, WANT=−1 on NOT WANT, and WANT=+1 on the explicitly selected desire sense.

The native corpus did not trigger the new absence defaults: its 48,892 adjective guard checks were blocked by relevance (including unclassified evidence), and the remaining 261,334 guard checks were outside adjective scope. Focused integration tests cover eligible defaults, unresolved relevant evidence, both known nonzero components, candidate links, altered saved evidence, and model immutability. This distinction prevents a no-conflict corpus result from being mislabeled as validation of the defaults' linguistic coverage.

`scripts/ci_local.sh` completed successfully after these implementation changes. Scoped type checking of the construction package and retired modifier writer also passed; the repository-wide type pass remains advisory. Machine-readable build, replay and comparison receipts are saved in `docs/readings/2026-10-29-lexicon-coherence/accepted-*.json`. These are structural verification results; independent semantic gold remains NOT_CHECKED.

## Verification receipt — full-cohort rebuild after the project audit

The production CLI rebuilt `data/lexicon_builder/2026-10-29/corpus.db` from the established 67,111-spelling cohort and all eleven available local source adapters. There are 155,113 definition entries and 3,208,354 native observations. Every requested spelling is accounted for: 65,967 have identified definitions and 1,144 carry an explicit `NO_IDENTIFIED_DEFINITION` diagnostic. The two separately authored spellings, THIS and NOT WANT, remain outside that requested list. This is full coverage of the requested cohort, not a claim to have enumerated every word in every local graph or dictionary.

The snapshot contains 215,857 assigned cells, including 106,606 explicit zeros, with 8,470,471 unresolved cells. All definitions remain PARTIAL. There are no conflicted cells and no model calls. Compared with the preceding accepted artifact, no definition identity or known assignment was lost, and no known value changed. The only new assigned cells are the two exact INTENSITY anchors; their hierarchy levels are 1 and 2. The collector classified 114,316 in-cohort SentiWordNet observations. Unrestricted WordNet evidence still blocks all 48,892 adjective absence-guard checks; a relevance annotation on one source cannot suppress another source's unresolved information.

Full read-only replay checked all 155,113 entries with zero mismatches and verified the representation contract. SQLite integrity checking returned `ok`, and all published coordinates are balanced ternary integers. Replay remains a local arc-consistency check; it is not a global satisfiability proof or independent semantic evaluation. The machine receipts preserve these qualifications rather than replacing them with a single success score.

The public runtime audit verifies the restored causal, comparison and restriction operations, existing coordination/control/temporal structure and demonstrative type assertion, signed WANT anchors, THIS objectness without HAVE, and the distinct nonzero degree vectors. Its finite structural probes use the empty genealogy provider, so they do not establish world-grounded correctness. At this measurement, “not very good” still receives the wrong scope through ambiguous ordinary lexical lookup even though its explicit intensity definition encodes correctly. This migration failure is distinct from the older full-path degree-emission defect described above; the active lexicon has not been replaced.

The independent-resource readiness audit reads SimLex-999, WordSim-353 and 187 adjective intensity scales with all 75 tied rank groups preserved. These are useful human-label resources. Their scores and ranks are not bank trits, and a unique spelling/POS candidate is not proof of the annotation's intended definition. The audit therefore records `NOT_BANK_GOLD` and `NOT_EVALUATED` for bank-semantic correctness. Complete sense-linked prime signatures and an appropriate independent bank evaluation remain unestablished; no missing labels or unknown coordinates have been manufactured to close that gap.

The final repository gate completed successfully: 5,565 tests passed, 55 were skipped, and 16 were expected failures, with no failures or collection errors. The gate includes pinned lint and format checks; scoped type checking of changed production code and audit scripts also passed. A collection-order dependency exposed by the real `uv run pytest` entry point was fixed in `tests/conftest.py`, so operational-script imports no longer rely on another test having already placed the repository root on the import path.

### Reproduction and receipts

Run from the repository root:

```bash
.venv/bin/python -m gse.curation.cli.commands \
  --lexicon-db data/lexicon_builder/2026-10-29/corpus.db build \
  --words-file data/lexicon_builder/2026-10-29/words.txt \
  --rules docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json \
  --report docs/readings/2026-10-29-lexicon-coherence/corpus-build-report.json
.venv/bin/python -m gse.curation.cli.commands \
  --lexicon-db data/lexicon_builder/2026-10-29/corpus.db validate
.venv/bin/python scripts/audit_lexicon_runtime.py \
  --lexicon-db data/lexicon_builder/2026-10-29/corpus.db \
  --report docs/readings/2026-10-29-lexicon-coherence/runtime-corpus-audit.json
.venv/bin/python scripts/audit_lexicon_evaluation_readiness.py \
  --lexicon-db data/lexicon_builder/2026-10-29/corpus.db \
  --output docs/readings/2026-10-29-lexicon-coherence/evaluation-readiness.json
bash scripts/ci_local.sh
```

`corpus-verification-receipt.json` indexes `corpus-build-report.json`, `corpus-validation-report.json`, `corpus-comparison.json`, `runtime-corpus-audit.json` and `evaluation-readiness.json`, saved together under `docs/readings/2026-10-29-lexicon-coherence/`. The comparison receipt includes hashes of the exact word list and approved manifest. The build database, JUnit results and detailed execution logs remain local under `data/lexicon_builder/2026-10-29/`.
