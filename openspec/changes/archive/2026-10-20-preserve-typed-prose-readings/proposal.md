# Preserve typed prose readings

## Why

GSE computes distinctions that downstream consumers lose: modal statements become facts, operators discard events, and failed readings become empty or zero-valued results. The voice profiler needs the complete, typed, located reading promised by GSE's theory, including what could not be read.

## What Changes

- Preserve clause content, roles, modality, polarity and document identity through encoding, resolution, proposition extraction and bounded inference.
- Expose complete document intake with stable source identities, explicit failures and incremental utterance results.
- Publish lexical states, general-English frequency, structural E/P/A, lexical VAD and concreteness as separate evidenced channels.
- Extract SymbolicSpellCheck's reusable core and persistent protected dictionary; retain the MCP as a wrapper.
- Consolidate duplicated claim semantics used by inference, proof demonstrations and profile consumers.
- **BREAKING:** corrected readings and profile features change where the old code lost structure or fabricated absence; consumers receive versioned contracts and explicit migration evidence.
- Keep the current deterministic architecture, its bounded inference fragment and existing working proofs. This change repairs the substrate needed by the linked voice build; it does not redesign all of GSE or implement language generation.

## Capabilities

### New Capabilities

These are newly recorded OpenSpec capabilities, including existing behavior whose contract was never captured in OpenSpec.

- `compositional-reading`: faithful typed claims, scope, identity and bounded derivations.
- `reading-evidence`: complete multiscale readings, source accounting, failures and degradation.
- `lexical-evidence`: distinct lexical, frequency, affect and dictionary evidence.
- `text-healing`: source-preserving corrections and protected learned terms through one reusable core.

### Modified Capabilities

None. No existing OpenSpec specifications were present at initialization.

## Impact

`gse/api`, `gse/nlp`, `gse/symbolic`, `gse/discourse`, `gse/cassettes`, dictionary curation, spell MCP, proof demonstrations and their tests. The consuming change is `/Users/rohanvinaik/Projects/SquishOS/openspec/changes/restore-voice-profile`. The cross-project contract is `contracts/gse-voice-boundary.md` here. No new runtime dependency is presumed. No production code is changed by this proposal.
