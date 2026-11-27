## 0. Clear the old construction path

- [x] 0.1 Move the NSM chart data that the runtime imports (`SOURCE`, `_CHART_BOXES`, the chart records and prime
  links) from the old `catalog.py` to `GSE/curation/external_sources/nsm_chart_data.py`. Move the two WordNet
  identity helpers (`_attested_wordnet_lemma`, `_exact_wordnet_ancestry`) to the WordNet source module. Repoint
  `GSE/symbolic/lexical_grounding.py` and `external_sources/nsm_chart.py`.
  Acceptance: encoder and grounding tests pass with a zero pytest exit code; neither module imports the old package.
- [x] 0.2 Delete the old builder code in `GSE/curation/lexicon_builder/`, keeping only the authored data files
  (`prime_profiles.json`, `bank_laws.json`). Delete `GSE/curation/cli/commands.py`, the scripts and tests that
  exercise the old builder, the old OpenSpec change `lexicon-symbolic-foundation` and
  `docs/program/LEXICON_CONSTRUCTION_DESIGN.md`. Point `BUILD_SPEC.md` GSE-01 at this change.
  Acceptance: no file outside the records imports the old modules; the remaining test suite collects and passes;
  the live lexicon and the active pointer are unchanged; the records in `docs/readings`, `docs/verification` and
  the archives are untouched.

## 1. Pin the inputs

- [ ] 1.1 Write the source manifest: every parser, its snapshot digest, its declared competence (banks it may and
  must not write) and its binding rule. Account for all 401,596 readings, including the difference from the four
  source subtotals (401,593).
  Acceptance: every reading has a source and a binding kind; no old assignment enters as a premise.
  Progress (2026-11-26): `inventory.py` pins the cohort from the live artifact's identities (id, lemma, POS, gloss;
  no values): 401,596 readings = 155,111 WordNet + 246,240 Wiktionary + 213 closed-class + 29 NSM chart + 2
  authored GSE primes + 1 Webster's 1913, over 67,174 lemmas; sha256 67f91348...; receipt
  `docs/verification/2026-11-26-rebuild-cohort.json`. Still to do: each source's declared competence and binding.
- [ ] 1.2 Write the bank registry: the 56 banks, polarity aliases, which banks are bipolar and the starting mask of
  each.
  Acceptance: matches the runtime's coordinate registry; NUMBER and hierarchy stay separate.

## 2. State, ledger and closure at population scale (E1, E9)

- [x] 2.1 `cells.py`: the (readings x 56) mask array, dense ids, starting masks, H and the census.
  Acceptance: round-trips +1, -1, 0, SILENT, unresolved and empty (conflict); the opening H is measured and saved.
- [ ] 2.2 `ledger.py`: append-only observations and derivations with premise lineage.
  Acceptance: two derived cells cannot certify each other without a root; every removal names its cause.
- [ ] 2.3 `relations.py` and `closure.py`: guarded tuple relations applied to whole populations as mask
  operations, with a worklist of changed cells and edges, to a fixed point.
  Acceptance: a synthetic population shows a single-bank consequence, a conjunctive consequence (F073: two premises
  remove a state neither removes alone) and a forced placement. Cold and incremental runs agree, the result does not
  depend on order, and a full-size run over 22.5M cells completes in minutes.
  Progress (2026-11-26): `relations.py` and `closure.py` written; 9 tests pass (`tests/test_lexicon_population_closure.py`).
  Timing: 113 relations over all 401,596 readings (22,489,376 cells) closed in 2.9 s. Opening H with every cell at
  its starting mask: 37,978,301 bits. Still to do: the cold-against-incremental replay check.

## 3. Source lenses (E2)

- [x] 3.1 `projection.py`: every parser's observations into the ledger under its declared competence. Ratings,
  associations and classifier outputs are recorded but write nothing.
  Acceptance: the field-to-bank map is published; a wrong-role observation and an incompetent source each get a
  named disposition; the directly decided cells are counted by source and bank.
  Done (2026-11-27, by the lenses implementer; reviewed): `projection.py` implements the authored contracts in
  `bank_laws.json`. VerbNet's native predicates are bound by exact WordNet 3.0 sense keys and hold only in every
  frame of the class. USAS and FrameNet bind at lemma and part of speech, so they give obligations. They decide
  3,589 cells (MOVE 796, CAUSE 1,025, DO 1,023, HAVE 259, EXIST 177, TOUCH 143, FEEL 88, START 39, WANT 23,
  ALIVE -1 16) and 190 obligations in 103 groups, with 0 conflicts; H falls a further 5,711 bits after the laws.
  Ratings wrote nothing. Receipt: `docs/verification/2026-11-26-rebuild-source-lenses.json`. Open items: the
  authored `definition_boundary` silences of EMOTION_FEAR_ADJ need compiling as a law; negated predicates
  (`source_polarity`) are not yet used; guard facts reach a reading only once its obligation is forced.

## 4. Prime foundation (E3)

- [ ] 4.1 `primes.py`: the 72 primes and the function words, with content, declared silences, absences and frames.
  Acceptance: 4,032 prime cells are decided, each with its authored warrant; removing a warrant reopens its
  consequences.

## 5. Relations between banks from NSM (E4)

- [ ] 5.1 `nsm_laws.py`: compile the chart's categories and frames, the reviewed head laws, valency, and molecules
  and templates from the verified explications into relations, each with its warrant and must-not witness.
  Acceptance: on real readings, a cross-bank consequence, a conjunctive consequence and an exclusion (F067:
  evaluator against descriptor) each fire within their scope and not outside it; every relation names its source
  passage by key and line range (the NSM texts stay out of git).
  Progress (2026-11-26): `laws.py` compiles the 16 authored laws (`bank_laws.json`) into relations, and `guards.py`
  computes only warranted guards (verb -> lexical predicate; adjective -> modifier, F088; authored substantive
  primes). First full round over the cohort: 1,253,536 cells decided (all zeros: substantive banks of verb and
  adjective heads, SOMETHING of adjectives), H 37,978,301 -> 35,991,475 bits, 0.31 s. Guards with no warrant yet
  (affective feeling, change of place, evaluator, size, Fear frame, valence domain, operators, time and place) select
  nothing until the source lenses (task 3) establish them.

## 6. Inheritance (E8)

- [ ] 6.1 `inheritance.py`: typed edge families with the properties each carries; defaults with applicability and
  declared defeaters; conflicting defaults suspended; hub silence never carried.
  Acceptance: `creatures` gives `animal.n.01` MOVE and FEEL and its kinds inherit them; a kind using a prime its hub
  never mentions does not inherit silence; retracting a misfiled link defeats only what depended on it.

- [ ] 6.2 Wiktionary bindings: `form_of`/`alt_of` and `synonyms` as edges or obligations to the target lemma's
  readings; the exact anchor alignment to WordNet senses (design E8); categories and topics as domain facts.
  Acceptance: an alignment exists only where exactly one candidate has a linked word's synset among its ancestors;
  zero or several candidates abstain; content crosses an alignment only as a suspendable default.

## Execution (2026-11-26)

Implementation is delegated: each task goes to an implementer with a written brief, owning disjoint files, and is
reviewed against this design before it is committed. Wave 1, running: source lenses (`projection.py`, `guards.py`);
inheritance and cross-reading obligations (`inheritance.py`, `obligations.py`); coherence and admission
(`coherence.py`, `admission.py`); NSM content (`nsm.py`). Next: Wiktionary bindings (6.2); the round runner and its
receipt; senses and the runtime artifact (10.1).

### Findings and rulings (2026-11-27)

- **Obligations force nothing yet** (0 of 103 lens groups, 0 of 2,274 NSM obligations). The nearest groups are the
  same sense in WordNet and in Wiktionary, so the Wiktionary binding (6.2) is the unlock. NSM obligations are being
  narrowed to the readings typed by the explication's head-line category (a typed alignment proof, E2).
- **Verb inheritance reaches spurious cells** (43,503 inherited cells; e.g. MOVE on illuminate.v.03 and
  recess.v.02, CAUSE on acknowledge.v.04). There are three causes: a VerbNet sense key putting a physical class on an
  informational sense (communicate.v.01, impart.v.01); drift down deep troponym chains; class semantics applied to
  every member. Ruling: these cells stay interpolated, never known. They are audited against the NSM explications as
  complete meanings (F148: the tail is the disagreement with NSM by word, bank and rule). A disagreement names the
  link where the value entered, as a candidate defeater with its NSM warrant, decided by review (TrialLedger:
  "Defaults have declared applicability and defeaters"). Landed cells record their origin.
- `causes` carries the caused reading's content to the causer as a default and writes no CAUSE
  (`native_predicate_policy.lexical_component`). Zeros carry along kind-of and similar_to.

- **Coherence and admission** are committed (337c346). Confirmation comes only from stated observations of
  distinct roots (F108). Exposure, counterexamples and contradiction may also come from known strict consequences of
  the authored laws (TrialLedger: "Known is a source fact or a strict conclusion from known premises"); interpolated
  values count for nothing. A censor needs an antecedent bank (e.g. THINK forbidden if ALIVE=0): one conditioned only
  on its type is unexposed or contradicted by construction.
- **NSM typing:** a category of PEOPLE reads through "person", its suppletive plural, which is grammar. SOMETHING or
  THING gives no typing (`MOST_GENERAL_CATEGORY`).
- **Finding for Rohan:** the closed-class rows for `i` and `you` state SOMEONE +1, against the founder-approved
  one-hot law on substantive primes (F088). Both sources are kept, with the conflict recorded.

- **Wiktionary binding** committed (1cf07e0): 46,072 exact alignments; 12 obligation groups force; the Fear boundary
  fires; interpolated +1 63,660. Single-target form_of/alt_of classes are known; anchor alignments are interpolated;
  identity obligations are resolved between rounds by the runner. Sense-level synonyms carry +1/-1 only.
- **Round runner** committed (571dd5b). Its first run used an in-flight gate that admitted 25 VerbNet-only rules;
  that state was discarded. The corrected gate (acd83bc) admits 0 on main: only 9 of 2,041 readings with stated
  facts carry two datasets, so F108's cross-dataset witnesses do not yet exist at reading level.
- **A located obligation in the known layer** is its source family's own statement placed by strict structure. It
  can confirm, expose and contradict; one located only in the interpolated layer counts for nothing.
- **Next measurement:** coherence at the WORD level (F108: "relations between banks in single words ... words that
  exist in multiple datasets"), with exact every-time sets and NSM entailment as the symbolic validation (F101).
  Ratings are discovery-only families.

- **The Wiktionary-only tail, measured** (228a71a). 22,885 common definitions have no WordNet reading of their lemma
  and part of speech; 16,941 of them carry no structured evidence (no single-reading source fact, form link,
  Wiktionary hypernym or topic). Under E10 they join their word's core, but for these words the core itself has no
  evidence beyond the part-of-speech laws. This is the tail; F080 allows the gloss only for "the top 0.001%".
  Decision for Rohan when the bulk is measured.

### Rohan's decisions, 2026-11-27 (from the measured state: about 7% decided; hub reach top 50 = 7.2M cells)

- **Hub teaching by a bounded typed teacher over the Anthropic API** (SquishOS's reader; the key never reaches a
  sub-agent). F078 shape: one typed request per hub, its open banks as fields with their legal states, answer one
  state or abstain. A value is given only if it holds for every kind under the hub (the default's declared
  applicability). Answers are teaching premises with receipts at interpolated standing, carried by inheritance,
  suspended on conflict, and audited against the NSM explications. Top 50 hubs first; measure H before going on.
- **USAS contracts for prime-aligned verb categories,** with FrameNet corroboration where it exists (F115): M1 to
  MOVE, E1-E6 to FEEL with sign, L1 to ALIVE, Q2 to SAY, X3 to SEE/HEAR/TOUCH.
- **No noun GOOD-0 law.**

## 7. Censors (E7)

- [ ] 7.1 `censors.py`: scoped forbidding relations with sourced near-miss witnesses; zero only with a warrant of
  explicit absence; SILENT only with a warrant of silence; a signed value only with a positive root.
  Acceptance: the valency censor is re-derived and admitted through task 8's gate; elimination down to one sign
  without a root is reported as a missing content warrant, not written.

## 8. Coherence and admission (E5, E6)

- [ ] 8.1 `coherence.py`: agreement and conflict among independent lenses per reading; population postings;
  candidate relations with exact witness, counterexample and unknown sets.
  Acceptance: two encodings of one observation count once; unknowns are neither confirmation nor counterexample;
  nothing uses a rate, threshold or support count.
- [ ] 8.2 `admission.py`: the Significance Weighting gate (stated-fact confirmation, retained plurality,
  kappa > 0) and narrowing of oscillating candidates by an imputed type.
  Acceptance: a population-latent relation is admitted and changes closure beyond its discovery witnesses;
  self-confirming, association-only, redundant and overbroad candidates are refused, each with its verdict.
- [ ] 8.3 The loop: close, discover, admit, re-close, measure, until no admissible candidate adds reach.
  Acceptance: each round's receipt reports H, the census, and the admitted rules with their reach.

## 9. A full round (E9)

- [ ] 9.1 Run the whole build with zero model calls and record its receipt.
  Acceptance: every reading and bank is accounted for; timings and memory are recorded; the decided cells are
  compared, by warrant, with the live lexicon's stored states.

## 10. Senses and the runtime (E10, E11)

- [ ] 10.0 `senses.py`: the homonym and coherence collapse (design E10). Rohan, 2026-11-26: this is "something I
  addressed in my homynym/coherence multiple definition collapse concept that I laid out very explicitly". Unlinked
  definitions join their word's core; homonyms separate only on destructive interference.
  Acceptance: "lock" collapses to its genuine homonyms; an unlinked definition joins its core without changing it; an
  interfering pair separates with the bank named; an out-of-variance definition is kept apart; the census counts
  senses.

- [ ] 10.1 `senses.py` and `store.py`: senses by equal load-bearing encodings; the artifact in the runtime's form.
  Acceptance: "lock" keeps its genuine homonyms and one sense per part of speech without a frequency winner; missing
  evidence never merges; the encoder reads the artifact; the florbles sentence, chemical "He" against the pronoun,
  and ordinary prose pass through the real consumer.

## 11. The tail (E12)

- [ ] 11.1 `tail.py`, only after the bulk is measured: typed requests over residuals whose reason is a genuine
  bounded choice. The answer becomes a rule candidate.
  Acceptance: stale or illegal answers cannot write; an abstention leaves the cell open; no residual of another
  kind is sent.

## 12. Switch

- [ ] 12.1 Two-sign audit against held-out NSM explications and ordinary prose; set the active pointer when the new
  artifact is strictly better; delete the superseded copy.
  Acceptance: the audit counts false additions, omissions, polarity errors and zero/silence errors separately; the
  pointer moves only on a better artifact; at most three copies remain.
