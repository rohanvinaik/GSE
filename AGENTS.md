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

## Rules from his corrections

Each was learned from a correction. The full record, in his words, is in `~/.claude/archive/2026-10-20-memory/gse/`
under the file name given.

- **Derive structure from the domain theory first.** Before proposing a closed set, taxonomy or classifier for a GSE
  feature, pull the established domain theory, derive the structure from it, and encode it as data the system carries
  (as `gse/pragmatics/figures.py` carries each figure's pole, licensing relation and `refines` edge), grounded in GSE's
  existing substrate, never a new ontology. Why: the Janus figure structure came by luck, when the scholarship should
  have made it obvious. (`feedback_engage_domain_theory_first_principles.md`)
- **Ground through the existing pipeline.** A new grounding source is a parser exposing `to_primitives`, one entry in
  `integrator.load_all_sources()` and one scope in `SOURCE_PRIMITIVE_SCOPE`: never a new grounding module, a flat
  word→primitive lookup or a similarity score. A new file or a big new function is the tell; where no structural way
  exists, stop and say so. Why: a whole day lost reinventing it three times. (`feedback_ground_via_existing_pipeline.md`)
- **The lexicon is definitional only, over a closed basis.** A word's meaning is a ternary sign {-1, 0, +1} over the
  build's fixed set of primes; a component not expressible that way is not lexical meaning (no borderline, no extra
  slot), so `dog` and `cat` may be near-identical, correctly. World facts and world-affect belong to sparse-wiki, the
  orthogonal world leg; sparseness is the contract. Why: corrected twice for judging decompositions by a
  feature-vector yardstick. (`feedback_gse_lexicon_definitional_only.md`)
- **No cosine resolver.** Never use vector cosine or embedding similarity as a resolver or yardstick when measuring or
  composing GSE: meaning is discrete structure (IS-A genealogy, exact sign-match, resolved keys). Compose GSE's own
  resolver (`grounding._select_by_coherence`, `_jaccard` over type threads); the HDC `sense_resonance` cosine is a
  guarded secondary re-ranker only. Why: a cosine yardstick inflated a 6% basis gap to 46–57%.
  (`feedback_no_cosine_resolver_in_gse.md`)
- **No reflexive cynicism.** Critique GSE only from gaps observed in the code or the session, never from a "this
  shouldn't be possible" prior; the vision docs are aspirational by design. Why: hedging from that prior once smuggled
  preference-encoded rules into the classical core. (`feedback_gse_no_reflexive_cynicism.md`)
- **DeepNSM is silver: anchors and evaluation only.** Never bake its text into the shipped lexicon: it is LLM-generated
  and CC-BY-NC-SA 4.0 (his decision, 2026-06-19). (`reference_nsm_gold_sources.md`, which also says where the
  canonical prime chart and the dataset live)
- **No shell or monitor thrash.** Run a short job synchronously in one foreground call; leave no background task or
  monitor armed; after two failed attempts, rethink the execution path instead of re-running with a tweak. Why: ten
  turns lost re-running a background grep. (`feedback_no_shell_monitor_thrash.md`)
