## ADDED Requirements

### Requirement: One population state of four-state cells
The builder SHALL hold every reading's 56 banks as masks over +1, -1, 0 and SILENT in a single state, and SHALL
derive every published value, measurement and sense from that state. A singleton mask SHALL be a decided cell, a
mask of two or more states SHALL be a residual with a named reason, and an empty mask SHALL be a conflict. Zero and
silence SHALL remain distinct.

#### Scenario: Silence is not zero
- **WHEN** no warrant establishes explicit absence on a bank
- **THEN** the bank is not written as 0, and it is SILENT only under a warrant of definitional silence

#### Scenario: Nothing lives in a side layer
- **WHEN** inheritance, a relation or a source decides a cell
- **THEN** the decision is in the population state that the measurement and every rule read

### Requirement: Sources write only within their declared competence
Each source lens SHALL declare the banks it may write, the banks it must not write, and the binding it requires.
Ratings, associations and classifier outputs SHALL be recorded and SHALL NOT decide a cell. Two encodings of one
observation SHALL count as one witness.

#### Scenario: A rating does not write a bank
- **WHEN** an emotion lexicon associates a word with a feeling
- **THEN** the association is recorded and no bank of the word changes because of it

### Requirement: Relations between banks propagate over the whole population
Relations SHALL be guarded tables of permitted or forbidden tuples over banks, each with a warrant, applied to
their whole eligible population, and closure SHALL reach an order-independent fixed point in which every removed
state names its cause.

#### Scenario: Two premises together remove a state
- **WHEN** neither of two decided banks alone excludes a state of a third, but a relation over all three does
- **THEN** closure removes that state and records both premises

#### Scenario: Closure runs at the scale of the lexicon
- **WHEN** a full round runs over all 401,596 readings
- **THEN** it completes without any per-definition resolution step, and cold and incremental replays agree

### Requirement: Coherence is agreement among independent sources, never a threshold
The builder SHALL settle a cell where independent competent sources agree and SHALL record a conflict where they
disagree. A relation latent across the population SHALL be proposed only when its exact counterexample set among
independently stated readings is empty within its scope. No probability, rate, support count or similarity score
SHALL admit a relation or decide a cell.

#### Scenario: Unknown is not a counterexample
- **WHEN** a candidate relation's consequent is unstated for a reading
- **THEN** that reading neither confirms nor contradicts the candidate

#### Scenario: Disagreement is investigated, not voted
- **WHEN** two independent sources state opposite values on one bank of one reading
- **THEN** a conflict record names the reading, the bank and the source roots, and no side wins by count

### Requirement: Admission follows the significance-weighting gate
A candidate relation or censor SHALL be admitted only if a stated fact confirms it, it leaves lawful plurality, and
it adds reach against current closure. A candidate confirmed and contradicted SHALL be narrowed to an imputed type
that separates the cases, or SHALL be recorded as a finding when no type separates them.

#### Scenario: A rule cannot confirm itself
- **WHEN** the only support for a candidate comes from values the builder derived
- **THEN** the candidate is not admitted

#### Scenario: A redundant rule earns nothing
- **WHEN** a candidate's consequences are already reachable under current closure
- **THEN** its reach is zero and it is not admitted

### Requirement: Positive values need a positive root
A signed value SHALL be written only with a positive root: a source component, an authored prime, or content carried
through an admitted relation or inheritance. Elimination that leaves one sign without such a root SHALL be reported
as a missing content warrant.

#### Scenario: Exclusion alone does not define a thing
- **WHEN** censors remove every state of a bank but +1, and no positive root exists
- **THEN** the cell is reported as missing a content warrant and is not published as +1

### Requirement: Inheritance carries declared properties as defeasible defaults
Inheritance edges SHALL be typed and directed and SHALL carry only the properties their family declares, as
defaults with applicability and defeaters. Conflicting defaults SHALL be suspended and reported, and a hub's silence
SHALL NOT be inherited.

#### Scenario: Conflicting defaults are suspended
- **WHEN** two inherited defaults disagree on a bank of one reading
- **THEN** both are suspended and reported, and neither is chosen by order

### Requirement: Senses form from equal load-bearing encodings
Readings of one lemma and part of speech SHALL form one sense only when their resolved load-bearing encodings are
equal. Missing evidence SHALL NOT establish equality, every part of speech present SHALL keep at least one sense,
and no sense SHALL be ranked as a main sense.

#### Scenario: A word with many definitions keeps its real senses
- **WHEN** the builder forms the senses of "lock"
- **THEN** its genuine homonyms and each part of speech remain, and no frequency-defined winner appears

### Requirement: Every round is measured
Each round SHALL record the specification bits H, the census of every cell by state, bank, part of speech and
source, the decided cells by warrant, the conflicts, each admitted rule's reach, and the wall time and memory.

#### Scenario: Progress is a measurement
- **WHEN** a round finishes
- **THEN** its receipt reports how far H fell, split into direct premises, structural consequences and admitted
  population laws

### Requirement: The model is only a bounded, typed tail
The ordinary build SHALL make no model calls. A tail SHALL run only when explicitly enabled after the bulk is
measured, SHALL offer only legal states with their warrants, SHALL accept one of them or an abstention, and its
answer SHALL become a rule candidate rather than a lexical value on its own.

#### Scenario: A stale answer cannot write
- **WHEN** a tail answer no longer matches the current closure of its cell
- **THEN** it is refused and the cell is unchanged
