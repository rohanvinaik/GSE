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

At the interface, each lexical definition has a set of permitted grammatical roles. A present but uninstantiated grammatical dimension is distinct from a dimension outside that set. Grammar narrows the permitted bindings to compatible entities; ambiguity remains unresolved. Set membership, argument ownership, and operator scope operate on structured identities, not vector equality. Two sentences can have similar lexical geometry and different comparison truth conditions.

The construction artifact must eventually persist this capability set and the runtime must consume it without dropping its uninstantiated members. Current `sentence_primitive_values` storage exists but the new construction writer does not yet populate it; existing lookup filters zero-valued rows. Native parsing currently misclassifies determiner THIS in “this dog” as a pronoun, and generic reference binders do not yet enforce dedicated demonstrative constraints. These are identified implementation obligations, not evidence for changing the lexical basis.

FOR SOME TIME likewise must not be forced into a positive or negative LONG_TIME value merely to close a vector. Temporal lexical content and a duration/interval operation belong at their appropriate scales; duration magnitude remains unspecified unless warranted. Its full construction-to-sentence integration remains open.

## Source evidence and competence

Sources enter through the existing parser/integrator architecture. A source exposes native records and justified `to_primitives` projections; its assertion scope is explicit. Native records retain full available content and exact identifiers. WordNet currently supplies the definition spine. Exact VerbNet sense links can support event assertions; unresolved ratings and frame links remain evidence.

Every projection must distinguish the definition's own content from participants, embedded evaluations, examples, world facts, and associations. A verb taking a body argument does not thereby denote a body. World facts remain on the separate sparse-wiki leg. DeepNSM remains silver material for anchors/evaluation only and is not baked into the shipped lexicon.

An assertion requires an exact definition link and source competence. An unresolved candidate link cannot assert a sign, but it can prevent an absence claim while its relevant evidence remains unresolved. Source disagreement is retained. A large, optionally Zipf-weighted population tests proposed causal structure; its frequency does not establish that structure's truth.

### Relevance is not a value

An observation may carry `features.bank_relevance = {code: CLASSIFIED, banks: [...], provenance: [...]}`. This annotation names canonical coordinates the record can inform, without assigning their values. Empty banks means an explicitly justified classification as irrelevant to word-coordinate assignment. Missing classification means UNCLASSIFIED, conservatively potentially relevant to all coordinates. Malformed annotations fail ingestion/replay.

Source competence is an upper bound on what may be asserted, not a complete relevance classification for an individual record. The current native adapters do not yet provide complete reviewed relevance annotations; unclassified records therefore block absence defaults. This conservative state is visible and must be improved through typed source interpretation, not by assuming every unparsed record irrelevant.

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

Both historical competing tables already occur in the first repository commit. Their pre-repository origins cannot be recovered from this Git history. The exploratory quantity ordering does not justify declaring every historical rank authoritative. Other ordinal positions therefore require explicit justified definition-specific manifest input; they are not automatically imported from either old table.

The old `scripts/encode_modifiers.py` writer selects the first matching spelling and writes an unused competing hierarchy table. Writes through it are disabled; its dry-run inspection remains read-only. Historical constants remain readable for diagnosis, not authoritative construction inputs.

The active encoder's repeated-VERY and negation-scope composition still do not implement the sentence document fully, and versioned per-component hierarchy does not yet enter its legacy modifier-transfer branch. A separate unused parser already accumulates modifiers but uses different vector operations; substituting it blindly would alter representation. These consumer repairs remain explicit work. Stable ranks alone do not claim to fix sentence composition.

## Construction and inference

The production entry point is `python -m gse.curation.cli.commands`. Construction loads local sources or strict typed evidence; establishes definitions and source links; validates competence/relevance; loads approved anchors, relations and per-component hierarchy; resolves ordinary structure and guarded absence; optionally completes a bounded residual; stores one atomic snapshot; and reports coverage/conflicts.

Hard source assertions and foundational constraints are inviolate. Approved ordinary conditional constraints can be locally excepted with receipts. Jointly contradictory conditional components are withdrawn together rather than selecting an arbitrary winner. Current closure is generalized arc consistency, not exhaustive global satisfiability. Counts and weighting never turn a candidate into an approved law.

The intended induction loop uses independent source evidence to propose mechanisms, retain counterexamples, identify justified typed guards, test specialized rules against independent anchors and the whole eligible population, and version admitted rules. Significance orders investigations; it does not become a truth gate. The current candidate-discovery and local-exception mechanisms do not yet implement the full induction/specialization/promotion loop.

## Bounded residual model

Only after symbolic closure may an explicitly selected local model receive one unresolved bank. Input is typed JSON containing the exact definition, source observations, known assignments and surviving values; output is constrained to that bank's surviving ternary values or null. There is no English task prompt, whole-vector fallback, automatic model selection or automatic unlimited budget.

The ruling cannot change known cells or introduce new contradiction exceptions. It is rechecked under the same evidence guards and propagated before acceptance. Abstention, transport failure, malformed data and contradictory output remain distinct outcomes. Model-generated values cannot independently validate their own generating rules. The large current residual must not be sent wholesale to a model merely because the boundary exists.

## Storage, runtime and verification

The versioned SQLite snapshot separates definitions, published assignments, unresolved domains, source observations, assertions, proof traces, hierarchy, normalized diagnostics, candidate evidence and representation metadata. Large evidence sets are stored as rows rather than one giant JSON value. Rebuilds are transactional; a failed rebuild preserves the earlier snapshot.

Runtime selects explicit definition identities or reports ambiguity. It does not select the first spelling match or merge equal vectors. Published encoding uses warranted values; explicit zero remains in evidence even though it adds no vector signal. Conflicted entries abstain. Exact definition encoding preserves per-component hierarchy signs.

Validation replays the snapshot read-only, checking source provenance, metadata, domains, assignments, guard decisions and model receipts. Semantic evaluation separately uses independently supplied labels and reports correct/abstained/conflicted/wrong/not-found by bank, lexical type and source cohort. Replay success is not semantic gold. Reports state metadata reconstruction limits.

The previous 155,111-definition baseline was replay-validated before these decisions. Its reports remain historical evidence; updated artifacts must be rebuilt and replayed under this convention version before reporting current measurements. The active runtime lexicon is not silently replaced by a sparse construction result.

## Implementation status and completion criteria

| Area | Status |
|---|---|
| Definition identity, strict evidence, domains, storage, runtime selection | Implemented |
| Eighteen approved category relations | Implemented in default construction |
| Evidence-conditioned evaluation/size defaults | Implemented with typed relevance and replay |
| WANT polarity; explicit NOT WANT and THIS lexical anchors | Implemented contract and manifest |
| Stable supported ordinal laws and competing writer prevention | Implemented; broader ordinal justification remains |
| Complete reviewed prime signatures and native relevance classification | Incomplete |
| Full significance-guided induction, specialization and promotion | Incomplete |
| Grammatical capability persistence/consumption, demonstrative reference constraints | Incomplete |
| Active modifier composition consistent with ordinal/scope laws | Incomplete |
| Independent semantic gold and readiness to replace active lexicon | Not established |

Completion requires these remaining consumers and semantic foundations to be implemented and exercised through the production path, followed by whole-corpus replay and independent semantic evaluation. Neither passing unit tests nor a fully populated registry substitutes for those requirements.

## Verification receipt — accepted convention build

The production CLI rebuilt the 67,111-spelling source cohort into `data/lexicon_builder/2026-10-29/accepted.db`, retaining the preceding baseline separately. The accepted snapshot has 155,113 definitions (including the two authored definitions), 3,208,354 source observations, 23 approved relations, and three explicit anchor definitions. It has 215,855 assigned cells, including 106,606 explicit zeros, and 8,470,473 unresolved cells. All entries remain PARTIAL; no model calls were made.

The read-only CLI replay checked all 155,113 definitions: REPLAY_VALIDATED, zero mismatches, representation contract VERIFIED. Direct comparison against the baseline found zero changed or lost known values and 1,942 new assignments: HAPPEN=+1 on 1,939 definitions, SOMETHING=+1 on THIS, WANT=−1 on NOT WANT, and WANT=+1 on the explicitly selected desire sense.

The native corpus did not trigger the new absence defaults: its 48,892 adjective guard checks were blocked by relevance (including unclassified evidence), and the remaining 261,334 guard checks were outside adjective scope. Focused integration tests cover eligible defaults, unresolved relevant evidence, both known nonzero components, candidate links, altered saved evidence, and model immutability. This distinction prevents a no-conflict corpus result from being mislabeled as validation of the defaults' linguistic coverage.

`scripts/ci_local.sh` completed successfully after these implementation changes. Scoped type checking of the construction package and retired modifier writer also passed; the repository-wide type pass remains advisory. Machine-readable build, replay and comparison receipts are saved in `docs/readings/2026-10-29-lexicon-coherence/accepted-*.json`. These are structural verification results; independent semantic gold remains NOT_CHECKED.
