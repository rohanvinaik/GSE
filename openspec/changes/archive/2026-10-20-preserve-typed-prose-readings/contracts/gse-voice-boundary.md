# GSE / voice boundary — version 1 proposal

This is the single seam contract for the two changes. It specifies required information, not a new framework. GSE owns language reading; SquishOS owns source-file reduction, metric definitions, references and display. The SquishOS adapter runs under GSE's interpreter and converts GSE records into `voice.reading/1`. No consumer reimplements grammar, grounding or claim commitment.

## 1. Ownership and paths

| Operation | Owner and required public surface | Consumer |
|---|---|---|
| Encode and evaluate | Existing `GSEEncoder`, `from_trace`, `resolve`, `evaluate_tree` | speech/document intake, profile adapter |
| Paragraph boundaries | Public `split_paragraphs`; shared by existing multiscale consumer | source-unit validation |
| Complete speech intake | New `encode_document_utterance_events(enc, sentences, deadline)` | legacy triple wrapper, voice probe |
| Lexical states | Public lookup returning row/prime/availability evidence, selected record identity | source-word adapter, healing |
| Negative morphology and signs | Corrected `resolve_negation`, public `negation_signs` | claim polarity, stacked signs |
| Proposition semantics | Existing `propositions` plus public `commitment`, `claim_key`, `polarity`, `scope_signature`, `identity` | KB, proof demonstrations, passage adapter |
| Structure | Public `operation_counts` and `clause_depth` over serialized structure; existing token SYN evidence | profile adapter and legacy fixed classifier projection |
| Document context | Existing `resolve_document`, `read_fold`, `NarrativeGraph`, grounding flags | located threads/edges/flags |
| Optional raw lexical data | Explicit local-resource readers for frequency, VAD and concreteness; existing `epa_projection` | word and register adapter |
| Healing and learning | `gse.nlp.heal.suggest`, `boundaries`, `learn`; typed `personal_dictionary.entries` | MCP and SquishOS spelling/voice doors |

New names are proposed public API contracts from the historical build plan, consolidated here. Implement flat atomic decisions underneath, not a second parser. Existing equivalent public surfaces can satisfy a row if documented and exercised by its consumers.

## 2. Intake events and identity

GSE's public iterator receives complete source sentences with stable supplied IDs. It yields a manifest before results, then one outcome per expected utterance. The iterator includes content, quotation/speaker/addressee, source sentence ID and ordinal; trace/tree or named error; the error boundary includes deixis. It preserves complete-document attribution and streams successes and failures before the deadline. The compatibility triple API consumes this iterator and explicitly documents that it returns only successes.

SquishOS transport is JSON Lines: `sentence`, `manifest`, `utterance`, `document`, `end`. Every event has a version and stable identity. `sentence` carries source-word evidence independently of utterance reading. `document` has its own state and failures. `end` declares complete or deadline. No process memory object or dynamic Python attribute is required across transport.

IDs are `(document, sentence, utterance, ordinal)` as applicable. Token joins are `(utterance_id, position)`; positions restart within utterances. Document-tree indices map explicitly to utterance IDs and source sentences. A skipped/failed item cannot shift subsequent identities.

## 3. Required payload

| Record | Required information |
|---|---|
| Provenance | schema/API/metrics identities, GSE commit and dirty-source fingerprint when applicable, basis/lexicon/frequency/dictionary/VAD/concreteness hashes or named unavailable source, policies |
| Source units | section/paragraph/line/sentence IDs, text and source span; excluded-block kind and span |
| Source word | surface, lemma, POS and position/span, lexical state and selected-record evidence, frequency rank/state/source, dictionary membership, raw VAD/concreteness with presence/scale |
| Encoded token | surface/lemma/POS/position, signed word primitives, sentence primitives, contextual operator status and typed operation/arity, lexical operation, negative-prefix evidence, structural EPA or explicit silence |
| Claim | kind, located surface, serialized predicate, roles with head positions, ordered scopes with owner identities, commitment, clause sign, composed polarity, comparison key and supported/unresolved state |
| Structure | typed operations, embedding evidence, clauses and degradation findings, explicit verb/head position state unique/ambiguous/absent |
| Document | mentions with referent IDs and source joins, resolved nodes/typed edges, grounding flags, fold role/significance with evidence and per-channel state |
| Derivation | query claim ID, earlier premise IDs, scope/context and supported rule chain, or named not-entailed/unsupported state |
| Heal ledger | original/measured hashes, policy/dictionary versions; edit span, original/replacement, leg, evidence, decision and reason |

The implementer writes a JSON Schema and checked fixtures for `voice.reading/1` before integrating the probe. A schema permits optional unavailable channels but requires their explicit states. Schema tests validate both producer and consumer, not one handwritten example alone.

## 4. State algebra

- Sentence encoding: `read` all expected utterances succeed; `partial` some succeed; `unread` none succeed or manifest missing; `empty` explicit manifest has no expected utterances.
- Document channels: `read`, `partial`, `unread`, `empty` as warranted by their own populations; receiving an event does not establish successful analysis.
- Lexicon: `primes`, `no_primes`, `no_row`, `unread`. Frequency: `ranked`, `unranked`, `not_applicable`, `unread`. Unreviewed or ambiguous selection is evidence, never silently validated sense resolution.
- Scalar/distribution/list result: `state`, `value`, `num`, `den`, `n`, `failed`, `support`, `evidence`, `definition`, `provenance`; only applicable fields carry numbers. States are `measured`, `partial`, `unread`, `absent`, `not_applicable`, `undefined`, `unsupported`. Support is separately `sufficient`, `thin`, `none`.
- Empty observed population gives null value with a reason, not 0/0. A valid observed zero remains numeric. Failed records preserve their IDs and are excluded from observed denominators, counted as failed.
- Termination precedence: shell kill → `killed`; nonzero exit → `crashed`; valid end reason → `complete`/`deadline`; otherwise `incomplete_protocol`. Transport defects are counted separately. Unreceived outcomes remain unread.

## 5. Claim semantics and comparison boundary

Use full ordered scopes for commitment: questions → `in_question`; denied knowing/believing or explicitly abstained content → `abstained`; every scope transparent (`asserted`, `epistemic`, `negated`) and valid → `committed`; otherwise → `non_committed`. Structural invalidity is a separate unread/unresolved state. This preserves a committed negative without mistaking a possible negative for one. Lossy `status` remains a convenience projection only.

Compose clause sign with verified negative-prefix sign; reversal is not negation. Never derive prefix polarity merely from spelling. Preserve both signs as evidence, not just the product. Questions use source interrogative evidence even where the current tree has no question node.

Comparison keys are versioned tagged tuples. Supported Event keys include the relation's signed primitive form, resolved agent/patient identities and every other represented argument role relevant to equivalence; TypeAssertion keys include entity identity and base kind; Comparison keys include axis, direction and ordered operands. Keep wording, decomposition and abstraction limits alongside. Key construction abstains where unsupported. Identity uses resolved entity ID; lemma fallback is marked unresolved/local and cannot certify a cross-referent match. Coarse generic forms remain separate candidates.

Non-negation scopes, their owners and represented temporal/context qualifiers participate in comparability. A missing qualifier is not an affirmative match against a contradictory explicit qualifier. Exact equality of a coarse key establishes equality at that declared projection only. It does not prove that all worldly or pragmatic meanings coincide.

The KB consumes this authority rather than independently deciding modal truth. Preserve the bounded inference fragment; unsupported modalities, argument structures or conditions remain withheld. Derivation over a passage snapshots earlier premises before querying its current claim.

## 6. Raw versus encoded channels

All retained prose words receive source-word reading even when utterance processing fails or consumes attribution. Encoded-token measures explicitly exclude unencoded attribution. Content eligibility is content POS with no lexical composition operation; contextual operator status is separately retained. Do not infer lexical absence from an empty prime map.

General-English rarity uses `FrequencyInfo.david47k_rank`, not combined/local rank or unknown-default weight. Resource-open failures must be surfaced rather than swallowed by the legacy frequency API. Load raw VAD/concreteness from declared local resources; do not trigger automatic downloads during a read. Raw ratings remain separate from their curation-to-prime conversions. `epa_projection` is structural and returns null when no prime projects. World salience remains a separate optional source.

## 7. Text and edit coordinates

Use half-open Unicode code-point offsets over the exact decoded original and reduced text, with each coordinate's text identity explicit. Read original UTF-8 bytes without newline normalization; retain the byte hash and original encoding. Invalid UTF-8 is a named input refusal, not ignored bytes. A source map stores monotone retained segments between reduced and original coordinates. An edit crossing a removed segment, a discontinuity or an ambiguous alignment is refused. Applied replacements are tested to preserve every other serialized byte, including CRLF and non-ASCII forms.

Do not normalize source punctuation or respell valid prose as a side effect of token reconstruction. Missing-stop edits have their own evidence and before/after sentence manifests.

## 8. Shared adversarial fixture set

Before wiring, freeze public-boundary fixtures containing: two paragraphs with a cross-paragraph pronoun; quotation with separate attribution; one failed utterance followed by a successful one; an explicit empty manifest; modal positive/negative, committed negative and denied belief; a question; nested complements; clause and adjective contrast; unary restriction; true and false prefix cases; same-form paraphrase, argument swap and generic relation; grounded city versus unknown name; missing database versus designed zero; all-unread document; malformed event; deadline/crash/no-end; markup, CRLF, µm, Papert and a learned term. Expected results are hand-derived from the requirements and checked through the real entry points.
