# Organize GSE by subsystem

## Why

GSE grew by accretion into one namespace: a June 14 import of an earlier design (the HDC learning-network stack), the deterministic text-to-math engine built June–November, two lexicon constructors built in parallel (`GSE/lexicon_builder`, Oct 24–26; `GSE/curation/lexicon_builder`, Oct 29–Nov 23), the applications built on the engine, and the offline build tooling. The 2026-11-23 import graph and runtime trace (design.md) show what that costs:

- 63 modules (about 19,600 lines, 22% of the package) never run on any consumer path, and 28 test files exercise only them.
- The runtime depends on build tooling: the encoder, lexical evidence and the spell checker read the lexicon through `curation.lexicon_builder.storage`, and the encoder takes its grammatical catalog from `curation.external_sources`.
- Core modules import the Genesis/Regenesis bridge and the genre application; `encode` and `symbolic` import each other; the package root advertises the legacy stack.
- The test suite is one flat directory, so every change runs about 7,600 tests (six and a half minutes).
- Two consumer imports (`GSE.discourse.document.claim_records`, `GSE.nlp.spellcheck.spelling_protection`, both in SquishOS) target functions GSE does not publish.

## What Changes

- Group the package into subsystems, each with one job and a fixed dependency direction (design.md, *Target structure*).
- Move the read side of the lexicon (definition-database reader, closed-class catalog, prime basis) into the runtime lexicon subsystem; the constructors depend on it, never the reverse.
- Move the legacy stack into `GSE/_archive/` once the owner confirms it; nothing is deleted, and the package root stops advertising it.
- Arrange tests by subsystem with a scoped gate command, and select cross-cutting tests by change impact.
- Each move is one reviewable commit that updates every importer (package, tests, scripts, readings runners and consumer repositories) and passes the gates listed in tasks.md.
- What GSE computes does not change. Stored identifiers that name module paths are pinned before any module moves.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This change rearranges code; no specification changes.

## Impact

- Import paths used by Genesis, Regenesis, SquishOS, StartupForge, StoryClaude, CareerForge and ShortcutForge, updated in the same commits.
- Detective certificates keyed by source path, regenerated for each moved module.
- Documentation that cites module paths.

## Decisions required from the owner before any module moves

1. Which lexicon constructor remains, or how the two are combined (their record formats differ; see `docs/program/LEXICON_CONSTRUCTION_DESIGN.md`).
2. Whether the legacy stack is archived.
3. Whether consumers keep today's import names (`GSE.api`, `GSE.symbolic`, …) as stable public modules or move to the new paths.
4. Pausing the concurrent Codex session in this checkout while modules move.
