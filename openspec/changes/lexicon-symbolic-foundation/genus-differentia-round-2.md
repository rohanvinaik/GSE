# Task: genus/differentia closure, round 2 (Rohan, 2026-11-26: "Agreed on your reads. Please proceed")

Round 1 (commits 2d2b459, 4152375, df7d911; receipt `docs/verification/2026-11-26-genus-differentia-closure.json`;
module `GSE/curation/lexicon_builder/word_sense_genus_differentia.py`) settled 29,779 cells. Its receipt shows why so
few: 12,264,821 open cells sit under an open genus, and 3,361,095 sit behind an open differentia word. Read round 1's
code and receipt in full first. Then make these four approved changes in that module and its script, with tests.

## The four decisions (all approved by Rohan)

1. **Word senses read the derived values.**
   - `GSE/curation/lexicon_builder/word_senses.py` reads the `derived:genus-differentia` channel as member evidence.
   - `tests/test_lexicon_every_value_has_a_warrant.py` gains a `genus-differentia` warrant kind. A value with that
     kind must trace to a stored closure record: its axiom or genus edge, plus its differentia. You may edit this one
     guard test for exactly that purpose.
   - Derived values never become stated source assertions. Nothing may use them to confirm themselves.
2. **A differentia contributes its content, never its noun's identity.**
   - A differentia word's substantive identity banks (SOMEONE, SOMETHING, PEOPLE, BODY, KIND, PART, WORDS, WHEN,
     WHERE, ALIVE as identity) never carry to the kind. "Sterling" must not get WHERE+ from "Scotland", "minaret" must
     not get SOMEONE+ from "muezzin", and a citation name in a gloss is not differentia.
   - Its predicate content (DO, HAPPEN, MOVE, FEEL, THINK, SAY, CAUSE, …) does carry.
   - Derive the identity-bank set from the NSM chart's categories (substantives, relational substantives,
     life/place/time), which are in `lexicon_builder/catalog.py`. Do not hand-pick it.
3. **WordNet's roots and main genus words become axioms, seeded from the NSM prime bindings.**
   - Each root gets the identity its own prime binding or gloss states: `entity` is SOMETHING, `person` is SOMEONE,
     `time_period` is WHEN, `location` is WHERE, and so on.
   - Use the existing anchor table `wordnet_hierarchy._WARRANTED_ROOT_PRIMITIVES` and the release's `prime_entries`.
   - Write every root axiom, with its warrant, to a reviewable table in the receipt, so Rohan can strike any entry.
   - A root axiom states what the root IS. Its other banks follow the same law as everything else.
4. **The 16 NSM units with no settled bank become axioms on their own bank.** These include die, live, time, place,
   some and mine. Take each unit's bank and sign from `catalog.py`'s `_EXACT`/`_ADAPTED` maps, and record it.

## Then

- **Re-run the closure** from the live candidate `data/lexicon_builder/2026-11-12/sparse-release-022-verbnet-do.db` to
  a new output beside it.
- **Measure** with round 1's own measure. Report:
  - H before and after;
  - per-bucket gains, as axiom cells versus propagated cells;
  - contradictions by type;
  - open cells by cause, compared with round 1.
- **Rebuild word senses** on the output, then run `--verify 300` and the sense, guard and warrant tests, with real
  exit codes.
- **Witness the reading of these five sentences** with `GSEEncoder(db_path=<output>)`:
  - "The happy dog runs to his mother."
  - "She gave the boy a big lock."
  - "I want to know what you see."
  - "The sad man cut the rope."
  - "My friend loves the beautiful house."
- **Sample check:** for 30 newly settled cells across buckets, write the cell, the value, and its full chain (axiom →
  genus edges → differentia). Flag any that read as wrong.
- **Delete round 1's five superseded files** listed in its receipt.
- **Write the receipt** to `docs/verification/2026-11-26-genus-differentia-round-2.json`.
- **Commit** on main, with no AI attribution in commit messages, and push.

The full replay takes longer than your shell allows. Leave its command in the receipt and the main session will run
it.

## Hard constraints (as round 1)

- No model decides a value.
- No thresholds, samples or votes admit anything.
- No hand-authored word-to-bank tables. Root axioms come from the existing anchor table and prime bindings, each
  listed with its warrant.
- Pinned builder files are read-only, as are all guard tests except the one warrant test named in decision 1.
- Don't touch `data/lexicon_active.json`.
- Check pytest's real exit code. Pass test lists with `$(cat file)`.
