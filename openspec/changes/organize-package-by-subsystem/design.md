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

At `5792ca3`, 162 tests fail in CI (79 at `e9649ad`). All 60 newly failing test IDs come from the lexicon session's work-in-progress commit `8bfb980`, which extended `GSE/symbolic/lexical_grounding.py`: ordinary encoding now reaches `select` → `_primary_frame_support` → `_primary_frames`, which reads the NSM chart from the untracked `data/external/references/`. On any checkout without that file, CI included, `GSEEncoder.encode` raises `FileNotFoundError` rather than a named refusal. Bisected in clean extracts holding only tracked files: one degree-runtime test passes at `e9649ad` and fails at `8bfb980` and at every later commit; the six affected test files that commit did not touch go from 192 passed to 52 failed. The other new failures are in the session's new `test_runtime_native_identity_controls.py` (19) and in `test_checkpoint_canonical_projection.py` (3), which read local run data. The structural commits of this change (lazy initializers, the definition-reader move, the contracts) leave the failing set unchanged. Whether encoding should refuse by name or keep the built-in grammar when the chart is absent is the same owner's lexicon-design call as above.

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
- **A cycle through a package initializer (fixed 2026-11-24).** The symbolic layer imports the trace types from `GSE.api`, and `GSE/api/__init__.py` imported the encoder eagerly, which itself uses the symbolic layer, so every trace-type import ran through the encoder. The encoder using symbolic grounding inside `encode()` is the intended direction; the eager initializer was not. It now loads the encoder and decoder on first use.
- **The symbolic package re-exports the bridge.** `GSE/symbolic/__init__.py` imports `emit` eagerly, and `symbolic.coherence` holds two bridge functions (`emit_contract_with_coherence` and its variable form) that import `emit` and `variables`. Both move with the interface (task 5.4): fifteen GSE tests and a demo import `emit` through the package, and two of its names (`emit`, `predicates`) collide with submodule names, so a lazy initializer would silently change what they return.
- **Core imports an app (fixed 2026-11-24):** `discourse/__init__` imported `discourse.registers` eagerly; the register names now load on first use.
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
| personal-wiki (MentalAtlas) | Imports, lowercase `gse` until 2026-11-24 (the rename sweep missed this repository; fixed in place, untracked); `GSE_REPO` | The spellcheck server's `spell_suggest` at capture; encoder, symbolic spine, document resolution, healer and narrative in its semantic layer |

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

The suite census of 2026-11-24 (commit `8bfb980`) is recorded in [`docs/readings/2026-11-24-test-suite-census/`](../../../docs/readings/2026-11-24-test-suite-census/README.md): cost, per-test coverage clusters, containment, zero-reach tests, assertion-free and duplicate bodies, experiment-only files, fixtures, and what it could not measure. It is advisory; removals follow task 7.2.

## Interface shape (proposal for the owner's review)

Status: proposal for task 5.2. Nothing here is built until the owner has reviewed it. It implements `specs/gse-interface/spec.md` and is derived from the call sites traced on 2026-11-24 (*Call sites and their kinds* below).

### How every project uses GSE (measured 2026-11-24)

| Project | How its work runs | The text it sends | What it needs back | GSE state it changes |
|---|---|---|---|---|
| Genesis (Java) | A conversation: while it reasons it asks for one sentence, rule clause, word list or genre at a time and waits (a resident co-process today); also whole stories | Sentences it has split itself; rule clauses with typed slots (`${name:type}`); words; stories | Predicate contracts and their vocabulary; signed valence per word; genre | None |
| Regenesis | Interactive (MCP tools, the question parser) and corpora (`understand_batch`, with its own staging and resume) | Story files; articles pulled from Wikipedia into memory; prose from MCP callers; single clauses; tokens to spell-clean | Document-resolved contracts; narrative spine; oblique roles; spelling decisions | None |
| SquishOS | One document at a time under a deadline; comparisons of two drafts; an optimization loop that asks for tokens repeatedly | Markdown and prose files it reduces itself, with a source map; its own sentence and paragraph segmentation | The full typed reading joined back to its own units; the heal ledger; word facts; vocabularies. It fingerprints GSE's code and resources and treats a change during a run as a defect | `learn` writes GSE's protected dictionary |
| personal-wiki (MentalAtlas) | Capture (heal what is captured) and a semantic layer over notes | Markdown notes; captured snippets | Healed text; document readings | Not traced |
| StoryClaude | An analysis script | A Claude session transcript (dialogue turns), split with its own regex | Contracts, narrative compression, signal-to-noise | None |
| ShortcutForge | Interactive routing per user prompt, plus bulk encoding of shortcut descriptions with its own disk cache | Short texts | Vectors | None |
| StartupForge, CareerForge | Corpora: a list of short definitions; 1,000+ narratives (through Regenesis); verb harvests | Short texts; documents | Vectors; contracts | None |
| ARC_AGI_3 | Setup and readiness checks | None | Resource states | None |
| MCP clients | Interactive, through GSE's own spellcheck server | Snippets | Healed text | `learn` |

### What that means for the interface

1. **Three ways of working, one door.** A conversation of small requests, a single document under a deadline, and a corpus are all common. One resident process per calling project serves all three. Every response line carries its request's id, so a caller never matches answers by order, and a caller can keep several requests open.
2. **Text arrives in forms, and intake owns them.** Each document declares its form: `prose`, `markdown`, `dialogue` (turns with speakers), `sentences` (already split), `rules` (clauses with typed slots). Intake reduces each form to prose with one splitter (paragraphs, hard wraps, abbreviations; card #13) and records a source map, so every span in a response points into the original file. A project that has its own segmentation can supply it, and the slip records that the segmentation came from the caller. Short texts come many to a file: a corpus file holds one `{"id", "text"}` per line, so a list of definitions or pulled articles is one file, kept as the record.
3. **One state-changing kind.** `learn` changes GSE's protected dictionary for every project. The dictionary's identity is part of GSE's identity in every slip, so a response says which dictionary it was read under, and a kept response whose dictionary has since changed is stale and is read again (`lexical-evidence`: changing a resource invalidates dependent readings).
4. **The slip names what actually answered.** A resident process keeps the code and resources it loaded even if the checkout changes beneath it. Its slips record the loaded identity, and at each docket it compares that with the checkout; on a difference it refuses by name (`GSE_CHANGED_SINCE_LOAD`, with both identities) rather than answer under a label that is no longer true.
5. **Complete, but only for the work asked.** An interactive caller wants one sentence's reading quickly; a corpus caller wants documents read through every scale. A request names the steps to run (healing; word, sentence, paragraph and document scales; cassettes; narrative compression). The response is GSE's complete account of the steps it ran, never a subset tailored to one project, and the slip lists the steps that ran.
6. **One reading, several published forms.** The typed reading (the GSE-06 export), the predicate contract that Genesis and Regenesis walk, and vectors are forms of the same reading. GSE defines and versions each form and lists them through `describe`; a project asks for the forms it consumes.
7. **Plain data only, language-neutral.** JSON lines in and out of a process. Genesis is Java; nothing that crosses depends on Python.
8. **Kept responses are the fixtures.** Regenesis already captures contract fixtures and SquishOS validates events. Written responses are what each project tests against, without GSE.

### The door

A project runs GSE as its own process and never imports it. `$GSE_ROOT/.venv/bin/GSE serve` loads GSE once (card #19) and stays resident. The project writes requests as lines on stdin and reads response lines on stdout; stderr carries logs only. The process does not depend on its working directory: paths are absolute or relative to the file that names them. `GSE_ROOT` is the one variable that locates GSE; Regenesis, StartupForge and ARC_AGI_3 already use it, SquishOS and personal-wiki use `GSE_REPO`, and Genesis hardcodes the path.

### Requests (`GSE.request/1`)

A request is a docket of documents or a snippet.

```json
{"contract": "GSE.request/1", "kind": "read", "id": "run-7",
 "documents": {"manifest": "runs/run-7/documents.jsonl"},
 "options": {"steps": ["heal", "word", "sentence", "paragraph", "document", "cassettes"], "forms": ["reading", "contract"]},
 "destination": "runs/run-7/gse"}
```

- **Documents** are listed in a manifest, one line each: `{"id", "path", "form"}` for a file, or `{"id", "corpus": "<file>", "form"}` for a corpus file of `{"id", "text"}` lines. GSE opens every file itself, reads the original bytes, records their hash, and refuses an unreadable one by name (`INVALID_INPUT`, with the byte position).
- **Snippets** are inline and answered inline, for interactive use: `{"input": {"sentences": [...]}}`, `{"input": {"rules": [...], "variables": {...}}}`, `{"input": {"words": [...]}}` or `{"input": {"texts": [...]}}`.
- **`destination`** is a directory in the requesting project. GSE writes each document's response there: the formal written response, kept in the project's own repository.

### The written response (`GSE.response/1`)

Each document's response, written to `destination` and named by the document's content hash, holds its slip, the department's records and its `end`. A snippet's response is the same three parts, returned inline. The slip records:
- the input's identity: path and form, byte hash, size, the source map, and whether segmentation came from the caller;
- the steps that ran and the options as applied, with every default filled in;
- any normalizations;
- the identity of what answered: GSE version and commit as loaded, and the lexicon, dictionary and other resources used.

A docket also keeps a ledger, `docket.jsonl`, streamed as progress on stdout. It opens with a manifest of every document before any work starts (the `GSE.intake/1` discipline at corpus scale), then has exactly one outcome line per document as each finishes, then the docket's `end`. Book-sized readings never pass through the pipe.

```json
{"record": "manifest", "request": "run-7", "docket": "sha256:...", "kind": "read", "documents": 1043}
{"record": "document", "request": "run-7", "id": "doc-0001", "sha256": "...", "outcome": "answered", "response": "runs/run-7/gse/3f9a….jsonl"}
{"record": "document", "request": "run-7", "id": "doc-0412", "sha256": "...", "outcome": "refused", "refusal": {"code": "INVALID_INPUT", "field": "path", "problem": "invalid UTF-8", "position": 18211}}
{"record": "end", "request": "run-7", "outcome": "partial", "counts": {"documents": 1043, "answered": 1041, "partial": 1, "refused": 1}}
```

- **One document's failure never sinks the docket;** it is named in its own outcome line.
- **Content-addressed and resumable.** A response is identified by the document's byte hash, its form, the steps and options as applied, and the identity of what answered. Re-submitting a docket keeps every response that still matches and reads only what is missing or stale. This is the lexicon builder's journaled `--retry` and Regenesis's staging, done once, by the desk.
- **Deterministic.** The same input under the same options and identity gives byte-identical records; timing is never part of a record.
- **Scheduled by GSE.** The door works through a docket within a memory bound, the job Regenesis's `run_batch` does for itself today.

A request refused before any work (for example `UNSUPPORTED_CONTRACT_VERSION`) gets a single `end` carrying the named refusal.

### Named refusals at the desk

| Code | When | Fields |
|---|---|---|
| `MALFORMED_REQUEST` | The line is not a JSON object, or a required field is missing or mistyped | `field`, `problem` |
| `UNSUPPORTED_CONTRACT_VERSION` | `contract` names a version GSE does not answer | `received`, `supported` |
| `UNKNOWN_REQUEST_KIND` | No department owns `kind` | `received`, `offered` |
| `UNSUPPORTED_OPTION` | An option, step, form or document form the kind does not declare | `kind`, `option`, `accepted` |
| `INVALID_INPUT` | An input cannot be read as declared, such as invalid UTF-8 | `field`, `problem`, `position` |
| `RESOURCE_UNAVAILABLE` | A resource a step needs is missing or unreadable | `resource`, `state`, `path`, `fix` |
| `GSE_CHANGED_SINCE_LOAD` | The checkout's code or resources differ from what the resident process loaded | `loaded`, `current` |
| `DEPARTMENT_FAILURE` | A department raised on part of the work; the part is located, never a bare traceback | `department`, `unit`, `error` |

Within an answered or partial response, each unit carries the named outcome its capability spec defines: reading states (`read`, `partial`, `unread`, `empty`), lexical states (`primes`, `no_primes`, `no_row`, `unread`), healing decisions (`applied`, `offered`, `kept`, `refused`), and per-unit contract outcomes (`emitted`; `abstained` or `failed`, each with a reason). A deadline turns the remaining units into `unread` with reason `deadline`, and the response is `partial`.

### Kinds: GSE's services

A kind is a kind of work GSE does. Its response is GSE's complete account of that work, defined by GSE's own capability specs and program packages, not by what any project reads today. The call sites below are a coverage check: every current use must be expressible, and nothing a project needs may be missing.

| Kind | Department | The work | The response is defined by |
|---|---|---|---|
| `read` | reading | Read documents or snippets through the requested steps: healing, then the word, sentence, paragraph and document scales, cassettes, and narrative compression | The computable-language record of GSE-06 (structure, prime-basis version, vectors and signs, roles, operators, modality and negation, repair ledger, profile observations, world candidate references, spans, confidence basis, named partial and abstention codes), under `compositional-reading`, `reading-evidence`, `text-healing`, GSE-04 and GSE-05. Published forms: `reading` (the full record), `contract` (the predicate form Genesis and Regenesis walk; its operations, arities and feature keys are published, card #102), `vectors` |
| `words` | lexicon | Look up words without a text | `lexical-evidence`: per word, lexical state, primitives, definition identity and alternatives, frequency, V/A/D, concreteness, structural E/P/A, dictionary membership |
| `heal` | healing | Heal a text without reading it | `text-healing`: healed text and the located ledger, with candidates and decisions |
| `learn` | healing | Add protected terms and names (the one state-changing kind) | `text-healing`: per entry, stored or a named malformed-entry refusal |
| `describe` | desk | Say what GSE offers | Supported contract versions; kinds with their steps, options, document forms and published forms with defaults; record formats; vocabularies (primitive banks and hierarchy markers, syntactic roles and tense/aspect/mood primitives, contract operations and arities, claim-key version) |
| `doctor` | desk | Check what GSE needs | Every resource (lexicon, WordNet, genealogy, frequency, V/A/D, concreteness, dictionary), its named state and the command that fixes it, and whether the loaded process matches the checkout (card #25) |

### Call sites and their kinds

| Project | Purpose today | Request |
|---|---|---|
| Genesis | Sentence to contract (tag `E`; per-call and batch scripts; `scripts/framegen`, `scripts/story_bakeoff`) | `read`, snippet sentences, steps `word`+`sentence`, form `contract` |
| Genesis | Rule clause with typed slots to contract (tag `R`) | `read`, snippet rules with `variables`, form `contract` |
| Genesis | Word to signed valence (tag `V`, through the private `_lookup_lexeme`) | `words` (card #54 decides whether GSE also publishes the valence number) |
| Genesis | Story to genre (tag `G`) | `read`, through the `document` step; genre is among the profile observations |
| Regenesis | Story, file, pulled article or MCP prose to document-resolved contracts | `read`, document (pulled articles in a corpus file), steps through `document`+`cassettes`, form `contract` |
| Regenesis | Narrative spine (oracle and certify scripts) | `read`, document, steps including `heal` and narrative compression, form `contract` |
| Regenesis | Contract per sentence plus oblique roles | `read`, form `contract`; oblique roles are part of the reading's roles |
| Regenesis | Token spell-cleaning | `heal` |
| StoryClaude | A session transcript, healed, resolved and compressed | `read`, document form `dialogue`, steps including narrative compression |
| SquishOS | Voice readings of prose and markdown, under a deadline | `read`, document form `markdown` or `prose` with its own segmentation, form `reading` |
| SquishOS | Word facts; tokens for the scoring loop | `words`; `read` snippet texts with step `word` |
| SquishOS | Heal; learn; membership, spans and protection | `heal` (protected spans are part of its ledger); `learn`; `words` (membership) |
| SquishOS | Vocabularies, claim-key version, provenance; the `resolve_gse` verdicts | `describe`; `doctor` |
| personal-wiki | Heal captured text; read notes | `heal`; `read`, document form `markdown` |
| ShortcutForge | Prompt to vector; bulk descriptions | `read` snippet texts, form `vectors`; a corpus file for the bulk |
| StartupForge | Concept similarity over definitions | `read`, corpus file of definitions, form `vectors` |
| StartupForge, CareerForge | Verbs that survive the parse | `read`, documents, form `contract` |
| ARC_AGI_3, Regenesis | Preflight checks | `doctor` |

### Silent failures today, and the named outcome each becomes

| Today | Under the interface |
|---|---|
| Genesis's server and batch scripts write a blank line on any exception; Java pads missing lines with `""` and skips them | That unit's record has outcome `failed` with its reason |
| Genesis's valence defaults to 0 for a missing word | `no_row` or `unread`, never a number |
| Regenesis's driver swallows an encode failure and exits 0 with no contracts; Regenesis then reports `abstained` | `DEPARTMENT_FAILURE` naming the unit, or `failed` units in a partial response |
| StartupForge's and CareerForge's verb harvests return `[]` when the driver fails (today: missing `data/genealogy.db`) | `RESOURCE_UNAVAILABLE` naming `genealogy` |
| SquishOS's guarded imports leave claims, protection, multiword spans and document composition silently unread | Part of `read` and `dictionary`; a channel GSE does not offer is refused by name through `describe` |

### Not GSE's work

- World lookups: Regenesis's `puller/genre.py` and `corpus.py`, and Genesis's `mcp/corpus.py`, read `genealogy.db` directly. That is Sparse Wiki's interface (GSE-02).
- `scripts/rohan_voice.py`, which SquishOS loads for `recognize`, is SquishOS code living in GSE (card #148).
- Verb-class and verb-thread enrichment and world E/P/A, computed inside the narrative driver today (`GENESIS_UNIVERSE` selects a Genesis `.index` file whose trigger verbs define the classes): a post-step in Genesis and Regenesis over `contracts`, using `vectors` and Sparse Wiki (card #16).
- The two copies of the narrative driver (Regenesis's, and the one in Genesis's `gsebridge/`) are replaced by `contracts`.
- ARC's import of the archived `GSE.primitives` has no caller in ARC.

The archived voice-boundary contract (2026-10-20) had SquishOS's adapter run under GSE's interpreter. The door replaces that arrangement; its payload and state algebra remain the content contract for `read`.

## Target structure (proposal)

Each subsystem is one directory under `GSE/` whose name states its job. A subsystem imports only those to its left. The order below is measured from the code (2026-11-24), not assumed: the encoder uses symbolic grounding inside `encode()`, and SymbolicSpellCheck's context leg reads sentence-scale evidence (resolution goes up a scale), so neither sits below the symbolic layer.

`substrate` ← `lexicon` ← `front end` (tokens, morphology, word-level spelling) ← `trace types` ← `symbolic` ← `encode` ← `healing with context` ← `document` ← {`bridges`, `apps`}

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
