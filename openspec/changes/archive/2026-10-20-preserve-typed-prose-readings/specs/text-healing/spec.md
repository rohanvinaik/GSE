## Purpose

Provide SymbolicSpellCheck as a reusable, deterministic text-healing operation whose edits can be inspected and safely mapped back to the original source.

## ADDED Requirements

### Requirement: All interfaces share one correction operation
The reusable healing API, spelling MCP and downstream prose probe SHALL use the same correction policy and return equivalent healed text and ledgers for the same text, data and policy versions. The reusable core SHALL operate without importing an MCP server or starting a model.

#### Scenario: Two interface doors
- **WHEN** the same misspelling is processed through the MCP and a direct core call
- **THEN** accepted edits and healed text agree and each record identifies the same policy version.

### Requirement: Every edit has source evidence
Healing SHALL return original and resulting text identities plus located applied, offered, kept and refused decisions. Accepted edits SHALL use source offsets and preserve every other character. Ambiguous or overlapping mappings SHALL be refused rather than reconstructed by joining tokens.

#### Scenario: Punctuation survives
- **WHEN** a typo is corrected beside quotes, commas and non-ASCII text
- **THEN** only the accepted typo span changes and the remaining text is byte-preserved on serialization.

#### Scenario: An edit cannot align
- **WHEN** the token span cannot be aligned uniquely or edits overlap
- **THEN** the ledger reports unaligned or overlap and leaves the affected source unchanged.

### Requirement: Protected and valid text is preserved
Healing SHALL preserve recognized valid words, protected names, terms and aliases, units, digits, markup and non-ASCII forms under the declared policy. Uncertain corrections SHALL remain offers rather than destructive commitments.

#### Scenario: Technical prose survives
- **WHEN** text contains Papert, µm, déterminants and a protected domain term
- **THEN** these forms remain unchanged and their protection or refusal evidence is reported.

#### Scenario: Clear typo and valid unusual word
- **WHEN** the input contains a supported clear typo such as "beleive" and the valid word "anser"
- **THEN** the typo is corrected under the policy and the valid unusual word is preserved.

### Requirement: Learning is persistent and semantically bounded
Learning SHALL atomically store validated term/name entries and aliases, preserve confirmed definitions and provenance, resolve duplicate-entry conflicts deterministically, and invalidate dependent caches. It SHALL not silently promote a learned spelling into a verified semantic decomposition.

#### Scenario: Learning survives a new process
- **WHEN** a term is learned and the process restarts
- **THEN** the term remains protected and its source, kind and review status remain inspectable.

#### Scenario: Malformed learning request
- **WHEN** an entry has invalid fields or an invalid surface form
- **THEN** learning returns a named malformed-entry result and preserves the existing store.

### Requirement: Boundary repair remains an evidenced edit
Missing sentence-stop repair SHALL preserve its evidence, location and applied or offered state. An uncertain boundary SHALL be offered. The output SHALL retain source sentence boundaries before and after repair so downstream measurements identify the text they measured.

#### Scenario: An uncertain capitalized word
- **WHEN** an apparent sentence boundary could instead be a proper name
- **THEN** the repair remains offered unless the declared structural policy resolves it, and no silent sentence-count change occurs.
