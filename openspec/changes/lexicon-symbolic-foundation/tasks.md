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

## Completion work packages (mechanized; each is one commit by one small agent)

Each package names its inputs, the command it adds or runs, and its acceptance. Agents, including
API-run agents, execute packages and report; they never supply lexical values. Every package must
satisfy three rules:
- No package makes a semantic judgment. Judgments are owner decisions (D-1 to D-3) or stated defaults,
  applied as named constants with a test.
- Every package rebuilds the candidate and passes, unchanged: `tests/test_lexicon_word_sense_acceptance.py`,
  `scripts/build_word_senses.py --verify 300` (0 mismatches) and `validate_build` (REPLAY_VALIDATED).
- No resolved value changes without a named cause.

- [x] D-1 GOOD on nouns (Rohan, 2026-11-24: option (c), "be very judicious"; implemented: a noun sense whose most
  common WordNet definition is noun.feeling carries agreed GOOD; hatred/anger/grief GOOD-, love/joy GOOD+; pain,
  happiness, mom, widow, success, murder stay 0). F057 vs F066: the noun rule blocks 544 agreed GOOD+ signs (love, joy,
  success, beauty, health; also mom, eyes) and 855 GOOD- signs (hate, pain, murder, danger, tragedy; also
  widow, nerve).
- [x] D-2 Reading rule (Rohan, 2026-11-24: "everything" meant the whole set; a sense that breaks coherence is an
  out-of-variance exception; implemented as the main sense with `exceptions`). Confirm the main sense with alternatives; it changes the 2026-11-24 "yes"
  to the reading carrying only what the surviving senses share.
- [x] D-3 Switch `data/lexicon_active.json` to the candidate (Rohan approved, 2026-11-24; after the rebuild under
  D-1 passes acceptance, replay and validation). Done 2026-11-25 through `publish_sparse`:
  `sparse-release-022-senses.db` (sha256 00fd5306…), release replay 401,596/401,596 with 0 mismatches,
  the 022 publication gold evaluated; before it, replay sample 300/300 and every word-sense value
  warranted (`tests/test_lexicon_every_value_has_a_warrant.py`). The default encoder reads happy FEEL+
  GOOD+, dog ALIVE+ BODY+ SOMETHING+, gave DO+ HAPPEN+, want WANT+, know KNOW+, see SEE+, sad GOOD−.
- Not owner decisions; defaults with a stated rule, which Rohan may override at any time:
  - the measurement thresholds (valence 0.5, felt strength 3.5, perceptual 3.0, coherent group 3, the
    genuine-emotion list), each measured against words that should and should not pass;
  - the salience cut, derived by WP-2 from the weight distribution by a stated rule;
  - grammar-to-bank constraints, admitted by WP-7's stability criterion.
- [ ] WP-0 Tighten the main-sense rule. Trust WordNet's first sense only when the word has one synset for
  that part of speech, or the first sense has tagged uses (count ≥ 5). Otherwise use the coherent-group
  rule, or leave it unresolved. Acceptance: snowball and dud have no main sense; inkstand and knut keep
  theirs; beauty's main sense is not "a beautiful woman" (SOMEONE+); the obvious words are unchanged.
- [ ] WP-1 Pin source data. Hash every integrator data file into the `word_senses` metadata; `--verify`
  refuses a changed source by name. Acceptance: editing a copy of a source file makes verify fail.
- [ ] WP-2 Salience. Compute each definition-bank weight (alternatives removed × (1 + κ)) and compare senses
  on banks at or above a salience cut τ. Report the groupings at τ = 0, median and top-3 for the top 1,000
  words; τ is the cut its stated rule derives from that distribution. Acceptance: the τ = 0 rebuild equals today's.
- [ ] WP-3 Admit coherence rules (FC-5).
  1. Rerun `scripts/lexicon_coherence.py` on the sense cores.
  2. Apply the existing population policy: conditional probability ≥ 0.85, support ≥ 40 per partition,
     held-out drift ≤ 0.1.
     Superseded 2026-11-25: Rohan, "a constraint propagation problem, not a statistics one where you
     mine a database for a random match with a hand-tuned arbitrary filter". Governing source:
     `SIGNIFICANCE_WEIGHTING.md` §6, §14 and §16.7, with `Regenesis/regenesis/promotion_ledger.py`; see
     design.md, "Superseded 2026-11-25".
  3. Admit the survivors as conditional `Relation`s and rebuild.
  Acceptance: 0 resolved values changed, the counterexamples of each admitted rule listed, ΔH reported.
- [ ] WP-4 Symbolic read side. The relation evidence in `symbolic/lexical_grounding.py` reads senses, so
  proof-packet §8 and §9 run. That file is owned by Rohan's session: schedule it with them.
- [ ] WP-5 SSL measurement. Report H0, H per epoch, the κ distribution and the knee on the candidate with
  `specification.py`. Acceptance: the numbers reproduce from the committed command.
- WP-6 (model rulings for the tail) is withdrawn. Rohan, 2026-11-25: "Why is the *model* making decisions?
  Is this not...symbolic? Just get it to run the analysis and report, not do inference-driven nonsense."
  No model answer becomes a lexicon value. API credit pays for agents that execute these packages
  (deterministic code, checked by replay and tests) and report.
- [ ] WP-7 Grammar to banks (design rule 4). Measure which banks are load-bearing and stable across the
  words observed in each operator's argument slot (the comparative's operands, for example) over a
  pinned corpus. Admit the stable ones as sentence-time constraints by that criterion.

## Structural propagation (founder correction 2, 2026-11-25; supersedes the WP order above)

- [x] SP-1 Identity roots. `wordnet_hierarchy.py` carries identity from each prime's own concept (gloss
  or approved binding) to every kind; the substance branch is excluded from PART.
  `scripts/revise_lexicon_wordnet_identity.py` adds the projected assertions to the release through
  `revise_source_candidate` with full replay. Forecast: 30,466 definitions, about 42,000 signs, 0
  conflicts in a 400-definition sample.
  measure.n.02 (QUANTITY) is withdrawn: its subtree holds named months, ages and currencies, and the
  release's own duration rule reserves date and temporal-phase senses for separate treatment.
  Reviewed 2026-11-25 by reading each root's members against its gloss (after Rohan's "airline"
  objection): withdrawn social_group (institutions are not people), part.n.01 (words and titles are not
  parts), change.v.02, make.v.03, be.v.01, get.v.01, equal.v.01, enter.v.01, say.v.01, touch.v.05 (their
  kinds are mostly not what the gloss says). PEOPLE comes from groups of persons only: people.n.01,
  gathering.n.01, kin.n.02, family.n.01, team.n.01. Kept roots still carry WordNet's own odd members
  (a tree's crown under location; a bishop under state); census in
  docs/verification/2026-11-25-identity-root-census.json.
  Result 2026-11-25 (candidate sparse-release-022-identity.db, not yet published): the revision changed
  29,134 definitions and settled 47,718 cells (HAPPEN 19,125, DO 9,404, CAUSE 6,993, BE 4,234, MOVE
  2,401, WHERE 2,215, TOUCH 703, SAY 587, WHEN 540, PEOPLE 505, SEE 243, adjective poles); 7 definitions
  bound to Rohan's model receipts were left unchanged; release replay 401,596/401,596, complete search, 0
  mismatches. Word senses rebuilt: replay sample 300/300; word-sense, guard and warrant tests 51/51.
  Against the live lexicon: 20,330 main-sense values filled; 5 changed (BIG 0 to +1 on gargantuan, great,
  heroic, monstrous, prodigious: the absence default gives way to size identity); 728 removed on 466
  words where richer definitions regroup and move the main sense (412 are I/YOU convention zeros; the
  rest mostly drop values that came from mixing senses, e.g. boot DO, catch DO, assembly PEOPLE, and a
  few real losses, e.g. chill FEEL). Mean meaning banks per word: top 1,000 1.44 to 1.72; all words
  1.11 to 1.37.
  Published 2026-11-25 by Rohan's instruction through publish_sparse: sparse-release-022-identity-published.db
  (sha256 2a104a5f...), replay 401,596/401,596 with 0 mismatches, gold evaluated; the previous copy is
  the rollback. Known loss: the main sense of "cut" (verb) moved to the contact sense, TOUCH without DO.
  Withdrawn and republished 2026-11-25 (Rohan: "Fine, do it"): the state.n.02 BE root (9f810d1) exceeded the
  approved convention, own state denotation. Revision: 4,234 BE values reopened, nothing else changed, replay
  401,596/0. Word senses: 2,738 readings lose BE, 0 changed, 122 gained by sense regrouping (43 FEEL, 79 BE from
  explicit-state member definitions; some merges are wrong, e.g. job, play, check: WP-2 salience). Active:
  sparse-release-022-identity2-published.db (sha256 f1c71d88...), gold evaluated; the identity copy is the rollback.
- [ ] SP-2 One layer: attach each word's agreed signs to its main sense's definitions.
- [ ] SP-3 Adjective identity: a head whose own gloss is a prime's pole (good/bad GOOD, large/small BIG,
  far/distant and near/close FAR, true/false TRUE, same/other/different SAME, alive/dead ALIVE) and every
  satellite of its cluster (`ADJECTIVE_IDENTITY_HEADS`). Word-level signs are not carried through
  clusters: measured 2026-11-25, that spreads connotation (dying's FEEL+ to "last"), not identity.
  Sensory attributes: a head whose attribute is a visual, sound or tactile property, and its satellites,
  carry SEE, HEAR or TOUCH (colors are SEE: 12 heads, 291 satellites; loudness and pitch HEAR; coarse
  and fine TOUCH). Taste, smell and temperature have no prime and assert nothing.
- [ ] SP-4 Round 2 identity roots: state.n.02 BE (Rohan's "own state denotation is sufficient for
  BE=+1"; the reserved nonbeing branch excluded), make.v.03 and induce.v.02 CAUSE, be.v.01 BE, get.v.01
  HAVE, equal.v.01 SAME, enter.v.01 and leave.v.01 MOVE; stated causatives (218 verbs) CAUSE.
  Derivation: an act or event noun takes the identity every derivationally related verb shares
  ("departure" MOVE, "touch" TOUCH); about 1,350 nouns before the strict all-verbs condition. Agent nouns
  ("teacher") and verb entailment remain.
- [ ] SP-5 Measure H, C and L per channel after each round; rebuild senses; publish.

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
