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

- [ ] 3.1 `projection.py`: every parser's observations into the ledger under its declared competence. Ratings,
  associations and classifier outputs are recorded but write nothing.
  Acceptance: the field-to-bank map is published; a wrong-role observation and an incompetent source each get a
  named disposition; the directly decided cells are counted by source and bank.

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
