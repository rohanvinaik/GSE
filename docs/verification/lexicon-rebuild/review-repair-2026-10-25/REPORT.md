# Lexicon builder review response — 2026-10-25

The independent review's central finding is confirmed. The constructor has a
working finite-domain engine, native readers and constrained decoder, but lacks
the source-conditioned bank relations required for a general lexical build.
The earlier adjective demonstration did not establish complete definitions.
The active design is corrected in `docs/program/LEXICON_CONSTRUCTION_DESIGN.md`
§7.3. This is a verification receipt, not a second design.

## Current real-entry-point coverage

Command:

```sh
uv run python -m gse.lexicon_builder build \
  --word-file docs/verification/lexicon-rebuild/top1000-2026-10-25/words.txt \
  --symbolic-only \
  --output docs/verification/lexicon-rebuild/review-repair-2026-10-25/top1000
```

The frozen 1,000 surfaces produce 886 without an applicable rule and 114 with
partial readings. The latter comprise 10 adjective-profile records and 588
VerbNet class/frame records. Eleven canonical coordinates receive a nonzero
assignment. These are partial source projections, not 598 completed senses.
No full vector is exported. Input, rulebook, source and implementation digests
are in `top1000/manifest.json`; all word outcomes are in `top1000/words.jsonl`.
This is a coverage measurement, not a speed benchmark or a 90% token-mass audit.

## Corrections made

1. **Shared law admission.** `core.admitted_laws()` is used by default resolution,
   word construction and atomic proof. Only `FOUNDER_APPROVED` is active under
   the current registry policy. A candidate, discovered, prototype or missing
   status cannot write through an alternate consumer. Explicitly supplied
   low-level `Law` objects remain available for solver tests; compiling a saved
   relation does not admit it. Source projections under audit retain their
   separate status. No coherence candidate was promoted.
2. **Independent test collection.** Pytest's configuration explicitly includes
   the repository root. `uv run pytest tests/test_lexicon_coherence.py` now passes
   alone: 16 tests. The import no longer depends on another test mutating PATH.
3. **Bank review and repair diagnostic.** All eight banks receive separate
   three-option accounts, batched into at most five fields per call. A missing
   component is located within its bank. A scoped `completion_domains` contract
   can permit a legal fill; the solver then runs again and all coverage accounts
   are reconsidered. Missing contracts, unresolved choices and limits stay
   explicit. Current source recipes do not yet supply those completion domains.
4. **No promotion from reassurance.** Model bank accounts and blanket proposed
   silence are kept in `provisional_vector`/`provisional_closure`. They cannot
   create `candidate_vector` or `CANDIDATE_COMPLETE`. An exportable candidate
   requires all domains resolved before blanket closure, possibly through
   bounded model fills and subsequent symbolic propagation. A synthetic closed
   problem verifies that one typed fill can settle its coupled partner and emit
   the complete representation; it is not an English rule or lexical proof.

## Live known-omission control — FAILED

`intact.json` and `remove_FEEL.json` contain the exact native typed sources,
requests, schemas, model identity/digest, answers, fixed states and before/after
domains. The configured backend was `gemma4:e4b-it-q4_K_M`.

- Intact *happy*: SOMETHING:0, KIND:0, GOOD:+1, FEEL:+1, INTENSITY:+1.
- Damaged control: the same record with FEEL deliberately withheld.
- Observed: the model answered ACCOUNTED for **all eight banks in both cases**.
  It did not detect or repair the known omission.

The control was run directly against the coverage diagnostic to inject the
fault. The source-based normal constructor still forces FEEL for this reading.
The negative result establishes that the model checklist cannot license silence;
it does not establish that the backend can never make a useful bounded choice.
The control's exact implementation snapshot digests are in each JSON. They
precede the constructor's completion-boundary correction; no semantic success is
claimed from those receipts.

The corrected real entry point was then run:

```sh
uv run python -m gse.lexicon_builder build --words happy \
  --output docs/verification/lexicon-rebuild/review-repair-2026-10-25/live-cli
```

Result: PARTIAL, `completion_status:UNPROVEN_COVERAGE`, two diagnostic model
calls, a retained provisional proposal and **zero exported vectors**. The five
source-forced states above remain intact. The manifest's implementation hashes
matched the current files when checked after the run.

## Verification and limits

- 92 focused tests passed: builder foundation, native constraints, atomics,
  typed workflow, bank review/repair, artifact representation, NUMBER,
  source coherence, admission regression and existing Detective-generated
  builder tests. Pytest reported one existing Hypothesis directory warning.
- Admission regression exercises atomic and word paths, and confirms that an
  explicitly admitted test relation actually changes the resolution.
- MUST-NOT tests cover incomplete bank review, unresolved review, multiple
  omissions, wrong-bank options, illegal unpaired repair, exhausted repair
  budget, accidental template export and unapproved-law execution.
- Detective: `law_admission_status` COMPLETE, 9/9 killed;
  `bank_coverage_status` COMPLETE, 28/28 killed. These pin pure decisions, not
  semantic completeness. The coverage style plan was advisory with no funded
  rewrite; decompose found no separable block; survey found no trapped pure
  decision. The larger review function has authored transport/propagation tests,
  not a claimed mutation-complete certificate.
- Scoped pinned Ruff check and format passed; `ty check gse/lexicon_builder`
  passed. No full repository suite, speedup, production promotion or full
  lexical construction is claimed.

## Remaining construction work

Complete and connect the actual bank-law/atomic-profile knowledge. Bring native
source categories, roles, morphology and frame constraints into the same reading
state, including noun and prime routes. Treat sentence frames as scoped
realizations rather than independent established senses. Generate the small
surviving decisions from those constraints and repropagate each checked fill.
Then demonstrate complete non-atomic definitions and both omission/addition
controls before the 1,000-word quality run. The source-coherence catalog is
discovery evidence to use in that work, not a populated bank-law registry.

The central omission is this knowledge and wiring, not JIT, SQL throughput,
JSON validity or a shortage of verification infrastructure.
