## ADDED Requirements

### Requirement: The mode is declared, never inferred
A request SHALL read in declarative mode only when it declares `mode: declarative`. GSE SHALL NOT infer the mode
from the text, its source or its sender, and SHALL read an undeclared request exactly as standard GSE does.

#### Scenario: A declared request
- **WHEN** a request declares `mode: declarative`
- **THEN** intake records the mode on the slip and the declarative reading department reads it.

#### Scenario: The same text without the declaration
- **WHEN** the same text arrives without the declaration
- **THEN** it is read by standard GSE, and its reading is identical to the reading before this change.

### Requirement: The mode's grammar is closed and positional
In declarative mode each non-empty line SHALL be exactly one clause of the form
`SUBJECT [MODAL] [not] VERB [OBJECT] [PREPOSITION PHRASE]*`, where a noun phrase is
`[DETERMINER] [ADJECTIVE]* NOUN+` and its head is its last noun. Roles SHALL follow from position: the noun phrase
before the verb is the subject, the word in the verb slot is read only through its verb senses, and the noun
phrase after it is the object. Capitalization SHALL carry no grammatical role. The vocabulary SHALL be the whole
active lexicon.

#### Scenario: A spine line
- **WHEN** the line `Detective writes tests for Python code` is read in declarative mode
- **THEN** the reading is detective —write→ test, with `for Python code` attached to the verb.

#### Scenario: A noun compound with a plural head
- **WHEN** the line `The team builds verification tools` is read in declarative mode
- **THEN** the object is the noun phrase headed by `tool`, and `tools` is not read as a verb.

#### Scenario: A modal and a negation
- **WHEN** the line `The engineer should not ship unverified code` is read in declarative mode
- **THEN** the reading is engineer —ship→ code with the modal and the negation recorded as operators on the event.

### Requirement: A line outside the grammar is refused by name
A line that does not fit the mode's grammar SHALL be refused as `NOT_DECLARATIVE_FORM`, naming the position and
the expected slot. The mode SHALL NOT fall back to standard heuristics or supply a missing subject, verb or role.

#### Scenario: An imperative
- **WHEN** the line `Translate design intent into properties` is read in declarative mode
- **THEN** it is refused as `NOT_DECLARATIVE_FORM` with the missing subject named, and no event is emitted for it.

#### Scenario: A coordinated clause
- **WHEN** a line contains two verbs joined by a coordinator
- **THEN** it is refused as `NOT_DECLARATIVE_FORM`, naming the second verb's position.

#### Scenario: A word that cannot fill its slot
- **WHEN** the word in the verb slot has no verb sense in the active lexicon
- **THEN** the line is refused as `NOT_DECLARATIVE_FORM`, naming the word and the slot.

### Requirement: The response has the standard form
A declarative-mode reading SHALL be returned in the same response form as a standard reading, with the mode
recorded in its provenance, so that a consumer reads both with the same code.

#### Scenario: A downstream consumer
- **WHEN** Regenesis receives a declarative-mode reading
- **THEN** it consumes the events exactly as it consumes a standard reading, and the provenance shows the mode.
