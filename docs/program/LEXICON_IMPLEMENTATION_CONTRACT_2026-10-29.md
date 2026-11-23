> Historical pre-decision record. Rohan has since accepted and refined the conventions. The current formal design and implementation status are in [LEXICON_CONSTRUCTION_DESIGN.md](LEXICON_CONSTRUCTION_DESIGN.md); the original unapproved proposal JSON and its audit remain historical evidence.

# Confirmed lexicon implementation contract — 2026-10-29

Authority: Rohan's complete LEXICON_FOUNDER_WORDS_2026-10-24.md and his current conversation. His latest authorization: “Otherwise, yes, I agree, confirm the design, then fire it off with as many sub-agents to plow through the design as efficiently and effectively as we can”. This contract makes the approved design executable; it is not a replacement for his words.

## Confirmed semantics

One dictionary entry per definition. Multiple source records are evidence, not automatically new entries. Different lexical objects may share semantic coordinates. Dictionary identity never comes from vector equality. Existing incompatible code must be upgraded rather than preserved.

Every semantic coordinate is balanced ternary. Zero is explicit absence; None/missing is silence. Unresolved cells retain a nonempty admissible set until evidence/relations identify a value. Conflicting evidence is reported, never voted into a winner or converted to zero. NUMBER is hierarchy metadata on a semantic component, not an ordinary lexical coordinate. Intensity metadata never changes base signs or presence.

Source projection is typed and scoped. Embedded evaluations, participants, world facts and association ratings are retained as evidence but are not automatically own-word primitive assignments. Naming nouns have zero own-word evaluation under the approved convention; embedded BAD is not lost from the source record. Non-substantive modifiers do not acquire objecthood from argument slots. No source may claim banks outside its declared competence.

Foundational relations/anchor assignments are explicit versioned inputs with provenance. Approved conditional relations narrow possibilities and carry their justification and scope. Broad source coherence proposes rules; a high frequency or compatibility score does not establish a causal rule. No rule's derived outputs validate itself. Candidate rules do not fire. Silence is never a counterexample or confirmation. Report identified/abstained/conflicted/wrong where gold exists, per class and source, plus weighted and unweighted coverage.

Model: only after symbolic closure, one specifically unresolved bank per call. Typed JSON data, no English task prompt, constrained JSON generation. Known assignments cannot be returned/changed. Only surviving ternary values or explicit abstention. Validate against rules and rerun symbolic closure after each accepted ruling. Errors, missing output and malformed output never become zero. Source assertions and model assertions retain separate provenance.

## Composition and file ownership

Use GSE/curation/lexicon_builder/ as the new construction path, integrated into the actual curation CLI by the lead. Existing weighted and full-vector builder paths must not remain the default CLI build. No new dependencies. Standard library core; existing source and vector machinery reused at typed boundaries.

constraint_engine agent owns engine.py, discovery.py, and tests/test_lexicon_builder_engine.py plus tests/test_lexicon_builder_discovery.py.
source_evidence agent owns evidence.py and tests/test_lexicon_builder_evidence.py.
typed_residual agent owns residual.py and tests/test_lexicon_builder_residual.py.
Lead owns __init__.py, pipeline.py, storage.py, foundation.py, CLI integration, runtime integration, cross-component tests and documentation. No worker edits another owner's files. No branches/worktrees. No worker commits. Existing unrelated modifications are preserved.

## Shared engine interface

Implement frozen dataclasses in engine.py:
Assertion(bank: str, value: int, source: str, record_id: str, family: str, scope: str = "lexical"). Only exact ints -1/0/1 (bool rejected). scope lexical means own-word warrant; any other scope is retained elsewhere but cannot assert a coordinate.
Relation(rule_id: str, banks: tuple[str,...], allowed_rows: tuple[tuple[int,...],...], provenance: tuple[str,...], authority: str = "conditional", approved: bool = False, guards: tuple[tuple[str,str],...] = ()). approved foundational/conditional relations only; guard keys match context values exactly. Empty allowed rows expresses an impossible relation, not silence. Require distinct bank names and correctly typed rows. Provenance mandatory for firing.
Resolution(code: str, domains: dict[str,frozenset[int]], assignments: dict[str,int], conflicts: tuple[dict,...], trace: tuple[dict,...]). Codes RESOLVED, PARTIAL, CONFLICT. Singleton domains yield assignments, but no commit/model request on CONFLICT. Trace records justified removals/assignments with source/rule identifiers; no confidence vote.
propagate(banks: tuple[str,...], assertions: tuple[Assertion,...], relations: tuple[Relation,...], context: dict[str,str] | None = None) -> Resolution. Initialize {-1,0,1}, intersect assertions, run relational generalized arc consistency to fixed point with deterministic ordering. Keep zero and silence distinct. Any empty domain -> CONFLICT. No mutating inputs. Unknown bank/invalid input -> explicit ValueError before doing work. Higher-order rows support conjunctive and inverse propagation; no automatic unsafe contraposition of defeasible implications.

Discovery is a diagnostic of typed observations, not a truth gate: collect candidate implications/counterexamples/support/unknown by source family and optional nonnegative finite word weights. Only source-backed observations, not derivations/model outputs, validate candidates. No automatic approval based on count or threshold. Return candidate relations approved=False and explicit eligibility/support records. Keep inconsistent source observations visible rather than vote.

## Evidence interface

Implement frozen Definition(entry_id: str, lemma: str, pos: str, definition: str, source_ids: tuple[str,...] = ()) and Observation(entry_id: str | None, source: str, record_id: str, family: str, features: dict, scope: str, candidate_entry_ids: tuple[str,...] = ()).
EvidenceBundle(definitions: tuple[Definition,...], observations: tuple[Observation,...], assertions: tuple[Assertion,...], unresolved: tuple[dict,...]).
collect_evidence(parsers: dict[str,object], words: tuple[str,...] | None = None) -> EvidenceBundle. Receives already-loaded adapters; no downloads, models or writes. Preserve native records and full available content. Use WordNet dictionary definitions as the initial explicit identity spine where supplied; source-native exact identifiers may link evidence. Syntactic classes/rolesets cannot themselves create duplicate definitions. Broad word ratings and ambiguous linkage stay typed observations, never copied across all definitions as facts. Report words without identified definitions separately. Map only native per-definition structural evidence using already-established existing adapter taxonomy logic and scope; no majority, averaged sentiment as definition, or argument->object projection. Preserve original evidence as well as any warranted projection. Source IDs must be stable, not dict iteration indexes. Use canonical positive-pole coordinate names for actual assertions; exclude NUMBER and hierarchy markers from coordinate assertions.
Provide collect_native_observations or equivalent small helpers as needed; root calls collect_evidence and consumes bundle, no parallel builder.

## Residual interface

BankRequest frozen dataclass carries entry_id, bank, allowed_values, known, observations, definition and request_id (deterministic hash of typed payload). build_request(entry_id: str, bank: str, resolution: Resolution, observations: tuple[dict,...], *, definition: Definition) -> BankRequest. The matching definition's ID, lemma, POS and full definition are mandatory typed context, even when no observations exist. Reject conflict/already-assigned/unknown bank. Payload is data only, with output exactly one named bank; output JSON schema admits only surviving ints plus null for abstention, additionalProperties=False. Null is never zero.
Completion(code: str, assertion: Assertion | None, resolution: Resolution | None, details: dict). Codes ASSIGNED, ABSTAINED, INVALID_OUTPUT, TRANSPORT_ERROR, CONTRADICTION, STALE_REQUEST.
complete_bank(request: BankRequest, banks: tuple[str,...], assertions: tuple[Assertion,...], relations: tuple[Relation,...], transport, context: dict[str,str] | None = None) -> Completion. Recompute current resolution/request admissibility before invoking, strictly parse response, reject extra fields/wrong types/known-cell rewrites/nonadmissible values, repropagate with model assertion; conflict -> CONTRADICTION and original state unchanged. Do not catch programmer bugs as model zero. Transport returns raw JSON string; exceptions -> TRANSPORT_ERROR.
OllamaTransport(model: str, base_url: str = "http://localhost:11434", timeout: float = 60) callable takes typed payload and JSON schema. Use JSON encoded payload as prompt, schema as format, no natural-language instructions. Existing requests or urllib allowed, schema enforced during generation, bounded timeout; no external paid calls. No automatic model choice or whole-word fallback.

## Lead integration and verification

Persist definitions, explicit coordinate assignments, residual domains, proof/evidence and NUMBER hierarchy separately. Version the new storage so empty old zero-filled tables cannot masquerade as the new contract. Published encoding contains warranted assignments, not guessed completion. Runtime handles ambiguity explicitly instead of first row. Source links do not hash vector equality into identity.

Build CLI invokes collect_evidence -> approved foundations/relations -> propagate -> optional explicitly configured typed residual -> storage/export. Report actual source coverage, unresolved definitions/cells and conflicts, not invented completeness. Reuse existing integrator source loading only after verifying it performs no unintended downloads. Run adversarial unit tests and an end-to-end CLI build/lookup/export using temporary databases; then real local corpus pass with diagnostics before any replacing of the active lexicon. Never silently publish a conflicted entry. Validate the whole eligible corpus with named outcomes. Full foundational coverage is a measured deliverable, not inferred from the existence of a registry.

## Implemented composition

The production path is `python -m GSE.curation.cli.commands`. `build` uses the new package, and `init` creates its versioned empty store. The old whole-word builders' five executable entry points now stop with `SUPERSEDED_LEXICON_BUILDER`; their imported legacy APIs remain for existing consumers and tests. The default active runtime dictionary is not switched to this sparse construction output.

`engine.propagate` is the hard relational closure. `resolution.resolve_dictionary` composes it with local exceptions: hard source/anchor assertions and foundational relations survive; an individually contradicted conditional is excepted locally. Jointly conflicting conditional components are withdrawn together, including connectivity through foundational rules. This is conservative and independent of rule iteration order. A harmless conditional sharing that component may also be withdrawn; the receipt names all affected rules. This is not a substitute for significance-guided rule induction or a proof of global satisfiability.

The model boundary uses the same resolver. It rejects a ruling that changes a previously known value, removes a known value, or introduces a new conditional exception. No model was used to populate the corpus build. The live local transport still needs an explicitly named model and positive call budget.

Source identity comes from native dictionary keys. WordNet supplies the initial definitions. VerbNet supplies exact unmarked WordNet sense keys, with native member/class/frame evidence preserved; positive event motion and causation predicates must occur in every applicable frame before they produce MOVE/CAUSE. Other ratings, frame descriptions, and ambiguous links remain observations. Full FrameNet descriptions, PropBank role/link information, and Lancaster raw missingness are retained. Known source competence is checked both at typed ingestion and replay. Record IDs are globally namespaced; collisions fail before output creation.

Storage separates published assignments, unresolved domains, hard assertions, source observations, rule receipts, per-component hierarchy, source-link diagnostics, and candidate evidence. Large corpus diagnostics and candidate evidence are rows, not one enormous JSON field. An unsuccessful rebuild rolls back the snapshot. A successful rebuild removes old entries. `0` is persisted and retained in runtime evidence even though it contributes no HDC signal. Runtime selection never picks an arbitrary definition by row order; explicit definition encoding and morphology respect all known values and remaining domains.

`validation.validate_build` checks a read-only snapshot, reconstructs provenance and model requests, and replays definitions. It also checks normalized diagnostics/candidate evidence and catalog metadata. Replay is structural consistency, not semantic gold. Metadata verification explicitly identifies unpersisted definition source-ID order and unverified discovery populations/weights. `evaluation.evaluate_build` accepts separately supplied gold and reports IDENTIFIED_CORRECT, ABSTAINED, CONFLICT, WRONG and NOT_FOUND per bank, POS and overlapping source cohort. No aggregate accuracy claim substitutes for those outcomes.

## Running it

From `/Users/rohanvinaik/Projects/GSE`, with the project's environment:

```sh
.venv/bin/python -m GSE.curation.cli.commands --lexicon-db data/lexicon_builder/2026-10-29/lexicon.db build --words-file data/lexicon_builder/2026-10-29/words.txt --report data/lexicon_builder/2026-10-29/build-report.json
.venv/bin/python -m GSE.curation.cli.commands --lexicon-db data/lexicon_builder/2026-10-29/lexicon.db validate
.venv/bin/python -m GSE.curation.cli.commands --lexicon-db data/lexicon_builder/2026-10-29/lexicon.db lookup dog
.venv/bin/python -m GSE.curation.cli.commands --lexicon-db data/lexicon_builder/2026-10-29/lexicon.db catalog
```

`build --evidence FILE` consumes `GSE.lexicon-evidence/1` instead of loading native sources. `--rules FILE` consumes `GSE.lexicon-rules/1`: relations, exact-entry anchors, per-bank hierarchy, explicitly authored missing definitions, and explicit `prime_entries` bindings. Unknown fields, duplicate JSON keys, malformed provenance, boolean trits and invalid hierarchy levels fail. Source silence is never defaulted to zero. `--weights FILE` supplies nonnegative frequency weights keyed by definition ID; `--discover` records unapproved implication diagnostics. Neither option approves rules.

`catalog --inventory` displays the saved primary chart independently of a build. `evaluate --gold FILE --report FILE` evaluates supplied `GSE.lexicon-gold/1` records `{entry_id, bank, expected}`; optional weights must cover every supplied record. `export --output FILE` preserves all definition identities, assignments and residual state. Read commands refuse missing database paths without creating files.

Programmatic explicit runtime selection is `GSEEncoder.lookup_definition(entry_id)` and `GSEEncoder.encode_definition(entry_id)`. Ordinary ambiguous lookup abstains. Hierarchy metadata is encoded on each explicitly named component using the existing hierarchy machinery, preserving base sign and presence.

## Semantic readiness and review boundary

The runtime registry has 73 labels including NUMBER; the curation registry has 72. Collapsing 14 bipolar pairs gives 58 coordinates including two hierarchy markers. The new word-value domain has 56 ordinary coordinates; hierarchy markers and NUMBER are metadata. This is a computed reconciliation of the existing registries, not a new prime count.

The primary NSM v20 catalog contains 65 units and their complete saved combinatorial frames. Those frames are not automatically own-word bank assignments. The build reports explicit prime-definition bindings and anchor closure separately. The admitted default currently contains three founder projection relations, conservative WordNet projections, and the exact VerbNet projections described above. It does not yet contain the complete reviewed prime signatures or a complete significance-driven cross-corpus promotion loop. It must not be presented as the finished semantic foundation or as having reduced the residual to a few model calls per word.

Rohan explicitly requested proposed GSE conventions for review on 2026-10-29. They are in `LEXICON_PROJECTION_PROPOSALS_2026-10-29.json` and explained in `LEXICON_PROJECTION_REVIEW_2026-10-29.md`. Their format is deliberately distinct from an executable rules manifest and every candidate remains unapproved. Corpus effect audits provisionally apply them only in memory; lack of exceptions does not establish correctness, particularly when a proposed antecedent has no source coverage.

Remaining semantic work is concrete: review these conventions, identify the prime definitions, author their complete justified signatures and scoped rules, validate against independent labels and source counterexamples, then expand construction. GSE extensions and adaptations remain identified rather than mislabeled as canonical NSM. DeepNSM is not baked into the shipped lexicon. The active lexicon must be replaced only after that semantic review and evaluation establish a better representation.
