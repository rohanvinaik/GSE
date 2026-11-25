# GSE-01 execution checklist

The single engineering sequence is CP-01–CP-08 in
`docs/program/LEXICON_CONSTRUCTION_DESIGN.md#engineering-execution-one-checkpoint-and-a-continuing-learner`.
This checklist records implementation/verification, not another specification or release result.
Historical October foundation/family reports remain evidence of their original scope.

## Founder correction — build the lexicon by Rohan's design (2026-11-24)

See design.md, *Founder correction*. These precede the checkpoint work below; a checkpoint over an
empty lexicon is not a usable lexicon.

- [x] FC-1 Before code: confirm what replay validation and publication recompute, which builder
  sources the checkpoint pins, and how `SOURCE_FAMILY` groups correlated sources.
- [x] FC-2 Source agreement: independent families vote per bank within their declared scopes; a sign
  commits on agreement with no opposition; it enters through the resolver so replay reproduces it.
- [x] FC-3 Sense collapse: per lemma and part of speech, senses grouped by agreement on load-bearing
  banks (alternatives removed × downstream reach), split only on a witness, cores closed under the
  rules, rebuildable from the release.
- [x] FC-4 Acceptance in Rohan's order (F070): write each obvious word's expected banks before
  running (happy, dog, give, big, mother, lock, and negatives), then the top 1,000, then the full
  build, in a working copy beside the release; 0 changed values among already-resolved cells.
- [ ] FC-5 Admit the 648 coherence relations after re-checking them on current held-out words.
- [x] FC-6 Runtime reads senses by part of speech; a word is never refused for having several
  definitions.
- [ ] FC-7 Rohan rules on F057 vs F066 (GOOD on nouns): the current rule blocks 1,437 agreed GOOD signs on
  noun senses in the full build.
- [ ] FC-8 Switching `data/lexicon_active.json` to the result waits for Rohan's word.

Result (2026-11-24): candidate `data/lexicon_builder/2026-11-12/sparse-release-022-word-senses.db`, a copy of
release-022 with `word_source_agreement` and `word_senses` added; no release table changed.
- 67,173 lemmas become 99,303 senses, placing all 377,720 non-name definitions. 54% of main senses
  carry a sign; signed lemmas cover 71% of the top-1,000's token mass, and the remainder is mostly
  function words, which correctly carry none.
- Acceptance 12/12. Replay of 300 random lemmas: 0 mismatches.
- Sentences that read as all-unread under 022 now read: happy FEEL+ GOOD+, dog ALIVE+ SOMETHING+,
  gave DO+, know KNOW+, see SEE+, loves FEEL+, sad GOOD−.
- Proof packet on the candidate:
  - §3, §4, §5, §6, §11 and §12 run; §5 and §11 newly.
  - §8 and §9 still fail in the symbolic layer's relation evidence, which requires one identified
    definition.
  - §10 needs "hurt", whose main sense is unresolved.
  - §1 and §7 need `genealogy.db`.
- The release's own replay validation on the candidate: REPLAY_VALIDATED, 401,596 definitions, 0 mismatches
  (the added tables do not disturb it). The full suite: 7,745 passed, 0 failed. The checkpoint's 50 source
  pins cover none of the new or edited files; its 24 tests pass.
- F075 random sample (40 words from ranks 2,000–10,000, 20 from the tail) is mostly sound: people ALIVE+
  SOMEONE+, things SOMETHING+, evaluative adjectives GOOD±. Known error class: where the only evidenced
  definition is a minority sense, it becomes the main sense, because WordNet's order rests on thin tagged
  counts. Examples: snowball (the viburnum plant, ALIVE+) and dud ("someone unsuccessful", count 0).
  Borderline: educated GOOD+ and frigid GOOD−. Both await Rohan's ruling.
- Not yet done:
  - salience is only partly implemented: senses group by exact load-bearing encoding, and the
    significance weight only breaks ties;
  - the build metadata pins code hashes but not the source data files.

## Urgent checkpoint execution — 2026-11-24

The direct user instruction now prioritizes a validated usable checkpoint before
completion of generic CP-02–CP-06 research machinery. The existing source,
semantic, replay, runtime and declared-workload gates are not waived. The
controller's current owned-scope gate passes **1,800 tests, zero skips/failures/errors**,
including the real Regenesis guard-imputer integration; this is not the final
integrated repository gate or a publication receipt. Exact evidence and source
pins: `docs/readings/2026-11-13-ssl-explicit-genera/ssl-api-controller-code-freeze.json`.
That receipt marks controller edits stopped, not a whole-run protocol freeze:
the runtime peer's repaired completion receipt remains the synchronization boundary.

The original v1 plan remains unchanged. The explicit v2 rebase and eight exact
typed questions are retained beside it. The reference packet completed, with
dog/I NULL explicitly reserved. Four canonical source own-coordinates and two
typed reference coordinates are actually written to the private teaching head.
On the fixed 401,595-definition lexical cohort, exact joint H changes from
32,819,332.148767773 to 32,819,323.24870193 bits (zero search limits); no
unfinished population migration is included in that measurement.

The atomic joint I/YOU corpus migration completed at 18:36:42Z, exit 0. Both
mandatory full replays validate all 401,596 entries with zero mismatches and
zero solver limits. After six unsupported dependent cells reopen, the rule
revision adds a net 50,517 filled coordinates and contracts exact joint H by
63,216.05024011806 bits relative to the post-teaching head. Including the six
earlier source/teaching coordinates, the actual foundation-to-candidate net is
50,523 filled coordinates and 63,224.95030596107 bits, not the old 50,526 forecast.
The private lexical head has 461,608 filled / 22,027,712 unknown coordinates,
H = 32,756,107.198461812 bits. Seven separately identified 98K-context prime
answers and six controller residual/child answers are retained. The queued
ordinary writer reconstructs exact historical requests before using ten of
these answers; exact historical precheck passed and mandatory full writer
preflight is running, with no service-call repetition.
A scoped 1,289-definition own-happening child excludes the retained euphemism
and abbreviation challenges; its queued fresh current-head audits precede
ordinary admission and replay. The broad event ancestor remains unadmitted.

Controller builder edits are stopped (`ssl-api-controller-source-freeze.json`).
The runtime peer is explicitly unfrozen for two composed-scope defects. The
integrated repository gate, full eight-operation artifact-verified workload,
fresh final semantic audit and CAS publication remain open. Active release 021
has not changed. See `ssl-api-controller-blockers.json` and
`ssl-api-controller-root-handoff.json` for actual phase and exit receipts.

## Contract reconciliation

- [x] Read the complete SSL paper skeleton and the relevant whole significance/workflow units.
- [x] Trace the production runner, discovery consumers, comparison and publication/retention path.
- [x] Reconcile GSE-01, the current lexical design and this existing change around the active
  56-ordinary-bank path; retain the upstream 58-coordinate contract as distinct historical work.
- [x] Link the [engineering-audit receipt](../../../docs/readings/2026-11-13-ssl-explicit-genera/ssl-v2-engineering-audit.json):
  strict OpenSpec validation, three-repository reference/dependency check and document whitespace
  checks pass. This closes the specification audit only; CP-01–CP-08 remain implementation work.

## CP-01 — valid opening state

- [x] Diagnose and repair catalogue derivation/refresh without relaxing noncatalogue replay checks;
  explicit repair and subsequent ordinary replay now pass for all 401,596 entries.
  Trace: `_replay` checks the saved derived catalogue before allowing `refresh_catalog` to propose
  its replacement. Separate that repair phase and test refusal on corrupted authoritative evidence.
- [ ] Preserve exact historical source/request identities across namespace alias comparison.
- [x] Upgrade the two reduced-basis fixtures consuming native YOU evidence; do not filter valid
  assertions or weaken unknown-bank validation. Rerun affected tests and the full repository gate.
  Latest maintained-suite gate: 7,520 tests, zero failures/errors, 66 skips. Whole-project ty
  reports 216 advisory diagnostics; the changed controller files pass their scoped type check.
- [ ] Pin the replay-valid baseline, basis, cohort, source/rule/link/frequency identities and H report.
  If metadata changes, record a rebase; reuse a journal only when its exact request still matches.
- [ ] Distinguish the published 021 baseline from the unpublished foundation working head, preserve
  intervening migration lineage and reconcile publication's active-baseline check without relabelling.

## CP-02 — discovery feeds subsequent work

- [ ] Add versioned durable head/candidate/surprise/task records to the existing working state.
- [ ] Consume native, reviewed and source-backed discovery plus newly grounded chains during the
  run. Retain source/role/sense witnesses, warrants, counterexamples and original dependencies.
- [ ] Schedule a candidate absent from the opening family list without a replacement manual plan.
  Synthetic integration witnesses now cover open-bank discovery, durable warrant intake, fresh
  audit and replay under the same plan; real-corpus execution remains CP-08 work.
- [ ] Teach an unresolved bank absent from every opening family; retain any legal answer and
  feed its scoped hypotheses through durable warrant intake, fresh audit and replay under the
  same frozen plan. Keep teaching tasks independent of proposed signs and audit sense aliases.
- [ ] Preserve complementary candidates, pending warrants, already-entailed shortcuts and typed
  operational refusals; candidate or legacy-vector output cannot self-validate.

## CP-03 — counterexample to refinement to replay

- [ ] Route scope/audit challenges into the existing refinement/revision machinery.
- [ ] Learn an independently justified distinguishing condition; retain the rejected parent's
  counterexamples, valid exact exceptions and null reservations separately.
- [ ] Freshly audit the changed rule and its boundary with proposed-rule descendants withheld.
- [ ] Jointly migrate additions/retirements/exceptions/reservations, replay every eligible entry,
  preserve independent support and reopen unsupported conclusions before choosing again.

## CP-04 — scheduling from the constrained state

- [ ] Recompute strata, per-answer closure and interacting proposal reach after every accepted
  teaching or revision. Frequency ranks eligible senses; it supplies no semantic sign.
- [ ] Extend needed joint-tuple/guard candidates through the existing Relation and source-context
  contracts, including multiple surviving signs and unchanged-marginal exclusions.
- [ ] Verify a complementary multi-rule bridge changes priority; limits stay unavailable and
  unsupported guards, hypothetical candidate outputs and unadmitted rules enable nothing.

## CP-05 — reporting consumes actual joint measurements

- [x] Update the public equal-budget comparison and acceptance code to consume phase joint H,
  exact-count coverage and bucket deltas, retaining singleton diagnostics separately.
- [ ] Separate direct teaching, propagation, new-rule effects, overlap and reopened cells using
  replayed counterfactuals. Keep sigma_sem minimum teaching evidence distinct from log-space H.
- [ ] Compare closure-aware and Zipf arms with identical frozen starting inputs/search language
  and equal actual question budgets; report audit/review costs and incomplete arms honestly.
- [ ] Record the observed amplification curve across successive rounds; no exponential result
  follows from the prospective I/YOU population stage alone.

## CP-06 — bounded working storage and crash recovery

- [x] Reuse the existing sustained writer's shared replay for explicit bounded definition–bank
  work; preserve identical single/batch acceptance and invalidate changed rules/sources. The
  writer now accepts an explicit tuple of entry–bank questions without creating
  their Cartesian product. One invocation shares full preflight and the existing
  indexed, data-version-checked connection. This does not claim to retain one
  writer connection across rule-version boundaries.
- [ ] Replace per-epoch retained whole DBs with one working head and compact transition records,
  reusing existing transactions, copy-on-write staging, receipt deduplication and retention.
- [ ] Resume correctly after teaching, audit, transition installation and pointer activation,
  including partial output and a process interrupted before its receipt is finalized.
- [x] Verify resumption after obsolete owned staging DBs are removed; no request repeats or
  unsupported answer commits. Active/previous/source/audit resources remain protected.
  Synthetic connected tests cover teaching-result, migration-result, head-before/head-after
  CAS and post-unlink interruptions, with old DBs actually removed and native/audit
  streams retained. Publication-interruption recovery remains separately open.
- [ ] Demonstrate a fixed bound on working DB count as epoch count grows.

## CP-07 — usable-checkpoint workload and actual consumer

- [ ] Freeze the workload manifest: basis/cohort/frequency/corpora, eligible token denominators,
  operations, required bank queries/structures, labels and development/final split.
- [ ] Use the existing 90% eligible-token-mass requirement in both sources, with genre slices;
  keep every dictionary sense/tail entry and separately report missing-sign challenges.
- [ ] Repair real closed-class/contextual identity eligibility, including pronoun versus chemical
  symbol He; test parser-role error, ambiguity, proper names and preservation of correct readings.
- [ ] Exercise WANT polarity, BE own-state, anatomy, modifier/negation scope, reference binding,
  unspecified/long duration and required event/action outputs through the real encoder.
- [ ] Require all promised critical outcomes and no known wrong/missing required component;
  report partial/abstained/unavailable outcomes without treating them as passed NLP functions.
- [ ] Retire development-exposed benchmarks from untouched-holdout claims and run independent
  final audits. Finite sparse-publication labels cannot certify untested banks or general usability.

## CP-08 — execute and publish the same system

- [ ] Run one mechanical public-entry cycle that discovers a new rule, encounters a genuine
  contradiction, refines it, audits independently, replays, selects again and resumes exactly.
- [ ] Kill regressions for 3→2 narrowing, 9→3 unchanged marginals, cyclic/self-confirming support,
  stale context, source identity, alias leakage, unknown guards, retraction and solver limits.
- [ ] Complete the real I/YOU teaching/audits without assuming admission, then use the connected
  learner for the pinned common-word workload and record exact counterexamples/refinements.
- [ ] Run full candidate replay, semantic/corpus/runtime acceptance and applicable repository
  gates. Detective remains explicitly deferred, not reported as complete.
- [ ] Activate the pinned sparse successor atomically through existing publication, with one
  rollback and protected sources/audit. Verify real consumers select that artifact.
- [ ] Update the living draft from computed receipts, then continue the same controller from the
  installed checkpoint with expanded scope and unchanged epistemic requirements.
