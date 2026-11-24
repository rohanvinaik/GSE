# Design: GSE-00 capability map and package organization

Evidence below was measured on 2026-11-23 at `67c49b0`: an AST import graph of `GSE/` (288 modules, 87,187 lines, `GSE/_archive/` excluded), a coverage trace of consumer-style calls, and the test suite. "Latest substantive change" excludes repository-wide sweeps (the Oct 4 format and lint commits, the Nov 23 rename and format commits). The `__main__` modules and `curation/validation/__init__.py` show Nov 23 only because the rename recorded them as delete-and-add.

## Current state

### Pass brief (workflow §0)

| Field | Content |
|---|---|
| Objective | A reproducible, documented, organized GSE: a capability map, certainly-dead code retired, modules and tests arranged by subsystem, consumers bound through one interface (USER_INTENT) |
| Protected behavior | Every entry point's output (the recorded probe), every stored identifier and hash, the active lexicon's replay, and each live test's outcome |
| Permitted change | Same-answer reorganization and retirement only; no semantic change. Retiring the upstream constructor removes its release-format reader, which no data uses |
| Workload | The probe's sentences and commands; the full suite; the active lexicon's replay; the consumer repositories' import sites |
| Entry point | `python -m GSE.cli`; `GSE-lexicon`; `GSE-spellcheck-mcp`; the Python API that consumers import |
| Environment | Python 3.14.7 (uv-managed), `uv sync --locked`; macOS case-insensitive disk, checked on a case-sensitive clone where names matter |
| Gate | `scripts/ci_local.sh` locally and in `.github/workflows/ci.yml` |
| Unknowns | `resolve_document` and narrative compression (**UNMEASURED**: no `data/genealogy.db`); the experiments' intended consumers; the consumer interface (decision 3) |

### Setup receipt (2026-11-24)

Codes are the workflow's: READY, MISSING, STALE, CONFLICT, UNVERIFIED. Each row names the check that established it. The receipt describes the committed tree; the working tree also holds the owner's lexicon session's uncommitted edits.

| Operation | Code | Evidence |
|---|---|---|
| Dependency resolution | READY | `uv lock --check`: 82 packages resolved. Prism reports the lock STALE by file time after the `pyproject.toml` edit; the package manager's own check governs |
| Known vulnerabilities | READY | `pip-audit` over `uv export --all-extras --all-groups`: none. `en-core-web-sm` (URL dependency) is UNVERIFIED |
| Workflow security | READY | `zizmor --offline .github/workflows`: no findings |
| Local gate | READY | ruff check and pinned ruff format check pass on the committed tree; the full suite per commit is compared test by test (tasks.md) |
| Remote gate (CI) | CONFLICT | Red since the Nov 23 pushes; local and remote disagree because CI lacks local data. 64 failures at `67c49b0`, itemized under *CI* below |
| Secret scanning | MISSING | Prism: secrets unconfigured; neither `detect-secrets` nor `gitleaks` is installed (card #35) |
| License | CONFLICT | `README.md` says MIT; there is no `LICENSE` file (repo-review PY003) |
| pytest warnings policy | MISSING | No `filterwarnings` (repo-review PP309; card #34) |
| Pre-commit hooks, task runner | MISSING | repo-review PY006, PY007 (cards #36, #37) |
| Ruff rule set | STALE | Bugbear not selected; `target-version` duplicates `requires-python` (repo-review RF101, RF002; card #38) |
| Declared dependencies | CONFLICT | deptry, in the project environment: live modules import undeclared `torch` (the register-router experiments, `qwen_client`), `transformers` (`qwen_client`) and `amrlib` (`nlp/sentence_parser`); scripts import undeclared `datasets`, `ijson`, `gensim`, `sentence_transformers`. Matches card #152 (gates-23). deptry needs the archive and record exclusions the other tools have before its 224-issue report is readable |
| Layer contracts | MISSING | Import Linter is installed but the project has no `[tool.importlinter]` contract (task 4.4) |
| Detective state | STALE | Generated-test content hashes predate the rename; five certificate entries name the archived constructor |
| LintGate files | STALE | `.claude/rules/lg_*.md` are tracked but rewritten on every tool call (card #45) |
| Machine inventory | STALE | SetupAtlas last scanned 2026-05-03; not used as evidence for this session |
| Data: active lexicon | READY | `data/lexicon_active.json` → `sparse-release-021.db`; replay 401,596 entries, 0 mismatches (2026-11-23) |
| Data: `genealogy.db` | MISSING | Blocks `resolve_document`, narrative compression and the Genesis bridge script |
| Data: spelling and frequency resources | MISSING | HDC speller cache, `spell_entities.db`, the Wiktionary wordlist with `frequency.db`; with absent `torch`, these account for the suite's skips |
| Model transport (Ollama) | UNVERIFIED | Not exercised in this pass |

#### CI

At `67c49b0`, 64 tests fail in CI:

- 45 (`UNKNOWN_BANK:YOU`, body-scope and scope-admission tests) come from the in-progress I/YOU projection and also fail with full local data.
- The other 19 pass locally with `data/` present. 3 fail because `load_all_sources` (since `1a520dd`) loads the NSM chart without the guard the optional sources have, so a checkout without the chart raises instead of keeping the built-in grammar. The chart loader deliberately refuses a revision mismatch (`NSM_CHART_SOURCE_REVISION_MISMATCH`); whether an absent chart should refuse or be skipped is the owner's lexicon-design call. 3 PropBank load tests raise `LookupError` because CI has no PropBank corpus and patching NLTK's lazy loader forces a load; these tests predate Oct 26, when CI passed, and the change is not yet explained. 13 epoch, linkage, catalog, publication and runtime-audit tests read local lexicon data (frequency database, NSM chart).

### Subsystems

| Subsystem | Modules | Lines | Runtime status (2026-11-23 trace) | Latest substantive change |
|---|---:|---:|---|---|
| substrate | 8 | 3,119 | 6 observed, 2 reachable, not observed | 2026-11-23 |
| lexicon | 14 | 3,779 | 13 observed, 1 tooling | 2026-11-14 |
| parse | 7 | 1,789 | 7 observed | 2026-11-14 |
| encode | 11 | 3,580 | 10 observed, 1 reachable, not observed | 2026-11-23 |
| symbolic | 20 | 7,858 | 20 observed | 2026-11-23 |
| document | 15 | 3,390 | 15 observed | 2026-11-14 |
| spellcheck | 13 | 2,522 | 6 observed, 2 test-only, 5 unreferenced | 2026-11-14 |
| bridge | 15 | 3,294 | 13 observed, 2 reachable, not observed | 2026-11-23 |
| apps | 19 | 4,364 | 12 observed, 3 tooling, 4 unreferenced | 2026-11-14 |
| verification | 3 | 1,167 | 2 observed, 1 test-only | 2026-11-14 |
| lexicon-build | 100 | 32,699 | 25 observed, 24 reachable, not observed, 41 tooling, 6 test-only, 4 unreferenced | 2026-11-23 |
| legacy | 63 | 19,626 | 16 reachable, not observed, 6 tooling, 23 test-only, 18 unreferenced | 52 of 63 last changed 2026-06-14; latest 2026-10-29 (two `curation/llm` modules) |

The owner's three tiers map onto these as follows. **Tier 1, the text-to-math engine:** substrate, lexicon, parse, encode, symbolic and document. **Tier 2, side extensions:** spellcheck (SymbolicSpellCheck) and bridge (Genesis/Regenesis). **Tier 3, beyond the core:** apps. Apps cover genre and register classification (`discourse.registers`, `router`, `nested_router`, `infer`, `encoders.som_genre`), the trained register router (the current trained model), Janus figures (`pragmatics`) and the LSAT-style reasoning showcase (`demo.reasoning` over `symbolic.inference`). Lexicon construction and the legacy stack sit outside the three tiers.

"Observed" means the coverage trace executed the module. The trace exercised encoding and the CLI, the `from_trace → resolve → evaluate_tree` spine, `emit_contract`, document intake and utterance events, the statement healer, `KnowledgeBase` queries, `demo.reasoning`, cassettes, healing and the MCP tools, lexical evidence and the personal dictionary, `encode_text`, the register classifier and Janus figures. **UNMEASURED:** `resolve_document` and narrative compression, which need the missing `genealogy.db`; and the constructors, which run offline and are measured instead by the build replay and their tests.

### Observed paths from input to output

1. **Sentence.** `GSEEncoder.encode` runs the native front end (`nlp.native`), looks up definitions through the active lexicon (`lexical_evidence`, read via `curation.lexicon_builder.storage`) and binds vectors (`vectors_v2`, `primitives_v2`), producing an `OperationTrace`. Then `symbolic.from_trace`, `resolve` and `evaluate_tree` produce a typed predicate tree, and `symbolic.emit.emit_contract` turns it into the Genesis/Regenesis contract.
2. **Document.** `discourse.profile.split_sentences` and `discourse.speech.encode_document_utterances_traced` / `encode_document_utterance_events` produce per-utterance traces and trees. `resolve_document` and cassette composition (`MultiScaleDoc`) then give the document reading that SquishOS consumes.
3. **Healing.** `nlp.heal.suggest` / `nlp.spellcheck` produce the corrected text and a decision ledger; the MCP server wraps them.
4. **Register.** `discourse.profile.text_profile` feeds the nested router, which yields a register label (`encoders.som_genre`).
5. **Reasoning.** Resolved trees go into `symbolic.inference.KnowledgeBase`, which answers `is_a` and `greater` queries with derivations.
6. **Build, offline.** Sources (`curation.external_sources`) go through `curation.lexicon_builder` to a definition database, which `data/lexicon_active.json` activates.

### Dependency problems

- **The runtime reads the lexicon through build tooling:**
  - `lexical_evidence`, `api.encoder` and `nlp.spellcheck` import `curation.lexicon_builder.storage`;
  - `api.encoder` imports `curation.external_sources.gse_closed_class`;
  - `symbolic.lexical_grounding` imports `curation.lexicon_builder.foundation`;
  - `curation` and `frequency_integration` import `curation.lexicon_db`.
- **Cycles:** `encode` ↔ `symbolic` (the encoder imports modality and tier vocabularies), and `symbolic` ↔ `bridge` (`symbolic` re-exports healer and narrative).
- **Core imports an app:** `discourse/__init__` imports `discourse.registers`.
- **The package root advertises the legacy stack:** `GSE/__init__.py` lazily exports `merkle`, `patterns`, `pipeline_v2` and `encoders`.
- **Consumers import functions GSE does not publish:** `GSE.discourse.document.claim_records` (never existed) and `GSE.nlp.spellcheck.spelling_protection`. SquishOS guards both, which hides the gap.

### Consumers today (measured 2026-11-24)

An AST pass over each consumer repository's Python files, at their current commits.

| Project | How it reaches GSE | What it uses |
|---|---|---|
| Regenesis | Imports through a hardcoded checkout path; subprocesses; `GSE_ROOT` | Encoder; cassettes, deck and cheat-sheet; document reading; spell check; statement healer; narrative compression; `emit_contract` (26 names from 9 modules) |
| SquishOS | Subprocesses into GSE's environment; `GSE_REPO` | 28 names from 16 modules, including internals (lexical evidence and its data path, primitive registries, claim-key version, serialization, personal dictionary); imports `GSE.discourse.document.claim_records` and `GSE.nlp.spellcheck.spelling_protection`, which do not exist (guarded) |
| Genesis | Python bridge scripts in `gsebridge/` that import GSE (how the Java side starts them was not traced) | Encoder, the symbolic spine, `emit_contract`, `emit_contract_with_variables`, `encode_text` |
| StoryClaude | Imports through a hardcoded checkout path | Encoder, document reading, healer, narrative, including the private `_op_of` |
| ShortcutForge | Imports through a hardcoded checkout path | Encoder |
| StartupForge, CareerForge | Subprocesses into GSE's own Python | Text-structure (genre) encoding |
| ARC | Import | `GSE.primitives`, which exists only in `GSE/_archive/` |
| ARC_AGI_3, cell_tracking | `GSE_ROOT` and `GSE_REPO` respectively | Location only |

GSE itself reaches Sparse Wiki by ingesting its world data into local tables (`scripts/build_genealogy_db.py`; DATED_REPORT, `docs/program/BUILD_GAPS.md`, world-ownership row), not through an interface. That is GSE-02's work.

### Superseded code (dates and runtime evidence)

| Older code | Replaced by | Older code's status |
|---|---|---|
| `parsing/` (constraint-propagation parser, Jun 14) | `nlp/native` (deterministic front end, Jun 20–Nov 14) took the live path | test-only; not confirmed dead |
| `composition/` (HDC composer, Jun 14) | composition inside `api/encoder` took the live path | test-only; not confirmed dead |
| `curation/llm/` (Ollama decomposition and the Qwen client, Jun 14–Oct 29) | partly, by the `curation/lexicon_builder` model protocol, which still uses `ollama_client` as its transport | **unfinished experiment, kept** (decision 5); test-only |
| `curation/decomposition/` (Jun 20), `curation/pipeline/`, `curation/validation/`, `curation/constraint_aggregation/` (Jun 14) | the current constructors | old build tools: used only by `build_clean_layer2`, the old curation CLI, scripts and, for `constraint_aggregation`, the uninstalled daemon |
| `pipeline_v2`, `merkle/`, `patterns/`, `teaching/`, `profiles/`, with the `cache/` and `orchestration/` re-export shims (the learning-network stack, Jun 14) | not replaced: the deterministic engine took the live path | **unfinished experiment, kept** (decision 5); never observed; reachable only through the root's lazy exports |
| `evaluation/`, `verb_templates`, `benchmarks/` (Jun 14) | none in use | tooling, test-only or unreferenced; not confirmed dead |
| `demo/` other than `reasoning` | none | unreferenced |
| `GSE/cli.py` | the `GSE/cli/` package, which shadows it on import | **archived** (task 1.1) |
| eight scripts importing modules that exist only in `GSE/_archive/` | none needed | **archived** (task 1.2) |
| `GSE/lexicon_builder` (upstream constructor, Oct 24–26) | `GSE/curation/lexicon_builder` (Oct 29–Nov 23), decision 1 | **archived** (task 1.3). The retained builder imported nothing from it and shared no function with it, checked with names and literals stripped |

`nlp/sentence_parser` (Jun 14–24, the spaCy/AMR/CCG bridge) still loads on the encoding path. Its live surface has to be traced before it is classified.

### Test suite

314 test files and about 7,640 tests take about six and a half minutes. By imports, 164 files exercise one subsystem, 150 exercise two to six, and 11 import no GSE module. Single-subsystem files: lexicon-build 81, legacy 28, symbolic 12, lexicon 11, parse 11, substrate 10, encode 4, apps 3, spellcheck 3, document 1. A known no-op: `test_returns_existing_gse_data_path` (`tests/test_GSE_curation_frequency_integration.py`) ends in `pass`.

Coverage of the full suite puts the testing where it is least needed. Tests execute 55 of the 63 legacy modules. No test executes these live modules:

- the trained register router (`discourse.router`, `discourse.nested_router`);
- Janus figures (`pragmatics.*`);
- four statement-healer lenses and `healer.recollect`;
- `symbolic.variables`, which Genesis imports;
- `demo.reasoning`;
- the `mcp` package module.

The census should add obligations for those before removing tests elsewhere.

## Target structure (proposal)

Each subsystem is one directory under `GSE/` whose name states its job. A subsystem imports only those to its left:

`substrate` ← `lexicon` ← `heal` ← `parse` ← `encode` ← `symbolic` ← `document` ← {`bridges`, `apps`}

`build` imports `substrate` and `lexicon` only; nothing at runtime imports `build`. `cli`, `mcp` and `verification` sit on top.

| Target | Job | Comes from |
|---|---|---|
| `GSE/substrate/` | Sparse vectors, bases, primitive registry, scales | `vectors_v2`, `primitives_v2`, `scale_definition`, `prime_projection`, `scales/`, `namespace` |
| `GSE/lexicon/` | Read the active lexicon and lexical facts | `lexicon_resource`, `lexical_evidence`, `frequency`, `lexicon/*`, `curation/schema`, `curation/personal_dictionary`, `curation/frequency_integration`; the read side of `curation/lexicon_builder/storage` and the prime basis from `foundation`; the closed-class catalog (`gse_closed_class`, `tier_0_dispatch`) |
| `GSE/heal/` | SymbolicSpellCheck: correction, healing, keyboard HDC | `nlp/spellcheck*`, `nlp/heal`, `nlp/hdc_speller`, `nlp/healing_resources` |
| `GSE/parse/` | Deterministic front end | `nlp/native`, `morphology`, `contractions`, `linkers`; `sentence_parser` after review |
| `GSE/encode/` | Text to `OperationTrace` and back | `api/*`, `structure`; the modality and tier vocabularies move down out of `symbolic` |
| `GSE/symbolic/` | Trace to typed claims, resolution, modality, inference | `symbolic/*` without the bridge modules |
| `GSE/document/` | Multi-sentence reading and multiscale grounding | `discourse/speech`, `intake`, `split_sentences`; `cassettes/*` |
| `GSE/bridges/` | Genesis and Regenesis contracts | `symbolic/emit`, `variables`, `healer/`, `narrative` |
| `GSE/apps/` | Register classification, Janus figures, the reasoning showcase | `discourse/registers`, `router`, `nested_router`, `infer`, `text_profile`; `encoders/*`; `pragmatics/*`; `demo/reasoning` |
| `GSE/build/` | Offline lexicon construction | `curation/lexicon_builder`, `curation/external_sources` minus the catalog, `curation/cli`; `curation/build_*` and `curation/lexicon_db` pending task 1.5 |
| `GSE/cli/`, `GSE/mcp/`, `GSE/verification/` | Entry points and proof suites | unchanged |
| `GSE/_archive/` | Retired code, kept for provenance | only code that is certainly dead (decision 2) |
| experiments | Unfinished experiments (decision 5) | the learning-network stack and `curation/llm`; their place is the owner's call (task 6.2) |

## Constraints on moving modules

Moving a module must not change any stored identifier. These name module paths today:

1. **Closed-class provenance labels.** `GSE.lexicon.pronouns`, `GSE.lexicon.function_words`, `GSE.curation.build_clean_closed_class`, `GSE.curation.external_sources.tier_0_dispatch` and `GSE.nlp.native` are literal strings inside hashed record features. They stay byte-identical; they become named constants and are never derived from `__name__`.
2. **Source keys.** `gse_closed_class` is both a stored source key and the module name: `curation.lexicon_builder.evidence` imports each source module by its key. An explicit source registry replaces import-by-key before `external_sources` moves.
3. **Detective.** `tests/detective/certificates.json` is keyed by source path, and its generated tests import by path. Regenerate them for each moved module.
4. **Documents cited in stored provenance.** `docs/program/LEXICON_CONSTRUCTION_DESIGN.md` is cited by path in stored provenance and `foundation.json`, so it does not move. `REFERENCE_MANIFEST.json` pins documents, not modules.
5. **Readings runners.** Tests import them as `docs.readings.*` modules; they stay where they are as records.
6. **Consumers.** Consumer imports move in the same commit, or keep working through public modules (decision 3).
7. **Package exports.** `GSE/__init__.py` keeps only the public surface.
8. **Format identifiers** (`GSE.lexicon-builder/1`, …) are not module paths and do not change.
9. **Package data.** The only package-data entry named the archived constructor and was removed with it (task 1.3).

## Test scoping

- Tests live under `tests/<subsystem>/`. A test that exercises several subsystems lives with the highest one, so `uv run pytest tests/<subsystem>` covers a subsystem and its dependents' tests.
- `scripts/ci_local.sh` stays the full gate and CI keeps running it; a scoped command runs one subsystem.
- For local cycles, a change-impact selector (`pytest-testmon` via `uv run --with`) reruns only the affected tests.
- The census (durations, overlap, stale and no-op tests) uses pytest durations and coverage contexts. Removals keep every named obligation, and use Detective where its function contract applies, per the engineering workflow. No test is deleted on an overlap score alone.
