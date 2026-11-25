# Engineering the existing lexicon path as one system

This bounded change implements GSE-01. The founder correction below governs: where
`docs/program/LEXICON_CONSTRUCTION_DESIGN.md` conflicts with it, the correction wins. Otherwise,
lexical authority and the dependency-ordered CP-01–CP-08 contract live in that document under
“Engineering execution: one checkpoint and a continuing learner”. Do not maintain an alternate
acceptance plan here.

## Founder correction (2026-11-24): why the lexicon was empty, and the design it must follow

### What happened

Release-022 has 401,596 definitions, all `PARTIAL`. An ordinary definition has about one narrowed
bank of 56, and that bank is mostly a part-of-speech zero. Measured on release-022:

- "happy": none of its 12 adjective definitions has a signed bank. Its evidence is stored, including
  SentiWordNet linked exactly to `happy.a.01` (positive 0.875), NRC-VAD valence 0.985 and NRC joy.
  The builder labels it "association", and association evidence may not set a sign
  (`evidence.py:925-927`, `:849-851`). The June build gave happy FEEL+ and GOOD+.
- The 68 rules: 23 can only force zero, 29 only pass on a sign that is already present, and 16
  create a sign, nouns only. None can produce GOOD, FEEL, BIG, HAVE, ALIVE, WANT, THINK, KNOW, SEE,
  SAY, MOVE or CAUSE. In a 4,000-definition sample, 0 of 597 adjectives and 15 of 2,417 Wiktionary
  definitions have a sign.
- Each definition is solved alone. Wiktionary definitions, about 60% of the total, get no WordNet
  evidence, so all 7 WordNet senses of "dog" are signed and none of its 25 Wiktionary senses are.
  Word-level records (2.9 million) attach to nothing.
- Discovery found 648 bank-to-bank coherence relations and checked them on held-out words. All 648
  are `DISCOVERED_NOT_ADMITTED` with `may_write_lexical_cells: false`.
- The model became the only route to the obvious banks, one bank question at a time. It has run on
  87 definitions (239 attempts) and has never been asked about FEEL.
- `founder:noun-own-evaluation` sets GOOD = 0 on every noun (208,553 derivations). Rohan has not
  yet reconciled F057 ("'Hatred' is a noun without value attached") with F066 ("words with strong
  encoding of emotive valence are not '0'").

None of this is a storage or guard bug. The agent-written design closed every route that Rohan's
design uses to turn evidence into meaning.

### Rohan's design, in his words

- "The presence of multiple definitions for a single word is not a hard problem to solve… There is
  a sane core that is the *real* and obvious meaning of the word."
- **Grammar first.** "Grammar is a constraint harness. It *rigidly* constrains the representation
  space of possible meanings of words." See `papers/Core Documents/GSE/sentence_architecture.md`.
- **Definitions collapse to the real senses by:**
  - the symbolic rules, used as "a constraint used to measure coherence", not an inviolate filter;
  - part of speech: "at least one for each part of speech" present;
  - coherence: "de-duplicate the core meaning of a word down to the really obvious, central
    elements", one "platonic ideal" for each genuinely distinct homonym.
- **Coherence is math.** "They're the same sense of the word if they resolve to the same bank
  encodings across the ones that are of high salience, that are definitional across the load-bearing
  banks, the ones that are resolved cleanly and well according to the symbolic rules." "Across a
  single word and single sense of that word, the meaning should be highly stable across the load
  bearing banks." Load-bearing is derivational significance (`SIGNIFICANCE_WEIGHTING.md`): a value
  derived against real alternatives, weighted by its downstream reach. This is the same question
  TrialLedger answers for clinical trials.
- **Meaning is interference.** The result "isn't *a* definition, it's an encoded vector of the
  concept… guided by constraint propagation across a set of ground truth and simple, deterministic,
  symbolic rules that constructively and destructively interfere".
- **From the founder record:**
  - Independent sources give "robust orthogonal decomposition of uncertainty" (F017).
  - Rules "*narrow* the decision space that the model selects between" (F047), and "the messy/hard
    tail is what the small model is FOR" (F119).
  - "A rule that is stable and coherent in the dynamics between banks IS a rule that can be built"
    (F101, F108).
  - A single pass fills "every rule-warranted cell", 40–50,000 words "in… minutes-to-hours" (F148).
- **Scope.** Proper nouns and jargon are handled elsewhere (the proper-noun and jargon systems,
  sparse-wiki). This lexicon resolves words' relational and grammatical meaning.
- When surviving senses disagree on a bank, the reading carries the set of possible signs (Rohan,
  2026-11-24).

### Design rules that follow

1. **Sources vote as orthogonal constraints, and only measurements count.** Each independent source
   family gives a sign per bank within its declared scope (`SOURCE_PRIMITIVE_SCOPE`). A sign commits
   only when two independent families that *measure* that bank agree and no measuring family
   opposes. Opposition leaves the bank open, carrying its possible signs.
   - Rohan, 2026-11-24: "I do NOT want crap in the lexicon. That's why I killed the 'clean
     lexicon'." The June rule (any two families) committed associations: Lancaster's hand/arm rating
     plus a topical tag gave "lock" BODY+ and DO+.
   - What each family measures is declared in `source_agreement.MEASURES`. Examples: VAD valence and
     SentiWordNet polarity measure GOOD; Lancaster measures SEE, HEAR, TOUCH and interoceptive FEEL,
     not BODY, DO or MOVE; WordNet's hierarchy measures its categories; VerbNet's predicates measure
     verb banks. The topical taggers and dictionary glosses measure nothing.
   - Rating lexicons count only strong ratings, read from their raw values (F066: "strong encoding
     of emotive valence"):
     - NRC-VAD valence |v| >= 0.5 for GOOD;
     - a genuine NRC emotion (joy, sadness, anger, fear, disgust, surprise; not trust or
       anticipation) for FEEL;
     - Lancaster interoceptive strength >= 3.5 for FEEL; genuine feelings rate higher, while
       words that cause a feeling rate lower ("dangerous" 3.2);
     - Lancaster perceptual strength >= 3.0 for SEE, HEAR and TOUCH.
     NRC-Emotion and NRC-VAD are one family (same lab, same method).
   - Correlated sources count as one family. A family votes only for the parts of speech it speaks
     to: VerbNet for verbs, WordNet's word-level projection for nouns, the ratings for the word's
     dominant use.
   - Lemma-level ratings attach only to senses they do not contradict.
2. **Rules narrow and propagate.** Stable bank-to-bank coherence relations are admitted as
   conditional rules once re-checked against current held-out words. Discovery that can never
   write is not a stage.
3. **A word's definitions collapse into senses within each part of speech.**
   - Definitions with the same load-bearing encoding form a group.
   - The main sense is the group holding the word's most common sense: WordNet's first, which
     WordNet orders by tagged-text frequency. This only decides which coherent group is the default.
   - When that first sense has no evidence, the main sense stays unresolved, unless at least three
     definitions share one encoding (coherence across definitions; a recorded judgment). An
     evidenced minority sense, such as buy's "accept as true" (THINK+), never stands in for the
     common one.
   - Without a WordNet first sense, the main sense is the best-supported group: the one sharing the
     most values with the sources' agreement, then the one with the fewest values no independent
     source corroborates, then the largest.
   - Another group joins a sense only if it conflicts with nothing and every value it adds is
     corroborated by an independent, measuring word-level family. A family cannot corroborate its
     own value. VerbNet's word-level vote is the union of a verb's classes, so it never identifies
     a sense. Otherwise the group is a different meaning: the "a man" sense of "dog" (SOMEONE+)
     stays apart from the animal.
   - Splitting needs a witness: a conflict, or an uncorroborated load-bearing value.
   - A definition with no load-bearing evidence is absorbed into a sense; it never becomes a sense
     of its own.
   - A sense's core is its members' load-bearing values, closed under the rules.
   - Part-of-speech conventions (GOOD = 0 on nouns, SOMETHING = 0 on adjectives, I/YOU = 0) are not
     load-bearing.
4. **No model writes a value.** Banks left open after 1–3 stay open until a source, a rule or an owner
   ruling closes them (Rohan, 2026-11-25). Models only run the analysis as agents.
5. **Runtime reads senses.** The sentence's part of speech selects a word's senses.
   - The reading is the main sense, the word's core ("the real and obvious meaning").
   - The other senses are carried as alternatives, with the banks where they differ and their
     possible signs.
   - Context that identifies one definition selects its sense.
   - A word is never refused for having several definitions.
   - Reading only what every sense shares erased the obvious meaning. One minority sense of "give"
     (THINK+) cancelled its DO+, though nothing in a sentence that fixes only the part of speech
     selects a minority sense.

### Completing the build, then the SSL loop

The founder-corrected base (rules 1–5) is a single deterministic pass. Everything after it is the
Semantic Completeness Equation of SSL (`Semantic_Specification_Learning/01_PAPER_SKELETON.md` §2.5)
run on the lexicon. These are the quantities, each computed rather than judged:

- **Degrees of freedom.** For each word sense *w*, Ω(*w*) is the set of bank assignments its admitted
  constraints still allow. The entropy is H = Σ_w log2 |Ω(w)|, measured by `specification.py`.
  Completeness(t) = 1 − H(t)/H0.
- **Teaching.** A fact is one committed (sense, bank) value: an owner ruling or an admitted rule. Committing it resolves 1 cell, plus κ further cells through closure under the rules
  and the senses (its marginal coverage). The equation is dH/dt = −Σ(1 + κ).
- **Curriculum.** Greedy maximum-κ order is (1 − 1/e)-optimal because coverage is submodular. The bulk
  (κ ≥ 2) falls exponentially. The tail (κ → 0) needs one fact per cell (I_solve). The knee H* is
  where κ collapses.
- **Rule learning.** A bank-to-bank relation that holds stably across the resolved population and on
  held-out words is a compression (F101/F108). Admitting it re-flows κ, and a bridge between two
  clusters is the largest jump.
- **Surprise.** A committed fact that contradicts a rule's prediction is a counterexample. It drives
  refinement: an exception, a narrower guard, or withdrawing the rule. Each is a named outcome, never
  a silent overwrite.
- **Reported.** Each epoch reports (H0, L = ∫κ/H0, H*, I_solve, Completeness(t)), so "is the lexicon
  done?" is a number.

Every value is computed by this symbolic process: sources, rules, coherence and closure. No model answer
becomes a lexical value (Rohan, 2026-11-25: "Just get it to run the analysis and report, not do
inference-driven nonsense"). A teaching fact is an owner ruling or an admitted rule. Models are used
only as agents that execute the deterministic packages and report.

### Founder correction 2 (2026-11-25): positive identity, propagated through structure

Rohan, 2026-11-25, after the build had settled 3.6% of the space: the lexicon is meant to be full, and
"this is a constraint propagation problem, not a statistics one where you mine a database for a random
match with a hand-tuned arbitrary filter." And, when the build swung to pure elimination: "You can't
define a thing only by what it's not ... A thing is a thing because it's a thing, not because it's not
not a thing."

What the build is, therefore:

- **Identity is positive.** Each definition's value is what it IS, stated by a source or carried through
  structure from what is stated: a dog is an animal, so it is ALIVE; a minute is an amount of time, so it
  is WHEN. Zeros are consequences of an established identity, never the identity itself.
- **Structure carries identity (SSL's C(H)).** The release resolved every definition alone, so a fact on a
  genus never reached its kinds and every round was linear (about 0.002% of the space per round). The
  structural relations the sources already state are the coupling: IS-A (identity roots: a synset whose
  own gloss is a prime's meaning, or the prime's approved binding, carries the prime to every kind),
  synonymy, adjective clusters (a satellite refines its head), antonym pairs on an attribute that is a
  prime (big/small on BIG), derivation (by part-of-speech pair), verb entailment and cause.
- **One layer.** Word-level agreed signs (happy: FEEL+ GOOD+) attach to the definitions of the word's main
  sense, so the structural channels carry them too; senses collapse from the propagated layer.
- **No statistics decides a value.** No thresholds, recall tests or samples admit anything. A relation
  either states the identity or it does not. A branch a source files wrongly (WordNet files all matter
  under part.n.01) is a reviewed exclusion with its reason, as the SAY exclusions already are.
- **Interference.** Agreement settles; a contradiction with existing evidence is recorded and the value is
  not stored. No stored value is ever changed.
- **Measure each round:** H = sum of log2 |domain|, the cells each channel settles (C), and L = C / H0.

### Superseded statements in `LEXICON_CONSTRUCTION_DESIGN.md`

These lines conflict with the rules above and no longer govern:
- :13, definitions keep separate identities;
- :124, SentiWordNet marks relevance only;
- :136, concurrence never admits a value;
- :325, model completion of the remaining banks as the main route;
- :597, never merge;
- :917, a source observation is not definitional content, read as forbidding signs from agreeing
  sources;
- :1056 and :1077, discovered coherence relations and the association catalog may not write.

"Unknown is not zero" (:13, :72) still holds: an open bank stays open.

## Ownership and composition

| Responsibility | Existing owner / seam | Required consumer |
|---|---|---|
| Definition identity and source competence | `GSE/curation/lexicon_builder/evidence.py`, `definition_frames.py`, `wordnet_identity.py`, native adapters | Shared resolver context and exact reading eligibility |
| Joint legal state | `engine.py`, `resolution.py` | Teaching, forecasts, migration, replay and runtime domains |
| Discovery | `discovery.py`, `grounded_rules.py`, reviewed export and `epoch.mine_scope_chains` | Persistent candidate work ledger in the next cycle |
| Teaching and audit | `completion.py`, `residual.py`, `model_protocol.py`, `reviewed_patterns.py` | Reclosed exact decisions; independent admission evidence |
| Exception learning | Existing refinement command, `rule_revisions.py`, `rule_reservations.py` | Revised candidate, fresh boundary audit and joint migration |
| Revision and history | `rule_admission.py`, `rule_migration.py`, `rule_history.py` | Replayed working head and invalidation of dependent queued work |
| Scheduling | `epoch.py` and existing durable completion scheduling | Informative next question using current legal alternatives and candidate interactions |
| Measurement | `specification.py`, epoch phase reports | Equal-budget comparison, checkpoint gate and experiment notebook |
| Publication and consumption | `publication.py`, `lexicon_resource.py`, `GSEEncoder`, `publish_round` | One installed sparse successor and the next learning baseline |

Paths without a prefix in the table are within `GSE/curation/lexicon_builder/`. Split controller
responsibilities into focused modules there if needed; do not create a parallel construction stack.

## Representation boundary

The production basis is 56 ordinary lexical banks. Hierarchy and NUMBER remain separately scoped
metadata. The upstream constructor uses 58 coordinates and authored silence. Adapt only mechanisms
whose contracts match, with representation/mask/provenance tests. No prime-only one-hot import,
blanket remaining silence, silence-to-zero conversion or spelling-based definition identity is
permitted. The original sources and model request identities survive namespace normalization.

## Persistent control state

Version the new controller schema rather than silently changing fixed version-1 plans. Keep
historical replay and exact journals. The current working store owns the canonical run/head,
candidate mechanisms, typed surprise work and resumable tasks; compact reports are projections
of that state. Record basis/cohort/source/rule/curriculum/model versions, candidate warrants,
lineage-separated witnesses, audit outcomes, dependencies and next actions. Version candidate
contracts and invalidate only work whose dependencies changed.

A candidate can await evidence, warrant, audit or refinement; be challenged, reserved, rejected,
already entailed, admitted or retired; or be operationally unavailable. Distinct dispositions
receive distinct remedies. A visited bit cannot permanently hide a reopened question. Concurrent
writers, changed inputs or incomplete transitions receive a named refusal, not silent resumption.

The canonical design defines the learning-head, candidate-mechanism, surprise-work, next-work
and transition records and their consumers. Distinguish the published baseline from an unpublished
working head and preserve its migration lineage. The present active-baseline publication check
must be reconciled with this protocol; relabelling the current foundation candidate as active is
not an admissible shortcut.

## One cycle

1. Verify the working head and close admitted constraints using the existing resolver.
2. Measure legal joint space and regenerate eligible evidence/curriculum strata.
3. Consume discoveries and unresolved challenges, including newly grounded source-only candidates.
4. Stage candidate relations individually and together, preserving complementarity and limits.
5. Select a useful unresolved teaching or audit question from its legal alternatives and record it.
6. Validate the typed answer and closure; retain independent evidence and exact surprises.
7. Derive a warranted refinement or revision; independently audit the changed claim and boundary.
8. Apply reviewed additions, retirements, exceptions and reservations atomically; replay the full cohort.
9. Update the head, phase measurements and next work. Repeat or pin the passed checkpoint.

Each accepted residual answer can restart broad discovery. A rule already entailed by the admitted
closure is a shortcut, not newly acquired semantic information. A new candidate cannot approve
itself, supply its audit target, or become a premise before admission. Typed model calls remain
bounded word–bank rulings, not free-form rule authorship or whole-vector completion.

The generator's initial templates may be finite, but useful discoveries are no longer confined to
opening families. Extend tuple and guard vocabulary through the shared Relation/native-context
contracts with explicit warrants and tests. A bounded or exhausted search is reported relative to
that language, never as proof that no further symbolic structure exists.

## Refinement and retained plurality

Independent counterexamples retain the exact reading, context, conflicting values/combinations and
parent proof. Route wrong identity to existing grounding, unsupported projection to its adapter,
missing conditions to reviewed guard refinement, and genuine exceptions/reservations to the joint
revision path. A model disagreement alone is not the correction's authority. Do not suppress a
lawful alternative to make the rule pass. Unknown guards activate nothing. Review a semantic
boundary only when sources and the approved contract cannot settle it.

## Measurement and budgets

Use the exact joint H from `specification.py` with complete-count coverage, plus separate marginal
potential, filled/explicit-zero/unresolved/reopened counts and the pinned frequency buckets. Save
baseline, direct-teaching and post-revision results. Counterfactual replay distinguishes propagated
teaching effects from newly admitted rules and avoids double-counted overlaps. `compare` must
consume those measurements; it cannot retain a singleton-only success predicate.

Equal-budget arms share frozen initial evidence/cohort, discovery language, model/protocol and
accounting policy, while their learned trajectories may differ. Report actual teaching, audit,
review and execution costs separately. Unequal actual budgets or unavailable counts leave the
comparison incomplete. Exponential bulk learning is an observed H/amplification trajectory under
its stated conditions, not a conclusion from one large forecast or a log-count identity.

## Bounded storage and recovery

Keep the active release, its single rolling predecessor and one working head. Permit bounded
owned staging files during an atomic transition. Compact evidence/rule/model/transition records
must reproduce historical decisions without retaining every teaching.db/candidate.db. Resume
must validate event/head identities rather than require deleted intermediate database paths.
Protect source data, audit records and other sessions' files. Test interruption at each boundary
before enabling retention. Use the existing publication and retention mechanisms, not another
release tree or pointer.

## Checkpoint boundary

Freeze the workload manifest described in the canonical design: source/frequency/corpus pins,
90% eligible token-mass cohort in both sources, promised NLP operations and required banks,
independent two-sided labels, development/final split, explicit critical outcomes, and whole-build
replay/gates. Frequency is importance; current marginal coverage is leverage. Keep all senses and
all tail definitions in the dictionary accounting.

A final audit used to guide a correction becomes development evidence. A critical unresolved or
wrong result blocks its promised operation. Finite sparse-runtime probes do not establish general
usability. Repair closed-class contextual eligibility, including he/He, through the real encoder.
A passing sparse checkpoint preserves its unknowns and states its workload limitations. Continue
from that installed release using this same controller; whole-lexicon completion remains separate.

## Verification and current blockers

### Checkpoint-first execution update — 2026-11-24

The direct owner deadline defers generic controller completeness until after the
usable checkpoint; it does not defer its validity gates. Controller-owned code
now has exact request-context archival, a durable head CAS, owned-stage retirement
with native/unique-audit preservation, explicit model-prefix review, a reviewed
joint-revision intake and bounded explicit entry–bank work on the sustained
writer. Its 1,800-test scoped pass includes crash recovery after obsolete files
are removed and the actual Regenesis refinement integration. It is not the
integrated gate, a real linguistic admission, or a full CP-02–CP-06 receipt.

The catalogue repair and subsequent full replay are already recorded as valid;
the older failed catalogue/fixture observations below remain historical. The
active pointer still names 021. The v2 rebase preserves the original v1 plan and
water/I wire identity. Fresh reference audits are being supplied by the root's
pinned local transport; ordinary admission, full-corpus joint revision/replay,
usable-workload acceptance and the runtime peer's repaired code-freeze receipt
remain prerequisites to activation. Generic joint-tuple discovery and complete
source/identity/projector surprise correction remain deferred, not declared done.

Use the scenario requirements and checklist, then real corpus execution and full replay. CP-01
currently includes the failed catalogue refresh and reference-bank fixture failures. CP-02–CP-06
cover the controller feedback, comparison and retention gaps. CP-07 includes the reproduced wrong
pronoun selection in the chemical-symbol sentence. None is closed by this design edit.

Original upstream foundation, ordinary-family, native-role and independently rooted provenance
controls remain reusable regression obligations. Their historical counts or authored boundaries
are not evidence that the production current-basis checkpoint passes. Detective is explicitly
deferred; retain that status rather than claiming the prescribed mutation gate ran.
