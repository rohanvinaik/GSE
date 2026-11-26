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
- [x] GD-1 Whole-population genus/differentia closure (Rohan, 2026-11-26). `GSE/curation/lexicon_builder/word_sense_genus_differentia.py`
  and `scripts/word_sense_genus_differentia.py` (edges, close, measure, verify) do the following:
  - Axioms: the primes whose own bank the release settles, and the closed-class grammar. Their open banks are set to 0.
  - Genus: WordNet hypernyms, or the head the definition linker parses from a Wiktionary gloss. A genus word with
    several definitions carries all of them (their union).
  - Differentia: the parsed clause heads.
  - One joint constraint per definition goes through `resolve_dictionary` under the release's rules, and passes repeat
    to a fixpoint (12 passes).
  - Output: `sparse-release-022-genus-differentia-closure.db`, the live release plus three derived-channel tables. All
    29 release tables are row-for-row identical.
  - Result:
    - 10,074 definitions narrowed and 29,779 cells settled (15,464 zero, 14,315 nonzero). Of these, 13,214 are axiom
      zeros and 13,831 are nonzero values inherited from WordNet hypernyms, mostly CAUSE and HAPPEN on kinds of
      causative verbs.
    - H (sum of log2 |domain|) fell from 34,841,855 to 34,793,835 bits, a reduction of 48,020 bits or 0.14%.
    - Exact joint H fell from 32,707,235 to 32,666,770 bits.
    - Filled banks per definition rose from 1.26 to 1.34.
    - Contradictions: 16 primes whose own bank is open (not made axioms) and 1 stored conflict (hand.n.09 BODY), kept.
    - Word senses: rebuilt, verify 300/300, 65 tests pass. They are identical to the live release (0 filled, 0 changed,
      0 removed) because they do not read the derived channel.
  - Receipt: `docs/verification/2026-11-26-genus-differentia-closure.json`.
  - Why so little: of the open banks on definitions with an edge, 12.3M are open because the genus itself is open and
    3.4M because a differentia word is.
    - A Wiktionary genus word's definitions (act, state, quality, person: dozens each) union to open.
    - The WordNet roots are not axioms.
  - Not run: the full replay. It takes more than 10 minutes, the session's command limit, and nothing is written to a
    release table. The command is in the receipt.
  - Rohan decides:
    1. May word senses read the derived channel? The warrant test (read-only) admits only members, source-agreement
       and rules.
    2. Should a differentia noun's own identity banks carry to the kind? The law as stated does carry them.
       - 36 cells come from this, e.g. sterling WHERE+ via "Scotland", minaret SOMEONE+ via "muezzin", pavilion (verb)
         SOMEONE+ via a parenthetical citation "Robert".
       - Most are wrong as identity.
    3. Are the WordNet roots (entity.n.01, abstraction, the verb roots) or the main genus words axioms? Nothing else in
       the sources settles them, and they gate most of the lexicon.
    4. Are the 16 NSM units with no settled own bank axioms, and with which bank? die, live, time, place, some, mine
       and others. The catalog marks die, live and mine as unvalidated alignments.
  - Answered 2026-11-26 ("Agreed on your reads. Please proceed"): GD-2.
- [x] GD-2 Genus/differentia closure, round 2 (brief: `genus-differentia-round-2.md`; code 1b1ea94; receipt
  `docs/verification/2026-11-26-genus-differentia-round-2.json`). Output `sparse-release-022-genus-differentia-r2b.db`.
  - Decision 1: word senses read the closure's settled cells as member evidence of the lowest standing. A derived
    value fills a bank only where no stated value or agreed sign speaks to it, and only where every definition of the
    sense holds it. The warrant test gains the `genus-differentia` kind, checked against the stored closure record.
    - Unanimity was added after the witness: with "no disagreement" alone, one causative sense of 101 gave "runs"
      CAUSE+, and one definition of 49 gave "have" CAUSE+.
  - Decision 2: on the identity banks the kind takes its genus's state. Those banks are I, YOU, SOMEONE, SOMETHING,
    PEOPLE, BODY, KIND, PART, ALIVE, WHEN, WHERE and WORDS, from Goddard 2012 Table 1 (substantives, relational
    substantives, life and death, the TIME and PLACE exponents, and WORDS as named) and the catalog's bank map.
    - A capitalized differentia head is a name, not differentia: 565 removed.
    - A capitalized Wiktionary genus is a name, not a genus: 1,179 edges withdrawn. This was added after the sample
      check found primer WHERE+ via "England".
  - Decision 3: each of the 42 anchors in `_WARRANTED_ROOT_PRIMITIVES` is its identity and nothing more. The five
    anchors absent from the release stand in the graph with that identity. Every anchor already held its identity,
    so this adds 0 cells by itself. The review table is in the receipt.
  - Decision 4: 11 of the 16 units take their catalog bank and sign and are fully determined (56 cells each). The
    other five have no catalog sign: little-few, more, much-many, some, some-time.
  - Closure: 10,509 definitions, 31,327 cells (17,178 zero, 14,149 nonzero); round 1 was 10,074 and 29,779.
    - No cell has a different value than in round 1. 2,074 cells are new, mostly I/YOU zeros through differentia.
    - 526 round-1 cells are gone, 264 of them nonzero: identity from names and from differentia nouns.
  - H fell 50,394 bits (round 1: 48,020). Exact joint H: 32,707,235 to 32,664,646 bits. Filled banks per definition
    went from 1.26 to 1.34. Release tables are all identical.
  - Contradictions: 5 AXIOM_OWN_BANK_OPEN, 3 AXIOM_CONDITIONAL_EXCEPTION (the rules make long-time and short-time
    WHEN+ and side WHERE+), and 1 STORED_CONFLICT (hand.n.09, as before).
  - Open cells on edged definitions: genus 12.91M (was 12.26M), differentia 2.65M (was 3.36M), total down 65,777.
  - Word senses: rebuilt; verify 300/300; 82 tests pass, pytest exit 0.
    - Assigned values went from 254,128 to 266,786, nonzero from 130,612 to 131,225, and unassigned banks from
      5,696,600 to 5,683,942.
    - Against the live lexicon: 11,678 readings filled, 78 of them nonzero; 0 changed, 0 removed.
    - The five witness sentences read exactly as live.
  - Sample of 30 cells with their chains:
    - 22 read right.
    - 2 are wrong: they inherit stored values that WordNet files wrongly (shuffle THINK+, finale CAUSE+).
    - 3 rest on the adjective parser's numeral genus "two" (513 cells in all).
    - 3 are questionable.
  - Not done:
    - The full replay; its command is in the receipt.
    - Deleting round 1's five files and this session's intermediate runs (the shell refused rm). They are listed in
      the receipt.
  - Rohan decides:
    1. Should anything settle the roots' and main genus words' other banks? 12.9M cells wait on that.
    2. Should a Wiktionary genus word that names an anchor read as the anchored synset rather than the union of its
       senses?
    3. Keep or strike WORDS (Goddard 2012 files it under speech) and I/YOU as identity banks?
    4. May a numeral or quantifier prime be a genus? ("two" gives 513 cells.)
    5. Should catalog axioms be fully determined (die HAPPEN 0, be-somewhere WHERE 0), or state only their own bank?
    6. Which bank and sign, if any, for little-few, more, much-many, some and some-time?
    7. Closed-class axioms zero undeclared banks, so "nowhere" is WHERE 0. Should the curated entries declare them?

## NSM-disagreement tail (F148, 2026-11-26; brief `nsm-disagreement-tail.md`)

- [x] TL-1 Classify every disagreement with NSM's verified explications by computed cause. Done with
  `GSE/curation/lexicon_builder/word_sense_nsm_tail.py`, `scripts/word_sense_nsm_tail.py` and
  `tests/test_lexicon_nsm_tail.py`.
  - Receipts:
    - `docs/verification/2026-11-26-nsm-tail-classes.json`;
    - `docs/verification/2026-11-26-nsm-disagreement-tail.md` (the summary).
  - The 381 disagreements, from 35 explications (12 contradictions and 369 open primes):

    | Class | Count | Breakdown |
    |---|---|---|
    | CONTENT | 217 | no source vote 166; association families only 45; one measuring family 6 |
    | LOGICAL_OPERATOR | 41 | CAN 26, NOT 15 |
    | SENSE_SPLIT | 33 | |
    | COPULA_BE | 28 | |
    | TEMPLATE_FRAME | 27 | |
    | EXPONENT_COLLISION | 22 | the article "a" read as AS/LIKE |
    | CONVENTION_ZERO | 12 | GOOD on nouns 11, SOMETHING on childlike 1 |
    | DEICTIC_THIS | 1 | |

  - Of the 41 agreements, 11 rest only on THIS read as SOMETHING and 2 only on the collision.
- [x] TL-2 Fixes, measured before writing anything. None was admitted.
  - The synset carry was refuted. It would have given a derived-spelling WordNet definition its synset's
    native-spelling values: 20,762 cells, 0 stored-value clashes, but 5 NSM counterexamples (hands and legs, WANT 0
    and BODY 0). See `docs/verification/2026-11-26-tail-synset-carry-refuted.md`.
  - Cells changed: 0.
  - Rebuild on a copy of the live lexicon (`sparse-release-022-senses3-tail.db`):
    - verify 300/300;
    - against live: 0 filled, 0 changed, 0 removed;
    - 135,417 nonzero of 264,317 assigned values, and 5,933,651 unassigned cells, before and after;
    - NSM measurement 41 / 12 / 369, before and after.
  - Tests:
    - word-sense tests 65 passed;
    - the 66 encoder test files: 1,691 passed, 12 xfailed, and only the accepted genealogy-store failure.
  - The launcher's candidate `sparse-release-022-word-senses.db` was stale (47/300 mismatches against code unchanged
    since 5d018f0). It was rebuilt with `--all` and now verifies 300/300.
    - Its definitions come from bare release-022, before SP-1. Against live senses3 it shows 4,388 filled, 5 changed
      (the SP-1 BIG changes, reversed) and 16,439 removed (mostly SP-1 identity values). This run caused none of it.
    - This run's own comparison is the tail candidate: 0 / 0 / 0.
  - `lint-imports` has one broken contract from before this run: `GSE.symbolic.clause_selection` imports
    `valency_absence` (1585115).
- Rohan decides:
  1. GOOD on nouns (FC-7). NSM puts GOOD or BAD in the word's own clauses in 11 noun explications:
     - happiness +1 (GOOD inside a FEEL clause);
     - disease, violence, snake and children −1;
     - animals, dogs, kangaroo, trauma and parricide with both signs.

     The release's noun-evaluation zero (F057, D-1) holds all of them at 0.
  2. Derived spellings. 40,719 WordNet definitions sit under a spelling outside their synset's `lemma_names` (dogs,
     birds, accepted …). The native-lemma guard keeps reviewed rules off them on purpose ("identity abstention").
     Should verified inflections (for example Wiktionary `form_of` to a native lemma) carry their synset's values? The
     carry as measured is refuted, and its counterexamples come from question 4(e).
  3. Vertebrate BODY scope. NSM's animals and creatures explications use BODY, but animal.n.01 is outside the reviewed
     vertebrate rule. Widen it or not?
  4. The measurement instrument (`template_types`, `lexicon_measure_vs_nsm.py`; not this run's files to change). Five
     faults it could fix:
     - (a) the article "a" is read as AS, so LIKE (22 disagreements, 2 agreements);
     - (b) THIS is read as SOMETHING (11 agreements rest on it);
     - (c) every "is" and "are" is read as BE (28);
     - (d) signs are ignored: BAD, SMALL, OTHER and "inside" are −1 poles, which affects 28 content disagreements and
       the GOOD contradictions;
     - (e) clauses whose subject is a participant that `own_lines` does not exclude count as the referent's own,
       which produces the WANT counterexamples above and many THINK, FEEL and WANT disagreements.

     Should it be corrected before the tail is measured again?
  5. Operators and relations. Should a noun's banks carry the following at all?
     - CAN and NOT (41);
     - the referent's parts and their counts (PART, ONE, TWO);
     - PEOPLE from the category line of a plural human noun whose sense holds SOMEONE+.
  6. Sense split (33). Should the NSM comparison be made against the sense an explication explicates, rather than
     the reading? Under the no-main-sense ruling the reading stays open there.

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
- Answers, from the founder record and NSM (2026-11-26, after the run; none needed a new ruling):
  4. Done (04b104f): the matcher keys exponents as written plus WordNet bases of two or more letters (no article AS),
     returns signs, skips THIS and BE, and excludes bare someone/something subjects as other participants. Remeasured:
     43 agree, 7 contradict, 312 missing, 11 with both signs; classes CONTENT 217, LOGICAL_OPERATOR 41, TEMPLATE_FRAME
     41, SENSE_SPLIT 33, COPULA_BE 28, CONVENTION_ZERO 12, DEICTIC_THIS 1, no collisions.
  6. Done (04b104f): each explication is compared with the sense its own category line identifies (a molecule there,
     e.g. "creatures [m]", contributes its own explication's category); the whole-word reading only when no sense holds
     that identity. This is a measurement choice, not a main sense: the reading GSE uses is unchanged.
  5. No. F151: "combinability isn't content" (CAN and NOT scope a clause; they are not the noun's cells). F144's head
     record: a participant in a word's content is a role, not a cell (the referent's parts and their counts are
     participants). PEOPLE on a plural human noun is number, not the noun's identity.
  1. GOOD stays 0 on disease, violence, snake and children: F057, "'Satan' and 'Dog' do not have definitional value
     judgements"; NSM's GOOD/BAD there sits in clauses about what happens to or because of the referent. Felt valence
     on feeling nouns is ruling (c) (2026-11-25 05:30), already applied to feeling senses by D-1; happiness.n.01 is
     filed noun.state, so its sense is not a feeling sense and stays 0 until a source-located sign exists (the
     classifier-based felt-valence rule was deleted, 5d018f0).
  3. Keep the vertebrate scope: NSM's own "animals" explication (G18) gives BODY through "their bodies are like
     people's bodies", the vertebrate body plan; its "creatures" explication has no BODY ("something living / can
     move / can feel").
  2. Keep the abstention: the measured carry is refuted by NSM counterexamples (receipt above).

## GSE-02 — Complete the lexicon by running the SSL loop at population scale (2026-11-26)

Rohan, 2026-11-26: "There are several dozen million combinations of bank encodings and associations, the SSL-driven,
information-theoretic approach to constraint propagation ... tell you how to finish this." Basis:
`docs/readings/2026-11-26-build-completion-consult/` (his prompts, this contract and the theory, read independently
by GPT-6.2 Sol; Claude's reading recorded first). The unit of work is the rule, never the cell: each admitted rule
covers its whole population and becomes a premise for the next (C(H)). Completion means all 22,489,376 cells accounted
for (decided, or a typed residual with its reason), not filled.

Standing rules: one production state and path (no side layers the meter or controller cannot read); the model teaches
through typed questions and admitted rules write (07 draft, section 3; F078); family `derived` never confirms anything;
significance-weighting admission (spine-sourced confirmation, retained plurality, kappa > 0); zeros only by typed laws;
one live lexicon plus at most one build copy.

- [x] GSE-02.0 Baseline of the live lexicon (senses6) with `specification.measure_dictionary`: 32,707,151 joint bits;
  506,613 filled banks (331,373 explicit zeros); 21,982,707 unresolved; 54.74 unresolved per definition. It reads only
  the stored definition states.
- [ ] GSE-02.1 (pinned replay of senses6 validated: 401,596 definitions, 0 mismatches. First revision attempt failed
  on archived model receipts (MODEL_OBSERVATIONS_MISMATCH); fixed in e0b5c5a by leaving all 147 receipt-pinned
  definitions untouched; revision, senses rebuild, verify and re-measure re-running, chained)
  Install the derived layers into the stored definitions (`scripts/revise_lexicon_derived_layers.py`,
  source-revision path): sub-kind inheritance and form-of (inherited defaults only; their consequences re-derive),
  NSM molecule inheritance, NSM valency zeros. One `derived` observation per channel per definition; replay witnesses
  in `validation._validate_derived_witness`. Needs the pinned full replay of senses6 (running), then the revision with
  full replay, then promotion (build copy replaces senses6).
- [ ] GSE-02.2 Re-measure joint bits on the installed state; record the receipt.
- [ ] GSE-02.3 (generator written: `scripts/plan_population_epochs.py`; 18 scopes validated, run after promotion)
  Population-scale plan (`GSE.lexicon-epoch-plan/2`): all 56 banks; broad scopes by native POS and
  approved identity roots (selections, never values); larger frontier and candidate limits; no authored families
  (rules come from the controller's discovery over what it is taught); audits on held-out common words.
- [ ] GSE-02.4 Run `scripts/run_lexicon_epochs.py` (closure arm; local qwen3.8:27b-q8_0) on the build copy; joint bits
  per round; counterexamples to guard refinement or recorded exceptions; checkpoint when the common-use workload passes.
- [ ] GSE-02.5 Make the reviewed four-state laws (head laws F144, F067, F088's reading) release relations through the
  rule-revision path (today measurement only).
- [ ] GSE-02.6 Propagation speed: indexed fact, edge and rule-instance tables with a worklist, replacing per-definition
  SQL solves (30-40 definitions/s).
- [ ] GSE-02.7 Coverage beyond WordNet nouns and verbs. The first plan's scopes reach about 155k of 401,596 definitions;
  Wiktionary (246k) and adjectives/adverbs need witnessed native scopes (native frames, Wiktionary sense-to-sense
  bindings the sources state, cluster heads) before the loop can teach them.
- [ ] GSE-02.8 Teacher and audit. NSM's verified explications first (as teaching and as held-out audit), the local
  model second, and held-out audits for every rule before admission: rules amplify a wrong answer across a scope.
- [ ] GSE-02.9 Positive content deliberately. The curriculum targets positive identity and content banks (taught
  positives whose premises carry them across a scope), not only the closure-reach ranking, which favours exclusions.
- [ ] GSE-02.10 Completion criterion. A per-bank, per-channel census of all 22,489,376 cells (decided, typed residual
  with its reason) and the stopping rule (kappa -> 0, the SSL tail); report it every round with the joint bits.
Order: GSE-02.1-02.2 (running), then 02.6 (speed) before any long run; 02.3-02.4 start on WordNet scopes with 02.8's
audits; 02.7 and 02.9 widen the curriculum; 02.10 measures toward done.
