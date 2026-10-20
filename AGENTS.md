# GSE

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

## Design constraints

- **Grounding goes through the existing pipeline.** A new grounding source is a parser exposing `to_primitives`, one
  entry in `integrator.load_all_sources()` and one scope in `SOURCE_PRIMITIVE_SCOPE`, not a new grounding module, a
  flat word→primitive lookup or a similarity score.
- **The lexicon is definitional only, over a closed basis.** A word's meaning is a ternary sign {-1, 0, +1} over the
  build's fixed set of primes; a component not expressible that way is not lexical meaning, so `dog` and `cat` may be
  near-identical, correctly. World facts and world-affect belong to sparse-wiki, the orthogonal world leg.
- **No cosine resolver.** Meaning is discrete structure (IS-A genealogy, exact sign-match, resolved keys); GSE's own
  resolver is `grounding._select_by_coherence` with `_jaccard` over type threads. The HDC `sense_resonance` cosine is
  a guarded secondary re-ranker only.
- **DeepNSM is silver: anchors and evaluation only.** Its text is LLM-generated and CC-BY-NC-SA 4.0, so it is never
  baked into the shipped lexicon (Rohan's decision, 2026-06-19).
