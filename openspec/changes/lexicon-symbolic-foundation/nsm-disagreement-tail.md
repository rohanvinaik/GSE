# Task: resolve the lexicon's disagreements with NSM (the tail, F148)

Approved by Rohan, 2026-11-26 ("Finally, a reasonable place to wait for my approval. Given"). This task replaces the
work packages named in the launcher's TASK. The launcher brief's hard rules 1, 2, 4, 6 and 7 apply unchanged; its
rule 3 (the statistical coherence admission policy) does NOT apply here: admission in this task is by the NSM
counterexample test below.

## What the tail is (Rohan, F148, verbatim)

"What that tail is comes from the informational disagreement/surprise between the rules/symbolic layer we build ...
and what NSM has hand-built over the past 50 years. That informational disagreement is where we get strict 'surprise'
as a teaching signal, then we can plow it over the full 40-50K lexicon. Disagreements are identified per-word,
per-bank, and per-source/rule that caused the disagreement, then resolving THESE disagreements is where the small
model work comes into play!"

You resolve disagreements by finding their cause and writing the symbolic fix (a rule over source data, in code). You
never write a value. The fix is then applied by the build to the whole lexicon.

## Inputs

* The disagreement measurement: `docs/verification/2026-11-26-lexicon-vs-nsm.json`, made by
  `scripts/lexicon_measure_vs_nsm.py` (re-run it with `--db <candidate>` on anything you build). 35 explications of
  words in the live lexicon: 41 primes agree, 369 are open in the word's reading, 12 are held otherwise (GOOD 0 on
  nouns under F057; SOMETHING 0 on "childlike").
* The verified NSM explications: `data/external/references/notes/explications/*.verified.jsonl` (248 records:
  Goddard 2018 menagerie, Goddard & Wierzbicka 2014 Words and Meanings, GW 2016 doing/happening, GW 2007 physical
  qualities, Goddard 2012). They are copyrighted and git-ignored: never commit their text, only source keys, line
  ranges and bank names. `GSE/curation/lexicon_builder/template_types.py` reads them (`own_lines`, `banks_in`).
* The live lexicon (active pointer): `data/lexicon_builder/2026-11-12/sparse-release-022-senses3.db`. Build any
  candidate on a copy beside it; never touch `data/lexicon_active.json`.
* The reviewed foundation: prime profiles and bank laws (`prime_profiles.json`, `bank_laws.json`,
  `prime_profiles.py`), the approved WordNet identity roots (`wordnet_hierarchy._WARRANTED_ROOT_PRIMITIVES`), the
  founder words `docs/program/LEXICON_FOUNDER_WORDS_2026-10-24.md` (F001-F160: the design).

## The work

1. Classify every disagreement (word, bank) by cause. Read the word's definitions, senses, stored values and the
   sources that observe it. Typical causes: a sense that holds the value is outvoted or split from the others; a
   source field that establishes it is not projected; a reviewed rule's scope excludes it; the NSM prime is
   explication scaffolding rather than the word's own content ("of one kind", "like this", "can" before a capacity,
   GOOD/BAD in a clause about what happens to the referent). Decide scaffolding from NSM's own template structure
   (section labels, the category line), never from your judgment of the word.
2. For each cause that a source or reviewed rule can fix, write the fix as code (a sense-level rule module
   `GSE/curation/lexicon_builder/word_sense_*.py`, applied by `scripts/build_word_senses.py`), with a test.
3. Before any fix writes a value, measure it:
   * against every verified NSM explication it reaches (zero counterexamples, or it is refuted);
   * against the values already stored (a clash is a counterexample, never overwritten);
   * its coverage over the whole lexicon.
   A refuted fix is deleted, not tuned; record it in `docs/verification/2026-11-26-tail-<name>-refuted.md`.
4. Rebuild word senses on a copy of the live lexicon with the admitted fixes, run
   `build_word_senses.py --verify 300`, re-run the NSM measurement on the copy, and run the encoder test files
   (`grep -rl GSEEncoder tests --include='*.py' | grep -v _archive`; real pytest exit codes; the only accepted failure
   is `test_GSE_genealogy_store.py::test_world_strand_returns_thing_rooted_lineage`, sparse-wiki's data).
5. Commit each step that passes with its receipt. Finish with
   `docs/verification/2026-11-26-nsm-disagreement-tail.md`: each disagreement class, its cause, the fix or why there
   is none, each fix's warrant, its NSM and stored-value counterexample counts, cells changed, and the before/after
   measurement.

## Never (Rohan's rulings; each has a measured failure behind it)

* No statistical lexicon writes a value: SentiWordNet, NRC VAD, NRC emotion, concreteness and Lancaster are
  classifier or rating outputs; they may only corroborate (the felt-valence rule was deleted for this, 5d018f0).
* No identity or genus read out of free gloss text (measured and rejected:
  `docs/verification/2026-11-26-wiktionary-genus-identity-measured-not-built.md`).
* No zero by exclusion, closed world or "not derived". A confident zero only from a warranted channel (the pattern
  is `valency_absence.py`: reviewed valency plus an NSM corpus check). "A positive definition can never be assembled
  through pure exclusion."
* No category-to-prime mapping you author gates anything until NSM's explications fail to refute it (WordNet verb
  categories and hub silences were refuted: `docs/verification/2026-11-26-verb-category-primes-measured-not-built.md`,
  `docs/verification/2026-11-26-hub-silence-vs-nsm-subkinds.json`).
* No list of words with values in code, and no main or default sense (Rohan, 20:20: the reading is what the senses
  agree on).
* A semantic judgment no source or rule settles is Rohan's: write the question in tasks.md and move on.
