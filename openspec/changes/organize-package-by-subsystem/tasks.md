# Tasks

Every task is one reviewable commit on `main` that updates every importer: the package, tests, scripts, readings runners and consumer repositories. Before the next task starts, it must pass:

- the full suite in a fresh directory, compared test by test with the previous commit;
- a replay of the active lexicon build (0 mismatches) when lexicon reading or construction code changed;
- entry-point output identical to the recorded probe;
- `scripts/check_program.py`;
- CI green, once 0.3 holds.

No task edits the owner's concurrent lexicon session's files (`GSE/curation/lexicon_builder/`, `docs/program/`, `openspec/changes/lexicon-symbolic-foundation/`, `scripts/run_lexicon_epochs.py` and its tests) or disturbs its running processes.

## 0. Decisions and preconditions

- [x] 0.1 Owner decisions recorded in proposal.md (2026-11-24).
- [ ] 0.2 The interface design session with the owner (decision 3).
- [ ] 0.3 CI is green on `main`:
  - the lexicon work settles the 45 tests its I/YOU projection contradicts;
  - the owner decides whether an absent NSM chart refuses (the integrator tests then supply or skip it) or is skipped like the optional sources;
  - the PropBank tests stop depending on the corpus being installed;
  - the 13 tests that need local lexicon data use a fixture or skip when it is absent.

## 1. Retire what is certainly dead (decision 2)

- [x] 1.1 `GSE/cli.py`, shadowed by the `GSE/cli/` package (`973d97f`).
- [x] 1.2 Eight scripts that import modules existing only in `GSE/_archive/` (`af6e230`).
- [x] 1.3 The upstream constructor `GSE/lexicon_builder/` (decision 1), with its tests, gate scripts and Detective-generated tests. `GSE-lexicon` runs the retained builder. Flat rows from its release format are refused as `RETIRED_RELEASE_FORMAT`, with a MUST-NOT test. Full suite before and after: 7,940 → 7,486 collected (455 tests left with the 32 archived files; 1 added); every shared test kept its outcome; entry-point probe identical apart from the checkout path; active-lexicon replay 0 mismatches over 401,596 entries (`00657d0`).
- [ ] 1.4 Owner decision (card #47): `daemon/` (not installed; would write 0 for "unknown") together with `deploy_to_desktop.sh`, which installs it, and the root `lexicon.db` stub.
- [ ] 1.5 Owner decision: the flat-lexicon builder (`curation/build_clean_*`, `curation/lexicon_db`, `data/lexicon_clean.db`), which the runtime still uses when the active pointer is absent.

## 2. Setup receipt and pass brief

- [x] 2.1 Pass brief per the workflow's §0 (design.md).
- [x] 2.2 Setup receipt with remedy codes (READY / MISSING / STALE / CONFLICT / UNVERIFIED), from Prism, SetupAtlas and LintGate, plus the repo-hygiene kit: pip-audit over the lock with all extras and groups, zizmor, a secret scan, sp-repo-review, deptry. Each finding is checked at its source before it is recorded. LintGate's project check ran on a clean extract of `9a773a4`, so the owner's working tree was untouched. No secret scanner is configured in the project (recorded as MISSING); this pass scans each commit through `uvx`.
- [x] 2.3 Add `[tool.deptry]` exclusions matching the other tools' archive and record exclusions, so its report is readable (`1cd6dc8`: 224 reported issues become 25 real findings).

## 3. Pin what must not change

- [x] 3.1 The five closed-class provenance labels become named constants with a test that pins their exact bytes (`7a3eec7`; all 213 closed-class records byte-identical).
- [ ] 3.2 An explicit source registry replaces importing source modules by stored key (`curation.lexicon_builder.evidence`). This touches the owner's lexicon session's files; schedule it with the owner.

## 4. Make dependencies point one way (no files move)

- [ ] 4.1 The read side of the lexicon lives in the runtime: the definition reader (`runtime_lookup`, `read_entries`, format check), the prime basis and the closed-class catalog. The encoder, lexical evidence, spell checker and lexical grounding stop importing `curation.*`.
  - [x] The definition reader and its format identifier moved verbatim to `GSE/lexicon/definitions.py`; `storage.py` re-exports them for the builder. The encoder, lexical evidence, the active-lexicon resolver and the spell checker read it there (`56c81ba`; full suite identical, replay 0 mismatches).
  - [x] `GSE/curation/__init__.py` no longer loads the flat-lexicon builder when a runtime module under it is imported (`8fc200a`).
  - [ ] The closed-class catalog, which is assembled from build-side tables (`EXPONENTS`, `TIER0_FORMS`, `ZERO`, `PERIPHRASTIC_MODALS`, `canonical_decomposition`); those tables move with it, under the pinned provenance labels.
  - [ ] `symbolic.lexical_grounding` (prime basis, catalog, closed-class catalog), once the owner's lexicon session has committed its edits to that file.
- [x] 4.2 The cycle ran through `GSE/api/__init__.py`, which imported the encoder eagerly; it now loads the encoder and decoder on first use, so the trace types no longer pull in the encoder (`65dcf62`). Measured, the encoder is meant to use the symbolic layer (grounding inside `encode()`), so no vocabulary moves.
- [ ] 4.3 `symbolic` stops re-exporting bridge modules, and `discourse/__init__.py` stops importing `discourse.registers`.
  - [x] The register names in `discourse/__init__.py` load on first use (`65dcf62`).
  - [ ] The symbolic package's `emit` re-export and coherence's two bridge functions move with the interface (task 5.4); see design.md, *Dependency problems*.
- [x] 4.4 Five Import Linter contracts in `pyproject.toml` state the dependency direction, and the gate runs them; each remaining violation is a recorded exception naming the task that removes it (11 at first, 7 after the definition reader moved; `3464b35`).

## 5. The consumer interface (decision 3)

- [x] 5.1 Principles agreed with the owner (2026-11-24) and written as `specs/gse-interface/spec.md`.
- [ ] 5.2 Propose the concrete request and response shape (slip fields, request kinds, departments, outcome and refusal names, contract versioning) for the owner's review. No code before that review. Proposal written in design.md, *Interface shape* (2026-11-24); awaiting review.
- [ ] 5.3 Build the intake, routing and written responses; departments answer under the existing capability specs.
- [ ] 5.4 Move each consumer's calling code to the interface, one consumer per commit, in the consumer's own repository (design.md, *Consumers today*), including the three imports of modules that do not exist.
- [ ] 5.5 GSE's own calls to Sparse Wiki go through Sparse Wiki's interface (with GSE-02).

## 6. Move subsystems, in dependency order (after 5)

- [ ] 6.1 `substrate`, `lexicon`, `heal`, `parse`, `encode`, `symbolic`, `document`, `bridges`, `apps`, `build`: one commit each, with the Detective tests and certificates for moved modules regenerated by Detective.
- [ ] 6.2 Experiments (decision 5) get their place in the structure from the owner.

## 7. Tests by subsystem

- [ ] 7.1 Move tests to `tests/<subsystem>/` by the rule in design.md; document the scoped command and impact selection beside the gate.
  - [x] Scoped runs without moving files: every test is marked with the GSE areas its file imports, derived at collection (`tests/conftest.py`), so `uv run pytest -m symbolic` runs one area; `pytest-testmon` runs only tests affected by changed code; both documented in the README (`351fce1`).
  - [ ] Test files move into `tests/<subsystem>/` with their modules (task 6), so they move once.
- [ ] 7.2 Suite census: durations, overlap, stale and no-op tests, each candidate with its suite candidate record. Remove only what keeps every obligation, with Detective where its function contract applies.
  - [x] Census measured and recorded (`docs/readings/2026-11-24-test-suite-census/`).
  - [x] First decisions: two exact twins removed with their obligations kept, one empty test rewritten, five tests strengthened, 14 assertion-free tests kept with their stated obligations (census record §8).
  - [ ] The 693 identical-reach clusters, 2,497 contained tests and 545 zero-reach tests: read each, with Detective's audit where its function contract applies, before any removal.
- [ ] 7.3 Add obligations for the live modules no test executes (design.md, *Test suite*).

## 8. GSE-00 completion receipt

- [ ] 8.1 Fixtures that protect existing correct readings, run through the real entry points.
- [x] 8.2 Reproduce the dated proof-packet demonstrations, or mark each unverified (`docs/readings/2026-11-24-proof-packet-rerun/`, at `5792ca3`): 4 reproduced (§1, §3, §4, §6), 1 changed (§7), 4 broken (§8–§11), 6 unverifiable here (§2, §5, §12–§15; `genealogy.db`, `spell_entities.db` and `frequency.db` are missing, or the packet gives no command). §8–§11 break because the active definition lexicon holds several definitions for each word they use, so ordinary encoding attaches no word meaning; they reproduce on the flat `lexicon_clean.db`.
- [ ] 8.3 A per-class outcome ledger (identified / abstained / wrong / unavailable / partial), attached to issue #166 with source, data and code hashes.

## 9. Documentation

- [ ] 9.1 `docs/ARCHITECTURE.md` describes the final tree; the root `README.md` follows it.
