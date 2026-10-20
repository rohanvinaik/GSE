# reading-evidence Specification

## Purpose
Make a document reading auditable from its original units through utterances, claims, referents and aggregate features, including bounded failures and unavailable channels.

## Requirements

### Requirement: Every intake unit has an outcome
Document intake SHALL identify expected utterances before encoding results and account for each source sentence and utterance exactly once. Each outcome SHALL preserve its source identity, successful reading or named failure. An empty expected set SHALL differ from an unread unit.

#### Scenario: One utterance fails
- **WHEN** one of two expected utterances fails during encoding, evaluation or deixis
- **THEN** both outcomes remain located, the successful utterance remains usable, and the sentence is partial.

#### Scenario: No utterances are expected
- **WHEN** a source sentence is consumed as attribution and has no content utterance
- **THEN** it is explicitly empty for encoded claims and remains available for applicable source-text measures.

### Requirement: Document context is composed once
A document reading SHALL preserve cross-sentence attribution, coreference, referent identities and available multiscale evidence over the whole document. A unit view SHALL select from that reading without silently re-resolving its referents in isolation.

#### Scenario: A paragraph view keeps its antecedent
- **WHEN** a paragraph contains a pronoun whose antecedent occurs in an earlier paragraph
- **THEN** its unit view retains the whole-document referent and locates the supporting antecedent.

#### Scenario: Context resolution fails
- **WHEN** document resolution or fold analysis fails
- **THEN** sentence readings remain available and the failed document channel is explicitly unread; fallback trees are not represented as successfully resolved.

### Requirement: Structural losses are observable
The reading SHALL expose recoverable content lost during structural construction and unsupported attachments. No empty degradation report SHALL certify semantic correctness. Reported coverage SHALL distinguish successful transport, successful encoding and preserved structural evidence.

#### Scenario: An operator swallows a verb
- **WHEN** source predicate evidence has no licensed counterpart in the resulting claim structure
- **THEN** the affected unit is marked degraded with the missing evidence located, even if the result has a valid container type.

### Requirement: Missing values never masquerade as measured zeros
Reading and feature APIs SHALL distinguish measured zero, not applicable, unavailable data, failed computation and unresolved analysis. Missing observations SHALL be excluded from numeric populations and counted beside the result.

#### Scenario: All encodes fail
- **WHEN** every sentence fails to encode
- **THEN** feature output states unread populations and failures instead of reporting a complete neutral profile or a successful zero degradation rate.

#### Scenario: A balanced affect reading
- **WHEN** a successfully measured population has equal positive and negative contributions
- **THEN** its zero is retained as a measured value and distinguished from absence of projecting evidence.

### Requirement: Person eligibility follows available grounding
Identity-resolution guards SHALL retain positive, negative and unknown person evidence separately. Proper-name syntax alone SHALL not override grounded non-person types or certify personhood.

#### Scenario: A city is a proper name
- **WHEN** Paris or London resolves to a place/city lineage
- **THEN** a person-only identity guard rejects it as a person target.

#### Scenario: An unknown fictional name
- **WHEN** a proper name has no decisive person evidence
- **THEN** its person status remains unresolved unless independent permitted evidence establishes it.

### Requirement: Structural measurements expose their evidence
Public readings SHALL expose syntactic roles, typed operations, embedding structure and located referent/edge evidence needed for independent downstream measurements. Counts SHALL retain their population and supported-label vocabulary rather than hiding it inside a classifier vector.

#### Scenario: Nested clauses and a temporal operation
- **WHEN** the text contains nested complements and a temporal linker
- **THEN** the reading retains embedding evidence and the temporal operation even when a legacy classifier uses a smaller fixed feature layout.
