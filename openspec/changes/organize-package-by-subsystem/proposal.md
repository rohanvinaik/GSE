# GSE-00: live capability map, retirement of dead code, and package organization

Issue: https://github.com/rohanvinaik/GSE/issues/166

The enduring contract is `docs/program/BUILD_SPEC.md#gse-00`. Program work ID: **GSE-00**. This change also carries the owner's 2026-11-23 professional-pass instruction (organization, documentation and tests), which BUILD_SPEC does not cover.

## Why

USER_INTENT (2026-11-23): map the codebase by the owner's three tiers and trace how input becomes output; document it; get the code into flat modules that say what they do, connected where they should be and separate where they should be; scope tests by subsystem; find wasted, duplicate and stale tests; where code conflicts, use dates to find improvements whose old version was never retired. The workflow is `PROFESSIONAL_CODING_PERFORMANCE_ENGINEERING.md`.

USER_INTENT (2026-11-24, the owner's decisions on this change):

1. `GSE/curation/lexicon_builder/` is the one lexicon builder; check that it is complete on its own and not a wrapper over the upstream constructor.
2. Archive dead code only when it is certainly dead. Code not in active use is not dead; experiments the owner put off are kept.
3. Everything and everyone uses GSE through one interface, agreed with the owner on 2026-11-24 (`specs/gse-interface/spec.md`): "a clean central bureaucracy for code. Input comes in, it's handed a slip and sent off to one department or another, where it is allowed to present its problem and have a formal, written response to take back to its own repo." Refusals are named. GSE and each consumer are severable both ways ("cassette" is relative: a project is a cassette in GSE when it asks for NLP work; GSE is a cassette in that project when it supplies the information an algorithm needs). Each project keeps its own calling code; GSE uses Sparse Wiki the same way.
4. The owner's lexicon session (the `lexicon-symbolic-foundation` change) continues in this checkout. This change never edits that session's files.
5. The custom-model-training work means both the trained register router and `curation/llm` (with the Qwen client); both are unfinished experiments.

USER_INTENT (2026-11-24, later the same day):

6. The NSM primes chart is a short list; write it formally in code so nothing depends on a text file.
7. Archive the audit daemon (with `deploy_to_desktop.sh` and the empty root `lexicon.db`) and the flat lexicon. The owner has a simple, already-devised answer for what replaces the flat lexicon, and will explain it.
8. Experiments go in one `experiments` folder.
9. Genesis is out of scope; Regenesis succeeds it.
10. The proof-packet readings are demonstrations, not formal test cases: a high-level check that GSE keeps its advertised ability to interpret natural-language input. The specifics do not matter.
11. The interface proposal is broadly accepted; details later.
12. Ordinary words reading as unread under the definition lexicon (`AMBIGUOUS`) misses the point of GSE. The owner will explain GSE, NLP and language before any change is made to it; this pass stops here until then.

CODE_OBSERVED (2026-11-23, design.md):

- 63 modules (about 19,600 lines) never ran on a consumer path. Most belong to the June 14 learning-network experiment, which decision 5 keeps.
- The runtime reads the lexicon through build code: the encoder, lexical evidence and the spell checker import `curation.lexicon_builder.storage`.
- `encode` and `symbolic` import each other, and `symbolic` re-exports the Genesis/Regenesis bridge modules.
- Tests run 55 of the 63 never-observed modules, but nothing tests the live register router, Janus figures, four statement-healer lenses or `symbolic.variables`.
- SquishOS imports two functions GSE does not publish (`GSE.discourse.document.claim_records`, `GSE.nlp.spellcheck.spelling_protection`).

## Work-package restatement

- **Authored input:** the repository at a pinned commit, the consumer repositories' import sites, and the owner's decisions.
- **Computation:** an AST import graph; a coverage trace of consumer-style calls; full-suite coverage; module dates that exclude repository-wide sweeps; re-verification of the 2026-10-04 theory audit's dead-code findings (card #152) against current code.
- **Emitted artifact:** `docs/ARCHITECTURE.md` §7 (drift map) and §8 (module reference), and this change's design.
- **Consuming decision:** which code is archived, which stays as an experiment, and how the package and tests are organized. Each archive is one commit with its evidence.
- **Named abstention:** a module whose status cannot be established is labelled, never archived: "not confirmed dead", "unfinished experiment", or **UNMEASURED** where a required resource is missing (`data/genealogy.db` for `resolve_document` and narrative compression).

GSE-00's completion receipt also requires fixtures that protect existing correct readings, reproduction of the dated proof-packet demonstrations (or marking them unverified), and a per-class outcome ledger. Those remain open in tasks.md.

## What Changes

- Archive code that is certainly dead, one reviewed commit each, with the evidence in the commit and in `docs/ARCHITECTURE.md` §7. Done so far: the shadowed `GSE/cli.py`; eight scripts that could not start; the upstream constructor (decision 1).
- Keep experiments in place and label them (decision 5).
- Make dependencies point one way: the read side of the lexicon moves out of build code into the runtime lexicon.
- Organize modules and tests by subsystem, after the consumer interface (decision 3) exists, so consumers are not moved twice.
- What GSE computes does not change. Stored identifiers that name module paths are pinned before any module moves.

## Capabilities

### New Capabilities

- `gse-interface`: the one interface through which anything and anyone uses GSE, and through which GSE uses other projects. Its principles are agreed; the concrete request and response shape comes to the owner for review before any code.

### Modified Capabilities

None. Retiring the upstream constructor removes its unpublished release-format reader; flat-format rows it wrote are now refused as `RETIRED_RELEASE_FORMAT`.

## Related cards on the GSE overhaul board (Project #4)

Read in full: #152 (periphery: archived imports, shadowed CLI, dead daemon, demos) and #29 (W9 engineering foundations; keep-or-archive for off-spine modules). Related by title, not yet read: #26 (repository root resolved in 18 modules), #33 (`TestResult` collected as a test class), #45 and #46 (tracked LintGate and Serena files), #47 (root leftovers: `deploy_to_desktop.sh`, `lootdrop.db`, the `lexicon.db` stub), #96 and #111 and #134 (dead and duplicate code in the front end, encoder and symbolic layer), #107 (two word-encoding paths), #144 (superseded keyword encoders), #21 (import cost of `GSE.symbolic`), #102 (publish the contract spec). This change cites their evidence and closes nothing on its own.

## Impact

- `GSE-lexicon` runs the retained builder's CLI (`GSE.curation.cli.commands`).
- Every consumer's calling code moves to the interface: Genesis, Regenesis, SquishOS, StartupForge, StoryClaude, CareerForge, ShortcutForge and ARC (design.md, *Consumers today*). Responses are written data, not live GSE objects, so consumers that pass GSE objects around today (SquishOS, Regenesis, StoryClaude) change shape.
- Detective certificates keyed by source path: the five entries for the archived constructor are stale until Detective's next run.
