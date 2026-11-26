# Task: whole-population genus/differentia closure (Rohan, 2026-11-26)

Rohan: "The lexicon is supposed to be a functional symbolic system. That means the encoding must be useful and
complete AND it must come from a warranted source. For some reason I can't get agents to understand this--they
either resort to LLM slop to just plow through and fill the lexicon or they go on to build a series of complex
rules that fix 1% of the lexicon despite the ENTIRE thing being resolvable."

Today about 2% of the lexicon is resolved (1.26 of 56 banks per definition; 25% of definitions have none).

## The one law

The dictionary is a closed system of definitions, and every definition is a genus plus a differentia. That
structure is the warrant. It is not a population rule that needs teaching bank by bank.

- **Axioms.** The tier-0 primes are fully determined. Curated closed-class grammar (`gse_closed_class`) is
  authoritative in its scope.
- **Genus edge.**
  - A WordNet sense's genus is its hypernyms. Walk `hypernym_paths()` sorted by synset names: nltk's own order
    varies with PYTHONHASHSEED.
  - A Wiktionary sense's genus is the genus head that `definition_linker` parses from its gloss
    (`GSE/curation/build_clean_layer2.py`).
  - Where the genus word has several senses, the edge carries all of them as possibilities. Never pick one by
    frequency.
- **Differentia.** These are the gloss's other content words, each itself a defined entry.
- **The constraint.** A kind is its genus plus its differentia, compiled as one joint constraint across all 56
  banks at once:
  - every bank the differentia does not touch takes the genus's state, zeros included;
  - every bank the differentia touches takes the contribution of the differentia's own words.
  - Compile this into the existing constraint state (`resolution.resolve_dictionary`: GAC plus component
    enumeration), never a parallel solver.
- **Propagate.** Run to a fixpoint over the whole graph, repeating passes until nothing changes.
- **Contradictions.** A contradiction is a typed exception with both causes. It never silently overwrites.
  No stored value is ever changed.

## What to read first, in full

- `GSE/curation/build_clean_layer2.py` and `definition_linker`. Port the mechanism (genus and differentia parsing,
  composition over the grounded floor). Do not port the archived lexicon's values.
- `GSE/curation/lexicon_builder/resolution.py`, `specification.py`, `source_enrichment.revise_source_candidate`.
- `scripts/revise_lexicon_wordnet_identity.py` and `scripts/revise_lexicon_verbnet_do.py`. These are the
  sanctioned revision path: a private copy, conflicts recorded rather than stored, the catalog recomputed, then a
  full replay.
- `openspec/changes/lexicon-symbolic-foundation/design.md`, rules 1–5 and the founder corrections.

## Constraints (hard)

- No model decides any lexical value. You write code; the build computes every value.
- No thresholds, samples or votes admit anything. No hand-authored per-bank conventions as the path.
- Derived values are stored as their own derived channel, never as a stated source assertion. They must never be
  usable as confirmation of themselves.
- New code goes in new modules in `GSE/curation/lexicon_builder/` plus one revision script in `scripts/`, with
  tests.
- Pinned builder files and guard tests are read-only.
- Check pytest's real exit code: `echo "pytest exit $?"`, never through `| tail`. zsh does not split `$VAR`, so
  pass test lists with `$(cat file)`.
- Commit on `main` as you go, with no AI attribution in commit messages. Push.

## Run and deliver

1. **Candidate.** Start from `data/lexicon_builder/2026-11-12/sparse-release-022-verbnet-do.db` (live). Write a
   new output DB beside it. Do not touch `data/lexicon_active.json`.
2. **Measure, before and after:**
   - H as the sum of log2 |domain|, plus the joint count from `specification.py` where available;
   - singleton gains per spelling-frequency bucket (1–500, 501–1500, 1501–5000, 5001+, absent), using SUBTLEX
     through `scripts/build_word_senses.py`'s `subtlex_counts`;
   - contradiction counts by type.
3. **Rebuild word senses on the output.** Run:
   - `scripts/build_word_senses.py --candidate <out> --all`, then `--verify 300`;
   - the word-sense, guard and warrant tests with `GSE_SENSE_CANDIDATE`.
4. **Witness.** Run `/tmp/gse-senses/e2e2.py <out>`, or rebuild it from `GSEEncoder(db_path=...)`, on these
   sentences:
   - "The happy dog runs to his mother."
   - "She gave the boy a big lock."
   - "I want to know what you see."
   - "The sad man cut the rope."
   - "My friend loves the beautiful house."
5. **Write the receipt** to `docs/verification/2026-11-26-genus-differentia-closure.json`:
   - commands, input and output sha256, H before and after, per-bucket gains, contradictions, the witness
     readings, and test results.
6. **Final message.** Report exactly what was computed and measured. Report failures honestly.
