# Stage 1a code shape — one constructor, same answers

An engineering record, not a second design: `docs/program/LEXICON_CONSTRUCTION_DESIGN.md` remains the only design. The sketch was reviewed before the refactor; this version records what was built and how it was verified.

## Before

`build` CLI → `NativeSources.for_word` → two separate producers:

- **Adjectives** (`build.source_matches` + `build.construct`): the source rule asserts its own facts; admitted laws, source restrictions and residual domains; solve; the residual loop and opt-in bank review; diagnostic closure; export if resolved.
- **Verbs** (`native_constraints.native_readings` + `perception.py`): VerbNet predicate laws and perception, which may call the model through its own cached call; solve with no bank laws and no typed facts; never export.

## After

| Module | Single job | Public interface |
|---|---|---|
| `reading` (new) | One seed → one reading record: admitted bank laws plus the seed's laws, solve, the open-decision loop with a re-solve after each answer, opt-in bank review, provisional proposal, export check. Also the single typed model call, `ask`, with an optional shared payload cache. | `ReadingSeed`, `CoordinateDecision`, `ReviewContract`, `Construction`, `construct_reading`, `ask`, `restriction` |
| `build` | The adjective adapter (`source_matches`, `adjective_seed`, `construct`) and the CLI batch loop. | `construct`, `source_matches`, `build`, `main` |
| `native_constraints` | The VerbNet adapter: frame projection and one seed per frame. | `frame_constraints`, `native_readings`, `predicate_domain` |
| `perception` | The perception-mode adapter; its model call goes through `reading.ask`. | `perception_constraints` |

Every reading now passes through `construct_reading`, with the same admitted laws, solver, decision loop and export check. A seed carries its typed facts, source laws, any model laws already chosen at word scope, its open decisions, an optional review contract, an export flag and its record layout. Perception is chosen once per word and payload, through the shared cache, and enters each frame's seed as a chosen law. Admitted bank laws now reach verb readings too; with no verb facts yet, no guard fires.

The public names the tests and Detective pin stay where they were. The Detective-certified pure functions (`vector_status`, `selection_status`, `predicate_domain`, `paired_order_status`, `law_admission_status`, `bank_coverage_status`) are untouched.

Path-map status (process doc §3):

| Status | Item |
|---|---|
| Orphaned | `core.NumberScale` / `apply_number_scale`; only tests call them. |
| Reachable, never exercised | The open-decision loop (no rule has residual slots), the `completion_domains` repair, and bank review (opt-in). |
| Not consumed by `build` | `atomic_definitions`. |

## Verification

1. `scripts/lexicon_gate.sh`: the frozen symbolic build of all 1,040 gate words is **byte-identical** to the baseline (`IDENTICAL`, stronger than the JSON-equal threshold).
2. All 97 lexicon tests pass with no test file changed. They pin model-call payloads, call counts and the perception cache through recorded selectors, which a symbolic build cannot see.
3. ty is clean for `gse/lexicon_builder`; the repo gate (`scripts/ci_local.sh`) passes.

The frozen comparison establishes preservation, including any existing defects, not correctness.

## Stage 1b (contract changes, after the rule decisions)

Each gets authored tests and a deliberate `--rebaseline`:
- one admission check for every rule family (in progress next);
- the approved rule changes from the review;
- typed facts from verbs, so bank laws can fire on them;
- **one reading per VerbNet class that preserves frame distinctions.** Frames are realizations of the class's sense. A frame-specific assertion, such as the "hit at" frame's negated contact, stays scoped to its frame; the class reading must not union every frame's assertions;
- **a negated-only predicate stays in the derivation.** When it writes no cell, the binding and its negative evidence remain visible in the reading's trace;
- export for fully resolved verb readings;
- lemma routing from Kaikki, reading only `form_of`, part of speech and tags. It needs a one-time index of the 3.2 GB file, never reads glosses (F080), and does not use `wiktionary_primitives.db`;
- the emotion rules once revised and approved;
- wiring in or removing the orphaned NumberScale path.
