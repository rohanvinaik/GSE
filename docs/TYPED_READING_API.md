# Complete document readings

The reading substrate exposes local Python records under `gse.intake/1` and
profiles under `gse.profile/2`. These records support the accepted
`preserve-typed-prose-readings` change. The voice transport owner serializes
live traces and trees into the separate `voice.reading/1` contract.

## Source units and intake

`gse.discourse.split_paragraphs(text)` preserves internal paragraph whitespace.
`document_sentences(text)` collapses wrapped prose for the bounded sentence
splitter and returns `SourceSentence(id, text, paragraph_id)` records. Exact
original offsets and source maps remain the source-file owner's responsibility.
`split_sentences` retains its existing `. ! ?` followed by whitespace policy.

`gse.discourse.speech.encode_document_utterance_events(enc, sentences,
deadline=None)` accepts complete ordered source records (`{"id": ..., "text":
...}`), `SourceSentence` objects, `(id, text)` pairs, or legacy strings. Explicit
IDs survive unchanged; legacy strings receive positional `s0`, `s1`, … IDs.
Malformed or duplicate IDs are refused before a manifest is emitted.

The iterator performs document attribution once, then yields:

1. A manifest listing every source sentence's expected utterance IDs and each
   utterance's content, ordinal, speaker, addressee and quoted status. An
   attribution-only source sentence can explicitly have no expected utterance.
2. One outcome for every expected utterance, retaining those identities with
   `state=read|unread`, trace/tree, structural evidence, or a named error.
3. An end record declaring `complete|deadline` and expected/read/failed counts.

Errors distinguish `encode_error`, `construction_error`, `evaluation_error`,
`deixis_error`, and `deadline`. A deadline is an absolute `time.monotonic()` value
checked before starting each synchronous encode. It cannot interrupt a running
encoder. Remaining expected outcomes are unread with their original IDs.

`gse.symbolic.resolve_with_sources(expression)` returns `source` and `bound`
expressions after one shared refinement. `resolve(expression)` retains the same
bound result. The source expression precedes within-sentence pronoun binding.
Intake evaluates it as a separate `source_tree` with `source_origins` availability;
an auxiliary source evaluation failure leaves a successful primary tree read.

`encode_document_utterances_traced` deliberately projects only successful
`(trace, tree, utterance)` triples. `encode_document_utterances` and
`encode_utterances` project those successes to trees. These legacy wrappers omit
failure records; auditable consumers must retain the event stream.

## Shared document context and person evidence

`MultiScaleDoc` composes the event iterator, existing `resolve_document`,
`read_fold`, and `NarrativeGraph.from_document`. `sentence_trees` and
`utterance_outcomes` retain the sentence evidence. `tree_sources` explicitly maps
each successful tree index to its source sentence and utterance IDs.
`sentence_states` and `phases` preserve `read|partial|unread|empty` populations.
Resolution fallback trees remain available while the resolution channel is
unread. Fold and graph failures have independent named errors. A fold computed
without successful document resolution is not represented as a resolved fold.

`unit_view(paragraph_id=..., source_sentence_id=...)` selects those same resolved
trees and mentions. It performs no encoding or grounding. `supporting_mentions`
retains same-referent evidence outside the selected unit, including antecedents
in earlier paragraphs.

`is_person(mention)` now returns `PersonEligibility(code, evidence)` with
`person|non_person|unknown`. Grounded person types and definitional kinship/title
words can establish positive evidence. Grounded city/place and other non-person
roots establish negative evidence. Conflicts and shallow unknown proper names
remain unknown. Proper-name syntax, recurrence and `fold.eligible` establish
neither verdict. Boolean conversion raises: consumers must compare `.code`
explicitly. `EntityIdentity`, `RelationalIdentity`, and `CorefJunk` now require
positive person evidence for person-only identity guards. Existing real-referent
and person-validation cassettes retain their distinct questions.

## Public structural measurements

`gse.structure.operation_counts(tree)` accepts live or serialized trees and
retains every encountered operation, including `TEMPORAL` and unknown labels.
`OPERATION_VOCABULARY` publishes the supported evaluated-label catalog.
`clause_depth(tree)` counts embedded Control, relative and event-complement
boundaries. Sequential temporal, contrast and coordination siblings do not add
depth; arbitrary dictionary nesting does not count as a clause.

`verb_head_evidence(trace, tree)` returns every represented verb's candidate
positions, tree path, and `unique|ambiguous|absent` state. GSE Events currently
retain verb lemmas rather than unique verb token coordinates. Repeated identical
verbs therefore remain ambiguous instead of receiving guessed positions.

`clause_head_evidence(trace, tree)` locates each Event's subject/object heads in
the current utterance with `supported|absent|ambiguous|unsupported` evidence.
It checks the head lemma against the local trace and refuses mismatched rebound
antecedent coordinates. Consumers obtain this evidence before document
resolution, then retain it alongside the resolved tree. Coordinated or missing
heads cannot silently become a subject/object distance observation.

`entity_source_evidence(trace, source_tree, resolved_tree)` joins source Entity
occurrences to resolved entities at the same structural field path. Each local
head must match its trace lemma and position. Source heads and resolved heads
remain separate; substituted antecedent children do not become new mentions.
Missing source trees, changed paths and mismatched local heads remain explicit
unread evidence. Serialized nominal lemma spans are not source coordinates.

`structural_loss_evidence(trace, tree, utterance_id=..., boundary=...)` reports
located `missing_predicate`, `ambiguous_predicate_witness`, `empty_operand`, and
`operand_arity_mismatch` findings. Construction EVENTS carry the verb in
`Op.primitive`; evaluated Events carry `verb`. Intake checks both boundaries.
An open discourse operand remains explicit empty-operand evidence. The diagnostic
does not determine whether every argument attachment, sense, auxiliary, copula,
or pragmatic reading is correct. An empty report is not a correctness certificate.

## Profile change and classifier compatibility

`text_profile` consumes the shared utterance event stream. It commits an
observation only after all feature computations succeed. Failed IDs and errors
are returned; they cannot leave partially incremented counts. `n_sentences`
counts source sentences and `n_read` counts aggregated utterances.

The record includes overall state, independent populations, full operation
counts, embedding depths and located structural losses. Missing numeric values
are `None`; zero remains numeric when observed. Affect uses content tokens with
explicit GOOD/BAD evidence. Missing affect tokens and failed utterances are not
neutral observations. With fewer than two affect-bearing utterances, the arc is
undefined (`None`). An all-unread profile retains unread populations and failures.

The legacy operation bank and `PROFILE_FIELDS` layout remain fixed.
`legacy_vector(missing=0.0)` is an explicit historical-classifier projection
that fills unavailable values with the chosen fallback and omits new operation
labels. `vector()` delegates to that compatibility projection. Auditable callers
consume `to_dict()` and its populations, never infer measured zero from a legacy
vector. Existing serialized classifier references require refitting/versioning
when their semantic input assumptions change.

## Verification scope

`tests/test_complete_document_reading.py` exercises named failures, stable IDs,
deadlines, malformed inputs, attribution, paragraph support, independent document
phases, city/person/unknown guards through the deck, atomic profiles, measured
zero, and located structural losses. Existing profile and speech tests remain
compatibility checks. The integrated OpenSpec acceptance run owns the full-suite,
mutation, transport-schema and linked voice-command evidence.
