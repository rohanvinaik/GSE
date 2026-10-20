## Purpose

Preserve the compositional content of ordinary prose as typed claims whose roles, qualifications and derivations remain inspectable by every downstream consumer.

## ADDED Requirements

### Requirement: Operators preserve the propositions they qualify
The reading SHALL retain recoverable events, participants and scope when an operator qualifies or connects clauses. Unsupported attachment SHALL be explicitly unresolved rather than emitted as a complete reading with missing operands.

#### Scenario: Contrast at the head
- **WHEN** the input is "But the cell moved."
- **THEN** the movement with agent cell is retained and the head contrast is represented without fabricating a preceding proposition.

#### Scenario: Clause contrast and restriction
- **WHEN** the input is "The cell moved, but the lens stopped." or "Only the king slept."
- **THEN** both contrast clauses, or the sleeping proposition and its restriction, survive with their participants.

#### Scenario: An adjective contrast is preserved
- **WHEN** a within-phrase contrast such as "small but strong" is read
- **THEN** it remains a phrase-level contrast and does not fabricate clause events.

### Requirement: Scope polarity and commitment remain separate
The reading SHALL expose ordered scopes, claim polarity, commitment and their evidence separately. Negation SHALL compose with verified negative morphology. Conditions, beliefs, questions, possibilities and obligations SHALL remain distinguishable from committed positive and negative statements.

#### Scenario: Possible negative and committed negative
- **WHEN** "He might not leave." and "He did not leave." are read
- **THEN** the former retains possible negative content without asserting non-departure, and the latter retains a committed negative claim.

#### Scenario: Denied belief does not decide its content
- **WHEN** "She does not believe that he left." is read
- **THEN** the denial concerns believing and the truth of his departure remains uncommitted.

#### Scenario: Two independently verified signs
- **WHEN** "The knight is not disloyal." is read
- **THEN** clause negation and the verified lexical negation compose to positive loyal content while both mechanisms remain inspectable.

### Requirement: Inference admits only warranted premises
Bounded inference SHALL consume the same claim commitments and scope evidence as the public reading. It SHALL withhold questions, beliefs, possibilities, obligations and irrealis content as categorical facts. A negative fact SHALL never become a positive premise through traversal.

#### Scenario: Modal event does not become a fact
- **WHEN** a knowledge base is constructed from "He might leave." or "He should leave."
- **THEN** a query asserting his departure is not entailed.

#### Scenario: Modal type does not become a fact
- **WHEN** a knowledge base is constructed from "This should be clear."
- **THEN** clarity is not entailed as a categorical type assertion.

#### Scenario: Supported rule still fires
- **WHEN** "If Rex barks, Mike leaves." and "Rex barks." are admitted in the supported inference fragment
- **THEN** Mike's departure is derived with the actual premise and rule chain, while the rule alone asserts neither arm.

### Requirement: Claim identity preserves the supported distinction
The reading SHALL provide versioned comparison keys with resolved referent identities, relation content and polarity evidence for supported claims. Unsupported or ambiguous key construction SHALL abstain. Surface forms and argument roles SHALL remain available beside every reduced key.

#### Scenario: Pronoun and antecedent meet
- **WHEN** document resolution establishes that "it" denotes the previously mentioned cell
- **THEN** supported claims about the pronoun and the cell share that referent identity without merging another cell merely because its lemma matches.

#### Scenario: Synonymous forms and role swaps
- **WHEN** verified primitive decompositions identify the same supported relation in two claims
- **THEN** reduction can expose their common form while retaining their wording, and exchanging agent and patient produces a distinct key.

#### Scenario: A coarse or incomplete key cannot prove identity
- **WHEN** a relation is generic, a relevant argument is unresolved, or a semantic role cannot be represented in the supported key
- **THEN** the comparison reports its limitation and does not certify complete meaning-equivalence or contradiction.

### Requirement: Derivations state their boundary
The reasoner SHALL retain its supported type/order closure and single-antecedent implication fragment, with located premise chains. Unsupported reasoning SHALL produce a named non-entailment or unsupported state, distinct from a demonstrated negative conclusion.

#### Scenario: The reverse chain does not follow
- **WHEN** A greater than B and B greater than C are read
- **THEN** A greater than C is derivable with its chain and the reverse remains not entailed.

#### Scenario: Unsupported logic stays bounded
- **WHEN** an inference requires unsupported quantifier scope or conjunction of rule antecedents
- **THEN** the system exposes the unsupported boundary and does not silently flatten the input into a supported rule.
