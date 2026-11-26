## Why

Rohan, 2026-11-26: "throw everything in the trash and start over, full new openspec plan and everything." The
lexicon he designed is his Data Geometry architecture applied to language. That architecture is the one he built in
harmonizing (NCEMS), TriageGeist, TrialLedger and sparse-wiki, and formalised in Significance Weighting, Semantic
Specification Learning and Negative Specification. The previous build drifted from it at every load-bearing point:

- "Coherence" (F101/F108) was implemented as conditional-probability thresholds over rating features (648
  candidates, `P >= 0.85`, support `>= 40`). That is the statistical filter he banned (2026-11-25 07:48; 2026-11-26
  21:54).
- Definitions were solved one at a time by SQL at 30-40 per second. Nothing ran over the population, so the work
  stayed at 10^3-10^5 cells while the lexicon has 22,489,376 cells.
- NSM's combinatorics were never turned into relations between banks. The release holds 46 inter-bank relations
  touching 34 of 56 banks; 22 banks have none (F088: "the true atomic is a *sub*-prime symbolic rule of relation
  between banks").
- Sub-kind propagation, "the *easiest* tier" (2026-11-26 19:38), was never part of the build path.

The live lexicon decides about 2.3% of its cells. The runtime senses carry about 1.35 nonzero values each.

## What Changes

- **BREAKING:** the construction path is deleted. That covers the `GSE/curation/lexicon_builder/` code, the curation
  CLI built on it (`GSE/curation/cli/commands.py`), its scripts and its tests. The old OpenSpec change
  `lexicon-symbolic-foundation` and its design document `docs/program/LEXICON_CONSTRUCTION_DESIGN.md` are removed.
  Git history keeps them.
- A new builder is written from scratch at the same place, `GSE/curation/lexicon_builder/`, as small modules, one
  responsibility each. It does not wrap, import or replay the old code (2026-11-24 01:06: not "a wrapper that uses
  code from the older one").
- The whole lexicon becomes one constraint state held in arrays: 401,596 readings x 56 banks, each cell a mask over
  {+1, -1, 0, SILENT}. Each round of closure runs over the whole population.
- Relations between banks become the computational atoms. They come from two places, and one admission gate decides
  both: NSM's own combinatorics and templates compiled into laws, and relations latent across the population and
  found by coherence among independent sources.
- Coherence means the agreement of independent sources on a reading's banks. Agreement settles a value, a
  contradiction is recorded, and a relation that holds every time across words several datasets describe is imputed
  and then validated symbolically. No thresholds, rates or support counts decide anything.
- Confident zeros are censors, carved from near-misses across the population. Positive values need a positive root.
- Inheritance across readings (kind-of, synonymy, form-of, entailment) follows TrialLedger's defaults with declared
  applicability and defeaters. Conflicting defaults are suspended.
- Joint specification bits and a census of every cell are measured each round. The loop stops when no admissible
  rule adds reach (kappa -> 0).
- Senses form from equal encodings on load-bearing banks. Sentence selection uses the same constraints. A small,
  typed tail runs only where independent evidence dissents.

**Kept:** the source parsers and their `to_primitives` projection through `integrator.load_all_sources` and
`SOURCE_PRIMITIVE_SCOPE` (AGENTS.md design constraint). Also kept: the raw source data, the verified NSM records,
the NSM chart and the hand-authored prime foundation, Rohan's founder words and rulings, and every record in
`docs/readings`, `docs/verification` and the archives. The live lexicon stays live until a strictly better one
replaces it.

## Capabilities

### New Capabilities
- `lexicon-construction`: building the definition-indexed, four-state, 56-bank lexicon by symbolic closure over the
  whole population, and the artifact the GSE runtime consumes.

### Modified Capabilities
- None. The runtime consumer contract (`GSE.lexicon_resource`, `GSEEncoder`) is unchanged. The new artifact must
  satisfy it.

## Impact

- Code: `GSE/curation/lexicon_builder/` is replaced and `GSE/curation/cli/commands.py` is removed. The NSM chart
  data and two WordNet identity helpers that the runtime imports from the old package move to
  `GSE/curation/external_sources/` (`GSE/symbolic/lexical_grounding.py`, `nsm_chart.py`). About 31 scripts and 115
  test files that exercise the old builder are removed.
- Data: the live lexicon `data/lexicon_builder/2026-11-12/sparse-release-022-senses6.db` is untouched and remains
  the comparison baseline (32,707,151 joint bits measured on its stored states). The new build writes one copy in
  progress.
- Documents: `docs/program/BUILD_SPEC.md` points GSE-01 at this change. `LEXICON_FOUNDER_WORDS_2026-10-24.md` stays
  as his words.
