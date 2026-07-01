# GSE — working agreement

## Wait for scope before acting.

Rohan front-loads context before he states the task. "Here is some context",
a file path, or "I made changes" is preamble, NOT a go signal. Do not read,
explore, or write until he has given an explicit, scoped instruction. If
unsure, ask one line and wait.

## Docs are not ground truth.

This repo is in active drift. `docs/THEORY.md` is known-invalid — do not use
it as a source. Treat the other planning docs as unverified. Authoritative
sources: Rohan, then the code. When sources conflict, surface it.

## The statement healer is biology-shaped (design framing).

The Genesis-facing statement healer (the voice-mode repair layer that produces clean
statements) is modeled on DNA error-correction + gene regulation — biology as a tested
reference design, not loose analogy. A sentence is a **coding sequence**: a *coding-sequence
repair* re-reads a mis-parsed ORF under the structural law. A correct read's driver is often
in the bounded **cis-regulatory neighborhood** (~±2 lines — `resolve_document` /
`encode_document_utterances`), sourced by a *regulatory repair*. **Intervention scope (one
clean statement) ≠ signal scope (±2 lines)**; meaning is in the combination of local +
regional frames. Full: Genesis `docs/ARCHITECTURE.md` + memory `project_l2_voice_modes_flywheel`.

## The cassette layer (additive; `gse/cassettes/`).

Domain-portable experts that resolve ONE in-frame uncertainty using OUT-OF-frame multi-scale context —
**GSE is the player, a cassette is the tape**; the single-sentence scale is the ceiling, cassettes are
contingent on the higher scales. Built: `MultiScaleDoc` (four scales, composed once) + `Cassette` base
(SymbolicSpellCheck spine) + `entity_identity` / `relational_identity` / `person_validation` +
`CassetteDeck` + `cheatsheet` (ride-along + span-aware `make_merge_repair` at the
`from_document(repair=)` seam). Non-negotiable laws: **compose existing tools (read_fold / grounding /
facets), never re-ground; confidence = CONVERGENCE; never destroy a correct value; validate
resolve-or-abstain across the WHOLE corpus.** Purely additive — no existing GSE source is modified.
Full: `~/Genesis/docs/CASSETTE_ARCHITECTURE.md` + `CASSETTE_ARCHITECTURE_DESIGN_BRIEF.md`.
