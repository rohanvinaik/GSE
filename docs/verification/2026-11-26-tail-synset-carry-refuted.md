# Tail fix measured and refuted: the synset carry (2026-11-26)

Part of the NSM-disagreement tail (`openspec/changes/lexicon-symbolic-foundation/nsm-disagreement-tail.md`). The fix was
measured before it wrote anything. It is refuted and was not built.

## The candidate fix

Some WordNet definitions sit under a spelling that is not in the synset's own `lemma_names`. For example,
`wordnet:dogs:dog.n.01` sits under "dogs". The release's reviewed rules carry the guard `wordnet_native_lemma=true`,
so they do not reach these definitions. The vertebrate BODY rule, for instance, gives `wordnet:dog:dog.n.01` BODY+ but
leaves `wordnet:dogs:dog.n.01` without it.

The candidate fix: a derived-spelling definition of synset S takes the values that S's native-spelling definitions
hold, on banks it does not hold itself. The proposed warrant was WordNet's synset identity plus the native
definitions' stored, replay-validated values.

## Measured

Command:

    .venv/bin/python scripts/word_sense_nsm_tail.py --db data/lexicon_builder/2026-11-12/sparse-release-022-senses3.db \
        --receipt docs/verification/2026-11-26-nsm-tail-classes.json \
        --synset-carry docs/verification/2026-11-26-tail-synset-carry-measured.json

Receipt: `docs/verification/2026-11-26-tail-synset-carry-measured.json`. The measurement code is
`word_sense_nsm_tail.synset_carry`, which is measurement only and writes nothing.

| Check | Result |
|---|---|
| Derived-spelling definitions that have a native sibling | 40,719 |
| Definitions that would gain values | 9,365 (4,320 lemmas) |
| Cells that would be filled | 20,762: DO+ 5,000, HAPPEN+ 4,624, YOU 0 3,432, I 0 3,431, CAUSE+ 2,329, MOVE+ 1,093, FEEL+ 260, BODY+ 132, … |
| Clashes with stored values | 0 |
| Cells that reach a verified NSM explication | 15 |
| Of those, agree (+1 on a bank NSM uses) | 10 |
| Of those, NSM counterexamples | **5** |

The five counterexamples:

- G12 408–414 (hands):
  - `hands:hand.n.01` WANT 0
  - `hands:hand.n.13` WANT 0
  - `hands:hand.n.09` BODY 0
- G12 481–486 (legs):
  - `legs:leg.n.01` WANT 0
  - `legs:leg.n.02` WANT 0

In each case the explication's own clauses use the bank with a positive sign, and the carry would write 0.

## Verdict

The fix is refuted (task rule: zero NSM counterexamples, or it is refuted). It is deleted, not re-scoped. Restricting
it to nonzero values after seeing these five would be the tuning the task forbids.

Two facts for Rohan. Neither rescues the fix.

1. The scope was never mine to widen. The release excludes derived spellings on purpose. The design's "Native identity
   guard for population rules" (`docs/program/LEXICON_CONSTRUCTION_DESIGN.md`) calls this "an identity abstention".
   For example, `as`→angstrom and `ms`→metre reach their synsets only through morphology. The design also says
   "ordinary verified inflections should eventually reuse the established identity/morphology machinery". Whether and
   how to do that is Rohan's decision; it is recorded in tasks.md.
2. The WANT counterexamples sit in clauses where the possessor (someone) wants and the hands or legs move as a result.
   `template_types.own_lines` counts such a clause as the referent's own, because the clause names the referent and
   its subject is not on the participant list. The stored WANT 0 on the native `hand.n.01` and `leg.n.01` therefore
   already disagrees with NSM under this instrument; the carry only copies it.
3. The BODY 0 counterexample lands on `hand.n.09`, the unit-of-length sense. NSM's explication is of the body part.
   The counterexample exists because the test compares the explication with every sense of the word, not only the
   sense it explicates.

Even unrefuted, the carry would change no reading-level agreement in the NSM measurement. Read through its base lemma
(child, woman, bird, dog, animal, …), each plural explicandum agrees on exactly the same primes: 19 agree and 4
contradict, before and after. The senses that would gain sit beside other senses that do not hold the bank, so the
reading still leaves it open.
