# Tasks

Every task is one reviewable commit on `main`. It updates every importer: the package, tests, scripts, readings runners and consumer repositories. It must pass all of these gates before the next task starts:

- the full suite in a fresh case-sensitive clone;
- a replay of the active lexicon build (0 mismatches);
- entry-point output identical to the recorded probe;
- SquishOS's GSE-facing tests, with no new failures;
- `scripts/check_program.py`;
- CI green.

## 0. Decisions and preconditions

- [ ] 0.1 Owner decisions 1–4 in proposal.md are recorded here.
- [ ] 0.2 The concurrent Codex session is paused; `main` is clean and equals `origin/main`.
- [ ] 0.3 CI is green on `main`: the lexicon work settles the 45 tests its I/YOU projection contradicts; `load_all_sources` treats the NSM chart as optional like every other source; the PropBank tests stop depending on the corpus being installed; the 13 tests that need local lexicon data use a fixture or skip when it is absent.

## 1. Pin what must not change

- [ ] 1.1 The five closed-class provenance labels become named constants with a test that pins their exact bytes.
- [ ] 1.2 An explicit source registry replaces importing source modules by stored key (`curation.lexicon_builder.evidence`).
- [ ] 1.3 `GSE/__init__.py` exports only the public surface chosen in decision 3.

## 2. Make dependencies point one way (no files move)

- [ ] 2.1 The read side of the lexicon lives in the runtime: the definition reader (`runtime_lookup`, `read_entries`, format check), the prime basis and the closed-class catalog. The constructors import them; the encoder, lexical evidence, spell checker and lexical grounding stop importing `curation.*`.
- [ ] 2.2 The vocabularies the encoder needs (modality, clause tiers) move below `symbolic`, removing the `encode` ↔ `symbolic` cycle.
- [ ] 2.3 `symbolic` stops re-exporting bridge modules, and `discourse/__init__.py` stops importing `discourse.registers`.
- [ ] 2.4 Settle the two consumer imports GSE does not publish (`GSE.discourse.document.claim_records`, `GSE.nlp.spellcheck.spelling_protection`) with the SquishOS owner: publish them or remove the imports.

## 3. Retire superseded code (decision 2)

- [ ] 3.1 Move the legacy modules in design.md to `GSE/_archive/` and their tests to `tests/_archive/`; record the move in `docs/ARCHITECTURE.md` §7.
- [ ] 3.2 Trace the live surface of `nlp/sentence_parser` before classifying it.
- [ ] 3.3 Retire `GSE/cli.py`, which the `GSE/cli/` package shadows.

## 4. Move subsystems, in dependency order

- [ ] 4.1 `substrate`
- [ ] 4.2 `lexicon`
- [ ] 4.3 `heal`
- [ ] 4.4 `parse`
- [ ] 4.5 `encode`
- [ ] 4.6 `symbolic`
- [ ] 4.7 `document`
- [ ] 4.8 `bridges`
- [ ] 4.9 `apps`
- [ ] 4.10 `build` (after decision 1)

For each move, also regenerate the Detective tests and certificates for the moved modules.

## 5. Tests by subsystem

- [ ] 5.1 Move tests to `tests/<subsystem>/` by the rule in design.md; document the scoped command and impact selection beside the gate.
- [ ] 5.2 Run the suite census (durations, overlap, stale and no-op tests); list removal candidates with their obligations. Remove only what keeps every obligation, using Detective where its function contract applies.

## 6. Documentation

- [ ] 6.1 `docs/ARCHITECTURE.md` describes the new tree; the stale root `README.md` follows it.
