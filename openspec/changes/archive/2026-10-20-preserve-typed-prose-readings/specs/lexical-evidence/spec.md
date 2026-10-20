## Purpose

Expose the lexical facts prose instruments need without conflating a word's frequency, domain membership, decomposition availability or distinct affective readings.

## ADDED Requirements

### Requirement: Lexical lookup reports its actual state
Word readings SHALL distinguish a decomposed lexeme, an existing lexeme with no active primitives, a missing lexeme and an unread data source. The selected lexical record and source SHALL be identifiable. Missing senses SHALL not be silently presented as verified sense resolution.

#### Scenario: Designed zero and absent word
- **WHEN** an operator with an intentionally empty word decomposition and a nonexistent word are read
- **THEN** the former is an existing zero lexeme and the latter is absent, even though both contribute no word primitives.

#### Scenario: Lexicon unavailable
- **WHEN** the lexical data cannot be read
- **THEN** the channel reports unread data and does not call every word absent.

### Requirement: Rarity uses the named general-English source
Frequency evidence SHALL expose the general-English rank separately from local or combined ranks, with ranked, unranked, not-applicable and unread states. Source identity and data version SHALL accompany the rank.

#### Scenario: Only a local rank exists
- **WHEN** a content word has a domain-corpus rank but no rank in the named general-English source
- **THEN** it is unranked for the general-English channel and its local rank does not substitute.

#### Scenario: Frequency data cannot be opened
- **WHEN** the named frequency source is unavailable
- **THEN** rank evidence is unread rather than a fabricated maximum rank or unranked observation.

### Requirement: Dictionary membership and semantic curation are distinct
The protected dictionary SHALL preserve term/name kind, aliases, definitions when supplied, source and review status. Membership SHALL support spelling protection and term counting without claiming that an unreviewed definition or decomposition is validated.

#### Scenario: A learned domain term
- **WHEN** a user learns a term without a validated decomposition
- **THEN** it is protected and listed as a term while semantic decomposition remains explicitly pending or absent.

#### Scenario: Independent drafts disagree
- **WHEN** two proposed decompositions disagree on a prime or sign
- **THEN** the disagreement remains visible and only a validated agreed result can enter the curated semantic lexicon.

### Requirement: Morphological reading respects lexical evidence
Morphological composition SHALL preserve the distinction between verified negation, reversal, inflection and an unresolved apparent prefix. It SHALL not silently replace a known lexical reading merely because stripping letters yields another valid word.

#### Scenario: A false prefix
- **WHEN** "inside" is encountered
- **THEN** it retains its supported containment reading and is not represented as the negation of "side".

#### Scenario: A genuine coined negative
- **WHEN** "unloyal" has a supported base and licensed negative composition
- **THEN** its negative meaning is derived with the base, operation and evidence recorded.

#### Scenario: A reversal
- **WHEN** "unlock" is recognized as reversing an action
- **THEN** reversal is not passed off as evaluative negation or proof that every aspect of lock is false.

### Requirement: Affect and concreteness channels retain their own meaning
Structural E/P/A, lexical V/A/D, world salience and concreteness SHALL retain separate source identities, scales and availability states. A missing channel SHALL not be replaced by another. Cross-channel differences SHALL be computed only where a documented comparable scale and paired evidence exist.

#### Scenario: Structural projection without a felt rating
- **WHEN** a word projects structurally but has no lexical V/A/D rating
- **THEN** structural E/P/A is available and felt V/A/D is absent, with no invented zero or fallback.

#### Scenario: A raw rating is available
- **WHEN** a lexical V/A/D or concreteness resource supplies a rating
- **THEN** the original rating and scale are exposed rather than only its coarse primitive conversion.

### Requirement: Evidence pins reproducibility
The reading SHALL identify the code, basis, lexical resources, dictionary and policy versions that affect its results. Changing a resource SHALL change its provenance and invalidate cached dependent readings.

#### Scenario: Dictionary changes between runs
- **WHEN** an alias or term is learned after a cached reading
- **THEN** a later run cannot silently reuse the old dictionary-dependent result.
